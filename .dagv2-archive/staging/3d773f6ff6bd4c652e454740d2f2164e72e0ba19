# R8 first-case structural review

- Frozen commit: `ada3261a6a725711ee52c3e291a2817a8f403c9e`.
- First unit: `acd74206-37dc-4756-94a8-b99a395d9a21`.
- Outcome: `unresolved_or_exhausted`; LLM 12, ANN 3, JSON repairs 6. No terminal request.
- No labels or predictions were inspected; source text is omitted from this report.

The planner declared only the downstream `history_summary` as a revisable personal summary. `attended_events`, `music_preferences`, and `cultural_interests` remained ordinary text values. The first retrieval bound one event; later calls repeatedly returned that same value plus a different compatible event under the same variable. The whole-value checker therefore kept the variable unresolved. Explicit obligation IDs in calls 5 and 6 did not repair the underlying two-whole-value mismatch. No summary revision was requested or offered, so the latest no-op change was not exercised.

The other two retrieval variables were blocked by `citation_capacity` at mandatory `joint_read` of the intermediate `history_summary` node. The unresolved `attended_events` history materially inflated that handoff: its accepted proof cites 3 spans, but its retained failure/obligation closure contains 65 original spans. The code intentionally includes those unresolved originals for a related parent; dropping them would discard outstanding evidence.

| Candidate | Draft sources | With accepted parent only | With unresolved parent closure | Actual base / repair input tokens | Admission total / limit |
| --- | ---: | ---: | ---: | ---: | ---: |
| music_preferences | 8 | 11 | 72 | 14236 / 14420 | 18780 / 16384 |
| cultural_interests | 42 | 42 | 92 | 16422 / 16606 | 20966 / 16384 |

The calculated source unions exactly match recorded capacity events. Totals include the unchanged 4096 output allowance, 256 input margin, and 8 fixed tokens. No tokenization of a hypothetical request with discharged obligations was performed; the evidence does not establish that correcting the planner alone will make the handoff fit.

An explicit planner choice between revisable history summary and a single atomic fact is a suitable narrow follow-up. Missing declarations should trigger planner correction, never automatic promotion. Atomic declarations must retain ordinary whole-value semantics and remain ineligible for summary revision. This addresses omission, while semantic misclassification and independent capacity limits still require real smoke validation.

Code, configuration, outputs, and the live process were not modified by this audit. Structural request hashes and counts are in the adjacent JSON report.
