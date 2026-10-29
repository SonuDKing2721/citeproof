"""Run a request-budget-matched single-investigator control."""

from collections.abc import Callable
from dataclasses import dataclass, field
import argparse
import json
from pathlib import Path
import sys
import time

from .agent import MAX_FINAL_RESPONSE_RETRIES, MODEL_ID, ModelRequestBudget, investigate
from .evaluation import (
    LocalizationMetrics,
    build_comparison_report,
    export_run_report,
    score_localization,
)
from .models import AgentResult, VerificationReview
from .orchestration import PAIR_STRATEGIES, investigate_pair
from .repo import Repo
from .verifier import verify_findings
from dotenv import load_dotenv


@dataclass(frozen=True)
class BudgetMatchedComparison:
    status: str
    pair_results: tuple[AgentResult, AgentResult]
    baseline_result: AgentResult | None
    pair_model_requests: int
    baseline_model_requests: int
    budget_matched: bool
    pair_metrics: LocalizationMetrics
    baseline_metrics: LocalizationMetrics | None
    verification: VerificationReview | None = None
    stage_timings: dict[str, float | None] = field(default_factory=dict)

BASELINE_STRATEGY = (
    "Investigate the issue independently. Use the repository tools to locate the relevant public API, "
    "follow its implementation into helpers, and cite only source evidence you inspected. State uncertainty."
)


def _progress_callback(
    on_progress: Callable[[str], None] | None,
    label: str,
) -> Callable[[str], None] | None:
    if on_progress is None:
        return None
    return lambda message: on_progress(f"{label}: {message}")


def run_budget_matched_comparison(
    repo: Repo,
    issue: str,
    gold_case: dict,
    on_progress: Callable[[str], None] | None = None,
    investigator: Callable[..., AgentResult] = investigate,
) -> BudgetMatchedComparison:
    """Run two investigators, then one control with the same request count.

    Gold labels are used only after inference to score localization; they are
    never passed to an investigator. If either member of the pair fails, the
    baseline is skipped so the run does not spend more calls on a bad control.
    """
    total_started = time.monotonic()
    investigators_started = total_started
    pair = investigate_pair(
        repo,
        issue,
        on_progress=(lambda label, message: on_progress(f"{label}: {message}")) if on_progress else None,
        investigator=investigator,
    )
    investigators_ended = time.monotonic()
    verification_started = time.monotonic()
    verification = verify_findings(
        issue,
        list(pair),
        on_progress=_progress_callback(on_progress, "Bounded evidence verifier"),
    )
    verification_ended = time.monotonic()
    stage_timings = {
        "investigators_seconds": round(max(0.0, investigators_ended - investigators_started), 3),
        "verification_seconds": round(max(0.0, verification_ended - verification_started), 3),
        "baseline_seconds": None,
        "total_seconds": None,
    }
    investigator_request_count = sum(max(0, int(result.model_requests)) for result in pair)
    pair_request_count = investigator_request_count + max(0, int(verification.model_requests))
    pair_metrics = score_localization(list(pair), gold_case)
    if any(result.error for result in pair) or pair_request_count == 0:
        stage_timings["total_seconds"] = round(max(0.0, time.monotonic() - total_started), 3)
        return BudgetMatchedComparison(
            status="incomplete",
            pair_results=pair,
            baseline_result=None,
            pair_model_requests=pair_request_count,
            baseline_model_requests=0,
            budget_matched=False,
            pair_metrics=pair_metrics,
            baseline_metrics=None,
            verification=verification,
            stage_timings=stage_timings,
        )

    baseline_budget = ModelRequestBudget(limit=pair_request_count)
    baseline_completion_budget = max(1, pair_request_count - MAX_FINAL_RESPONSE_RETRIES)
    baseline_started = time.monotonic()
    baseline_result = investigator(
        repo,
        issue,
        "Single investigator · neutral",
        BASELINE_STRATEGY,
        first_tool=None,
        on_progress=_progress_callback(on_progress, "Single investigator baseline"),
        max_completions=baseline_completion_budget,
        request_budget=baseline_budget,
    )
    baseline_ended = time.monotonic()
    stage_timings["baseline_seconds"] = round(max(0.0, baseline_ended - baseline_started), 3)
    stage_timings["total_seconds"] = round(max(0.0, time.monotonic() - total_started), 3)
    baseline_request_count = baseline_budget.used
    budget_matched = baseline_request_count == pair_request_count
    baseline_metrics = score_localization([baseline_result], gold_case, minimum_agents=1)
    count_is_consistent = baseline_request_count == max(0, int(baseline_result.model_requests))
    complete = (
        not baseline_result.error
        and budget_matched
        and count_is_consistent
        and pair_metrics.status == "complete"
        and baseline_metrics.status == "complete"
    )

    return BudgetMatchedComparison(
        status="complete" if complete else "incomplete",
        pair_results=pair,
        baseline_result=baseline_result,
        pair_model_requests=pair_request_count,
        baseline_model_requests=baseline_request_count,
        budget_matched=budget_matched,
        pair_metrics=pair_metrics,
        baseline_metrics=baseline_metrics,
        verification=verification,
        stage_timings=stage_timings,
    )


