import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
