# Citeproof MVP Implementation Plan

**Goal:** Build a local-first Python bug-investigation demo that produces checked source citations and uses Muse Glimmer through Hugging Face's no-card free inference allowance when available.

**Architecture:** A Streamlit UI calls a bounded investigation orchestrator. The orchestrator gives the model only allowlisted, read-only repository tools; a deterministic checker validates every citation. The only hosted model route in this slice is NVIDIA's free API Catalog endpoint pinned to Meta Muse Glimmer. No paid route or automatic provider fallback is configured; rate-limit or endpoint failure ends the run clearly.

**Tech Stack:** Python, Streamlit, OpenAI-compatible SDK, Python AST, Git.

---

## File map

- `app.py`: Streamlit user interface and result rendering.
- `citeproof/repo.py`: safe repository discovery, text search, symbol search, and bounded reads.
- `citeproof/models.py`: typed finding and citation data.
- `citeproof/agent.py`: independent agent prompts, bounded tool loop, and NVIDIA provider adapter.
- `citeproof/checker.py`: deterministic citation integrity checks and cross-agent merge.
- `requirements.txt`: runtime dependencies.
- `.env.example`: names of optional settings; never contains secrets.
- `README.md`: setup, no-card inference constraints, safety boundaries, and run command.

## Tasks

1. Create the Python package and dependency manifest.
2. Implement repository path containment, bounded source reading, text search, and AST symbol discovery.
3. Implement typed citations and deterministic verification.
4. Implement two independent, read-only agents with a strict call cap using Muse Glimmer through NVIDIA's free API Catalog endpoint.
5. Implement the Streamlit investigation flow and clear incomplete/quota-exhausted states.
6. Document setup and run the app locally. No billing key or card is requested by the app.

## Explicit safety behavior

- Do not call Meta Model API from this MVP because the user's RuPay card is unsupported and they have no alternate card.
- Do not call paid HF inference when the free account allowance is exhausted. Do not configure a fallback model or provider.
- The NVIDIA endpoint is trial access with account-specific rate limits and may be unavailable; failure must be shown as unavailable, not silently retried against paid inference.
- NVIDIA trial inputs and outputs may be recorded for product improvement; only public issue and source text are sent.
- The Billing alert is not treated as a spending cap.
- Model-supplied text is untrusted. The model can only invoke the repository functions declared in the application.
- Generated shell commands and generated tests are never executed.
