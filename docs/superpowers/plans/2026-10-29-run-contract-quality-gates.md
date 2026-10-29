# Run Contract and Quality Gates Implementation Plan

**Status:** Implemented and verified; latest free-endpoint comparison is recorded as incomplete where appropriate.

> **For implementation:** Work inline in the current checkout. Preserve the existing uncommitted changes; stage only files explicitly named in a later user-approved commit.

**Goal:** Make the app, benchmark, JSON exports, and documentation report the same workflow state and provenance without confusing checked citations, localization, verifier output, or diagnosis correctness.

**Architecture:** Keep `citeproof.evaluation` as the single source that builds the run report. Add explicit per-stage status, workflow provenance, model settings, and measured durations there; make Streamlit render those same fields and teach saved-report loading to accept both v1 and v2. Keep inference architecture and request limits unchanged while the new report contract is tested.

**Tech Stack:** Python 3.12, Streamlit 1.66.1, `unittest`, Muse Glimmer through the already configured free NVIDIA API Catalog endpoint.

---

## File responsibilities

- `citeproof/evaluation.py` — shared status projection, report schemas, and export payload.
- `citeproof/model_config.py` — single source for shared model ID, timeout, and per-role inference settings.
- `citeproof/agent.py`, `citeproof/verifier.py` — use the shared per-role settings for API calls.
- `citeproof/benchmark.py` — pair/baseline elapsed-time measurement and comparison provenance.
- `citeproof/presentation.py` — saved v1/v2 report loading, preservation of request counts, and live/cached provenance.
- `app.py` — use the report summary for visible status and start-to-finish timing.
- `tests/test_evaluation.py`, `tests/test_benchmark.py`, `tests/test_presentation.py`, `tests/test_app_ui.py` — contract, timing, migration, and visible-state checks.
- `README.md`, `docs/CITEPROOF_PROJECT_GUIDE.md`, `docs/CITEPROOF_HANDOFF.md` — align claims with the saved reports and code.

## Task 1: Define and test the run-state contract

**Files:** `tests/test_evaluation.py`, `citeproof/evaluation.py`

- [x] **Step 1: Add failing tests for the shared state projection.** Define `run_status_payload(results, gold_case, verification, workflow_kind, minimum_agents=2)` and require keys `investigation`, `citation_validation`, `cross_check`, `verification`, `localization`, `diagnosis_review`, and `workflow_kind`. Cover one failed investigator, no citations, all rejected citations, mixed valid/rejected citations, missing gold, and a one-agent baseline. Empty or rejected evidence may be scored as a localization miss when the investigation completed and gold exists; failed investigations and missing labels must not be scored. Human diagnosis states are allowlisted separately from citation checks.

```python
def test_report_states_distinguish_valid_quotes_from_optional_review():
    pair = [
        result("A", ["src/fix.py"]),
        result("B", ["src/fix.py"]),
    ]
    review = VerificationReview(status="unavailable", error="timeout")

    state = run_status_payload(
        pair,
        {"primary_files": ["src/fix.py"]},
        review,
        workflow_kind="live_pair",
    )

    assert state["investigation"] == "complete"
    assert state["citation_validation"] == "all_valid"
    assert state["cross_check"] == "overlapping_lines"
    assert state["verification"] == "unavailable"
    assert state["localization"] == "scored"
    assert state["diagnosis_review"] == "not_reviewed"
```

- [x] **Step 2: Run the focused test and confirm the expected missing-function failure.**

Run: `.\.venv312\Scripts\python.exe -m unittest tests.test_evaluation.RunStateContractTests -v`

Expected: FAIL because `run_status_payload` is not defined.

- [x] **Step 3: Implement the smallest pure status projection.** Reuse `score_localization` and `compare_evidence`; use explicit existing cross-check states (`needs_two_agents`, `incomplete`, `no_verified_citations`, `different_files`, `same_file`, `overlapping_lines`). Count every citation as not present, none valid, partly valid, or all valid. `verification=None` means `not_requested`; preserve `skipped` and `unavailable` as distinct states. A baseline passes `minimum_agents=1`.

