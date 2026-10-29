"""Small, explicit file-localization metrics for human-curated issue cases."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import re
from typing import Any

from .comparison import compare_evidence
from .model_config import (
    INVESTIGATOR_REQUEST_SETTINGS,
    MODEL_REQUEST_TIMEOUT_SECONDS,
    VERIFIER_REQUEST_SETTINGS,
)
from .models import AgentResult, VerificationReview

DIAGNOSIS_REVIEW_STATES = {
    "not_reviewed",
    "supported",
    "partly_supported",
    "unsupported",
    "incorrect",
}


@dataclass(frozen=True)
class LocalizationMetrics:
    status: str
    ranked_files: tuple[str, ...]
    primary_hit_at_1: bool | None
    gold_file_recall_at_3: float | None


def score_localization(
    results: list[AgentResult],
    gold_case: dict[str, Any],
    minimum_agents: int = 2,
) -> LocalizationMetrics:
    """Rank checked files by support among the required completed agents.

    By default, a complete two-agent run is required. Set ``minimum_agents=1``
    for a single-investigator baseline. The metric uses human-curated primary
    files for hit@1 and primary plus supporting files for recall@3; changed-file
    labels remain proxies for causal correctness.
    """
    if minimum_agents < 1:
        raise ValueError("minimum_agents must be at least one.")
    if len(results) < minimum_agents or any(result.error for result in results[:minimum_agents]):
        return LocalizationMetrics("incomplete", (), None, None)

    primary_files = set(gold_case.get("primary_files", []))
    gold_files = primary_files | set(gold_case.get("supporting_files", []))
    if not primary_files or not gold_files:
        return LocalizationMetrics("missing_gold_labels", (), None, None)

    support: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    sequence = 0
    for result in results[:minimum_agents]:
        cited_by_agent: list[str] = []
        agent_paths: set[str] = set()
        for citation in (
            citation
            for finding in result.findings
            for citation in finding.citations
        ):
            if citation.valid and citation.path and citation.path not in agent_paths:
                agent_paths.add(citation.path)
                cited_by_agent.append(citation.path)
        for path in cited_by_agent:
            support[path] += 1
            first_seen.setdefault(path, sequence)
            sequence += 1

    ranked_files = tuple(sorted(support, key=lambda path: (-support[path], first_seen[path])))
    top_three = set(ranked_files[:3])
    return LocalizationMetrics(
        status="complete",
        ranked_files=ranked_files,
        primary_hit_at_1=bool(ranked_files and ranked_files[0] in primary_files),
        gold_file_recall_at_3=len(top_three & gold_files) / len(gold_files),
    )


def run_status_payload(
    results: list[AgentResult],
    gold_case: dict[str, Any],
    verification: VerificationReview | None,
    workflow_kind: str,
    minimum_agents: int = 2,
    diagnosis_review_status: str = "not_reviewed",
) -> dict[str, str]:
    """Project independent workflow states for the UI and exported report."""
    if workflow_kind not in {
        "live_pair",
        "cached_pair_live_review",
        "cached_demo",
        "single_agent_baseline",
    }:
        raise ValueError("Unknown Citeproof workflow kind.")
    if not isinstance(diagnosis_review_status, str) or diagnosis_review_status not in DIAGNOSIS_REVIEW_STATES:
        raise ValueError("Unknown diagnosis review state.")

    metrics = score_localization(results, gold_case, minimum_agents=minimum_agents)
    required_results = results[:minimum_agents]
    investigation_complete = (
        len(results) >= minimum_agents
        and not any(result.error for result in required_results)
    )
    citations = [
        citation
        for result in required_results
        for finding in result.findings
        for citation in finding.citations
    ]
    valid_citations = sum(citation.valid for citation in citations)
    if not citations:
        citation_validation = "not_present"
    elif valid_citations == 0:
        citation_validation = "none_valid"
    elif valid_citations < len(citations):
        citation_validation = "partly_valid"
    else:
        citation_validation = "all_valid"

    if workflow_kind == "single_agent_baseline":
        cross_check = "not_applicable"
    else:
        cross_check = compare_evidence(results).status

    localization_status = {
        "complete": "scored",
        "incomplete": "incomplete",
        "missing_gold_labels": "missing_labels",
    }.get(metrics.status, "not_scored")
    return {
        "investigation": "complete" if investigation_complete else "incomplete",
        "citation_validation": citation_validation,
        "cross_check": cross_check,
        "verification": verification.status if verification else "not_requested",
        "localization": localization_status,
        "diagnosis_review": diagnosis_review_status,
        "workflow_kind": workflow_kind,
    }


def _finding_summary(results: list[AgentResult], minimum_agents: int) -> dict[str, str | int]:
    required_results = results[:minimum_agents]
    investigation_complete = (
        len(required_results) == minimum_agents
        and not any(result.error for result in required_results)
    )
    findings = [finding for result in required_results for finding in result.findings]
    verified_citation_count = sum(
        citation.valid
        for finding in findings
        for citation in finding.citations
    )
    if not investigation_complete:
        status = "incomplete"
    elif not findings:
        status = "no_findings"
    elif verified_citation_count == 0:
        status = "no_verified_citations"
    else:
        status = "verified_citations_present"
    return {
        "status": status,
        "finding_count": len(findings),
        "agents_with_findings": sum(bool(result.findings) for result in required_results),
        "verified_citation_count": verified_citation_count,
        "required_agents": minimum_agents,
    }


def _safe_timings(timings: dict[str, Any] | None) -> dict[str, float | None]:
    timings = timings if isinstance(timings, dict) else {}
    normalized: dict[str, float | None] = {}
    for name in (
        "investigators_seconds",
        "verification_seconds",
        "baseline_seconds",
        "total_seconds",
    ):
        value = timings.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            normalized[name] = None
        elif not math.isfinite(value) or value < 0:
            normalized[name] = None
        else:
            normalized[name] = round(float(value), 3)
    return normalized


def _safe_request_counts(value: object) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    investigators = value.get("investigators")
    verification = value.get("verification")
    if any(
        isinstance(count, bool) or not isinstance(count, int) or count < 0 or count > 100000
        for count in (investigators, verification)
    ):
        return None
    return {
        "investigators": investigators,
        "verification": verification,
        "total": investigators + verification,
    }


def build_run_report(
    gold_case: dict[str, Any],
    repository_commit: str,
    model_id: str,
    provider: str,
    results: list[AgentResult],
    verification: VerificationReview | None = None,
    *,
    workflow_kind: str = "live_pair",
    run_timestamp_utc: str | None = None,
    timings: dict[str, Any] | None = None,
    minimum_agents: int = 2,
    model_settings: dict[str, Any] | None = None,
    model_request_counts: dict[str, Any] | None = None,
    diagnosis_review_status: str = "not_reviewed",
    diagnosis_review_reviewer: str | None = None,
    diagnosis_review_note: str | None = None,
) -> dict[str, Any]:
    """Build a shareable one-run report without copying hidden file labels."""
    metrics = score_localization(results, gold_case, minimum_agents=minimum_agents)
    evidence_comparison = compare_evidence(results)
    agents_with_verified_citations = sum(
        any(citation.valid for finding in result.findings for citation in finding.citations)
        for result in results[:minimum_agents]
    )
    if agents_with_verified_citations < minimum_agents:
        evidence_note = (
            f"Verified citations were returned by {agents_with_verified_citations} of "
            f"{minimum_agents} required investigator(s); this report does not show full-run corroboration."
        )
    else:
        evidence_note = (
            "Each required investigator returned at least one verified citation. This supports source locations, "
            "not diagnosis correctness."
        )
    if not isinstance(diagnosis_review_status, str) or diagnosis_review_status not in DIAGNOSIS_REVIEW_STATES:
        raise ValueError("Unknown diagnosis review state.")
    review_note = diagnosis_review_note[:1200].strip() if isinstance(diagnosis_review_note, str) else ""
    if diagnosis_review_status != "not_reviewed" and not review_note:
        diagnosis_review_status = "not_reviewed"
        diagnosis_review_reviewer = None
    states = run_status_payload(
        results,
        gold_case,
        verification,
        workflow_kind,
        minimum_agents=minimum_agents,
        diagnosis_review_status=diagnosis_review_status,
    )
    diagnosis_review = {
        "status": diagnosis_review_status,
        "reviewer": diagnosis_review_reviewer[:80] if isinstance(diagnosis_review_reviewer, str) else None,
        "note": review_note if diagnosis_review_status != "not_reviewed" else "",
    }
    timestamp = run_timestamp_utc
    if not isinstance(timestamp, str) or not timestamp.strip():
        timestamp = None if workflow_kind != "live_pair" else datetime.now(timezone.utc).isoformat()
    timing_payload = _safe_timings(timings)
    if model_settings is None and workflow_kind in {"live_pair", "single_agent_baseline"}:
        reported_model_settings = {
            "investigator": {
                "model_id": model_id,
                "request_parameters": dict(INVESTIGATOR_REQUEST_SETTINGS),
                "timeout_seconds": MODEL_REQUEST_TIMEOUT_SECONDS,
            },
            "verifier": {
                "model_id": model_id,
                "request_parameters": dict(VERIFIER_REQUEST_SETTINGS),
                "timeout_seconds": MODEL_REQUEST_TIMEOUT_SECONDS,
            },
        }
    else:
        reported_model_settings = model_settings
    request_counts = _safe_request_counts(model_request_counts)
    if request_counts is None:
        required_results = results[:minimum_agents]
        investigator_count = (
            sum(max(0, int(result.model_requests)) for result in required_results)
            if all(result.model_requests_known for result in required_results)
            else None
        )
        verification_count = (
            max(0, min(int(verification.model_requests), 1))
            if verification is not None
            else None
        )
        request_counts = {
            "investigators": investigator_count,
            "verification": verification_count,
            "total": (
                investigator_count + verification_count
                if investigator_count is not None and verification_count is not None
                else None
            ),
        }
    cross_check_status = (
        "not_applicable" if workflow_kind == "single_agent_baseline" else evidence_comparison.status
    )
    return {
        "schema": "citeproof-evaluation/v2",
        "run_timestamp_utc": timestamp,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "issue_id": gold_case.get("issue_id", "unknown"),
        "repository_commit": repository_commit,
        "model_id": model_id,
        "provider": provider,
        "status": metrics.status,
        "states": states,
        "workflow": {
            "kind": workflow_kind,
            "run_timestamp_utc": timestamp,
            "timings": timing_payload,
        },
        "model_settings": reported_model_settings,
        "metrics": {
            "ranked_files": list(metrics.ranked_files),
            "primary_hit_at_1": metrics.primary_hit_at_1,
            "gold_file_recall_at_3": metrics.gold_file_recall_at_3,
        },
        "finding_summary": _finding_summary(results, minimum_agents),
        "evidence": {
            "agents_with_verified_citations": agents_with_verified_citations,
            "cross_check_status": cross_check_status,
            "note": evidence_note,
        },
        "diagnosis_review": diagnosis_review,
        "diagnosis_correctness_metric": "not_scored",
        "model_requests": request_counts,
        "verification": verification_report_payload(verification),
        "evaluation_note": gold_case.get("evaluation_note", ""),
        "metric_note": (
            "File labels are human-curated proxies from the merged fix. These metrics do not score diagnosis correctness."
        ),
        "agents": [
            {
                "name": result.agent_name,
                "error": result.error,
                "model_requests": (
                    max(0, int(result.model_requests)) if result.model_requests_known else None
                ),
                "tool_trace": result.trace,
                "findings": [
                    {
                        "claim": finding.claim,
                        "explanation": finding.explanation,
                        "citations": [
                            {
                                "path": citation.path,
                                "symbol": citation.symbol,
                                "start_line": citation.start_line,
                                "end_line": citation.end_line,
                                "quote": citation.quote,
                                "valid": citation.valid,
                                "reason": citation.reason,
                            }
                            for citation in finding.citations
                        ],
                    }
                    for finding in result.findings
                ],
            }
            for result in results
        ],
    }


def verification_report_payload(verification: VerificationReview | None) -> dict[str, Any]:
    if verification is None:
        return {
            "status": "not_run",
            "assessment": "not_run",
            "model_requests": 0,
            "selected_finding_id": None,
            "supporting_evidence_ids": [],
            "challenging_evidence_ids": [],
            "rationale": "",
            "test_scenario": None,
            "test_assertion": None,
            "error": None,
        }
    return {
        "status": verification.status,
        "assessment": verification.assessment,
        "model_requests": max(0, min(int(verification.model_requests), 1)),
        "selected_finding_id": verification.selected_finding_id,
        "supporting_evidence_ids": list(verification.supporting_evidence_ids[:8]),
        "challenging_evidence_ids": list(verification.challenging_evidence_ids[:8]),
        "rationale": verification.rationale[:1200],
        "test_scenario": verification.test_scenario[:500] if verification.test_scenario else None,
        "test_assertion": verification.test_assertion[:500] if verification.test_assertion else None,
        "error": verification.error[:300] if verification.error else None,
    }


def build_comparison_report(
    gold_case: dict[str, Any],
    repository_commit: str,
    model_id: str,
    provider: str,
    comparison: Any,
    verification: VerificationReview | None = None,
) -> dict[str, Any]:
    """Create a shareable pair-versus-single report without exposing labels."""
    run_timestamp = datetime.now(timezone.utc).isoformat()
    comparison_timings = _safe_timings(getattr(comparison, "stage_timings", None))
    effective_verification = verification or getattr(comparison, "verification", None)
    pair_total = None
    if comparison_timings["investigators_seconds"] is not None and comparison_timings["verification_seconds"] is not None:
        pair_total = round(
            comparison_timings["investigators_seconds"] + comparison_timings["verification_seconds"],
            3,
        )
    pair_timings = {
        "investigators_seconds": comparison_timings["investigators_seconds"],
        "verification_seconds": comparison_timings["verification_seconds"],
        "total_seconds": pair_total,
    }
    baseline_timings = {
        "baseline_seconds": comparison_timings["baseline_seconds"],
        "total_seconds": comparison_timings["baseline_seconds"],
    }
    pair_report = build_run_report(
        gold_case,
        repository_commit,
        model_id,
        provider,
        list(comparison.pair_results),
        verification=effective_verification,
        workflow_kind="live_pair",
        run_timestamp_utc=run_timestamp,
        timings=pair_timings,
    )
    baseline_results = [comparison.baseline_result] if comparison.baseline_result else []
    baseline_report = build_run_report(
        gold_case,
        repository_commit,
        model_id,
        provider,
        baseline_results,
        workflow_kind="single_agent_baseline",
        run_timestamp_utc=run_timestamp if baseline_results else None,
        timings=baseline_timings,
        minimum_agents=1,
    )

    def metric_payload(metrics: LocalizationMetrics | None) -> dict[str, Any]:
        if metrics is None:
            return {
                "status": "not_run",
                "ranked_files": [],
                "primary_hit_at_1": None,
                "gold_file_recall_at_3": None,
            }
        return {
            "status": metrics.status,
            "ranked_files": list(metrics.ranked_files),
            "primary_hit_at_1": metrics.primary_hit_at_1,
            "gold_file_recall_at_3": metrics.gold_file_recall_at_3,
        }

    return {
        "schema": "citeproof-budget-comparison/v2",
        "run_timestamp_utc": run_timestamp,
        "issue_id": gold_case.get("issue_id", "unknown"),
        "repository_commit": repository_commit,
        "model_id": model_id,
        "provider": provider,
        "status": comparison.status,
        "budget_matched": comparison.budget_matched,
        "timings": comparison_timings,
        "pair": {
            "model_requests": comparison.pair_model_requests,
            "localization": metric_payload(comparison.pair_metrics),
            "finding_summary": pair_report["finding_summary"],
            "cross_check": pair_report["evidence"]["cross_check_status"],
            "states": pair_report["states"],
            "model_settings": pair_report["model_settings"],
            "verification": verification_report_payload(effective_verification),
            "agents": pair_report["agents"],
        },
        "baseline": {
            "model_requests": comparison.baseline_model_requests,
            "localization": metric_payload(comparison.baseline_metrics),
            "finding_summary": baseline_report["finding_summary"],
            "cross_check": "not_applicable",
            "states": baseline_report["states"],
            "model_settings": baseline_report["model_settings"],
            "agents": baseline_report["agents"],
        },
        "diagnosis_review": {"status": "not_reviewed", "reviewer": None, "note": ""},
        "diagnosis_correctness_metric": "not_scored",
        "metric_note": (
            "File labels are human-curated proxies from the merged fix. These metrics do not score diagnosis correctness. "
            "Equal request counts do not imply equal token use or equal reasoning quality."
        ),
    }


def export_run_report(report: dict[str, Any]) -> tuple[str, str]:
    """Return a safe descriptive filename and deterministic JSON payload."""
    issue_slug = re.sub(r"[^a-z0-9]+", "-", str(report.get("issue_id", "run")).casefold()).strip("-")
    status_slug = re.sub(r"[^a-z0-9]+", "-", str(report.get("status", "unknown")).casefold()).strip("-")
    filename = f"citeproof-{issue_slug or 'run'}-{status_slug or 'unknown'}.json"
    content = json.dumps(report, ensure_ascii=False, indent=2)
    return filename, content
