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

## Temporal metadata

Normalized memory records may carry a `metadata.time` object.  The portable
schema is:

```json
{
  "observed_start": 12,
  "observed_end": 12,
  "event_start": "2025-02-01T00:00:00Z",
  "event_end": null,
  "validity": "instant",
  "time_source": "explicit"
}
```

`validity` is one of `instant`, `durative`, or `unknown`.  An instant has one
event point; a durative mark has an event interval (open-ended endpoints are
treated as the available endpoint); and an unknown mark contributes the neutral
temporal overlap of `1` while being reported as `time_unavailable`.  The
`observed_*` fields describe when a record was observed, whereas
`event_*` fields describe the event being compared.  Explicit event fields take
precedence in the temporal kernel.

When a source has no event timestamps, preprocessing records the source message
indices as `observed_start`/`observed_end` with
`time_source: "message_index"`.  These indices define ordering and cutoffs
within a conversation only; they are not calendar dates and are never used as
a recency weight.  A caller may provide query-level `query_time`, `query_date`,
`cutoff`, or a structured `query_metadata` mark.  Absent query or memory time is
preserved as unknown rather than guessed from wall-clock time.

## Protocol and TMIC artifacts

The persisted `confirmatory_v1` manifest records the disjoint
`development-seen` and `confirmatory-test` persona/question roles plus their
stable hashes; `full-benchmark` is their materialized union.  An internal
persona split inside `development-seen` must be labeled as such and does not
redefine the confirmatory partition.

`run-tmic-matrix` writes one `predictions_A*.jsonl` stream for the fixed A0–A4
T/M/I/C rows.  Each record retains memory IDs and chronological context order,
the `K`/`P` transition and time diagnostics, real-member mass and posterior
paths, PSD information atoms, exact-domain/bound provenance, selection gaps,
context hash, and separate outcome/cost/diagnostic fields.  A3 and A4 use the
same frozen state basis and generation response for a question.  If exact
finite-domain conditions cannot be verified, the row records
`certificate_unavailable`; it must continue under the configured budget/depth.
