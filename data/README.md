# Data layout

Data is deliberately separate from source code:

```text
data/
  raw/personamem-v1/          # official immutable downloads
  processed/personamem-v1/    # normalized JSONL + checksummed manifest
```

`download-personamem` pins `bowen-upenn/PersonaMem-v1` at revision `fd7c30f...` and downloads matching `questions_[SIZE].csv` and `shared_contexts_[SIZE].jsonl` files. The 32k split is the default because it is the primary practical development split; repeat `--split` to prepare 128k or 1M.

`prepare-personamem` validates foreign keys, converts questions/contexts to stable JSONL, and emits `manifest.json` with counts and SHA-256 hashes. Runtime slicing still uses the official `end_index_in_shared_context` field, preventing future messages from leaking into a query.

PersonaMem does not ship evidence-memory annotations. Independent bridge annotations must be JSONL:

```json
{"question_id":"official-question-uuid","gold_memory_ids":["official-question-uuid:m00012"]}
```

Annotators or a separate answer-supported evidence process must create these IDs. Evaluation defines the bridge subset as annotated gold memories whose direct query rank exceeds `k`; it never uses BridgeTree's `bridge_lift` as gold.
