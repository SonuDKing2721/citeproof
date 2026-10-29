import json
import inspect
import unittest

from citeproof import evaluation
from citeproof import agent as agent_module
from citeproof import verifier as verifier_module
from citeproof.evaluation import build_run_report, export_run_report, score_localization
from citeproof.models import AgentResult, Citation, Finding, VerificationReview


def result(name, files=(), error=None):
    citations = [
        Citation(path=path, symbol="", start_line=1, end_line=1, quote="x", valid=True)
        for path in files
    ]
    findings = [Finding("claim", "explanation", citations)] if citations else []
    return AgentResult(name, findings, [], error)


class RunStateContractTests(unittest.TestCase):
    def project(self, results, gold, verification=None, workflow_kind="live_pair", minimum_agents=2, diagnosis_review_status="not_reviewed"):
        project = getattr(evaluation, "run_status_payload", None)
        self.assertTrue(callable(project), "run_status_payload should define the shared result contract")
        return project(results, gold, verification, workflow_kind, minimum_agents, diagnosis_review_status)

    def test_complete_pair_keeps_optional_verifier_failure_separate(self):
        review = VerificationReview(status="unavailable", error="timeout")
        state = self.project(
            [result("A", ["src/main.py"]), result("B", ["src/main.py"])],
            {"primary_files": ["src/main.py"]},
            review,
        )

        self.assertEqual(state, {
            "investigation": "complete",
            "citation_validation": "all_valid",
            "cross_check": "overlapping_lines",
            "verification": "unavailable",
            "localization": "scored",
            "diagnosis_review": "not_reviewed",
            "workflow_kind": "live_pair",
        })

    def test_empty_and_rejected_evidence_are_scored_as_misses_when_investigation_completed(self):
        empty = self.project(
            [result("A"), result("B")],
            {"primary_files": ["src/main.py"]},
        )
        self.assertEqual(empty["investigation"], "complete")
        self.assertEqual(empty["citation_validation"], "not_present")
        self.assertEqual(empty["cross_check"], "no_verified_citations")
        self.assertEqual(empty["verification"], "not_requested")
        self.assertEqual(empty["localization"], "scored")

        rejected = [result("A", ["src/main.py"]), result("B", ["src/main.py"])]
        for agent in rejected:
            agent.findings[0].citations[0].valid = False
        invalid = self.project(rejected, {"primary_files": ["src/main.py"]})
        self.assertEqual(invalid["citation_validation"], "none_valid")
        self.assertEqual(invalid["cross_check"], "no_verified_citations")
        self.assertEqual(invalid["localization"], "scored")

    def test_partial_citations_missing_labels_and_incomplete_pair_have_distinct_states(self):
        mixed = [result("A", ["src/main.py"]), result("B", ["src/main.py"])]
        mixed[1].findings[0].citations.append(
            Citation("src/other.py", "", 1, 1, "x", valid=False)
        )
        partial = self.project(mixed, {"primary_files": ["src/main.py"]})
        self.assertEqual(partial["citation_validation"], "partly_valid")
        self.assertEqual(partial["localization"], "scored")

        missing_labels = self.project([result("A"), result("B")], {})
        self.assertEqual(missing_labels["localization"], "missing_labels")

        incomplete = self.project(
            [result("A", ["src/main.py"]), result("B", error="timeout")],
            {"primary_files": ["src/main.py"]},
        )
        self.assertEqual(incomplete["investigation"], "incomplete")
        self.assertEqual(incomplete["cross_check"], "incomplete")
        self.assertEqual(incomplete["localization"], "incomplete")

    def test_single_agent_baseline_is_scored_without_claiming_cross_agent_agreement(self):
        state = self.project(
            [result("Single investigator", ["src/main.py"])],
            {"primary_files": ["src/main.py"]},
            workflow_kind="single_agent_baseline",
            minimum_agents=1,
        )

        self.assertEqual(state["investigation"], "complete")
        self.assertEqual(state["cross_check"], "not_applicable")
        self.assertEqual(state["localization"], "scored")

    def test_human_diagnosis_review_state_is_separate_and_allowlisted(self):
        accepted = ("supported", "partly_supported", "unsupported", "incorrect")
        for status in accepted:
            with self.subTest(status=status):
                state = self.project(
                    [result("A", ["src/main.py"]), result("B", ["src/main.py"])],
                    {"primary_files": ["src/main.py"]},
                    diagnosis_review_status=status,
                )
                self.assertEqual(state["diagnosis_review"], status)
        with self.assertRaisesRegex(ValueError, "diagnosis review"):
            self.project(
                [result("A"), result("B")],
                {},
                diagnosis_review_status="model_says_correct",
            )


