import json
import os
import time
import hashlib
from datetime import datetime, timezone
from contextlib import ExitStack
from pathlib import Path

import streamlit as st
import streamlit_shadcn_ui as ui
from dotenv import load_dotenv
from openai import OpenAI

from citeproof.agent import MODEL_ID
from citeproof.cases import load_curated_cases
from citeproof.blind_review import begin_blind_review, list_reviewable_reports, save_blind_review
from citeproof.comparison import compare_evidence
from citeproof.evaluation import build_run_report, export_run_report, score_investigator_localization
from citeproof.health import check_endpoint
from citeproof.orchestration import investigate_pair
from citeproof.presentation import (
    agent_result_card_status,
    citation_range_details,
    citation_quote_details,
    finding_citation_summary,
    find_saved_report,
    make_run_snapshot,
    normalize_diagnosis_review,
    snapshot_from_saved_report,
)
from citeproof.repo import Repo, RepoError
from citeproof.verifier import build_candidates, verify_findings
from citeproof.trace import normalize_trace_events
from citeproof.ui_components import evidence_panel_html, issue_comment_markdown, sentence_citation_anchors

load_dotenv()
st.set_page_config(page_title="Citeproof · evidence workbench", page_icon="⌕", layout="wide")

PROJECT_DIR = Path(__file__).resolve().parent
THEME_CSS = (PROJECT_DIR / "assets" / "citeproof.css").read_text(encoding="utf-8")
st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)
CURATED_CASES = load_curated_cases(PROJECT_DIR)
PROVIDER = "NVIDIA API Catalog"
SAVED_CLICK_3449_REPORT = PROJECT_DIR / "data" / "benchmarks" / "click-3449-cached-demo-rechecked-v3-human-review-20261101.json"
SAVED_CLICK_3449_VERIFIER_REPORT = PROJECT_DIR / "data" / "benchmarks" / "click-3449-live-verifier-on-cached-pair-20261029.json"
BLIND_ANNOTATIONS_PATH = PROJECT_DIR / "data" / "annotations" / "blind-review.json"


def render_saved_run_button(
    issue_id: str,
    repo_commit: str | None,
    issue_title: str,
    gold_case: dict | None,
    *,
    key: str,
) -> bool:
    if not issue_id or not repo_commit or not gold_case:
        return False
    candidate = find_saved_report(PROJECT_DIR / "data" / "benchmarks", issue_id, repo_commit)
    if candidate is None:
        return False
    report_path, report = candidate
    if not st.button("Open saved run", key=key):
        return True
    try:
        pinned_repo = Repo(repo_path, expected_commit=repo_commit)
        st.session_state["last_run"] = snapshot_from_saved_report(
            report,
            gold_case,
            issue_title,
            pinned_repo,
        )
        st.session_state["last_run"]["saved_report_path"] = report_path.name
        st.rerun()
    except (RepoError, OSError, ValueError) as exc:
        st.error(f"Could not open the saved run for this pinned repository revision: {exc}")
    return True


