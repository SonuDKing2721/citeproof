# Citeproof Evaluation and Interface Implementation Plan

> **For agentic workers:** Execute inline in this thread, following each checkbox in order.

**Goal:** Give Citeproof an honest, reproducible issue-localization evaluation and a polished Streamlit interface built with selected MIT-licensed Shadcn components.

**Architecture:** Keep model orchestration in `citeproof/agent.py`, add deterministic metrics and report serialization in `citeproof/evaluation.py`, and keep the interface in Streamlit. Use only the current Shadcn component package APIs supported by Streamlit 1.66.1; retain native Streamlit controls where that avoids fragile component state.

**Tech Stack:** Python 3.12, Streamlit 1.66.1, streamlit-shadcn-ui 1.4.0, unittest, Muse Glimmer through NVIDIA's free API Catalog endpoint.

---

## Task 1: Establish reproducible evaluation metrics

**Files:**
- Create: `citeproof/evaluation.py`
- Create: `tests/test_evaluation.py`
- Modify: `data/gold/click-2877.json`
- Modify: `README.md`

- [ ] Define file-hit@1 and recall@3 from ranked cited source files against human-curated primary/supporting labels. Exclude errored runs and count only completed runs. State that changed files are proxy labels.
- [ ] Add tests for correct primary hit, supporting-file recall, missed result, duplicate citations, and failed-run exclusion.
- [ ] Add a report format with case ID, repo commit, model ID, provider, timestamp, result status, metric values, and an explicit human-review field for diagnosis correctness.
- [ ] Add a UI download report that includes run metadata and checked findings while omitting hidden gold file lists from the export.
- [ ] Document that one case is a smoke evaluation only and cannot support broad performance claims.

## Task 2: Refine the Streamlit product flow

**Files:**
- Modify: `app.py`
- Modify: `requirements.txt`
- Modify: `README.md`

- [ ] Add a precise dependency on `streamlit-shadcn-ui==1.4.0`, which supports Streamlit 1.60+; test component imports and renders under the current 1.66.1 runtime.
- [ ] Use Shadcn components selectively for compact status badges/cards; retain native text inputs and trace rendering.
- [ ] Move billing, provider privacy, and trial limitations into a compact expandable note; keep the active provider/model visible near the run control.
- [ ] Present issue intake, run state, agent evidence, and verified overlap in a clear hierarchy; preserve incomplete/error states and rejected quotes.
- [ ] Run the full unit suite, Python compilation, Streamlit health check, and browser inspection at desktop and narrow viewport widths.

## Task 3: Validate the live workflow and evaluation boundary

**Files:**
- Modify: `docs/reviews/Citeproof-Stress-Simulation-Report.md`
- Modify: `README.md`

- [ ] Confirm the sample checkout is still the pinned clean pre-fix commit.
- [ ] Run one controlled plain request, one tool round trip, then the full two-agent sample if the provider is responsive; record latency and outcome without logging credentials.
- [ ] Save a real result through the evaluation path and verify the issue's gold data is not present in the prompt or exported agent result.
- [ ] Record provider failures as incomplete and avoid presenting one issue as a benchmark.
- [ ] Review the updated UI in the local browser and correct any runtime or layout regressions.
