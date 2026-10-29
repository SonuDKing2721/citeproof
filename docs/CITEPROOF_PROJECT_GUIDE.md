# Citeproof Project Guide

## 1. What Citeproof is

Citeproof is a small AI tool for helping maintainers investigate Python bug reports. A user gives it a public issue and a local copy of the affected repository. Two AI investigators search the code independently and concurrently; Citeproof checks their source quotes, then may ask one no-tools verifier to review only accepted evidence.

The main idea is **evidence before confidence**: the app should show which files and lines support an answer, and make unsupported claims visible.

## 2. The problem it addresses

When a bug report arrives, a maintainer often has to locate the relevant code, follow the behavior across files, and decide what to test. General chat answers can sound convincing while pointing to the wrong file or inventing code.

Citeproof aims to make that investigation easier by:

- searching the repository with small, read-only tools;
- asking two investigators to take different starting approaches;
- checking each citation against the checked-out source; and
- showing where the investigators' verified evidence overlaps; and
- optionally asking a verifier to compare supported findings and suggest an unrun regression-test scenario.

The first intended users are open-source maintainers working on Python projects.

## 3. What the user sees

1. Choose a curated example or enter an issue manually.
2. Select the local repository folder.
3. Read or edit the issue title and report.
4. Start the two-agent investigation.
5. Review each agent's explanation and citations.
6. See verified source overlap, if any, and a bounded verifier assessment when both investigators returned checked citations.
7. Review an optional regression-test suggestion marked **not run**.
8. For a curated case, view a small file-localization score and download a JSON run report.

For a no-call presentation on Click #3449, the sidebar also offers **Load cached A/B + live verifier demo**. It rechecks the saved investigator citations against the pinned repository and labels the older pair and separate live verifier call with their timestamps.

If either agent fails, Citeproof marks the run incomplete and does not show a score based on only one agent.

## 4. System design

```text
Issue report + local repository
              |
       Streamlit interface
          /          \
 symptom-first      structure-first
 investigator       investigator
          \          /
       read-only repository tools
              |
       deterministic citation checker
              |
      no-tools verifier (if eligible)
              |
 evidence comparison + optional case score
              |
       results and JSON report
```

### Main parts of the code

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit interface, case selection, progress display, and result review. |
| `citeproof/agent.py` | Calls Muse Glimmer, directs each investigation, and runs the allowlisted tools. |
| `citeproof/orchestration.py` | Runs independent investigations concurrently and relays progress on Streamlit's main thread. |
| `citeproof/repo.py` | Searches Python files, finds symbols, reads bounded ranges, and confines reads to the chosen repository. |
| `citeproof/checker.py` | Checks that a citation's file, line range, quote, and optional symbol match the source. |
| `citeproof/comparison.py` | Compares the two agents' verified files and line ranges. |
| `citeproof/verifier.py` | Makes one optional, no-tools review limited to checked findings and allowlisted evidence IDs. |
| `citeproof/evaluation.py` | Calculates small localization metrics and builds JSON run reports. |
| `citeproof/presentation.py` | Prepares citation labels and keeps results available across Streamlit reruns. |
| `data/issues/` | Curated issue reports sent to the investigators. |
| `data/gold/` | Private-to-the-agents evaluation labels based on maintainer fixes. |
| `tests/` | Unit tests for repository safety, citation checking, agents, and evaluation helpers. |

## 5. Investigation workflow

### A. The two investigations

- **Investigator A (symptom-first)** starts by searching for an error message or distinctive text from the report.
- **Investigator B (structure-first)** starts by finding likely functions or classes. When the issue includes a Python reproducer, Citeproof safely parses imported call names and seeds this first search with the first public-looking API call; names imported from test-harness modules are excluded. The example is parsed as syntax and never executed. If no safe name is found, the model chooses a symbol search as before.
- Each call has its own conversation. One investigator's findings are not passed to the other.
- The calls run concurrently, but neither investigator receives the other's output.
- Each investigator gets at most three tool rounds and a final synthesis request. In practice, this is up to four API completions, plus one bounded correction for malformed JSON, no findings after source was read, or citations the source checker rejected.
- Each model request is capped at two minutes, and each investigator has a four-minute wall-clock budget. Because they run concurrently, the investigation stage is capped at about four minutes; live progress reports each request's time.
- If a request times out or an investigator exhausts its time budget, that investigator is incomplete and the pair receives no localization score.
- The first round starts with a different forced tool for each investigator. The final tool round is restricted to `read_file`, so the answer has a chance to inspect actual source lines before it cites them.
- The diagnostic prompt treats `ValueError` about a closed file as a clue to inspect stream ownership and lifetime, including wrappers that might close borrowed streams. This is guidance for investigation, not a diagnosis rule.

