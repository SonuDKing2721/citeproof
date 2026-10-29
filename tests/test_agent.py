import os
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import APITimeoutError

from citeproof import agent as agent_module
from citeproof.agent import _auto_follow_local_calls, _run_tool, investigate
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
    def test_forced_first_tool_query_overrides_model_selected_query(self):
        seen_queries = []

        def create(**kwargs):
            if "tools" not in kwargs:
                return response(FakeMessage(content='{"findings":[]}', tool_calls=None))
            call = SimpleNamespace(
                id="first-search",
                function=SimpleNamespace(name="find_symbols", arguments='{"query":"invoke"}'),
            )
            return response(FakeMessage(content=None, tool_calls=[call]))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            Path(tmp, "sample.py").write_text("def echo_via_pager():\n    pass\n", encoding="utf-8")
            repo = Repo(tmp)
            original_find_symbols = repo.find_symbols

            def record_query(query):
                seen_queries.append(query)
                return original_find_symbols(query)

            with patch.object(repo, "find_symbols", side_effect=record_query), patch(
                "citeproof.agent.OpenAI", return_value=fake_client,
            ):
                result = investigate(
                    repo, "issue", "Agent", "structure-first",
                    first_tool="find_symbols", first_tool_query="echo_via_pager", max_completions=2,
                )

        self.assertIsNone(result.error)
        self.assertEqual(seen_queries, ["echo_via_pager"])
        self.assertTrue(any('find_symbols({"query": "echo_via_pager"})' in item for item in result.trace))

    def test_model_request_uses_the_bounded_timeout(self):
        requests = []
        progress = []
        self.assertEqual(agent_module.MODEL_REQUEST_TIMEOUT_SECONDS, 120.0)

        def create(**kwargs):
            requests.append(kwargs)
            return response(FakeMessage(content='{"findings":[]}', tool_calls=None))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(
                    Repo(tmp), "sample issue", "Agent", "test strategy",
                    max_completions=1, on_progress=progress.append,
                )

        self.assertIsNone(result.error)
        self.assertEqual(len(requests), 1)
        self.assertLessEqual(requests[0]["timeout"], agent_module.MODEL_REQUEST_TIMEOUT_SECONDS)
        self.assertTrue(any(item.startswith("Model API responded in ") for item in progress))

    def test_agent_deadline_stops_before_spending_a_model_request(self):
        requests = []

        def create(**kwargs):
            requests.append(kwargs)
            return response(FakeMessage(content='{"findings":[]}', tool_calls=None))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            with patch("citeproof.agent.OpenAI", return_value=fake_client), patch(
                "citeproof.agent.AGENT_TIME_BUDGET_SECONDS", 0
            ):
                result = investigate(Repo(tmp), "sample issue", "Agent", "test strategy", max_completions=1)

        self.assertEqual(requests, [])
        self.assertEqual(result.model_requests, 0)
        self.assertIn("time budget", result.error.lower())

    def test_model_timeout_is_reported_as_an_incomplete_provider_timeout(self):
        request = httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")
        progress = []

        def create(**kwargs):
            raise APITimeoutError(request)

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(
                    Repo(tmp), "sample issue", "Agent", "test strategy",
                    max_completions=1, on_progress=progress.append,
                )

        self.assertIn("timed out", result.error.lower())
        self.assertTrue(any(item.startswith("Model request ended after ") for item in progress))

    def test_non_list_citations_get_a_bounded_format_correction(self):
        requests = []
        outputs = [
            '{"findings":[{"claim":"likely cause","explanation":"Inspect the parser.","citations":null}]}',
            '{"findings":[{"claim":"likely cause","explanation":"Inspect the parser.","citations":[]}]}',
        ]

        def create(**kwargs):
            requests.append(kwargs)
            return response(FakeMessage(content=outputs.pop(0), tool_calls=None))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(Repo(tmp), "sample issue", "Agent", "test strategy", max_completions=1)

        self.assertIsNone(result.error)
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].claim, "likely cause")

    def test_traceback_hints_are_passed_as_untrusted_context_without_extra_calls(self):
        requests = []

        def create(**kwargs):
            requests.append(kwargs)
            return response(FakeMessage(content='{"findings":[]}', tool_calls=None))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        issue = '''Traceback (most recent call last):
  File "/workspace/src/sample/reader.py", line 42, in decode
    return payload.decode("utf-8")
UnicodeDecodeError: invalid start byte
'''
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(Repo(tmp), issue, "Agent", "test strategy", max_completions=1)

        user_message = next(message["content"] for message in requests[0]["messages"] if message["role"] == "user")
        self.assertIsNone(result.error)
        self.assertEqual(len(requests), 1)
        self.assertIn("Extracted diagnostic hints from the report (untrusted; verify with repository tools)", user_message)
        self.assertIn("UnicodeDecodeError: invalid start byte", user_message)
        self.assertIn("sample/reader.py:42 in decode", user_message)

    def test_repository_tool_timeout_is_reported_without_masking_error(self):
        request = httpx.Request("GET", "https://example.com")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            with patch.object(repo, "search_text", side_effect=APITimeoutError(request)):
                result = _run_tool(repo, "search_text", '{"query":"needle"}')

        self.assertEqual(result, "Tool error: APITimeoutError: Request timed out.")

    def test_reserves_last_completion_for_final_answer(self):
        requests = []
        progress = []
        final_count = 0

        def create(**kwargs):
            nonlocal final_count
            requests.append(kwargs)
            if "tools" not in kwargs:
                final_count += 1
                return response(FakeMessage(
                    content='{"findings":[]}',
                    tool_calls=None,
                ))
            tool_names = [tool["function"]["name"] for tool in kwargs["tools"]]
            tool_name = "search_text" if "search_text" in tool_names else "read_file"
            arguments = '{"path":"sample.py","start_line":1,"end_line":1}' if tool_name == "read_file" else '{"query":"needle"}'
            call = SimpleNamespace(
                id=f"call-{len(requests)}",
                function=SimpleNamespace(name=tool_name, arguments=arguments),
            )
            if tool_name == "read_file":
                call.function.arguments = '{"path":"sample.py","start_line":1,"end_line":4}'
            return response(FakeMessage(content=None, tool_calls=[call]))

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            Path(tmp, "sample.py").write_text(
                "from lib import helper\n\ndef wrapper():\n    return helper()  # needle\n",
                encoding="utf-8",
            )
            Path(tmp, "lib.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(
                    Repo(tmp), "sample issue", "Agent", "test strategy",
                    first_tool="search_text", on_progress=progress.append,
                )

        self.assertIsNone(result.error)
        self.assertEqual(result.findings, [])
        self.assertEqual(len(requests), 5)
        self.assertEqual(getattr(result, "model_requests", 0), 5)
        self.assertEqual(sum("tools" in request for request in requests), 3)
        self.assertEqual(requests[0]["tool_choice"], {"type": "function", "function": {"name": "search_text"}})
        self.assertEqual([tool["function"]["name"] for tool in requests[0]["tools"]], ["search_text"])
        self.assertEqual([tool["function"]["name"] for tool in requests[1]["tools"]], ["read_file"])
        self.assertEqual(requests[1]["tool_choice"], {"type": "function", "function": {"name": "read_file"}})
        self.assertEqual(
            [tool["function"]["name"] for tool in requests[2]["tools"]],
            ["find_symbols", "read_file"],
        )
        self.assertNotIn("tool_choice", requests[2])
        self.assertTrue(all(request["temperature"] == 0.95 for request in requests))
        self.assertTrue(all(request["max_tokens"] == 8192 for request in requests))
        self.assertTrue(all(request["top_p"] == 1.0 for request in requests))
        self.assertTrue(all(request["reasoning_effort"] == "low" for request in requests))
        self.assertTrue(all(
            {key: request[key] for key in agent_module.INVESTIGATOR_REQUEST_SETTINGS}
            == agent_module.INVESTIGATOR_REQUEST_SETTINGS
            for request in requests
        ))
        final_tool_results = [item["content"] for item in requests[-1]["messages"] if item.get("role") == "tool"]
        self.assertTrue(any("Auto-followed local call 'helper'" in content for content in final_tool_results))
        self.assertTrue(any("1: def helper" in content for content in final_tool_results))
        self.assertNotIn("tools", requests[-1])
        self.assertIn("empty findings", requests[-1]["messages"][-1]["content"].lower())
        self.assertIn("at most three tool rounds", requests[0]["messages"][0]["content"].lower())
        self.assertIn("exact reported symptom", requests[0]["messages"][0]["content"].lower())
        self.assertIn("line numbers are hints", requests[0]["messages"][0]["content"].lower())
        self.assertIn("incomplete scan", requests[0]["messages"][0]["content"].lower())
        self.assertIn("qualified method names", requests[0]["messages"][0]["content"].lower())
        self.assertIn("follow at least one delegation", requests[0]["messages"][0]["content"].lower())
        self.assertIn("failing stack frame", requests[0]["messages"][0]["content"].lower())
        self.assertIn("valueerror about a closed file", requests[0]["messages"][0]["content"].lower())
        self.assertIn("borrowed stream", requests[0]["messages"][0]["content"].lower())
        self.assertIn("in the final tool round, deepen source evidence", requests[0]["messages"][0]["content"].lower())
        self.assertIn("after the initial search, read a source file before searching again", requests[0]["messages"][0]["content"].lower())
        self.assertIn("cautious location hypothesis", requests[0]["messages"][0]["content"].lower())
        self.assertIn("start_line` must be the first quoted source line", requests[0]["messages"][0]["content"])
        self.assertIn("line-number prefixes are metadata", requests[0]["messages"][0]["content"])
        self.assertIn("exact named ast symbol", requests[0]["messages"][0]["content"].lower())
        self.assertIn("escape newline characters inside json strings", requests[0]["messages"][0]["content"].lower())
        self.assertTrue(progress[0].startswith("Model request 1/4"))
        self.assertTrue(any(item.startswith("Tool call: search_text") for item in progress))
        self.assertEqual(progress[-1], "Final evidence checked.")