class RunReportV2Tests(unittest.TestCase):
    def test_report_records_human_diagnosis_review_separately_from_model_validation(self):
        report = build_run_report(
            {"issue_id": "org/repo#10", "primary_files": ["src/main.py"]},
            "abc123",
            "meta/muse-glimmer-30b",
            "NVIDIA API Catalog",
            [result("A", ["src/main.py"]), result("B", ["src/main.py"])],
            diagnosis_review_status="partly_supported",
            diagnosis_review_reviewer="maintainer",
            diagnosis_review_note="The file is right, but the explanation omits the resource lifetime condition.",
        )

        self.assertEqual(report["states"]["diagnosis_review"], "partly_supported")
        self.assertEqual(report["diagnosis_review"], {
            "status": "partly_supported",
            "reviewer": "maintainer",
            "note": "The file is right, but the explanation omits the resource lifetime condition.",
        })
        self.assertEqual(report["diagnosis_correctness_metric"], "not_scored")

    def test_report_preserves_run_identity_states_settings_and_timings(self):
        parameters = inspect.signature(build_run_report).parameters
        self.assertIn("workflow_kind", parameters)
        self.assertIn("run_timestamp_utc", parameters)
        self.assertIn("timings", parameters)

        report = build_run_report(
            {"issue_id": "org/repo#10", "primary_files": ["src/main.py"]},
            "abc123",
            "meta/muse-glimmer-30b",
            "NVIDIA API Catalog",
            [result("A", ["src/main.py"]), result("B", ["src/main.py"])],
            verification=VerificationReview(status="unavailable", error="timeout", model_requests=1),
            workflow_kind="cached_pair_live_review",
            run_timestamp_utc="2026-10-29T00:00:00+00:00",
            timings={"investigators_seconds": 12.5, "verification_seconds": 1.5, "total_seconds": 14.0},
            model_settings={
                "investigator": {
                    "model_id": "meta/muse-glimmer-30b",
                    "request_parameters": agent_module.INVESTIGATOR_REQUEST_SETTINGS,
                    "timeout_seconds": agent_module.MODEL_REQUEST_TIMEOUT_SECONDS,
                },
                "verifier": {
                    "model_id": "meta/muse-glimmer-30b",
                    "request_parameters": verifier_module.VERIFIER_REQUEST_SETTINGS,
                    "timeout_seconds": verifier_module.MODEL_REQUEST_TIMEOUT_SECONDS,
                },
            },
        )

        self.assertEqual(report["schema"], "citeproof-evaluation/v2")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["states"]["verification"], "unavailable")
        self.assertEqual(report["states"]["localization"], "scored")
        self.assertEqual(report["states"]["workflow_kind"], "cached_pair_live_review")
        self.assertEqual(report["workflow"]["run_timestamp_utc"], "2026-10-29T00:00:00+00:00")
        self.assertEqual(report["workflow"]["timings"], {
            "investigators_seconds": 12.5,
            "verification_seconds": 1.5,
            "baseline_seconds": None,
            "total_seconds": 14.0,
        })
        self.assertEqual(
            report["model_settings"]["investigator"]["request_parameters"],
            agent_module.INVESTIGATOR_REQUEST_SETTINGS,
        )
        self.assertEqual(
            report["model_settings"]["verifier"]["request_parameters"],
            verifier_module.VERIFIER_REQUEST_SETTINGS,
        )
        self.assertEqual(report["model_requests"]["total"], 1)
        self.assertNotIn("primary_files", json.dumps(report))

    def test_unmeasured_cached_run_uses_null_durations_and_stable_original_timestamp(self):
        self.assertIn("workflow_kind", inspect.signature(build_run_report).parameters)
        report = build_run_report(
            {"issue_id": "org/repo#10", "primary_files": ["src/main.py"]},
            "abc123",
            "meta/muse-glimmer-30b",
            "NVIDIA API Catalog",
            [result("A", ["src/main.py"]), result("B", ["src/main.py"])],
            workflow_kind="cached_demo",
            run_timestamp_utc="2026-10-28T19:00:00+00:00",
        )

        self.assertEqual(report["workflow"]["run_timestamp_utc"], "2026-10-28T19:00:00+00:00")
        self.assertIsNone(report["workflow"]["timings"]["investigators_seconds"])
        self.assertIsNone(report["workflow"]["timings"]["verification_seconds"])
        self.assertIsNone(report["workflow"]["timings"]["total_seconds"])

    def test_cached_run_keeps_aggregate_request_totals_when_agent_split_was_not_saved(self):
        results = [
            AgentResult("A", [], [], model_requests_known=False),
            AgentResult("B", [], [], model_requests_known=False),
        ]
        report = build_run_report(
            {"issue_id": "org/repo#10", "primary_files": ["src/main.py"]},
            "abc123",
            "meta/muse-glimmer-30b",
            "NVIDIA API Catalog",
            results,
            workflow_kind="cached_demo",
            model_request_counts={"investigators": 9, "verification": 1, "total": 10},
        )

        self.assertEqual(report["model_requests"], {"investigators": 9, "verification": 1, "total": 10})
        self.assertIsNone(report["agents"][0]["model_requests"])
        self.assertIsNone(report["agents"][1]["model_requests"])


