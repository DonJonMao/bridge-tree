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
  -> ranking.py (shared PersonaMem rank query/document formatting + atomic full-ranking cache)
  -> guided_retriever.py
       Dense candidate floor -> task-ranked real anchors -> anchor clustering
       -> batched query+anchor probes -> optional path filter -> union rerank
  -> clients.py (one final generation call)
  -> budget.py (shared SearchBudget and separate core/diagnostic CostTracker)
  -> experiment.py + metrics.py (layered outcome/cost/diagnostic records)
  -> training.py + module_metrics.py
       persona-disjoint split -> one complete validation per configuration
       -> module-level metrics -> validation selection -> held-out final test
  -> run_audit.py (independent persisted-artifact completion gate)
```

The temporary tree and probe queue have different types. `TreeNode` always owns an original `Memory`; `Branch.probe` is a NumPy vector and cannot enter the output context. All deterministic choices use stable memory IDs as the final tie-breaker.

The accuracy-first pipeline is intentionally not a replacement implementation
of the certified tree. `GuidedCandidatePool` carries candidate provenance and
stage scores without mutating `TreeNode.reachability`. In query-anchor mode,
every bridge edge points to the real memory used to construct that branch's
conditional query. Two branch queries are encoded in one batch, and the Dense
pool plus every previously proposed node is excluded from subsequent bridge
ANN calls. The final context is exactly the common task reranker's Top-k over a
stable Dense-first union and is then serialized chronologically for generation.

Exact uses `np.argpartition` followed by deterministic score/ID ordering and is intended for small validation. FAISS FlatIP starts at `top_k + exclusion_margin` and expands only when exclusions leave too few hits or a cutoff tie may be truncated; it never requests the full bank by default. Indexes are reused by shared-context cut and embedding fingerprint, and index-build time is separate from retrieval time.

The code has no dependency on the parent datacenter package. Paths are configuration values, model endpoints can be remote or local, and runtime outputs never mix with source or raw data.

The tuning runner does not mutate model weights. Its modules communicate through `RetrievalResult` plus numeric vectors, and every module metric group is independently serializable. The tree is deterministic first-arrival: a discovered memory is never reopened or reparented. Because a trial is fixed, tuning does not repeat validation around an inert train pass. The complete validation split selects a configuration only when an external outcome exists; otherwise test is not evaluated. Formal tuning returns success only after `run_audit.py` re-reads the completed files and validates protocol identity, counts, common question sets, failure logs, budgets, and module-event alignment.

`diagnostic_level=off|light|full` is enforced at the retrieval boundary. Off and light reuse core candidates and have `ann_calls_diagnostic=0`. Full diagnostics may query the index, but those calls and time are isolated from core retrieval cost.
