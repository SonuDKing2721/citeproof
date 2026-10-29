# Citeproof Hackathon Submission Prep

**Current state:** Submission-ready work in progress. The public repo is `SonuDKing2721/citeproof`, with MIT license and Shravan Kumar attribution; `main` is at `3b8452665a6de54488cf878db4d4204359b39193`. The participant guide supplied for this event requires a public repository, a three-minute demo video, and a clear account of features built during the hackathon. Git history begins with the Citeproof MVP on October 27, after the October 26 kickoff; preserve that history and describe only those contributions. The current code and documentation changes are pushed, and the full 120-test suite plus `compileall` passed before the latest documentation refresh.

The curated catalog now has eight cases across five repositories. The new sse-starlette #211 and openai-python #3811 cases are diagnosis-revealing smoke examples; no live pair, baseline, or human diagnosis review has been run for them. Keep the demo on the cached Click #3449 report, and don't imply these extra examples produced performance results.

## Three-minute demo run-of-show

Use the curated Click #3449 case and the saved A/B report. The recent NVIDIA trial endpoint timed out, so the reliable path is the app's **Load Cached Click #3449 Demo · No Model Call** button. The UI rechecks citations against the pinned repository on load. Say clearly that the investigator answers are cached and give their original timestamp.

| Time | Show | Suggested narration |
| --- | --- | --- |
| 0:00–0:20 | Citeproof title and issue brief | “Maintainers often get a reproducer and stack trace without a source location. Citeproof investigates a public Python issue and returns source quotes you can inspect.” |
| 0:20–0:40 | Click #3449 issue and pinned pre-fix commit | “This is a saved run for Click issue #3449 at its pre-fix commit. I’m loading the cached result; no model request is being made now.” |
| 0:40–1:05 | Two investigator sections | “The run used independent symptom-first and structure-first investigations. They explored separately, then returned findings with file and line citations.” |
| 1:05–1:35 | Open a finding and inspect its source quote/check | “The checker compares each cited path, line range, and quote with this checkout. A valid quote proves the source text is present; it does not prove the explanation is right.” |
| 1:35–2:00 | Evidence comparison and localization score | “Here, both agents returned verified citations and their evidence overlaps. The primary changed file is ranked first, but recall@3 is only 0.2. These are one-case file-location proxies, not diagnosis accuracy.” |
| 2:00–2:25 | Load the saved cached-pair/live-review snapshot, if useful | “This second snapshot contains a previously completed verifier review attached to a cached pair. Loading it makes no call. The verifier can select existing evidence, but it is the same model route and is not independent ground truth.” |
| 2:25–2:45 | Diagnosis-review control or reviewed export | “Citeproof keeps human diagnosis review separate from citation checks.” The October 27 cached snapshot itself remains unreviewed. A separate review of the October 28 final-symbol-lookup run is recorded as partly supported in `data/benchmarks/click-3449-live-final-symbol-lookup-human-review-20261029.json`; do not conflate the two runs. |
| 2:45–3:00 | End on the safety/limitations summary | “Repository access is read-only and pinned for this example. The tool does not run issue code or claim the root cause is correct; it gives maintainers evidence to evaluate.” |

Keep the pace brisk. If the second snapshot is confusing or runs over time, omit it and use the first saved A/B run. Do not present a cached result as a live model run.

## Capture checklist

- Launch with `streamlit run app.py` and choose Click #3449.
- Confirm the local repository is at the pinned pre-fix commit before loading either saved snapshot.
- Use the explicitly labeled cached button; show its saved-run caption and timestamp.
- Keep the screen free of `.env`, private code, and personal data. NVIDIA's trial terms may record prompts and outputs; use only the public issue and source.
- Show one finding's exact quote and its checker result, then the cross-check and limited localization metric.
- Mention that the recent Pydantic live comparison was incomplete after both requests timed out; don't omit failures when describing reliability.
- A later minimal endpoint health request also timed out after 24.9 seconds and sent no issue text. Use the clearly labeled cached demo unless service availability changes.
- Keep claims to features present in the repository and dates in its history. The initial commit is dated October 27, 2026.
- If showing the human review, use only the adjudicated v2 report at `data/benchmarks/click-3449-live-final-symbol-lookup-human-review-20261029.json` and identify it as a separate October 28 live run. The label is partly supported: the investigators found the pager cleanup path but missed the borrowed-stdout ownership failure.
- Confirm the public GitHub repository and video are accessible before submitting. Review the workspace for scratch files, ignored credentials, third-party licenses, and generated artifacts first.

The participant guide states a **three-minute video** is required and the submission deadline is **November 4 at 9:00 PM ET**. Since the deadline falls after the U.S. daylight-saving transition, that is **November 5 at 7:30 AM India time**. Recheck the event platform before the final upload.

## Submission text draft

