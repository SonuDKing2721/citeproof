# Citeproof submission text

Copy-ready material for the participant portal. The project owner submits this through the event portal; this document is preparation only.

## Project fields

- **Project name:** Citeproof
- **Track:** Indie Developer — solo entrant
- **Problem statement:** Push the Frontier — software development tooling
- **Repository:** <https://github.com/SonuDKing2721/citeproof>
- **Demo video:** [Three-minute Citeproof walkthrough](../assets/demo/citeproof-hackathon-demo.mp4)
- **Public demo URL for the portal:** <https://github.com/SonuDKing2721/citeproof/blob/main/assets/demo/citeproof-hackathon-demo.mp4>
- **Demo captions:** [Timed captions](../assets/demo/citeproof-hackathon-demo.srt)
- **Voiceover:** [Voiceover script](CITEPROOF_DEMO_VOICEOVER.md)

## Short description

Citeproof helps Python maintainers investigate bug reports with source evidence they can inspect. Two independent Muse Glimmer investigators search a pinned repository using bounded, read-only tools. A deterministic checker verifies each cited file, line range, quote, and symbol. Citeproof then compares the evidence while keeping citation validity, file-localization metrics, and human judgment about the diagnosis separate.

## Model and implementation

Citeproof uses Meta Muse Glimmer 30B (open-weight) through NVIDIA API Catalog's free inference endpoint. It does not call Meta Model API and does not use a paid fallback. The captioned demo is an interactive screen recording of the current UI; it shows an earlier saved Click #3449 run, rechecks citations locally, and makes no model request for playback.

## What is new in the project

- Two independent investigation paths with repository access confined to a selected, pinned checkout.
- Deterministic checks for cited paths, line ranges, exact quotes, and symbols.
- Explicit incomplete states, separate per-investigator file rankings, request-budget-aware comparisons, and versioned reports.
- A human diagnosis review kept separate from citation checks and file-localization scores.

## Demo limitations

The video shows one cached Click #3449 example, not a live model run. Its rechecked localization result has `hit@1=false` and `recall@3=0.2`; the participant marked the diagnosis partly supported because the investigators found the pager-cleanup path but missed the borrowed-stdout ownership cause. This is one smoke case and does not establish general accuracy, time saved, or diagnosis quality. The demo has timed captions and no synthesized voiceover.

## Local run

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

No API key is required to load the cached Click #3449 demo. Live inference requires a locally configured `NVIDIA_API_KEY`.
