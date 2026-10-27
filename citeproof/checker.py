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
            if ancestors:
                depth = min(len(qualifiers), len(ancestors))
                if qualifiers[-depth:] != ancestors[-depth:]:
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


def check_citation(repo: Repo, citation: Citation) -> Citation:
    try:
        path = repo._confined(citation.path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except (RepoError, OSError) as exc:
        citation.reason = str(exc)
        return citation
    if citation.start_line < 1 or citation.end_line < citation.start_line or citation.end_line > len(lines):
        citation.reason = "Line range is outside the file."
        return citation
    if citation.end_line - citation.start_line > 40:
        citation.reason = "Citation spans more than 41 lines."
        return citation
    if not citation.quote.strip():
        citation.reason = "Quote is empty."
        return citation
    cited = "\n".join(lines[citation.start_line - 1 : citation.end_line])
    if citation.quote.strip() not in cited:
        citation.reason = "Quoted text does not occur within the cited line range."
        return citation
    if citation.symbol:
        source = "\n".join(lines)
        if not _symbol_exists(source, citation.symbol):
            citation.reason = f"Symbol '{citation.symbol}' was not found in this file."
            return citation
        if not _symbol_contains_lines(source, citation.symbol, citation.start_line, citation.end_line):
            citation.reason = f"Cited lines fall outside symbol '{citation.symbol}'."
            return citation
    citation.valid = True
    citation.reason = "File, line range, quote, and symbol verified. This does not prove the diagnosis is correct."
    return citation


def check_result(repo: Repo, result: AgentResult) -> AgentResult:
    for finding in result.findings:
        finding.citations = [check_citation(repo, citation) for citation in finding.citations]
    return result
