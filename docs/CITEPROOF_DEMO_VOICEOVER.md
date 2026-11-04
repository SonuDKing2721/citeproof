# Citeproof Hackathon Demo — Voiceover Script

**Length:** 3:00  
**Source:** Cached Click #3449 investigation, originally run 27 October 2026 at 20:20 UTC.  
**Video:** A captioned screen recording of the current app UI, with the mouse pointer hidden. It shows a cached report whose citations are rechecked locally; no model request is made for playback. This script is for a human voiceover; the MP4 is silent.

| Time | Voiceover |
|---|---|
| 0:00–0:20 | Maintainers often receive a reproducer and a stack trace without a clear source location. Citeproof returns evidence they can inspect while investigating an open-source issue. |
| 0:20–0:45 | This is Click issue 3449, pinned to the pre-fix commit. The displayed investigation is cached from 27 October 2026 at 20:20 UTC. Playback rechecks citations locally; no model request is made. |
| 0:45–1:10 | The Findings tab shows the cached answers from two independent Muse Glimmer investigators: three findings and four verified citations. This is a replay, not a live run. |
| 1:10–1:32 | The deterministic checker confirms the cited file, line range, quote, and symbol against the selected checkout. That verifies source integrity only; it does not prove the diagnosis. |
| 1:32–1:55 | The Compare tab shows overlapping pager-cleanup lines and keeps each investigator's file ranking separate. Shared evidence supports a source location, not a diagnosis. |
| 1:55–2:10 | The rechecked result misses the primary file at rank one: hit@1 is false and recall@3 is 0.2. These are localization proxies for one case. |
| 2:10–2:25 | The Report tab records a human review of partly supported. The investigators found the pager-cleanup path but missed that a temporary `TextIOWrapper` closed borrowed stdout. PR 3533 kept the borrowed stream open. |
| 2:25–2:42 | The Trace tab says stored trace events are unavailable for this older run. Replaying its summary makes no model call. Repository tools are read-only; the app does not run issue code. |
| 2:42–3:00 | This is one smoke case. It cannot establish general accuracy, time saved, or award eligibility. Citeproof gives maintainers evidence they can assess; it does not issue an automatic verdict. |

The matching timed captions are in `../assets/demo/citeproof-hackathon-demo.srt`.