class LocalizationEvaluationTests(unittest.TestCase):
    def test_scores_primary_file_at_one_and_recall_over_primary_and_supporting(self):
        metrics = score_localization(
            [
                result("A", ["src/main.py", "tests/test_main.py"]),
                result("B", ["src/main.py"]),
            ],
            {"primary_files": ["src/main.py"], "supporting_files": ["tests/test_main.py"]},
        )

        self.assertEqual(metrics.status, "complete")
        self.assertTrue(metrics.primary_hit_at_1)
        self.assertEqual(metrics.gold_file_recall_at_3, 1.0)
        self.assertEqual(metrics.ranked_files, ("src/main.py", "tests/test_main.py"))

    def test_ranks_files_by_independent_agent_support_and_deduplicates_within_agent(self):
        metrics = score_localization(
            [
                result("A", ["src/noise.py", "src/main.py", "src/main.py"]),
                result("B", ["src/main.py", "tests/test_main.py"]),
            ],
            {"primary_files": ["src/main.py"], "supporting_files": ["tests/test_main.py"]},
        )

        self.assertEqual(metrics.ranked_files, ("src/main.py", "src/noise.py", "tests/test_main.py"))
        self.assertTrue(metrics.primary_hit_at_1)
        self.assertEqual(metrics.gold_file_recall_at_3, 1.0)

    def test_scores_a_single_investigator_only_when_explicitly_enabled(self):
        single_result = result("Baseline", ["src/noise.py", "src/main.py", "src/main.py"])
        single_result.findings[0].citations[0].valid = False

        default_metrics = score_localization(
            [single_result],
            {"primary_files": ["src/main.py"], "supporting_files": []},
        )
        baseline_metrics = score_localization(
            [single_result],
            {"primary_files": ["src/main.py"], "supporting_files": []},
            minimum_agents=1,
        )

        self.assertEqual(default_metrics.status, "incomplete")
        self.assertEqual(baseline_metrics.status, "complete")
        self.assertEqual(baseline_metrics.ranked_files, ("src/main.py",))
        self.assertTrue(baseline_metrics.primary_hit_at_1)
        self.assertEqual(baseline_metrics.gold_file_recall_at_3, 1.0)

    def test_marks_failed_agent_run_incomplete_without_scoring_partial_evidence(self):
        metrics = score_localization(
            [result("A", ["src/main.py"]), result("B", ["src/noise.py"], error="timeout")],
            {"primary_files": ["src/main.py"], "supporting_files": []},
        )

        self.assertEqual(metrics.status, "incomplete")
        self.assertIsNone(metrics.primary_hit_at_1)
        self.assertIsNone(metrics.gold_file_recall_at_3)

    def test_empty_predictions_score_zero_without_inventing_a_hit(self):
        metrics = score_localization(
            [result("A"), result("B")],
            {"primary_files": ["src/main.py"], "supporting_files": []},
        )

        self.assertEqual(metrics.status, "complete")
        self.assertFalse(metrics.primary_hit_at_1)
        self.assertEqual(metrics.gold_file_recall_at_3, 0.0)

    def test_run_report_is_reproducible_and_does_not_export_gold_labels(self):
        gold = {
            "issue_id": "pallets/click#2877",
            "primary_files": ["src/main.py"],
            "supporting_files": ["tests/test_main.py"],
        }
        report = build_run_report(
            gold,
            "abc123",
            "meta/muse-glimmer-30b",
            "NVIDIA API Catalog",
            [result("A", ["src/main.py"]), result("B", ["src/main.py"])],
        )

        self.assertEqual(report["repository_commit"], "abc123")
        self.assertEqual(report["model_id"], "meta/muse-glimmer-30b")
        self.assertEqual(report["metrics"]["primary_hit_at_1"], True)
        self.assertEqual(report["diagnosis_review"]["status"], "not_reviewed")
        self.assertEqual(report["diagnosis_correctness_metric"], "not_scored")
        self.assertNotIn("primary_files", report)
        self.assertNotIn("supporting_files", report)

    def test_incomplete_run_report_keeps_partial_findings_but_has_no_scores(self):
        gold = {"issue_id": "pallets/click#2877", "primary_files": ["src/main.py"]}
        report = build_run_report(
            gold,
            "abc123",
            "meta/muse-glimmer-30b",
            "NVIDIA API Catalog",
            [result("A", ["src/main.py"]), result("B", error="timeout")],
        )

        self.assertEqual(report["status"], "incomplete")
        self.assertIsNone(report["metrics"]["primary_hit_at_1"])
        self.assertEqual(report["agents"][0]["findings"][0]["citations"][0]["path"], "src/main.py")

    def test_report_marks_when_only_one_agent_has_verified_citations(self):
        report = build_run_report(
            {"issue_id": "pallets/click#3449", "primary_files": ["src/click/_termui_impl.py"]},
            "abc123",
            "meta/muse-glimmer-30b",
            "NVIDIA API Catalog",
            [result("A", ["src/click/_termui_impl.py"]), result("B")],
        )

        self.assertEqual(report["evidence"]["agents_with_verified_citations"], 1)
        self.assertEqual(report["evidence"]["cross_check_status"], "no_verified_citations")
        self.assertIn("does not show full-run corroboration", report["evidence"]["note"])

    def test_incomplete_run_export_is_named_as_incomplete_and_keeps_partial_evidence(self):
        report = {
            "issue_id": "pallets/click#2877",
            "status": "incomplete",
            "agents": [{"findings": [{"claim": "partial"}]}],
        }

        filename, content = export_run_report(report)

        self.assertEqual(filename, "citeproof-pallets-click-2877-incomplete.json")
        self.assertEqual(json.loads(content)["agents"][0]["findings"][0]["claim"], "partial")

    def test_run_report_counts_verifier_request_separately_from_localization_agents(self):
        review = VerificationReview(
            status="reviewed",
            assessment="supports_candidate",
            selected_finding_id="A-F1",
            supporting_evidence_ids=["A-F1-C1"],
            rationale="Checked evidence supports this candidate.",
            test_scenario="Call the public method with the reported value.",
            test_assertion="Assert the returned value is preserved.",
            model_requests=1,
        )
        report = build_run_report(
            {"issue_id": "org/repo#10", "primary_files": ["src/main.py"]},
            "abc123",
            "meta/muse-glimmer-30b",
            "NVIDIA API Catalog",
            [result("A", ["src/main.py"]), result("B", ["src/main.py"])],
            verification=review,
        )

        self.assertEqual(report["model_requests"], {"investigators": 0, "verification": 1, "total": 1})
        self.assertEqual(report["verification"]["status"], "reviewed")
        self.assertEqual(report["verification"]["test_assertion"], "Assert the returned value is preserved.")
        self.assertNotIn("primary_files", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