class AutoFollowResolutionTests(unittest.TestCase):
    def test_follows_module_local_helper_calls_from_read_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "impl.py").write_text(
                "def outer():\n"
                "    return _borrowed_stream()\n"
                "\n"
                "def _borrowed_stream():\n"
                "    return open_stream()\n",
                encoding="utf-8",
            )

            followup = _auto_follow_local_calls(Repo(tmp), "impl.py", 1, 2)

        self.assertIn("Auto-followed local call '_borrowed_stream' in impl.py", followup)
        self.assertIn("def _borrowed_stream():", followup)
        self.assertIn("return open_stream()", followup)

    def test_follows_three_local_calls_when_stream_wrapper_is_the_third_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "impl.py").write_text(
                "def outer():\n"
                "    first()\n"
                "    second()\n"
                "    StreamWrapper()\n"
                "\n"
                "def first():\n"
                "    return 1\n"
                "\n"
                "def second():\n"
                "    return 2\n"
                "\n"
                "class StreamWrapper:\n"
                "    pass\n",
                encoding="utf-8",
            )

            followup = _auto_follow_local_calls(Repo(tmp), "impl.py", 1, 4)

        self.assertIn("Auto-followed local call 'first'", followup)
        self.assertIn("Auto-followed local call 'second'", followup)
        self.assertIn("Auto-followed local call 'StreamWrapper'", followup)

    def test_prefers_imported_helper_over_an_unrelated_same_named_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a_framework.py").write_text(
                "class Framework:\n    def helper(self):\n        return 'wrong'\n",
                encoding="utf-8",
            )
            Path(tmp, "z_app.py").write_text(
                "from helpers import helper\n\ndef run():\n    return helper()\n",
                encoding="utf-8",
            )
            Path(tmp, "helpers.py").write_text(
                "def helper():\n    return 'right'\n",
                encoding="utf-8",
            )
            repo = Repo(tmp)

            followup = _auto_follow_local_calls(repo, "z_app.py", 1, 4)

        self.assertIn("helpers.py", followup)
        self.assertNotIn("a_framework.py", followup)

    def test_resolves_package_relative_helper_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp, "src", "sample")
            package.mkdir(parents=True)
            Path(package, "api.py").write_text(
                "from ._implementation import helper\n\ndef run():\n    return helper()\n",
                encoding="utf-8",
            )
            Path(package, "_implementation.py").write_text(
                "def helper():\n    return 'right'\n",
                encoding="utf-8",
            )
            Path(tmp, "unrelated.py").write_text(
                "def helper():\n    return 'wrong'\n",
                encoding="utf-8",
            )
            repo = Repo(tmp)

            followup = _auto_follow_local_calls(repo, "src/sample/api.py", 1, 4)

        self.assertIn("src/sample/_implementation.py", followup)
        self.assertNotIn("unrelated.py", followup)

    def test_does_not_fuzzy_follow_an_unimported_same_named_symbol(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "z_app.py").write_text(
                "def run():\n    return plugin.helper()\n",
                encoding="utf-8",
            )
            Path(tmp, "unrelated.py").write_text(
                "def helper():\n    return 'unrelated'\n",
                encoding="utf-8",
            )
            repo = Repo(tmp)

            followup = _auto_follow_local_calls(repo, "z_app.py", 1, 2)

        self.assertEqual(followup, "")


