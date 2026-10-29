import tempfile
import unittest
from pathlib import Path

from citeproof.models import AgentResult, Citation, Finding, VerificationReview
from citeproof.evaluation import build_run_report
from citeproof.presentation import (
    agent_result_card_status,
    citation_range_details,
    citation_quote_details,
    finding_citation_summary,
    make_run_snapshot,
    snapshot_from_saved_report,
    verification_from_payload,
)
from citeproof.repo import Repo


class CitationPresentationTests(unittest.TestCase):
    def test_finding_citation_summary_has_all_four_states(self):
        self.assertEqual(finding_citation_summary(Finding("claim", "", [])), "no_citations")
        self.assertEqual(
            finding_citation_summary(Finding("claim", "", [Citation("a.py", "", 1, 1, "x", outcome="quote_not_found")])),
            "none_verified",
        )
        self.assertEqual(
            finding_citation_summary(Finding("claim", "", [
                Citation("a.py", "", 1, 1, "x", outcome="verified_exact"),
                Citation("b.py", "", 1, 1, "y", outcome="quote_not_found"),
            ])),
            "partly_verified",
        )
        self.assertEqual(
            finding_citation_summary(Finding("claim", "", [
                Citation("a.py", "", 1, 1, "x", outcome="verified_exact"),
                Citation("b.py", "", 1, 1, "y", outcome="corrected_unique_exact_quote"),
            ])),
            "all_verified",
        )

    def test_corrected_citation_range_details_keep_claim_and_correction_distinct(self):
        citation = Citation(
            "a.py", "", 2, 3, "x", outcome="corrected_unique_exact_quote",
            claimed_start_line=2, claimed_end_line=3,
            corrected_start_line=2, corrected_end_line=2,
        )

        details = citation_range_details(citation)

        self.assertIn("Claimed range: 2-3", details)
        self.assertIn("Corrected range: 2-2", details)

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
                            "claimed_start_line": 1,
                            "claimed_end_line": 1,
                            "corrected_start_line": 2,
                            "corrected_end_line": 2,
                            "quote": "needle = True",
                            "valid": False,
                            "reason": "Saved result is untrusted until rechecked.",
                            "outcome": "path_outside_repo",
                        }],
                    }],
                },
                {"name": "B", "error": None, "tool_trace": [], "findings": []},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "sample.py").write_text("header\nneedle = True\n", encoding="utf-8")
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
        self.assertEqual(snapshot["results"][0].findings[0].citations[0].outcome, "corrected_unique_exact_quote")
        self.assertEqual(snapshot["results"][0].findings[0].citations[0].claimed_start_line, 1)
        self.assertEqual(snapshot["results"][0].findings[0].citations[0].corrected_start_line, 2)
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
            report_schema=snapshot["report_schema"],
            ranking_method=snapshot["ranking_method"],
            preserved_investigator_localization=snapshot["saved_investigator_localization"],
        )
        self.assertEqual(restored_report["schema"], "citeproof-evaluation/v1")
        self.assertNotIn("ranking_method", restored_report)
        self.assertNotIn("investigator_localization", restored_report)
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
        self.assertEqual(snapshot["report_schema"], "citeproof-evaluation/v2")
        self.assertIsNone(snapshot["ranking_method"])
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

    def test_v1_and_v2_exports_keep_their_schema_without_invented_ranking_metrics(self):
        for schema in ("citeproof-evaluation/v1", "citeproof-evaluation/v2"):
            with self.subTest(schema=schema), tempfile.TemporaryDirectory() as tmp:
                repo = Repo(tmp)
                repo.commit = "abc123"
                report = {
                    "schema": schema,
                    "issue_id": "pallets/click#1",
                    "repository_commit": "abc123",
                    "agents": [{"name": "A", "findings": []}, {"name": "B", "findings": []}],
                }
                snapshot = snapshot_from_saved_report(report, {"issue_id": "pallets/click#1"}, "Issue", repo)
                restored = build_run_report(
                    {"issue_id": "pallets/click#1", "primary_files": ["src/click.py"]},
                    "abc123",
                    "model",
                    "provider",
                    snapshot["results"],
                    report_schema=snapshot["report_schema"],
                    ranking_method=snapshot["ranking_method"],
                    preserved_investigator_localization=snapshot["saved_investigator_localization"],
                )

                self.assertEqual(restored["schema"], schema)
                self.assertNotIn("ranking_method", restored)
                self.assertNotIn("investigator_localization", restored)

    def test_v3_saved_report_preserves_ranking_and_metrics_but_rechecks_citations(self):
        ranking = [
            {
                "name": "A",
                "status": "complete",
                "ranked_files": ["stored-rank.py"],
                "primary_hit_at_1": False,
                "primary_file_reciprocal_rank": 0.25,
                "gold_file_recall_at_3": 0.5,
            },
            {
                "name": "B",
                "status": "complete",
                "ranked_files": [],
                "primary_hit_at_1": False,
                "primary_file_reciprocal_rank": 0,
                "gold_file_recall_at_3": 0,
            },
        ]
        report = {
            "schema": "citeproof-evaluation/v3",
            "ranking_method": "finding_order_descending_plausibility",
            "investigator_localization": ranking,
            "issue_id": "pallets/click#1",
            "repository_commit": "abc123",
            "agents": [
                {
                    "name": "A",
                    "findings": [{
                        "claim": "A claim",
                        "citations": [{
                            "path": "sample.py",
                            "symbol": "",
                            "start_line": 1,
                            "end_line": 1,
                            "claimed_start_line": 1,
                            "claimed_end_line": 1,
                            "corrected_start_line": 200,
                            "corrected_end_line": 200,
                            "quote": "needle = True",
                            "valid": False,
                            "outcome": "path_outside_repo",
                        }],
                    }],
                },
                {"name": "B", "findings": []},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "sample.py").write_text("header\nneedle = True\n", encoding="utf-8")
            repo = Repo(tmp)
            repo.commit = "abc123"
            snapshot = snapshot_from_saved_report(report, {"issue_id": "pallets/click#1"}, "Issue", repo)

        checked = snapshot["results"][0].findings[0].citations[0]
        self.assertTrue(checked.valid)
        self.assertEqual(checked.outcome, "corrected_unique_exact_quote")
        self.assertEqual(checked.corrected_start_line, 2)
        self.assertEqual(snapshot["report_schema"], "citeproof-evaluation/v3")
        self.assertEqual(snapshot["ranking_method"], "finding_order_descending_plausibility")
        self.assertEqual(snapshot["saved_investigator_localization"], ranking)

        exported = build_run_report(
            {"issue_id": "pallets/click#1", "primary_files": ["sample.py"]},
            "abc123",
            "model",
            "provider",
            snapshot["results"],
            report_schema=snapshot["report_schema"],
            ranking_method=snapshot["ranking_method"],
            preserved_investigator_localization=snapshot["saved_investigator_localization"],
        )
        self.assertEqual(exported["ranking_method"], "finding_order_descending_plausibility")
        self.assertEqual(exported["investigator_localization"], ranking)

    def test_saved_reports_fail_closed_on_malformed_schema_and_v3_metric_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            repo.commit = "abc123"
            with self.assertRaisesRegex(ValueError, "unsupported schema"):
                snapshot_from_saved_report(
                    {"schema": [], "issue_id": "pallets/click#1", "repository_commit": "abc123"},
                    {"issue_id": "pallets/click#1"},
                    "Issue",
                    repo,
                )
            malformed_v3 = {
                "schema": "citeproof-evaluation/v3",
                "ranking_method": "finding_order_descending_plausibility",
                "investigator_localization": [{
                    "name": "A",
                    "status": [],
                    "ranked_files": [],
                    "primary_hit_at_1": None,
                    "primary_file_reciprocal_rank": None,
                    "gold_file_recall_at_3": None,
                }],
            }
            with self.assertRaisesRegex(ValueError, "invalid investigator localization"):
                snapshot_from_saved_report(
                    malformed_v3,
                    {"issue_id": "pallets/click#1"},
                    "Issue",
                    repo,
                )


if __name__ == "__main__":
    unittest.main()
