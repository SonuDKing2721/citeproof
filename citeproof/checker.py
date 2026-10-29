"""Deterministic citation integrity checks; these do not prove diagnosis correctness."""

import ast
from pathlib import Path

from .models import AgentResult, Citation
from .repo import Repo, RepoError


def _symbol_nodes(source: str, symbol: str) -> list[ast.AST]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    parts = symbol.split(".")
    if not parts or any(not part for part in parts):
        return []
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    matching: list[ast.AST] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or node.name != parts[-1]:
            continue
        qualifiers = parts[:-1]
        if qualifiers:
            ancestors = []
            parent = parents.get(node)
            while parent is not None:
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    ancestors.append(parent.name)
                parent = parents.get(parent)
            ancestors.reverse()
            if qualifiers != ancestors:
                continue
        matching.append(node)
    return matching


def _symbol_exists(source: str, symbol: str) -> bool:
    return bool(_symbol_nodes(source, symbol))


def _symbol_contains_lines(source: str, symbol: str, start_line: int, end_line: int) -> bool:
    return any(
        node.lineno <= start_line
        and getattr(node, "end_lineno", 0) >= end_line
        for node in _symbol_nodes(source, symbol)
    )


def _range_outcome(start_line: int, end_line: int, line_count: int) -> str | None:
    if start_line < 1 or end_line < start_line or end_line > line_count:
        return "invalid_range"
    if end_line - start_line > 40:
        return "range_too_wide"
    return None


def _quote_ranges(lines: list[str], quote: str) -> list[tuple[int, int]]:
    needle = quote.strip()
    if not needle:
        return []
    source = "\n".join(lines)
    matches: list[tuple[int, int]] = []
    offset = 0
    while (first := source.find(needle, offset)) >= 0:
        last = first + len(needle) - 1
        matches.append((source.count("\n", 0, first) + 1, source.count("\n", 0, last) + 1))
        if len(matches) == 2:
            return matches
        offset = first + 1
    return matches


def _range_contains_quote(lines: list[str], start_line: int, end_line: int, quote: str) -> bool:
    invalid = _range_outcome(start_line, end_line, len(lines))
    if invalid is not None:
        return False
    cited = "\n".join(lines[start_line - 1 : end_line])
    return quote.strip() in cited


def _set_outcome(citation: Citation, outcome: str, reason: str, *, valid: bool = False) -> Citation:
    citation.valid = valid
    citation.outcome = outcome
    citation.reason = reason
    return citation


def check_citation(repo: Repo, citation: Citation) -> Citation:
    citation.valid = False
    citation.outcome = None
    citation.corrected_start_line = None
    citation.corrected_end_line = None
    try:
        path = repo._confined(citation.path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except RepoError as exc:
        outcome = exc.code or "path_unreadable"
        return _set_outcome(citation, outcome, str(exc))
    except OSError as exc:
        return _set_outcome(citation, "path_unreadable", str(exc))

    if not citation.quote.strip():
        return _set_outcome(citation, "empty_quote", "Quote is empty.")

    source = "\n".join(lines)
    symbol_nodes = _symbol_nodes(source, citation.symbol) if citation.symbol else []
    if citation.symbol and not symbol_nodes:
        return _set_outcome(
            citation,
            "symbol_not_found",
            f"Symbol '{citation.symbol}' was not found in this file.",
        )

    claimed_range_outcome = _range_outcome(citation.start_line, citation.end_line, len(lines))
    if claimed_range_outcome is None and _range_contains_quote(
        lines, citation.start_line, citation.end_line, citation.quote
    ):
        if not citation.symbol or any(
            node.lineno <= citation.start_line
            and getattr(node, "end_lineno", 0) >= citation.end_line
            for node in symbol_nodes
        ):
            return _set_outcome(
                citation,
                "verified_exact",
                "File, line range, quote, and symbol verified. This does not prove the diagnosis is correct.",
                valid=True,
            )

    matches = _quote_ranges(lines, citation.quote)
    if len(matches) > 1:
        return _set_outcome(
            citation,
            "quote_match_ambiguous",
            "The exact quote occurs more than once in this file; its corrected range is ambiguous.",
        )
    if not matches:
        if claimed_range_outcome is not None:
            reasons = {
                "invalid_range": "Line range is outside the file.",
                "range_too_wide": "Citation spans more than 41 lines.",
            }
            return _set_outcome(citation, claimed_range_outcome, reasons[claimed_range_outcome])
        if citation.symbol and not any(
            node.lineno <= citation.start_line
            and getattr(node, "end_lineno", 0) >= citation.end_line
            for node in symbol_nodes
        ):
            return _set_outcome(
                citation,
                "symbol_range_mismatch",
                f"Cited lines fall outside symbol '{citation.symbol}'.",
            )
        return _set_outcome(
            citation,
            "quote_not_found",
            "Quoted text does not occur in this file.",
        )

    corrected_range = matches[0]
    corrected_range_outcome = _range_outcome(*corrected_range, len(lines))
    if corrected_range_outcome is not None:
        reason = (
            "Citation spans more than 41 lines."
            if corrected_range_outcome == "range_too_wide"
            else "Line range is outside the file."
        )
        return _set_outcome(citation, corrected_range_outcome, reason)
    if citation.symbol and not any(
        node.lineno <= corrected_range[0]
        and getattr(node, "end_lineno", 0) >= corrected_range[1]
        for node in symbol_nodes
    ):
        return _set_outcome(
            citation,
            "symbol_range_mismatch",
            f"Quoted lines fall outside symbol '{citation.symbol}'.",
        )

    citation.corrected_start_line, citation.corrected_end_line = corrected_range
    original = citation.claimed_start_line, citation.claimed_end_line
    return _set_outcome(
        citation,
        "corrected_unique_exact_quote",
        f"Unique exact quote; corrected line range from {original[0]}-{original[1]} "
        f"to {corrected_range[0]}-{corrected_range[1]}. File, quote, and symbol verified. "
        "This does not prove the diagnosis is correct.",
        valid=True,
    )


def check_result(repo: Repo, result: AgentResult) -> AgentResult:
    for finding in result.findings:
        finding.citations = [check_citation(repo, citation) for citation in finding.citations]
    return result
