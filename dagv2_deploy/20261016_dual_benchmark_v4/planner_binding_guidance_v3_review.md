# Unapplied generic planner guidance patch

Target: `dagbt/webwalker_reasoning.py` only. This patch has NOT been applied.

Changes:
- Explicitly require typed, unbound variable declarations for retrieval tasks and actual terminal bindings.
- Add a fact-free three-node item → maker → deterministic answer example; all values remain unbound, scopes are explicit, and the entity output contract stays intact.
- Append sorted `unrepresented_task_ids` and `nonparticipating_task_ids` to the existing coverage rejection. Its original error prefix and acceptance condition are preserved.

Unchanged: acceptance criteria, output conservation, engine/data/common core, model budgets, repair loop, and number of calls. The example adds no constants containing factual answers.

Minimal regression additions proposed for `tests/test_webwalker_plan_coverage.py`:
1. A retrieval parent with no variable declaration is rejected; assert its exact ID occurs in both diagnostic lists, without modifying the draft.
2. A graph parent with a declared variable that a deterministic terminal does not consume is still rejected; assert an empty unrepresented list and its ID in the nonparticipating list.
3. Parse `PLANNER_MULTIHOP_BINDING_EXAMPLE` and validate it with the ordinary typed-plan validator and Web coverage; assert no factual `value` is supplied and declarations remain open/unbound.
4. Retain existing graph-only-parent, deterministic-compose omission, output-loss and branch-preservation negative cases; keep their current admission outcomes and paid repair limits.

Verification performed without applying the patch: Python syntax parsing and pure in-memory validation of the three invented cases above against both current and proposed coverage. Both versions accept the valid example and reject both invalid examples. No Engine/model/HTTP generation or official labels/tests were used. Production source bytes were rechecked unchanged.

After the active run reaches its terminal boundary, review/apply in a new frozen version; do not alter the active deployment or replay paid attempts.

## Additional terminal-closure diagnostic

The same unapplied patch now appends sorted `outside_terminal_task_ids` and `terminal_task_id` to the existing terminal-closure rejection. The comparison remains exactly `set(tasks) != closure(final)` with its computed closure stored once; there is no admission relaxation or graph rewriting. Its original error prefix is unchanged.

Add one further minimal regression: a fully declared independent retrieval branch outside the final dependency closure must still be rejected, with its exact ID in `outside_terminal_task_ids` and the designated final ID in `terminal_task_id`. This is separate from the missing-binding test and does not rely on any benchmark question or answer.

Repeated pure validation after this extension: the valid generic example is accepted by both current and proposed validators; missing variable, declared-but-unused parent, and disconnected independent component are rejected by both. The candidate names the expected structural IDs in each case. No production source was changed and no model/HTTP call or label test was performed.
