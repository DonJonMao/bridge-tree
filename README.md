# BridgeTree Preference-RAG

This directory is a self-contained, portable implementation of the 2026-09-01 design **“BridgeTree: 面向 Preference-RAG 的桥接感知路径条件临时记忆树检索方法”**. It keeps source code, immutable raw data, normalized data, caches, and run artifacts in separate directories so the directory can be copied to an Ascend 910B host without depending on the parent `datacenter` package.

The repository now contains two deliberately separate retrieval families. The
legacy, certificate-oriented BridgeTree path remains available unchanged:

```text
coarse ANN -> effective-rank spherical clustering -> centroid probe
-> real-parent projection -> bottleneck reachability -> path-conditioned feature
-> certified log-det greedy selection -> one generator call
```

Centroids are never inserted as memories. Retrieval makes zero LLM calls. A generator is called exactly once only when `--generate` is enabled. There is one `BridgeTreeRetriever`; Core, +Path, +Certificate and Full-current are runtime parameter combinations, not separate classes or code profiles. The project intentionally has no distillation, RL, online Judge, retrieval LLM, or model-weight training stage.

The accuracy-first path uses BridgeTree only for candidate discovery:

```text
Dense Top-W -> task rerank anchors -> anchor clusters
-> batched query+anchor bridge retrieval -> optional per-path rerank
-> stable Dense/bridge union -> task rerank Top-k -> one generator call
```

It does not mix dense, path, recency, and reranker scores into a new weighted
objective. Reranker scores never overwrite tree reachability, and certificate
stopping is rejected for the new reranker-selected BridgeTree methods.

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

# Detached one-command launch; safe to close SSH immediately afterwards.
./scripts/start_train_32k_background.sh

# Detached validation-only accuracy-first comparison.
./scripts/start_effect_first_background.sh

.venv/bin/pytest
```

The default model services match the parent `datacenter` project:

| Use | Model/service |
| --- | --- |
| Embedding | `qwen3-embedding-8b`, `http://111.19.156.74:8001/v1/embeddings` |
| Rerank comparison baseline | `http://111.19.156.74:8002/rerank` |
| Final generator | `deepseek-v4-flash`, `http://111.19.156.30:8006/v1/chat/completions` |

Dense query embeddings use a PersonaMem retrieval instruction; memory documents
are encoded without that prefix. Bridge queries use a separate explicit
query+anchor instruction, which is included in the embedding-cache identity.

The generator credential is intentionally not stored in the repository. Set
`BRIDGETREE_CHAT_API_KEY` on the Linux host (or provide an explicit local
overlay) before enabling generation. Legacy BridgeTree still uses its original
proxy objective; the new `*_rerank` methods form a separate, non-certified
family whose final selection is owned by the common task-aware reranker.

## Train-free conditional-activation Chain run

The current production Chain entry point uses a separate fixed-target
conditional-activation implementation. It scores complete sets with the frozen
pointwise reranker, uses `q + target + premises` only to propose additional
real memories, and performs a fresh bundle-marginal comparison after every
final selection. Legacy tree and Chain planning entry points remain available.

```bash
# After extracting the server bundle on Linux, this creates/reuses .venv,
# validates all 589 questions / 2,945 tasks without model calls, and starts
# the detached worker only if every preflight assertion passes.
bash scripts/start_chain_linux.sh configs/chain_full.yaml

# Complete 589-question / 2,945-task data check; no service calls.
PYTHONPATH=src python -m bridgetree chain-run \
  --config configs/chain_full.yaml \
  --output-dir outputs/chain/data_check \
  --preflight-only

# Detached server execution and exact-directory resume.
bash scripts/run_chain.sh start configs/chain_full.yaml
bash scripts/run_chain.sh status
bash scripts/run_chain.sh log
bash scripts/run_chain.sh module-log effectiveness
bash scripts/run_chain.sh module-log effectiveness-current
bash scripts/run_chain.sh resume
```

