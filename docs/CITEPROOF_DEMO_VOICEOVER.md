# Citeproof Hackathon Demo — Voiceover Script

**Length:** 3:00  
**Source:** Cached Click #3449 investigation, originally run 27 October 2026 at 20:20 UTC.  
**Recording:** The report is loaded and citations are rechecked locally. No model request or upload occurs during capture. This script is for a human voiceover; the MP4 uses timed captions and has no synthesized narration.

| Time | Voiceover |
|---|---|
| 0:00–0:20 | Maintainers often receive a reproducer and a stack trace without a clear source location. Citeproof returns source evidence they can inspect while investigating an open-source issue. |
| 0:20–0:40 | This is Click issue 3449, pinned to the pre-fix commit. The displayed investigation is cached from 27 October 2026 at 20:20 UTC. Loading it rechecks citations locally; no model request is made during this recording. |
| 0:40–1:05 | Two independent Muse Glimmer investigators followed separate paths through the code. These answers were generated in the earlier saved run; we are replaying that result, not presenting it as live. |
| 1:05–1:35 | Here, the checker confirms that the quoted lines exist in the selected checkout and match the cited symbol. That verifies source integrity only. It does not show that the explanation or diagnosis is correct. |
| 1:35–1:47 | Both investigations cite overlapping pager-cleanup lines. The v3 report also keeps each investigator's ordered file ranking separate from the pair-level score. |
| 1:47–2:00 | The rechecked result ranks `src/click/termui.py` first but misses the primary file: hit@1 is false and recall@3 is 0.2. The historical v1 report stored hit@1=true. |
| 2:00–2:25 | A human review marked the diagnosis partly supported. The investigators found the pager cleanup and flush path, but missed that finalizing a temporary `TextIOWrapper` closed borrowed stdout. PR 3533 kept the borrowed stream open. |
| 2:25–2:45 | Repository tools are read-only and bounded, and the app does not run issue code. The ranking measures file localization against maintainer-curated changed-file labels. It is not a diagnosis score. |
| 2:45–3:00 | This is one smoke case. It cannot establish general accuracy, time saved, or award eligibility. Citeproof gives maintainers evidence they can assess; it does not issue an automatic verdict. |

The matching timed captions are in `output/demo/citeproof-hackathon-demo.srt`.
