# Citeproof

For the plain-language project overview and end-to-end workflow, see the [Citeproof Project Guide](docs/CITEPROOF_PROJECT_GUIDE.md).
For the hackathon's three-minute demo run-of-show and submission checklist, see [Citeproof Submission Prep](docs/CITEPROOF_SUBMISSION_PLAN.md).
For pinned issue, fix, and contamination notes for all eight examples, see the [curated-case review](docs/CITEPROOF_CASE_REVIEW.md).

## License

Citeproof's project code is licensed under the [MIT License](LICENSE). Third-party dependencies, public issue material, benchmark labels, and any separately supplied assets retain their own licenses and applicable terms.

Citeproof is a local-first prototype for investigating Python bug reports with source evidence. Two independent Muse Glimmer investigations run concurrently with bounded, read-only repository tools. A deterministic checker validates each citation's file, line range, quote, symbol, and whether the cited lines fall within that symbol. When both investigators return checked citations, one additional Muse call skeptically reviews their candidate findings and may suggest a regression-test scenario. It can select only existing finding/evidence IDs, has no repository tools, and cannot add a citation. Evidence overlap and model review do not prove that a diagnosis is correct.

## Hackathon contribution

The Git history begins with the Citeproof MVP commit (`6fd4295`) on October 27, 2026, after the hackathon kickoff on October 26. The project work shown here adds:

- independent parallel investigations with a bounded, no-tools evidence verifier;
- repository path confinement, pinned clean sample commits, and deterministic source-quote and symbol checks;
- explicit incomplete states, request-budget-matched comparisons, and versioned run reports;
- human diagnosis review kept separate from citation checks and file-localization scores; and
- eight curated issue examples across five Python repositories, with contamination and issue-text leakage cautions.

Citeproof helps maintainers inspect source evidence; it does not generate or apply a code fix, execute repository code, or claim a diagnosis is correct.

## Current inference route and cost boundary

This MVP calls `meta/muse-glimmer-30b` through NVIDIA's official API Catalog free endpoint for prototyping. It does **not** call Meta Model API, does not have a paid fallback, and does not change providers when a request fails. NVIDIA's free trial endpoint is rate-limited and availability may vary; when access is unavailable, the run stops with an error. The NVIDIA trial terms limit the endpoint to trial, development, and evaluation use—not production.

