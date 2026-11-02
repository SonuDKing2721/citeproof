import html
import unittest

from citeproof.models import Citation, Finding
from citeproof.ui_components import evidence_panel_html, issue_comment_markdown, sentence_citation_anchors


class EvidencePanelTests(unittest.TestCase):
    def test_escapes_untrusted_path_symbol_source_lines_and_rejected_quote(self):
        citation = Citation(
            "src/<script>.py",
            "<img src=x>",
            1,
            1,
            "<script>alert('x')</script>",
            valid=False,
            outcome="quote_not_found",
        )

        panel = evidence_panel_html(
            citation,
            ["actual <tag> & text"],
            window_start=1,
            total_lines=1,
        )

        for untrusted in ("src/<script>.py", "<img src=x>", "actual <tag> & text", citation.quote):
            self.assertNotIn(untrusted, panel)
            self.assertIn(html.escape(untrusted), panel)
        self.assertIn("Rejected", panel)
        self.assertIn("Claimed quote", panel)

    def test_corrected_panel_shows_claimed_and_actual_lines_and_highlights_source(self):
        citation = Citation(
            "src/module.py", "convert", 2, 2, "return value.encode('utf-8')",
            valid=True,
            outcome="corrected_unique_exact_quote",
            claimed_start_line=2,
            claimed_end_line=2,
            corrected_start_line=4,
            corrected_end_line=4,
        )

        panel = evidence_panel_html(
            citation,
            ["header", "noise", "def convert(value):", "    return value.encode('utf-8')"],
            window_start=1,
            total_lines=4,
        )

        self.assertIn("Corrected", panel)
        self.assertIn("Claimed lines: 2-2 · actual lines: 4-4", panel)
        self.assertIn("cp-source-line-cited", panel)
        self.assertIn("value.encode", panel)

    def test_missing_source_panel_states_that_file_is_unavailable(self):
        citation = Citation("missing.py", "", 3, 3, "quoted source", outcome="path_missing")

        panel = evidence_panel_html(citation, None, window_start=1, total_lines=None)

        self.assertIn("Source file is unavailable in the current pinned checkout", panel)
        self.assertIn("Rejected", panel)


class EvidenceLinkTests(unittest.TestCase):
    def test_sentence_anchors_require_backticked_identifier_overlap_with_verified_citation(self):
        finding = Finding(
            "claim",
            "The `parse_value` helper decodes the input. It also logs the request.",
            [Citation("module.py", "parse_value", 1, 1, "def parse_value(value):", valid=True)],
        )

        sentences = sentence_citation_anchors(finding)

        self.assertEqual(sentences[0]["status"], "Direct citation anchor")
        self.assertEqual(sentences[0]["citation_indices"], [0])
        self.assertEqual(sentences[1]["status"], "No direct citation anchor")

    def test_issue_comment_links_verified_and_corrected_citations_at_pinned_commit(self):
        finding = Finding(
            "Convert fails",
            "The helper encodes the string.",
            [Citation(
                "src/a file.py", "convert", 3, 4, "quoted",
                valid=True,
                outcome="corrected_unique_exact_quote",
                corrected_start_line=8,
                corrected_end_line=9,
            )],
        )

        markdown = issue_comment_markdown(finding, "owner/repo", "abc123")

        self.assertIn("https://github.com/owner/repo/blob/abc123/src/a%20file.py#L8-L9", markdown)
        self.assertIn("Corrected", markdown)
        self.assertIn("does not prove the diagnosis is correct", markdown)

    def test_unpinned_manual_repository_does_not_get_a_fabricated_github_link(self):
        finding = Finding(
            "Possible cause",
            "Check `convert`.",
            [Citation("module.py", "convert", 1, 1, "quote", valid=True)],
        )

        markdown = issue_comment_markdown(finding, None, None)

        self.assertNotIn("github.com", markdown)
        self.assertIn("Pinned source link unavailable", markdown)


if __name__ == "__main__":
    unittest.main()
