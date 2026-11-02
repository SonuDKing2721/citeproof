from pathlib import Path
import unittest

import yaml


class ContinuousIntegrationWorkflowTests(unittest.TestCase):
    def test_workflow_runs_offline_test_suite_on_windows_and_linux(self):
        root = Path(__file__).resolve().parents[1]
        workflow_path = root / ".github" / "workflows" / "tests.yml"
        workflow_text = workflow_path.read_text(encoding="utf-8")
        config = yaml.load(workflow_text, Loader=yaml.BaseLoader)

        self.assertIn("push", config["on"])
        self.assertIn("pull_request", config["on"])
        jobs = config["jobs"]
        self.assertEqual(len(jobs), 1)
        job = next(iter(jobs.values()))
        self.assertEqual(job["strategy"]["matrix"]["os"], ["ubuntu-latest", "windows-latest"])
        self.assertEqual(job["strategy"]["matrix"]["python-version"], ["3.12"])
        commands = "\n".join(step.get("run", "") for step in job["steps"])
        self.assertIn("pip install -r requirements.txt", commands)
        self.assertIn("python -m pytest -q tests", commands)

    def test_workflow_contains_no_model_inference_credentials_or_live_calls(self):
        root = Path(__file__).resolve().parents[1]
        workflow_text = (root / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

        self.assertNotIn("NVIDIA_API_KEY=", workflow_text)
        self.assertNotIn("OPENAI_API_KEY=", workflow_text)
        self.assertNotIn("citeproof.bench", workflow_text)
        self.assertNotIn("ghp_", workflow_text)
        self.assertNotIn("sk-", workflow_text)


if __name__ == "__main__":
    unittest.main()
