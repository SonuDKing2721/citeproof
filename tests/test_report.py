import unittest
import json
import tempfile
from pathlib import Path

from citeproof.report import (
    render_benchmark_summary,
    refresh_documents,
    replace_marked_block,
    select_latest_by_issue,
    load_comparison_reports,
)


def localization(*, status="complete", hit=True, recall=0.5):
    return {
        "status": status,
        "ranked_files": ["src/example.py"] if status == "complete" else [],
        "primary_hit_at_1": hit if status == "complete" else None,
        "gold_file_recall_at_3": recall if status == "complete" else None,
    }


def comparison(
    issue_id="owner/repo#12",
    timestamp="2026-11-01T12:00:00+00:00",
    *,
    status="complete",
    matched=True,
    pair_localization=None,
    baseline_localization=None,
    pair_requests=8,
    baseline_requests=8,
):
    return {
        "schema": "citeproof-budget-comparison/v2",
        "run_timestamp_utc": timestamp,
        "issue_id": issue_id,
        "status": status,
        "budget_matched": matched,
        "pair": {
            "model_requests": pair_requests,
            "localization": pair_localization or localization(),
        },
        "baseline": {
            "model_requests": baseline_requests,
            "localization": baseline_localization or localization(hit=False),
        },
    }


class ReportTests(unittest.TestCase):
    def test_summary_uses_counts_and_preserves_incomplete_small_sample(self):
        reports = [
            comparison(),
            comparison(
                "owner/other#9",
                status="incomplete",
                matched=False,
                pair_localization=localization(status="incomplete"),
                baseline_localization=localization(status="incomplete"),
                baseline_requests=5,
            ),
        ]

        markdown = render_benchmark_summary(reports)

        self.assertIn("1/2 workflows completed with matched request budgets", markdown)
        self.assertIn("1/2 were incomplete or unmatched", markdown)
        self.assertNotIn("50%", markdown.splitlines()[0])
        self.assertIn("Diagnosis correctness: not scored", markdown)
        self.assertIn("owner/repo/issues/12", markdown)
        self.assertIn("not scored (incomplete)", markdown)

    def test_latest_report_per_issue_is_selected_by_run_timestamp(self):
        older = comparison(timestamp="2026-10-28T12:00:00+00:00", status="incomplete", matched=False)
        newer = comparison(timestamp="2026-10-29T12:00:00+00:00")

        selected = select_latest_by_issue([
            ("later-name.json", older),
            ("earlier-name.json", newer),
        ])

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0][1]["run_timestamp_utc"], "2026-10-29T12:00:00+00:00")

    def test_completed_run_with_unscored_localization_is_not_misrepresented(self):
        report = comparison(
            pair_localization=localization(status="incomplete"),
            baseline_localization=localization(status="incomplete"),
        )

        markdown = render_benchmark_summary([report])

        self.assertIn("1/1 workflows completed with matched request budgets", markdown)
        self.assertIn("run complete; budget matched", markdown)
        self.assertIn("not scored (incomplete)", markdown)

    def test_missing_report_fields_render_unknown_and_not_scored(self):
        malformed_but_valid_json = {
            "schema": "citeproof-budget-comparison/v2",
            "issue_id": "owner/repo#3",
            "budget_matched": None,
        }

        markdown = render_benchmark_summary([malformed_but_valid_json])

        self.assertIn("0/1 workflows completed with matched request budgets", markdown)
        self.assertIn("1/1 were incomplete or unmatched", markdown)
        self.assertIn("unknown requests", markdown)
        self.assertIn("not scored (unknown)", markdown)

    def test_replace_marked_block_preserves_content_outside_markers(self):
        original = "before\n<!-- citeproof-benchmarks:start -->\nold\n<!-- citeproof-benchmarks:end -->\nafter\n"

        updated = replace_marked_block(original, "new table")

        self.assertEqual(
            updated,
            "before\n<!-- citeproof-benchmarks:start -->\nnew table\n<!-- citeproof-benchmarks:end -->\nafter\n",
        )

    def test_replace_marked_block_rejects_missing_or_repeated_markers(self):
        with self.assertRaises(ValueError):
            replace_marked_block("unmarked content", "new")
        with self.assertRaises(ValueError):
            replace_marked_block(
                "<!-- citeproof-benchmarks:start -->x<!-- citeproof-benchmarks:end -->\n"
                "<!-- citeproof-benchmarks:start -->y<!-- citeproof-benchmarks:end -->",
                "new",
            )

    def test_refresh_documents_check_is_read_only_and_detects_stale_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "data" / "benchmarks").mkdir(parents=True)
            for relative in (Path("README.md"), Path("docs/RELATED_WORK_AND_GAP_REVIEW.md")):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    f"prefix\n{START}\nstale\n{END}\nsuffix\n", encoding="utf-8"
                )
            report = comparison()
            report["_source_file"] = "case-comparison.json"
            (root / "data" / "benchmarks" / "case-comparison.json").write_text(
                json.dumps(report), encoding="utf-8"
            )

            code, changed = refresh_documents(root, check=True)

            self.assertEqual(code, 1)
            self.assertEqual(len(changed), 2)
            self.assertIn("stale", (root / "README.md").read_text(encoding="utf-8"))

    def test_refresh_documents_updates_only_marked_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "data" / "benchmarks").mkdir(parents=True)
            for relative in (Path("README.md"), Path("docs/RELATED_WORK_AND_GAP_REVIEW.md")):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    f"prefix\n{START}\nstale\n{END}\nsuffix\n", encoding="utf-8"
                )
            report = comparison()
            (root / "data" / "benchmarks" / "case-comparison.json").write_text(
                json.dumps(report), encoding="utf-8"
            )

            code, changed = refresh_documents(root)

            self.assertEqual(code, 0)
            self.assertEqual(len(changed), 2)
            updated = (root / "README.md").read_text(encoding="utf-8")
            self.assertTrue(updated.startswith("prefix\n"))
            self.assertTrue(updated.endswith("\nsuffix\n"))
            self.assertIn("1/1", updated)
            self.assertNotIn("stale", updated)

    def test_report_loader_keeps_local_model_runs_out_of_muse_summary_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            muse = comparison(timestamp="2026-11-01T12:00:00+00:00")
            muse["provider"] = "NVIDIA API Catalog"
            local = comparison(timestamp="2026-11-02T12:00:00+00:00")
            local["provider"] = "Ollama local"
            (directory / "muse-comparison.json").write_text(json.dumps(muse), encoding="utf-8")
            (directory / "local-comparison.json").write_text(json.dumps(local), encoding="utf-8")

            reports = load_comparison_reports(directory)

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["provider"], "NVIDIA API Catalog")


START = "<!-- citeproof-benchmarks:start -->"
END = "<!-- citeproof-benchmarks:end -->"


if __name__ == "__main__":
    unittest.main()
