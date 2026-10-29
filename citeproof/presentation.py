"""Small presentation helpers for clear citation states."""

from datetime import datetime, timezone
import math

from .checker import check_result
from .evaluation import DIAGNOSIS_REVIEW_STATES
from .models import AgentResult, Citation, Finding, VerificationReview
from .repo import Repo


def citation_quote_details(citation: Citation) -> tuple[str, str]:
    label = "Verified source quote" if citation.valid else "Rejected model quote"
    return label, citation.quote


def agent_result_card_status(result: AgentResult) -> tuple[str, str]:
    """Summarize model findings without implying unchecked claims are supported."""
    if result.error:
        return "Incomplete run", result.error
    if not result.findings:
        return "No findings returned", "No model claim was returned for evidence review."

    citations = [citation for finding in result.findings for citation in finding.citations]
    verified = sum(citation.valid for citation in citations)
    finding_label = f"{len(result.findings)} finding{'s' if len(result.findings) != 1 else ''} returned"
    if not citations:
        return finding_label + " · no citations", "The returned claims have no source citations and remain unverified."
    if verified == 0:
        return (
            f"{finding_label} · 0/{len(citations)} citations verified",
            "No citation passed the source checker; treat these claims as unverified.",
        )
    if verified < len(citations):
        return (
            f"{finding_label} · {verified}/{len(citations)} citations verified",
            "Some citations passed and others were rejected; inspect each quote. Diagnosis still needs human review.",
        )
    return (
        f"{finding_label} · {verified}/{len(citations)} citations verified",
        "All supplied quotes matched the selected source; diagnosis still needs human review.",
    )


def make_run_snapshot(
    results: list[AgentResult],
    repo_commit: str | None,
    issue_title: str,
    gold_case: dict | None,
    source: str = "live",
    run_timestamp_utc: str | None = None,
    model_id: str | None = None,
    provider: str | None = None,
    verification: VerificationReview | None = None,
    workflow_kind: str | None = None,
    timings: dict | None = None,
    model_settings: dict | None = None,
    model_request_counts: dict | None = None,
    diagnosis_review: dict | None = None,
) -> dict:
    """Keep the completed UI run available when Streamlit reruns the script."""
    normalized_timestamp = _safe_timestamp(run_timestamp_utc)
    if source == "live" and normalized_timestamp is None:
        normalized_timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "results": results,
        "repo_commit": repo_commit,
        "issue_title": issue_title,
        "gold_case": gold_case,
        "source": source,
        "run_timestamp_utc": normalized_timestamp,
        "model_id": model_id,
        "provider": provider,
        "verification": verification,
        "workflow_kind": workflow_kind or ("live_pair" if source == "live" else "cached_demo"),
        "timings": _safe_timings(timings),
        "model_settings": _safe_model_settings(model_settings),
        "model_request_counts": _safe_request_counts(model_request_counts),
        "diagnosis_review": normalize_diagnosis_review(diagnosis_review),
    }


