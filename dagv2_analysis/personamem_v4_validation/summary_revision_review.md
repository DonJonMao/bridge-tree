# Independent assessment: revision of open historical summaries

Scope: conceptual and code-contract review after R6; no production changes, labels, generation or new run. The existing fixed budgets, original-source obligations, counter preservation, and final response audit remain constraints.

## Recommendation

Use an explicit, narrowly scoped **summary supersession** protocol for a historical aggregate that is revised after reading compatible new evidence. Keep genuine contradiction as a distinct relation. Do not make the controller infer compatibility, union summaries, prefer newer text automatically, or delete the old proof.

R6 shows a concrete semantic mismatch: the old `event_history` text says that the user has attended “several” music-related events. The new text preserves it in full and adds two directly sourced user experiences. The old facts remain true. The existing planner says historical summaries need sufficient relevant examples, not an exhaustive inventory. A new relevant experience therefore does not by itself contradict the old history or its stated scope.

## Can the current contradiction mechanism be retained with clearer guidance?

There is a technically possible interpretation: contradiction retracts the assertion that the old route is the *current complete binding*, not each underlying historical fact. The schema already permits a counter citing the old route ID. An explicit sourced counter plus replacement support would trigger the existing provenance/version machinery; there is no missing target-ID bug in R6.

That interpretation would need to be made an explicit contract, not merely a phrase in the prompt. Current routes conflate a fact proof, a whole string value, and an accepted summary version. A supposedly sufficient non-exhaustive summary can remain factually sufficient after compatible evidence arrives. Calling its replacement a contradiction gives one relation two meanings: factual refutation versus administrative retirement of an older aggregation. The ambiguity affects counter protection, audit interpretation, and which obsolete routes may later be reused. A clearer generic failure message is warranted, but by itself does not resolve the modeling ambiguity.

If the project deliberately broadens `contradiction` to mean source-grounded withdrawal of a whole binding for either refutation or revision, it should still record the reason as a distinct typed relation (for example, `refutation` versus `summary_supersession`) and enforce the corresponding separate constraints. That is substantively an explicit revision protocol even if the wire representation reuses an existing counter envelope.

## Minimum constraints for a revision protocol

1. **Narrow eligibility.** Only a planner-declared open historical aggregate may be superseded. Do not infer eligibility from a variable name or enable it for every text scalar, atomic fact, finite answer, rule, terminal response, or audit. Existing fixed-scope semantic values keep their current contracts.
2. **Explicit request and target.** The model must identify the exact old route(s), old variable version, replacement draft ID, same variable and scope, and actual parent versions. It must distinguish compatible extension/reformulation from factual correction or unresolved conflict. The controller does not decide this from string containment, timestamps or retrieval scores.
3. **Read the evidence.** The paid request must contain the old proof's original text, new cited original text, old summary, and every relevant known counter or pending obligation. Preserve source roles, conditions, event time and observed order separately. Assistant advice alone cannot supply a new user preference.
4. **No evidence erasure.** Replacement is a new sourced whole summary, not an automatic union. Negative experiences, temporal changes and valid counter relations remain explicit. Merely including an old source in the window is not proof that the replacement reviewed or preserved its meaning. Require explicit sourced dispositions for any old claim or protected observation that is no longer represented. Unresolved genuine contradictions remain pending.
5. **Atomic state transition.** Validate the complete revision, source obligations, actual capacity and downstream handoff before retiring the old active binding. Keep the old route and its provenance in history with a distinct superseded relation; do not mark its underlying historical facts false. Failed validation, invalid counters, unavailable handoff or budget exhaustion must not publish the replacement or clear failure markers.
6. **Dependency validity.** Successful revision increments the actual bound variable version and invalidates dependent conclusions. A superseded route must not silently reactivate when the new route later fails, is contradicted, or is replayed from cache. Reinstatement requires its own explicit reviewed transition, or the variable remains unresolved.
7. **Replay and recovery.** Snapshots, restart, failed-batch review, duplicate IDs and protected counters must preserve the distinct relation. Changing query identity or supplying a newer summary is not authorization to discard a failed batch. Revisions consume the existing normal-call and repair budgets and exact 16k checks.

These constraints describe necessary invariants, not a claim that all of them can be guaranteed by citation membership alone. Semantic preservation still relies on the model's sourced judgment and needs end-to-end validation.

## Practical scope

A small explicit revision relation is preferable to changing the broad fact semantics or introducing a new fully atomized claim graph during this repair. A larger redesign could separate immutable atomic history facts from versioned summaries, but it would substantially widen implementation and validation scope. Neither route should be implemented merely to make R6 pass.

The next reviewable implementation proposal should show one successful compatible extension, one true contradiction that remains protected, one temporal/negative-evidence preservation case, and one failed or overflowing revision that leaves the old route and unresolved obligation intact. End-to-end PersonaMem completion is still required; unit tests and token replay cannot establish response accuracy.
