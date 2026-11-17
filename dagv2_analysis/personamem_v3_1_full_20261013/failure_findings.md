# PersonaMem residual failures: read-only evidence review

This review reads only compressed authoritative residual result rows and matching production source. No gold labels were opened, no scores recomputed, no model called, and no production file edited. The archive contains 445 residual rows: 239 `ok`, 107 `budget_exhausted`, 48 `invalid_output_format`, 23 `unresolved_or_exhausted`, 17 `audit_incomplete`, 7 `execution_failed`, 4 `timeout`. This file investigates the first four failure groups, 195 rows in total.

Reproduction: run `python analyze_failures_readonly.py` from this directory. It streams each selected `.json.gz` through `gzip.open`/`json.load`, keeping one row in memory and writing only small features. Evidence paths for every unit are in `failure_features.jsonl`. Summary counts are in `failure_analysis_summary.json`; additional checks are in `failure_supplemental_features.json`.

## 1. Terminal output incompatibilities: all 48 invalid-output rows

Disjoint observable groups:

- 34 have `final_prediction: null` in the terminal reasoning response.
- 14 have a syntactically legal `a`/`b`/`c`/`d`, but their generated `semantic_answer` is not byte/canonical-JSON identical to the value checked at publication.

All 48 have zero `joint_reading.batches[].failed_slots`; 41 completed audit successfully. Thus this group is not a JSON-slot repair failure, and 14 are not invalid option-letter syntax. All retain substantial LLM budget (12–22 calls remaining).

Evidence: locate the `diagnostics.events[]` reasoning response whose `logical_call_index` equals `diagnostics.terminal_input.logical_call_index`; parse its `raw_output`. Compare `semantic_answer` with `answer.semantic_answer`, and inspect `final_prediction` independently. Production `residual_control.py:579–591` checks exact semantic equality and option validity late, after slot validation/audit; `joint_reading.py:578–579, 664–670` captures these terminal fields without adding a failed-slot obligation when they disagree with slot values.

Example `27b61c09-e5ab-4d00-b395-eea8ee619b70`: valid letter `a`; 3 LLM calls; audit supported; generated semantic answer is a conversational reply, while its terminal slot value is a factual summary. The exact consistency check correctly rejects the conflicting meanings. The remedy should be a coherent terminal-output contract with early consistency validation and bounded repair, **not bypassing the check or accepting the pre-audit letter**. Without gold, this review makes no claim that any rejected letter was correct.

There is also a concrete representation bug. Four rejected rows have a typed JSON object as generated `semantic_answer`, while the node's value at publication is its JSON-serialized string. Parsing that string produces the exact same object. `sync_nodes` calls `display` (`residual_control.py:245–256`), but publication compares the original typed object to the display string (`:579–581`). Of these four, only one has a legal letter, so fixing the type comparison alone would not remove all four failures. The clean isolated case is `e0961881-e2b5-4e54-b370-aa6b4d533df9`: legal `c`, audit complete, identical object after `json.loads(published_value)`, but different types. The four IDs are recorded in `failure_supplemental_features.json`.

The 34 null letters should not all be called parser errors. The protocol allows null on ambiguity. Some plans produce a factual entity/list when the options are personalized conversational replies; null may reflect that task mismatch or model abstention. No truth claim is inferred from null alone.

## 2. Audit-incomplete: 17 rows, mutually exclusive classifications

| Observed blocking condition | Rows |
| --- | ---: |
| Completed slots, final audit verdict conflict | 8 |
| Completed slots, final audit verdict unknown | 1 |
| Verdict supported but unresolved obligations remain | 1 |
| Duplicate observation ID prevents unambiguous repair | 4 |
| Audit observation value violates declared text type | 1 |
| Audit exhausts LLM budget | 1 |
| Audit input exceeds real wire capacity | 1 |

Do not label all 17 infrastructure/protocol failures: ten have completed slots but unresolved semantic audit conditions. Example `789f0d73-3011-4855-9fae-308b12d9379c` has just 3 LLM calls and no errors/failed slots. Audit explicitly retracts a claimed creative-writing workshop because cited history instead discusses a constructive-criticism workshop. This is an actual audit disagreement, and allowing the original answer through would defeat the check.

The controller immediately stops when `audit()` returns false (`residual_control.py:429–433`), even when a counterexample revokes a fact and there is ample remaining budget. That design may deserve a bounded recovery path; this review does not establish which revoked claims could subsequently be repaired.

## 3. Budget-exhausted: separate retrieval and LLM budgets

The 107 rows divide exactly into:

- **97 ANN exhausted**: `diagnostics.ledger.remaining.ann == 0`; LLM budget remains. Ninety-four of these have no failed slots, none repeat a reasoning response reference, and 96 never reach semantic composition. These are predominantly unresolved prerequisite/retrieval workflows, not protocol repair loops.
- **10 LLM at its audit reserve**: remaining LLM calls = 1, ANN still 14–20. Every row repeats at least one reasoning `response_ref`; semantic composition runs 16–22 times. Three have failed slots. Cache replay is charged as logical budget: repeated references are **not proof of repeated HTTP generation**.