### B. Repository tools

The model can request only these tools:

- `search_text`: search Python source for a literal phrase;
- `find_symbols`: find Python functions, async functions, or classes by name; and
- `read_file`: read a limited line range from one file.

Each search scans at most 64 MiB of Python source, skips individual files over 256 KB, inspects no more than 5,000 files, and returns at most 30 matches. Search tools label capped results and mark scans incomplete when a scan limit excludes source; the model should treat partial evidence cautiously.

The investigators cannot run shell commands, execute repository code, or edit files. The verifier may suggest a test scenario in plain text, but Citeproof does not create test code or execute tests. Paths are checked to stay inside the selected repository. Search results, file size, and read ranges are limited.

### C. Citation checking

After an investigator answers, Citeproof checks each citation in deterministic Python code. A citation passes only if:

- the file exists inside the selected repository;
- the line range is valid and within the size limit;
- the quoted text appears in that range; and
- if a symbol is named, it exists and contains the cited lines.

This proves that the source quote is real. It **does not** prove that the explanation is the right diagnosis.

### D. Cross-checking

Citeproof compares only citations that passed the checker. It reports shared files and overlapping line ranges. Overlap is useful corroboration of where to look, but it does not mean the two agents independently proved the same cause.

### E. Skeptical evidence review

- If either investigator fails, or either returns no source-checked citation, the verifier is skipped without spending a request.
- Otherwise, Muse Glimmer gets one extra request with the issue, candidate claims, and only citations accepted by the deterministic checker. The verifier has no repository tools.
- It can select only an existing finding ID and evidence IDs already supplied. Citeproof rejects unknown IDs or malformed results; a failed review leaves both investigator results visible.
- Its assessment is still model output, not ground truth. Any regression-test suggestion is explicitly marked **not run** and must be reviewed and executed by a maintainer.

## 6. Model and service