def run_benchmark_cli(
    repo_path: str | Path,
    issue_path: str | Path,
    gold_path: str | Path,
    output_path: str | Path,
    on_progress: Callable[[str], None] | None = None,
    investigator: Callable[..., AgentResult] = investigate,
) -> tuple[int, dict]:
    """Load separate issue/gold files, verify the pin, and save a report."""
    issue_data = json.loads(Path(issue_path).read_text(encoding="utf-8"))
    gold_case = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    if not isinstance(issue_data, dict) or not isinstance(gold_case, dict):
        raise ValueError("Issue and gold files must contain JSON objects.")
    if issue_data.get("issue_id") != gold_case.get("issue_id"):
        raise ValueError("Issue and gold files must identify the same issue.")
    pinned_commit = gold_case.get("pre_fix_commit")
    if not isinstance(pinned_commit, str) or not pinned_commit.strip():
        raise ValueError("Gold file must include its pinned pre-fix commit.")
    if issue_data.get("commit") and issue_data["commit"] != pinned_commit:
        raise ValueError("Issue and gold files specify different pinned commits.")
    if not gold_case.get("primary_files"):
        raise ValueError("Gold file must include at least one primary file label.")

    title = str(issue_data.get("title", "")).strip()
    body = str(issue_data.get("body", "")).strip()
    if not title and not body:
        raise ValueError("Issue file must include a title or body.")
    issue_text = f"Title: {title}\n\n{body}".strip()

    repo = Repo(repo_path, expected_commit=pinned_commit)
    comparison = run_budget_matched_comparison(
        repo,
        issue_text,
        gold_case,
        on_progress=on_progress,
        investigator=investigator,
    )
    report = build_comparison_report(
        gold_case,
        repo.commit or pinned_commit,
        MODEL_ID,
        "NVIDIA API Catalog",
        comparison,
        verification=comparison.verification,
    )
    _, content = export_run_report(report)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content + "\n", encoding="utf-8")
    return (0 if comparison.status == "complete" else 1), report


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run Citeproof's request-budget-matched baseline.")
    parser.add_argument("--repo", required=True, help="Path to the clean, pinned pre-fix repository")
    parser.add_argument("--issue", required=True, help="Path to the public issue JSON file")
    parser.add_argument("--gold", required=True, help="Path to the separate gold-label JSON file")
    parser.add_argument("--output", required=True, help="Path for the comparison report JSON")
    args = parser.parse_args(argv)
    try:
        exit_code, report = run_benchmark_cli(
            args.repo,
            args.issue,
            args.gold,
            args.output,
            on_progress=lambda message: print(message, flush=True),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Benchmark could not run: {exc}", file=sys.stderr)
        return 2
    print(
        f"{report['status']}: pair={report['pair']['model_requests']} requests, "
        f"baseline={report['baseline']['model_requests']} requests, "
        f"budget_matched={report['budget_matched']}; report saved to {args.output}"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
