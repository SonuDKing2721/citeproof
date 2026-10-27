"""Read-only, bounded repository tools. All paths are confined to the selected root."""

import ast
import os
from pathlib import Path

IGNORED_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
MAX_FILES = 5000
MAX_FILE_BYTES = 256_000
MAX_MATCHES = 30


class RepoError(ValueError):
    pass


class Repo:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise RepoError("Repository path must be a folder.")

    def _confined(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve(strict=True)
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise RepoError("Path is outside the selected repository.") from exc
        if not candidate.is_file():
            raise RepoError("Path is not a file.")
        if candidate.stat().st_size > MAX_FILE_BYTES:
            raise RepoError(f"File exceeds the {MAX_FILE_BYTES}-byte read limit.")
        return candidate

    def python_files(self) -> list[Path]:
        result: list[Path] = []
        for current, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not (Path(current) / d).is_symlink()]
            for name in files:
                if name.endswith(".py"):
                    path = Path(current) / name
                    try:
                        path.resolve(strict=True).relative_to(self.root)
                    except (ValueError, OSError):
                        continue
                    if path.stat().st_size <= MAX_FILE_BYTES:
                        result.append(path)
                        if len(result) >= MAX_FILES:
                            return result
        return result

    def read_file(self, relative_path: str, start_line: int = 1, end_line: int = 160) -> str:
        if start_line < 1 or end_line < start_line or end_line - start_line > 200:
            raise RepoError("Read range must be 1–201 lines and start at line 1 or later.")
        path = self._confined(relative_path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = lines[start_line - 1 : end_line]
        return "\n".join(f"{i}: {line}" for i, line in enumerate(selected, start=start_line))

    def search_text(self, query: str) -> str:
        query = query.strip()
        if not query or len(query) > 120:
            raise RepoError("Search query must contain 1–120 characters.")
        hits: list[str] = []
        needle = query.casefold()
        for path in self.python_files():
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = path.relative_to(self.root).as_posix()
            for number, line in enumerate(lines, 1):
                if needle in line.casefold():
                    hits.append(f"{rel}:{number}: {line[:300]}")
                    if len(hits) >= MAX_MATCHES:
                        return "\n".join(hits)
        return "\n".join(hits) if hits else "No matching Python lines found."

    def find_symbols(self, query: str) -> str:
        query = query.strip().casefold()
        if not query or len(query) > 120:
            raise RepoError("Symbol query must contain 1–120 characters.")
        hits: list[str] = []
        for path in self.python_files():
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (OSError, SyntaxError, ValueError):
                continue
            rel = path.relative_to(self.root).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and query in node.name.casefold():
                    hits.append(f"{rel}:{node.lineno}: {type(node).__name__} {node.name}")
                    if len(hits) >= MAX_MATCHES:
                        return "\n".join(hits)
        return "\n".join(hits) if hits else "No matching Python symbols found."

    def source_lines(self, relative_path: str, start_line: int, end_line: int) -> list[str]:
        path = self._confined(relative_path)
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[start_line - 1 : end_line]

