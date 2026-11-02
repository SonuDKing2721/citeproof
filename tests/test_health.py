import unittest
from types import SimpleNamespace

from citeproof.health import check_endpoint


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class HealthCheckTests(unittest.TestCase):
    def test_reports_ready_when_small_request_returns_within_five_seconds(self):
        clock = FakeClock()

        def create(**kwargs):
            self.assertEqual(kwargs["max_tokens"], 5)
            self.assertEqual(kwargs["timeout"], 15)
            clock.now += 2
            return object()

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        result = check_endpoint(client, clock=clock)

        self.assertEqual(result, {"status": "ready", "elapsed_seconds": 2, "error": None})

    def test_reports_slow_when_small_request_returns_after_five_seconds(self):
        clock = FakeClock()

        def create(**kwargs):
            clock.now += 7

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

        result = check_endpoint(client, clock=clock)

        self.assertEqual(result["status"], "slow")
        self.assertEqual(result["elapsed_seconds"], 7)

    def test_reports_unavailable_when_the_timed_request_raises(self):
        clock = FakeClock()

        def create(**kwargs):
            clock.now += 15
            raise TimeoutError("request exceeded timeout")

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

        result = check_endpoint(client, clock=clock)

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["elapsed_seconds"], 15)
        self.assertEqual(result["error"], "TimeoutError")

    def test_reports_missing_client_without_attempting_a_request(self):
        result = check_endpoint(None)

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["elapsed_seconds"], 0)
        self.assertEqual(result["error"], "missing_api_key")


if __name__ == "__main__":
    unittest.main()
