# Citeproof Citation and Investigator Localization Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each citation a stable deterministic outcome and add per-investigator file-ranking metrics without changing the meaning or provenance of historical reports.

**Architecture:** Keep citation checks local and deterministic. Preserve the model's original line claim, record any unique exact-quote correction separately, and derive citation summaries from typed outcomes. Add a new ranking contract in which findings are ordered from most to least plausible; retain pair metrics and keep legacy reports on their original contract.

**Tech Stack:** Python dataclasses, pathlib/AST source checks, Streamlit, JSON reports, unittest.

---

### Task 1: Implement typed citation outcomes and quote-range provenance

**Files:**
- Modify: `citeproof/models.py`
- Modify: `citeproof/checker.py`
- Test: `tests/test_checker.py`
- Read: `citeproof/repo.py` (`Repo._confined` path, file, and size behavior)

- [ ] Add failing tests in `tests/test_checker.py` for every stable outcome: `verified_exact`, `corrected_unique_exact_quote`, `path_missing`, `path_outside_repo`, `path_unreadable`, `invalid_range`, `range_too_wide`, `empty_quote`, `quote_not_found`, `quote_match_ambiguous`, `symbol_not_found`, and `symbol_range_mismatch`.
- [ ] Add a test where an exact quote appears once far from the claimed range. Assert the status is corrected, original `start_line`/`end_line` remain unchanged, and the corrected fields identify the true source span.
- [ ] Add tests that a repeated exact quote is ambiguous, a corrected range outside the named symbol is rejected, an absent symbol is rejected, an outside-root path is rejected, and an empty quote is never repaired.
- [ ] Run `python -m unittest tests.test_checker -v`. Expected before implementation: failures report missing outcome/provenance behavior; existing unrelated checker tests still run.
- [ ] Extend `Citation` in `citeproof/models.py` with `outcome: str | None = None`, `claimed_start_line: int | None = None`, `claimed_end_line: int | None = None`, `corrected_start_line: int | None = None`, and `corrected_end_line: int | None = None`. In `__post_init__`, copy the original `start_line`/`end_line` into claimed fields when none were supplied. Add an `effective_range` property that returns corrected fields when both are present, otherwise the original range.
- [ ] In `citeproof/checker.py`, map the twelve outcomes directly in code; leave `reason` as explanatory text, never parse it to recover a status. Map a confinement escape to `path_outside_repo`, a missing/non-file target to `path_missing`, and filesystem read errors to `path_unreadable`.
- [ ] Preserve exact quote, line-width, and AST symbol checks. When the claimed range fails, find exact-string occurrences in the same confined file. Correct only one unique occurrence, at any offset, and accept it only if its complete corrected range passes width and symbol checks. Multiple correction candidates return `quote_match_ambiguous`; zero return `quote_not_found` unless the input is structurally invalid or a symbol-specific outcome applies.
- [ ] Set `valid` to true only for `verified_exact` and `corrected_unique_exact_quote`. Keep model-claimed `start_line` and `end_line` unchanged; populate corrected fields only after all correction checks pass. Do not introduce fuzzy matching, quote normalization, or minimum-length rules.
- [ ] Run `python -m unittest tests.test_checker -v`. Expected after implementation: all checker tests pass, including all twelve outcome and range-provenance assertions.
- [ ] Run `git diff --check`; commit as `feat: classify citation checks and preserve claimed ranges`.

### Task 2: Render finding-level citation states in the app and report

**Files:**
- Modify: `citeproof/presentation.py`
- Modify: `citeproof/evaluation.py`
- Modify: `app.py`
- Test: `tests/test_presentation.py`, `tests/test_evaluation.py`, `tests/test_app_ui.py`

- [ ] Add failing tests for one finding in each summary state: `no_citations`, `none_verified`, `partly_verified`, and `all_verified`. A successful citation is one with outcome `verified_exact` or `corrected_unique_exact_quote`.
- [ ] Add tests that a corrected citation displays both the claimed and corrected range, a rejected quote remains visible with its reason, and a finding with no successful citation is called unverified by checked citations rather than an incorrect diagnosis.
- [ ] Run `python -m unittest tests.test_presentation tests.test_evaluation tests.test_app_ui -v`. Expected before implementation: new summary/render/export assertions fail.
- [ ] Add one pure finding summary helper in `citeproof/presentation.py`; reuse it in `citeproof/evaluation.py` so finding and run-level citation validation use the same four codes. Keep `diagnosis_review` separate.
- [ ] Update `app.py` to show the outcome, readable reason, quote, original claimed range, and corrected range when one exists. Keep rejected source text visible. Display an explicit note that citation verification does not determine diagnosis correctness.
- [ ] Serialize `outcome`, claimed range, corrected range, and finding citation summary in new reports. On saved-report load, disregard stored validity/outcome and recheck the quote against the pinned local checkout; retain original claim and correction provenance as data, not as proof.
- [ ] Run `python -m unittest tests.test_presentation tests.test_evaluation tests.test_app_ui -v`. Expected after implementation: all added and existing UI/report compatibility tests pass.
- [ ] Run `git diff --check`; commit as `feat: show typed citation support states`.

