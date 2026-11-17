# Discovery frontier implementation review

Implementation baseline: committed RECONCILE `8dac32b0d28e37b75d5cb1c0b06c69ccfc33bcd8`. Changes are uncommitted. RELEASE/R17 remains frozen at `bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94`; this task did not modify RELEASE, send HTTP/model requests, increase budgets, alter original methods, trim sources, or run the full suite.

## Final scope and interface

The policy applies to all ordinary residual `document_windows`, independent of PersonaMem or variable type. The controller explicitly passes `discovery_doc_ids` for existing local pools and newly discovered/fixed-pool candidates. `None` retains conservative legacy hard unread/whole-pool processing. Mandatory compose/audit cannot accept discovery provenance and keep their indivisible required closure.

`discovery_doc_ids` must be an explicit list/tuple contained in this call's document IDs. A candidate only becomes pure frontier if its source is not already required by the payload's selected/current proof, actual parent or rule inputs, known counters, source-bearing obligations, failed reviews, clues, or existing unread work. There is no new model acknowledgement field and no interpretation of natural-language locator text beyond existing sourced partial/unresolved obligations.

## State and provenance

- `discovery_frontier[(query_identity, alias)]` stores the original source identity/hash, task, requested variables/scopes, program identity/revision, direct parent versions, explicit discovery provenance and scoped `unoffered` status. Its ordered entries remain unknown, not irrelevant, resolved or corpus-complete.
- `discovery_contexts` binds an identity to one task/variable/scope/parent/program context, including after all original frontier entries have moved out. Reusing the identity with new context is rejected before no-alias early returns. Genuine new controller identities retain the old scoped history and must establish current observations normally.
- `discovery_promotions` preserves an original frontier record when it becomes known required evidence before a request. This avoids silently dropping discovery provenance.
- `source_exposures` captures the full actual original-source payload of every initial/scoped repair/terminal-only repair invocation, including sources beyond the window prefix or citations. Each record distinguishes attempted work, returned/failed/not-sent request state, logical request index and final conditional batch assessment/incompleteness. Attempted does not assert successful physical HTTP delivery or semantic use of every source.
- Original-source identity hashes all span fields except the temporary alias, including original text, offsets, role, temporal and adjacency metadata. Sources remain intact in mapper/spans.

A scoped `unoffered` record is not a global never-seen claim: prior exposure under another query/version is retained in history but cannot substitute for assessing a newly grounded scope. Same-owner actual exposure or completed reading cannot be restored as pure frontier. Existing hard work owned by another query remains blocking.

All new queues/identity registries/exposure logs are excluded from `material_signature`; registering, renaming, pausing or rearranging them cannot buy semantic progress or fresh attempts. Actual validated reading state, observations, gaps and hard obligations continue to drive progress. The controller resumes its local frontier before another bridge/ANN step.

## Atomic request, completion and interruption

A whole batch and its bounded repairs are processed before any return to the controller. All valid rows and counters are integrated together; partial/unknown/unresolved and invalid drafts remain hard through existing evidence/failed-review mechanisms. Valid required-slot completion conditionally assesses the whole wire scope. An uncited source is recorded as assessed/read, never automatically irrelevant or unseen.

One ordinary batch then yields for the controller's free residual re-evaluation. Remaining pure frontier can pause while the actual current certificate or terminal semantic output proceeds to real audit. Necessary evidence, finite-world completeness requirements, missing rules, universal/absence/extreme contracts, known counters, actual parent versions and audit constraints retain their prior meaning.

The reader's exception boundary synchronizes remaining hard work into `state.pending`. Temporary in-flight markers do not become pre-existing semantic gaps during normal atomic processing, which would incorrectly widen mandatory proof projection. Existing mandatory unread markers keep their exact variables before actual processing. A failed transport invocation adds its incomplete requested variables conservatively; successful cleanup subtracts only actual current-owner assessed variables. Terminal-only repair has no factual requested variables, creates no empty hard markers, and retains terminal-output failure handling.

## Snapshot compatibility

New snapshots/public diagnostics use explicit `frontier_policy_version=1`. Legacy unread snapshots retain their hard meanings; unversioned nonempty frontier/context/exposure/promotion state is rejected. Restore validates source identity, context shape, archived program variables/scopes, historical parent-version shape, identity consistency and overlap with exposed/read work.

Program matching accepts `initial_program`, current program and all recorded instantiations. Historical contexts are not forced to equal the current program/parent versions. Nonzero-revision reuse of initial_program after rule withdrawal is legal; there is no requirement for every revision to appear in instantiations. Budgets, bridge/session state and paid failed-review recovery eligibility are not reset or replenished.

## Targeted validation and review findings

All executed tests were offline targeted files with synthetic transport responses; they do not establish real semantic accuracy.

1. Initial independent discovery file: 17 passed, one fixture failure because the alleged fresh session had already consumed a planner call. The independent owner repaired the fixture to use the supported fresh resume flow; production restoration constraints were retained.
2. First five existing files: 95 passed, seven failures exposed temporary pending widening mandatory proof projections. Production was corrected; the only remaining old assertion assumed the entire obligation snapshot, including newly added exposure history, must stay byte-identical after an audit. Root updated that assertion while retaining exact factual/obligation/source checks and checking the new precise audit exposure.
3. New implementation tests, independent frontier tests, proof projection, control and residual regressions: **100 passed** after that correction.
4. Seven additional existing reader/recovery/mandatory files: **151 passed**, one exact existing-marker variable test exposed early widening during exposure registration. Production now preserves pre-existing markers until actual failed processing.
5. Latest targeted implementation + independent frontier + mandatory group: **82 passed**, including the newly independent same-identity previously-read/new-document bypass counterexamples. The final subsequent source-only adjustment expanded source hashes to include all original span metadata; final exact-byte independent testing is delegated to the independent owner and root's full-suite gate.

6. Contracts' final independent file on the frozen hashes: **30 passed, 1.40 seconds**, with matching before/after production hashes. Receipt: `discovery_frontier_review_final_receipt.json`; test file SHA256 `992594a1d000a0694055dd396e68f63d203afdcb89780c01107b97abe176fc29`.

Root maintains old tests that deliberately distinguish explicit discovery and legacy behavior. Contracts owns `tests/test_v4_discovery_frontier_review.py`; reader_v4 performs a separate read-only production review. This report is not a full-suite or deployment approval.

## Limits and handoff

The implementation fixes an explicit policy mismatch: discovery membership alone no longer becomes a required proof obligation, and residual re-evaluation happens after one atomic batch. This explains avoidable reading, budget and capacity blocking in synthetic counterexamples. It does not prove an accuracy gain, absence of unseen counterevidence, or the correctness of model extraction. Valid semantic Γ remains the condition for symbolic guarantees; semantic assessment still requires actual terminal generation and audit.

Use a fresh run/source identity. Do not reinterpret R17 or older outputs under this policy. No real-model experiment, release merge, archive build or installation was performed here.

Production and owned test files are now frozen for independent full validation:

- `dagbt/joint_reading.py`: `0de601762d03daa8c4d59c6204c2413c31095b8bdca147a1a5916f8d372b3a3c`
- `dagbt/residual_control.py`: `2ac20adf4cc24f473542915b2d8b8207c24607c962430c8943ca22f114f797aa`
- `tests/test_v4_discovery_frontier.py`: `c6468250025107d662f466b8d8016a671d6579974865d08f307dd74988f35e5f`
