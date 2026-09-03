# Full PersonaMem-v1 32K tuning

This run performs training-free retrieval-configuration selection. It does not update embedding, generator, reranker, or BridgeTree model weights.

## One-command server launch

Create a migration artifact from the current worktree:

```bash
./scripts/package_server.sh
```

The resulting `dist/server/bridgetree_preference_rag_server_*.tar.gz` includes the formal code/configuration and pinned raw/processed 32K data; copy its adjacent `.tar.gz.sha256` file as the transport checksum. `SERVER_BUNDLE_MANIFEST.json` contains every payload path, SHA-256, byte size, and permission mode. Packaging automatically validates the archive, extracts it to a fresh temporary directory, and executes the offline launcher preflight from that new path. `.git`, `.venv`, outputs, caches, egg metadata, and build products are excluded.

After copying or extracting the bundle on the server, run from the extracted project root:

```bash
sha256sum -c bridgetree_preference_rag_server_*.tar.gz.sha256
tar -xzf bridgetree_preference_rag_server_*.tar.gz
cd bridgetree_preference_rag
./scripts/start_train_32k_background.sh
```

The launcher returns immediately and survives SSH logout. All console output,
state, PID, timestamps, duration, exit code, exact run directory, final summary,
completion audit, and best configuration are exposed through fixed paths under
`outputs/background/`. Use `./scripts/start_train_32k_background.sh status` or
`./scripts/start_train_32k_background.sh log`; no `tmux`, redirection, or manual
PID bookkeeping is required.

The launcher performs these gates before tuning:

1. Selects a runnable `BRIDGETREE_PYTHON`, or creates/repairs `.venv` with `python3 -m venv --clear`.
2. Installs the project and verification dependencies with `python -m pip`.
3. Downloads the pinned 32K source only if the tracked raw files are absent, and prepares it only if the manifest is absent.
4. Runs the complete unit suite, Ruff, and the offline q→m1→m2 smoke.
5. Verifies raw-file checksums, all 589 parsed questions, the pinned seed/split/retrieval protocol, the exact 16-trial grid, the external answer objective, and strict failure handling.
6. Sends one schema check to each service needed by the configured main table: embedding, generator, and reranker.
7. Starts `bridgetree tune` only if every gate succeeds.
8. Re-reads the completed artifacts independently and returns success only if `completion_audit.json.status=passed`.

No copied console script is executed. Calling tools through the selected interpreter (`python -m ...`) prevents a copied `.venv/bin/pytest` or `.venv/bin/bridgetree` shebang from pointing back to the source machine.

## Protocol

The pinned seed-42 partition is:

| Partition | Personas | Questions | Use |
| --- | ---: | ---: | --- |
| Train | 14 | 432 | Reserved; never traversed because trials do not learn |
| Validation | 3 | 84 | Full external answer-accuracy selection |
| Test | 3 | 73 | Full seven-method main table after selection |

The search space is `2 × 2 × 4 = 16` trials:

```yaml
initial_width: [8, 12]
branch_width: [4, 8]
search_budget: [20, 28, 36, 44]
```

Only `bridgetree` runs during configuration search. Ablations remain a separate post-selection experiment. The final main table contains Dense, Dense+rerank, RF-Mem Familiarity, RF-Mem Recollection, routed RF-Mem, cluster-PRF, and BridgeTree. The formal run estimates 1,855 generator calls (`84 × 16 + 73 × 7`).

## Useful controls

```bash
# Run every gate but stop before tuning.
PREFLIGHT_ONLY=true ./scripts/train_32k.sh

# Use an already prepared interpreter or environment.
BRIDGETREE_PYTHON=/path/to/python BOOTSTRAP=false ./scripts/train_32k.sh

# Apply server-local endpoint/cache/device settings.
OVERRIDE_CONFIG=configs/server.yaml ./scripts/train_32k.sh

# Select another artifact root without editing YAML.
OUTPUT_DIR=/data/bridgetree/tuning-32k ./scripts/train_32k.sh
```

`RUN_CHECKS=false`, `CHECK_SERVICES=false`, and `DOWNLOAD_DATA=false` are available for controlled debugging, but should not be disabled for a formal run. `APP_CONFIG` and `TUNING_CONFIG` replace their respective default paths.

`scripts/train_32k.sh` remains the foreground implementation used by CI and the
bundle verifier. For normal server use, `scripts/start_train_32k_background.sh`
runs it in a detached process group and persists the authoritative exit status.

## Full-size offline scheduler validation

The following command executes the exact complete split/search/method schedule with local deterministic fake clients and no network calls:

```bash
./scripts/validate_full_32k_offline.sh
```

It must produce 16 validation events over 84 questions, seven test events over 73 common questions, 1,855 `example_metrics.jsonl` rows, an empty failure log, `best_config.json`, `run_status.json.status=completed`, and `completion_audit.json.status=passed`. Its output is rooted at `outputs/offline-full-32k-validation` and every model/endpoint/report is explicitly labelled `offline`; the answer accuracy and chosen trial are synthetic and must never be reported as experiment results.

## Failure and completion criteria

Each run is written under `outputs/tuning-32k/tune_<timestamp>/` unless `OUTPUT_DIR` overrides the parent. A query exception is appended to `failures.jsonl` and immediately aborts formal tuning. Failed queries are never removed from an accuracy denominator and cannot make a configuration look better.

`run_status.json` is the scheduler lifecycle marker (`running`, `failed`, or `completed`). `progress.json` is replaced atomically at query 1, every 10 queries, the end of each validation/test method, and the terminal transition; it records the current phase, trial, method, last question ID, counts, and timestamp while running, then becomes `completed` or `failed`. Long-running trials therefore remain observable before their aggregate event is complete.

The launcher automatically runs the artifact audit. It can also be repeated without contacting model services:

```bash
python -m bridgetree.cli audit-tuning-run \
  --run-dir outputs/tuning-32k/tune_<timestamp> \
  --require-full-32k
```

A completed formal run must satisfy all of the following:

- `failures.jsonl` is empty.
- `run_status.json.status` is `completed` and `run_status.json.failure_count` is `0`.
- `progress.json.status` is `completed`.
- `final_summary.json.selection_status` is `selected_on_external_validation_outcome`.
- `final_summary.json.best_trial` is non-null and `best_config.json` exists.
- Every validation/test summary has equal `attempted_queries` and `successful_queries`, `failed_queries = 0`, and `failure_rate = 0`.
- All seven test methods have the same `successful_question_id_sha256`, matching `common_test_question_id_sha256`.
- `final_summary.json.evaluated_validation_queries = 84` and `evaluated_test_queries = 73` for the pinned seed/configuration.
- `completion_audit.json.status` is `passed`; it independently verifies source hashes, configuration hashes, event/example counts, unique-node and context budgets, parse-failure threshold, module records, and absence of temporary files.

If a service failure aborts a run, fix the endpoint and start the launcher again. Embedding files under `outputs/cache` are content-addressed and reused; a fresh timestamped run directory preserves the failed attempt as evidence.
