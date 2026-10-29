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

    def test_rejects_partial_qualifier_that_names_wrong_nested_method(self):
        source = """class Outer:
    class Other:
        def run(self):
            return 'nested'
"""
        (self.root / "sample.py").write_text(source, encoding="utf-8")
        repo = Repo(self.root)
        citation = Citation(
            path="sample.py",
            symbol="Other.run",
            start_line=4,
            end_line=4,
            quote="            return 'nested'",
        )

        checked = check_citation(repo, citation)

        self.assertFalse(checked.valid)
        self.assertIn("not found in this file", checked.reason)

    def test_accepts_exactly_qualified_nested_method_symbol(self):
        source = """class Outer:
    class Other:
        def run(self):
            return 'nested'
"""
        (self.root / "sample.py").write_text(source, encoding="utf-8")
        repo = Repo(self.root)
        citation = Citation(
            path="sample.py",
            symbol="Outer.Other.run",
            start_line=4,
            end_line=4,
            quote="            return 'nested'",
        )

        checked = check_citation(repo, citation)

        self.assertTrue(checked.valid)

    def test_repairs_nearby_boundaries_for_a_unique_exact_quote(self):
        source = "def render():\n    return 'expected'\n"
        (self.root / "sample.py").write_text(source, encoding="utf-8")
        repo = Repo(self.root)
        citation = Citation(
            path="sample.py",
            symbol="render",
            start_line=2,
            end_line=3,
            quote="    return 'expected'",
        )

        checked = check_citation(repo, citation)

        self.assertTrue(checked.valid)
        self.assertEqual((checked.start_line, checked.end_line), (2, 2))
        self.assertIn("unique exact quote", checked.reason.lower())

    def test_does_not_repair_ambiguous_or_distant_exact_quotes(self):
        source = (
            "def first():\n    return 'same'\n\n\n"
            "def second():\n    return 'same'\n"
            + "\n" * 20
            + "def far():\n    return 'distant'\n"
        )
        (self.root / "sample.py").write_text(source, encoding="utf-8")
        repo = Repo(self.root)
        ambiguous = Citation(
            path="sample.py", symbol="first", start_line=3, end_line=3,
            quote="    return 'same'",
        )
        distant = Citation(
            path="sample.py", symbol="far", start_line=2, end_line=2,
            quote="    return 'distant'",
        )

        checked_ambiguous = check_citation(repo, ambiguous)
        checked_distant = check_citation(repo, distant)

        self.assertFalse(checked_ambiguous.valid)
        self.assertEqual((checked_ambiguous.start_line, checked_ambiguous.end_line), (3, 3))
        self.assertFalse(checked_distant.valid)
        self.assertEqual((checked_distant.start_line, checked_distant.end_line), (2, 2))


if __name__ == "__main__":
    unittest.main()
