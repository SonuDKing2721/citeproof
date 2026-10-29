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
