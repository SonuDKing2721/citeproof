import tempfile
import threading
import unittest
from pathlib import Path

from citeproof.models import AgentResult
from citeproof.orchestration import investigate_pair
from citeproof.repo import Repo


class PairOrchestrationTests(unittest.TestCase):
    def test_structure_first_is_seeded_with_api_from_issue_reproducer(self):
        captured = []
        issue = '''```python
from click import command, echo_via_pager
from click.testing import CliRunner

@command()
def cli():
    echo_via_pager("Hello")

CliRunner().invoke(cli)
```'''

        def investigator(repo, issue, agent_name, strategy, **kwargs):
            captured.append((agent_name, kwargs.get("first_tool_query")))
            return AgentResult(agent_name, [], [])

        with tempfile.TemporaryDirectory() as tmp:
            investigate_pair(Repo(Path(tmp)), issue, investigator=investigator)

        self.assertIn(("Investigator B · structure-first", "echo_via_pager"), captured)
        self.assertIn(("Investigator A · symptom-first", None), captured)

    def test_runs_investigators_concurrently_and_returns_stable_agent_order(self):
        barrier = threading.Barrier(2)

        def investigator(repo, issue, agent_name, strategy, **kwargs):
            barrier.wait(timeout=2)
            return AgentResult(agent_name, [], [strategy])

        with tempfile.TemporaryDirectory() as tmp:
            result = investigate_pair(Repo(Path(tmp)), "public issue", investigator=investigator)

        self.assertEqual(len(result), 2)
        self.assertIn("Investigator A", result[0].agent_name)
        self.assertIn("Investigator B", result[1].agent_name)

    def test_progress_from_workers_is_delivered_to_caller_thread(self):
        caller_thread = threading.get_ident()
        progress_threads = []

        def investigator(repo, issue, agent_name, strategy, on_progress=None, **kwargs):
            on_progress("Model request 1/4…")
            return AgentResult(agent_name, [], [])

        with tempfile.TemporaryDirectory() as tmp:
            investigate_pair(
                Repo(Path(tmp)), "public issue", investigator=investigator,
                on_progress=lambda label, message: progress_threads.append(threading.get_ident()),
            )

        self.assertTrue(progress_threads)
        self.assertTrue(all(thread_id == caller_thread for thread_id in progress_threads))


if __name__ == "__main__":
    unittest.main()