This run is train-free inference/evaluation, not model-weight training:
`optimizer_steps=0` and `weights_updated=false`. The one-command Linux launcher
requires Linux, Bash, Python 3.9+ with `venv`, access to Python package sources
on first install, at least 20 GiB free by default, and reachable configured
embedding/reranker/generator services. Credentials remain outside the bundle;
use `BRIDGETREE_CHAT_API_KEY` or a mode-0600 sibling
`configs/credentials.local.yaml`.

See [the migration and server guide](docs/conditional_activation_migration.md)
for the mathematical contract, resource accounting, artifacts, limitations,
and all lifecycle commands. The preserved acceptance contract is in
[the implementation goal](docs/conditional_activation_goal.md), with the
[original supplied text](docs/conditional_activation_goal_source.txt) beside it.

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

## TMIC: the four composable operators

The TMIC path is one train-free execution chain.  It is selected with the four
boolean retrieval switches and does not add a learned utility or a reward
weight:

```text
T (temporal measure) -> M (real-member mass propagation)
  -> I (query-state PSD information atoms) -> C (finite-domain certificate)
```

`T` builds an angular-rank relation and multiplies it by a Jaccard measure of
explicit instant/interval time marks.  Missing time is neutral and is recorded
as `time_unavailable`; message indices are ordered observations, never calendar
dates.  `M` normalizes the non-negative first-hop member mass and propagates it
through the row-stochastic transition matrix.  When enabled, ANN proposals are
made from every real branch member in deterministic round-robin order; a
centroid/probe is never used as a memory or as the M proposal vector.

`I` constructs a frozen orthonormal state basis from centered answer-option
embeddings.  It uses the identity basis with
`state_basis_fallback=identity` when options are absent, and combines
path-conditioned PSD atoms with the fixed `logdet(I + sum Q)` objective.  This
is a query-conditioned linear-Gaussian/Fisher-style surrogate, not a claim of
label-estimated mutual information.  `C` is conservative search accounting
only: it can certify a next greedy item only over an explicit finite
`exact_partition` domain.  If the domain, time envelope, basis, or exact index
cannot be audited, the result is `certificate_unavailable` and the configured
budget/depth continues to apply.

The fixed module matrix is available without tuning:

| Row | T | M | I | C | Meaning |
| --- | ---: | ---: | ---: | ---: | --- |
| A0 | 0 | 0 | 0 | 0 | R1 path-conditioned reference |
| A1 | 1 | 0 | 0 | 0 | Add temporal measure |
| A2 | 1 | 1 | 0 | 0 | Add real-member propagation |
| A3 | 1 | 1 | 1 | 0 | Add query-state PSD atoms |
| A4 | 1 | 1 | 1 | 1 | Add finite-domain certificate |

Run a development matrix with deterministic local embeddings, then audit every
serialized row:

```bash
python -m bridgetree.cli run-tmic-matrix \
  --phase development --limit 20 --no-generate --offline \
  --output-dir outputs/tmic
python -m bridgetree.cli audit-tmic \
  --input-dir outputs/tmic/tmic_development_<timestamp> --raise-on-error
```

Each `predictions_A*.jsonl` record keeps greedy and chronological IDs,
`nodes`/`edges`, transition `K/P` diagnostics, branch `mass`/`support`, all
posterior paths, PSD information atoms, exact domains and bound ingredients,
selection gaps, context hash, outcome, cost, and diagnostic provenance.  A3 and
A4 share the same frozen basis and generation cache; equal context hashes must
produce the same generation response.

The leakage-safe protocol is initialized once from the pinned PersonaMem
source.  Development code may use the persisted `development-seen` role (an
explicitly named internal persona split); confirmatory execution requires a
frozen manifest and rejects `tune`, `train`, and configuration rewrites:

```bash
python -m bridgetree.cli protocol init
python -m bridgetree.cli protocol audit --protocol confirmatory_v1
python -m bridgetree.cli protocol freeze \
  --protocol confirmatory_v1 --config-hash <resolved-config-sha256>
```

The answer-effect oracle is development-only and requires token log
probabilities.  Services without log probabilities emit
`oracle_unavailable`; no guessed answer effect is used for selection.

## Experiments

`--method` supports every baseline or ablation required by the design:

