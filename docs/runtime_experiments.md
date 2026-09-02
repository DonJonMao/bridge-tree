# Runtime experiment protocol

BridgeTree uses one `BridgeTreeRetriever` and one resolved configuration. There are no Core/Path/Certified code profiles. Resolution order is:

```text
trailing explicit CLI argument > launch-script environment value > YAML > dataclass default
```

Every run writes `resolved_config.json` with the canonical configuration and SHA-256 hash, plus `run_manifest.json` with commit, PersonaMem revision, models, prompt hash and seed. Per-query exceptions go to `failures.jsonl`.

## Runtime arguments

| CLI | Environment variable | Meaning |
| --- | --- | --- |
| `--initial-width` | `INITIAL_WIDTH` | Initial query ANN width |
| `--branch-width` | `BRANCH_WIDTH` | Candidates returned per expanded branch |
| `--context-size` | `CONTEXT_SIZE` | Final number of memories before token truncation |
| `--search-budget` | `SEARCH_BUDGET` | Maximum unique discovered nodes |
| `--max-ann-calls` | `MAX_ANN_CALLS` | Core ANN-call cap |
| `--max-candidate-exposure` | `MAX_CANDIDATE_EXPOSURE` | Returned-candidate cap |
| `--max-depth` | `MAX_DEPTH` | Maximum temporary-tree depth |
| `--cluster-mode` | `CLUSTER_MODE` | `none`, `fixed`, or `effective_rank` |
| `--cluster-count` | `CLUSTER_COUNT` | Number of fixed clusters |
| `--max-clusters` | `MAX_CLUSTERS` | Effective-rank cluster cap |
| `--min-cluster-size` | `MIN_CLUSTER_SIZE` | Cluster-count capacity constraint |
| `--search-order` | `SEARCH_ORDER` | `best_first` or `bfs` |
| `--feature-mode` | `FEATURE_MODE` | `rho` or `path_conditioned` |
| `--selection-mode` | `SELECTION_MODE` | `rho_topk`, `mmr`, `rho_logdet`, or `path_logdet` |
| `--stop-mode` | `STOP_MODE` | `budget` or `certificate_or_budget` |
| `--diagnostic-level` | `DIAGNOSTIC_LEVEL` | `off`, `light`, or `full` |
| `--root-anchor-weight` | `ROOT_ANCHOR_WEIGHT` | Optional query anchor in `[0,1]`; default 0 |
| `--seed` | `SEED` | Experiment and deterministic tie seed |
| `--memory-granularity` | `MEMORY_GRANULARITY` | `user_only` or `user_assistant_pair` |

Invalid combinations fail before retrieval: `path_logdet` requires `path_conditioned`; `rho_logdet` requires `rho`; certificates require a log-det selection mode; initial width and context size must fit the node and candidate budgets.

## Cost matching

`SearchBudget` has three independent limits: unique nodes, core ANN calls and returned candidates. `CostTracker` reports core and diagnostic ANN separately. Dynamic methods consume the same object. Dense and Dense+rerank are evaluated once at their actual one-search retrieval cost.

```bash
bridgetree sweep --budget-protocol matched_ann_calls --budget 4 --budget 8
bridgetree sweep --budget-protocol matched_candidate_exposure --budget 32 --budget 64
```

Stop reasons are one of `frontier_empty`, `max_depth`, `search_budget`, `certificate`, or `insufficient_candidates`.

## Formal runs

The following runs all required main-table methods for seeds 41, 42 and 43, enables the common generator by default, and writes query-paired bootstrap confidence intervals:

```bash
SEEDS="41 42 43" ./scripts/main_table.sh
```

The parameter-matrix ablation uses the same three seeds. Generation is off unless explicitly requested:

```bash
GENERATE=true SEEDS="41 42 43" ./scripts/ablation.sh
```

Both scripts write individual run directories and one `aggregate_summary.json`. Aggregation pairs observations by `(seed, question_id)`, reports a 95% bootstrap interval, and flags labels with fewer than three seeds.

## Tuning safeguards

`bridgetree tune` supports only external objectives. `objective_metric: auto` resolves to answer accuracy when validation generation is enabled, independent recall when a gold file is supplied, and no objective otherwise. Without an external objective it writes trials and a cost Pareto frontier but deliberately writes no best config and never evaluates test.

`bridgetree train` is a deprecated compatibility alias. Neither command updates model weights.

## Result layers

- `outcome`: answer accuracy, parse failure, independent recall and bridge recall;
- `cost`: ANN calls, candidate exposure, unique nodes, phase times, context count/tokens and stop reason;
- `diagnostic`: tree/path/cluster/selection/certificate behavior, including depth drift and first-arrival provenance.

Internal diagnostic objectives never participate in configuration selection.