def render_run(run: dict) -> None:
    results = run["results"]
    gold_case = run["gold_case"]
    if run.get("source") == "saved":
        if run.get("run_source") == "live_verifier_on_cached_agent_pair":
            st.caption(
                f"Cached investigator pair from {run.get('agent_pair_source_timestamp_utc') or 'unknown time'} · "
                f"live verifier from {run.get('verifier_run_timestamp_utc') or 'unknown time'} · "
                f"{run.get('model_id') or MODEL_ID} via {run.get('provider') or PROVIDER} · "
                f"commit `{run['repo_commit']}`"
            )
            st.info("The A/B findings are cached and their citations were rechecked on load. The separate verifier review was live.")
        else:
            st.caption(
                f"Saved demo snapshot · original run {run.get('run_timestamp_utc') or 'timestamp unavailable'} · "
                f"{run.get('model_id') or MODEL_ID} via {run.get('provider') or PROVIDER} · "
                f"commit `{run['repo_commit']}`"
            )
            st.info("This is a cached model run. Citations were rechecked against the pinned repository when loaded.")
    else:
        st.caption(f"Last live run · {run['issue_title']} · commit `{run['repo_commit'] or 'un-pinned manual repository'}`")
    if any(result.error for result in results):
        issue_id = run.get("issue_id") or (gold_case or {}).get("issue_id", "")
        render_saved_run_button(
            issue_id,
            run.get("repo_commit"),
            run.get("issue_title", "Saved run"),
            gold_case,
            key="open-saved-run-incomplete-" + hashlib.sha256(
                f"{issue_id}|{run.get('repo_commit')}|{run.get('run_timestamp_utc')}".encode("utf-8")
            ).hexdigest()[:12],
        )
    timings = run.get("timings") or {}
    endpoint_health = run.get("endpoint_health")
    if endpoint_health:
        st.caption(
            f"Endpoint readiness · {endpoint_health['status'].title()} · "
            f"{endpoint_health['elapsed_seconds']:.1f}s · "
            f"{endpoint_health['request_count']} readiness request(s)"
        )
    if timings.get("total_seconds") is not None:
        stage_parts = [f"Total {timings['total_seconds']:.1f}s"]
        if timings.get("investigators_seconds") is not None:
            stage_parts.append(f"investigators {timings['investigators_seconds']:.1f}s")
        if timings.get("verification_seconds") is not None:
            stage_parts.append(f"verifier {timings['verification_seconds']:.1f}s")
        if timings.get("baseline_seconds") is not None:
            stage_parts.append(f"baseline {timings['baseline_seconds']:.1f}s")
        st.caption("Measured elapsed time · " + " · ".join(stage_parts))
    attempt_parts = []
    for result in results:
        name = result.agent_name.split("·", 1)[0].strip()
        attempts = str(result.model_requests) if result.model_requests_known else "unknown"
        retry_summary = (
            f"{result.model_retries} retries"
            if result.model_retries_known
            else "retry count not stored"
        )
        attempt_parts.append(f"{name} {attempts} ({retry_summary})")
    if attempt_parts:
        st.caption("Model attempts · " + " · ".join(attempt_parts))
    errors = sum(bool(result.error) for result in results)
    finding_count = sum(len(result.findings) for result in results)
    verified = sum(c.valid for r in results for f in r.findings for c in f.citations)
    state = "Incomplete" if errors else "Complete"
    st.markdown(f"**Status · {state}** — {finding_count} finding(s) · {verified} verified citation(s)")
    with st.popover("How to read this"):
        st.write("A verified citation proves the quote exists, not that the diagnosis is right.")
    findings_tab, compare_tab, trace_tab, report_tab = st.tabs(["Findings", "Compare", "Trace", "Report"])
    with findings_tab:
        st.header("02  /  Findings")
        st.caption("A direct citation anchor is literal text overlap for navigation only; it is not an entailment check.")
        evidence_repo = None
        if run.get("repo_commit"):
            try:
                evidence_repo = Repo(st.session_state.get("repo_path", ""), expected_commit=run["repo_commit"])
            except (RepoError, OSError):
                evidence_repo = None
        agent_columns = st.columns(2)
        for agent_index, (column, result) in enumerate(zip(agent_columns, results)):
            with column:
                card_content, card_description = agent_result_card_status(result)
                ui.card(
                    title=result.agent_name,
                    content=card_content,
                    description=card_description,
                    key=f"result-card-{result.agent_name.split('·')[0].strip().lower().replace(' ', '-')}",
                )
                if result.error:
                    st.error(result.error)
                elif not result.findings:
                    st.info("No supported finding returned.")
                for finding_index, finding in enumerate(result.findings):
                    with st.expander(finding.claim or "Unspecified claim", expanded=True):
                        for sentence in sentence_citation_anchors(finding):
                            st.write(sentence["sentence"])
                            anchor_status = sentence["status"]
                            if sentence["citation_indices"]:
                                anchor_status += " · source overlap only"
                            st.caption(anchor_status)
                        summary = finding_citation_summary(finding)
                        st.caption(f"Citation support state: `{summary}`")
                        if not finding.citations:
                            st.caption("No checked source support was supplied; this is not a verdict that the diagnosis is false.")
                        for citation_index, citation in enumerate(finding.citations):
                            citation_label = "Verified" if citation.valid else "Rejected"
                            if citation.valid and citation.outcome == "corrected_unique_exact_quote":
                                citation_label = "Corrected"
                            ui.badge(
                                citation_label,
                                variant=("default" if citation.valid else "destructive"),
                                key=f"citation-{agent_index}-{finding_index}-{citation_index}",
                            )
                            first_line, last_line = citation.effective_range
                            st.write(f"{citation.path}:{first_line}-{last_line} · {citation.symbol or 'no symbol'}")
                            st.caption(f"Outcome: `{citation.outcome or 'not_checked'}` · {citation.reason}")
                            st.caption(citation_range_details(citation))
                            if summary == "none_verified":
                                st.caption("No checked citation supports this finding; that does not show the diagnosis is false.")
                            label, quote = citation_quote_details(citation)
                            ui.badge(label, variant=("default" if citation.valid else "destructive"), key=f"quote-{agent_index}-{finding_index}-{citation_index}")
                            st.code(quote, language="python")
                            source_lines = None
                            window_start = max(1, first_line - 2)
                            if evidence_repo is not None:
                                window_end = min(max(last_line + 2, window_start), window_start + 39)
                                try:
                                    numbered_source = evidence_repo.read_file(
                                        citation.path,
                                        window_start,
                                        window_end,
                                    )
                                    source_lines = [line.partition(": ")[2] for line in numbered_source.splitlines()]
                                except (RepoError, OSError, ValueError):
                                    source_lines = None
                            st.markdown(
                                evidence_panel_html(
                                    citation,
                                    source_lines,
                                    window_start=window_start,
                                    total_lines=None,
                                ),
                                unsafe_allow_html=True,
                            )

    with compare_tab:
        comparison = compare_evidence(results)
        st.header("03  /  Cross-Check")
        ui.card(
            title=f"Evidence comparison · {comparison.status.replace('_', ' ')}",
            content=comparison.summary,
            description="Overlapping verified evidence is corroboration of source location only; it does not establish a correct diagnosis.",
            key="comparison-card",
        )
        if comparison.shared_files:
            st.write("Shared files: " + ", ".join(f"`{path}`" for path in comparison.shared_files))
        if comparison.overlapping_ranges:
            ranges = ", ".join(f"`{path}:{start}-{end}`" for path, start, end in comparison.overlapping_ranges)
            st.write("Overlapping verified ranges: " + ranges)
        if gold_case:
            st.subheader("Independent file rankings")
            for result in results:
                metrics = score_investigator_localization(result, gold_case)
                ranked = ", ".join(metrics.ranked_files[:5]) or "No verified files ranked"
                st.caption(f"{metrics.agent_name} · {ranked}")
                st.caption(
                    "Primary hit@1: "
                    + ("not scored" if metrics.primary_hit_at_1 is None else "HIT" if metrics.primary_hit_at_1 else "MISS")
                    + " · reciprocal rank: "
                    + ("not scored" if metrics.primary_file_reciprocal_rank is None else f"{metrics.primary_file_reciprocal_rank:.2f}")
                    + " · recall@3: "
                    + ("not scored" if metrics.gold_file_recall_at_3 is None else f"{metrics.gold_file_recall_at_3:.0%}")
                )

        verification = run.get("verification")
        st.header("04  /  Skeptical Review")
        if verification is None:
            st.caption("No verifier review was saved with this run.")
        elif verification.status == "skipped":
            st.caption(verification.error or "The verifier was skipped because its evidence prerequisites were not met.")
        elif verification.status == "unavailable":
            st.warning(
                "The verifier was unavailable. "
                + (verification.error or "The two investigation results are retained.")
            )
            st.caption(f"Verifier requests used: {verification.model_requests}/1")
        else:
            candidates, evidence = build_candidates(results)
            evidence_by_id = {item["evidence_id"]: item for item in evidence}
            candidate_by_id = {item["finding_id"]: item for item in candidates}
            selected_id = verification.selected_finding_id
            assessment_label = verification.assessment.replace("_", " ")
            selected_claim = candidate_by_id.get(selected_id, {}).get("claim", "No candidate selected")
            ui.card(
                title="Muse evidence review",
                content=f"Assessment: {assessment_label}",
                description="This is a bounded Muse review of checked evidence, not proof of the root cause.",
                key="verifier-review-card",
            )
            if selected_id:
                st.write(f"Selected candidate {selected_id}:", selected_claim)
            else:
                st.caption("No single finding was selected.")
            st.write(verification.rationale)

            def show_review_evidence(label: str, evidence_ids: list[str]) -> None:
                if not evidence_ids:
                    return
                st.caption(label)
                for evidence_id in evidence_ids:
                    item = evidence_by_id.get(evidence_id)
                    if not item:
                        continue
                    st.markdown(
                        f"**{evidence_id}** · `{item['path']}:{item['start_line']}-{item['end_line']}`"
                    )
                    st.code(item["quote"], language="python")

            show_review_evidence("Supporting checked evidence", verification.supporting_evidence_ids)
            show_review_evidence("Challenging checked evidence", verification.challenging_evidence_ids)
            if verification.test_scenario and verification.test_assertion:
                st.info("Suggested regression test · not run")
                st.write("Scenario:", verification.test_scenario)
                st.write("Expected assertion:", verification.test_assertion)
            st.caption(f"Verifier requests used: {verification.model_requests}/1")

    with trace_tab:
        st.header("Trace · read-only model tool activity")
        st.caption("Replaying a stored summary makes no model call.")
        rows = []
        unknown = []
        for result in results:
            events, known = normalize_trace_events(result.trace_events) if result.trace_events_known else ([], False)
            if known:
                rows.extend((result.agent_name, event) for event in events)
            else:
                unknown.append(result.agent_name)
        if rows:
            if len(rows) == 1:
                index = 0
                st.caption("Single recorded step")
            else:
                index = st.slider("Trace step", min_value=1, max_value=len(rows), value=1, key="trace-step") - 1
            agent_name, event = rows[index]
            st.subheader(f"{agent_name} · step {index + 1} of {len(rows)}")
            st.write("Tool:", event["tool"])
            st.write("Request summary:", event["request_summary"])
            st.write("Result summary:", event["result_summary"])
        elif not unknown:
            st.info("No repository tool calls were recorded for this run.")
        if unknown:
            st.caption("Trace results not stored for: " + ", ".join(unknown))
    with report_tab:
        if gold_case:
            review = run.get("diagnosis_review") or {
                "status": "not_reviewed",
                "reviewer": None,
                "note": "",
            }
            review_identity = "|".join((
                str(gold_case.get("issue_id", "unknown")),
                str(run.get("repo_commit") or "unknown"),
                str(run.get("run_timestamp_utc") or "untimed"),
            ))
            review_key = "diagnosis-review-" + hashlib.sha256(review_identity.encode("utf-8")).hexdigest()[:12]
            st.header("05  /  Human Diagnosis Review")
            st.caption(
                "Judge the proposed cause against the issue and maintainer-confirmed fix. "
                "A matching quote or file location does not establish a correct diagnosis."
            )
            with st.expander("Record a Human Review", expanded=review.get("status") != "not_reviewed"):
                review_status = st.selectbox(
                    "Diagnosis Assessment",
                    options=["not_reviewed", "supported", "partly_supported", "unsupported", "incorrect"],
                    index=["not_reviewed", "supported", "partly_supported", "unsupported", "incorrect"].index(review["status"]),
                    key=f"{review_key}-status",
                    format_func=lambda value: value.replace("_", " ").title(),
                )
                review_reviewer = st.text_input(
                    "Reviewer Initials or Role · Optional",
                    value=review.get("reviewer") or "",
                    key=f"{review_key}-reviewer",
                    max_chars=80,
                    autocomplete="off",
                )
                review_note = st.text_area(
                    "Evidence-Based Reason",
                    value=review.get("note") or "",
                    key=f"{review_key}-note",
                    max_chars=1200,
                    help="Required to save a supported, partly supported, unsupported, or incorrect judgment.",
                )
                normalized_review = normalize_diagnosis_review({
                    "status": review_status,
                    "reviewer": review_reviewer,
                    "note": review_note,
                })
                if review_status != "not_reviewed" and normalized_review["status"] == "not_reviewed":
                    st.info("Add a brief evidence-based reason to record this as a human review.")
            run["diagnosis_review"] = normalized_review
            st.session_state["last_run"] = run

            report = build_run_report(
                gold_case,
                run["repo_commit"] or "unknown",
                run.get("model_id") or MODEL_ID,
                run.get("provider") or PROVIDER,
                results,
                verification=run.get("verification"),
                workflow_kind=run.get("workflow_kind") or ("cached_demo" if run.get("source") == "saved" else "live_pair"),
                run_timestamp_utc=run.get("run_timestamp_utc"),
                timings=run.get("timings"),
                model_settings=run.get("model_settings"),
                model_request_counts=run.get("model_request_counts"),
                diagnosis_review_status=normalized_review["status"],
                diagnosis_review_reviewer=normalized_review["reviewer"],
                diagnosis_review_note=normalized_review["note"],
                report_schema=run.get("report_schema", "citeproof-evaluation/v4"),
                ranking_method=run.get("ranking_method") or "finding_order_descending_plausibility",
                preserved_investigator_localization=run.get("saved_investigator_localization"),
                endpoint_health=run.get("endpoint_health"),
            )
            metrics = report["metrics"]
            run_states = report["states"]
            st.header("06  /  Smoke Evaluation")
            verified_agent_count = report["evidence"]["agents_with_verified_citations"]
            required_agent_count = 1 if run_states["workflow_kind"] == "single_agent_baseline" else 2
            finding_summary = report["finding_summary"]
            if finding_summary["status"] == "no_findings":
                empty_message = (
                    "Investigation completed with no findings: "
                    f"0/{finding_summary['required_agents']} required investigator(s) returned a finding."
                )
                recall = metrics["gold_file_recall_at_3"]
                if report["status"] == "complete" and recall is not None:
                    empty_message += f" Localization scored {recall:.0%} gold-file recall for this case."
                st.warning(empty_message)
            elif finding_summary["status"] == "no_verified_citations":
                st.warning(
                    f"Investigation returned {finding_summary['finding_count']} finding(s), but none of their citations "
                    "passed source verification; localization only counts verified citations."
                )
            if verified_agent_count < required_agent_count:
                st.warning(
                    f"Verified citations were returned by {verified_agent_count} of {required_agent_count} required investigator(s); "
                    "this does not show full-run corroboration."
                )
            if report["status"] == "complete":
                score_columns = st.columns(2)
                with score_columns[0]:
                    ui.metric_card(
                        "Primary file hit @1",
                        "HIT" if metrics["primary_hit_at_1"] else "MISS",
                        description="Proxy location label from the maintainer's fix.",
                    )
                with score_columns[1]:
                    ui.metric_card(
                        "Gold-file recall @3",
                        f"{metrics['gold_file_recall_at_3']:.0%}",
                        description="Changed-file labels are location proxies, not diagnosis scores.",
                    )
                if gold_case.get("evaluation_note"):
                    st.caption(gold_case["evaluation_note"])
            else:
                st.warning("This run is incomplete, so no localization score is reported.")
            st.subheader("Per-investigator file-localization proxies")
            investigator_rows = report.get("investigator_localization")
            if investigator_rows is None:
                st.caption("Per-investigator rankings were not recorded in this legacy report.")
            for investigator_metrics in investigator_rows or []:
                ranked = ", ".join(investigator_metrics["ranked_files"]) or "No verified files ranked"
                st.caption(f"{investigator_metrics['name']} · ranked unique checked files: {ranked}")

                def score_label(value: object, *, percent: bool = False, reciprocal: bool = False) -> str:
                    if value is None:
                        return "Not scored"
                    if isinstance(value, bool):
                        return "HIT" if value else "MISS"
                    if reciprocal:
                        return f"{value:.2f}"
                    if percent:
                        return f"{value:.0%}"
                    return str(value)

                st.caption(
                    f"{investigator_metrics['name']} · Primary-file hit@1: "
                    f"{score_label(investigator_metrics['primary_hit_at_1'])} · "
                    f"Primary-file reciprocal rank: "
                    f"{score_label(investigator_metrics['primary_file_reciprocal_rank'], reciprocal=True)} · "
                    f"Gold-file recall@3: {score_label(investigator_metrics['gold_file_recall_at_3'], percent=True)}"
                )
            st.caption("Finding order defines each investigator's file rank. These are file-localization proxies, not diagnosis scores.")
            repo_slug = (gold_case.get("issue_id") or "").split("#", 1)[0] or None
            comment_parts = [
                issue_comment_markdown(finding, repo_slug, run.get("repo_commit"))
                for result in results
                for finding in result.findings
            ]
            if comment_parts:
                st.subheader("Issue-comment draft")
                st.caption("Pinned GitHub links are included only for citations that passed source verification.")
                st.code("\n\n---\n\n".join(comment_parts), language="markdown")
            if run.get("source") == "saved":
                report["run_source"] = (
                    "cached_agent_pair_live_review_rechecked"
                    if run_states["workflow_kind"] == "cached_pair_live_review"
                    else "cached_demo_snapshot_rechecked"
                )
                report["original_run_timestamp_utc"] = run.get("run_timestamp_utc")
            report_filename, report_content = export_run_report(report)
            download_label = (
                "Download evaluation run as JSON"
                if report["status"] == "complete"
                else "Download incomplete run · partial evidence only"
            )
            st.download_button(download_label, data=report_content, file_name=report_filename, mime="application/json")
        else:
            st.header("Run report")
            st.info(
                "No curated gold labels are attached to this manual issue, so localization and diagnosis correctness "
                "are not scored. The report still includes the investigation, checked citations, and workflow provenance."
            )
            report = build_run_report(
                {"issue_id": run.get("issue_id") or "manual/unknown"},
                run["repo_commit"] or "unknown",
                run.get("model_id") or MODEL_ID,
                run.get("provider") or PROVIDER,
                results,
                verification=run.get("verification"),
                workflow_kind=run.get("workflow_kind") or ("cached_demo" if run.get("source") == "saved" else "live_pair"),
                run_timestamp_utc=run.get("run_timestamp_utc"),
                timings=run.get("timings"),
                model_settings=run.get("model_settings"),
                model_request_counts=run.get("model_request_counts"),
                report_schema=run.get("report_schema", "citeproof-evaluation/v4"),
                ranking_method=run.get("ranking_method") or "finding_order_descending_plausibility",
                preserved_investigator_localization=run.get("saved_investigator_localization"),
                endpoint_health=run.get("endpoint_health"),
            )
            report["evaluation_note"] = "No curated gold labels are attached; localization and diagnosis correctness are not scored."
            report_filename, report_content = export_run_report(report)
            st.download_button(
                "Download unscored run as JSON",
                data=report_content,
                file_name=report_filename,
                mime="application/json",
            )


