# BridgeTree Preference-RAG

This directory is a self-contained, portable implementation of the 2026-09-01 design **“BridgeTree: 面向 Preference-RAG 的桥接感知路径条件临时记忆树检索方法”**. It keeps source code, immutable raw data, normalized data, caches, and run artifacts in separate directories so the directory can be copied to an Ascend 910B host without depending on the parent `datacenter` package.

The full-current runtime combination is:

```text
coarse ANN -> effective-rank spherical clustering -> centroid probe
-> real-parent projection -> bottleneck reachability -> path-conditioned feature
-> certified log-det greedy selection -> one generator call
```

Centroids are never inserted as memories. Retrieval makes zero LLM calls. A generator is called exactly once only when `--generate` is enabled. There is one `BridgeTreeRetriever`; Core, +Path, +Certificate and Full-current are runtime parameter combinations, not separate classes or code profiles. The project intentionally has no distillation, RL, online Judge, retrieval LLM, or model-weight training stage.

## Quick start

```bash
cd bridgetree_preference_rag
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'

# Official PersonaMem-v1 32k split, pinned to a repository revision.
.venv/bin/bridgetree download-personamem --split 32k
.venv/bin/bridgetree prepare-personamem --split 32k

# Offline implementation smoke: no model endpoint is contacted.
./scripts/smoke_synthetic.sh

# Runtime-parameterized Core experiment (zero generator calls by default).
./scripts/run_personamem.sh --limit 10

# Three-seed main table and module matrix; both write aggregate_summary.json.
./scripts/main_table.sh --limit 10
./scripts/ablation.sh --limit 10

# Configuration tuning with periodic validation (never updates model weights).
./scripts/train.sh

.venv/bin/pytest
```

The default model services match the parent `datacenter` project:

| Use | Model/service |
| --- | --- |
| Embedding | `qwen3-embedding-8b`, `http://111.19.156.74:8001/v1/embeddings` |
| Rerank comparison baseline | `http://111.19.156.74:8002/rerank` |
| Final generator | `deepseek-v4-flash`, `http://111.19.156.30:8006/v1/chat/completions` |

Query embeddings use the same Qwen retrieval instruction as datacenter's `EmbeddingClient.embed_query`; memory documents are encoded without that prefix.

The requested default API key is present in `configs/default.yaml`. `BRIDGETREE_CHAT_API_KEY` overrides it without editing files on another server. The reranker is confined to `dense_rerank`; inserting it into BridgeTree would change the certified proxy objective.

## One implementation, runtime-controlled modules

`scripts/run_personamem.sh` declares every algorithm switch at the top. Environment variables override YAML, and trailing CLI arguments override the script values:

```bash
FEATURE_MODE=path_conditioned \
SELECTION_MODE=path_logdet \
STOP_MODE=certificate_or_budget \
bash scripts/run_personamem.sh --max-depth 3 --limit 10
```

The named configurations are only labels:

| Label | Runtime combination |
| --- | --- |
| Core | `fixed + best_first + rho + rho_logdet + budget + depth=2` |
| +Path | Core with `path_conditioned + path_logdet` |
| +Certificate | +Path with `certificate_or_budget` |
| Full-current | `effective_rank + path_conditioned + path_logdet + certificate_or_budget + depth=3` |
| No-cluster / BFS / Depth1–3 | Change only the named switch |

See [docs/runtime_experiments.md](docs/runtime_experiments.md) for every argument, legal combinations, budget protocols and output schema.

## Experiments

`--method` supports every baseline or ablation required by the design:

- `dense`, `rfmem_familiarity`, `rfmem_recollection`, `rfmem`
- `cluster_prf` (cluster pseudo-relevance feedback without cognitive claims)
- `bridgetree`
- `ablation_no_cluster`, `ablation_bfs`, `ablation_fixed_depth`
- `ablation_topk`, `ablation_rho_dpp`, `ablation_direct_path`
- `dense_rerank` additionally exercises the datacenter reranker endpoint

Every prediction is split into `outcome`, `cost`, and `diagnostic`. Cost includes core/diagnostic ANN calls, candidate exposure, unique nodes, index/retrieval/diagnostic/generation time, final context count/tokens and stop reason. BridgeTree diagnostics include the deterministic first-arrival tree, depth drift, parent-child cosine, bridge lift, navigation-only parents, duplicate proposals, clustering statistics, certificate gaps and `Epost`. `diagnostic_level=light` is the formal default and makes zero diagnostic ANN calls.

Matched-cost sweeps are directly runnable:

```bash
# Dynamic methods get the same core ANN-call cap; Dense is evaluated once at actual cost.
.venv/bin/bridgetree sweep --budget-protocol matched_ann_calls \
  --budget 4 --budget 8 --limit 10

# Dynamic methods see the same number of returned candidates.
.venv/bin/bridgetree sweep --budget-protocol matched_candidate_exposure \
  --budget 32 --budget 64 --limit 10
```

PersonaMem-v1 does not provide gold memory IDs. `Recall@k` and `Bridge Recall@k` are therefore only computed when `--bridge-gold` supplies independent annotations in the schema described in [data/README.md](data/README.md). The implementation never defines gold bridge memories using its own bridge-lift score.

## Configuration tuning and module diagnostics

`./scripts/train.sh` invokes `bridgetree tune` (`train` remains a deprecated alias). It uses a persona-disjoint 70/15/15 split and a small validation probe every 50 train queries. Internal log-det, path-objective and certificate metrics are never tuning objectives:

- with generated validation answers, `outcome.answer_accuracy` is used;
- with independent memory gold, validation recall is used;
- with neither, all trials and a cost Pareto report are written, but there is no `best_config.json` and test is not read.

When a best configuration is externally justified, every final main-table method uses the same generator, prompt, segmentation, chronological serialization, final `k`, context token budget and output token budget. Edit `configs/train.yaml` to enable `validation_generate`, `final_generate`, or `bridge_gold_path`.

The dataset is self-contained in this repository, not under the sibling `datacenter` project:

- raw input: `data/raw/personamem-v1`
- normalized data: `data/processed/personamem-v1/32k`

Each tuning run creates `outputs/training/tune_<timestamp>/`. `events.jsonl` and `metrics.csv` contain progress and validation events; `modules/*.jsonl` separates encoding, coarse retrieval, clustering, path, innovation, selection, search, cost, outcome and timing. `pareto_frontier.json`, `trials.json`, `resolved_config.json`, `run_manifest.json`, `failures.jsonl` and `final_summary.json` are always retained. `best_config.json` and test events exist only after valid external-outcome selection.

Equivalent explicit command:

```bash
.venv/bin/bridgetree tune \
  --config configs/default.yaml \
  --tuning-config configs/train.yaml
```

## Ascend 910B transfer

Copy this directory and mount data/cache locations separately. Install the CANN-matched `torch` and `torch_npu` wheels from the target image, then:

```bash
pip install -r requirements-ascend910b.txt
bridgetree check-ascend --strict
bridgetree run --config configs/default.yaml --override-config configs/ascend910b.yaml --method bridgetree
```

With the default remote embedding backend BridgeTree itself uses NumPy and does not require NPU kernels. To host embeddings locally, set `models.embedding.backend: local`, point `local_model_path` to a local checkpoint, and retain `runtime.device: npu:0`. Copy or clone the repository onto the 910B host, install dependencies, and use `scripts/run_ascend.sh --method bridgetree`.

See [docs/requirements_matrix.md](docs/requirements_matrix.md) for the requirement-by-requirement implementation audit and [docs/architecture.md](docs/architecture.md) for module boundaries.