def snapshot_from_saved_report(
    report: dict,
    gold_case: dict,
    issue_title: str,
    repo: Repo,
) -> dict:
    """Restore a cached two-agent run only after checking case and commit identity.

    Citation validity stored in the JSON is ignored. Every quote is rechecked
    against the current pinned checkout before it is displayed.
    """
    if report.get("schema") not in {"citeproof-evaluation/v1", "citeproof-evaluation/v2"}:
        raise ValueError("Saved report has an unsupported schema.")
    if report.get("issue_id") != gold_case.get("issue_id"):
        raise ValueError("Saved report belongs to a different issue.")
    if not repo.commit:
        raise ValueError("Load saved runs only from a pinned curated repository.")
    if report.get("repository_commit") != repo.commit:
        raise ValueError("Saved report belongs to a different repository commit.")
    raw_agents = report.get("agents")
    if not isinstance(raw_agents, list) or len(raw_agents) != 2:
        raise ValueError("Saved report must contain exactly two agent results.")

    results: list[AgentResult] = []
    for raw_agent in raw_agents:
        if not isinstance(raw_agent, dict):
            raise ValueError("Saved report contains an invalid agent result.")
        raw_findings = raw_agent.get("findings", [])
        findings: list[Finding] = []
        if not isinstance(raw_findings, list):
            raise ValueError("Saved report contains an invalid findings list.")
        for raw_finding in raw_findings[:2]:
            if not isinstance(raw_finding, dict):
                continue
            citations: list[Citation] = []
            raw_citations = raw_finding.get("citations", [])
            if isinstance(raw_citations, list):
                for raw_citation in raw_citations[:4]:
                    if not isinstance(raw_citation, dict):
                        continue
                    try:
                        citations.append(Citation(
                            path=str(raw_citation["path"])[:300],
                            symbol=str(raw_citation.get("symbol", ""))[:160],
                            start_line=int(raw_citation["start_line"]),
                            end_line=int(raw_citation["end_line"]),
                            quote=str(raw_citation["quote"])[:2000],
                        ))
                    except (KeyError, TypeError, ValueError):
                        continue
            findings.append(Finding(
                claim=str(raw_finding.get("claim", ""))[:500],
                explanation=str(raw_finding.get("explanation", ""))[:1200],
                citations=citations,
            ))
        raw_trace = raw_agent.get("tool_trace", [])
        trace = [str(item)[:300] for item in raw_trace[:100]] if isinstance(raw_trace, list) else []
        error = raw_agent.get("error")
        result = AgentResult(
            agent_name=str(raw_agent.get("name", "Investigator"))[:120],
            findings=findings,
            trace=trace,
            error=str(error)[:300] if error else None,
            model_requests=_safe_request_count(raw_agent.get("model_requests")),
            model_requests_known=(
                isinstance(raw_agent.get("model_requests"), int)
                and not isinstance(raw_agent.get("model_requests"), bool)
            ),
        )
        results.append(check_result(repo, result))

    verification = verification_from_payload(report.get("verification"))

    workflow = report.get("workflow")
    workflow = workflow if isinstance(workflow, dict) else {}
    run_source = report.get("run_source")
    workflow_kind = workflow.get("kind")
    if workflow_kind not in {"live_pair", "cached_pair_live_review", "cached_demo", "single_agent_baseline"}:
        workflow_kind = (
            "cached_pair_live_review"
            if run_source == "live_verifier_on_cached_agent_pair"
            else "cached_demo"
        )
    source_timestamp = workflow.get("run_timestamp_utc") or report.get("run_timestamp_utc")
    snapshot = make_run_snapshot(
        results,
        repo.commit,
        issue_title,
        gold_case,
        source="saved",
        run_timestamp_utc=_safe_timestamp(source_timestamp),
        model_id=str(report.get("model_id", ""))[:120],
        provider=str(report.get("provider", ""))[:120],
        verification=verification,
        workflow_kind=workflow_kind,
        timings=_safe_timings(workflow.get("timings")),
        model_settings=_safe_model_settings(report.get("model_settings")),
        model_request_counts=_safe_request_counts(report.get("model_requests")),
        diagnosis_review=report.get("diagnosis_review"),
    )
    for name in ("run_source", "agent_pair_source_timestamp_utc", "verifier_run_timestamp_utc"):
        value = report.get(name)
        if isinstance(value, str):
            snapshot[name] = value[:120]
    return snapshot


