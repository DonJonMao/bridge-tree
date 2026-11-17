# R6 first-case independent review

Frozen commit: `74d265756a9e2ceac8306bd4b034d80ad9295150`.

Run: `/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r6`.
Question: `acd74206-37dc-4756-94a8-b99a395d9a21`.
This is a read-only review of saved requests, original history, runtime events, and the authoritative result. No evaluation labels, accuracy scoring, generation, or tokenizer calls were used. R6 was stopped by the root agent after this case; this review did not stop or modify the run.

## Actual result

The first authoritative residual result is `unresolved_or_exhausted`; terminal response selection and audit were not reached. Usage was LLM 16/24, ANN 3/36, JSON repairs 6/6. `audit_complete=false`. This proves neither a successful end-to-end run nor an accuracy improvement.

The new admission policy did enable a **real** whole-value repair: call 11 had 9,109 input tokens, unchanged output reserve 4,096, margin 256 and safety 8, total 13,469/16,384. The model returned a response. It did not satisfy the whole-binding reconciliation protocol.

## Music history windows

`music_prefs` initially received 12 local candidate documents and read 123 unique original spans across five windows. The observation is descriptive; it is not a recommendation to skip unread material.

| Call | Visible spans, including retained proof | Newly read unique spans | Input tokens | Valid whole supports |
|---|---:|---:|---:|---:|
| 3 | 58 | 58 | 7,338 | 1 |
| 4 | 38 | 16 | 7,065 | 1 |
| 5 | 38 | 16 | 7,088 | 1 |
| 6 | 40 | 20 | 7,095 | 1 |
| 7 | 35 | 13 | 6,924 | 1 |

All five returned the same complete text value. Each window completed without failed slots. This task used ANN 1, LLM 5, no local JSON repairs, 35,510 prompt tokens and 1,737 completion tokens. The planner separately used two LLM calls and one JSON repair.

## Event-history conflict: an old summary plus new facts

The relevant request directory is:

`personamem/dagbt_residual_memory_v2/attempts/7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0/attempt-001/requests/`

| Call | Request file |
|---|---|
| 10, new history window | `3ad7420bd81121be76f4ce1292d9dd19d043c9644ec3cc26140212042c5b5ca7.json` |
| 11, whole-value repair | `e27f55de31e56027dd8302c88b48e740a9460fde22f3e798e70a6995975486e4.json` |
| 12, durable failed-batch review | `ed9a0f82aba2bdb9766a516b2da27a643adacb1cef5b863e4817e259e801a1e7.json` |

The old integrated route is `fact_26ad8e2ae41a177eae8d74c3`, for `event_history`, entity `user`, time `past`, no parents. It has 17 source citations. Its text reports several music-related experiences: recording and remixing Pacific sounds, an online group, a documentary, Latin-rhythm exploration, and an album review.

Call 10 returns the draft `obs_event_history_1`. Its text retains the **entire old value as an exact string prefix**, then adds collaboration with a local musician and attendance at a Pacific-artist electronic music festival. Its 22 citations include all 17 old citations. The additions are directly stated in user originals `s75`–`s78` and `s115`; they are not assistant suggestions or inferred contradictions.

This is not a batch of two unintegrated competing drafts. It is an existing supported summary plus one compatible extended summary. The current scalar whole-value semantics treat their distinct text strings as competing live values.

### Call 11

The repair receives the old known route, the full failed draft and scope, and all required original citations. It returns the correct draft ID with all 22 original citations, the same value as call 10, valid scope and parents, and `retract_ids=[]`. Its response is history-only `slots`.

The schema **does** offer `fact_26ad8e2ae41a177eae8d74c3` as a legal same-variable contradiction target. The problem is not a missing route ID or a schema that prohibits counters. No explicit retraction is returned, so the old and expanded whole bindings would coexist. Event sequence 287 records `joint_repair_unchanged`; sequence 288 leaves the batch incomplete.

### Call 12 and the misleading generic feedback

Paid durable review is offered as `failed_batch_317bd75f3692fce5d4d9bebc`. All 37 original failed-window spans are visible in its 64-span request. The model returns the correct original draft ID and the correct `resolved_failed_batch_ids` entry. It retains all 22 original draft citations, expands to 29 citations, and adds a traditional Pacific music festival in 2012 and a playlist. The new festival is directly present in user originals `s126`–`s129`. The old whole route again receives no explicit retraction.

The error “requires every original failed draft ID, its complete original text and a sourced scoped review” must **not** be interpreted as proof that the response omitted the draft ID or that its original text was hidden. Those conditions were supplied.

The source-code order explains the feedback:

1. `JointReader._whole_value_review_failures` detects different live whole values, considering the old integrated route and the new support.
2. The reading loop removes that support from `valid` while preserving the unresolved draft.
3. `_failed_review_candidates` then evaluates the remaining empty valid-row set and overwrites the slot-level feedback with the generic ID/source-review message.

Call 12 itself fits at 11,736 input + 4,360 reserve = 16,096. Its next actual local repair needs 14,108 input + 4,360 = 18,468, so sequence 302 rejects it. This is a later durable-recovery capacity problem, distinct from R5's failure to admit the first whole repair.

## Additional first-case blocker

`interests` produces a support draft whose proof cannot fit the mandatory downstream semantic response composition. Local `citation_capacity` repairs and a later durable review do not establish a sufficient fitting handoff. Final sequences 378 and 406 retain `int_001` as failed. This also prevents terminal selection independently of the unresolved event summary.

## Modeling implication and limits

The immediate conflict is caused by failing to explicitly retire an older whole-summary binding when adding compatible information. The model did not meet the existing explicit-contradiction protocol. However, the planner also explicitly defines open historical summaries as sufficient query-relevant examples, not exhaustive inventories. New compatible facts do not establish that the old examples were false.

This supports investigating a distinct, source-grounded **summary revision** relationship, with preserved originals and counterevidence, rather than silently overwriting the old value or automatically merging values. See `summary_revision_review.md` for the independent design assessment. The evidence here does not determine the final implementation, justify raising budgets, or establish an accuracy improvement.

Machine-readable excerpts, exact request paths, original source excerpts and ledger values are in `r6_first_case_review.json`.
