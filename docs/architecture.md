# Architecture

```text
PersonaMem raw files
  -> personamem.py (slice, normalize, provenance-preserving memory turns)
  -> clients.py (fixed embedding encoder)
  -> index.py (float32 argpartition Exact / adaptive-overfetch FAISS FlatIP)
  -> retriever.py
       clustering.py: effective rank + deterministic spherical KMeans
       math_utils.py: bottleneck, thin-SVD path conditioning, log-det margin
       types.py: real tree, virtual probe branches, selection certificates
  -> clients.py (one final generation call)
  -> budget.py (shared SearchBudget and separate core/diagnostic CostTracker)
  -> experiment.py + metrics.py (layered outcome/cost/diagnostic records)
  -> training.py + module_metrics.py
       persona-disjoint split -> configuration trials -> periodic validation
       -> module-level metrics -> validation selection -> held-out final test
```

The temporary tree and probe queue have different types. `TreeNode` always owns an original `Memory`; `Branch.probe` is a NumPy vector and cannot enter the output context. All deterministic choices use stable memory IDs as the final tie-breaker.

Exact uses `np.argpartition` followed by deterministic score/ID ordering and is intended for small validation. FAISS FlatIP starts at `top_k + exclusion_margin` and expands only when exclusions leave too few hits or a cutoff tie may be truncated; it never requests the full bank by default. Indexes are reused by shared-context cut and embedding fingerprint, and index-build time is separate from retrieval time.

The code has no dependency on the parent datacenter package. Paths are configuration values, model endpoints can be remote or local, and runtime outputs never mix with source or raw data.

The tuning runner does not mutate model weights. Its modules communicate through `RetrievalResult` plus numeric vectors, and every module metric group is independently serializable. The tree is deterministic first-arrival: a discovered memory is never reopened or reparented. The fixed validation probe is progress diagnostics only. The complete validation split selects a configuration only when an external outcome exists; otherwise test remains unread.

`diagnostic_level=off|light|full` is enforced at the retrieval boundary. Off and light reuse core candidates and have `ann_calls_diagnostic=0`. Full diagnostics may query the index, but those calls and time are isolated from core retrieval cost.
