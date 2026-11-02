# Local Ollama Model Sweep

**Date:** November 2, 2026
**Workspace:** D:\hackathon

## Scope

The sweep ran through Citeproof's opt-in Ollama benchmark CLI against clean, pinned pre-fix repositories. The pair and baseline never receive gold-file labels or maintainer diagnoses. Local runs omit the separate hosted verifier and are not comparable to the default Muse route. Ollama reports stay out of the generated Muse summary.

This is a smoke test of the local inference path, not an accuracy claim. A citation that passes exact source checks would still not prove the diagnosis. In these latest runs the checker rejected the proposed evidence or the run did not complete, so no model earned a successful comparison.

## Latest runs after repository-hint and baseline-context fixes

| Model and case | Result | What happened |
|---|---|---|
| qwen3:1.7b, Click #3449 | Incomplete; 10 pair requests, 5 baseline requests; budget unmatched; 0 verified citations; localization recall@3 0.0 | Both investigators followed the reproducer API into src/click/termui.py, but their citations failed symbol-range and exact-quote validation. The baseline returned early, so the comparison could not be scored as budget matched. Report: data/benchmarks/click-3449-qwen3-1-7b-20261102T164945Z-comparison.json. |
| llama3.2:3b, Click #3449 | Incomplete; 8 pair requests, baseline skipped | Investigator A returned invalid JSON after one correction. Investigator B did not successfully read source within its bounded turns. No localization score. Report: data/benchmarks/click-3449-llama3-2-3b-20261102T165235Z-comparison.json. |

The Qwen run confirms the public-API candidate hint can steer an investigator away from a test-runner traceback frame. It does not establish a better localization result: the source checker correctly withheld credit because neither citation was verified.

## Earlier exploratory runs

These used the earlier preseed behavior and should not be pooled with the two latest runs:

- Qwen3 1.7B on Click #3449 cited src/click/testing.py, not a labeled changed file; the pair and baseline used 6 and 4 requests. Report: data/benchmarks/click-3449-qwen3-1-7b-20261102T164149Z-comparison.json.
- Llama 3.2 3B on Click #3449 cited src/click/testing.py, not a labeled changed file; the pair and baseline used 10 and 8 requests. Report: data/benchmarks/click-3449-llama3-2-3b-20261102T164344Z-comparison.json.
- Qwen3 1.7B on Pydantic #13957 produced one citation whose quote did not occur in the cited file; the other investigator failed the source-read gate. Report: data/benchmarks/pydantic-13957-qwen3-1-7b-20261102T164446Z-comparison.json.
- Llama 3.2 3B on Pydantic #13957 had a bad path/tool attempt from one investigator and invalid JSON from the other. Report: data/benchmarks/pydantic-13957-llama3-2-3b-20261102T164604Z-comparison.json.
- Gemma 2B was refused before inference because ollama show did not advertise tool calling. Qwen3 4B had a prior incomplete Click run with long requests; it was not retried on this memory-limited laptop.

The laptop has about 6 GiB of system RAM and a 4 GiB GPU. The 7B and 8B models were not run because their stored weights alone are about 4.7 GiB and 5.2 GiB, before inference memory. deepseek-v4-flash:cloud was excluded because it is not a local model.

## Follow-up

1. Use a verified Meta/Muse-compatible route when one is available, then rerun the same pinned cases. Do not treat this local sweep as an eligibility test for the open-weight bonus.
2. Improve the local prompt/tool loop only when a failing report supports a specific fix; keep the source gate and exact citation checker strict.
3. Review diagnosis correctness separately from citation and localization scores.
