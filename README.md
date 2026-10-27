# Citeproof

Citeproof is a local-first prototype for investigating Python bug reports with source evidence. Two independent Muse Glimmer investigations use bounded, read-only repository tools. A deterministic checker validates each citation's file, line range, quote, symbol, and whether the cited lines fall within that symbol. The app compares verified citation files and overlapping lines across agents; this is evidence overlap, not proof that either diagnosis is correct.

## Current inference route and cost boundary

This MVP calls `meta/muse-glimmer-30b` through NVIDIA's official API Catalog free endpoint for prototyping. It does **not** call Meta Model API, does not have a paid fallback, and does not change providers when a request fails. NVIDIA's free trial endpoint is rate-limited and availability may vary; when access is unavailable, the run stops with an error. The NVIDIA trial terms limit the endpoint to trial, development, and evaluation use—not production.

Generate a free NVIDIA API Catalog key from the [Muse Glimmer model page](https://build.nvidia.com/meta/muse-glimmer-30b). Store it locally in `.env` as `NVIDIA_API_KEY=...`. Never commit `.env`. This code uses only the free endpoint. Do not enable paid services or add a payment method if you need to avoid charges. The endpoint may be rate limited or unavailable; the app stops rather than switching to a paid provider. NVIDIA says trial inputs and outputs may be recorded and used to improve its products, so only send public issue and source text—not secrets or private code.

Put only the key value after `NVIDIA_API_KEY=` in `.env`; do not paste the sample Python snippet there. The app already contains the `OpenAI` client code.

The user's Meta Model API $150 credits are not used by this route. They remain on the Meta account until an accepted payment method is available. Meta's spend alert is not a hard cap.

## Run locally

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set NVIDIA_API_KEY. Set CITEPROOF_REPO to a local Python repository folder if desired.
streamlit run app.py
```

In the app, select a local Python repository folder, paste an issue title and description, and click **Investigate with two agents**.

The first curated case is Pallets Click issue [#2877](https://github.com/pallets/click/issues/2877), pinned to pre-fix commit `df2e5ed8c4e89f51ff4eddb9600d913083613e62`. Before the agents run this sample, Citeproof verifies that the selected repository is at that exact Git commit and has a clean working tree; it refuses the sample otherwise. Its separate ground-truth file records the merged fix for evaluation and is not included in the model prompt. The issue report describes a `BytesWarning` when comparing `bytes` and `str` under strict Python warning settings; [PR #3642](https://github.com/pallets/click/pull/3642) is the maintainer-confirmed fix. Manual issue inputs do not use this curated baseline and are not benchmark results.

## Safety and current limits

- The model can only call three allowlisted functions: text search, AST symbol search, and bounded source reads.
- Repository paths are confined to the selected root; reads, files, search results, and model calls are bounded.
- No code execution, generated tests, patches, or shell tools are exposed to the model.
- Issue text and repository contents are untrusted input.
- This early build has no maintainer-verified issue benchmark or runtime result claims yet.
