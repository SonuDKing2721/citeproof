import unittest

from citeproof.comparison import compare_evidence
from citeproof.models import AgentResult, Citation, Finding


def result(name, citations, error=None):
    return AgentResult(name, [Finding("possible bug", "", citations)], [], error)


class EvidenceComparisonTests(unittest.TestCase):
    def test_reports_overlapping_validated_lines(self):
        first = result("A", [Citation("src/module.py", "convert", 10, 12, "left", True)])
        second = result("B", [Citation("src/module.py", "convert", 12, 14, "right", True)])

        comparison = compare_evidence([first, second])

        self.assertEqual(comparison.status, "overlapping_lines")
        self.assertEqual(comparison.shared_files, ["src/module.py"])
        self.assertEqual(comparison.overlapping_ranges, [("src/module.py", 12, 12)])

    def test_uses_corrected_ranges_instead_of_claimed_ranges(self):
        first_citation = Citation(
            "src/module.py", "convert", 10, 12, "left", True,
            outcome="corrected_unique_exact_quote",
            corrected_start_line=30, corrected_end_line=32,
        )
        second_citation = Citation(
            "src/module.py", "convert", 12, 14, "right", True,
            outcome="corrected_unique_exact_quote",
            corrected_start_line=40, corrected_end_line=42,
        )

        comparison = compare_evidence([
            result("A", [first_citation]),
            result("B", [second_citation]),
        ])

        self.assertEqual(comparison.status, "same_file")
        self.assertEqual(comparison.overlapping_ranges, [])

    def test_detects_overlap_at_corrected_ranges(self):
        first_citation = Citation(
            "src/module.py", "convert", 10, 12, "left", True,
            outcome="corrected_unique_exact_quote",
            corrected_start_line=30, corrected_end_line=32,
        )
        second_citation = Citation(
            "src/module.py", "convert", 50, 52, "right", True,
            outcome="corrected_unique_exact_quote",
            corrected_start_line=32, corrected_end_line=55,
        )

        comparison = compare_evidence([
            result("A", [first_citation]),
            result("B", [second_citation]),
        ])

        self.assertEqual(comparison.status, "overlapping_lines")
        self.assertEqual(comparison.overlapping_ranges, [("src/module.py", 32, 32)])

    def test_ignores_invalid_citations(self):
        first = result("A", [Citation("src/module.py", "convert", 10, 12, "bad", False)])
        second = result("B", [Citation("src/module.py", "convert", 10, 12, "bad", True)])

        comparison = compare_evidence([first, second])

        self.assertEqual(comparison.status, "no_verified_citations")
        self.assertEqual(comparison.shared_files, [])

    def test_reports_incomplete_when_an_agent_failed(self):
        first = result("A", [Citation("src/module.py", "convert", 10, 12, "ok", True)])
        second = AgentResult("B", [], [], "endpoint timeout")

        comparison = compare_evidence([first, second])

        self.assertEqual(comparison.status, "incomplete")


if __name__ == "__main__":
    unittest.main()