st.session_state.setdefault("last_run", None)
case_options = list(CURATED_CASES) + ["Enter another issue manually"]
with st.sidebar:
    st.markdown("### Citeproof")
    st.caption("Evidence-first Python issue investigation")
    st.divider()
    sample_choice = st.selectbox("Issue case", case_options, key="selected_case")
    selected_case = CURATED_CASES.get(sample_choice)
    use_sample = selected_case is not None
    sample_issue = selected_case["issue"] if selected_case else None
    gold_case = selected_case["gold"] if selected_case else None
    if selected_case:
        default_repo = str(PROJECT_DIR / "demo_repos" / selected_case["repo_dir"])
        st.caption(selected_case["gold"].get("evaluation_note", ""))
    else:
        default_repo = os.getenv("CITEPROOF_REPO", str(PROJECT_DIR / "demo_repos" / "click"))

    if st.session_state.get("case_defaults") != sample_choice:
        st.session_state["repo_path"] = default_repo
        st.session_state["issue_title"] = sample_issue["title"] if sample_issue else ""
        st.session_state["issue_body"] = sample_issue["body"] if sample_issue else ""
        st.session_state["last_run"] = None
        st.session_state["case_defaults"] = sample_choice

    st.subheader("Repository")
    repo_path = st.text_input("Local repository folder", key="repo_path", placeholder=r"D:\path\to\repo")
    st.caption("Repository tools are read-only and confined to this folder.")
    if sample_issue and sample_issue["issue_id"] == "pallets/click#3449" and SAVED_CLICK_3449_REPORT.is_file():
        if st.button("Load Cached Click #3449 Demo · No Model Call", use_container_width=True):
            try:
                pinned_repo = Repo(repo_path, expected_commit=sample_issue["commit"])
                saved_report = json.loads(SAVED_CLICK_3449_REPORT.read_text(encoding="utf-8"))
                st.session_state["last_run"] = snapshot_from_saved_report(
                    saved_report,
                    gold_case,
                    sample_issue["title"],
                    pinned_repo,
                )
            except (RepoError, OSError, json.JSONDecodeError, ValueError) as exc:
                st.error(f"Could not load the saved demo: {exc}")
    if (
        sample_issue
        and sample_issue["issue_id"] == "pallets/click#3449"
        and SAVED_CLICK_3449_VERIFIER_REPORT.is_file()
    ):
        if st.button("Load Cached A/B + Live Verifier Demo · No Model Call", use_container_width=True):
            try:
                pinned_repo = Repo(repo_path, expected_commit=sample_issue["commit"])
                verifier_report = json.loads(SAVED_CLICK_3449_VERIFIER_REPORT.read_text(encoding="utf-8"))
                st.session_state["last_run"] = snapshot_from_saved_report(
                    verifier_report,
                    gold_case,
                    sample_issue["title"],
                    pinned_repo,
                )
            except (RepoError, OSError, json.JSONDecodeError, ValueError) as exc:
                st.error(f"Could not load the saved review demo: {exc}")
    st.divider()
    ui.badge("Muse Glimmer 30B", variant="outline", key="sidebar-model")
    st.caption(f"`{MODEL_ID}` · {PROVIDER}")
    st.caption(
        "Two independent investigators run in parallel (up to 4 minutes each), followed by at most one "
        "2-minute verifier request when both have checked citations. Each request is capped at 2 minutes. "
        "Investigators allow up to 3 tool rounds plus one bounded correction."
    )

