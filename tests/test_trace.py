import unittest

from citeproof.trace import make_trace_event, normalize_trace_events


class TraceSummaryTests(unittest.TestCase):
    def test_read_file_event_keeps_path_and_line_range_but_withholds_source_text(self):
        source = "10: password = 'DO_NOT_PERSIST'\n11: return password\n"

        event = make_trace_event(
            "read_file",
            '{"path":"src/module.py","start_line":10,"end_line":11}',
            source,
        )

        self.assertEqual(event, {
            "tool": "read_file",
            "request_summary": "src/module.py:10-11",
            "result_summary": "Read 2 source lines; source text withheld.",
        })
        self.assertNotIn("DO_NOT_PERSIST", str(event))

    def test_search_event_counts_hits_without_persisting_matched_source(self):
        event = make_trace_event(
            "search_text",
            '{"query":"secret symptom"}',
            "src/a.py:4: secret symptom value\nsrc/b.py:8: secret symptom branch",
        )

        self.assertEqual(event["request_summary"], "query: secret symptom")
        self.assertEqual(event["result_summary"], "Found 2 matching source lines; contents withheld.")
        self.assertNotIn("secret symptom value", str(event))

    def test_malformed_arguments_and_unrecognized_tool_are_bounded(self):
        event = make_trace_event("shell", "x" * 2000, "x" * 2000)

        self.assertEqual(event["tool"], "rejected")
        self.assertLessEqual(len(event["request_summary"]), 120)
        self.assertLessEqual(len(event["result_summary"]), 160)
        self.assertNotIn("x" * 200, str(event))

    def test_normalizing_rejected_tool_events_is_safe(self):
        event = make_trace_event("read_directory", {"path": "src"}, "Tool error: not allowlisted.")

        events, known = normalize_trace_events([event])

        self.assertTrue(known)
        self.assertEqual(events, [event])

    def test_persisted_trace_events_reject_extra_fields_and_redact_credentials(self):
        values = [
            {
                "tool": "search_text",
                "request_summary": "query: " + ("nvapi-" + "A" * 32),
                "result_summary": "Found 2 matching source lines; contents withheld.",
            },
            {
                "tool": "read_file",
                "request_summary": "src/module.py:1-2",
                "result_summary": "Read 2 source lines; source text withheld.",
                "raw_source": "password = 'must not persist'",
            },
        ]

        events, known = normalize_trace_events(values)

        self.assertFalse(known)
        self.assertEqual(events, [])

    def test_valid_persisted_trace_events_are_bounded_and_redacted(self):
        values = [{
            "tool": "search_text",
            "request_summary": "query: " + ("nvapi-" + "A" * 32),
            "result_summary": "Found 2 matching source lines; contents withheld.",
        }]

        events, known = normalize_trace_events(values)

        self.assertTrue(known)
        self.assertEqual(events[0]["request_summary"], "query: [redacted]")
        self.assertNotIn("nvapi-", str(events))


if __name__ == "__main__":
    unittest.main()
