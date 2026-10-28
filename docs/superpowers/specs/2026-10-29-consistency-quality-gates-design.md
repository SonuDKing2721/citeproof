# Citeproof Consistency and Reliability Gates

**Date:** 2026-10-29
**Status:** Draft for user review
**Scope:** Existing Citeproof workflow and its evaluation/reporting contract

## Goal

Make Citeproof's UI, JSON reports, benchmark results, and project documentation describe the same run consistently, while measuring localization and diagnosis quality separately. Keep the user-facing workflow useful when one optional stage fails, and preserve a bounded response time.

## Current findings

- The working-tree test suite has 97 passing tests; compilation, `git diff --check`, and the local Streamlit health check pass.
- A saved live end-to-end Click #3449 run completed in 79.7 seconds with 9 investigator requests and 1 verifier request. The investigators had checked overlapping evidence. The primary file ranked second (`hit@1=false`; `recall@3=0.2`), so it is not an unqualified localization success. Diagnosis correctness is unscored.
- A separate verifier call completed in 16.4 seconds using cached investigator results. It is a reviewer-only run, not another live end-to-end run.
- The handoff and README were last written before these reports and still say no end-to-end verifier run completed. The report also records `status=complete` when localization can be scored even though the verifier may be unavailable; the status needs a clearer definition in the user-facing contract.
- The app currently uses NVIDIA's documented endpoint sampling pair (`temperature=0.95`, `top_p=1.0`) and explicitly requests low reasoning effort. NVIDIA's endpoint reference says the default reasoning effort is high and reasoning shares the output-token budget. The model overview has different general sampling recommendations, so project settings must be tied to the exact endpoint reference rather than mixed across pages.

## Design

### 0. Map the work to judging and award eligibility

- **Stage 1:** show a clear fit with the software frontier theme and demonstrate a real Meta model contribution. Citeproof's use of Muse Glimmer is promising, but the competition's acceptance of the NVIDIA-hosted route for the open-weight bonus is not verified; keep this as an eligibility gate, not a marketing claim.
- **Impact:** demonstrate the maintainer workflow on real public issues and report per-case localization plus human diagnosis review. Add a small user validation or maintainer feedback if the user can obtain it; do not invent adoption or time-saved claims.
- **Use of Meta AI tooling:** make the actual Muse model, provider, tools, agent trace, and what each call contributed visible in the demo and run report. Avoid presenting the model name alone as proof of creative use.
- **Technical depth and execution:** highlight pinned pre-fix repositories, independent search strategies, read-only allowlisted tools, deterministic citation checking, and the budget-matched control; demonstrate that failures remain visible.
- **Demo:** prepare a reliable live path and an explicitly labeled cached fallback, with a short video that shows one useful discovery, one uncertainty/rejected citation, and measured runtime.
- **Bonus focus:** prioritize the agentic-use case and open-weight awards already selected by the user. Citeproof does not currently use Muse Image or Muse Wonder, so it should not claim the creative-build bonus without a deliberate, eligible creative feature and enough time to validate it.

The Meta event page describes Indie judging around creativity, technical ambition, and working behavior; the user-provided judging screenshot gives the four equally weighted Stage 2 categories. The currently published Cerebral event page lists Baseten, Modal, and Fireworks as inference partners for Meta open-weight models, but does not establish that NVIDIA is eligible for the open-weight bonus. Until an organizer confirms the route, distinguish Stage 1 model use from bonus eligibility and show the exact inference provider in the submission.

### 1. Keep one explicit result contract

Add a versioned result summary built once from the investigator results, verified citations, optional verifier review, localization metrics, and run provenance. The UI and exported JSON should consume the same summary rather than independently deriving labels.

Represent these dimensions separately:

- **Investigation:** complete or incomplete, including whether both investigators returned.
- **Citation validation:** not present, present but none valid, partly valid, or all valid; valid means path, source range, quote, and any supplied symbol passed deterministic checks.
- **Cross-check:** use the explicit states `needs_two_agents`, `incomplete`, `no_verified_citations`, `different_files`, `same_file`, or `overlapping_lines`.
- **Verifier:** reviewed, skipped with reason, unavailable, or not requested. This is optional and must not erase valid investigator output.
- **Localization evaluation:** scored, incomplete, missing labels, or not scored, with hit@1 and recall@3 clearly labeled as changed-file proxies.
- **Diagnosis review:** not reviewed, supported, partly supported, unsupported, or incorrect, entered by a human and kept separate from citation validity.
- **Provenance:** issue ID, pinned repository commit, model ID/provider, effective sampling and reasoning parameters, stage timings, request counts, and whether investigator results were live or cached.