Meta's [Muse Glimmer docs](https://dev.meta.ai/docs/muse-glimmer) describe Glimmer as open-weight and list NVIDIA among its launch ecosystem; the [deployment docs](https://dev.meta.ai/docs/muse-glimmer/deploy) cover hosted inference providers. The participant guide supplied for this event says Stage One requires reasonable use of Meta Model API and/or Meta open-weight models, so Citeproof's use of Glimmer fits the stated model category, subject to judging. The guide separately limits its open-weight bonus to participant hardware or partner-provided inference. The co-host's [current Cerebral Valley listing](https://events.cerebralvalley.ai/e/meta-ai-developer-hackathon) names Baseten, Modal, and Fireworks as inference partners, but not NVIDIA API Catalog; do not claim the bonus for Citeproof's current NVIDIA route. [Fireworks' model catalog](https://fireworks.ai/models/fireworks/muse-glimmer-30b) lists Glimmer as available only for on-demand deployment, with serverless unsupported; the event listing currently offers $100 credits only to selected participants. On-demand deployment is billed by GPU-second, so it is not a free fallback unless those credits are actually granted. Fireworks says usage pauses at zero credits when Auto Reload is off, and accounts without a payment method are suspended at depletion ([billing details](https://docs.fireworks.ai/faq-new/billing-pricing/what-happens-when-i-finish-my-1-dollar-credit)). Do not switch or call it until the no-cost credit balance and the accepted Official Rules are verified. Meta's [official hackathon page](https://dev.meta.ai/events/global-hackathon) says selected participants must accept the rules but does not link to their full text.

Generate a free NVIDIA API Catalog key from the [Muse Glimmer model page](https://build.nvidia.com/meta/muse-glimmer-30b). Store it locally in `.env` as `NVIDIA_API_KEY=...`. Never commit `.env`. This code uses only the free endpoint. Do not enable paid services or add a payment method if you need to avoid charges. The endpoint may be rate limited or unavailable; the app stops rather than switching to a paid provider. NVIDIA says trial inputs and outputs may be recorded and used to improve its products, so only send public issue and source text—not secrets or private code.

Put only the key value after `NVIDIA_API_KEY=` in `.env`; do not paste the sample Python snippet there. The app already contains the `OpenAI` client code.

The current app has no paid Meta Model API fallback.

## Run locally

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set NVIDIA_API_KEY. Set CITEPROOF_REPO to a local Python repository folder if desired.
streamlit run app.py
```

In the app, select a local Python repository folder, paste an issue title and description, and click **Investigate with both agents**. Any test scenario is labeled **not run**; Citeproof does not execute repository code or generated tests.

For a no-call presentation path on Click #3449, use **Load cached A/B + live verifier demo · no model call**. The interface labels the investigator pair as cached, rechecks its citations against the pinned checkout, and identifies the verifier review as a separate live call.

The primary **Load Cached Click #3449 Demo · No Model Call** button reloads the original v1 snapshot and rechecks its citations. The current app's v2 export ranks `src/click/termui.py` first, so `hit@1=false` and recall@3 is `0.2`; the v1 file's stored metric said hit@1 was true. The unchanged historical v1 record is preserved, and the rechecked export is [`click-3449-cached-demo-rechecked-20261029.json`](data/benchmarks/click-3449-cached-demo-rechecked-20261029.json). Use that v2 result when narrating the current UI. The diagnosis review remains unreviewed for this particular cached snapshot; the separate live run has a partly-supported human review.

The eight curated cases are public Python issues with separate issue text and gold labels:

| Issue | Pre-fix pin | Use and caution |
| --- | --- | --- |
| [#2877](https://github.com/pallets/click/issues/2877) | `df2e5ed8c4e89f51ff4eddb9600d913083613e62` | Smoke case only: it links to nearby code and suggests a type conversion. |
| [#3449](https://github.com/pallets/click/issues/3449) | `a5f5aa6d4012d256ccca24638f2642fc371e9f77` | Better localization candidate; its fix spans [PR #3482](https://github.com/pallets/click/pull/3482) and [PR #3533](https://github.com/pallets/click/pull/3533). |
| [#2994](https://github.com/pallets/click/issues/2994) | `3c12ce7050bf63c9fa522e5d7b95543037da0f63` | Windows-only `launch(..., locate=True)` bug with paths containing spaces; no implementation path in the report. |
| [#3059](https://github.com/pallets/click/issues/3059) | `8240d25bdbb8c081b745199620b8f2fe03b10579` | CLI help output for groups that allow no subcommand; no implementation path in the report. |
| [HTTPX #2883](https://github.com/encode/httpx/issues/2883) | `3b9060ee1121b48669e0b30045c9344065f4f2ae` | URL query percent-encoding report; historical smoke case only because the issue and fix were public in 2023, with elevated contamination risk. |
| [Pydantic #13957](https://github.com/pydantic/pydantic/issues/13957) | `ca359e009fcfaff2a80df33cb99ee6ab21aaf033` | Python 3.10.0 `ForwardRef` failure; fresh October 2026 report, but the one-file fix has no added regression test file, so use as a smoke case. |
| [sse-starlette #211](https://github.com/sysid/sse-starlette/issues/211) | `6754ef387da97cf6cfbcd1bd5c216b533937b304` | Later SSE streams are cancelled after a server stops; issue text explains the global shutdown flag, so use only as a diagnosis-revealing smoke case. |
| [openai-python #3811](https://github.com/openai/openai-python/issues/3811) | `ae41bc46cdd53d17e948ac8a73e16bdbf34123a1` | Stream read errors escape the SDK exception hierarchy; issue names the streaming module and expected exception types, so use only as a diagnosis-revealing smoke case. |

Four cases come from Click, and one each from HTTPX, Pydantic, sse-starlette, and openai-python. Meta's [Muse Glimmer model card](https://huggingface.co/meta-models/Muse-Glimmer-30B) lists a January 4, 2026 knowledge cutoff. Click #2877, #2994, #3059, and HTTPX #2883 were public before that date, so use them as smoke cases rather than blind-localization evidence. The other four postdate the listed cutoff, but that alone cannot prove the evaluation examples were absent from training or tuning. The new sse-starlette and openai-python issue reports already expose key diagnosis details; they are included to exercise repository diversity, not as blind tests. Eight cases remain too few for broad accuracy claims. Before running curated cases, create or verify clean pinned worktrees with `python scripts/setup_demo_repos.py`. The script provisions all five repositories and refuses to overwrite a checkout that is dirty or at a different commit. Citeproof checks the selected commit and clean state again when each run starts. Gold labels are not included in model prompts. Manual issue inputs do not use curated scores and are not benchmark results.

## Safety and current limits

- The model can only call three allowlisted functions: text search, AST symbol search, and bounded source reads.
- Repository paths are confined to the selected root. Each search scans at most 64 MiB of Python source, skips files larger than 256 KB, caps results at 30, and labels partial scans or capped results.
- Models cannot execute code, run tests, apply patches, or access shell tools. The verifier may describe a test scenario, but it is displayed as **not run** and no test code is executed.
- The verifier gets no repository tools. Its single bounded request sees only the issue and findings with citations that the deterministic checker accepted; its output must use allowlisted finding and evidence IDs. A proposed test is advisory and never implied to have run.
- Issue text and repository contents are untrusted input.
- The current evaluation contains eight curated issues across five repositories. The new sse-starlette and openai-python cases are diagnosis-revealing smoke cases. This set is still too small and too contaminated or leading for broad accuracy claims; diagnosis correctness remains unscored in aggregate.

## Evaluation output

After a completed pair of investigations on a curated case, the app reports a per-case smoke score and can download the run as JSON. `Primary file hit @1` checks whether the highest-ranked verified source file is in the human-curated primary-file labels. `Gold-file recall @3` measures how many of the primary and supporting changed files appear in the top three. A file receives one vote per investigator, and only citations that pass the deterministic checker count. If either investigator fails, Citeproof marks the score incomplete. Completed investigations with no findings remain scored misses, but the shared report contract and UI now label that outcome explicitly; incomplete investigations receive no localization score. Verifier failures are reported separately and do not erase the two investigation results; exports report investigator, verifier, and total model requests separately.

New exports use versioned v2 reports with separate investigation, citation, cross-check, verifier, localization, and human diagnosis-review states. The same report powers the UI and download. Reports include model settings, request counts, and measured phase durations; legacy cached runs keep unknown timings and per-agent request splits as unknown rather than inventing them. A human may record whether a diagnosis is supported, partly supported, unsupported, or incorrect, with a brief evidence-based note. This annotation stays separate from the model's citation checks and file-localization score.

These are file-localization proxies, not diagnosis-accuracy scores. Issue #2877 links to nearby source code and suggests a type conversion; #3449, #2994, and #3059 describe symptoms and APIs without naming the implementation file. #2994 is Windows-specific. HTTPX #2883 is historical and has elevated contamination risk. Pydantic #13957 is fresh but has a narrow one-file fix and no added regression test file. The sse-starlette #211 and openai-python #3811 reports reveal key diagnosis details and are diagnosis-revealing smoke cases. The model card's stated cutoff is January 4, 2026; four issues were public before that date, while later publication does not prove the other cases were excluded from training or tuning. Diagnosis correctness remains unscored in aggregate; one Click #3449 run has a separate partly-supported human review. Four of eight cases still come from one repository, so repeatable baseline comparisons across varied cases remain necessary.

### Request-budget-matched single-agent control

The comparison runner calls the same two investigators concurrently, then makes at most one bounded verifier request when both investigators have checked citations. It gives one neutral investigator a hard limit equal to the pair's total observed requests, including the verifier request. It records whether the single run actually used the same number of requests; an early answer or an error is reported as an incomplete comparison. A clean repository at the pinned pre-fix commit is required, and issue text and gold labels are loaded separately. Gold labels are used only for scoring and are omitted from the report. Request-count equality does not establish equal token use or diagnosis quality.

Run a comparison from the repository root:

```powershell
.\.venv312\Scripts\python.exe -m citeproof.benchmark `
  --repo .\demo_repos\click-3449-full `
  --issue .\data\issues\click-3449.json `
  --gold .\data\gold\click-3449.json `
  --output .\data\benchmarks\click-3449-budget-comparison.json
```

The CLI reads `NVIDIA_API_KEY` from `.env`, uses the existing NVIDIA API Catalog route only, and writes a report even when a provider failure makes the run incomplete. It does not configure a paid fallback.

For bounded wait time, both independent investigators run concurrently with a four-minute wall-clock budget each, so their combined stage is capped at about four minutes. The optional verifier adds at most one request capped at two minutes; the full workflow is therefore bounded at about six minutes, plus brief local setup. Request completion times appear in the live progress trace. A timeout or exhausted budget marks that investigator incomplete; verification is skipped unless both agents finish with checked citations. Each investigator may make one final correction request for malformed JSON, an empty answer after reading source, or citations rejected by the source checker.

Muse Glimmer is called with low reasoning effort and a sampled temperature of 0.95. Its API counts reasoning tokens and answer tokens against the same output limit, so each request allows up to 8,192 tokens while relying on the wall-clock cap to bound long generations. These settings follow [NVIDIA's Muse Glimmer API guidance](https://docs.api.nvidia.com/nim/reference/meta-muse-glimmer-30b-infer).

Live checks on Click #3449 are mixed and remain one-case evidence. A live pair-plus-verifier run completed in **79.7 seconds** with 9 investigator requests and 1 verifier request. It had overlapping checked evidence and returned a verifier assessment, but ranked `src/click/termui.py` above the primary changed file (`hit@1=false`, `recall@3=0.2`). A later human review of that run marked the diagnosis **partly supported**: it found the pager cleanup path but missed that finalization of a temporary `TextIOWrapper` closed borrowed stdout. The original v1 report remains unchanged; the review is preserved in a separate v2 export at `data/benchmarks/click-3449-live-final-symbol-lookup-human-review-20261029.json`.

An earlier budget-matched check is `data/benchmarks/click-3449-quality-gates-v2-20261029.json`. It took **88.312 seconds**: the pair and baseline each used 10 requests. Investigator A returned no finding, so cross-checking and verification were unavailable; the baseline exhausted its request budget after a malformed final response and correction, so the comparison is correctly marked **incomplete**. A prior 11-vs-11 run completed with recall@3 `0.2` for both paths and verifier assessment `insufficient_evidence` (`data/benchmarks/click-3449-live-quality-gates-comparison-20261029.json`).

The latest reserved-correction comparison, `data/benchmarks/click-3449-reserved-correction-20261029.json`, completed in **133.109 seconds** with 10 requests per path. Both pair investigators and the baseline returned zero findings; both localization scores are valid scored misses (`hit@1=false`, recall@3 `0.0`). The saved traces show the investigators read the public pager path but did not return a file hypothesis. Citeproof now marks this outcome explicitly in the report and UI while keeping the zero score. The findings remain one-case evidence and none of these runs score diagnosis correctness.

The post-follow rerun, `data/benchmarks/click-3449-post-follow-quality-20261029.json`, timed out both investigators' first NVIDIA requests after **122.468 seconds**; no baseline ran and localization was not scored. This is an availability failure, not a model-quality result. The code-level auto-follow test on the clean pinned checkout does include the nested `_termui_impl.py` helpers and `MaybeStripAnsi(io.TextIOWrapper)`, but the live model route did not stay available long enough to measure a localization effect.

An additional run used the clean, pinned Pydantic #13957 pre-fix checkout (`data/benchmarks/pydantic-13957-quality-gates-20261029.json`). Both investigators' first requests timed out after about **121.7 seconds total**; no baseline ran, request counts did not match, and localization was left unscored. This is an incomplete availability observation, not a model-quality result. Pydantic #13957 remains a narrow smoke case, not evidence of generalization.

A separate live verifier request took **16.4 seconds** against a cached investigator pair whose citations were rechecked against the pinned checkout. It is a cached-pair/live-review demonstration, not a live end-to-end run (`data/benchmarks/click-3449-live-citation-aligned-cached-review-20261029.json`). An earlier seeded pair took 236.7 seconds and its verifier timed out; this failure remains part of the reliability record. New reports use versioned schemas and preserve unknown cached timings as null. The earlier complete A/B snapshot is at `data/demo_runs/citeproof-pallets-click-3449-complete.json`.

The interface uses `streamlit-shadcn-ui` 1.4.0 (MIT) for selected status and evaluation components, with Streamlit 1.60 or newer.
