"""Bounded, content-free summaries of repository tool calls."""

import json
import re
from typing import Any

_ALLOWED_TOOLS = {"find_symbols", "read_file", "search_text"}
_SOURCE_LINE = re.compile(r"^\s*\d+:\s", re.MULTILINE)
_SEARCH_HIT = re.compile(r"^[^:\r\n]+:\d+:\s", re.MULTILINE)
_SYMBOL_HIT = re.compile(r"^[^:\r\n]+:\d+-\d+:\s", re.MULTILINE)
_SECRET = re.compile(
    r"(?i)(?:nvapi-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|"
    r"(?:api[_ -]?key|token|secret|password)\s*[:=]\s*[^\s,;]+)"
)
_ABSOLUTE_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:[/\\][^\s]+")
_COUNT = r"(?:0|[1-9][0-9]{0,5})"
_SAFE_RESULTS = {
    "read_file": re.compile(rf"^Read {_COUNT} source lines; source text withheld\.$"),
    "search_text": re.compile(rf"^Found {_COUNT} matching source lines; contents withheld\.$"),
    "find_symbols": re.compile(rf"^Found {_COUNT} matching symbols; source text withheld\.$"),
}


def _redact(value: str) -> str:
    value = _SECRET.sub("[redacted]", value)
    return _ABSOLUTE_WINDOWS_PATH.sub("[local path]", value)


def normalize_trace_event(value: Any) -> dict[str, str] | None:
    """Accept only bounded summaries with fixed, source-free result forms."""
    if not isinstance(value, dict) or set(value) != {"tool", "request_summary", "result_summary"}:
        return None
    tool = value.get("tool")
    request = value.get("request_summary")
    result = value.get("result_summary")
    if not isinstance(tool, str) or not isinstance(request, str) or not isinstance(result, str):
        return None
    if tool not in {*_ALLOWED_TOOLS, "rejected"} or len(request) > 220 or len(result) > 160:
        return None
    if any(ord(char) < 32 and char not in "\t" for char in request + result):
        return None
    request = _redact(" ".join(request.split()))
    if tool == "rejected":
        if not request.startswith("Tool rejected:") or result != "No source result stored.":
            return None
    elif tool == "read_file":
        if request == "Repository path rejected.":
            pass
        else:
            match = re.fullmatch(r"(.+):([1-9][0-9]{0,8})-([1-9][0-9]{0,8})", request)
            if not match:
                return None
            path = match.group(1).replace("\\", "/")
            if path.startswith("/") or re.match(r"^[A-Za-z]:", path) or any(
                part in {"", ".", ".."} for part in path.split("/")
            ):
                return None
            request = f"{path}:{match.group(2)}-{match.group(3)}"
    elif tool == "search_text" and not request.startswith("query: "):
        return None
    elif tool == "find_symbols" and not request.startswith("symbol: "):
        return None
    if tool != "rejected" and result != "Tool result withheld after an error." and not _SAFE_RESULTS[tool].fullmatch(result):
        return None
    return {"tool": tool, "request_summary": request[:220], "result_summary": result}


def normalize_trace_events(value: Any, *, max_events: int = 100) -> tuple[list[dict[str, str]], bool]:
    """Validate an entire persisted event list; malformed lists become unknown."""
    if not isinstance(value, list) or len(value) > max_events:
        return [], False
    events = [normalize_trace_event(item) for item in value]
    if any(event is None for event in events):
        return [], False
    return [event for event in events if event is not None], True


def _clean(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value).replace("\x00", "").split())
    return text[:limit]


def make_trace_event(tool_name: str, raw_arguments: str | dict, tool_result: str) -> dict[str, str]:
    """Summarize request and result without retaining repository excerpts."""
    if tool_name not in _ALLOWED_TOOLS:
        return {
            "tool": "rejected",
            "request_summary": f"Tool rejected: {_clean(tool_name, 40)}",
            "result_summary": "No source result stored.",
        }
    try:
        arguments = raw_arguments if isinstance(raw_arguments, dict) else json.loads(raw_arguments or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        arguments = None

    if not isinstance(arguments, dict):
        request_summary = "Request arguments could not be parsed."
    elif tool_name == "read_file":
        path = _clean(arguments.get("path", ""), 180).replace("\\", "/")
        start = arguments.get("start_line")
        end = arguments.get("end_line")
        if path.startswith("/") or re.match(r"^[A-Za-z]:", path) or ".." in path.split("/"):
            request_summary = "Repository path rejected."
        elif isinstance(start, int) and not isinstance(start, bool) and isinstance(end, int) and not isinstance(end, bool):
            request_summary = f"{path}:{start}-{end}"[:220]
        else:
            request_summary = f"{path}: line range unavailable"[:220]
    else:
        key = "query"
        label = "query" if tool_name == "search_text" else "symbol"
        request_summary = f"{label}: {_clean(arguments.get(key, ''), 80)}"

    result = str(tool_result or "")[:20000]
    if result.startswith("Tool error:"):
        result_summary = "Tool result withheld after an error."
    elif tool_name == "read_file":
        count = len(_SOURCE_LINE.findall(result))
        result_summary = f"Read {count} source lines; source text withheld."
    elif tool_name == "search_text":
        count = len(_SEARCH_HIT.findall(result))
        result_summary = f"Found {count} matching source lines; contents withheld."
    else:
        count = len(_SYMBOL_HIT.findall(result))
        result_summary = f"Found {count} matching symbols; source text withheld."

    event = {
        "tool": tool_name,
        "request_summary": request_summary[:220],
        "result_summary": result_summary[:160],
    }
    normalized = normalize_trace_event(event)
    return normalized or {
        "tool": "rejected",
        "request_summary": "Tool rejected: unsafe summary",
        "result_summary": "No source result stored.",
    }