- **Project:** Citeproof
- **One-line summary:** Two independent Muse Glimmer investigators trace Python bug reports to checkable source evidence, with deterministic citation validation and a bounded evidence review.
- **Theme fit:** Recommended: *Push the Frontier* (software agents), with a clear *Build for Your World* impact for open-source maintainers. Select the theme the participant can explain from personal experience.
- **Meta model:** Muse Glimmer, Meta's open-weight 30B model, currently served through NVIDIA API Catalog's free endpoint. Citeproof does not call Meta Model API. The event guide requires participant hardware or partner-provided inference for the open-weight bonus; NVIDIA API Catalog is not among the co-host's named partners, so do not claim the bonus for the current route. Fireworks is a named event partner, but its [current model catalog](https://fireworks.ai/models/fireworks/muse-glimmer-30b) lists Glimmer as on-demand only, with serverless unsupported; on-demand inference is billed by GPU-second. The current [event listing](https://events.cerebralvalley.ai/e/meta-ai-developer-hackathon) offers $100 credits only to selected participants. Do not switch or make calls unless this account's no-cost balance is confirmed, Auto Reload is off, and the accepted event rules have been checked.
- **No-cost route research:** Routeway lists exact-model `muse-glimmer-30b:free` at $0 with 200 daily requests, but its public terms do not establish whether signup needs a payment method or who the upstream provider is. Requesty lists the same model through NVIDIA at $0, but the upstream is the timed-out NVIDIA service and Requesty's free terms permit request use for training/improvement. Vercel AI Gateway lists the Together-hosted model with a $5 monthly free-credit allowance; this is a bounded credit pool, not a zero-priced route. None is configured or verified for this account, and none establishes bonus eligibility. No paid requests were made. See [`CITEPROOF_INFERENCE_ROUTE_RESEARCH.md`](CITEPROOF_INFERENCE_ROUTE_RESEARCH.md).
- **Technical proof:** Two independent tool-using investigators; read-only repository access pinned to a commit; deterministic file/range/quote/symbol checks; evidence overlap; at most one verifier call; explicit incomplete states; v2 run reports and human diagnosis review.
- **Honest result:** The original cached Click #3449 demo has verified overlapping citations and ranks the primary file first; that saved run remains unreviewed. A separate 79.7-second live pair-plus-verifier run also had checked evidence overlap, but missed the primary-file top rank (`hit@1=false`, recall@3 `0.2`). The user's review marked that live run's diagnosis partly supported. A later reserved-correction comparison completed in 133.109 seconds but both pair and baseline returned no findings (valid recall@3 `0.0`). The subsequent post-follow rerun timed out both first NVIDIA requests after 122.468 seconds, so it is incomplete and has no localization score. These results do not establish general accuracy or time saved.
**GitHub repository metadata (checked October 29):** The public repository has the description “Evidence-first Python issue investigation with independent Muse Glimmer agents and checked source citations,” topics `ai-agents`, `code-analysis`, `developer-tools`, `hackathon`, `meta-ai`, `python`, and `streamlit`, and the MIT license with `Shravan Kumar` attribution. Follow-up improvements are pushed to `main` at `3b84526`.

Track selection is intentionally left to the participant: choose Indie Developer if entering as an individual/student, or Startup if entering as a qualifying startup team. The participant guide says to submit one project per team/startup.

## Draft organizer question (not sent)

> Hi, I’m building Citeproof with Meta Muse Glimmer (open-weight), served through NVIDIA API Catalog’s free endpoint (`meta/muse-glimmer-30b`). The participant guide says Stage One accepts reasonable use of Meta open-weight models and the open-weight bonus requires participant hardware or partner-provided inference. The event listing names Fireworks as an inference partner and advertises $100 in credits to selected participants. Fireworks' current model catalog says Glimmer is on-demand only, not serverless; it bills GPU-seconds. Does that on-demand route qualify for the open-weight bonus under the accepted Official Rules? Are the advertised Fireworks credits available to all selected participants or only a subset, and can the route be used with Auto Reload off and no payment method? I want to describe the route accurately without enabling paid billing.

## Still needs a decision or action

- One human diagnosis review is recorded as **partly supported** in `data/benchmarks/click-3449-live-final-symbol-lookup-human-review-20261029.json`. This is a single case, not an aggregate diagnosis-accuracy result.
- The project code now has an MIT license. Third-party dependencies, issue material, benchmark records, and assets keep their own terms.
- Copyright attribution is confirmed: `Shravan Kumar`.
- Track selection and final submission fields: require the participant's choice and account access.
- Free route: Routeway is the most promising exact-model $0 candidate, conditional on signup/payment-method requirements, actual free quota, upstream identity, and data policy. No Routeway or Vercel AI Gateway key is configured; no account was created and no call was made. Do not spend money or enable top-ups.
- Event bonus: do not claim it for the current NVIDIA route or the Requesty gateway. Fireworks is a listed partner, but its model catalog lists Glimmer as on-demand only and bills GPU-seconds. The accepted rules and this participant's credit availability still need confirmation. Do not enable paid billing.
- A live model run is desirable for a live demo, but the trial endpoint timed out on the latest checks. Use the cached fallback if the service remains unavailable and identify it as cached.
