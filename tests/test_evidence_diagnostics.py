import tempfile
import unittest
from pathlib import Path

from citeproof.models import Citation, Finding
from citeproof.repo import Repo


class EvidenceDiagnosticTests(unittest.TestCase):
    def test_checks_backticked_symbols_exactly_against_ast_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "module.py").write_text(
                "def parse_value(value):\n    return value\n\ndef parse_value_extra():\n    return None\n",
                encoding="utf-8",
            )
            finding = Finding(
                "claim",
                "The `parse_value` API calls `parse_val` before returning.",
                [],
            )

            from citeproof.evidence_diagnostics import diagnose_finding
            diagnostics = diagnose_finding(Repo(tmp), finding)

        self.assertEqual(diagnostics["identifier_checks"], [
            {"identifier": "parse_value", "kind": "symbol", "status": "resolved"},
            {"identifier": "parse_val", "kind": "symbol", "status": "unresolved"},
        ])

    def test_checks_repository_paths_and_ignores_inline_literals(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            Path(tmp, "checker.py").write_text("VALUE = 1\n", encoding="utf-8")
            Path(outside, ".env").write_text("SECRET_OUTSIDE_REPO\n", encoding="utf-8")
            finding = Finding(
                "claim",
                "The `checker.py` file handles `../../.env`; it returns `None` for `42` and `\"literal\"`.",
                [],
            )

            from citeproof.evidence_diagnostics import diagnose_finding
            diagnostics = diagnose_finding(Repo(tmp), finding)

        self.assertEqual(diagnostics["identifier_checks"], [
            {"identifier": "checker.py", "kind": "path", "status": "resolved"},
            {"identifier": "../../.env", "kind": "path", "status": "unresolved"},
        ])
        self.assertNotIn("SECRET_OUTSIDE_REPO", str(diagnostics))

    def test_flags_only_failed_quotes_that_are_repeated_in_the_explanation(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "module.py").write_text("value = 1\n", encoding="utf-8")
            finding = Finding(
                "claim",
                "The returned expression was `made_up_call(value)` and is not in the checked code.",
                [
                    Citation("module.py", "", 1, 1, "made_up_call(value)", outcome="quote_not_found"),
                    Citation("module.py", "", 1, 1, "value = 1", valid=True, outcome="verified_exact"),
                ],
            )

            from citeproof.evidence_diagnostics import diagnose_finding
            diagnostics = diagnose_finding(Repo(tmp), finding)

        self.assertEqual(diagnostics["unverified_quote_leaks"], [
            {"citation_index": 0, "outcome": "quote_not_found", "quote": "made_up_call(value)"},
        ])


if __name__ == "__main__":
    unittest.main()