st.markdown(
    """
    <header class="cp-masthead" aria-label="Citeproof issue research">
      <span class="cp-mark" aria-hidden="true">C</span>
      <div class="cp-brand-copy">
        <p class="cp-eyebrow">Issue research · for open-source maintainers</p>
        <h1 class="cp-brand-name">Citeproof</h1>
        <p class="cp-brand-subtitle">Trace a Python issue to source evidence you can verify.</p>
      </div>
      <div class="cp-masthead-meta">
        <span class="cp-meta-primary">2 independent investigations</span>
        <span class="cp-meta-secondary">Read-only tools · pinned source</span>
      </div>
    </header>
    <div class="cp-method-strip" role="group" aria-label="How Citeproof works">
      <div class="cp-method-item"><strong>Independent paths</strong>Two distinct searches start from the same issue.</div>
      <div class="cp-method-item"><strong>Read-only access</strong>Agents inspect source without editing or running code.</div>
      <div class="cp-method-item"><strong>Quotes checked</strong>Each citation is checked against the selected source.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Provider, privacy, and cost notes"):
    st.write(
        "This prototype calls Muse Glimmer through NVIDIA's free API Catalog endpoint. "
        "It does not call Meta Model API or configure a paid fallback. Availability and rate limits can vary, and failures stop the run."
    )
    st.write(
        "NVIDIA says trial prompts and outputs may be recorded to improve its products. "
        "Use only public issue text and source code; do not send private code, secrets, or personal data."
    )
    st.write("The $150 Meta API credits are not used by this route. Citation checks establish source integrity, not diagnosis correctness.")

st.header("01  /  Investigation Brief")
if use_sample:
    issue_number = sample_issue["issue_id"].rsplit("#", 1)[-1]
    st.caption(f"{sample_issue['repo']} · pinned pre-fix commit `{sample_issue['commit'][:12]}` · [issue #{issue_number}]({sample_issue['issue_url']})")
issue_title = st.text_input("Issue title", key="issue_title", placeholder="e.g. Request encoding fails for ...")
issue_body = st.text_area(
    "Issue description",
    key="issue_body",
    height=190,
    placeholder="Paste a public bug report. Issue text is treated as untrusted input.",
)

health_column, run_column, scope_column = st.columns([0.2, 0.34, 0.46], vertical_alignment="center")
endpoint_health = st.session_state.get("endpoint_health")
endpoint_status = endpoint_health.get("status", "not_checked") if endpoint_health else "not_checked"
endpoint_label = {
    "ready": "Ready",
    "slow": "Slow",
    "unavailable": "Unavailable",
    "not_checked": "Not checked",
}.get(endpoint_status, "Unavailable")
with health_column:
    endpoint_pill = st.empty()
    endpoint_pill.markdown(
        f'<div class="cp-status-pill cp-status-{endpoint_status}" role="status">Endpoint: {endpoint_label}</div>',
        unsafe_allow_html=True,
    )
    check_endpoint_clicked = st.button("Check endpoint", use_container_width=True)
with run_column:
    investigate_clicked = st.button("Investigate With Both Agents", type="primary", use_container_width=True)
with scope_column:
    ui.badge("Muse Glimmer 30B", variant="outline", key="run-model")
    st.caption("NVIDIA API Catalog · two independent searches in parallel, then one bounded evidence review if eligible.")

token = os.getenv("NVIDIA_API_KEY", "").strip()
should_check_endpoint = check_endpoint_clicked or (
    investigate_clicked
    and token
    and repo_path.strip()
    and issue_title.strip()
    and issue_body.strip()
)
if should_check_endpoint:
    endpoint_client = (
        OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=token,
            timeout=15,
            max_retries=0,
        )
        if token
        else None
    )
    st.session_state["endpoint_health"] = check_endpoint(endpoint_client)
    health = st.session_state["endpoint_health"]
    label = {"ready": "Ready", "slow": "Slow", "unavailable": "Unavailable"}[health["status"]]
    endpoint_status = health["status"]
    endpoint_pill.markdown(
        f'<div class="cp-status-pill cp-status-{health["status"]}" role="status">Endpoint: {label}</div>',
        unsafe_allow_html=True,
    )
    if health["status"] == "unavailable" and not investigate_clicked:
        st.warning("The model endpoint did not answer the 15-second readiness check. Retry the check before starting a run.")
    else:
        if health["status"] != "unavailable":
            st.caption(f"Readiness request completed in {health['elapsed_seconds']:.1f}s.")
    if health["status"] == "unavailable" and sample_issue:
        render_saved_run_button(
            sample_issue["issue_id"],
            sample_issue["commit"],
            sample_issue["title"],
            gold_case,
            key="open-saved-run-endpoint-failure",
        )

if investigate_clicked:
    if not repo_path.strip():
        st.error("Choose a local Python repository folder first.")
    elif not issue_title.strip() or not issue_body.strip():
        st.error("Enter an issue title and description.")
    elif not token:
        st.error("No NVIDIA_API_KEY found. Put a free API Catalog key in a local .env file. Do not enable paid services if you need to avoid charges.")
    elif endpoint_status not in {"ready", "slow"}:
        st.warning("Check the endpoint before starting a live run. The readiness check uses a five-token request with a 15-second timeout.")
    else:
        try:
            repo = Repo(repo_path, expected_commit=sample_issue["commit"] if use_sample else None)
        except (RepoError, OSError) as exc:
            st.error(f"Could not open repository: {exc}")
        else:
            issue = f"Title: {issue_title.strip()}\n\n{issue_body.strip()}"
            run_timestamp_utc = datetime.now(timezone.utc).isoformat()
            total_started = time.monotonic()
            labels = ["Investigator A · symptom-first", "Investigator B · structure-first"]
            statuses = {}
            progress_slots = {}
            trace_slots = {}
            traces = {label: [] for label in labels}
            with ExitStack() as stack:
                for label in labels:
                    statuses[label] = stack.enter_context(st.status(f"Starting {label}…", expanded=True))
                    progress_slots[label] = st.empty()
                    trace_slots[label] = st.empty()

                def show_pair_progress(label: str, message: str) -> None:
                    progress_slots[label].caption(message)
                    if message.startswith(("Tool call:", "Tool rejected:")):
                        traces[label].append(message.removeprefix("Tool call: ").removeprefix("Tool rejected: ").strip())
                        trace_slots[label].code("\n".join(traces[label]), language="text")

                investigators_started = time.monotonic()
                results = list(investigate_pair(repo, issue, on_progress=show_pair_progress))
                investigators_seconds = max(0.0, time.monotonic() - investigators_started)
                for label, result in zip(labels, results):
                    statuses[label].update(
                        label=f"{label}: {'incomplete' if result.error else 'finished'}",
                        state="error" if result.error else "complete",
                    )

            with st.status("Running bounded evidence review…", expanded=True) as verifier_status:
                verifier_progress = st.empty()
                verification_started = time.monotonic()
                verification = verify_findings(issue, results, on_progress=verifier_progress.caption)
                verification_seconds = max(0.0, time.monotonic() - verification_started)
                if verification.status == "reviewed":
                    verifier_status.update(label="Evidence review finished", state="complete")
                elif verification.status == "skipped":
                    verifier_status.update(label="Evidence review skipped", state="complete")
                else:
                    verifier_status.update(label="Evidence review unavailable", state="error")

            last_run = make_run_snapshot(
                results,
                repo.commit,
                issue_title.strip(),
                gold_case,
                verification=verification,
                run_timestamp_utc=run_timestamp_utc,
                model_id=MODEL_ID,
                provider=PROVIDER,
                workflow_kind="live_pair",
                timings={
                    "investigators_seconds": investigators_seconds,
                    "verification_seconds": verification_seconds,
                    "baseline_seconds": None,
                    "total_seconds": max(0.0, time.monotonic() - total_started),
                },
                endpoint_health=st.session_state.get("endpoint_health"),
            )
            st.session_state["last_run"] = last_run
            render_run(last_run)

if st.session_state.get("last_run") and not investigate_clicked:
    render_run(st.session_state["last_run"])


def render_blind_option(option: dict, label: str) -> None:
    st.subheader(label)
    hit = option.get("primary_hit_at_1")
    hit_text = "not scored" if hit is None else "HIT" if hit else "MISS"
    recall = option.get("gold_file_recall_at_3")
    recall_text = "not scored" if recall is None else f"{recall:.0%}"
    requests = option.get("model_requests")
    request_text = "unknown" if requests is None else str(requests)
    st.caption(
        f"{request_text} model requests · localization {option.get('localization_status', 'unknown')} · "
        f"primary hit@1 {hit_text} · recall@3 {recall_text}"
    )
    ranked_files = option.get("ranked_files") or []
    st.write("Ranked files: " + (", ".join(str(path) for path in ranked_files) or "none returned"))
    for finding_index, finding in enumerate(option.get("findings") or [], start=1):
        st.markdown(f"Finding {finding_index}")
        st.write(finding.get("claim") or "No claim returned")
        if finding.get("explanation"):
            st.write(finding["explanation"])
        citations = finding.get("citations") or []
        for citation in citations:
            validity = "Verified quote" if citation.get("valid") is True else "Rejected or unchecked quote"
            start_line = citation.get("start_line") or "?"
            end_line = citation.get("end_line") or start_line
            st.caption(
                f"{validity} · {citation.get('path') or 'unknown path'}:{start_line}-{end_line} · "
                f"{citation.get('symbol') or 'no symbol'}"
            )
            if citation.get("quote"):
                st.code(citation["quote"], language="python")


def render_blind_review_panel() -> None:
    with st.expander("Blind pair-versus-baseline review", expanded=False):
        try:
            reviewable = list_reviewable_reports(PROJECT_DIR / "data" / "benchmarks")
        except ValueError as exc:
            st.error(str(exc))
            return
        if not reviewable:
            st.info("No saved pair-versus-baseline comparison is available to review yet.")
            return

        report_paths = [path.name for path, _ in reviewable]
        selected_name = st.selectbox(
            "Saved comparison",
            options=report_paths,
            key="blind-review-report-selection",
        )
        selected_path, report = next(item for item in reviewable if item[0].name == selected_name)
        current_name = st.session_state.get("blind-review-active-report")
        if current_name != selected_name:
            if st.button("Start blinded review", key="blind-review-start"):
                try:
                    begin_blind_review(report, BLIND_ANNOTATIONS_PATH)
                    st.session_state["blind-review-active-report"] = selected_name
                    st.rerun()
                except (OSError, ValueError) as exc:
                    st.error(f"Could not start the blinded review: {exc}")
            st.caption(
                f"{report.get('issue_id', 'Unknown issue')} · {report.get('model_id', 'unknown model')} · "
                f"{report.get('run_timestamp_utc', 'timestamp unavailable')}"
            )
            return

        issue_id = report.get("issue_id")
        issue_context = next(
            (item["issue"] for item in CURATED_CASES.values() if item["issue"].get("issue_id") == issue_id),
            None,
        )
        if issue_context:
            st.write(issue_context.get("title", "Saved issue"))
            st.write(issue_context.get("body", ""))
        try:
            session = begin_blind_review(report, BLIND_ANNOTATIONS_PATH)
        except (OSError, ValueError) as exc:
            st.error(f"Could not open the blinded review: {exc}")
            return

        options = st.columns(2)
        with options[0]:
            render_blind_option(session.option_a, "Option A")
        with options[1]:
            render_blind_option(session.option_b, "Option B")

        if session.mapping_revealed:
            st.success("Your blinded assessment is saved. The source mapping is now revealed.")
            st.write(f"Option A was the {session.mapping_revealed['A']}; Option B was the {session.mapping_revealed['B']}.")
            st.caption(f"Saved assessment: {session.saved_label}")
            st.write(session.note)
            return

        st.caption("Choose the stronger output from the issue evidence. Add a note before Citeproof reveals which workflow is which.")
        rating = st.selectbox(
            "Blind assessment",
            options=["A stronger", "B stronger", "Tie", "Neither useful", "Unable to judge"],
            key="blind-review-label-" + session.identity[:12],
        )
        note = st.text_area(
            "Evidence note",
            max_chars=1200,
            key="blind-review-note-" + session.identity[:12],
        )
        if st.button("Save assessment and reveal mapping", key="blind-review-save-" + session.identity[:12]):
            try:
                save_blind_review(report, BLIND_ANNOTATIONS_PATH, rating, note)
                st.rerun()
            except (OSError, ValueError) as exc:
                st.error(f"Could not save the blinded assessment: {exc}")


render_blind_review_panel()

st.divider()
st.caption("Citeproof · local-first prototype · no generated shell commands or tests are executed.")