class ModelRequestBudgetTests(unittest.TestCase):
    def test_budget_counts_calls_and_refuses_requests_after_its_limit(self):
        budget_type = getattr(agent_module, "ModelRequestBudget", None)
        self.assertIsNotNone(budget_type)
        budget = budget_type(limit=1)
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            return "response"

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        self.assertEqual(budget.request(client, {"model": "test"}), "response")
        with self.assertRaisesRegex(RuntimeError, "budget"):
            budget.request(client, {"model": "test"})

        self.assertEqual(budget.used, 1)
        self.assertEqual(len(calls), 1)

    def test_correction_attempt_obeys_budget_and_is_counted(self):
        budget_type = getattr(agent_module, "ModelRequestBudget", None)
        self.assertIsNotNone(budget_type)
        budget = budget_type(limit=1)
        requests = []

        def create(**kwargs):
            requests.append(kwargs)
            return response(FakeMessage(content="not JSON", tool_calls=None))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(
                    Repo(tmp), "issue", "Agent", "test", max_completions=1, request_budget=budget,
                )

        self.assertEqual(len(requests), 1)
        self.assertEqual(budget.used, 1)
        self.assertEqual(getattr(result, "model_requests", 0), 1)
        self.assertIn("budget", result.error.lower())

    def test_rejects_provider_tool_call_not_offered_in_the_current_round(self):
        requests = []

        def create(**kwargs):
            requests.append(kwargs)
            if "tools" not in kwargs:
                return response(FakeMessage(content='{"findings":[]}', tool_calls=None))
            call = SimpleNamespace(
                id=f"call-{len(requests)}",
                function=SimpleNamespace(name="search_text", arguments='{"query":"needle"}'),
            )
            return response(FakeMessage(content=None, tool_calls=[call]))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            Path(tmp, "sample.py").write_text("needle = True\n", encoding="utf-8")
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(Repo(tmp), "sample issue", "Agent", "test strategy", first_tool="search_text")

        self.assertIsNone(result.error)
        self.assertTrue(any("rejected unavailable tool search_text" in item.lower() for item in result.trace))

    def test_reports_malformed_model_json_as_response_error_not_inference_failure(self):
        def create(**kwargs):
            if "tools" not in kwargs:
                return response(FakeMessage(content="not JSON", tool_calls=None))
            name = kwargs["tools"][0]["function"]["name"]
            arguments = '{"query":"needle"}' if name == "search_text" else '{"path":"sample.py","start_line":1,"end_line":1}'
            call = SimpleNamespace(
                id="call",
                function=SimpleNamespace(name=name, arguments=arguments),
            )
            return response(FakeMessage(content=None, tool_calls=[call]))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            Path(tmp, "sample.py").write_text("needle = True\n", encoding="utf-8")
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(Repo(tmp), "sample issue", "Agent", "test strategy", first_tool="search_text")

        self.assertIsNotNone(result.error)
        self.assertIn("required JSON format", result.error)
        self.assertNotIn("Inference failed", result.error)

    def test_retries_rejected_source_quote_once_and_uses_verified_replacement(self):
        requests = []
        final_count = 0

        def create(**kwargs):
            nonlocal final_count
            requests.append(kwargs)
            if "tools" in kwargs:
                call = SimpleNamespace(
                    id="source-read",
                    function=SimpleNamespace(
                        name="read_file",
                        arguments='{"path":"sample.py","start_line":1,"end_line":1}',
                    ),
                )
                return response(FakeMessage(content=None, tool_calls=[call]))
            final_count += 1
            quote = "not in the source" if final_count == 1 else "needle = True"
            content = json.dumps({
                "findings": [{
                    "claim": "Relevant source location",
                    "explanation": "Cautious location hypothesis.",
                    "citations": [{
                        "path": "sample.py",
                        "symbol": "",
                        "start_line": 1,
                        "end_line": 1,
                        "quote": quote,
                    }],
                }],
            })
            return response(FakeMessage(content=content, tool_calls=None))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            Path(tmp, "sample.py").write_text("needle = True\n", encoding="utf-8")
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(
                    Repo(tmp), "sample issue", "Agent", "test strategy",
                    first_tool="read_file", max_completions=2,
                )

        self.assertIsNone(result.error)
        self.assertEqual(len(requests), 3)
        self.assertNotIn("tools", requests[-1])
        self.assertIn("rejected", requests[-1]["messages"][-1]["content"].lower())
        self.assertIn("first quoted source line", requests[-1]["messages"][-1]["content"].lower())
        self.assertIn("empty symbol", requests[-1]["messages"][-1]["content"].lower())
        self.assertEqual(result.model_requests, 3)
        self.assertEqual(len(result.findings), 1)
        self.assertTrue(result.findings[0].citations[0].valid)

    def test_keeps_original_finding_when_citation_repair_times_out(self):
        requests = []

        def create(**kwargs):
            requests.append(kwargs)
            if "tools" in kwargs:
                call = SimpleNamespace(
                    id="source-read",
                    function=SimpleNamespace(
                        name="read_file",
                        arguments='{"path":"sample.py","start_line":1,"end_line":1}',
                    ),
                )
                return response(FakeMessage(content=None, tool_calls=[call]))
            if len(requests) == 3:
                raise APITimeoutError(request=httpx.Request("POST", "https://example.com"))
            content = json.dumps({
                "findings": [{
                    "claim": "Relevant source location",
                    "explanation": "Cautious location hypothesis.",
                    "citations": [{
                        "path": "sample.py",
                        "symbol": "",
                        "start_line": 1,
                        "end_line": 1,
                        "quote": "not in the source",
                    }],
                }],
            })
            return response(FakeMessage(content=content, tool_calls=None))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        progress = []
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            Path(tmp, "sample.py").write_text("needle = True\n", encoding="utf-8")
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(
                    Repo(tmp), "sample issue", "Agent", "test strategy",
                    first_tool="read_file", max_completions=2, on_progress=progress.append,
                )

        self.assertIsNone(result.error)
        self.assertEqual(len(requests), 3)
        self.assertEqual(len(result.findings), 1)
        self.assertFalse(result.findings[0].citations[0].valid)
        self.assertTrue(any("correction failed" in item.lower() for item in result.trace))
        self.assertTrue(any("keeping the original result with unverified citations" in item.lower() for item in progress))

    def test_retries_malformed_json_once_and_accepts_corrected_valid_citation(self):
        requests = []
        final_count = 0

        def create(**kwargs):
            nonlocal final_count
            requests.append(kwargs)
            if "tools" not in kwargs:
                final_count += 1
                content = "not JSON" if final_count == 1 else (
                    '{"findings":[{"claim":"Relevant source location",'
                    '"explanation":"Cautious finding from source.","citations":[{'
                    '"path":"sample.py","symbol":"","start_line":1,"end_line":1,'
                    '"quote":"needle = True"}]}]}'
                )
                return response(FakeMessage(content=content, tool_calls=None))
            name = kwargs["tools"][0]["function"]["name"]
            arguments = '{"query":"needle"}' if name == "search_text" else '{"path":"sample.py","start_line":1,"end_line":1}'
            call = SimpleNamespace(id=f"call-{len(requests)}", function=SimpleNamespace(name=name, arguments=arguments))
            return response(FakeMessage(content=None, tool_calls=[call]))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            Path(tmp, "sample.py").write_text("needle = True\n", encoding="utf-8")
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(Repo(tmp), "sample issue", "Agent", "test strategy", first_tool="search_text")

        self.assertIsNone(result.error)
        self.assertEqual(len(requests), 5)
        self.assertEqual(len(result.findings), 1)
        self.assertTrue(result.findings[0].citations[0].valid)
        self.assertIn("not valid json", requests[-1]["messages"][-1]["content"].lower())
        roles = [message["role"] for message in requests[-1]["messages"]]
        self.assertFalse(any(left == right == "user" for left, right in zip(roles, roles[1:])))
        self.assertIn("untrusted output", requests[-1]["messages"][-1]["content"].lower())

    def test_rejects_tool_calls_in_final_synthesis_without_executing_them(self):
        requests = []

        def create(**kwargs):
            requests.append(kwargs)
            if "tools" not in kwargs:
                call = SimpleNamespace(
                    id="unexpected-final-call",
                    function=SimpleNamespace(name="search_text", arguments='{"query":"should-not-run"}'),
                )
                return response(FakeMessage(content=None, tool_calls=[call]))
            name = kwargs["tools"][0]["function"]["name"]
            arguments = '{"query":"needle"}' if name == "search_text" else '{"path":"sample.py","start_line":1,"end_line":1}'
            call = SimpleNamespace(id=f"call-{len(requests)}", function=SimpleNamespace(name=name, arguments=arguments))
            return response(FakeMessage(content=None, tool_calls=[call]))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            Path(tmp, "sample.py").write_text("needle = True\n", encoding="utf-8")
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(Repo(tmp), "sample issue", "Agent", "test strategy", first_tool="search_text")

        self.assertIn("after its investigation budget", result.error)
        self.assertIn("Rejected tool call during final synthesis", " ".join(result.trace))
        self.assertEqual(len(requests), 4)

    def test_retries_empty_final_answer_once_and_keeps_valid_source_citation(self):
        requests = []
        final_count = 0

        def create(**kwargs):
            nonlocal final_count
            requests.append(kwargs)
            if "tools" not in kwargs:
                final_count += 1
                content = '{"findings":[]}' if final_count == 1 else (
                    '{"findings":[{"claim":"The reported name occurs in the source.",'
                    '"explanation":"Cautious location hypothesis from the checked source.",'
                    '"citations":[{"path":"sample.py","symbol":"","start_line":1,'
                    '"end_line":1,"quote":"needle = True"}]}]}'
                )
                return response(FakeMessage(content=content, tool_calls=None))
            name = kwargs["tools"][0]["function"]["name"]
            arguments = '{"query":"needle"}' if name == "search_text" else '{"path":"sample.py","start_line":1,"end_line":1}'
            call = SimpleNamespace(id=f"call-{len(requests)}", function=SimpleNamespace(name=name, arguments=arguments))
            return response(FakeMessage(content=None, tool_calls=[call]))

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            Path(tmp, "sample.py").write_text("needle = True\n", encoding="utf-8")
            with patch("citeproof.agent.OpenAI", return_value=fake_client):
                result = investigate(Repo(tmp), "sample issue", "Agent", "test strategy", first_tool="search_text")

        self.assertIsNone(result.error)
        self.assertEqual(len(requests), 5)
        self.assertEqual(len(result.findings), 1)
        self.assertTrue(result.findings[0].citations[0].valid)


if __name__ == "__main__":
    unittest.main()
