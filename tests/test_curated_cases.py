import unittest
from pathlib import Path

from citeproof.cases import load_curated_cases


class CuratedCasesTests(unittest.TestCase):
    def test_all_issue_and_gold_pairs_are_aligned_and_documented(self):
        project_dir = Path(__file__).resolve().parents[1]

        cases = load_curated_cases(project_dir)

        self.assertEqual(
            set(cases),
            {
                "Curated case · Click #2877 · smoke",
                "Curated case · Click #3449 · multi-PR",
                "Curated case · Click #2994 · Windows",
                "Curated case · Click #3059 · CLI help",
                "Curated case · HTTPX #2883 · historical",
                "Curated case · Pydantic #13957 · fresh",
                "Curated case · sse-starlette #211 · smoke",
                "Curated case · openai-python #3811 · smoke",
            },
        )
        for case in cases.values():
            issue = case["issue"]
            gold = case["gold"]
            self.assertEqual(issue["issue_id"], gold["issue_id"])
            self.assertEqual(issue["commit"], gold["pre_fix_commit"])
            self.assertTrue(gold["primary_files"])
            self.assertTrue(gold["evaluation_note"])
            self.assertTrue(case["repo_dir"])

    def test_new_cases_describe_their_limits(self):
        project_dir = Path(__file__).resolve().parents[1]
        cases = load_curated_cases(project_dir)

        windows_note = cases["Curated case · Click #2994 · Windows"]["gold"]["evaluation_note"].lower()
        help_note = cases["Curated case · Click #3059 · CLI help"]["gold"]["evaluation_note"].lower()
        self.assertIn("windows", windows_note)
        self.assertIn("cutoff", windows_note)
        self.assertIn("cutoff", help_note)

    def test_httpx_case_is_marked_as_historical_smoke_only(self):
        project_dir = Path(__file__).resolve().parents[1]
        cases = load_curated_cases(project_dir)

        note = cases["Curated case · HTTPX #2883 · historical"]["gold"]["evaluation_note"].lower()
        self.assertIn("historical", note)
        self.assertIn("smoke", note)
        self.assertIn("contamination", note)

    def test_pydantic_case_has_fresh_issue_context_and_a_caution(self):
        project_dir = Path(__file__).resolve().parents[1]
        cases = load_curated_cases(project_dir)
        case = cases["Curated case · Pydantic #13957 · fresh"]

        self.assertEqual(case["issue"]["issue_id"], "pydantic/pydantic#13957")
        self.assertEqual(
            case["issue"]["commit"],
            "ca359e009fcfaff2a80df33cb99ee6ab21aaf033",
        )
        note = case["gold"]["evaluation_note"].lower()
        self.assertIn("october 2026", note)
        self.assertIn("cutoff", note)
        self.assertIn("smoke", note)


if __name__ == "__main__":
    unittest.main()