- Model: **Meta Muse Glimmer 30B**, model ID `meta/muse-glimmer-30b`.
- Current inference route: **NVIDIA API Catalog**, through its OpenAI-compatible API.
- The model is the reasoning and tool-selection component; repository access is implemented by Citeproof's local Python tools.
- The current app does not call Meta Model API and does not switch to a paid provider if NVIDIA is unavailable; provider failure is reported as an incomplete run.
- Investigator requests use low reasoning effort, temperature 0.95, top-p 1.0, and up to 8,192 output tokens. The verifier gets one request with a smaller output budget and a 120-second timeout. NVIDIA says Muse Glimmer shares that token budget between reasoning and the final answer. The model-call stages are bounded at about four minutes for the concurrent investigations plus up to two minutes for verification. See [NVIDIA's Muse Glimmer API reference](https://docs.api.nvidia.com/nim/reference/meta-muse-glimmer-30b-infer).
- NVIDIA trial service access can be intermittent and rate-limited. The app reports an incomplete run rather than inventing a successful result.
- Research-only exact-model candidates: Routeway lists `muse-glimmer-30b:free` at $0 and 200 free requests/day, with an OpenAI-compatible endpoint at `https://api.routeway.ai/v1`; however, the signup/payment-method requirement and serving upstream are unclear, no Routeway key is configured, and this project has not called it. Requesty lists `nvidia/muse-glimmer-30b` at $0 and 200 free requests/day without a payment method, but routes to NVIDIA and therefore is not known to fix the observed upstream timeouts. Requesty's free-plan terms allow training/improvement use of request content; send public issue/source material only. Neither gateway is a named event partner, so do not claim the open-weight bonus for either. Vercel AI Gateway also lists a $5 monthly free-credit allowance for Muse Glimmer via Together, but it is a bounded credit pool rather than a zero-priced model. See [`CITEPROOF_INFERENCE_ROUTE_RESEARCH.md`](CITEPROOF_INFERENCE_ROUTE_RESEARCH.md). These alternatives have not been configured or called.
- Only public issue text and public repository code should be sent to the service. Do not submit secrets or private code.

The co-host's [current Cerebral Valley listing](https://events.cerebralvalley.ai/e/meta-ai-developer-hackathon) names Baseten, Modal, and Fireworks as inference partners for Meta open-weight models, but not NVIDIA API Catalog; do not claim the open-weight bonus for the current NVIDIA route. The [Fireworks model catalog](https://fireworks.ai/models/fireworks/muse-glimmer-30b) lists Glimmer as available only on demand and says serverless is unsupported. On-demand deployment is billed by GPU-second. The current event listing offers $100 credits only to selected participants, so Fireworks is not a no-cost fallback unless a credit is actually granted. Fireworks' [billing documentation](https://docs.fireworks.ai/faq-new/billing-pricing/what-happens-when-i-finish-my-1-dollar-credit) says usage pauses at depletion with Auto Reload off and accounts without a payment method suspend. Do not switch or run inference until no-cost credits are verified and paid billing remains disabled. Meta's [official hackathon page](https://dev.meta.ai/events/global-hackathon) still says Official Rules will be published before Oct. 26 and does not link their full text; Cerebral Valley's [current event Markdown](https://cerebralvalley.ai/e/meta-ai-developer-hackathon.md) says registration is closed. The accepted rules may be available only to selected participants in the portal; final bonus eligibility remains unverified until the accepted rules or an organizer confirms the exact route.

## 7. Curated examples and evaluation

The app currently includes eight curated examples across five Python repositories:

| Issue | What it reports | Evaluation caution |
| --- | --- | --- |
| [Click #2877](https://github.com/pallets/click/issues/2877) | A `BytesWarning` from comparing `bytes` and `str`. | The issue points near the relevant source and suggests a type conversion. It predates the model card's stated cutoff, so this is a smoke test, not blind-localization evidence. |
| [Click #3449](https://github.com/pallets/click/issues/3449) | `CliRunner` fails after `echo_via_pager` with “I/O operation on closed file.” | The final fix was split across [PR #3482](https://github.com/pallets/click/pull/3482) and [PR #3533](https://github.com/pallets/click/pull/3533). Labels combine both PRs; treat it as one small case, not a broad benchmark. |
| [Click #2994](https://github.com/pallets/click/issues/2994) | `click.launch(..., locate=True)` opens the wrong folder when a Windows path contains spaces. | The report names the API and platform but not the implementation file. This is Windows-specific; its PR changes one source line and adds no regression test. It predates the model card's stated cutoff. |
| [Click #3059](https://github.com/pallets/click/issues/3059) | Help output makes a subcommand appear required even when `invoke_without_command=True`. | The report names the option and expected usage, but no implementation file. The fix adds tests and documentation as well as a source change. It predates the model card's stated cutoff. |
| [HTTPX #2883](https://github.com/encode/httpx/issues/2883) | A query value containing `application/pdf` is percent-encoded as `application%2Fpdf`. | The report gives an example but no implementation path. The issue and fix were public in 2023, so this is a historical smoke case with elevated contamination risk, not blind-localization evidence. |
| [Pydantic #13957](https://github.com/pydantic/pydantic/issues/13957) | Pydantic 2.14.0 raises a `ForwardRef` `TypeError` on Python 3.10.0. | The issue does not name the source file and was fixed the next day in October 2026. The one-file fix adds no regression test file. The issue postdates the model card's stated cutoff, but use it as a smoke case rather than claiming contamination-free evaluation. |
| [sse-starlette #211](https://github.com/sysid/sse-starlette/issues/211) | Later SSE streams are cancelled after one uvicorn server stops in a long-lived process. | The issue names the global shutdown flag and explains the state leak. PR [#212](https://github.com/sysid/sse-starlette/pull/212) merged the fix. This is diagnosis-revealing smoke coverage, not blind-localization evidence. |
| [openai-python #3811](https://github.com/openai/openai-python/issues/3811) | Mid-stream transport errors escape as raw HTTPX exceptions instead of SDK API errors. | The report names the streaming module and expected exception types. PR [#3827](https://github.com/openai/openai-python/pull/3827) merged the fix; it normalizes errors but does not retry a partially consumed stream. This is diagnosis-revealing smoke coverage, not blind-localization evidence. |

Four examples come from Click, and one each from HTTPX, Pydantic, sse-starlette, and openai-python. The eight-case set is still too small and partly diagnosis-revealing, so it cannot support broad accuracy claims. Meta's [Muse Glimmer model card](https://huggingface.co/meta-models/Muse-Glimmer-30B) lists a January 4, 2026 knowledge cutoff. Click #2877, #2994, #3059, and HTTPX #2883 were public before that date; treat them as contamination-risk smoke cases. Click #3449, Pydantic #13957, sse-starlette #211, and openai-python #3811 postdate the listed cutoff, but later publication alone cannot establish whether an example appeared in training or tuning. The last two issues disclose important diagnosis details and are explicitly marked as diagnosis-revealing smoke cases. For every curated case, Citeproof checks that the repository is at the exact pinned pre-fix commit and has no local changes. Gold labels are stored separately from the issue prompt so they are not shown to the model.

The score currently reports:

- **Primary file hit @1:** did the highest-ranked cited file match the main changed file?
- **Gold-file recall @3:** what share of the curated changed files appeared among the three highest-ranked files?

Files gain support when both investigators cite them with valid citations. These are **file-location proxies**, not diagnosis-accuracy scores. A completed run is not enough to claim the system is generally accurate. A stronger evaluation still needs more varied issues, repeatable single-investigator comparisons across cases, and human review of diagnosis correctness.

New exports use `citeproof-evaluation/v2` and store a shared status contract for the app and downloaded report. It separates investigation completion, citation validation, cross-checking, verifier state, localization status, and human diagnosis review. It also records workflow kind, original run time, effective model settings, request totals, and measured stage durations. Cached v1 reports remain readable; if an old report did not record timing or per-agent request counts, the new export keeps those values unknown. An optional human review can record supported, partly supported, unsupported, or incorrect with a short reason. It does not change citation validation or localization metrics.

Current live evidence is mixed and limited to individual smoke cases. On Click #3449, a pair-plus-verifier run completed in 79.7 seconds with 9 investigator requests and 1 verifier request; the pair had overlapping checked evidence, but ranked `src/click/termui.py` above the primary changed file (`hit@1=false`, recall@3 `0.2`). A human review of this run marked the diagnosis **partly supported**: it found the pager cleanup path but missed that finalization of a temporary `TextIOWrapper` closed borrowed stdout. The reviewed v2 export is `data/benchmarks/click-3449-live-final-symbol-lookup-human-review-20261029.json`; the original v1 report is unchanged. Reopening the original cached Click #3449 A/B report in the current UI rechecks citations and recalculates metrics: the new [`click-3449-cached-demo-rechecked-20261029.json`](../data/benchmarks/click-3449-cached-demo-rechecked-20261029.json) ranks `src/click/termui.py` first (`hit@1=false`, recall@3 `0.2`), while the historical v1 report stored `hit@1=true`. Both records are preserved; use the rechecked v2 report for current claims. The cached snapshot remains not human-reviewed. A separate cached-pair/live-review request took 16.4 seconds and is labeled as such in the app. The 88.312-second v2 budget comparison matched 10 requests per path but was incomplete: the pair had one empty investigator and the baseline exhausted its budget after malformed output. The 133.109-second reserved-correction comparison completed with 10 requests per path, but both pair and baseline returned no findings; each valid localization result was `hit@1=false`, recall@3 `0.0`. The report and UI now identify this as a completed no-findings miss, separately from an incomplete investigation. A post-follow rerun timed out both investigators' first NVIDIA requests after 122.468 seconds, with no baseline and no localization score; this is an availability failure, not a score. Local tests on the pinned source confirm the extended two-hop source trace includes the nested pager implementation and `MaybeStripAnsi(io.TextIOWrapper)`, but the timed-out live run cannot show a model-quality change. All Click runs remain one-case evidence. An additional Pydantic #13957 comparison timed out both investigators' first requests after 121.7 seconds total; no baseline ran and localization was not scored. A later minimal 8-token endpoint health request timed out after 24.9 seconds without sending issue or repository text. One human review does not establish aggregate diagnosis accuracy. See the exact reports in `data/benchmarks/`; none justify broad accuracy claims.

## 8. How the project fits the judging rubric

The participant-guide summary supplied for this project describes Stage 1 as a pass/fail theme and Meta-model fit check, Stage 2 as four equally weighted categories (25% each), and Stage 3 as the top five projects in each track advancing to a final round. Treat this as planning guidance until it can be checked against the participant's accepted Official Rules. The mapping below is evidence Citeproof can show, not a prediction of a score or award.

| Stage 2 category (weight) | What the demo can show | Current proof gap |
| --- | --- | --- |
| Impact (25%) | A workflow for open-source maintainers investigating Python bug reports; the selected theme can be *Push the Frontier* through software tooling. | No user study, adoption evidence, or measured time saved yet. Explain the target maintainer and concrete use case without claiming validated impact. |
| Use of Meta AI Tooling (25%) | Muse Glimmer is a Meta open-weight model used by two distinct code-investigation agents with repository tools. Per the supplied guide summary, this appears to satisfy Stage 1's model-use requirement, subject to judges' pass/fail decision. | The current NVIDIA route is not a named event inference partner, so do not claim the open-weight bonus for it. Fireworks is a named partner, but its catalog lists Glimmer as on-demand only and event credits are selective; verify an active no-cost balance and the accepted rules before switching. |
| Technical Depth & Execution (25%) | Separate investigations, safe read-only repository tools, deterministic citation checks, evidence comparison, pinned sample commits, explicit incomplete states, and a small evaluation report. | Provider timeouts and a tiny, partly diagnosis-revealing issue set limit the strength of reliability and accuracy claims. Show the limits alongside the engineering. |
| Demo (25%) | A three-minute walkthrough can show the issue, the independent investigations, checked source quotes, evidence comparison, and the bounded result. | A live run can fail if the hosted endpoint times out. Rehearse with the clearly labeled cached result, disclose that it is cached, and confirm the accepted rules allow saved results. |

For the Stage 1 gate, position the project as software-development tooling and identify Muse Glimmer explicitly as the Meta open-weight model. Based on the supplied guide summary, this appears to meet the model-use requirement, subject to judges' pass/fail decision. Do not blur that theme/model fit with the separate open-weight bonus eligibility question. The supplied guide summary says the bonus route must use participant hardware or partner inference; the current NVIDIA route is not a named partner on the public event listing. The supplied summary also says the top five projects in each track advance to Stage 3, which uses the same rubric; no separate final-round scoring advantage is documented here.

The current product fits the Indie Developer and agentic-workflow direction. The open-weight bonus depends on the official wording and organizer decision. **Best Creative Build** specifically asks for Muse Image or Muse Wonder, so the current code-investigation project does not target that category.

## 9. Run the project locally

Requirements: Windows, Python 3.12, Git, and an NVIDIA API Catalog key for Muse Glimmer.

```powershell
cd D:\hackathon
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add the key to `.env`:

```text
NVIDIA_API_KEY=your_key_here
```

The key stays in `.env`; do not paste a Python example into that file or commit the key. Then start the interface:

```powershell
streamlit run app.py
```

The curated Click, HTTPX, Pydantic, sse-starlette, and openai-python checkouts live under `demo_repos/` and are intentionally excluded from Git. Create or verify the eight exact pre-fix worktrees with:

```powershell
.\.venv\Scripts\python.exe .\scripts\setup_demo_repos.py
```

The setup script uses the public Pallets Click, Encode HTTPX, Pydantic, sse-starlette, and OpenAI Python repositories and leaves an existing checkout untouched if its commit or working tree does not match. Citeproof checks the selected commit and clean state again when a curated run starts.

To run the unit suite:

```powershell
python -m unittest discover -s tests
```

## 10. What Citeproof does not do

- It does not guarantee that a diagnosis is correct.
- It does not make or apply code changes.
- It does not execute project code or run generated tests.
- It does not provide a paid inference fallback or use Meta API credits today.
- Its eight curated issues include four Click cases and one each from four other repositories; two new reports are diagnosis-revealing smoke cases. This set does not support a broad accuracy claim.
- It does not prove that the hackathon judges will award a prize.

## 11. Short glossary

- **Agent:** a model call that can choose from tools and use their results to complete a task.
- **API:** a defined way for one program to request a service from another program.
- **Citation:** a file path, line range, and quote offered as evidence for a claim.
- **Commit:** a saved Git revision of a repository. A pinned commit means the sample always starts from a specific revision.
- **Inference:** asking a trained model to produce an answer.
- **Localization:** finding the files or lines related to a bug. It does not necessarily explain the cause correctly.
- **Baseline:** a simpler comparison system, such as one investigator instead of two, run under a fair model-call budget.
- **Ground truth / gold labels:** human-curated reference files and explanations based on the maintainers' merged fix. They are used for scoring and kept out of the model prompt.
- **AST:** Python's structured representation of code. Citeproof uses it to find function and class definitions without executing the project.

## 12. Current build priorities

1. Make the two-agent provider path reliable enough for repeatable, complete runs.
2. Grow the issue set with less-leading reports and carefully checked maintainer fixes.
3. Compare two agents with a fair one-agent baseline on the same cases and model budget.
4. Have a human review diagnosis correctness, not only citation validity or changed-file overlap.
5. Rehearse a short demo that shows one useful discovery and one rejected or corrected citation.

The project should be presented as a transparent evidence assistant, not as an autonomous maintainer or a proven bug-fixing system.
