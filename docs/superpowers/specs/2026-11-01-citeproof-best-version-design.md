# Citeproof Product and UI Design

## Goal

Make Citeproof dependable when inference is slow, make each source citation easy to inspect, and keep evaluation reports honest and reproducible. Keep the current Python and Streamlit stack, the read-only repository boundary, and the single configured Muse Glimmer route.

## Current-state audit

| Area | Already present | Gap from the requested design |
| --- | --- | --- |
| Citation integrity | Path confinement, bounded files and ranges, exact quote checks, unique quote range correction, AST symbol containment, typed rejection outcomes | No minimum quote-quality rule; no diagnostic for missing backticked identifiers or failed quotes repeated in explanations |
| Investigation hints | Issue traceback clues and a reproducer API hint are included in prompts | No deterministic source search for the error text or traceback filenames before inference |
| Run accounting | Per-agent request counts, bounded time budgets, phase timings, and saved JSON reports | No endpoint readiness check, bounded transient backoff, generic same-issue saved-run fallback, or compact request/time summary at the top of results |
| Results UI | Cached Click replay, A/B evidence comparison, reviewer form, per-agent localization rows, responsive CSS, and visible focus styles | Results are a long sequence of sections; evidence is shown as bare quoted blocks; verdicts use emoji; no Findings/Compare/Trace/Report tabs, source-line viewer, trace replay, or issue-comment export |
| Trace | Tool-call strings are retained in investigator results | Tool result summaries are not retained, so the UI cannot replay a useful saved trace |
| Evaluation | Versioned JSON reports, human diagnosis labels, and a matched single-agent baseline | README tables are hand-maintained; no blind comparison review or runnable report-generation command |
| Safety and delivery | Repository traversal is constrained and tests cover basic outside-root paths | Add explicit prompt-injection and symlink tests, verify escaping in the custom evidence panel, and add CI |

## Product design

### Run reliability

- Before a live run, send one small readiness request with a 15-second timeout. Show `Ready`, `Slow`, or `Unavailable`; do not ping on ordinary Streamlit reruns.
- Retry transient connection, timeout, rate-limit, and server errors after 5, 15, and 30 seconds. Never retry a bad request. Every attempt counts against the existing request and wall-clock budgets and is shown separately from successful completions.
- If readiness fails or an investigation times out, offer a same-issue saved report. Load it only against its pinned repository commit and label it cached; recheck citations on load.
- Before inference, search bounded repository text for the issue's exception/error phrase and list paths matching traceback filenames. Pass these results as untrusted source hints. Do not execute issue or repository code.
- Show readiness, request attempts, retries, and measured phase durations in a compact run summary.

### Evidence checking and review

- Keep citation outcomes deterministic and separate from diagnosis correctness.
- Reject trivial quotes such as `pass` and `return x` with a distinct outcome.
- Inspect backticked identifiers in each explanation against repository paths and AST symbols. Report unresolved names as diagnostics; do not turn them into a diagnosis verdict.
- Flag a failed citation quote repeated in the explanation as an unverified-quote leak.
- Preserve claimed and corrected line ranges and symbol containment behavior.

### Results UI

- Retain Streamlit. Use native tabs named Findings, Compare, Trace, and Report.
- Make the evidence viewer the primary surface. Show path and symbol above numbered source lines; highlight the checked range; label it `Verified`, `Corrected`, or `Rejected` in text and shape as well as color. For corrected ranges, show claimed and actual lines. For rejected quotes, show the requested quote beside the relevant file text or a clear missing-path state.
- Replace the long status paragraphs with one status line and a `How to read this` popover. Keep the sentence: “A verified citation proves the quote exists, not that the diagnosis is right.”
- Put investigator findings side by side in Compare with their ranked files and checked-citation outcomes.
- Store bounded trace events containing the tool name, sanitized request summary, and a safe result summary. Do not persist raw repository excerpts in trace events. Add one slider to replay these saved events; older reports show that trace results were not stored.
- In Report, keep the human review, JSON download, and an issue-comment Markdown block with source links at the pinned commit. Use Streamlit's built-in code copy control.
- Split explanations into sentences and show deterministic citation anchors where text explicitly overlaps a quoted identifier or symbol. Label sentences without an anchor `No direct citation anchor`; never imply that string overlap proves entailment.

### Visual and accessibility direction

- Cool light-gray canvas `#F6F8FA`, white panels, ink `#1B2330`, border `#D3D9E0`, teal verified `#0F6E6E`, amber corrected `#B7791F`, brick rejected `#B3382C`, and pale teal source highlight `#E8F1F1`.
- Use a flat, compact layout with 4px panel corners and no shadows or entrance animations. Load Atkinson Hyperlegible Next and Spline Sans Mono with local fallbacks.
- Preserve keyboard focus, text labels for every status, contrast, reduced-motion behavior, and a narrow-window layout.
- Escape every repository and issue value before inserting it into custom HTML. Keep HTML rendering isolated to the evidence viewer; use normal Streamlit text APIs elsewhere.

### Evaluation, safety, and commands

- Add `python -m citeproof.bench --case <id>` for a bounded run on one curated case and `python -m citeproof.report` for generating Markdown tables from saved JSON reports.
- Mark generated table sections in README and the related-work report so the generator owns only those blocks. Use counts for small samples; do not turn one-case outcomes into percentages.
- Add an optional blind review flow for a saved pair-versus-single comparison. Shuffle presentation order, hide the mapping until a label and note are saved, then reveal it. Preserve existing non-blind annotations as historical labels.
- Add hostile issue-text and symlink/path-traversal tests, then run the existing suite in GitHub Actions.

## Architecture and data flow

Keep orchestration, model calls, repository access, checking, and evaluation in the existing `citeproof` modules. Add small focused helpers for safe UI rendering and report generation instead of replacing Streamlit. New trace data contains summaries only. Additive report fields use a new evaluation schema version, and all prior report schemas continue to load with explicit “not stored” states.

The live sequence is: bounded readiness check → deterministic repository pre-seed → two independent investigators → citation checks and diagnostics → optional evidence review → versioned report. Retries share the same explicit request and wall-clock budgets. Saved fallback never calls a model.

## Implementation slices

1. **Run reliability:** preflight status, transient backoff, pre-seeding, generic cached fallback, and visible budgets.
2. **Evidence quality and UI:** quote/identifier/leak diagnostics, safe source panels, tabs, sentence anchors, trace replay, and issue-comment output.
3. **Evaluation and safety:** report generator and CLI, blind review, prompt-injection and symlink coverage, and CI.

## Non-goals

No new model provider, paid fallback, repository write access, issue-code execution, generated fix, auto-fix, or UI animation. Citation verification remains distinct from diagnosis review and does not become an automated truth score.
