import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from citeproof.models import AgentResult, Citation, Finding, VerificationReview
from citeproof.presentation import make_run_snapshot


class AppUITests(unittest.TestCase):
    def test_blind_review_is_available_for_saved_pair_baseline_comparisons(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)

        self.assertFalse(app.exception)
        self.assertTrue(any(item.label == "Blind pair-versus-baseline review" for item in app.expander))

    def test_results_are_grouped_into_accessible_evidence_tabs_with_safe_trace_replay(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        app.session_state["last_run"] = make_run_snapshot(
            [
                AgentResult(
                    "Investigator A",
                    [Finding("Cause", "The `render_result` helper drops the output.", [
                        Citation("src/example.py", "render_result", 1, 1, "render_result()", valid=True,
                                 outcome="verified_exact"),
                    ])],
                    [],
                    trace_events=[{
                        "tool": "read_file",
                        "request_summary": "src/example.py:1-1",
                        "result_summary": "Read 1 source lines; source text withheld.",
                    }, {
                        "tool": "find_symbols",
                        "request_summary": "symbol: render_result",
                        "result_summary": "Found 1 matching symbols; source text withheld.",
                    }],
                ),
                AgentResult("Investigator B", [], []),
            ],
            "abc123",
            "Bug report",
            None,
        )

        app.run(timeout=20)

        self.assertFalse(app.exception)
        self.assertEqual([tab.label for tab in app.tabs], ["Findings", "Compare", "Trace", "Report"])
        self.assertTrue(any("Status · Complete" in item.value for item in app.markdown))
        self.assertTrue(any("A verified citation proves the quote exists" in item.value for item in app.markdown))
        self.assertTrue(any(item.label == "Trace step" for item in app.slider))
        rendered_text = [item.value for item in app.markdown] + [item.value for item in app.caption]
        self.assertTrue(any("Direct citation anchor" in value for value in rendered_text))
        self.assertFalse(any("✅" in value or "❌" in value for value in rendered_text))

    def test_single_trace_event_and_manual_run_report_render_without_gold_labels(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        app.session_state["last_run"] = make_run_snapshot(
            [
                AgentResult(
                    "Investigator A",
                    [],
                    [],
                    trace_events=[{
                        "tool": "read_file",
                        "request_summary": "src/example.py:1-2",
                        "result_summary": "Read 2 source lines; source text withheld.",
                    }],
                ),
                AgentResult("Investigator B", [], []),
            ],
            "abc123",
            "Manual issue",
            None,
        )

        app.run(timeout=20)

        self.assertFalse(app.exception)
        self.assertFalse(app.slider)
        self.assertTrue(any("Single recorded step" in item.value for item in app.caption))
        self.assertTrue(any("No curated gold labels" in item.value for item in app.info))
        self.assertIn("Download unscored run as JSON", [item.label for item in app.get("download_button")])

    def test_unavailable_endpoint_offers_a_pinned_saved_run_without_calling_inference(self):
        with patch.dict("os.environ", {"NVIDIA_API_KEY": ""}):
            app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
            next(item for item in app.selectbox if item.label == "Issue case").select(
                "Curated case · Click #3449 · multi-PR"
            ).run(timeout=20)
            check_button = next(item for item in app.button if item.label == "Check endpoint")

            check_button.click().run(timeout=20)

        self.assertFalse(app.exception)
        self.assertTrue(any("Endpoint: Unavailable" in item.value for item in app.markdown))
        self.assertIn("Open saved run", [item.label for item in app.button])

    def test_incomplete_run_offers_same_issue_saved_run_only_for_matching_commit(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        next(item for item in app.selectbox if item.label == "Issue case").select(
            "Curated case · Click #3449 · multi-PR"
        ).run(timeout=20)
        gold_case = {"issue_id": "pallets/click#3449", "primary_files": ["src/click/core.py"]}
        app.session_state["last_run"] = make_run_snapshot(
            [
                AgentResult("Investigator A", [], [], error="provider timeout"),
                AgentResult("Investigator B", [], []),
            ],
            "a5f5aa6d4012d256ccca24638f2642fc371e9f77",
            "Click pager issue",
            gold_case,
        )

        app.run(timeout=20)

        self.assertFalse(app.exception)
        self.assertIn("Open saved run", [item.label for item in app.button])

        app.session_state["last_run"] = make_run_snapshot(
            [
                AgentResult("Investigator A", [], [], error="provider timeout"),
                AgentResult("Investigator B", [], []),
            ],
            "wrong-commit",
            "Click pager issue",
            gold_case,
        )
        app.run(timeout=20)

        self.assertFalse(app.exception)
        self.assertNotIn("Open saved run", [item.label for item in app.button])

    def test_run_summary_shows_model_attempts_and_retries_per_investigator(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        app.session_state["last_run"] = make_run_snapshot(
            [
                AgentResult("Investigator A", [], [], model_requests=4, model_retries=3),
                AgentResult("Investigator B", [], [], model_requests=1, model_retries=0),
            ],
            "abc123",
            "Bug report",
            None,
        )

        app.run(timeout=20)

        self.assertFalse(app.exception)
        self.assertTrue(any(
            "Model attempts · Investigator A 4 (3 retries) · Investigator B 1 (0 retries)" in item.value
            for item in app.caption
        ))

    def test_endpoint_status_labels_are_explicit_and_visible(self):
        for status, label in (("ready", "Ready"), ("slow", "Slow"), ("unavailable", "Unavailable")):
            with self.subTest(status=status):
                app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
                app.session_state["endpoint_health"] = {
                    "status": status,
                    "elapsed_seconds": 1.0,
                    "error": None,
                }

                app.run(timeout=20)

                self.assertFalse(app.exception)
                self.assertTrue(any(f"Endpoint: {label}" in item.value for item in app.markdown))

    def test_evidence_review_renders_outcomes_claimed_and_corrected_ranges_and_rejected_quote(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        corrected = Citation(
            "src/example.py", "", 7, 9, "actual source",
            valid=True, outcome="corrected_unique_exact_quote",
            reason="Unique exact quote; corrected line range from 7-9 to 8-8.",
            claimed_start_line=7, claimed_end_line=9,
            corrected_start_line=8, corrected_end_line=8,
        )
        rejected = Citation(
            "src/example.py", "missing", 12, 12, "rejected source quote",
            valid=False, outcome="quote_not_found", reason="Quoted text does not occur in this file.",
        )
        app.session_state["last_run"] = make_run_snapshot(
            [AgentResult(
                "Investigator A",
                [Finding("Cause", "Reason", [corrected]), Finding("Second cause", "Needs review", [rejected])],
                [],
            ), AgentResult("Investigator B", [], [])],
            "abc123",
            "Bug report",
            None,
        )

        app.run(timeout=20)

        self.assertFalse(app.exception)
        captions = [element.value for element in app.caption]
        self.assertTrue(any("Claimed range: 7-9" in value for value in captions))
        self.assertTrue(any("Corrected range: 8-8" in value for value in captions))
        self.assertTrue(any("corrected_unique_exact_quote" in value for value in captions))
        code_values = [element.value for element in app.code]
        self.assertIn("actual source", code_values)
        self.assertIn("rejected source quote", code_values)
        self.assertTrue(any("does not show the diagnosis is false" in value.lower() for value in captions))

    def test_per_investigator_file_localization_rows_are_separate_from_pair_scores(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        app.session_state["last_run"] = make_run_snapshot(
            [
                AgentResult("Investigator A", [Finding("First", "", [
                    Citation("src/noise.py", "", 1, 1, "x", valid=True, outcome="verified_exact"),
                    Citation("src/main.py", "", 1, 1, "y", valid=True, outcome="verified_exact"),
                ])], []),
                AgentResult("Investigator B", [Finding("First", "", [
                    Citation("src/main.py", "", 1, 1, "x", valid=True, outcome="verified_exact"),
                ])], []),
            ],
            "abc123",
            "Bug report",
            {"issue_id": "org/repo#1", "primary_files": ["src/main.py"], "supporting_files": []},
        )

        app.run(timeout=20)

        self.assertFalse(app.exception)
        self.assertIn("Per-investigator file-localization proxies", [item.value for item in app.subheader])
        captions = [item.value for item in app.caption]
        self.assertTrue(any("Investigator A" in value and "Primary-file reciprocal rank" in value for value in captions))
        self.assertTrue(any("Investigator B" in value and "1.00" in value for value in captions))

    def test_investigation_sections_use_second_level_headings(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        self.assertFalse(app.exception)
        headings = [element.value for element in app.header]
        self.assertIn("01  /  Investigation Brief", headings)

    def test_sidebar_describes_parallel_investigators_and_bounded_review(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        self.assertFalse(app.exception)
        captions = [element.value for element in app.caption]
        self.assertIn(
            "Two independent investigators run in parallel (up to 4 minutes each), followed by at most one 2-minute verifier request when both have checked citations. Each request is capped at 2 minutes. Investigators allow up to 3 tool rounds plus one bounded correction.",
            captions,
        )

    def test_completed_empty_run_calls_out_zero_findings_and_zero_localization(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        app.session_state["last_run"] = make_run_snapshot(
            [AgentResult("Investigator A", [], []), AgentResult("Investigator B", [], [])],
            "abc123",
            "Bug report",
            {"issue_id": "org/repo#1", "primary_files": ["src/fix.py"]},
        )

        app.run(timeout=20)

        self.assertFalse(app.exception)
        warnings = [item.value for item in app.warning]
        self.assertTrue(any("investigation completed with no findings" in item.lower() for item in warnings))
        self.assertTrue(any("0% gold-file recall" in item.lower() for item in warnings))

    def test_saved_review_renders_candidate_assessment_and_unrun_test_label(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        app.session_state["last_run"] = make_run_snapshot(
            [AgentResult("Investigator A", [], []), AgentResult("Investigator B", [], [])],
            "abc123",
            "Bug report",
            None,
            verification=VerificationReview(
                status="reviewed",
                assessment="insufficient_evidence",
                rationale="The checked lines do not distinguish the hypotheses.",
                test_scenario="Call the public API with the reported value.",
                test_assertion="Assert that the expected value is returned.",
                model_requests=1,
            ),
        )

        app.run(timeout=20)

        self.assertFalse(app.exception)
        self.assertIn("04  /  Skeptical Review", [item.value for item in app.header])
        self.assertIn("Suggested regression test · not run", [item.value for item in app.info])

    def test_saved_snapshot_renders_measured_stage_timings(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        app.session_state["last_run"] = make_run_snapshot(
            [AgentResult("Investigator A", [], []), AgentResult("Investigator B", [], [])],
            "abc123",
            "Bug report",
            None,
            timings={
                "investigators_seconds": 48.0,
                "verification_seconds": 12.5,
                "total_seconds": 60.5,
            },
        )

        app.run(timeout=20)

        self.assertFalse(app.exception)
        self.assertIn(
            "Measured elapsed time · Total 60.5s · investigators 48.0s · verifier 12.5s",
            [item.value for item in app.caption],
        )

    def test_incomplete_pair_and_unavailable_verifier_keep_distinct_ui_states(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        app.session_state["last_run"] = make_run_snapshot(
            [
                AgentResult("Investigator A", [], [], error="provider timeout"),
                AgentResult("Investigator B", [], []),
            ],
            "abc123",
            "Bug report",
            {"issue_id": "org/repo#1", "primary_files": ["src/fix.py"]},
            verification=VerificationReview(status="unavailable", error="Verifier timed out."),
        )

        app.run(timeout=20)

        self.assertFalse(app.exception)
        warnings = [item.value for item in app.warning]
        self.assertTrue(any("verifier was unavailable" in value.lower() for value in warnings))
        self.assertTrue(any("run is incomplete" in value for value in warnings))
        self.assertIn(
            "Download incomplete run · partial evidence only",
            [item.label for item in app.get("download_button")],
        )

    def test_human_diagnosis_review_requires_a_note_before_exporting_a_judgment(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        app.session_state["last_run"] = make_run_snapshot(
            [AgentResult("Investigator A", [], []), AgentResult("Investigator B", [], [])],
            "abc123",
            "Bug report",
            {"issue_id": "org/repo#1", "primary_files": ["src/fix.py"]},
        )
        app.run(timeout=20)

        diagnosis = next(item for item in app.selectbox if item.label == "Diagnosis Assessment")
        diagnosis.select("supported").run(timeout=20)
        self.assertEqual(app.session_state["last_run"]["diagnosis_review"]["status"], "not_reviewed")
        self.assertTrue(any("Add a brief evidence-based reason" in item.value for item in app.info))

        note = next(item for item in app.text_area if item.label == "Evidence-Based Reason")
        note.set_value("The explanation matches the issue and maintainer-confirmed fix.").run(timeout=20)

        self.assertEqual(app.session_state["last_run"]["diagnosis_review"]["status"], "supported")
        self.assertIn("maintainer-confirmed fix", app.session_state["last_run"]["diagnosis_review"]["note"])

    def test_app_offers_transparently_labeled_cached_pair_and_live_review_demo(self):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=20)
        next(item for item in app.selectbox if item.label == "Issue case").select(
            "Curated case · Click #3449 · multi-PR"
        ).run(timeout=20)
        demo_button = next(
            item for item in app.button
            if item.label == "Load Cached A/B + Live Verifier Demo · No Model Call"
        )

        demo_button.click().run(timeout=20)

        self.assertFalse(app.exception)
        self.assertTrue(any("Cached investigator pair" in item.value for item in app.caption))
        self.assertTrue(any("separate verifier review was live" in item.value for item in app.info))
        self.assertIn("04  /  Skeptical Review", [item.value for item in app.header])
        self.assertIn("Issue-comment draft", [item.value for item in app.subheader])
        self.assertTrue(any("https://github.com/pallets/click/blob/" in item.value for item in app.code))


if __name__ == "__main__":
    unittest.main()