```python
def run_status_payload(results, gold_case, verification, workflow_kind, minimum_agents=2):
    metrics = score_localization(results, gold_case, minimum_agents=minimum_agents)
    citations = [
        citation
        for agent in results[:minimum_agents]
        for finding in agent.findings
        for citation in finding.citations
    ]
    valid_count = sum(citation.valid for citation in citations)
    if not citations:
        citation_state = "not_present"
    elif valid_count == 0:
        citation_state = "none_valid"
    elif valid_count < len(citations):
        citation_state = "partly_valid"
    else:
        citation_state = "all_valid"

    complete = len(results) >= minimum_agents and not any(
        agent.error for agent in results[:minimum_agents]
    )
    localization = {
        "complete": "scored",
        "incomplete": "incomplete",
        "missing_gold_labels": "missing_labels",
    }.get(metrics.status, "not_scored")
    cross_check = (
        "not_applicable"
        if workflow_kind == "single_agent_baseline"
        else compare_evidence(results).status
    )
    return {
        "investigation": "complete" if complete else "incomplete",
        "citation_validation": citation_state,
        "cross_check": cross_check,
        "verification": verification.status if verification else "not_requested",
        "localization": localization,
        "diagnosis_review": "not_reviewed",
        "workflow_kind": workflow_kind,
    }
```

- [x] **Step 4: Re-run the focused test module.**

Run: `.\.venv312\Scripts\python.exe -m unittest tests.test_evaluation -v`

Expected: all evaluation tests pass.

## Task 2: Version reports and preserve workflow provenance

**Files:** `citeproof/evaluation.py`, `citeproof/presentation.py`, `tests/test_evaluation.py`, `tests/test_presentation.py`

- [x] **Step 1: Add failing report tests.** Require schema `citeproof-evaluation/v2`, the state projection from Task 1, an explicit live/cached workflow kind, exact model/provider and per-role inference settings, nonnegative duration fields, and request counts that sum correctly. Capture the fake OpenAI client payloads and assert the exported settings are the same constants passed to each API request. Ensure gold labels and secret-like environment values never appear.
- [x] **Step 2: Run the focused tests and confirm they fail on the current v1 report.**

Run: `.\.venv312\Scripts\python.exe -m unittest tests.test_evaluation tests.test_presentation -v`

Expected: FAIL on the missing v2 state/provenance fields and schema handling.

- [x] **Step 3: Centralize the settings currently passed by `agent.py` (Muse Glimmer, temperature 0.95, top-p 1.0, low reasoning, 8192 output tokens) and `verifier.py` (Muse Glimmer, temperature 0.2, endpoint-default top-p 1.0, low reasoning, 1800 output tokens) in `citeproof/model_config.py`. Use those constants in the API calls and export them from the same values.** Keep `status` temporarily for older consumers, but define it as the localization metric status; use the new `states` object for stage-specific status. Pass the original run timestamp into report construction so Streamlit reruns do not silently rewrite it. Store durations as bounded numeric seconds or null when not measured; never synthesize timings from old reports.
- [x] **Step 4: Add backward-compatible restore tests.** Continue to load v1 saved reports with citations rechecked against the pinned repository; load v2 the same way and retain its original workflow kind, timestamps, settings, and stage durations. Preserve legacy aggregate request counts without inventing per-agent splits.
- [x] **Step 5: Implement v1/v2 restore and run focused tests.** Reject unknown schemas and mismatched issue/commit exactly as today.

Run: `.\.venv312\Scripts\python.exe -m unittest tests.test_evaluation tests.test_presentation -v`

Expected: all focused tests pass, including old v1 fixtures.

## Task 3: Measure each live workflow phase and align the UI

**Files:** `citeproof/benchmark.py`, `app.py`, `citeproof/presentation.py`, `tests/test_benchmark.py`, `tests/test_app_ui.py`

- [x] **Step 1: Add failing timing tests for comparison runs.** Use an injected deterministic clock or a patched `time.monotonic`; verify investigator-pair time and verifier time are separate, baseline time is separate, and total time includes all stages. Incomplete pair/baseline outcomes must preserve durations and statuses.
- [x] **Step 2: Run benchmark tests and confirm timing assertions fail.**

Run: `.\.venv312\Scripts\python.exe -m unittest tests.test_benchmark -v`

Expected: FAIL because `BudgetMatchedComparison` does not yet expose measured durations.

- [x] **Step 3: Add bounded duration fields and measure with monotonic time.** Extend `BudgetMatchedComparison`; measure investigator pair, optional verifier, baseline, and total separately in `run_budget_matched_comparison`. In Streamlit, measure investigator pair, optional verifier, and total in the session snapshot. Cached runs must retain the original duration if known and otherwise show “not recorded.”
- [x] **Step 4: Make the app render from the same report state.** Build the report once per displayed result and use its metrics/states for the labels and download. Keep individual agent error, citation, and verifier details visible. Show “cached investigation + live review” as a distinct workflow kind, and never label verifier `unavailable` as an overall success. Add optional human review; require a reason before recording a reviewed diagnosis state.
- [x] **Step 5: Add UI tests for live, cached, incomplete, and verifier-unavailable labels; run focused tests.**

