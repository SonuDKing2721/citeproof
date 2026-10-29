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

from citeproof.agent import MODEL_ID
from citeproof.cases import load_curated_cases
from citeproof.comparison import compare_evidence
from citeproof.evaluation import build_run_report, export_run_report
from citeproof.orchestration import investigate_pair
from citeproof.presentation import (
    agent_result_card_status,
    citation_quote_details,
    make_run_snapshot,
    normalize_diagnosis_review,
    snapshot_from_saved_report,
)
from citeproof.repo import Repo, RepoError
from citeproof.verifier import build_candidates, verify_findings

load_dotenv()
st.set_page_config(page_title="Citeproof · evidence workbench", page_icon="⌕", layout="wide")

PROJECT_DIR = Path(__file__).resolve().parent
THEME_CSS = (PROJECT_DIR / "assets" / "citeproof.css").read_text(encoding="utf-8")
st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)
CURATED_CASES = load_curated_cases(PROJECT_DIR)
PROVIDER = "NVIDIA API Catalog"
SAVED_CLICK_3449_REPORT = PROJECT_DIR / "data" / "demo_runs" / "citeproof-pallets-click-3449-complete.json"
SAVED_CLICK_3449_VERIFIER_REPORT = PROJECT_DIR / "data" / "benchmarks" / "click-3449-live-verifier-on-cached-pair-20261029.json"


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
    timings = run.get("timings") or {}
    if timings.get("total_seconds") is not None:
        stage_parts = [f"Total {timings['total_seconds']:.1f}s"]
        if timings.get("investigators_seconds") is not None:
            stage_parts.append(f"investigators {timings['investigators_seconds']:.1f}s")
        if timings.get("verification_seconds") is not None:
            stage_parts.append(f"verifier {timings['verification_seconds']:.1f}s")
        if timings.get("baseline_seconds") is not None:
            stage_parts.append(f"baseline {timings['baseline_seconds']:.1f}s")
        st.caption("Measured elapsed time · " + " · ".join(stage_parts))
    st.header("02  /  Evidence Review")
    st.caption("Verified means the file, symbol, line range, and quote match the selected checkout. Diagnosis correctness needs human review.")
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
                    st.write(finding.explanation)
                    if not finding.citations:
                        st.caption("No citations were supplied.")
                    for citation_index, citation in enumerate(finding.citations):
                        icon = "✅" if citation.valid else "❌"
                        st.markdown(f"{icon} `{citation.path}:{citation.start_line}-{citation.end_line}` · `{citation.symbol or 'no symbol'}`")
                        st.caption(citation.reason)
                        label, quote = citation_quote_details(citation)
                        ui.badge(label, variant=("default" if citation.valid else "destructive"), key=f"quote-{agent_index}-{finding_index}-{citation_index}")
                        st.code(quote, language="python")

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
        )
        metrics = report["metrics"]
        run_states = report["states"]
        st.header("06  /  Smoke Evaluation")
        verified_agent_count = report["evidence"]["agents_with_verified_citations"]
        required_agent_count = 1 if run_states["workflow_kind"] == "single_agent_baseline" else 2
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

run_column, scope_column = st.columns([0.52, 0.48], vertical_alignment="center")
with run_column:
    investigate_clicked = st.button("Investigate With Both Agents", type="primary", use_container_width=True)
with scope_column:
    ui.badge("Muse Glimmer 30B", variant="outline", key="run-model")
    st.caption("NVIDIA API Catalog · two independent searches in parallel, then one bounded evidence review if eligible.")

if investigate_clicked:
    if not repo_path.strip():
        st.error("Choose a local Python repository folder first.")
    elif not issue_title.strip() or not issue_body.strip():
        st.error("Enter an issue title and description.")
    elif not os.getenv("NVIDIA_API_KEY", "").strip():
        st.error("No NVIDIA_API_KEY found. Put a free API Catalog key in a local .env file. Do not enable paid services if you need to avoid charges.")
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
            )
            st.session_state["last_run"] = last_run
            render_run(last_run)

if st.session_state.get("last_run") and not investigate_clicked:
    render_run(st.session_state["last_run"])

st.divider()
st.caption("Citeproof · local-first prototype · no generated shell commands or tests are executed.")
