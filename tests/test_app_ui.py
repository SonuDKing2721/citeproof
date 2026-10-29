import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from citeproof.models import AgentResult, VerificationReview
from citeproof.presentation import make_run_snapshot


class AppUITests(unittest.TestCase):
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
        app.selectbox[0].select("Curated case · Click #3449 · multi-PR").run(timeout=20)
        demo_button = next(
            item for item in app.button
            if item.label == "Load Cached A/B + Live Verifier Demo · No Model Call"
        )

        demo_button.click().run(timeout=20)

        self.assertFalse(app.exception)
        self.assertTrue(any("Cached investigator pair" in item.value for item in app.caption))
        self.assertTrue(any("separate verifier review was live" in item.value for item in app.info))
        self.assertIn("04  /  Skeptical Review", [item.value for item in app.header])


if __name__ == "__main__":
    unittest.main()
