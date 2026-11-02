import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from citeproof.blind_review import (
    begin_blind_review,
    list_reviewable_reports,
    save_blind_review,
)


def sample_report():
    return {
        "schema": "citeproof-budget-comparison/v2",
        "issue_id": "owner/repo#7",
        "repository_commit": "abc123",
        "run_timestamp_utc": "2026-11-02T10:00:00+00:00",
        "model_id": "local-test-model",
        "provider": "Ollama local",
        "pair": {
            "model_requests": 6,
            "localization": {"status": "complete", "ranked_files": ["src/a.py"], "primary_hit_at_1": True, "gold_file_recall_at_3": 1.0},
            "agents": [{"name": "Investigator A", "findings": [{"claim": "Pair claim", "explanation": "Pair evidence", "citations": [{"path": "src/a.py", "symbol": "run", "start_line": 1, "end_line": 1, "quote": "return 1", "valid": True}]}]}],
        },
        "baseline": {
            "model_requests": 6,
            "localization": {"status": "complete", "ranked_files": ["src/b.py"], "primary_hit_at_1": False, "gold_file_recall_at_3": 0.0},
            "agents": [{"name": "Single investigator", "findings": [{"claim": "Baseline claim", "explanation": "Baseline evidence", "citations": []}]}],
        },
    }


class BlindReviewTests(unittest.TestCase):
    def test_identity_is_stable_for_the_same_saved_comparison(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "annotations.json"
            first = begin_blind_review(sample_report(), path)
            second = begin_blind_review(sample_report(), path)

        self.assertEqual(first.identity, second.identity)
        self.assertEqual(first.option_a, second.option_a)
        self.assertEqual(first.option_b, second.option_b)

    def test_order_is_blinded_until_a_label_and_note_are_saved(self):
        report = sample_report()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "annotations.json"
            with patch("citeproof.blind_review.secrets.choice", return_value=["pair", "baseline"]):
                session = begin_blind_review(report, path)

            self.assertEqual(session.option_a["findings"][0]["claim"], "Pair claim")
            self.assertEqual(session.option_b["findings"][0]["claim"], "Baseline claim")
            self.assertIsNone(session.mapping_revealed)
            serialized_options = json.dumps({"a": session.option_a, "b": session.option_b}).lower()
            self.assertNotIn("two-agent pair", serialized_options)
            self.assertNotIn("single-agent baseline", serialized_options)

            saved = save_blind_review(report, path, "A stronger", "Option A matched the maintainer's fix path.")

        self.assertEqual(saved.saved_label, "A stronger")
        self.assertEqual(saved.note, "Option A matched the maintainer's fix path.")
        self.assertEqual(saved.mapping_revealed, {"A": "Two-agent pair", "B": "Single-agent baseline"})

    def test_annotations_are_separate_and_existing_labels_cannot_be_overwritten(self):
        report = sample_report()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_path = root / "original-comparison.json"
            original = json.dumps(report, sort_keys=True)
            report_path.write_text(original, encoding="utf-8")
            annotations = root / "annotations.json"

            save_blind_review(report, annotations, "Tie", "Both produced plausible locations.")

            with self.assertRaisesRegex(ValueError, "already saved"):
                save_blind_review(report, annotations, "A stronger", "Replacement label.")
            self.assertEqual(report_path.read_text(encoding="utf-8"), original)
            saved_store = json.loads(annotations.read_text(encoding="utf-8"))

        self.assertEqual(len(saved_store["reviews"]), 1)
        saved = next(iter(saved_store["reviews"].values()))
        self.assertEqual(saved["label"], "Tie")
        self.assertEqual(saved["note"], "Both produced plausible locations.")

    def test_review_requires_a_bounded_evidence_note(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "annotations.json"
            with self.assertRaisesRegex(ValueError, "brief note"):
                save_blind_review(sample_report(), path, "A stronger", "   ")

    def test_reviewable_report_listing_skips_single_run_and_rejects_bad_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "single-comparison.json").write_text(json.dumps({"schema": "citeproof-evaluation/v4"}), encoding="utf-8")
            (root / "pair-comparison.json").write_text(json.dumps(sample_report()), encoding="utf-8")
            reports = list_reviewable_reports(root)

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0][1]["issue_id"], "owner/repo#7")


if __name__ == "__main__":
    unittest.main()
