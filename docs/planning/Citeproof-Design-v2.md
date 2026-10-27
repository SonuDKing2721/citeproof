# Citeproof — revised design for review

**Status:** Draft for Shravan's review before implementation  
**Competition fit:** Indie Developer track; primary bonus targets: Best Agentic Use-Case and Best Build on Meta Open Weight Models  
**Build window:** Oct 27–Nov 4, 2026; aim to submit Nov 3

This plan is designed to improve the project's judging case. It cannot guarantee a prize.

## 1. Product

Citeproof helps open-source maintainers investigate a Python bug report. For one curated public repository, the user selects a real issue. Two agents, using the same chosen Meta model but different investigation strategies, independently inspect the repository through limited tools. A deterministic checker validates their file, symbol, line, and quote citations. If their findings differ, a verifier examines the competing evidence. The app returns a ranked evidence map and a suggested regression test, clearly separating checked citations from the model's diagnosis.

The core demo is a real, closed issue evaluated against the repository state before its merged fix. The user can follow each citation to source and see whether the investigation found the area changed by the maintainer's fix.

## 2. Judging fit

| Judging criterion | Evidence Citeproof should show |
|---|---|
| Impact | A real maintainer task, a chosen public Python repository, and results on several genuine issues. Be precise about who benefits; do not claim time savings unless measured. |
| Meta AI tooling | The Meta model makes tool calls, gathers evidence, produces structured findings, and participates in disagreement resolution. Show the model and tool trace in the demo. |
| Technical depth and execution | Independent investigation paths, safe repository tools, deterministic citation checks, a small ground-truth evaluation, and clear failure states. |
| Demo | A stable three-minute walkthrough of an actual issue, source links, a genuine cross-check or rejected citation, and honest evaluation results. |

Stage One requires a real, clear Meta-model contribution and work built during the hackathon. Keep dated commits and make the new work obvious in the public repository. The event guide permits partner-provided inference for the open-weight bonus; verify the selected provider and model meet the event's eligibility rules before relying on that prize.

**Not a target:** Best Creative Build is for a creative project using Muse Image or Muse Wonder. Citeproof is a developer tool, so adding image generation just to chase that bonus would dilute the project.

## 3. Deliberate scope

### First working version

- One small or medium public Python repository, pinned to a commit before the fix.
- Three to five real closed bug issues with merged fixes. Manually inspect the issue, patch, and tests to write a short gold diagnosis and gold source files; changed files alone are only proxy labels.
- Two independent agents, with different strategies. Each can choose from the same small, read-only tool set: search, read a bounded file range, find Python symbols, and inspect relevant history.
- Deterministic citation-integrity checks: file exists, symbol is in that file, line range is valid, and the cited quote occurs there.
- A verifier that runs only when findings disagree or citations fail. It must distinguish a valid citation from a correct diagnosis.
- A simple Streamlit view: issue, agent progress, evidence links, rejected citations and reasons, final ranked findings, and evaluation summary.
- A test suggestion shown as text. If safely isolated test execution is available and validated on the selected repository, allow only a preapproved test command in a disposable checkout with a timeout. Never run a model-supplied shell command or generated test automatically. If a real OS-level isolation method is unavailable, leave test execution disabled and say so.

### Explicitly deferred

- Arbitrary repository support, PR review, automatic patching, multi-repository indexing, production service, and additional model providers inside the workflow.
- A large agent swarm. Three agents are a stretch only after two agents and the complete evaluation work reliably.
- Running generated tests. The first version may suggest a test, but syntax validity does not prove that it catches the bug.

## 4. Model strategy

1. On the first build day, make a minimal tool-calling request work through an officially eligible partner endpoint.
2. If access is available, try Muse Glimmer and Muse Spark Open on the same two representative issues. Choose one by Oct 28 based on tool-call reliability, issue-localization quality, latency, and access stability. This honors the original model-comparison idea without turning comparison into a product feature.
3. Use the selected open-weight Meta model for both agents and any model-based adjudication. Log the exact model ID and host in the app and README so judges can verify the contribution.
4. If an eligible open-weight endpoint is unavailable by Oct 28, switch to the Meta Model API and finish a strong main-track project. Do not claim open-weight eligibility in that fallback.
5. ChatGPT or Claude can be used as development assistants. The submitted product must still use a Meta model substantively; the guide does not require Meta models to be exclusive.