### Task 3: Add per-investigator rankings and explicit plausibility order

**Files:**
- Modify: `citeproof/agent.py`
- Modify: `citeproof/evaluation.py`
- Modify: `app.py`
- Test: `tests/test_agent.py`, `tests/test_evaluation.py`, `tests/test_app_ui.py`

- [ ] Add failing tests with investigators whose findings rank the same gold file at different positions; assert unique valid-citation file order, hit@1, reciprocal rank, and gold-file recall@3 independently for each investigator.
- [ ] Add tests that duplicate citations do not duplicate a file rank, rejected citations are omitted, incomplete investigations have null metrics, and a complete empty investigation with labels gets hit@1 false, reciprocal rank `0`, and recall@3 `0.0`.
- [ ] Run `python -m unittest tests.test_agent tests.test_evaluation tests.test_app_ui -v`. Expected before implementation: new ranking and metric fields are missing.
- [ ] Update the agent response instructions in `citeproof/agent.py` to order findings from most to least plausible file location without changing the response JSON shape.
- [ ] Add `InvestigatorLocalizationMetrics` and a per-investigator scorer in `citeproof/evaluation.py`. Walk findings in response order, keep unique files with valid checked citations, compute primary-file hit@1, reciprocal rank of the first gold primary file (`1 / rank`, or `0` when none is ranked), and recall@3 against primary plus supporting gold files. Return null metrics for incomplete results or absent labels. Keep current pair aggregation unchanged.
- [ ] Add the investigator metric rows separately to the app/report and label them as file-localization proxies; do not call them diagnosis scores.
- [ ] Run `python -m unittest tests.test_agent tests.test_evaluation tests.test_app_ui -v`. Expected after implementation: per-agent and existing pair/baseline metric assertions pass.
- [ ] Run `git diff --check`; commit as `feat: score investigator file rankings separately`.

### Task 4: Add v3 reports while preserving v1/v2 provenance

**Files:**
- Modify: `citeproof/evaluation.py`
- Modify: `citeproof/presentation.py`
- Modify: `app.py`
- Test: `tests/test_evaluation.py`, `tests/test_presentation.py`

- [ ] Add failing tests that new reports carry schema `citeproof-evaluation/v3` and ranking method `finding_order_descending_plausibility`, while v1 and v2 saved reports re-export with their original schema and no invented investigator metric.
- [ ] Add a v3 load/export test that preserves the ranking method and per-investigator metrics; confirm citation text is still rechecked against the pinned source checkout.
- [ ] Run `python -m unittest tests.test_evaluation tests.test_presentation -v`. Expected before implementation: v3 is rejected or historical reports are relabeled.
- [ ] Make `build_run_report` emit v3 by default for new live and baseline runs, with ranking method `finding_order_descending_plausibility`. Carry the saved schema and ranking-contract presence through `snapshot_from_saved_report` and the app state; pass a legacy mode only when restoring v1/v2. For old v1/v2 snapshots, retain the original schema and omit new ranking fields on export.
- [ ] Keep v1/v2 as supported load schemas and do not rewrite their source JSON, prompt history, or historical metrics. For v3, retain the declared ranking method and metric values while recomputing citation validity from the current pinned source.
- [ ] Run `python -m unittest tests.test_evaluation tests.test_presentation -v`. Expected after implementation: v1/v2 compatibility and v3 contract assertions pass.
- [ ] Run `git diff --check`; commit as `feat: version ranked localization reports`.

### Task 5: Run the full regression suite and review the final diff

**Files:**
- Review: `citeproof/models.py`, `citeproof/checker.py`, `citeproof/presentation.py`, `citeproof/evaluation.py`, `citeproof/agent.py`, `app.py`
- Review: `tests/test_checker.py`, `tests/test_presentation.py`, `tests/test_evaluation.py`, `tests/test_agent.py`, `tests/test_app_ui.py`

- [ ] Run `python -m unittest discover -s tests -v` and read the final summary. Expected: the full suite passes.
- [ ] Review `git diff --check` and the complete diff for path confinement, exact-string-only correction, unchanged pair metrics, historical schema preservation, and absence of provider calls, uploads, paid routes, and third-party code.
- [ ] If any critical issue remains, add a regression test first, watch it fail, fix it, and rerun the full suite before committing the fix.

## Review Focus

- A unique quote must not cross the repository root, bypass the AST symbol constraint, or be reported as verified when the corrected range is too wide.
- Claimed and corrected ranges must remain distinguishable after a save/load cycle.
- Only verified citations enter file rankings; rank order comes from the new response contract, not from historical claims.
- Legacy v1/v2 reports must never be labeled as though their findings followed the v3 ranking prompt.
- Citation validity and per-agent localization are not diagnosis-correctness scores.
