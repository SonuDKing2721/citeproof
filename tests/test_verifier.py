import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import APITimeoutError

from citeproof.models import AgentResult, Citation, Finding
from citeproof.model_config import VERIFIER_REQUEST_SETTINGS
from citeproof.verifier import build_candidates, parse_verifier_response, verify_findings


def citation(path, quote, valid=True):
    return Citation(path, "parse", 3, 4, quote, valid, "checked" if valid else "rejected")


def pair_results(*, second_valid=True, error=None):
    return [
        AgentResult("Investigator A · symptom-first", [Finding("A claim", "A explanation", [citation("src/a.py", "return left")])], []),
        AgentResult("Investigator B · structure-first", [Finding("B claim", "B explanation", [citation("src/b.py", "return right", second_valid)])], [], error),
    ]


def response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class VerifierCandidateTests(unittest.TestCase):
    def test_candidates_include_only_checked_citations_and_stable_ids(self):
        results = pair_results(second_valid=False)

        candidates, evidence = build_candidates(results)

        self.assertEqual([item["finding_id"] for item in candidates], ["A-F1"])
        self.assertEqual([item["evidence_id"] for item in evidence], ["A-F1-C1"])
        self.assertNotIn("return right", repr(evidence))

    def test_accepts_only_allowlisted_candidate_and_evidence_ids(self):
        candidates, evidence = build_candidates(pair_results())
        payload = '{"assessment":"supports_candidate","selected_finding_id":"A-F1","supporting_evidence_ids":["A-F1-C1"],"challenging_evidence_ids":["B-F1-C1"],"rationale":"The checked lines match the claim.","regression_test":{"scenario":"Pass the reported value through the public entry point.","assertion":"Assert the output preserves the value."}}'

        review = parse_verifier_response(payload, candidates, evidence)

        self.assertEqual(review.status, "reviewed")
        self.assertEqual(review.selected_finding_id, "A-F1")
        self.assertEqual(review.supporting_evidence_ids, ["A-F1-C1"])
        self.assertEqual(review.challenging_evidence_ids, ["B-F1-C1"])
        self.assertEqual(review.test_scenario, "Pass the reported value through the public entry point.")

    def test_rejects_unknown_evidence_or_finding_ids(self):
        candidates, evidence = build_candidates(pair_results())
        payload = '{"assessment":"supports_candidate","selected_finding_id":"invented","supporting_evidence_ids":["new-file.py:99"],"challenging_evidence_ids":[],"rationale":"Looks right.","regression_test":null}'

        with self.assertRaisesRegex(ValueError, "allowlisted"):
            parse_verifier_response(payload, candidates, evidence)

    def test_requires_supported_assessment_to_cite_selected_finding_evidence(self):
        candidates, evidence = build_candidates(pair_results())
        payload = '{"assessment":"supports_candidate","selected_finding_id":"A-F1","supporting_evidence_ids":["B-F1-C1"],"challenging_evidence_ids":[],"rationale":"The claim is supported.","regression_test":null}'

        with self.assertRaisesRegex(ValueError, "selected finding"):
            parse_verifier_response(payload, candidates, evidence)

    def test_rejects_malformed_response_and_invalid_assessment(self):
        candidates, evidence = build_candidates(pair_results())

        with self.assertRaises(ValueError):
            parse_verifier_response("not JSON", candidates, evidence)
        with self.assertRaisesRegex(ValueError, "assessment"):
            parse_verifier_response('{"assessment":"correct","selected_finding_id":null,"supporting_evidence_ids":[],"challenging_evidence_ids":[],"rationale":"x","regression_test":null}', candidates, evidence)
        with self.assertRaisesRegex(ValueError, "assessment"):
            parse_verifier_response('{"assessment":[],"selected_finding_id":null,"supporting_evidence_ids":[],"challenging_evidence_ids":[],"rationale":"x","regression_test":null}', candidates, evidence)


class VerifierCallTests(unittest.TestCase):
    def test_review_uses_one_request_without_tools_and_sends_only_verified_evidence(self):
        requests = []
        output = '{"assessment":"supports_candidate","selected_finding_id":"A-F1","supporting_evidence_ids":["A-F1-C1"],"challenging_evidence_ids":["B-F1-C1"],"rationale":"The checked source supports the first hypothesis.","regression_test":{"scenario":"Call the public API with the reported value.","assertion":"Assert the result matches the expected behavior."}}'

        def create(**kwargs):
            requests.append(kwargs)
            return response(output)

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        results = pair_results()
        results[0].findings[0].citations.append(citation("src/private.py", "DO NOT SEND", False))
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            with patch("citeproof.verifier.OpenAI", return_value=fake_client):
                review = verify_findings("A public bug report", results)

        self.assertEqual(review.status, "reviewed")
        self.assertEqual(review.model_requests, 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["timeout"], 120)
        self.assertEqual(requests[0]["reasoning_effort"], "low")
        self.assertEqual(
            {key: requests[0][key] for key in VERIFIER_REQUEST_SETTINGS},
            VERIFIER_REQUEST_SETTINGS,
        )
        self.assertNotIn("tools", requests[0])
        prompt = repr(requests[0]["messages"])
        self.assertIn("return left", prompt)
        self.assertNotIn("DO NOT SEND", prompt)

    def test_skips_without_two_successful_agents_or_both_sets_of_checked_quotes(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            with patch("citeproof.verifier.OpenAI") as client:
                failed = verify_findings("issue", pair_results(error="timeout"))
                missing = verify_findings("issue", pair_results(second_valid=False))

        self.assertEqual(failed.status, "skipped")
        self.assertEqual(missing.status, "skipped")
        self.assertEqual(failed.model_requests + missing.model_requests, 0)
        client.assert_not_called()

    def test_reports_missing_key_without_calling_model(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("citeproof.verifier.OpenAI") as client:
                review = verify_findings("issue", pair_results())

        self.assertEqual(review.status, "unavailable")
        self.assertEqual(review.model_requests, 0)
        client.assert_not_called()

    def test_timeout_is_bounded_and_keeps_investigation_results_outside_review(self):
        request = httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")

        def create(**kwargs):
            raise APITimeoutError(request)

        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}):
            with patch("citeproof.verifier.OpenAI", return_value=fake_client) as constructor:
                review = verify_findings("issue", pair_results())

        self.assertEqual(review.status, "unavailable")
        self.assertEqual(review.model_requests, 1)
        self.assertIn("timed out", review.error.lower())
        self.assertEqual(constructor.call_args.kwargs["timeout"], 120)


if __name__ == "__main__":
    unittest.main()