- `dense`, `rfmem_familiarity`, `rfmem_recollection`, `rfmem`
- `cluster_prf` (cluster pseudo-relevance feedback without cognitive claims)
- `bridgetree`
- `ablation_no_cluster`, `ablation_bfs`, `ablation_fixed_depth`
- `ablation_topk`, `ablation_rho_dpp`, `ablation_direct_path`
- `dense_rerank` remains the compatibility alias for `dense_rerank_20`
- `dense_rerank_20`, `dense_rerank_28`, `bridgetree_union_rerank`
- `bridgetree_guided_rerank`, `bridgetree_guided_pathfilter`, `full_pool_rerank`

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

## Accuracy-first reranker-guided validation

The prior formal 32K run showed Dense+rerank at 51/73 (69.86%) and legacy
BridgeTree at 41/73 (56.16%). Legacy BridgeTree discovered eight second-hop
nodes in a 20-node pool, while 71.78% of its final context came from the second
hop. The effect-first experiment therefore tests candidate discovery separately
from final selection instead of treating path reachability as answer utility.

Run the six-method, persona-disjoint validation matrix with one command:

```bash
./scripts/start_effect_first_background.sh
```

The command returns immediately and the job continues after SSH disconnects.
No `tmux`, `nohup`, redirection, PID command, or manual `jq` pipeline is needed.
Its fixed files are under `outputs/background/`:

```text
effect_first.log                 complete stdout + stderr
effect_first.status.json         running/completed/failed, PID, timestamps, duration, exit code
effect_first.exit                numeric exit code after completion
effect_first.run_dir             exact timestamped artifact directory
effect_first.summary.json        copied final effect summary
effect_first.results.csv         copied comparison table
effect_first.paired_results.json copied paired analysis
```

Two short commands provide status and the latest 100 log lines:

```bash
./scripts/start_effect_first_background.sh status
./scripts/start_effect_first_background.sh log
```

Starting again while it is live reports `already_running`. Starting after it
finishes moves the previous fixed files into `outputs/background/history/` and
creates a fresh fixed set.

It evaluates only the validation personas and records `test_queries_read: 0`.
The matrix contains Dense-Rerank-20, the candidate-count control
Dense-Rerank-28, union reranking over legacy BridgeTree discoveries, two guided
versions, and a full-memory-pool diagnostic ceiling. Method selection uses the
validation accuracy point estimate; cost breaks only an exact accuracy tie.
Paired bootstrap intervals are report-only.

Every prediction preserves Dense, anchor, raw bridge, kept bridge, and final
union IDs; real parent/branch provenance; ANN, path-filter, and final reranker
scores; and separate ANN, reranker, bridge-embedding, and generation costs.
Complete rankings are cached by endpoint, model, query, and ordered documents.
Cache hits still count logical reranker documents for fair algorithm-cost
comparison, while cached wall time is reported as zero.

Width and protocol settings can be changed without editing source:

```bash
DENSE_POOL_WIDTH=20 ANCHOR_WIDTH=12 \
EXPAND_BRANCH_COUNT=2 BRANCH_OVERFETCH_WIDTH=8 BRANCH_KEEP_WIDTH=4 \
PATH_FILTER=true ./scripts/run_effect_first_validation.sh
```

See [docs/effect_first_reranker.md](docs/effect_first_reranker.md) for the old
result diagnosis, exact method definitions, artifacts, and interpretation rules.
See [docs/background_runs.md](docs/background_runs.md) for both detached launchers
and every fixed output file.

## Configuration tuning and module diagnostics

`./scripts/train_32k.sh` is the portable formal entrypoint. It installs the editable project and test tools, validates the pinned 32K data checksums, runs tests/Ruff/offline smoke, checks embedding/generator/reranker services, invokes `bridgetree tune`, and then independently audits the persisted run before returning success. It also repairs an unusable copied `.venv`; all Python tools are called with `python -m ...`, so stale console-script shebangs cannot redirect execution to the old server path.

The formal configuration uses a persona-disjoint 70/15/15 split. Each of the 16 retrieval configurations is evaluated exactly once on the complete validation partition. The train partition is reserved but not traversed: configurations are fixed and no model or retrieval parameter is updated during a train pass. Internal log-det, path-objective and certificate metrics are never tuning objectives:

