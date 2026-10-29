import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DiagnosticHintTests(unittest.TestCase):
    def _extract(self, issue: str) -> list[str]:
        module_path = PROJECT_ROOT / "citeproof" / "diagnostics.py"
        self.assertTrue(module_path.is_file(), f"Missing traceback hint extractor: {module_path}")
        from citeproof.diagnostics import extract_diagnostic_hints

        return extract_diagnostic_hints(issue)

    def test_extracts_exception_and_deepest_frames_without_absolute_paths(self):
        issue = '''Traceback (most recent call last):
  File "/tmp/venv/lib/python3.12/site-packages/pkg/wrapper.py", line 9, in call
    return parse(value)
  File "/workspace/src/pkg/parser.py", line 51, in parse
    return value.encode("utf-8")
TypeError: expected str, got bytes
'''

        self.assertEqual(
            self._extract(issue),
            [
                "Exception: TypeError: expected str, got bytes",
                "Traceback frame: pkg/parser.py:51 in parse",
                "Traceback frame: pkg/wrapper.py:9 in call",
            ],
        )

    def test_normalizes_windows_paths_and_limits_traceback_frames(self):
        issue = '''Traceback (most recent call last):
  File "D:\\repo\\src\\mylib\\outer.py", line 10, in outer
  File "D:\\repo\\src\\mylib\\middle.py", line 20, in middle
  File "D:\\repo\\src\\mylib\\inner.py", line 30, in inner
  File "D:\\repo\\src\\mylib\\leaf.py", line 40, in leaf
ValueError: invalid value
'''

        self.assertEqual(
            self._extract(issue),
            [
                "Exception: ValueError: invalid value",
                "Traceback frame: mylib/leaf.py:40 in leaf",
                "Traceback frame: mylib/inner.py:30 in inner",
                "Traceback frame: mylib/middle.py:20 in middle",
            ],
        )

    def test_plain_issue_without_traceback_returns_no_hints(self):
        self.assertEqual(self._extract("The file chooser shows the wrong label."), [])

    def test_zero_frame_limit_keeps_exception_without_including_traceback(self):
        from citeproof.diagnostics import extract_diagnostic_hints

        issue = '''Traceback (most recent call last):
  File "/workspace/src/sample/reader.py", line 42, in decode
TypeError: invalid input
'''

        self.assertEqual(
            extract_diagnostic_hints(issue, max_frames=0),
            ["Exception: TypeError: invalid input"],
        )

    def test_reproducer_api_hints_prioritize_product_calls_over_test_harness_calls(self):
        from citeproof.diagnostics import extract_reproducer_api_hints

        issue = '''```python
from click import command, echo_via_pager
from click.testing import CliRunner

@command()
def cli():
    echo_via_pager("Hello, Click!")

CliRunner().invoke(cli)
```'''

        self.assertEqual(extract_reproducer_api_hints(issue), ["echo_via_pager"])

    def test_reproducer_api_hint_handles_aliases_and_ignores_non_python_or_bad_blocks(self):
        from citeproof.diagnostics import extract_reproducer_api_hints

        issue = (
            "```text\n"
            "from pkg import wrong\n"
            "``` \n"
            "```python\n"
            "from pkg.rendering import render as show\n"
            "from pkg.testing import Runner\n"
            "\n"
            "Runner().invoke(show)\n"
            "show(\"hello\")\n"
            "```"
        )

        self.assertEqual(extract_reproducer_api_hints(issue), ["render"])

    def test_reproducer_api_hint_resolves_aliased_test_harness_modules(self):
        from citeproof.diagnostics import extract_reproducer_api_hints

        issue = '''```python
import click.testing as runner_api
from click import echo_via_pager

def cli():
    echo_via_pager("Hello")

runner_api.CliRunner().invoke(cli)
```'''

        self.assertEqual(extract_reproducer_api_hints(issue), ["echo_via_pager"])


if __name__ == "__main__":
    unittest.main()