`complete` must always name the stage it describes. A cached-pair/live-review demonstration must be visibly distinct from a live end-to-end investigation. An unavailable verifier must remain a verifier failure, not a fabricated success or a reason to discard valid searches. Keep the existing comparison status values and their separate meaning: a localization score can be complete while an optional verifier is unavailable.

### 2. Make evaluations reproducible and honest

- Keep the request-budget-matched single-investigator comparison. Record latency and request counts for both paths and state that equal request counts do not imply equal tokens, cost, or reasoning quality.
- Report each curated case separately. Show the number of reviewed cases and avoid presenting a six-case smoke set as a general accuracy claim.
- Add human diagnosis adjudication against the issue, pinned source, merged fix, and relevant tests. Record the reason and reviewer separately from machine citation checks.
- Treat post-cutoff issues as lower-contamination-risk candidates, not proof of training-data exclusion.
- Use stable, saved run records for all measured claims. Keep cached examples available for a reliable no-call demo, labeled with their original timestamps and model settings.

### 3. Keep latency bounded and diagnose before optimizing

- Preserve two independent concurrent investigators, current per-request timeout, per-investigator wall-clock budget, and at most one verifier call.
- Add/standardize per-stage timing and terminal status so slow requests, malformed responses, invalid citations, and verifier timeouts are distinguishable.
- Do not add more agents, tool rounds, streaming, or request retries until a measured case shows the current budget is inadequate. Any added request must be included in the comparison budget.
- Do not promise identical model answers. If a fixed API seed is evaluated, document that NVIDIA describes it as best-effort determinism; require repeated-run evidence before making it the default.

### 4. Use narrow, evidence-driven changes

- Use existing Python, Streamlit, unittest, and Muse/NVIDIA integrations. Do not add unrelated packages or skill packs. Discover/install an additional skill only for a concrete task that the available skills do not cover.
- Research model parameters and service behavior from the exact official endpoint documentation. Keep license, provider, privacy, and hackathon eligibility claims sourced and explicit.
- Keep repository analysis read-only and pinned for curated evaluations. Preserve issue text as untrusted data and never execute repository code as part of diagnosis.

## Alternatives considered

1. **Quality gates first (selected):** align statuses, reports, tests, evaluations, and documentation before adding more autonomy. This directly reduces misleading results and makes regressions diagnosable.
2. **Increase agent autonomy first:** more tool rounds or agents may find deeper code paths but increase latency, request use, and output variance before we know what failure it solves.
3. **UI polish first:** can make the demo feel better, but cannot resolve stale metrics or distinguish a checked quote from a correct diagnosis.

## Acceptance criteria for implementation

- A single run summary drives UI status and JSON export; cached and live workflow provenance cannot be confused.
- Table-driven tests cover combinations of investigator, citation, cross-check, verifier, localization, and diagnosis-review states.
- Optional verifier failure does not erase valid investigation evidence; incomplete investigator runs are never scored as complete localization results.
- Reports include bounded timing and request accounting and omit hidden gold labels and secrets.
- A paired evaluation report states its request budget, latency, per-case localization values, diagnosis-review status, and limitations.
- Handoff, README, and project guide agree with code and the saved run reports.
- Full unit suite, compilation, diff checks, Streamlit health, and at least one current live end-to-end run pass before claiming the workflow is verified. A live call may fail due to service availability; that is reported as unavailable/incomplete, not hidden.

## Research references

- [Meta Global AI Developer Hackathon page](https://dev.meta.ai/events/global-hackathon) — themes, tracks, and public schedule.
- [Cerebral Valley event page](https://events.cerebralvalley.ai/e/meta-ai-developer-hackathon) — announced inference partners and event details; exact bonus eligibility still requires the published rules or organizer confirmation.
- [NVIDIA Muse Glimmer chat-completions API reference](https://docs.api.nvidia.com/nim/reference/meta-muse-glimmer-30b-infer) — endpoint parameters, reasoning effort, token-budget behavior, and best-effort seed behavior.
- [NVIDIA Muse Glimmer model overview](https://docs.api.nvidia.com/nim/reference/meta-muse-glimmer-30b) — model-level capabilities and application-specific evaluation caveat; do not substitute its model-level sampling guidance for the endpoint reference.
- [SWE-bench paper](https://arxiv.org/abs/2310.06770) — real issues and repository context motivate issue-level evaluation.
- [Empirical study of SWE-bench patch correctness](https://arxiv.org/abs/2503.15223) — passing proxy checks do not guarantee behavior matches maintainer intent; supports human review and cautious claims.
