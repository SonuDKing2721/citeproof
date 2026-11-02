"""Low-cost evidence diagnostics kept separate from citation validity and diagnosis."""

import ast
import keyword
import re
from pathlib import PurePosixPath

from .models import Finding
from .repo import Repo, RepoError

MAX_BACKTICKED_IDENTIFIERS = 20
MAX_IDENTIFIER_LENGTH = 120
MAX_QUOTE_LEAK_LENGTH = 2000
_BACKTICKED = re.compile(r"`([^`\r\n]{1,120})`")
_FILE_SUFFIXES = {".cfg", ".css", ".html", ".ini", ".js", ".json", ".md", ".py", ".toml", ".ts", ".txt", ".yaml", ".yml"}
_IGNORED_IDENTIFIERS = {"None", "True", "False", "self", "cls"}


def _identifier_items(explanation: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in _BACKTICKED.finditer(explanation[:12000]):
        value = match.group(1).strip()
        if not value or len(value) > MAX_IDENTIFIER_LENGTH or value in seen:
            continue
        seen.add(value)
        normalized_path = value.replace("\\", "/")
        suffix = PurePosixPath(normalized_path).suffix.casefold()
        is_path = "/" in normalized_path or "\\" in value or suffix in _FILE_SUFFIXES
        if is_path:
            items.append((value, "path"))
            if len(items) >= MAX_BACKTICKED_IDENTIFIERS:
                break
            continue
        parts = value.split(".")
        if (
            value in _IGNORED_IDENTIFIERS
            or any(keyword.iskeyword(part) for part in parts)
            or not all(part.isidentifier() for part in parts)
        ):
            continue
        items.append((value, "symbol"))
        if len(items) >= MAX_BACKTICKED_IDENTIFIERS:
            break
    return items


def _repository_symbol_names(repo: Repo) -> set[str]:
    names: set[str] = set()
    files, _ = repo._python_files_with_status()
    for path in files:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError, ValueError):
            continue
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            names.add(node.name)
            qualified: list[str] = []
            current = node
            while current is not None:
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qualified.append(current.name)
                current = parents.get(current)
            names.add(".".join(reversed(qualified)))
    return names


def _path_exists(repo: Repo, path: str) -> bool:
    normalized = path.replace("\\", "/")
    try:
        repo._confined(normalized)
    except (RepoError, OSError, ValueError):
        return False
    return True


def diagnose_finding(repo: Repo, finding: Finding) -> dict:
    """Check backticked names and failed-quote echoes without scoring diagnosis truth."""
    identifiers = _identifier_items(finding.explanation)
    symbols = _repository_symbol_names(repo) if any(kind == "symbol" for _, kind in identifiers) else set()
    identifier_checks = []
    for value, kind in identifiers:
        exists = _path_exists(repo, value) if kind == "path" else value in symbols
        identifier_checks.append({
            "identifier": value,
            "kind": kind,
            "status": "resolved" if exists else "unresolved",
        })

    explanation = finding.explanation[:12000]
    quote_leaks = []
    for index, citation in enumerate(finding.citations[:4]):
        quote = citation.quote.strip()
        if not citation.valid and quote and quote[:MAX_QUOTE_LEAK_LENGTH] in explanation:
            quote_leaks.append({
                "citation_index": index,
                "outcome": (citation.outcome or "not_checked")[:80],
                "quote": quote[:MAX_QUOTE_LEAK_LENGTH],
            })
    return {
        "identifier_checks": identifier_checks,
        "unverified_quote_leaks": quote_leaks,
    }
