import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from citeproof.bench import main, parse_local_models, parse_model_tool_support
from citeproof.verifier import verify_findings


class BoundedBenchmarkCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "data" / "issues").mkdir(parents=True)
        (self.root / "data" / "gold").mkdir(parents=True)
        (self.root / "demo_repos" / "click-3449-full").mkdir(parents=True)
        issue = {
            "issue_id": "pallets/click#3449",
            "commit": "a5f5aa6d4012d256ccca24638f2642fc371e9f77",
            "title": "Broken pager",
            "body": "A public issue reproduction.",
        }
        gold = {
            "issue_id": issue["issue_id"],
            "pre_fix_commit": issue["commit"],
            "primary_files": ["src/click/termui.py"],
            "supporting_files": ["src/click/_termui_impl.py"],
        }
        (self.root / "data" / "issues" / "click-3449.json").write_text(json.dumps(issue), encoding="utf-8")
        (self.root / "data" / "gold" / "click-3449.json").write_text(json.dumps(gold), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def fake_runner(self, *args, **kwargs):
        self.runner_args = args
        self.runner_kwargs = kwargs
        return 0, {
            "status": "complete",
            "pair": {"model_requests": 6},
            "baseline": {"model_requests": 6},
            "budget_matched": True,
        }

    def test_unknown_case_is_rejected_before_runner(self):
        with self.assertRaises(SystemExit):
            main(["--case", "not-a-case"], root=self.root, runner=self.fake_runner)

    def test_nvidia_route_requires_key_before_runner(self):
        with patch.dict("os.environ", {"NVIDIA_API_KEY": ""}):
            code = main(["--case", "click-3449"], root=self.root, runner=self.fake_runner)

        self.assertEqual(code, 2)
        self.assertFalse(hasattr(self, "runner_args"))

    def test_ollama_route_is_local_sequential_and_skips_hosted_verifier(self):
        output = self.root / "out" / "qwen3.json"

        code = main(
            ["--case", "click-3449", "--provider", "ollama", "--model", "qwen3:1.7b",
             "--output", str(output)],
            root=self.root,
            local_models=["qwen3:1.7b"],
            model_capabilities={"qwen3:1.7b": True},
            runner=self.fake_runner,
        )

        self.assertEqual(code, 0)
        self.assertEqual(self.runner_args[0], self.root / "demo_repos" / "click-3449-full")
        self.assertEqual(self.runner_kwargs["model_id"], "qwen3:1.7b")
        self.assertEqual(self.runner_kwargs["provider"], "Ollama local")
        self.assertIsNone(self.runner_kwargs["verifier"])
        self.assertFalse(self.runner_kwargs["parallel_pair"])
        self.assertEqual(self.runner_kwargs["pair_max_completions"], 4)
        self.assertEqual(self.runner_kwargs["investigator"].__name__, "local_investigator")
        self.assertEqual(self.runner_kwargs["model_settings"]["investigator"]["model_id"], "qwen3:1.7b")

    def test_nvidia_route_preserves_existing_verifier_and_parallel_pair(self):
        with patch.dict("os.environ", {"NVIDIA_API_KEY": "test-key"}):
            code = main(
                ["--case", "click-3449"], root=self.root, runner=self.fake_runner,
            )
        self.assertEqual(code, 0)
        self.assertIs(self.runner_kwargs["verifier"], verify_findings)
        self.assertTrue(self.runner_kwargs["parallel_pair"])
        self.assertEqual(self.runner_kwargs["provider"], "NVIDIA API Catalog")

    def test_rejects_uninstalled_or_cloud_models_without_running(self):
        code = main(
            ["--case", "click-3449", "--provider", "ollama", "--model", "qwen3:8b"],
            root=self.root, local_models=["qwen3:1.7b"], model_capabilities={"qwen3:1.7b": True}, runner=self.fake_runner,
        )
        self.assertEqual(code, 2)
        self.assertFalse(hasattr(self, "runner_args"))

        code = main(
            ["--case", "click-3449", "--provider", "ollama", "--model", "deepseek-v4-flash:cloud"],
            root=self.root, local_models=["deepseek-v4-flash:cloud"], model_capabilities={"deepseek-v4-flash:cloud": True}, runner=self.fake_runner,
        )
        self.assertEqual(code, 2)
        self.assertFalse(hasattr(self, "runner_args"))

    def test_existing_output_is_never_overwritten(self):
        output = self.root / "comparison.json"
        output.write_text("keep", encoding="utf-8")
        code = main(
            ["--case", "click-3449", "--provider", "ollama", "--model", "qwen3:1.7b", "--output", str(output)],
            root=self.root, local_models=["qwen3:1.7b"], model_capabilities={"qwen3:1.7b": True}, runner=self.fake_runner,
        )
        self.assertEqual(code, 2)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep")
        self.assertFalse(hasattr(self, "runner_args"))

    def test_local_model_parser_omits_cloud_and_deduplicates_names(self):
        output = """NAME                       ID              SIZE      MODIFIED
qwen3:1.7b                 8f68893c685c    1.4 GB    4 weeks ago
qwen3:1.7b                 8f68893c685c    1.4 GB    4 weeks ago
deepseek-v4-flash:cloud    ea027821675c    -         6 months ago
"""
        self.assertEqual(parse_local_models(output), ["qwen3:1.7b"])

    def test_model_capability_parser_requires_tools(self):
        self.assertTrue(parse_model_tool_support("Capabilities\n  completion\n  tools\n\nParameters\n"))
        self.assertFalse(parse_model_tool_support("Capabilities\n  completion\n\nParameters\n"))

    def test_local_cli_rejects_models_without_tools_before_inference(self):
        code = main(
            ["--case", "click-3449", "--provider", "ollama", "--model", "gemma:2b"],
            root=self.root,
            local_models=["gemma:2b"],
            model_capabilities={"gemma:2b": False},
            runner=self.fake_runner,
        )
        self.assertEqual(code, 2)
        self.assertFalse(hasattr(self, "runner_args"))

    def test_local_cli_requires_enough_completions_for_source_read(self):
        with self.assertRaises(SystemExit):
            main(
                ["--case", "click-3449", "--provider", "ollama", "--model", "qwen3:1.7b",
                 "--max-completions", "2"],
                root=self.root,
                local_models=["qwen3:1.7b"],
                model_capabilities={"qwen3:1.7b": True},
                runner=self.fake_runner,
            )

        self.assertFalse(hasattr(self, "runner_args"))


if __name__ == "__main__":
    unittest.main()