- with generated validation answers, `outcome.answer_accuracy` is used;
- with independent memory gold, validation recall is used;
- with neither, all trials and a cost Pareto report are written, but there is no `best_config.json` and test is not evaluated.

`configs/train.yaml` is the full 32K answer-accuracy protocol: widths `8/12`, branch widths `4/8`, node budgets `20/28/36/44`, generation enabled on validation and test, and strict zero-failure evaluation. Any query exception aborts selection after it is recorded in `failures.jsonl`; a method can never improve its score by failing on difficult questions. When a best configuration is externally justified, every final main-table method uses the same generator, prompt, segmentation, chronological serialization, final `k`, context token budget and output token budget.

The dataset is self-contained in this repository, not under the sibling `datacenter` project:

- raw input: `data/raw/personamem-v1`
- normalized data: `data/processed/personamem-v1/32k`

Each tuning run creates `outputs/tuning-32k/tune_<timestamp>/`. `run_status.json` records `running`, `failed`, or `completed`; `progress.json` is atomically refreshed on query 1, every 10 queries, at the end of each evaluation set, and with a terminal `completed` or `failed` state. `events.jsonl` and `metrics.csv` contain validation/test events; every summary records attempted/successful/failed query counts and question-set hashes. `modules/*.jsonl` separates encoding, coarse retrieval, clustering, path, innovation, selection, search, cost, outcome and timing. `pareto_frontier.json`, `trials.json`, `resolved_config.json`, `run_manifest.json`, `failures.jsonl`, `final_summary.json`, and the post-run `completion_audit.json` are retained. `best_config.json` and test events exist only after valid external-outcome selection.

Equivalent explicit command:

```bash
.venv/bin/bridgetree tune \
  --config configs/default.yaml \
  --tuning-config configs/train.yaml \
  --audit-full-32k
```

To validate a copied server without starting the expensive run:

```bash
PREFLIGHT_ONLY=true ./scripts/train_32k.sh
```

To exercise the complete 16-trial/84-validation/73-test/seven-method scheduler without contacting model services:

```bash
./scripts/validate_full_32k_offline.sh
```

This command uses conspicuously named deterministic fake clients and writes `OFFLINE_VALIDATION_REPORT.json`; its answer scores are never experiment results. It exists solely to validate full-size scheduling, strict failure accounting, common question sets, checkpoints, and the same independent completion audit used by the formal launcher.

The current pinned data produces 84 validation and 73 test questions. The 16-trial, seven-method protocol therefore estimates 1,855 generator calls. See [docs/full_32k_tuning.md](docs/full_32k_tuning.md) for launcher controls and artifact-level success checks.

## Ascend 910B transfer

Build a checked server archive from the current worktree (including uncommitted fixes and pinned 32K data):

```bash
./scripts/package_server.sh
```

The command writes `dist/server/*.tar.gz` plus a transport `.sha256` sidecar, verifies every bundled file against an embedded SHA-256/permission manifest, extracts it into a fresh temporary path, and runs the offline launcher preflight there. It excludes `.git`, `.venv`, outputs, caches, and build products.

Copy and extract that archive on the server. With remote embedding/generation services, enter the extracted `bridgetree_preference_rag` directory and run one detached command:

```bash
./scripts/start_train_32k_background.sh
```

For local NPU-hosted embeddings, install the CANN-matched `torch` and `torch_npu` wheels from the target image, then:

```bash
pip install -r requirements-ascend910b.txt
bridgetree check-ascend --strict
bridgetree run --config configs/default.yaml --override-config configs/ascend910b.yaml --method bridgetree
```

With the default remote embedding backend BridgeTree itself uses NumPy and does not require NPU kernels. To host embeddings locally, set `models.embedding.backend: local`, point `local_model_path` to a local checkpoint, and retain `runtime.device: npu:0`. Copy or clone the repository onto the 910B host, install dependencies, and use `scripts/run_ascend.sh --method bridgetree`.

See [docs/requirements_matrix.md](docs/requirements_matrix.md) for the requirement-by-requirement implementation audit and [docs/architecture.md](docs/architecture.md) for module boundaries.
