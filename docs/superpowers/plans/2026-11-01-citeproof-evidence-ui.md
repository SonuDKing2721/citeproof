# Citeproof Evidence Quality and UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use the executing-plans skill to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make checked evidence the focus of the results view and add independent diagnostics for weak quotes and unsupported identifiers.

**Architecture:** Keep checking in `citeproof/checker.py` and diagnostics in a small helper module. Keep Streamlit as the UI, move only display helpers into a focused presentation module, version report additions, and render custom source HTML only after escaping all untrusted values.

**Tech Stack:** Python, AST, Streamlit, stdlib `html.escape`, CSS, unittest/pytest.

---

### Task 1: Add minimum quote quality

**Files:**
- Modify: `citeproof/checker.py`
- Test: `tests/test_checker.py`

- [ ] Add failing cases for `pass`, `return x`, an empty quote, and a meaningful one-line quote.
- [ ] Add a deterministic quote-quality predicate and `quote_too_short` outcome. Preserve the current empty, path, range, quote, and symbol outcomes.
- [ ] Run `python -m pytest -q tests/test_checker.py`; expect trivial quotes rejected and the meaningful quote verified.

### Task 2: Add identifier and failed-quote diagnostics

**Files:**
- Create: `citeproof/evidence_diagnostics.py`
- Modify: `citeproof/models.py`
- Modify: `citeproof/evaluation.py`
- Test: `tests/test_evidence_diagnostics.py`
- Test: `tests/test_evaluation.py`

- [ ] Add tests for an existing AST symbol, a missing symbol, a repository path, ignored inline literals, and an invalid citation quote echoed in its explanation.
- [ ] Implement bounded parsing of backticked identifiers and exact failed-quote echo detection. Store results separately from citation validity and diagnosis review.
- [ ] Run `python -m pytest -q tests/test_evidence_diagnostics.py tests/test_evaluation.py`; expect diagnostic rows to remain separate from localization scores.

### Task 3: Build safe numbered source panels

**Files:**
- Create: `citeproof/ui_components.py`
- Modify: `assets/citeproof.css`
- Modify: `app.py`
- Test: `tests/test_ui_components.py`
- Test: `tests/test_app_ui.py`

- [ ] Test HTML escaping for `<script>`, ampersands, quotes, issue text, file paths, and source lines before creating the panel markup.
- [ ] Render a bounded context window with line numbers, a pale-teal cited range, and an explicit Verified/Corrected/Rejected label. Show claimed and corrected ranges separately.
- [ ] Run `python -m pytest -q tests/test_ui_components.py tests/test_app_ui.py`; expect hostile strings rendered as text and no app exceptions.

### Task 4: Replace the long results page with evidence tabs

**Files:**
- Modify: `app.py`
- Modify: `assets/citeproof.css`
- Test: `tests/test_app_ui.py`

- [ ] Add AppTest assertions for Findings, Compare, Trace, and Report tabs, no emoji verdicts, a one-line run status, the `How to read this` popover, and the permanent diagnosis caveat.
- [ ] Implement the tabs and the exact palette/typography/shape constraints from the design spec. Keep the issue input accessible after a run.
- [ ] Show each sentence with a deterministic direct-citation anchor when one can be established; label other sentences `No direct citation anchor` and state that this is not entailment checking.
- [ ] Run `python -m pytest -q tests/test_app_ui.py`; expect correct tab contents and no unsafe HTML.

### Task 5: Persist and replay safe trace summaries

**Files:**
- Modify: `citeproof/models.py`
- Modify: `citeproof/agent.py`
- Modify: `citeproof/evaluation.py`
- Modify: `citeproof/presentation.py`
- Modify: `app.py`
- Test: `tests/test_agent.py`
- Test: `tests/test_presentation.py`
- Test: `tests/test_app_ui.py`

- [ ] Test that trace events contain tool names, sanitized request summaries, and bounded result summaries but never raw `read_file` text.
- [ ] Add an additive evaluation schema version and backward-compatible loading for v1-v3 reports, with `Trace results not stored` for older runs.
- [ ] Implement a slider that replays one saved trace event at a time without model calls.
- [ ] Run `python -m pytest -q tests/test_agent.py tests/test_presentation.py tests/test_app_ui.py`; expect old reports to load unchanged.

### Task 6: Generate issue-comment Markdown

**Files:**
- Create: `citeproof/issue_comment.py`
- Modify: `app.py`
- Test: `tests/test_issue_comment.py`
- Test: `tests/test_app_ui.py`

- [ ] Test pinned commit links for verified and corrected citations and safe fallback text for rejected citations or unpinned manual repositories.
- [ ] Build Markdown containing the finding, citation verdicts, exact GitHub line links, and the diagnosis limitation. Show it in a code block with the native copy control.
- [ ] Run `python -m pytest -q tests/test_issue_comment.py tests/test_app_ui.py`; expect links to use the pinned SHA and escaped path segments.
