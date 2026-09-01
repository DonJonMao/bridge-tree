# BridgeTree Preference-RAG

This directory is a self-contained, portable implementation of the 2026-09-01 design **“BridgeTree: 面向 Preference-RAG 的桥接感知路径条件临时记忆树检索方法”**. It keeps source code, immutable raw data, normalized data, caches, and run artifacts in separate directories so the directory can be copied to an Ascend 910B host without depending on the parent `datacenter` package.

The proof-aligned online chain is:

```text
coarse ANN -> effective-rank spherical clustering -> centroid probe
-> real-parent projection -> bottleneck reachability -> path-conditioned feature
-> certified log-det greedy selection -> one generator call
```

Centroids are never inserted as memories. Retrieval makes zero LLM calls. A generator is called exactly once only when `--generate` is enabled. The method intentionally has no distillation, RL, or task-level training stage; “deployment on 910B” means model inference/runtime portability, not adding a training procedure that contradicts the design.

## Quick start

```bash
cd bridgetree_preference_rag
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'

# Official PersonaMem-v1 32k split, pinned to a repository revision.
.venv/bin/bridgetree download-personamem --split 32k
.venv/bin/bridgetree prepare-personamem --split 32k

# Retrieval-only experiment (zero LLM calls).
.venv/bin/bridgetree run --method bridgetree --limit 10

# End-to-end experiment (one deepseek-v4-flash call per query).
.venv/bin/bridgetree run --method bridgetree --limit 10 --generate

# Required baseline/ablation suite and effect-cost-gap budget curve.
.venv/bin/bridgetree sweep --budget 32 --budget 64 --limit 10

# One-click training-free configuration search with periodic validation.
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

## Experiments

`--method` supports every baseline or ablation required by the design:

- `dense`, `rfmem_familiarity`, `rfmem_recollection`, `rfmem`
- `cluster_prf` (cluster pseudo-relevance feedback without cognitive claims)
- `bridgetree`
- `ablation_no_cluster`, `ablation_bfs`, `ablation_fixed_depth`
- `ablation_topk`, `ablation_rho_dpp`, `ablation_direct_path`
- `dense_rerank` additionally exercises the datacenter reranker endpoint

Every BridgeTree prediction records the real tree, all probe branches, reachability, bridge lift, innovation norm, greedy margins, unseen bounds, per-step epsilon, `Epost`, ANN calls, visited nodes, certificate status, budget status, and cluster radii. Summary files report certified-stop rate, budget-truncation rate, posterior gap, cost, and latency.

PersonaMem-v1 does not provide gold memory IDs. `Recall@k` and `Bridge Recall@k` are therefore only computed when `--bridge-gold` supplies independent annotations in the schema described in [data/README.md](data/README.md). The implementation never defines gold bridge memories using its own bridge-lift score.

## One-click training and module diagnostics

BridgeTree has no model-weight training stage. `./scripts/train.sh` performs the design-compatible equivalent: deterministic retrieval-configuration search. It splits PersonaMem by persona (70% train, 15% validation, 15% test), runs a small validation probe every 50 train queries, selects the configuration only on full validation metrics, and evaluates the held-out test personas once at the end. Edit `configs/train.yaml` to change the search space, evaluation frequency, query limits, or objective.

The dataset is self-contained in this repository, not under the sibling `datacenter` project:

- raw input: `data/raw/personamem-v1`
- normalized data: `data/processed/personamem-v1/32k`

Each run creates `outputs/training/train_<timestamp>/`. `events.jsonl` and `metrics.csv` contain train-progress, validation-probe, validation, and final-test metrics. `modules/*.jsonl` separates encoding, coarse retrieval, clustering, path construction, innovation, selection, search, outcome, and timing metrics. `module_effects.jsonl` reports full BridgeTree minus each ablation, while `best_config.json` and `final_summary.json` contain the selected configuration and final results. Generator calls remain disabled unless `final_generate: true`; hyperparameter search itself never calls the generator.

Equivalent explicit command:

```bash
.venv/bin/bridgetree train \
  --config configs/default.yaml \
  --training-config configs/train.yaml
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