def _safe_timestamp(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 80:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.isoformat()


def _safe_request_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return min(max(value, 0), 1000)


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


def _safe_timings(value: object) -> dict[str, float | None]:
    source = value if isinstance(value, dict) else {}
    normalized: dict[str, float | None] = {}
    for name in ("investigators_seconds", "verification_seconds", "baseline_seconds", "total_seconds"):
        duration = source.get(name)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            normalized[name] = None
        elif not math.isfinite(duration) or duration < 0:
            normalized[name] = None
        else:
            normalized[name] = round(float(duration), 3)
    return normalized


def _safe_model_settings(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    roles: dict = {}
    for role in ("investigator", "verifier"):
        raw = value.get(role)
        if not isinstance(raw, dict):
            continue
        model_id = raw.get("model_id")
        model_id = model_id[:120] if isinstance(model_id, str) else None
        timeout = raw.get("timeout_seconds")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
            or timeout > 600
        ):
            timeout = None
        raw_parameters = raw.get("request_parameters")
        parameters = {}
        if isinstance(raw_parameters, dict):
            tokens = raw_parameters.get("max_tokens")
            if isinstance(tokens, int) and not isinstance(tokens, bool) and 1 <= tokens <= 100000:
                parameters["max_tokens"] = tokens
            for name, upper_bound in (("temperature", 2.0), ("top_p", 1.0)):
                setting = raw_parameters.get(name)
                if (
                    isinstance(setting, (int, float))
                    and not isinstance(setting, bool)
                    and math.isfinite(setting)
                    and 0 <= setting <= upper_bound
                ):
                    parameters[name] = float(setting)
            effort = raw_parameters.get("reasoning_effort")
            if isinstance(effort, str) and effort in {"low", "medium", "high"}:
                parameters["reasoning_effort"] = effort
        roles[role] = {
            "model_id": model_id,
            "request_parameters": parameters,
            "timeout_seconds": float(timeout) if timeout is not None else None,
        }
    return roles or None


def normalize_diagnosis_review(value: object) -> dict[str, str | None]:
    """Keep only explicit human review states and bounded reviewer notes."""
    source = value if isinstance(value, dict) else {}
    status = source.get("status")
    if not isinstance(status, str) or status not in DIAGNOSIS_REVIEW_STATES:
        status = "not_reviewed"
    note = source.get("note")
    note = note.strip()[:1200] if isinstance(note, str) else ""
    reviewer = source.get("reviewer")
    reviewer = reviewer.strip()[:80] if isinstance(reviewer, str) else ""
    if status != "not_reviewed" and not note:
        status = "not_reviewed"
    if status == "not_reviewed":
        return {"status": status, "reviewer": None, "note": ""}
    return {"status": status, "reviewer": reviewer or None, "note": note}


def verification_from_payload(payload: object) -> VerificationReview | None:
    """Restore a bounded, backward-compatible verifier summary from a saved report."""
    if not isinstance(payload, dict):
        return None
    status = payload.get("status")
    if not isinstance(status, str) or status not in {"reviewed", "skipped", "unavailable"}:
        return None
    assessment = payload.get("assessment", "not_run")
    if not isinstance(assessment, str) or assessment not in {
        "supports_candidate", "conflicting_evidence", "insufficient_evidence", "not_run",
    }:
        assessment = "not_run"

    def safe_ids(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item[:40] for item in value[:8] if isinstance(item, str)]

    selected = payload.get("selected_finding_id")
    if not isinstance(selected, str):
        selected = None

    def safe_text(name: str, limit: int) -> str | None:
        value = payload.get(name)
        return value[:limit] if isinstance(value, str) and value else None

    raw_requests = payload.get("model_requests", 0)
    model_requests = raw_requests if isinstance(raw_requests, int) and not isinstance(raw_requests, bool) else 0
    model_requests = min(max(model_requests, 0), 1)
    return VerificationReview(
        status=status,
        assessment=assessment,
        selected_finding_id=selected[:40] if selected else None,
        supporting_evidence_ids=safe_ids(payload.get("supporting_evidence_ids")),
        challenging_evidence_ids=safe_ids(payload.get("challenging_evidence_ids")),
        rationale=safe_text("rationale", 1200) or "",
        test_scenario=safe_text("test_scenario", 500),
        test_assertion=safe_text("test_assertion", 500),
        model_requests=model_requests,
        error=safe_text("error", 300),
    )
