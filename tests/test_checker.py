import tempfile
import unittest
from pathlib import Path

from citeproof.checker import check_citation
from citeproof.models import Citation
from citeproof.repo import Repo


class CitationScopeTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.source = """class Target:
    def relevant(self):
        return 'expected'

def unrelated():
    return 'other'
"""
        (self.root / "sample.py").write_text(self.source, encoding="utf-8")
        self.repo = Repo(self.root)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_rejects_quote_outside_named_symbol(self):
        citation = Citation(
            path="sample.py",
            symbol="relevant",
            start_line=6,
            end_line=6,
            quote="    return 'other'",
        )

        checked = check_citation(self.repo, citation)

        self.assertFalse(checked.valid)
        self.assertIn("outside symbol", checked.reason)

    def test_accepts_quote_inside_named_symbol(self):
        citation = Citation(
            path="sample.py",
            symbol="relevant",
            start_line=3,
            end_line=3,
            quote="        return 'expected'",
        )

        checked = check_citation(self.repo, citation)

        self.assertTrue(checked.valid)

    def test_accepts_qualified_class_method_symbol(self):
        citation = Citation(
            path="sample.py",
            symbol="Target.relevant",
            start_line=3,
            end_line=3,
            quote="        return 'expected'",
        )

        checked = check_citation(self.repo, citation)

        self.assertTrue(checked.valid)


if __name__ == "__main__":
    unittest.main()
