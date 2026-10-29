# Citeproof Related Work Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a source-backed comparison of every project, paper, package, and model/provider route in the user's note against the current local Citeproof implementation.

**Architecture:** Keep this as an evidence-led Markdown artifact with direct links to primary sources and a compact README entry point. Separate each source's task and reported evidence from Citeproof's measurements; distinguish localization, repair, citation validity, and diagnosis correctness.

**Tech Stack:** Markdown, GitHub/official documentation/arXiv/PyPI source review.

---

### Task 1: Verify the comparison ledger against current sources

**Files:**
- Read: `Citeproof_Related_Projects_and_Improvements.md` supplied in `C:\Users\SHRAVAN KUMAR\Downloads`
- Read: `citeproof/cases.py`, `citeproof/checker.py`, `citeproof/evaluation.py`, `citeproof/benchmark.py`, `citeproof/presentation.py`, `citeproof/orchestration.py`, `README.md`
- Create: `docs/RELATED_WORK_AND_GAP_REVIEW.md`

- [ ] Enumerate all entries and claims in the supplied note: SWE-agent, mini-SWE-agent, Agentless, Agentless Mini/swe-rl, OpenHands, Aider, Cline, the code-comprehension paper, code-archaeologist, citefact, source-distiller, report-workflow, and the Vaquill verification pattern. Add the actual model/provider routes discussed in the note as a separate route comparison.
- [ ] For each repository, paper, package, or route, record the task it addresses, the primary evidence for any performance claim, the limit of that evidence, the relevance to Citeproof, and one design lesson. Link the exact maintainer page, paper, repository file, or package page supporting each factual statement.
- [ ] Reconcile the comparison with the current checkout: eight curated issues across five repositories; existing request-budget-matched single-agent baseline; pinned clean checkout checks; cached traces; current checker scope; and the small live evidence set. State that the cached Click #3449 review is one distinct human-reviewed case even when exported more than once.
- [ ] Correct stale or overstated note claims. In particular, distinguish bug fixing from file localization; state the paper's actual sample and what its 100% figure measures; describe code-archaeologist's current public repository and its stated IBM Bob origin; and label repository/model performance claims as self-reported unless independently verified.
- [ ] Explain where Citeproof's evidence ends: a checked quote supports that source text and location, not a root-cause diagnosis. Do not claim checker novelty, independence from agent agreement, causal correctness, or event-bonus eligibility without evidence.

### Task 2: Publish and surface the comparison

**Files:**
- Modify: `docs/RELATED_WORK_AND_GAP_REVIEW.md`
- Modify: `README.md`

- [ ] Organize the report into a source table, deeper direct-peer analysis (Agentless, Agentless Mini, code-archaeologist, and the citation-grounded code paper), current-state comparison, lessons selected for implementation, and unresolved evidence gaps.
- [ ] Add a short `Related work and evaluation limits` link under the README's existing evaluation section. The link must point to `docs/RELATED_WORK_AND_GAP_REVIEW.md`; do not paste a performance table into the README.
- [ ] Check that every source named in the supplied note appears in the report and each external factual claim has a nearby direct source link. Remove unsupported star counts and stale volatile metrics.
- [ ] Run `git diff --check` and inspect the rendered Markdown links. This documentation-only task does not run application tests.

### Task 3: Review the report against the source note

**Files:**
- Review: `docs/RELATED_WORK_AND_GAP_REVIEW.md`
- Review: `README.md`

- [ ] Compare the report's source inventory line by line with the supplied note.
- [ ] Verify that localization, citation correctness, human diagnosis review, and bug-fix success remain separate throughout the report.
- [ ] Confirm that every numeric claim is scoped to its cited dataset and task, and that the report makes no claim that a verified citation proves a diagnosis.
- [ ] Commit the report and README link together as `docs: compare Citeproof with related tools and research`.
