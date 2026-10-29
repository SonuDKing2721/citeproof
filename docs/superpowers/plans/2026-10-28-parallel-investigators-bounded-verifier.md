# Parallel Investigators and Bounded Evidence Verifier

## Goal

Keep Citeproof's two searches independent, reduce their combined wall time by running them concurrently, and add one bounded Muse review that can select only findings and citations already accepted by Citeproof's deterministic checker. The reviewer also suggests one regression-test scenario, explicitly labeled as proposed and unexecuted.

## Constraints

- Investigator A and B receive the issue and repository tools independently; neither receives the other's output.
- Preserve deterministic A/B ordering in reports even if completion order differs.
- Do not call the verifier unless both investigators finish without errors and each has at least one source-checked citation.
- The verifier receives only the issue and allowlisted findings/citations with their exact checked source quotes. It receives no repository tools.
- The verifier gets one model request, capped at 120 seconds. It may select an existing finding/evidence ID or report conflict/insufficient evidence; it cannot create a path, line, quote, finding, or accepted citation.
- The test suggestion is advisory and must state that it has not been run.
- Report investigator and verifier request counts separately. Keep localization metrics based on the two investigators only.
- If the verifier times out or returns malformed/untrusted IDs, retain the investigator findings and mark review unavailable.

## Implementation sequence

1. Add failing tests for verifier candidate IDs, schema/status validation, one-request budget, timeout/malformed output handling, and skip conditions.
2. Add a verifier result model and a pure candidate-serialization/response-validation layer; implement the single-call API wrapper.
3. Add a pair-orchestration helper using two workers and a main-thread progress callback; test concurrency and stable ordering.
4. Add failing tests for snapshots, saved report compatibility, export metadata/request counts, and benchmark request accounting.
5. Integrate the pair runner and verifier into the Streamlit flow. Keep UI calls on the main thread, label the test scenario “Suggested · not run,” and visibly distinguish the model review from deterministic citation checks.
6. Integrate verifier counts/results into run and budget-comparison reports without changing localization score inputs.
7. Update README/project guide/handoff and run the full authorized verification suite, compile check, Streamlit AppTest, and local health check. Record live inference outcomes separately from mocked tests.

## Acceptance checks

- Parallel investigator calls overlap in time, remain independent, and are returned in stable A/B order.
- Verifier makes at most one request and cannot introduce a new evidence identifier or citation.
- Missing/failed investigators or missing checked citations skip verification without spending a request.
- Verifier failure does not erase the two investigation results or mislabel a diagnosis as proven.
- Reports include separate request totals and do not change gold-label scoring semantics.
- UI progress stays responsive while agents run and clearly labels suggested tests as unexecuted.
