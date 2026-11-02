"""Generate small-sample comparison tables from saved Citeproof reports."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Iterable


START_MARKER = "<!-- citeproof-benchmarks:start -->"
END_MARKER = "<!-- citeproof-benchmarks:end -->"
COMPARISON_SCHEMAS = {"citeproof-budget-comparison/v1", "citeproof-budget-comparison/v2"}
DOCUMENTS = (Path("README.md"), Path("docs/RELATED_WORK_AND_GAP_REVIEW.md"))
ISSUE_ID_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)#([0-9]+)$")


def select_latest_by_issue(reports: Iterable[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    """Return the newest report per issue, with stable filename tie-breaking."""
    newest: dict[str, tuple[str, dict[str, Any], str]] = {}
    for source, report in reports:
        issue_id = report.get("issue_id")
        if not isinstance(issue_id, str) or not issue_id.strip():
            issue_id = f"unknown:{source}"
        raw_timestamp = report.get("run_timestamp_utc")
        timestamp = _timestamp_sort_key(raw_timestamp)
        previous = newest.get(issue_id)
        if previous is None or (timestamp, source) > (previous[0], previous[2]):
            newest[issue_id] = (timestamp, report, source)
    return [
        (source, report)
        for _, report, source in sorted(
            newest.values(),
            key=lambda item: (
                str(item[1].get("issue_id", "unknown")).casefold(),
                item[2].casefold(),
            ),
        )
    ]


def _timestamp_sort_key(value: object) -> str:
    if not isinstance(value, str):
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        return parsed.isoformat()
    return parsed.astimezone().isoformat()


def _issue_markdown(issue_id: object) -> str:
    if not isinstance(issue_id, str):
        return "Unknown issue"
    match = ISSUE_ID_RE.fullmatch(issue_id)
    if not match:
        return "Unknown issue"
    owner, repo, number = match.groups()
    safe_id = f"{owner}/{repo}#{number}"
    return f"[{safe_id}](https://github.com/{owner}/{repo}/issues/{number})"


def _request_count(side: object) -> str:
    if not isinstance(side, dict):
        return "unknown requests"
    value = side.get("model_requests")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return f"{value} requests"
    return "unknown requests"


def _localization_text(side: object) -> str:
    if not isinstance(side, dict):
        return "unknown requests; not scored (unknown)"
    requests = _request_count(side)
    localization = side.get("localization")
    if not isinstance(localization, dict):
        return f"{requests} · not scored (unknown)"
    status = localization.get("status")
    if status != "complete":
        display_status = status if status in {"incomplete", "missing_gold_labels"} else "unknown"
        if display_status == "missing_gold_labels":
            display_status = "missing labels"
        return f"{requests}; not scored ({display_status})"
    hit = localization.get("primary_hit_at_1")
    hit_text = "HIT" if hit is True else "MISS" if hit is False else "not scored"
    recall = localization.get("gold_file_recall_at_3")
    if (
        isinstance(recall, (int, float))
        and not isinstance(recall, bool)
        and 0 <= recall <= 1
    ):
        recall_text = f"{recall:.0%}"
    else:
        recall_text = "not scored"
    return f"{requests}; hit@1 {hit_text}; recall@3 {recall_text}"


def _is_complete_and_matched(report: dict[str, Any]) -> bool:
    """Whether the workflow completed with equal request counts, independent of scoring."""
    return report.get("status") == "complete" and report.get("budget_matched") is True


def render_benchmark_summary(reports: Iterable[dict[str, Any]]) -> str:
    """Render latest-per-issue small-sample results without accuracy claims."""
    report_list = list(reports)
    selected = select_latest_by_issue((str(index), report) for index, report in enumerate(report_list))
    total = len(selected)
    complete = sum(_is_complete_and_matched(report) for _, report in selected)
    incomplete = total - complete
    lines = [
        (
            f"Latest comparison per issue: {complete}/{total} workflows completed with matched request budgets; "
            f"{incomplete}/{total} were incomplete or unmatched. Localization may still be unscored. "
            "Diagnosis correctness: not scored. These counts describe a small smoke-case set, not model accuracy."
        ),
        "",
        "| Issue | Two-agent pair | Single-agent baseline | Comparison state |",
        "| --- | --- | --- | --- |",
    ]
    if not selected:
        lines.append("| No comparison reports found | not scored | not scored | no data |")
        return "\n".join(lines)

    for _, report in selected:
        pair = report.get("pair")
        baseline = report.get("baseline")
        issue = _issue_markdown(report.get("issue_id"))
        is_complete = _is_complete_and_matched(report)
        run_status = "run complete; budget matched" if is_complete else "incomplete or unmatched"
        lines.append(
            "| "
            + " | ".join((
                issue,
                _localization_text(pair),
                _localization_text(baseline),
                run_status,
            ))
            + " |"
        )
    return "\n".join(lines)


def load_comparison_reports(
    directory: Path,
    *,
    provider_filter: str | None = "NVIDIA API Catalog",
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*comparison*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read comparison report {path.name}: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("schema") not in COMPARISON_SCHEMAS:
            raise ValueError(f"Comparison report {path.name} has an unsupported schema.")
        provider = raw.get("provider")
        if provider_filter is not None and provider is not None and provider != provider_filter:
            continue
        report = dict(raw)
        report["_source_file"] = path.name
        reports.append(report)
    return reports


def replace_marked_block(document: str, content: str) -> str:
    if document.count(START_MARKER) != 1 or document.count(END_MARKER) != 1:
        raise ValueError("Document must contain each generated benchmark marker exactly once.")
    start = document.index(START_MARKER)
    end = document.index(END_MARKER)
    if end <= start:
        raise ValueError("Generated benchmark markers are out of order.")
    return (
        document[: start + len(START_MARKER)]
        + "\n"
        + content.strip()
        + "\n"
        + document[end:]
    )


def refresh_documents(root: Path, *, check: bool = False) -> tuple[int, list[str]]:
    reports = load_comparison_reports(root / "data" / "benchmarks")
    generated = render_benchmark_summary(reports)
    stale: list[str] = []
    for relative in DOCUMENTS:
        path = root / relative
        original = path.read_text(encoding="utf-8")
        updated = replace_marked_block(original, generated)
        if original == updated:
            continue
        stale.append(relative.as_posix())
        if not check:
            path.write_text(updated, encoding="utf-8", newline="\n")
    if check:
        return (1 if stale else 0), stale
    return 0, stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate comparison tables from saved Citeproof reports.")
    parser.add_argument("--check", action="store_true", help="Exit nonzero if generated blocks are stale.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        code, changed = refresh_documents(args.root.resolve(), check=args.check)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Report generation failed: {exc}\n")
    if args.check:
        if changed:
            print("Stale generated benchmark blocks: " + ", ".join(changed))
        else:
            print("Generated benchmark blocks are current.")
    elif changed:
        print("Updated generated benchmark blocks: " + ", ".join(changed))
    else:
        print("Generated benchmark blocks are already current.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
