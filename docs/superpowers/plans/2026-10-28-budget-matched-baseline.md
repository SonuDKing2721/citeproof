# Budget-Matched Single-Agent Baseline Plan

> **For agentic workers:** Implement inline in this checkout. Use test-first checkpoints and keep live provider calls out of automated tests.

**Goal:** Compare Citeproof's two-investigator workflow with one investigator using exactly the same number of model requests on the same pinned issue and repository.

**Architecture:** Count every attempted model request, including correction requests, in `AgentResult`. Run the normal pair first, then give a single investigator the exact request count consumed by that pair. Score the single result as one investigator and the pair as two; export request counts, localization metrics, and checked evidence without exporting gold file labels.

**Tech Stack:** Python 3.12, Streamlit project modules, `unittest`, NVIDIA API Catalog Muse Glimmer.

---

## File map

- `citeproof/models.py`: store each investigator's model-request count.
- `citeproof/agent.py`: enforce a request budget and permit a benchmark-selected completion limit while preserving current defaults.
- `citeproof/evaluation.py`: score a one-investigator result and serialize a comparison report without exposing gold labels.
- `citeproof/benchmark.py`: run the two-agent pair, size the single-agent budget from observed pair calls, and load/save curated-case reports.
- `tests/test_agent.py`, `tests/test_evaluation.py`, `tests/test_benchmark.py`: cover counting, equal budgets, and label privacy with fake clients.
- `docs/CITEPROOF_HANDOFF.md`, `README.md`: state the baseline rule and latest actual comparison evidence.

## Task 1: Count model requests

**Files:** Modify `citeproof/models.py`, `citeproof/agent.py`, `tests/test_agent.py`.

- [x] Add `model_requests: int = 0` to `AgentResult` after existing default fields so current positional construction remains valid.
- [x] Add `ModelRequestBudget(limit: int, used: int = 0)` with `request(client, payload)`: reject when `used >= limit`, increment before attempting the provider request, and return `client.chat.completions.create(**payload)`.
- [x] Make `investigate(..., max_completions=MAX_COMPLETIONS_PER_AGENT, request_budget=None)` use a private budget of `max_completions + MAX_FINAL_RESPONSE_RETRIES` when none is supplied; route both normal completions and correction completions through it.
- [x] Build the strategy prompt's tool-round limit from `max_completions - 1`; keep the last completion reserved for synthesis and the prior tool round reserved for `read_file`.
- [x] Return the request budget's `used` count on every success or error result.
- [x] Add fake-client tests proving a normal four-completion investigation counts four, a correction request is counted, and an exhausted budget prevents an extra provider call.
- [x] Run `.venv312\Scripts\python.exe -m unittest discover -s tests -p test_agent.py`; test-first red/green verified and tests pass.

## Task 2: Permit single-investigator localization scoring

**Files:** Modify `citeproof/evaluation.py`, `tests/test_evaluation.py`.

- [x] Add `minimum_agents: int = 2` to `score_localization`; keep the default two-agent requirement and mark a single result complete only when `minimum_agents=1`.
- [x] Test that one result ranks unique valid citation paths in first-seen order, scores hit@1 and recall@3, and still ignores invalid citations.
- [x] Leave existing two-agent ranking and incomplete-run behavior unchanged.
- [x] Run `.venv312\Scripts\python.exe -m unittest discover -s tests -p test_evaluation.py`; 9 tests pass.

## Task 3: Run the budget-matched comparison

**Files:** Create `citeproof/benchmark.py`, create `tests/test_benchmark.py`.

- [x] Add `run_budget_matched_comparison(repo, issue, gold_case, on_progress=None, investigator=investigate)`.
- [x] Run symptom-first and structure-first investigators with their existing four-completion caps and distinct first tools; sum their actual `model_requests`.
- [x] If either paired result has an error or the pair used zero requests, return an incomplete comparison and do not spend calls on the baseline.
- [x] Otherwise run one investigator with `max_completions` and `ModelRequestBudget.limit` both equal to the pair's actual request count; use the same issue, repo, model, tools, and output-token cap.
- [x] Return paired results, baseline result, exact request counts, and equality status.
- [x] Unit-test exact budget equality, preservation of incomplete provider results, and that issue text—not gold labels—is passed to investigator calls.
- [x] Run `.venv312\Scripts\python.exe -m unittest discover -s tests -p test_benchmark.py`; 6 tests pass.

## Task 4: Export the comparison safely

**Files:** Modify `citeproof/evaluation.py`, `citeproof/benchmark.py`, `tests/test_benchmark.py`.

- [x] Build a versioned JSON report containing issue ID, pinned commit, model/provider, UTC time, pair and baseline request counts, `budget_matched`, localization metrics, findings, checked citations, and `diagnosis_review: not_scored`.
- [x] Omit `primary_files` and `supporting_files` from all report sections.
- [x] Mark single-agent evidence comparison as `not_applicable`; never imply it has two-agent corroboration.
- [x] Add a CLI entry point `python -m citeproof.benchmark --repo PATH --issue PATH --gold PATH --output PATH`; require a clean pinned `Repo`, load issue text separately from gold, and write JSON only after both evaluations finish.
- [x] Add tests for output schema, equal budget fields, no gold-label leakage, and refusal to run the baseline after an incomplete pair.

## Task 5: Verify and measure one live case

**Files:** Modify `docs/CITEPROOF_HANDOFF.md`, `README.md`; output `data/benchmarks/click-3449-budget-comparison.json`.

- [x] Run the CLI on Click #3449 at its pinned pre-fix commit using the configured NVIDIA free endpoint; do not switch to a paid provider. The 2026-10-28 attempt timed out on both pair requests and saved an incomplete result.
- [x] Check request counts; when provider calls fail, save the run as incomplete, skip the single-agent baseline, and do not report scores. The current report records pair=2, baseline=0.
- [x] Confirm the result JSON contains no gold file lists and makes no diagnosis-accuracy claim.
- [x] Run `.venv312\Scripts\python.exe -m unittest discover -s tests` (42 pass), `.venv312\Scripts\python.exe -m compileall -q app.py citeproof`, and `git diff --check`.
- [x] Update README and the handoff with the measured result and its two-case benchmark limits.

The experiment is implemented and the failure path is verified. A successful, actually budget-matched live comparison is still a required follow-up because the endpoint timed out.
