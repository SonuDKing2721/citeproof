# Citeproof Evaluation and Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use the executing-plans skill to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make benchmark summaries reproducible, add a blind comparison review path, and verify the app's read-only boundary in CI.

**Architecture:** Read only saved JSON reports for documentation generation. Store blind labels as separate local annotations, never rewrite prior human reviews. Test issue-injected tool calls and symlinks at the repository boundary. Run the same unittest/pytest suite in GitHub Actions.

**Tech Stack:** Python stdlib, unittest/pytest, GitHub Actions.

---

### Task 1: Generate benchmark tables from saved reports

**Files:**
- Create: `citeproof/report.py`
- Create: `tests/test_report.py`
- Modify: `README.md`
- Modify: `docs/RELATED_WORK_AND_GAP_REVIEW.md`

- [x] Add fixture-based tests for complete, incomplete, and missing report fields and for small-sample count output.
- [x] Implement `python -m citeproof.report` to validate saved JSON and replace only marked generated blocks in README and related-work docs.
- [x] Render counts such as `1/5` for small n; retain explicit incomplete and not-scored states.
- [x] Run `.venv312\Scripts\python.exe -m pytest -q tests/test_report.py`; then run `.venv312\Scripts\python.exe -m citeproof.report --check` and expect both generated blocks current.

### Task 2: Add a bounded benchmark command

**Files:**
- Create: `citeproof/bench.py`
- Test: `tests/test_bench_cli.py`

- [x] Test argument parsing for a known case, unknown case, missing API key, and no-write behavior; mock the model client.
- [x] Implement `python -m citeproof.bench --case <id>` using the existing pinned-case loader, run orchestration, checker, and report builder. Keep the existing provider and request caps. Add an opt-in local Ollama profile limited to this CLI; local pair runs are sequential, omit the separate verifier call, and exclude cloud-tagged models.
- [x] Run `.venv312\Scripts\python.exe -m pytest -q tests/test_bench_cli.py`; tests use injected runners and make no inference calls.

### Task 3: Add blind pair-versus-baseline review

**Files:**
- Create: `citeproof/blind_review.py`
- Modify: `app.py`
- Test: `tests/test_blind_review.py`
- Test: `tests/test_app_ui.py`

- [x] Test stable report identity, randomized display order, hidden mapping before label save, reveal after a note is saved, and preservation of existing labels.
- [x] Implement an optional comparison review that persists only the blinded label/note/order mapping in a separate annotation file.
- [x] Run `.venv312\Scripts\python.exe -m pytest -q tests/test_blind_review.py tests/test_app_ui.py`; the suite passes and the comparison-report bytes remain unchanged.

### Task 4: Verify prompt injection, path traversal, and symlinks

**Files:**
- Modify: `citeproof/repo.py` only if a failing boundary test requires it
- Modify: `tests/test_agent.py`
- Modify: `tests/test_repo_symbols.py`
- Modify: `tests/test_checker.py`

- [x] Test an issue prompt that requests `../../.env`, a traversal path, a symlink to a file outside the root, and a symlinked directory outside the root.
- [x] Assert that tools refuse the read, no file contents escape, and the investigation receives a bounded tool error.
- [x] Run `.venv312\Scripts\python.exe -m pytest -q tests/test_agent.py tests/test_repo_symbols.py tests/test_checker.py`; 64 tests pass (symlink cases skip only where the OS cannot create links).

### Task 5: Add continuous integration

**Files:**
- Create: `.github/workflows/tests.yml`

- [x] Configure Windows and Linux jobs on pushes and pull requests, install Python 3.12 and `requirements.txt`, and run `python -m pytest -q tests`.
- [x] Validate YAML and confirm the workflow contains no secret values or inference calls.
- [x] Run `.venv312\Scripts\python.exe -m pytest -q tests`; 240 tests and 9 subtests passed after the final code changes.