Muse Glimmer is a 30B model, so local inference is not a realistic dependency on a computer with 8 GB or less of RAM and under 8 GB of GPU memory. Prefer eligible partner inference. Do not publish a minimum hardware claim until it has been checked against the selected model card and quantization.

## 5. Evaluation that supports the claims

For each issue, record the pinned pre-fix commit, issue text, merged fix, tests, gold diagnosis, and gold files. Have a human inspect those labels before running the benchmark. Do not expose the fix commit, patch, or post-fix code to the agents.

Compare a single-agent baseline with the two-agent-plus-checker workflow using the same model and a similar total token budget. Report the small sample size and avoid claims of statistical significance.

Report:

- Gold source-file hit@1 and recall@3.
- Human-reviewed diagnosis correctness, with the rubric for what counts as correct.
- Citation integrity rate: the share of claims whose cited file/symbol/lines/quote pass the checker. This is not semantic correctness.
- Number of claims rejected, agent disagreement frequency, how often adjudication resolved the disagreement correctly, latency, and token use when available.

Do not call agreement a probability or calibrated confidence. In the UI use labels such as **corroborated**, **single-agent finding**, or **unresolved**. Deduplicate support by agent before ranking; do not let repeated claims from one agent increase its weight.

## 6. Safety and reliability boundaries

- Model tools are allowlisted Python functions; the model cannot pass arbitrary shell commands.
- Resolve and validate every path under the pinned repository before reading it. Bound file size, line ranges, search results, tool-call count, and runtime.
- Treat issue text and repository contents as untrusted input; tell agents to ignore instructions found inside them.
- Keep API keys in environment configuration and never commit them.
- Show errors and uncertainty in the UI instead of inventing evidence when inference, parsing, or tests fail.

## 7. Three-minute demo

1. **0:00–0:25:** Explain the maintainer problem and show the real issue.
2. **0:25–1:10:** Run the two investigators; show actual model tool calls and source evidence.
3. **1:10–1:50:** Show a genuine disagreement, rejected citation, or unresolved result from the evaluation. Never stage a fabricated error.
4. **1:50–2:25:** Open a source link and compare the finding with the maintainer's merged fix, which the agents did not see.
5. **2:25–3:00:** Show the real evaluation table, exact Meta model and host, and one honest limitation.

Pick the demo issue only after the evaluation. If no real disagreement occurs, demonstrate citation validation on an actual invalid citation from a run, or simply show that agents agreed and report that honestly.

## 8. Time gates

| Date | Gate |
|---|---|
| Oct 26–27 | Confirm exact submission time; claim Meta credits when the claim form is available; check partner inference; select repo and manually verify the first issues. |
| Oct 28 | Model/host decision. If open-weight access is still blocked, switch to Meta Model API and keep building. |
| Oct 29 | One issue runs end to end; baseline recorded. |
| Oct 30–31 | Second agent, citation checker, verifier, and small evaluation. Cut any component that is not working. |
| Nov 1 | Freeze the issue set and report honest results; finish the UI and demo flow. |
| Nov 2 | Feature freeze; record and review the demo. |
| Nov 3 | Submit with buffer, before the guide's Nov 4, 9:00 PM Eastern deadline. |

If the exact issue labels or evaluation are not ready by Nov 1, shrink the set and report the smaller number. A truthful small result is stronger than an inflated claim.

## 9. Submission proof checklist

- Public repository, clear license, and new-work commits from the event build period.
- README names the exact Meta model, model ID, inference host, and what the model does.
- Evaluation data and scoring notes are reproducible, with secrets removed and issue/repository licenses respected.
- Video link works without login and stays within the guide's three-minute requirement.
- Project is submitted before the guide's deadline; confirm it in the submission platform.
- If targeting the community-vote or viral bonus, share the finished demo only after the product and submission are ready; these prizes depend on public response and cannot be engineered into a guaranteed outcome.
