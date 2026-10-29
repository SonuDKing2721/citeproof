import tempfile
import unittest
from pathlib import Path

from citeproof.models import AgentResult, Citation, Finding, VerificationReview
from citeproof.evaluation import build_run_report
from citeproof.presentation import (
    agent_result_card_status,
    citation_quote_details,
    make_run_snapshot,
    snapshot_from_saved_report,
    verification_from_payload,
)
from citeproof.repo import Repo


class CitationPresentationTests(unittest.TestCase):
    def test_agent_card_labels_all_rejected_citations_as_unverified(self):
        result = AgentResult(
            "Investigator A",
            [Finding("Possible cause", "Explanation", [Citation("module.py", "", 1, 1, "made up", valid=False)])],
            [],
        )

        content, description = agent_result_card_status(result)

        self.assertEqual(content, "1 finding returned · 0/1 citations verified")
        self.assertIn("unverified", description.lower())

    def test_keeps_rejected_model_quote_visible_with_clear_label(self):
        quote = "this line is not in the cited source"
        citation = Citation("src/module.py", "convert", 3, 3, quote, valid=False)

        label, displayed_quote = citation_quote_details(citation)

        self.assertEqual(label, "Rejected model quote")
        self.assertEqual(displayed_quote, quote)

    def test_labels_verified_source_quote(self):
        citation = Citation("src/module.py", "convert", 3, 3, "actual source", valid=True)

        label, displayed_quote = citation_quote_details(citation)

        self.assertEqual(label, "Verified source quote")
        self.assertEqual(displayed_quote, "actual source")

    def test_run_snapshot_retains_results_and_issue_context_across_reruns(self):
        results = [AgentResult("A", [], [])]
        gold_case = {"issue_id": "pallets/click#3449"}

        snapshot = make_run_snapshot(results, "abc123", "Issue title", gold_case)

        self.assertIs(snapshot["results"], results)
        self.assertEqual(snapshot["repo_commit"], "abc123")
        self.assertEqual(snapshot["issue_title"], "Issue title")
        self.assertEqual(snapshot["gold_case"], gold_case)

    def test_run_snapshot_retains_bounded_verification_result(self):
        review = VerificationReview(
            status="reviewed",
            assessment="insufficient_evidence",
            rationale="The checked lines do not distinguish the hypotheses.",
            model_requests=1,
        )

        snapshot = make_run_snapshot([], "abc123", "Issue", None, verification=review)

        self.assertIs(snapshot["verification"], review)

    def test_saved_verification_payload_is_bounded_and_rejects_bad_status_types(self):
        self.assertIsNone(verification_from_payload({"status": []}))
        review = verification_from_payload({
            "status": "reviewed",
            "assessment": [],
            "selected_finding_id": "A-F1" * 100,
            "supporting_evidence_ids": ["A-F1-C1", object(), "B-F1-C1"],
            "rationale": "x" * 2000,
            "model_requests": 900,
        })

        self.assertEqual(review.assessment, "not_run")
        self.assertEqual(review.selected_finding_id, "A-F1" * 10)
        self.assertEqual(review.supporting_evidence_ids, ["A-F1-C1", "B-F1-C1"])
        self.assertEqual(len(review.rationale), 1200)
        self.assertEqual(review.model_requests, 1)

    def test_cached_report_is_restored_only_for_matching_commit_and_citations_are_rechecked(self):
        gold_case = {"issue_id": "pallets/click#1"}
        report = {
            "schema": "citeproof-evaluation/v1",
            "issue_id": "pallets/click#1",
            "repository_commit": "abc123",
            "run_timestamp_utc": "2026-10-28T00:00:00+00:00",
            "model_id": "meta/muse-glimmer-30b",
            "provider": "NVIDIA API Catalog",
            "run_source": "live_verifier_on_cached_agent_pair",
            "model_requests": {"investigators": 9, "verification": 1, "total": 10},
            "agent_pair_source_timestamp_utc": "2026-10-28T00:00:00+00:00",
            "verifier_run_timestamp_utc": "2026-10-29T00:00:00+00:00",
            "verification": {
                "status": "reviewed",
                "assessment": "supports_candidate",
                "selected_finding_id": "A-F1",
                "supporting_evidence_ids": ["A-F1-C1"],
                "rationale": "Checked source supports this candidate.",
                "model_requests": 1,
            },
            "agents": [
                {
                    "name": "A",
                    "error": None,
                    "tool_trace": [],
                    "findings": [{
                        "claim": "A claim",
                        "explanation": "A source explanation",
                        "citations": [{
                            "path": "sample.py",
                            "symbol": "",
                            "start_line": 1,
                            "end_line": 1,
                            "quote": "needle = True",
                            "valid": False,
                            "reason": "Saved result is untrusted until rechecked.",
                        }],
                    }],
                },
                {"name": "B", "error": None, "tool_trace": [], "findings": []},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "sample.py").write_text("needle = True\n", encoding="utf-8")
            repo = Repo(tmp)
            repo.commit = "abc123"
            snapshot = snapshot_from_saved_report(report, gold_case, "Issue title", repo)

        self.assertEqual(snapshot["source"], "saved")
        self.assertEqual(snapshot["run_timestamp_utc"], "2026-10-28T00:00:00+00:00")
        self.assertEqual(snapshot["run_source"], "live_verifier_on_cached_agent_pair")
        self.assertEqual(snapshot["agent_pair_source_timestamp_utc"], "2026-10-28T00:00:00+00:00")
        self.assertEqual(snapshot["verification"].selected_finding_id, "A-F1")
        self.assertEqual(snapshot["model_request_counts"], {"investigators": 9, "verification": 1, "total": 10})
        self.assertFalse(snapshot["results"][0].model_requests_known)
        self.assertTrue(snapshot["results"][0].findings[0].citations[0].valid)
        restored_report = build_run_report(
            gold_case,
            snapshot["repo_commit"],
            snapshot["model_id"],
            snapshot["provider"],
            snapshot["results"],
            verification=snapshot["verification"],
            workflow_kind=snapshot["workflow_kind"],
            run_timestamp_utc=snapshot["run_timestamp_utc"],
            model_settings=snapshot["model_settings"],
            model_request_counts=snapshot["model_request_counts"],
        )
        self.assertEqual(restored_report["model_requests"], {"investigators": 9, "verification": 1, "total": 10})
        self.assertIsNone(restored_report["agents"][0]["model_requests"])

    def test_v2_saved_report_restores_provenance_timings_and_request_counts(self):
        report = {
            "schema": "citeproof-evaluation/v2",
            "issue_id": "pallets/click#1",
            "repository_commit": "abc123",
            "run_timestamp_utc": "2026-10-29T10:00:00+00:00",
            "model_id": "meta/muse-glimmer-30b",
            "provider": "NVIDIA API Catalog",
            "workflow": {
                "kind": "cached_pair_live_review",
                "run_timestamp_utc": "2026-10-29T10:00:00+00:00",
                "timings": {
                    "investigators_seconds": 24.5,
                    "verification_seconds": 2.25,
                    "baseline_seconds": None,
                    "total_seconds": 26.75,
                },
            },
            "model_settings": {
                "investigator": {
                    "model_id": "meta/muse-glimmer-30b",
                    "request_parameters": {"max_tokens": 8192, "temperature": 0.95},
                    "timeout_seconds": 120.0,
                },
                "verifier": {
                    "model_id": "meta/muse-glimmer-30b",
                    "request_parameters": {"max_tokens": 1800, "temperature": 0.2},
                    "timeout_seconds": 120.0,
                },
            },
            "diagnosis_review": {
                "status": "supported",
                "reviewer": "maintainer",
                "note": "Matches the issue and merged fix.",
            },
            "verification": {"status": "reviewed", "model_requests": 1},
            "model_requests": {"investigators": 7, "verification": 1, "total": 8},
            "agents": [
                {"name": "A", "model_requests": 3, "findings": []},
                {"name": "B", "model_requests": 4, "findings": []},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.commit = "abc123"
            snapshot = snapshot_from_saved_report(
                report,
                {"issue_id": "pallets/click#1"},
                "Issue title",
                repo,
            )

        self.assertEqual(snapshot["workflow_kind"], "cached_pair_live_review")
        self.assertEqual(snapshot["timings"]["total_seconds"], 26.75)
        self.assertEqual([item.model_requests for item in snapshot["results"]], [3, 4])
        self.assertEqual(snapshot["model_request_counts"], {"investigators": 7, "verification": 1, "total": 8})
        self.assertEqual(snapshot["model_settings"]["verifier"]["request_parameters"]["max_tokens"], 1800)
        self.assertEqual(snapshot["run_timestamp_utc"], "2026-10-29T10:00:00+00:00")
        self.assertEqual(snapshot["diagnosis_review"]["status"], "supported")

    def test_legacy_saved_report_without_timestamp_does_not_receive_a_fake_original_time(self):
        report = {
            "schema": "citeproof-evaluation/v1",
            "issue_id": "pallets/click#1",
            "repository_commit": "abc123",
            "agents": [{"name": "A", "findings": []}, {"name": "B", "findings": []}],
        }

        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.commit = "abc123"
            snapshot = snapshot_from_saved_report(report, {"issue_id": "pallets/click#1"}, "Issue", repo)

        self.assertIsNone(snapshot["run_timestamp_utc"])
        self.assertEqual(snapshot["workflow_kind"], "cached_demo")

    def test_cached_report_with_wrong_commit_is_rejected(self):
        report = {
            "schema": "citeproof-evaluation/v1",
            "issue_id": "pallets/click#1",
            "repository_commit": "wrong",
            "agents": [{"name": "A", "findings": []}, {"name": "B", "findings": []}],
        }

        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.commit = "abc123"
            with self.assertRaisesRegex(ValueError, "different repository commit"):
                snapshot_from_saved_report(report, {"issue_id": "pallets/click#1"}, "Issue", repo)


if __name__ == "__main__":
    unittest.main()
