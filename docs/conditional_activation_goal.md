# Conditional-activation implementation goal

This file preserves the acceptance contract used for the migration from base
commit `65f411e3d3270874c54ec1e74d65f63e22564784`. The executable interpretation,
configuration, artifact map, and server commands are documented in
`conditional_activation_migration.md`. The original supplied contract is also
preserved verbatim in `conditional_activation_goal_source.txt`.

## Scope

Make the Chain production entry point execute the latest train-free memory
retrieval design over the complete PersonaMem-v1 32k dataset. Measure how
candidate conditions change a fixed target memory's marginal utility for the
unchanged original question, use that interaction to control further
retrieval, and choose final evidence by its current marginal contribution.

Preserve history normalization, visibility boundaries, original-query dense
retrieval, query-plus-memory proposals, source IDs, deployment settings, and
the final generator interface. Keep legacy tree and Chain experiments at their
existing entry points; the new `chain-run` entry point must explicitly invoke
the dependency implementation.

Do not add training, generator log-probabilities, value models, generated
personal facts, weighted reward mixtures, path-protection rules, hard search
depth, a fixed final bundle count, or global-optimality certificates.

## Mathematical contract

For one unchanged original query `q`:

```text
R(S) = frozen_reranker(q, canonical_serialize(real_memories_in_S))
M(e | P) = R(P ∪ {e}) - R(P)
A(G => e | P) = R(P ∪ G ∪ {e}) - R(P ∪ G)
                 - R(P ∪ {e}) + R(P)
```

`G` is a singleton or explicitly proposed small group. Score the empty set
using the fixed neutral serialization and the same endpoint; never substitute
zero. Use one declared pointwise scale unchanged through the run. The set
scorer must not apply sigmoid, batch softmax, min-max normalization, or rank
conversion.

Every reranker query is exactly the original question. Richer `q + e + P`
text is only an embedding proposal. Canonical serialization includes the raw
text, role, time, and provenance in chronological/stable-ID order and is
independent of target/premise roles.

Positive activation means score interaction, not necessity or causal
direction, and can coexist with a decrease in total bundle score. Preserve
target singletons, independent singletons, and observed intermediate bundles
for final selection.

## Search contract

- Use modules `dependency_config.py`, `dependency_retrieval.py`,
  `dependency_scoring.py`, `dependency_search.py`, and
  `dependency_experiment.py` for their documented responsibilities.
- State identity is `(target_id, canonical_premise_ids)`. A transition adds
  premises while retaining the target. Re-evaluate a candidate when `P`
  changes; do not globally ban it.
- Initialize from the full union of dense and bridge proposals. Every exposed
  initial record may be a target, with no independent-score filter on bridge
  candidates.
- Put zero-priority roots and positive successors in one deterministic
  best-first frontier so nonempty-premise states can progress before every
  root consumes the budget.
- Each state makes a finite-width proposal over the complete visible history,
  excluding only the target and current premises. Proposal edges are not
  dependency claims.
- Measure every candidate through the same four utility terms. If all
  singleton signals are nonpositive, optionally test pairs from the bounded
  rescue set. Archive positive successors before queueing them.
- Distinguish resource exhaustion, input capacity, empty finite proposals, no
  positive measured signal, and already-seen successors. None is a proof that
  no useful memory exists elsewhere.
- Freeze the archive before selection. Each round compares
  `Delta(B | S) = R(S ∪ B) - R(S)` for every feasible bundle, selects the
  largest positive marginal, updates the ID union, and recomputes. An
  incomplete comparison round commits nothing.
- Deduplicate shared memories and costs. Use the exact selected union in one
  strict `ContextPlan`, including query/options/prompt overhead, with no
  downstream fitting or truncation.

## Scoring and accounting contract

Cache identity includes the query, complete visible-history cutoff/content,
raw metadata, serialization template, model/endpoint, scale, and pointwise
contract. Validate complete unique response indices, finite values, and no
explicit backend truncation.