Run: `.\.venv312\Scripts\python.exe -m unittest tests.test_benchmark tests.test_app_ui tests.test_presentation -v`

Expected: all focused tests pass; cached and live states are visibly distinct.

## Task 4: Refresh measured claims and verify the integrated contract

**Files:** `README.md`, `docs/CITEPROOF_PROJECT_GUIDE.md`, `docs/CITEPROOF_HANDOFF.md`, `tests/test_evaluation.py`

- [x] **Step 1: Add a regression test for the current budget-matched comparison artifact.** Confirm pair and baseline each used 11 calls, the pair ranked `src/click/_termui_impl.py` first, the single investigator ranked `src/click/testing.py` first, both recall@3 values were `0.2`, and the verifier returned `insufficient_evidence`. Treat this as one Click case, not a general result.
- [x] **Step 2: Run the focused artifact check.**

Run: `.\.venv312\Scripts\python.exe -m unittest tests.test_evaluation -v`

Expected: the saved report can be parsed without exposing gold labels and the checked values match the artifact.

- [x] **Step 3: Update documentation from the verified reports.** Replace stale statements that no end-to-end review succeeded. Clearly distinguish the 79.7-second live pair-plus-verifier run, the newer 11-vs-11 budget-matched comparison, the 88.312-second incomplete v2 comparison, and the 16.4-second cached-pair/live-review run. Do not claim diagnosis accuracy, broad success, or open-weight bonus eligibility from these runs.
- [x] **Step 4: Run the full verification set.**

Run: `.\.venv312\Scripts\python.exe -m unittest discover -s tests`

Expected: all tests pass.

Run: `.\.venv312\Scripts\python.exe -m compileall -q app.py citeproof scripts`

Expected: exit code 0.

Run: `git diff --check`

Expected: exit code 0; ignore only Git's expected LF/CRLF conversion notices.

Run: `Invoke-WebRequest -Uri http://127.0.0.1:8501/ -TimeoutSec 5 | Select-Object -ExpandProperty StatusCode`

Expected: `200`.

- [x] **Step 5: Run one current live end-to-end comparison only if the free NVIDIA endpoint remains available.** Used the exact clean pre-fix pin and saved a v2 comparison with measured durations. The free NVIDIA route responded; the pair completed but the baseline exhausted its request budget after malformed final output, so the overall comparison is retained as incomplete rather than called a pass.

## Task 5: Surface completed empty outcomes and follow bounded local calls

**Files:** `citeproof/evaluation.py`, `citeproof/agent.py`, `app.py`, `tests/test_evaluation.py`, `tests/test_agent.py`, `tests/test_app_ui.py`

- [x] **Step 1: Add failing tests.** Require complete zero-finding reports to carry a `no_findings` summary and preserve 0% recall; incomplete runs must remain `incomplete`. Require the UI to say when a completed investigation returned no findings. Require source auto-follow to reach a nested imported helper and expose followed paths in the trace.
- [x] **Step 2: Add the deterministic report and UI summary.** Keep run/localization completion semantics unchanged, but export a bounded per-run `finding_summary` and display a clear no-findings or no-verified-citations outcome.
- [x] **Step 3: Extend local source following without adding model calls.** Follow no more than two additional call levels, five snippets, and 4,300 characters; preserve import-resolution rules and log each included symbol/path in the investigator trace.
- [x] **Step 4: Verify focused and full checks.** The new regression tests first failed on the old implementation. Focused tests then passed; the full suite passed **120 tests**, `compileall` passed, and `git diff --check` reported only expected LF/CRLF notices.
- [x] **Step 5: Rerun the exact pinned Click #3449 comparison through the existing free NVIDIA prototype route.** No paid fallback was configured. Both first requests timed out after 122.468 seconds, so the saved comparison is incomplete with no localization score: `data/benchmarks/click-3449-post-follow-quality-20261029.json`.

## Plan self-review

- All seven run-state dimensions are covered by projection tests, JSON export tests, UI tests, and compatibility tests.
- Live, cached, comparison, incomplete, verifier-skipped, and verifier-unavailable paths are represented separately.
- The existing v1 format remains readable; new output uses a versioned v2 schema.
- No plan task adds agents, tools, a paid provider, or uncapped model calls.
- Human diagnosis review is an optional explicit human label with a required note; it does not change localization metrics or claim a benchmark score.
- The plan does not mark diagnosis quality as verified until a human reviewer checks the issue/fix evidence.
