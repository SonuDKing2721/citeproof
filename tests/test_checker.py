import tempfile
import unittest
from pathlib import Path

from citeproof.checker import check_citation
from citeproof.models import Citation
from citeproof.repo import MAX_FILE_BYTES, Repo


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
        self.assertEqual((checked.start_line, checked.end_line), (2, 3))
        self.assertEqual((checked.claimed_start_line, checked.claimed_end_line), (2, 3))
        self.assertEqual((checked.corrected_start_line, checked.corrected_end_line), (2, 2))
        self.assertEqual(checked.outcome, "corrected_unique_exact_quote")
        self.assertIn("unique exact quote", checked.reason.lower())

    def test_does_not_repair_ambiguous_exact_quotes(self):
        source = (
            "def first():\n    return 'same'\n\n\n"
            "def second():\n    return 'same'\n"
        )
        (self.root / "sample.py").write_text(source, encoding="utf-8")
        repo = Repo(self.root)
        ambiguous = Citation(
            path="sample.py", symbol="first", start_line=3, end_line=3,
            quote="    return 'same'",
        )
        checked_ambiguous = check_citation(repo, ambiguous)

        self.assertFalse(checked_ambiguous.valid)
        self.assertEqual(checked_ambiguous.outcome, "quote_match_ambiguous")
        self.assertEqual((checked_ambiguous.start_line, checked_ambiguous.end_line), (3, 3))


class CitationOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name) / "repo"
        self.root.mkdir()
        self.repo = Repo(self.root)
        (self.root / "sample.py").write_text(
            "def target():\n    return 'needle'\n\ndef other():\n    return 'other'\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def citation(self, **changes):
        values = {
            "path": "sample.py",
            "symbol": "",
            "start_line": 2,
            "end_line": 2,
            "quote": "return 'needle'",
        }
        values.update(changes)
        return Citation(**values)

    def assert_outcome(self, citation, outcome, valid):
        checked = check_citation(self.repo, citation)
        self.assertEqual(checked.outcome, outcome)
        self.assertEqual(checked.valid, valid)
        return checked

    def test_exact_quote_has_verified_exact_outcome(self):
        checked = self.assert_outcome(self.citation(), "verified_exact", True)
        self.assertEqual(checked.effective_range, (2, 2))

    def test_unique_quote_is_relocated_from_any_offset_without_losing_claim(self):
        lines = ["header"] + [f"filler_{index}" for index in range(1, 98)] + ["needle = True"]
        (self.root / "sample.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
        checked = self.assert_outcome(
            self.citation(start_line=1, end_line=1, quote="needle = True"),
            "corrected_unique_exact_quote",
            True,
        )
        self.assertEqual((checked.start_line, checked.end_line), (1, 1))
        self.assertEqual((checked.claimed_start_line, checked.claimed_end_line), (1, 1))
        self.assertEqual((checked.corrected_start_line, checked.corrected_end_line), (99, 99))
        self.assertEqual(checked.effective_range, (99, 99))

    def test_missing_path_has_path_missing_outcome(self):
        self.assert_outcome(self.citation(path="missing.py"), "path_missing", False)

    def test_outside_root_path_has_path_outside_repo_outcome(self):
        outside = Path(self.tempdir.name) / "outside.py"
        outside.write_text("needle = True\n", encoding="utf-8")
        self.assert_outcome(self.citation(path="../outside.py"), "path_outside_repo", False)

    def test_missing_outside_root_path_is_still_classified_as_outside(self):
        self.assert_outcome(
            self.citation(path="../missing-outside.py"),
            "path_outside_repo",
            False,
        )

    def test_symlink_citation_to_file_outside_repo_is_rejected(self):
        outside = Path(self.tempdir.name) / "outside_source.py"
        outside.write_text("needle = True\n", encoding="utf-8")
        link = self.root / "linked.py"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlinks are unavailable in this environment: {type(exc).__name__}")

        self.assert_outcome(self.citation(path="linked.py"), "path_outside_repo", False)

    def test_oversized_file_has_path_unreadable_outcome(self):
        (self.root / "large.py").write_bytes(b"x" * (MAX_FILE_BYTES + 1))
        self.assert_outcome(
            self.citation(path="large.py", quote="x"),
            "path_unreadable",
            False,
        )

    def test_invalid_line_range_has_invalid_range_outcome(self):
        checked = self.assert_outcome(
            self.citation(start_line=0, end_line=0, quote="absent"),
            "invalid_range",
            False,
        )
        self.assertEqual((checked.start_line, checked.end_line), (0, 0))

    def test_too_wide_range_has_range_too_wide_outcome(self):
        source = "\n".join(f"line_{index}" for index in range(1, 51)) + "\n"
        (self.root / "sample.py").write_text(source, encoding="utf-8")
        self.assert_outcome(
            self.citation(start_line=1, end_line=42, quote="not present"),
            "range_too_wide",
            False,
        )

    def test_empty_quote_has_empty_quote_outcome(self):
        self.assert_outcome(self.citation(quote="  \n "), "empty_quote", False)

    def test_rejects_pass_as_a_quote_too_short_to_support_a_location_claim(self):
        (self.root / "sample.py").write_text("def target():\n    pass\n", encoding="utf-8")

        self.assert_outcome(
            self.citation(start_line=2, end_line=2, quote="pass"),
            "quote_too_short",
            False,
        )

    def test_rejects_return_variable_as_a_quote_too_short_to_support_a_location_claim(self):
        (self.root / "sample.py").write_text("def target(value):\n    return x\n", encoding="utf-8")

        checked = self.assert_outcome(
            self.citation(start_line=2, end_line=2, quote="return x"),
            "quote_too_short",
            False,
        )

        self.assertIsNone(checked.corrected_start_line)

    def test_keeps_a_meaningful_one_line_quote_verified(self):
        source = "def target(value):\n    result = value.encode('utf-8')\n    return result\n"
        (self.root / "sample.py").write_text(source, encoding="utf-8")

        checked = self.assert_outcome(
            self.citation(start_line=2, end_line=2, quote="result = value.encode('utf-8')"),
            "verified_exact",
            True,
        )

        self.assertEqual(checked.effective_range, (2, 2))

    def test_absent_quote_has_quote_not_found_outcome(self):
        self.assert_outcome(self.citation(quote="not in the file"), "quote_not_found", False)

    def test_ambiguous_repair_has_quote_match_ambiguous_outcome(self):
        (self.root / "sample.py").write_text("header\nrepeat\nother\nrepeat\n", encoding="utf-8")
        self.assert_outcome(
            self.citation(start_line=1, end_line=1, quote="repeat"),
            "quote_match_ambiguous",
            False,
        )

    def test_missing_symbol_has_symbol_not_found_outcome(self):
        self.assert_outcome(
            self.citation(symbol="missing"),
            "symbol_not_found",
            False,
        )

    def test_quote_outside_symbol_has_symbol_range_mismatch_outcome(self):
        self.assert_outcome(
            self.citation(symbol="other"),
            "symbol_range_mismatch",
            False,
        )

    def test_unique_quote_outside_symbol_is_not_relocated_as_verified(self):
        checked = self.assert_outcome(
            self.citation(symbol="target", start_line=1, end_line=1, quote="return 'other'"),
            "symbol_range_mismatch",
            False,
        )
        self.assertIsNone(checked.corrected_start_line)
        self.assertIsNone(checked.corrected_end_line)

    def test_citation_captures_original_range_and_effective_range(self):
        citation = self.citation(start_line=7, end_line=9)
        self.assertEqual((citation.claimed_start_line, citation.claimed_end_line), (7, 9))
        self.assertEqual(citation.effective_range, (7, 9))


if __name__ == "__main__":
    unittest.main()
