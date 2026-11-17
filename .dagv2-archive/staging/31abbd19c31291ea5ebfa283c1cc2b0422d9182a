# Selected proof and actual dependency review

Reviewed frozen RELEASE/RECONCILE commit `bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94`, read only, without services, labels or tests. R17 remains running. This report distinguishes current behavior from a proposed future change; it is not evidence of improved model accuracy or measured token savings.

## Finding

FactState already selects one sufficient OR proof and follows its actual parent versions. The reader API does not currently preserve that selection at the model boundary: mandatory closure prevents whole-document expansion, but `_payload` reunites every retained route for a requested variable. Audit requests actual certificate/semantic variables while giving the payload every nonterminal task as an input. These are separate sources of additional mandatory input.

In `fact_state.py:132`, `valid()` accepts only active, correctly scoped, current-parent routes. Differing complete values leave a variable unbound; same-value alternatives yield one selected route minimizing its complete recursive source closure. Selected route identity is part of version identity. It is incorrect to select away a conflicting value or to trim premises within the chosen route.

`residual_control.py:99,192` already expresses certificate and semantic actual dependencies. However `audit()` at line 425 constructs all nonterminal task inputs. `_handoff_failures` in `joint_reading.py:1693` duplicates this audit envelope. Both must use the same dependency-scope helper. A task can declare several variables, so narrowing task IDs alone is insufficient: the payload's parent variable frontier must also match actual dependencies.

`joint_reading.py:477` uses selected parent values but all retained `known_observations`, then collects their raw sources, counters, task outputs, obligations, failed records and clues. `mandatory_closure` at line 1854 changes expansion/batching, not proof selection. Its foreign-unread guard checks requested variables, not every incidental parent variable; unrelated owned work is retained and should not be described as universally blocking audit.

## Joint evidence versus archival provenance

The current mandatory request must jointly contain the selected proof's complete original sources, recursive actual parent premises, relevant counters with their semantic targets, relevant outstanding obligations, and any legally offered failed-review drafts and source sets. Clues and original identities/roles/coordinates remain intact. Unselected nonconflicting positive alternatives can remain archival only where independence from these review objects can be established. Uncertain relevance must fall back to retention.

Summary revision is representation ancestry, not a contradiction. `summary_revision_sources` retains inherited original IDs, actual parents and recorded counter sources. A current summary's cumulative source set cannot be pruned by this change. Revoked ancestors invalidate descendants; their semantic relation and counter context must survive. The conservative first implementation retains all revision/retired/counter-bearing routes and their original sources, rather than inventing an unproved source-minimal counter representation.

If a variable has no selected binding, especially because complete values disagree, retain the full competing review group. An empty selected route list is never authority to hide conflicts.

Before a semantic output exists, declared grounded parents have not been proved irrelevant. Their selected sufficient proofs remain required. Only a legal deterministic projection or actual completed certificate justifies eliminating a branch. Audit may use the certificate/semantic frontier, including sourced rule assumptions, rather than unrelated nonterminal tasks.

## Phase and recovery boundaries

Historical extraction, intermediate personal history compose, summary revision and whole-value review retain their full candidate/review scope. `_whole_value_conflicts` inspects prospective global state; `_whole_value_review_failures` builds offered groups from known rows only in `history_evidence`. Keeping that phase full avoids concealing conflicts or creating repair groups with missing premises. Global conflict detection must not be weakened.

Failed recovery keeps original draft IDs, original complete record sources, protected counters, same-task/history phase and actual new-source/parent-change conditions, plus existing finite repair budgets. Query renaming and unrelated revision do not unlock recovery. Relevant evidence obligations require their offered identity and complete original review coverage; empty slots do not discharge them. No projection may erase pending/unread/failed records or clear unrelated work.

## Request authority and repair interfaces

`_schema` derives legal retraction IDs from wire `known_observations`. `_observation` currently accepts any global same-variable route, despite its error wording referring to known rows. Once routes are omitted, this becomes an authority gap: plain-mode output could guess an unseen route ID. Every production observation validation path must receive the exact request-local offered route IDs, including initial draft counter capture, ordinary normalization, duplicate comparison and durable failed-draft guards. Schema and local validation must agree.

Repair payload rebuilding must keep the same projection mode and preserve failed/whole-review/obligation references. Failed records conservatively disable route omission for their variables. Current repair data carries original batch sources, frozen draft records and protected counter relations; this is not permission to reduce their sources. The repair forecast, handoff check, preflight and actual request need the same payload semantics.

