"""Load the small, human-curated set of public issue cases."""

import json
from pathlib import Path
from typing import Any


CASE_MANIFEST = (
    ("Curated case · Click #2877 · smoke", "click-2877", "click"),
    ("Curated case · Click #3449 · multi-PR", "click-3449", "click-3449-full"),
    ("Curated case · Click #2994 · Windows", "click-2994", "click-2994"),
    ("Curated case · Click #3059 · CLI help", "click-3059", "click-3059"),
    ("Curated case · HTTPX #2883 · historical", "httpx-2883", "httpx-2883"),
    ("Curated case · Pydantic #13957 · fresh", "pydantic-13957", "pydantic-13957"),
    ("Curated case · sse-starlette #211 · smoke", "sse-starlette-211", "sse-starlette-211"),
    ("Curated case · openai-python #3811 · smoke", "openai-python-3811", "openai-python-3811"),
)


def load_curated_cases(project_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Load issue and gold JSON separately, rejecting mismatched pairs."""
    root = Path(project_dir)
    cases: dict[str, dict[str, Any]] = {}
    for label, slug, repo_dir in CASE_MANIFEST:
        issue = json.loads((root / "data" / "issues" / f"{slug}.json").read_text(encoding="utf-8"))
        gold = json.loads((root / "data" / "gold" / f"{slug}.json").read_text(encoding="utf-8"))
        if not isinstance(issue, dict) or not isinstance(gold, dict):
            raise ValueError(f"Curated case {slug} must have JSON object files.")
        if issue.get("issue_id") != gold.get("issue_id"):
            raise ValueError(f"Curated issue and gold labels do not match for {slug}.")
        if issue.get("commit") != gold.get("pre_fix_commit"):
            raise ValueError(f"Curated issue and gold files do not share a pre-fix pin for {slug}.")
        if not gold.get("primary_files"):
            raise ValueError(f"Curated case {slug} has no primary file labels.")
        cases[label] = {"issue": issue, "gold": gold, "repo_dir": repo_dir}
    return cases
