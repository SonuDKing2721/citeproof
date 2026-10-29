# Citeproof Related Work and Evidence Quality Design

**Date:** 2026-10-29  
**Status:** Draft for participant review  
**Scope:** A source-backed comparison of related tools and a deterministic improvement to citation adjudication and localization evaluation.

## Goal

Compare the projects and papers in `Citeproof_Related_Projects_and_Improvements.md` with the current local Citeproof tree, correct claims that have changed or do not match their cited sources, and turn the strongest relevant ideas into reviewable improvements. The work must stay within the user's zero-money constraint, make no inference calls, copy no third-party code, and keep source-citation validity separate from diagnosis correctness.

## User-approved direction

- Complete and document a primary-source comparison before resuming demo production.
- Review every project and paper named in the supplied note; give deeper treatment to direct localization and code-evidence peers.
- Implement the evidence improvements in small, reviewable phases after the design and implementation plan are approved.
- Do not use peer bug-fix percentages as Citeproof localization scores, and do not claim that a valid citation proves a diagnosis.

## Work phases

### 1. Comparative review

Create `docs/RELATED_WORK_AND_GAP_REVIEW.md` and link it from the README. Compare the local checkout, not only the older pushed snapshot. Cover every listed repository, paper, package, and model/provider pattern. For each source, identify its task, evidence, limitations, relevance, and any useful design lesson. Prefer maintainer documentation, official repository files, paper text, or package metadata. Label self-reported performance as self-reported and omit volatile star counts from project claims.

The review must correct the attached note where current evidence requires it, including the current eight-case/five-repository inventory, the existing request-matched single-agent baseline and cached traces, the small amount of multi-case live evidence, the scope of the cited code-comprehension paper's results, and the current public status and stated origin of code-archaeologist. Keep the note's valid distinctions: repair benchmarks do not measure localization, and human diagnosis review is not interchangeable with citation checking.

### 2. Deterministic citation adjudication

Extend the checker/report contract with this stable outcome vocabulary: `verified_exact`, `corrected_unique_exact_quote`, `path_missing`, `path_outside_repo`, `path_unreadable`, `invalid_range`, `range_too_wide`, `empty_quote`, `quote_not_found`, `quote_match_ambiguous`, `symbol_not_found`, and `symbol_range_mismatch`. If an exact quote occurs uniquely elsewhere in the same file, the checker may correct its range regardless of offset only when the corrected citation still passes all path and symbol checks. Ambiguous matches remain rejected. Preserve both the model-claimed and corrected ranges in structured fields; do not rely on parsing a human-readable reason string.

Show each finding's citation state in the UI and export. A finding with no surviving verified citation must be labeled as having no checked source support; this is not a verdict that its diagnosis is false. Keep the quoted text, failed reason, and repair provenance visible. Do not add fuzzy matching, semantic quote normalization, or a minimum quote-length rejection rule in this phase; the present evidence does not establish a threshold that is both useful and low-risk.

Use the summary states `no_citations`, `none_verified`, `partly_verified`, and `all_verified`. These describe source-string checks only and must not be named or styled as diagnosis-verdict states.

### 3. Per-investigator localization metrics

Retain the current pair-level metrics and add per-investigator rankings and scores so the aggregate does not hide disagreement. Define the rank source explicitly in the agent response contract: findings are ordered from most to least plausible location. For each investigator, include only unique files with checked citations in that order; report primary-file hit@1, primary-file reciprocal rank, and gold-file recall@3. Keep pair aggregation and single-agent results distinct. These remain file-localization proxies; do not add an aggregate diagnosis-correctness score without independent human reviews across distinct cases.

For reciprocal rank, use the first ranked file in the gold primary-file set (`1 / rank`); report `0` when no primary file is ranked and `null` for an incomplete investigation.

Existing historical reports without an explicit ranking contract remain unchanged and must not be relabeled as if they were produced under the new prompt. New reports use `citeproof-evaluation/v3`, state the ranking method, and keep v1/v2 reports loadable without rewriting their provenance.

## Data flow and boundaries

Model findings pass through the existing local source checker. The checker assigns typed citation outcomes, safely relocates only a unique exact quote that passes the same file and symbol checks, and preserves its input location. The presentation layer renders each outcome without deleting the model's original claim. The export layer writes the typed citation outcomes and per-agent localization metrics. No checker or metric calls a model, contacts a provider, or executes repository code.

Gold labels remain separate from prompts. Missing, ambiguous, or malformed data fails closed as unverified or incomplete. A human diagnosis review continues to be a separate annotation; repeated reports of Click #3449 count as one reviewed case, not multiple independent labels.

## Validation and acceptance criteria

- The related-work review covers all sources in the participant's note and links to the exact primary sources used for its claims.
- It compares against the current local implementation, including eight curated cases, the budget-matched baseline, pinned checkout checks, cached traces, and the actual limitations of available outcome data.
- Unique exact-quote relocation is deterministic, records claimed and corrected ranges, and refuses ambiguous or symbol-inconsistent matches.
- Every citation outcome has a stable code and a clear explanation in both the UI and the saved report.
- A finding with no valid citation is described as unverified by checked citations, never as a false diagnosis.
- Per-investigator scores use an explicit rank contract and do not change historical report values or provenance.
- Unit tests cover outcome categories, unique and ambiguous relocation, symbol/path constraints, per-agent ranking, and old-report compatibility.
- No paid route, model call, external upload, or third-party code copy is introduced.

## Deferred work

Do not start a retrieval overhaul with embeddings or a code graph in this phase. Its cost and evaluation burden are not justified by the current small, mostly single-issue live evidence set. Do not resume video capture until this comparison and the first evidence-quality improvement are reviewed; the already-approved demo design remains a separate deliverable afterward.
