# Citeproof Run Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use the executing-plans skill to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make live runs report endpoint health, retry transient provider failures within explicit budgets, and offer a verified cached fallback.

**Architecture:** Keep the NVIDIA OpenAI-compatible client and existing `ModelRequestBudget`. Add a separate health-check helper, bounded repository pre-seed, retry accounting, and same-issue saved-report lookup. No test makes a live model request.

**Tech Stack:** Python, OpenAI SDK, Streamlit, unittest/pytest.

---

### Task 1: Add endpoint health states

**Files:**
- Create: `citeproof/health.py`
- Modify: `app.py`
- Test: `tests/test_health.py`

- [x] Test ready under 5 seconds, slow response before 15 seconds, timeout at 15 seconds, and missing key. Use a fake clock/client; assert no real network access.
- [x] Implement `check_endpoint(client, *, timeout_seconds=15, slow_after_seconds=5)` returning only `{status, elapsed_seconds, error}`. Send a fixed, non-sensitive prompt with a five-token output limit.
- [x] Run `python -m unittest discover -s tests -p 'test_health.py' -v`; all four health-state cases passed after the expected missing-module RED run.
- [x] Add a single status pill to the run controls. Trigger the ping only when the user asks to check endpoint and retain its result in session state; require Ready or Slow before a run.
- [x] Run `python -m unittest discover -s tests -p 'test_app_ui.py' -v`; all 11 AppTest cases pass and the three endpoint labels are visible.

### Task 2: Retry only transient model failures

**Files:**
- Modify: `citeproof/agent.py`
- Modify: `citeproof/model_config.py`
- Test: `tests/test_agent.py`

- [x] Add fake-client tests proving retry delays are `[5, 15, 30]` for retryable errors and that `BadRequestError` is attempted once.
- [x] Add a test proving each attempt increments `ModelRequestBudget.used` and that the agent deadline stops further retries.
- [x] Implement retry classification for connection errors, timeouts, rate limits, and server errors only. Wait via an injected sleeper in tests and `time.sleep` in production. Keep the SDK's automatic retries disabled.
- [x] Run `python -m unittest discover -s tests -p 'test_agent.py' -v`; all 28 cases passed.
- [x] Surface retry count and total attempts in progress events and the saved run summary.

### Task 3: Pre-seed from issue clues

**Files:**
- Modify: `citeproof/repo.py`
- Modify: `citeproof/diagnostics.py`
- Modify: `citeproof/orchestration.py`
- Modify: `citeproof/agent.py`
- Test: `tests/test_repo_symbols.py`
- Test: `tests/test_orchestration.py`

- [x] Test that error phrases and traceback basenames produce bounded search results, that duplicate/short clues are dropped, and that traversal-like path text is never opened.
- [x] Implement deterministic, read-only text search and basename matching with limits of three clues, 20 source hits, and 3,000 total characters.
- [x] Prefix the resulting prompt block as untrusted source context and pass the same pre-seed to both investigators.
- [x] Run `python -m unittest discover -s tests -p 'test_repo_symbols.py' -v` and `python -m unittest discover -s tests -p 'test_orchestration.py' -v`; all 6 and 4 cases passed.

### Task 4: Offer same-issue cached fallback and account budgets

**Files:**
- Modify: `citeproof/presentation.py`
- Modify: `app.py`
- Test: `tests/test_presentation.py`
- Test: `tests/test_app_ui.py`

- [x] Test saved-report selection by issue ID, pinned commit, valid JSON, and complete-first preference. Include an explicit legacy state where trace results were not stored.
- [x] Implement lookup of the newest complete saved report for the selected issue and reject commit mismatches before loading.
- [x] Offer `Open saved run` after an unavailable health result or incomplete timeout, and label it cached with its original time and current citation recheck.
- [x] Show health request, investigator attempts, retries, verifier requests, and elapsed phase times separately.
- [x] Run `python -m unittest discover -s tests -p 'test_presentation.py' -v`, `...test_evaluation.py...`, and `...test_app_ui.py...`; 18, 29, and 14 cases passed.