The empty-visible-source protocol loop is confirmed in one row, not 107: `26e1084c-2235-4dd6-9637-4f7b8990ac37`, 16 semantic compositions, 6 repairs, 19 cache hits, 23 charged LLM calls. Later batches have no visible source aliases and repeatedly fail `Supported/counter observation needs original sources`. Their response reference is identical. The controller receives `progressed=True` even for a failed batch (`joint_reading.py:671–674`) and can continue issuing semantically unchanged reads. Raising the budget alone does not address this case.

A non-protocol repeat exists in `0a90b38b-9bdf-437b-a4ee-fb671162c430`: 22 semantic compositions, no failed slots, repeated cached response 18 times, `observations=[]` and an unresolved statement that available sources do not describe yesterday's film-blog post. This is a no-progress control issue rather than malformed JSON.

### Six inspected ANN-exhausted examples (not a random prevalence estimate)

Details and initial DAGs are saved in `ann_exhaustion_sample_features.json`. Examples were selected from small/middle/large row sizes to cover different workflows; findings should not be extrapolated to all 97.

- `1d914339-dec5-4e6d-90e2-881c5ca505fc`: user asks for reading recommendations. Preferences are successfully bound, but the DAG demands externally notable books from the last five years as a retrieval prerequisite. Readers repeatedly state that supplied personal history has preferences, not an external book catalogue. It stops after 36 ANN calls and 20 retrieved documents.
- `6defbf8e-0c2e-42f6-99e0-809ec183852e`: user asks what activities/workshops to consider. Interests are successfully bound, but the DAG requires currently available workshop listings from a personal-memory corpus. It stops after 36 ANN calls and 20 retrieved documents.
- `89393cad-6d64-438d-a897-d0784d7eb3b1`: user says they recently cooked a traditional dish from another culture. The plan converts this into identifying the dish and culture; inspected evidence batches do not name the dish. It stops after 36 ANN calls and 18 documents.
- `7f7c4177-a11b-4a29-add6-b78ff733799c`: user says they packed quickly for an overnight trip. The plan demands the trip identity and an enumerated packing list; read batches lack a complete list. It stops after 36 ANN calls and 22 documents.
- `bf1209ec-2d77-4385-be78-04abfba82f31`: set variable `recent_courses` accumulates 60 model support observations. Persisted state has six distinct unrevoked whole-set values, and `facts={}`. `FactState.valid` rejects distinct values rather than unioning them (`fact_state.py:30–39`). Examples include singleton sets for an online course, an effective-study workshop, and a case-study-analysis workshop. This is a whole-set interpretation/state-reconciliation failure, not absence of retrieved evidence.
- `3315a6fd-fcc2-4101-8766-f6b01d457713`: several facts and a final summary are bound, but `sentiment` remains pending after conflicting past/present blog attitudes. A malformed non-support observation also appears. More ANN calls do not resolve that outstanding obligation.

These cases support a task/planner alignment problem and missing no-progress/conflict handling. They do **not** prove that the entire visible memory prefix lacks relevant evidence, that BridgeTree retrieval has poor recall, or that removing evidence requirements would improve valid accuracy. No full-corpus relevance judgement or retrieval ablation was performed.

## 4. Confirmed certificate dead ends: unresolved/exhausted

All 23 unresolved rows were inspected. Twelve have `one_reason` (11) or `all_failures` (1) contracts paired with a program root `op=var`. Original `certify_output` immediately returns `None` for this pair (`residual.py:481–483`); the semantic fallback only handles mode `semantic`.

For 11 of these 12, actual persisted facts yield `possible_outputs.status='determined'`, `nonempty_proven=True`, no pending variables, yet no certificate. The twelfth also has unresolved facts, so contract repair alone is not enough. A separate `value` row, `63f0c40f-a1c8-4e5d-af0a-37bc2b317185`, is determined with no pending facts but `rules_complete=False`, preventing certification. The other 11 unresolved rows remain indeterminate.

This was reproduced by invoking the original `possible_outputs` and `certify_output` on persisted `diagnostics.fact_state.program/facts/contract/versions/sources/pending_variables`; no model or labels are involved. Results are in `certificate_deadend_reproduction.json`. Example `5117e665-5204-44ae-9946-0c984965c04e` (`all_failures`, `op=var`) already binds a sourced reasons list and emits a legal `d`, yet cannot certify under the configured mode. This is an invalid planner-contract combination that should be rejected/repaired when the plan is accepted, rather than weakening certification at the end.

## Interpretation limits

Counts above describe observable runtime conditions, not recoverable correct-answer gains. Some conditions co-occur: four type/display mismatches overlap null-letter cases, semantic mismatches overlap missing letters, and protocol failures overlap budget groups. Do not add overlapping counts as separate roots or claim these patches will close the measured accuracy gap.