Warm cache hits consume the same logical unique-set budget as cold misses.
Record unique scored sets separately from client requests and cache hits.
Search and final selection receive independent new-set quotas; a scorer limit
may never be reduced below its already consumed count. Preflight each complete
four-term request before making calls.

Run empty/single/mixed/reversed numerical protocol probes once per real
execution attempt, outside per-task budgets, and record configured tolerance
and measured deviations. Passing this numerical check is not evidence of
semantic validity.

## Evaluation contract

The five default methods are `dense`, `dense_rerank`, `activation`,
`context_marginal`, and `activation_fixed_pool`. Optional methods are
`activation_no_pairs` and `activation_singleton_selection`, using the same
pipeline.

`context_marginal` uses `R(PGe)-R(Pe)` for state acceptance and priority while
retaining the same four-score measurement and dynamic selector. Dense
baselines perform only one original-query retrieval and select under the same
full generator input budget without a separate evidence-count cap.

Validate and freeze all 589 questions and 2,945 default method tasks before
model work. Check fixed raw and normalized data identities, nonempty inputs,
unique question IDs, and visibility cutoffs. Never add a silent limit,
development sample, or empty-plan fallback.

Gold labels are only for post-generation evaluation and must not enter any
model request, candidate cache, or diagnostic prompt. Public answer options
may enter only the final generator prompt. Keep all-data metrics. Use an
explicit authoritative seen/confirmation protocol when supplied; otherwise
mark those reports `not_defined` instead of deriving a new split.

## Execution and persistence contract

The worker must do real retrieval, scoring, generation, and evaluation.
Persist `optimizer_steps=0` and `weights_updated=false`; progress logs describe
inference rather than simulated training.

Provide working `preflight`, `start`, `status`, `log`, `resume`, and `stop`
actions. Start must detach safely. Resume must reuse the exact
original run directory and frozen plan, skip successful tasks, retry failed or
pending tasks, and reject changed config, data, source, or protocol identities.
A fully successful resume must make zero model calls.

Write authoritative per-task outcomes atomically; keep append-only prediction
and failure histories; compute metrics from authoritative outcomes; preserve
failures in the original denominator. Persist the current failure and stop the
attempt on infrastructure transport outage, leaving other tasks pending.

Default observability is a progress message every 10 tasks, metrics every 25
tasks, and a heartbeat every 30 seconds. Save the frozen plan, resolved config,
run/completion identities, predictions/failures/outcomes, visibility snapshots,
candidate pools, proposal graph, four scores, activations, search states,
stops, selection rounds, exact final context, and separated cost counters.

Package source, configs, scripts, tests, documentation, and complete raw and
processed data for Linux. Keep model installation and private credentials out
of the package.

## Required offline evidence

Deterministic fake-service tests must cover at least:

- `R(empty)=.10`, `R(e)=.25`, `R(p)=.35`, `R(pe)=.90`, yielding activation
  `.40`;
- positive activation with a lower total score while the singleton can win
  final selection;
- fixed-target multistep evolution and premise-conditioned re-evaluation;
- pair activation when both singleton activations are nonpositive;
- dynamic marginal reranking and all-or-nothing selection rounds;
- empty-set calls, canonical cache ordering, shuffled indices, warm/cold
  logical budgets, invalid responses, explicit truncation, and capacity;
- full-bank discovery outside the initial pool versus fixed-pool exclusion;
- nonempty premise states under the default-style finite ANN budget;
- a real small fake-service experiment that writes predictions/metrics,
  resumes with zero calls when complete, rejects identity conflicts, and keeps
  failures in the denominator;
- a data-only full preflight freezing 2,945 tasks without model calls or a
  false inference-complete status;
- relevant legacy client, CLI, and background regression tests.

Do not contact the user's model deployment from the workstation. Separate
offline implementation evidence from server-side real-model evidence and do
not claim improved accuracy, semantic validity, server compatibility, or
global optimality without the corresponding experiment.
