import unittest
import json
import subprocess
import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from citeproof.agent import ModelRequestBudget
from citeproof.benchmark import run_budget_matched_comparison, run_benchmark_cli
from citeproof.evaluation import build_comparison_report, export_run_report
from citeproof.models import AgentResult
from citeproof.models import Citation, Finding, VerificationReview


class BudgetMatchedComparisonTests(unittest.TestCase):
    def test_recorded_click_budget_comparison_matches_the_saved_evaluation(self):
        root = Path(__file__).resolve().parents[1]
        report = json.loads(
            Path(root, "data", "benchmarks", "click-3449-live-quality-gates-comparison-20261029.json")
            .read_text(encoding="utf-8")
        )

        self.assertEqual(report["schema"], "citeproof-budget-comparison/v1")
        self.assertEqual(report["pair"]["model_requests"], 11)
        self.assertEqual(report["baseline"]["model_requests"], 11)
        self.assertTrue(report["budget_matched"])
        self.assertEqual(report["pair"]["localization"]["ranked_files"][0], "src/click/_termui_impl.py")
        self.assertEqual(report["baseline"]["localization"]["ranked_files"][0], "src/click/testing.py")
        self.assertEqual(report["pair"]["localization"]["gold_file_recall_at_3"], 0.2)
        self.assertEqual(report["baseline"]["localization"]["gold_file_recall_at_3"], 0.2)
        self.assertEqual(report["pair"]["verification"]["assessment"], "insufficient_evidence")
        self.assertEqual(report["diagnosis_review"], "not_scored")
        self.assertNotIn("primary_files", json.dumps(report))

    def test_latest_live_quality_gates_comparison_preserves_partial_baseline_failure(self):
        root = Path(__file__).resolve().parents[1]
        report = json.loads(
            Path(root, "data", "benchmarks", "click-3449-quality-gates-v2-20261029.json")
            .read_text(encoding="utf-8")
        )

        self.assertEqual(report["schema"], "citeproof-budget-comparison/v2")
        self.assertEqual(report["status"], "incomplete")
        self.assertTrue(report["budget_matched"])
        self.assertEqual(report["pair"]["model_requests"], 10)
        self.assertEqual(report["baseline"]["model_requests"], 10)
        self.assertEqual(report["pair"]["localization"]["status"], "complete")
        self.assertFalse(report["pair"]["localization"]["primary_hit_at_1"])
        self.assertEqual(report["pair"]["localization"]["gold_file_recall_at_3"], 0.2)
        self.assertEqual(report["pair"]["cross_check"], "no_verified_citations")
        self.assertEqual(report["pair"]["verification"]["status"], "skipped")
        self.assertEqual(report["baseline"]["localization"]["status"], "incomplete")
        self.assertIsNone(report["baseline"]["localization"]["gold_file_recall_at_3"])
        self.assertEqual(report["diagnosis_review"]["status"], "not_reviewed")
        self.assertEqual(report["diagnosis_correctness_metric"], "not_scored")
        self.assertEqual(
            report["timings"]["total_seconds"],
            report["timings"]["investigators_seconds"]
            + report["timings"]["verification_seconds"]
            + report["timings"]["baseline_seconds"],
        )

    def test_comparison_records_separate_stage_and_total_timings(self):
        def investigator(*args, **kwargs):
            finding = Finding(
                "claim",
                "explanation",
                [Citation("src/fix.py", "run", 1, 1, "value = True", valid=True)],
            )
            if "request_budget" in kwargs:
                kwargs["request_budget"].used = 4
                count = 4
            else:
                count = 2
            return AgentResult(args[2], [finding], [], model_requests=count)

        review = VerificationReview(status="skipped", model_requests=0)
        with (
            patch("citeproof.benchmark.verify_findings", return_value=review),
            patch("citeproof.benchmark.time.monotonic", side_effect=[10, 12, 12, 13, 13, 16, 17]),
        ):
            comparison = run_budget_matched_comparison(
                SimpleNamespace(commit="pinned-sha"),
                "issue",
                {"issue_id": "org/repo#1", "primary_files": ["src/fix.py"]},
                investigator=investigator,
            )

        self.assertTrue(hasattr(comparison, "stage_timings"))
        self.assertEqual(comparison.stage_timings, {
            "investigators_seconds": 2.0,
            "verification_seconds": 1.0,
            "baseline_seconds": 3.0,
            "total_seconds": 7.0,
        })

    def test_baseline_reserves_correction_inside_pair_request_budget(self):
        calls = []

        def investigator(*args, **kwargs):
            calls.append((args, kwargs))
            count = 2 if len(calls) == 1 else 3 if len(calls) == 2 else 5
            if "request_budget" in kwargs:
                kwargs["request_budget"].used = count
            return AgentResult(args[2], [], [], model_requests=count)

        repo = SimpleNamespace(commit="pinned-sha")
        gold = {
            "issue_id": "org/repo#12",
            "primary_files": ["src/fix.py"],
            "supporting_files": [],
            "diagnosis": "hidden maintainer diagnosis",
        }

        comparison = run_budget_matched_comparison(
            repo,
            "public issue text",
            gold,
            investigator=investigator,
        )

        self.assertEqual(len(calls), 3)
        self.assertEqual([call[0][1] for call in calls], ["public issue text"] * 3)
        pair_calls = [call for call in calls if call[1].get("first_tool") is not None]
        self.assertEqual({call[1]["first_tool"] for call in pair_calls}, {"search_text", "find_symbols"})
        baseline_kwargs = next(call[1] for call in calls if call[1].get("first_tool") is None)
        self.assertEqual(baseline_kwargs["first_tool"], None)
        self.assertEqual(baseline_kwargs["max_completions"], 4)
        self.assertIsInstance(baseline_kwargs["request_budget"], ModelRequestBudget)
        self.assertEqual(baseline_kwargs["request_budget"].limit, 5)
        self.assertEqual(comparison.status, "complete")
        self.assertEqual(comparison.pair_model_requests, 5)
        self.assertEqual(comparison.baseline_model_requests, 5)
        self.assertTrue(comparison.budget_matched)
        self.assertEqual(comparison.pair_metrics.status, "complete")
        self.assertEqual(comparison.baseline_metrics.status, "complete")
        report = build_comparison_report(
            gold,
            repo.commit,
            "meta/muse-glimmer-30b",
            "NVIDIA API Catalog",
            comparison,
        )
        payload = export_run_report(report)[1]
        self.assertEqual(report["schema"], "citeproof-budget-comparison/v2")
        self.assertEqual(report["pair"]["model_requests"], 5)
        self.assertEqual(report["baseline"]["model_requests"], 5)
        self.assertTrue(report["budget_matched"])
        self.assertEqual(report["diagnosis_review"]["status"], "not_reviewed")
        self.assertEqual(report["diagnosis_correctness_metric"], "not_scored")
        self.assertEqual(report["baseline"]["cross_check"], "not_applicable")
        self.assertEqual(report["pair"]["states"]["verification"], "skipped")
        self.assertEqual(report["baseline"]["states"]["cross_check"], "not_applicable")
        self.assertIn("total_seconds", report["timings"])
        self.assertNotIn("primary_files", payload)
        self.assertNotIn("supporting_files", payload)
        self.assertNotIn("hidden maintainer diagnosis", payload)

    def test_verifier_request_is_included_in_pair_budget_and_review_export(self):
        calls = []

        def investigator(*args, **kwargs):
            calls.append((args, kwargs))
            findings = [Finding(
                "claim",
                "explanation",
                [Citation("src/fix.py", "run", 1, 1, "value = True", valid=True)],
            )]
            if "request_budget" in kwargs:
                kwargs["request_budget"].used = 5
                count = 5
            else:
                count = 2
            return AgentResult(args[2], findings, [], model_requests=count)

        review = VerificationReview(
            status="reviewed",
            assessment="supports_candidate",
            selected_finding_id="A-F1",
            supporting_evidence_ids=["A-F1-C1"],
            rationale="Checked evidence supports this candidate.",
            model_requests=1,
        )
        with patch("citeproof.benchmark.verify_findings", return_value=review) as verifier:
            comparison = run_budget_matched_comparison(
                SimpleNamespace(commit="pinned-sha"),
                "public issue text",
                {"issue_id": "org/repo#12", "primary_files": ["src/fix.py"]},
                investigator=investigator,
            )

        verifier.assert_called_once()
        self.assertEqual(comparison.pair_model_requests, 5)
        self.assertEqual(comparison.baseline_model_requests, 5)
        self.assertTrue(comparison.budget_matched)
        self.assertIs(comparison.verification, review)

    def test_incomplete_pair_does_not_spend_calls_on_baseline(self):
        calls = []

        def investigator(*args, **kwargs):
            calls.append((args, kwargs))
            if len(calls) == 1:
                return AgentResult(args[2], [], [], "provider timeout", 2)
            return AgentResult(args[2], [], [], model_requests=3)

        comparison = run_budget_matched_comparison(
            SimpleNamespace(commit="pinned-sha"),
            "issue only",
            {"issue_id": "org/repo#12", "primary_files": ["src/fix.py"]},
            investigator=investigator,
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(comparison.status, "incomplete")
        self.assertIsNone(comparison.baseline_result)
        self.assertEqual(comparison.pair_model_requests, 5)
        self.assertEqual(comparison.baseline_model_requests, 0)
        self.assertFalse(comparison.budget_matched)
        self.assertEqual(comparison.pair_metrics.status, "incomplete")
        self.assertIsNone(comparison.baseline_metrics)

    def test_incomplete_pair_keeps_observed_stage_timings_and_null_baseline_time(self):
        def investigator(*args, **kwargs):
            return AgentResult(args[2], [], [], "provider timeout", 2)

        with (
            patch("citeproof.benchmark.verify_findings", return_value=VerificationReview(status="skipped")),
            patch("citeproof.benchmark.time.monotonic", side_effect=[1, 3, 3, 4, 5]),
        ):
            comparison = run_budget_matched_comparison(
                SimpleNamespace(commit="pinned-sha"),
                "issue",
                {"issue_id": "org/repo#1", "primary_files": ["src/fix.py"]},
                investigator=investigator,
            )

        self.assertEqual(comparison.status, "incomplete")
        self.assertEqual(comparison.stage_timings, {
            "investigators_seconds": 2.0,
            "verification_seconds": 1.0,
            "baseline_seconds": None,
            "total_seconds": 4.0,
        })

    def test_baseline_provider_error_is_incomplete_even_if_request_count_matches(self):
        calls = 0

        def investigator(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls < 3:
                return AgentResult(args[2], [], [], model_requests=2)
            kwargs["request_budget"].used = 4
            return AgentResult(args[2], [], [], "provider timeout", 4)

        comparison = run_budget_matched_comparison(
            SimpleNamespace(commit="pinned-sha"),
            "issue only",
            {"issue_id": "org/repo#12", "primary_files": ["src/fix.py"]},
            investigator=investigator,
        )

        self.assertEqual(comparison.status, "incomplete")
        self.assertTrue(comparison.budget_matched)
        self.assertEqual(comparison.pair_model_requests, 4)
        self.assertEqual(comparison.baseline_model_requests, 4)
        self.assertEqual(comparison.baseline_metrics.status, "incomplete")

    def test_baseline_underuse_is_not_reported_as_budget_matched(self):
        calls = 0

        def investigator(*args, **kwargs):
            nonlocal calls
            calls += 1
            count = 2 if calls < 3 else 3
            if "request_budget" in kwargs:
                kwargs["request_budget"].used = count
            return AgentResult(args[2], [], [], model_requests=count)

        comparison = run_budget_matched_comparison(
            SimpleNamespace(commit="pinned-sha"),
            "issue only",
            {"issue_id": "org/repo#12", "primary_files": ["src/fix.py"]},
            investigator=investigator,
        )

        self.assertEqual(comparison.status, "incomplete")
        self.assertEqual(comparison.pair_model_requests, 4)
        self.assertEqual(comparison.baseline_model_requests, 3)
        self.assertFalse(comparison.budget_matched)

    def test_cli_loads_issue_separately_and_writes_label_private_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_path = root / "repo"
            repo_path.mkdir()
            Path(repo_path, "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
            subprocess.run(["git", "add", "app.py"], cwd=repo_path, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo_path, check=True)
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo_path, check=True, capture_output=True, text=True,
            ).stdout.strip()
            issue_path = root / "issue.json"
            issue_path.write_text(json.dumps({"issue_id": "org/repo#1", "commit": commit, "title": "Bug", "body": "public repro"}), encoding="utf-8")
            gold_path = root / "gold.json"
            gold_path.write_text(json.dumps({
                "issue_id": "org/repo#1",
                "pre_fix_commit": commit,
                "primary_files": ["app.py"],
                "supporting_files": ["tests/test_app.py"],
                "diagnosis": "private diagnosis marker",
            }), encoding="utf-8")
            output_path = root / "nested" / "comparison.json"
            calls = []
            progress = []

            def investigator(*args, **kwargs):
                calls.append((args, kwargs))
                if kwargs.get("on_progress"):
                    kwargs["on_progress"]("Model request started")
                count = 1 if len(calls) < 3 else 2
                if "request_budget" in kwargs:
                    kwargs["request_budget"].used = count
                return AgentResult(args[2], [], [], model_requests=count)

            exit_code, report = run_benchmark_cli(
                repo_path, issue_path, gold_path, output_path,
                on_progress=progress.append,
                investigator=investigator,
            )

            content = output_path.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["issue_id"], "org/repo#1")
            self.assertEqual(len(calls), 3)
            self.assertTrue(any(item.startswith("Investigator A · symptom-first:") for item in progress))
            self.assertTrue(any(item.startswith("Investigator B · structure-first:") for item in progress))
            self.assertTrue(any(item.startswith("Single investigator baseline:") for item in progress))
            self.assertTrue(all(call[0][1] == "Title: Bug\n\npublic repro" for call in calls))
            self.assertNotIn("primary_files", content)
            self.assertNotIn("supporting_files", content)
            self.assertNotIn("private diagnosis marker", content)

    def test_cli_refuses_issue_and_gold_commit_mismatch_before_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue_path = root / "issue.json"
            issue_path.write_text(json.dumps({"issue_id": "org/repo#1", "commit": "issue-sha", "title": "Bug", "body": "text"}), encoding="utf-8")
            gold_path = root / "gold.json"
            gold_path.write_text(json.dumps({
                "issue_id": "org/repo#1",
                "pre_fix_commit": "gold-sha",
                "primary_files": ["app.py"],
            }), encoding="utf-8")
            calls = []

            with self.assertRaisesRegex(ValueError, "pinned commits"):
                run_benchmark_cli(root, issue_path, gold_path, root / "out.json", investigator=lambda *a, **k: calls.append(a))

            self.assertEqual(calls, [])
            self.assertFalse((root / "out.json").exists())


if __name__ == "__main__":
    unittest.main()
