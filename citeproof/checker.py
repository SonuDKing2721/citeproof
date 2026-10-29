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


def _citation_failure(lines: list[str], citation: Citation) -> str | None:
    if citation.start_line < 1 or citation.end_line < citation.start_line or citation.end_line > len(lines):
        return "Line range is outside the file."
    if citation.end_line - citation.start_line > 40:
        return "Citation spans more than 41 lines."
    if not citation.quote.strip():
        return "Quote is empty."
    cited = "\n".join(lines[citation.start_line - 1 : citation.end_line])
    if citation.quote.strip() not in cited:
        return "Quoted text does not occur within the cited line range."
    if citation.symbol:
        source = "\n".join(lines)
        if not _symbol_exists(source, citation.symbol):
            return f"Symbol '{citation.symbol}' was not found in this file."
        if not _symbol_contains_lines(source, citation.symbol, citation.start_line, citation.end_line):
            return f"Cited lines fall outside symbol '{citation.symbol}'."
    return None


def _unique_quote_range(lines: list[str], quote: str) -> tuple[int, int] | None:
    needle = quote.strip()
    if not needle:
        return None
    source = "\n".join(lines)
    first = source.find(needle)
    if first < 0 or source.find(needle, first + 1) >= 0:
        return None
    last = first + len(needle) - 1
    return source.count("\n", 0, first) + 1, source.count("\n", 0, last) + 1


def check_citation(repo: Repo, citation: Citation) -> Citation:
    try:
        path = repo._confined(citation.path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except (RepoError, OSError) as exc:
        citation.valid = False
        citation.reason = str(exc)
        return citation
    citation.valid = False
    original_range = (citation.start_line, citation.end_line)
    reason = _citation_failure(lines, citation)
    if reason is not None:
        exact_range = _unique_quote_range(lines, citation.quote)
        if (
            exact_range is not None
            and abs(exact_range[0] - citation.start_line) <= 2
            and abs(exact_range[1] - citation.end_line) <= 2
        ):
            citation.start_line, citation.end_line = exact_range
            repaired_reason = _citation_failure(lines, citation)
            if repaired_reason is None:
                citation.valid = True
                citation.reason = (
                    f"Unique exact quote; corrected line range from {original_range[0]}-{original_range[1]} "
                    f"to {exact_range[0]}-{exact_range[1]}. File, quote, and symbol verified. "
                    "This does not prove the diagnosis is correct."
                )
                return citation
            citation.start_line, citation.end_line = original_range
            reason = repaired_reason
    if reason is not None:
        citation.reason = reason
        return citation
    citation.valid = True
    citation.reason = "File, line range, quote, and symbol verified. This does not prove the diagnosis is correct."
    return citation


def check_result(repo: Repo, result: AgentResult) -> AgentResult:
    for finding in result.findings:
        finding.citations = [check_citation(repo, citation) for citation in finding.citations]
    return result
