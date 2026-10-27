import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import APITimeoutError

from citeproof.agent import _run_tool, investigate
from citeproof.repo import Repo


class FakeMessage(SimpleNamespace):
    def model_dump(self, exclude_none=False):
        payload = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in self.tool_calls
            ]
        return payload


def response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class AgentFinalTurnTests(unittest.TestCase):
    def test_repository_tool_timeout_is_reported_without_masking_error(self):
        request = httpx.Request("GET", "https://example.com")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            with patch.object(repo, "search_text", side_effect=APITimeoutError(request)):
                result = _run_tool(repo, "search_text", '{"query":"needle"}')

        self.assertEqual(result, "Tool error: APITimeoutError: Request timed out.")

    def test_reserves_last_completion_for_final_answer(self):
        requests = []

        def create(**kwargs):
            requests.append(kwargs)
            if "tools" not in kwargs:
                return response(FakeMessage(
                    content='{"findings":[]}',
                    tool_calls=None,
                ))
            call = SimpleNamespace(
                id=f"call-{len(requests)}",
                function=SimpleNamespace(name="search_text", arguments='{"query":"needle"}'),
            )
            return response(FakeMessage(content=None, tool_calls=[call]))

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            Path(tmp, "sample.py").write_text("needle = True\n", encoding="utf-8")
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(Repo(tmp), "sample issue", "Agent", "test strategy", first_tool="search_text")

        self.assertIsNone(result.error)
        self.assertEqual(result.findings, [])
        self.assertEqual(len(requests), 3)
        self.assertEqual(sum("tools" in request for request in requests), 2)
        self.assertEqual(requests[0]["tool_choice"], {"type": "function", "function": {"name": "search_text"}})
        self.assertEqual([tool["function"]["name"] for tool in requests[0]["tools"]], ["search_text"])
        self.assertNotIn("tools", requests[-1])
        self.assertIn("at most two tool rounds", requests[0]["messages"][0]["content"].lower())
        self.assertIn("exact expression", requests[0]["messages"][0]["content"].lower())
        self.assertIn("line numbers are hints", requests[0]["messages"][0]["content"].lower())
        self.assertIn("qualified method names", requests[0]["messages"][0]["content"].lower())


if __name__ == "__main__":
    unittest.main()
