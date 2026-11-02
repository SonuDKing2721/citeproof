import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from citeproof.repo import Repo


class QualifiedSymbolSearchTests(unittest.TestCase):
    def test_finds_method_by_qualified_name_and_reports_its_span(self):
        source = """class Path:
    def convert(self, value):
        return value

    def unrelated(self):
        return None
"""
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "sample.py").write_text(source, encoding="utf-8")

            results = Repo(tmp).find_symbols("Path.convert")

        self.assertIn("sample.py:2-3: FunctionDef Path.convert", results)
        self.assertNotIn("unrelated", results)


class RepositoryScanBudgetTests(unittest.TestCase):
    def test_file_and_directory_symlinks_cannot_expose_outside_source(self):
        with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as outside_dir:
            root = Path(root_dir)
            outside = Path(outside_dir)
            secret_file = outside / "secret.py"
            secret_file.write_text("SECRET_OUTSIDE_REPO = True\n", encoding="utf-8")
            secret_directory = outside / "private"
            secret_directory.mkdir()
            (secret_directory / "module.py").write_text("PRIVATE_MARKER = True\n", encoding="utf-8")
            try:
                (root / "linked_file.py").symlink_to(secret_file)
                (root / "linked_directory").symlink_to(secret_directory, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"Symlinks are unavailable in this environment: {type(exc).__name__}")

            repo = Repo(root)
            self.assertNotIn("linked_file.py", {path.relative_to(root).as_posix() for path in repo.python_files()})
            self.assertNotIn("linked_directory/module.py", {path.relative_to(root).as_posix() for path in repo.python_files()})
            self.assertNotIn("SECRET_OUTSIDE_REPO", repo.search_text("SECRET_OUTSIDE_REPO"))
            self.assertNotIn("PRIVATE_MARKER", repo.search_text("PRIVATE_MARKER"))
            with self.assertRaisesRegex(ValueError, "outside the selected repository"):
                repo.read_file("linked_file.py")
            with self.assertRaisesRegex(ValueError, "outside the selected repository"):
                repo.read_file("linked_directory/module.py")

    def test_preseed_searches_error_text_and_matches_only_repo_python_basenames(self):
        issue = '''Traceback (most recent call last):
  File "../../.env", line 1, in leak
  File "/repo/pkg/parser.py", line 12, in parse
ValueError: stream is already closed
'''
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            Path(tmp, "pkg").mkdir()
            Path(tmp, "pkg", "parser.py").write_text(
                "def parse():\n    raise ValueError('stream is already closed')\n",
                encoding="utf-8",
            )
            Path(tmp, "other.py").write_text("value = 'unrelated'\n", encoding="utf-8")
            Path(outside, ".env").write_text("SECRET_OUTSIDE_REPO\n", encoding="utf-8")

            result = Repo(tmp).preseed_issue(issue)

        self.assertIn("Error text hit: pkg/parser.py:2", result)
        self.assertIn("Traceback file match: pkg/parser.py", result)
        self.assertNotIn("SECRET_OUTSIDE_REPO", result)
        self.assertNotIn("../../.env", result)

    def test_preseed_prioritizes_reproducer_api_definition_over_test_harness_frame(self):
        issue = '''```python
from click import echo_via_pager
from click.testing import CliRunner

def cli():
    echo_via_pager("Hello")

CliRunner().invoke(cli)
```
Traceback (most recent call last):
  File "/workspace/src/click/testing.py", line 676, in invoke
ValueError: I/O operation on closed file
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "click").mkdir(parents=True)
            (root / "src" / "click" / "testing.py").write_text(
                "class CliRunner:\n    def invoke(self):\n        return None\n",
                encoding="utf-8",
            )
            (root / "src" / "click" / "termui.py").write_text(
                "def echo_via_pager(text):\n    return text\n",
                encoding="utf-8",
            )

            result = Repo(root).preseed_issue(issue)

        self.assertIn("Reproducer API candidate: src/click/termui.py:1-2", result)
        self.assertNotIn("Traceback file match: src/click/testing.py", result)
        self.assertNotIn("tests/test_termui.py", result)

    def test_preseed_finds_reproducer_api_without_traceback_clues(self):
        issue = '''```python
from pkg.api import public_api

public_api("value")
```'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "pkg", "api.py")
            path.parent.mkdir(parents=True)
            path.write_text("def public_api(value):\n    return value\n", encoding="utf-8")

            result = Repo(tmp).preseed_issue(issue)

        self.assertIn("Reproducer API candidate: pkg/api.py:1-2", result)

    def test_preseed_respects_hit_and_character_limits(self):
        issue = "ValueError: " + ("x" * 80)
        with tempfile.TemporaryDirectory() as tmp:
            for index in range(30):
                Path(tmp, f"sample_{index}.py").write_text("x" * 80 + "\n", encoding="utf-8")

            result = Repo(tmp).preseed_issue(issue, max_hits=5, max_chars=240)

        self.assertLessEqual(len(result), 240)
        self.assertLessEqual(result.count("Error text hit:"), 5)

    def test_preseed_stops_reading_files_after_reaching_hit_limit(self):
        issue = "ValueError: unique phrase for a bounded scan"
        with tempfile.TemporaryDirectory() as tmp:
            for index in range(20):
                Path(tmp, f"sample_{index}.py").write_text(
                    "raise ValueError('unique phrase for a bounded scan')\n",
                    encoding="utf-8",
                )

            read_names = []
            original_read_text = Path.read_text

            def tracked_read_text(path, *args, **kwargs):
                read_names.append(path.name)
                return original_read_text(path, *args, **kwargs)

            with patch.object(Path, "read_text", tracked_read_text):
                Repo(tmp).preseed_issue(issue, max_hits=1)

        self.assertEqual(read_names, ["sample_0.py"])

    def test_search_labels_partial_results_when_total_source_budget_is_reached(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.py").write_text("needle\n", encoding="utf-8")
            Path(tmp, "b.py").write_text("needle\n", encoding="utf-8")

            with patch("citeproof.repo.MAX_TOTAL_SOURCE_BYTES", 8, create=True):
                results = Repo(tmp).search_text("needle")

        self.assertIn("a.py:1", results)
        self.assertIn("incomplete", results.lower())
        self.assertNotIn("b.py:1", results)

    def test_symbol_search_labels_partial_results_when_total_source_budget_is_reached(self):
        source = "def helper():\n    return 1\n"
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.py").write_text(source, encoding="utf-8")
            Path(tmp, "b.py").write_text(source, encoding="utf-8")

            with patch("citeproof.repo.MAX_TOTAL_SOURCE_BYTES", len(source.encode()) + 10):
                results = Repo(tmp).find_symbols("helper")

        self.assertIn("a.py:1-2", results)
        self.assertIn("incomplete", results.lower())
        self.assertNotIn("b.py:1-2", results)

    def test_search_labels_results_capped_at_match_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "sample.py").write_text("needle\nneedle\n", encoding="utf-8")

            with patch("citeproof.repo.MAX_MATCHES", 1):
                results = Repo(tmp).search_text("needle")

        self.assertIn("result limit", results.lower())
        self.assertIn("more matches may exist", results.lower())


if __name__ == "__main__":
    unittest.main()
