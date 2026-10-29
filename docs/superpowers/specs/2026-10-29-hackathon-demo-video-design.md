# Citeproof Hackathon Demo Video Design

**Date:** 2026-10-29
**Status:** Draft for participant review
**Scope:** A local three-minute demonstration video and its voiceover script

## Goal

Prepare a clear, honest, reproducible three-minute Citeproof demo for the Meta Global AI Developer Hackathon. Use the real app and cached Click #3449 result, with timed on-screen captions and a separate voiceover script. Do not make a model call, enable paid inference, upload the video, or present the cached result as live.

## User-approved direction

- Use the actual Citeproof interface, not a slide-only explainer.
- Use timed captions plus a separate voiceover script; do not synthesize a voice.
- Keep the deliverable local for the participant to review and upload themselves.
- The participant selected the recommended lower-third treatment in the visual companion, after comparing it with a side narration panel. It preserves the evidence view and avoids narrowing the source citations.

## Story and factual claims

The video follows one curated issue from brief to source evidence, cross-check, human review, and limitations. It uses the cached Click #3449 investigation with its original timestamp and says clearly that loading it makes no model request.

Show these verified facts:

- Both investigators returned findings with checked source quotes and overlapping evidence.
- The app's current citation-rechecked v2 evaluation ranks `src/click/termui.py` first, with `hit@1=false` and `gold-file recall@3=0.2`.
- The diagnosis is **partly supported**: the investigators found the pager cleanup/flush path but missed that finalization of a temporary `TextIOWrapper` closed borrowed stdout.
- A valid citation verifies that the quoted source exists; it does not prove the explanation is correct.
- This is one smoke case. The video makes no general accuracy, speedup, or award-eligibility claim.

Preserve the historical v1 JSON and the cached-run unreviewed and reviewed v2 reports. Use the rechecked and reviewed report values already stored in `data/benchmarks/`; do not rewrite their provenance or metric values. Briefly disclose that rechecking in v2 recalculates the historical v1 `hit@1=true` to the current `hit@1=false`.

## Visual treatment

- Capture the real local app at 1280×720, with the sidebar collapsed so local filesystem paths are not shown.
- Use a restrained lower-third caption strip with a small persistent `CACHED · NO MODEL CALL` label. Keep captions clear of issue text, source quotes, and metrics.
- Show the issue brief and pinned commit, one investigator finding from each agent, the checked quote, evidence overlap, the miss and recall score, the partly-supported review, and the safety/limitations summary.
- Use simple cursor movements and deliberate scrolling. Do not add stock footage, external assets, or simulated live responses.
- Keep the project interface legible; do not cover the evidence with a side narration panel.

## Timing and deliverables

The video is 180 seconds. Follow the existing run-of-show in `docs/CITEPROOF_SUBMISSION_PLAN.md`, omitting the optional second cached snapshot to keep the story focused.

1. 0:00–0:20 — Title and maintainer problem.
2. 0:20–0:40 — Click #3449 issue, pinned pre-fix commit, and cached status.
3. 0:40–1:05 — Independent investigators and findings.
4. 1:05–1:35 — Inspect a checked source quote and explain what validation does not prove.
5. 1:35–2:00 — Evidence overlap and current v2 localization miss.
6. 2:00–2:25 — Partly-supported human diagnosis review and causal gap.
7. 2:25–3:00 — Read-only safety, one-case limits, and close.

Create `output/demo/citeproof-hackathon-demo.mp4` as an H.264 1280×720, 30-fps, 180-second video; `output/demo/citeproof-hackathon-demo.srt` for timed captions; and `docs/CITEPROOF_DEMO_VOICEOVER.md` for the separate voiceover script. Keep generated media under the ignored `output/demo/` directory unless the participant later chooses to publish it. Do not upload or attach the video to a public site.

## Alternatives considered

1. **Real app capture with lower-third captions and separate script (selected):** shows actual workflow and results, preserves room for citations, and leaves voice recording to the participant.
2. **Synthetic narration with captions:** would make a self-contained clip, but it risks sounding impersonal and is not needed for the requested draft.
3. **Slide montage:** would be simpler to edit, but would not demonstrate the working interface as directly.

## Acceptance criteria

- The MP4 is exactly 180 seconds and displays the real app at readable resolution.
- The cached/no-call status remains visible during result playback.
- The shown `hit@1=false`, recall@3 `0.2`, partly-supported review, and cached timestamp match their v2 report.
- Captions do not hide the checked source evidence or metric labels.
- The separate script matches the timed captions and does not claim the model produced a live result during recording.
- No credentials, private code, personal data, paid request, synthetic voice, or public upload appears in the output.
- The original v1 report and existing v2 exports remain unchanged.
