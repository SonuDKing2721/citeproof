# Citeproof Hackathon Demo — Voiceover Script

**Length:** 3:00  
**Source:** Cached Click #3449 investigation, originally run 27 October 2026 at 20:20 UTC.  
**Video:** A captioned walkthrough assembled from screenshots of the current app UI. It shows a cached report whose citations are rechecked locally; no model request is made for playback. This script is for a human voiceover; the MP4 is silent.

| Time | Voiceover |
|---|---|
| 0:00–0:20 | Maintainers often receive a reproducer and a stack trace without a clear source location. Citeproof returns source evidence they can inspect while investigating an open-source issue. |
| 0:20–0:40 | This is Click issue 3449, pinned to the pre-fix commit. The displayed investigation is cached from 27 October 2026 at 20:20 UTC. Loading it rechecks citations locally; no model request is made during this recording. |
| 0:40–1:05 | The Findings tab shows the saved answers from two independent Muse Glimmer investigators. These were generated in the earlier run; this playback is cached, not live. |
| 1:05–1:35 | The deterministic checker confirms the cited file, line range, quote, and symbol against the selected checkout. That verifies source integrity only. It does not show that the explanation or diagnosis is correct. |
| 1:35–1:47 | The Compare tab shows overlapping pager-cleanup lines and keeps each investigator's file ranking separate. Shared evidence supports a source location; it is not proof of the diagnosis. |
| 1:47–2:00 | The rechecked result misses the primary file at rank one: hit@1 is false and recall@3 is 0.2. These are localization proxies for one case, not diagnosis scores. |
| 2:00–2:25 | The Report tab records a human review of partly supported. The investigators found the pager cleanup path but missed that finalizing a temporary `TextIOWrapper` closed borrowed stdout. PR 3533 kept the borrowed stream open. |
| 2:25–2:45 | The Trace tab says stored trace events are unavailable for this older cached run. Replaying its summary makes no model call. Repository tools are read-only; the app does not run issue code. |
| 2:45–3:00 | This is one smoke case. It cannot establish general accuracy, time saved, or award eligibility. Citeproof gives maintainers evidence they can assess; it does not issue an automatic verdict. |

The matching timed captions are in `../assets/demo/citeproof-hackathon-demo.srt`.