## Smallest safe future change

1. Add a shared controller `audit_scope(certificate=None)` returning the audit task and exact requested dependency variables, including sourced rules and excluding deterministic expression slots.
2. Add an explicit mandatory-request proof projection option in `_payload`, passed identically by mandatory preflight, actual request, bounded repair and handoff. Enable OR omission only for terminal/semantic selection and audit. Keep history review unchanged.
3. Omit only ordinary active current-scope/current-parent same-value nonselected positive alternatives proven unrelated to counters, revision ancestry, obligations or failed reviews. Retain all uncertain cases. Do not mutate FactState.
4. Limit audit supported parents at variable level to the actual dependency frontier, recursively retaining selected actual ancestors. Do not replace semantic compose grounding with speculative dependency elimination.
5. Pass request-local offered route IDs into every production `_observation` call. Keep complete raw source identity and content, selected summary cumulative sources, state restore, versions and publication/audit freshness checks unchanged.

Regression coverage should distinguish same-value OR alternatives from conflicts; selected multi-source AND premises; countered/revised ancestors; hidden-ID retraction; one task with multiple variables; eliminated independent pending branch versus actual pending parent; unchanged history/failed/obligation/unread scopes; and equal handoff/preflight/request/repair selection. Capacity overflow remains an honest failure if the genuinely mandatory joint evidence does not fit.

No RELEASE mutation, R17 intervention, package or release approval is authorized by this report. Subsequent implementation belongs only in RECONCILE under separate root coordination.

## Coordinated RECONCILE implementation and final caller review

Root subsequently authorized the minimal change in RECONCILE only. Production files are now frozen for independent tests/full-suite review; no commit or service request was made by this agent. RELEASE was checked clean at the original frozen commit.

Implemented APIs are `_payload(..., proof_projection=False)`, `_observation(..., offered_route_ids=None)`, and `ResidualControl.audit_scope(certificate=None)`. Production observation calls always pass the current raw payload's known route IDs; the default exists for direct normalization helpers/tests, not model response handling. The protected-counter draft capture, ordinary normalization, duplicate-draft comparison and durable failed-draft guard all use this same request-local authority. Schema still derives its targets from that exact known list.

Caller review:

| Path | Projection behavior |
| --- | --- |
| Document window packing/forecast | Default false, complete existing review scope |
| Mandatory preflight, fit check and actual call | True, effective only for terminal/semantic/audit phase |
| Bounded mandatory repair | Same option; full paid batch sources and failure objects retained |
| Prospective handoff | True only for audit or compose, matching the actual caller; final retrieval stays unprojected |
| Audit parent bindings | Requested actual variables plus selected actual ancestors |
| Audit task projections | Excluded if their fact/rule assumptions lie outside that variable frontier |

One important review correction was made before freezing: a currently unresolved terminal output can require reinterpretation of its parents' original text even when the typed parent value is unchanged. Therefore pending/evidence/failed output work protects all current related parent alternatives. This protection survives a parent-only bounded repair by consulting all outputs of the originating compose task, rather than only the reduced repair slots. For audit, the output protection is limited to its actual variable frontier, so an eliminated same-task sibling cannot reintroduce unrelated review scope. Existing publication gates remain unchanged.

The original `test_repeated_terminal_state_still_allows_new_bridge_text_and_recomposition` was deliberately retained unchanged and passed after this protection was added. It establishes that actual new bridge text can resolve an open terminal gap. Ten independent controller/audit scope tests also passed in the same targeted run (11 total). An older capacity test assumed every same-value alternative was mandatory; root owns its contract update while retaining the separate tests for an oversized necessary proof and for a real counter removing the old sufficient proof. These targeted results are not a final whole-suite receipt; root and the independent contract reviewer own the final runs.

Final production SHA-256 at this review freeze:

* `dagbt/joint_reading.py`: `8f23b7c8673d9a6c8ca2803753c58e04e014f0046db5343690ce2b577e3bb103`
* `dagbt/residual_control.py`: `1d281f04f9e20ba042844afab134c53f52923b7618800a29dcc2a68d5009329c`

`git diff --check` passed. `README_PERSONAMEM_V4.md` was reviewed and matches the implemented conservative scope. The change does not claim source-minimal proof construction, slimmer inherited summaries, improved model accuracy, or a remedy for every observed R17 failure.
