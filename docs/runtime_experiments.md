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
| `--dense-pool-width` | `DENSE_POOL_WIDTH` | Dense candidate floor for reranker-guided methods |
| `--anchor-width` | `ANCHOR_WIDTH` | Task-reranked Dense anchors passed to clustering |
| `--expand-branch-count` | `EXPAND_BRANCH_COUNT` | Number of distinct anchor clusters expanded |
| `--branch-overfetch-width` | `BRANCH_OVERFETCH_WIDTH` | Raw ANN candidates retrieved per guided branch |
| `--branch-keep-width` | `BRANCH_KEEP_WIDTH` | Per-branch candidates retained before final union |
| `--probe-mode` | `PROBE_MODE` | `query_anchor` conditional embedding or diagnostic `centroid` probe |
| `--path-filter/--no-path-filter` | `PATH_FILTER` | Enable per-branch task-aware novelty filtering |
| `--rerank-use-options/--no-rerank-use-options` | `RERANK_USE_OPTIONS` | Include normalized answer options in every rerank query |
| `--rerank-include-time/--no-rerank-include-time` | `RERANK_INCLUDE_TIME` | Expose numeric interaction index metadata to the reranker |
| `--seed` | `SEED` | Experiment and deterministic tie seed |
| `--memory-granularity` | `MEMORY_GRANULARITY` | `user_only` or `user_assistant_pair` |

Invalid combinations fail before retrieval: `path_logdet` requires `path_conditioned`; `rho_logdet` requires `rho`; certificates require a log-det selection mode; initial width and context size must fit the node and candidate budgets.

The new `bridgetree_union_rerank`, `bridgetree_guided_rerank`, and
`bridgetree_guided_pathfilter` methods reject `certificate_or_budget`: their
final objective is task reranking, so the legacy log-det certificate does not
apply.

## Effect-first validation protocol

```bash
./scripts/start_effect_first_background.sh
```

The command uses `configs/personamem32k_effect_first.yaml` and evaluates six
labels sequentially in one timestamped run root. Every event and prediction has
its own method/run label, which preserves exact question pairing while allowing
the embedding and full-ranking caches to be shared safely. It does not evaluate
or use outcomes from the already inspected test partition; the manifest records
this as `test_queries_read=0`.

Accuracy point estimates determine the selected validation method. Only an
exact tie is broken by, in order, logical reranked-document count, core ANN
calls, and retrieval time. Paired bootstrap intervals, bidirectional correction
counts, and `bridge_net_correction` are descriptive outputs and never change
the selection order.

`rerank_calls` and `rerank_documents` are logical algorithmic costs, including
cache hits. `rerank_ms` is physical uncached service time. This prevents a warm
cache from making one method appear algorithmically cheaper while still making
reruns efficient.

The detached launcher writes the complete stream to the fixed
`outputs/background/effect_first.log`, lifecycle state to
`effect_first.status.json`, and copies the final summary/table to fixed JSON/CSV
paths. The timestamped scientific artifacts remain unchanged. The foreground
`run_effect_first_validation.sh` is retained for CI and debugging.

## Cost matching

`SearchBudget` has three independent limits: unique nodes, core ANN calls and returned candidates. `CostTracker` reports core and diagnostic ANN separately; every adaptive FAISS over-fetch pass counts as an actual backend ANN call. Dynamic methods consume the same object. Dense and Dense+rerank are evaluated once at their actual one-search retrieval cost.

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

The parameter-matrix ablation uses the same three seeds and covers no/fixed/effective-rank clustering, BFS/Best-first, depth 1/2/3, rho-Top-k/MMR/rho-logdet, path-conditioned selection, and budget/certificate stopping. Generation is off unless explicitly requested:

```bash
GENERATE=true SEEDS="41 42 43" ./scripts/ablation.sh
```

Both scripts write individual run directories and one `aggregate_summary.json`. Aggregation pairs observations by `(seed, question_id)`, reports a 95% bootstrap interval, and flags labels with fewer than three seeds.

## Tuning safeguards

`bridgetree tune` supports only external objectives. `objective_metric: auto` resolves to answer accuracy when validation generation is enabled, independent recall when a gold file is supplied, and no objective otherwise. A fixed candidate configuration is evaluated once on validation; the persona-disjoint train partition is deliberately not traversed because no parameters are updated. The validation point estimate selects the configuration; core ANN calls, candidate exposure, and retrieval time are lexicographic tie-breakers only when point estimates are exactly equal. Bootstrap uncertainty is report-only and never changes the incumbent. External-outcome selection requires `fail_on_evaluation_error=true`, and every summary records attempted/successful/failed counts plus question-set hashes. Without an external objective it writes trials and a cost Pareto frontier but deliberately writes no best config and never evaluates test.

`bridgetree preflight-tuning --require-full-32k --check-services` verifies the pinned source checksums, seed, complete persona split, exact search grid, retrieval protocol, external objective, zero-failure policy, and live embedding/generator/reranker response schemas before a formal run. `bridgetree tune --audit-full-32k` then re-reads the persisted artifacts and writes `completion_audit.json`; an audit failure makes the command fail even if the scheduler itself reached its final event.

`bridgetree train` is a deprecated compatibility alias. Neither command updates model weights.

## Result layers

- `outcome`: answer accuracy, parse failure, independent recall and bridge recall;
- `cost`: ANN calls, candidate exposure, unique nodes, phase times, context count/tokens and stop reason;
- `diagnostic`: tree/path/cluster/selection/certificate behavior, including depth drift and first-arrival provenance.

Internal diagnostic objectives never participate in configuration selection.
