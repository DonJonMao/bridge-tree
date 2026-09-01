# Architecture

```text
PersonaMem raw files
  -> personamem.py (slice, normalize, provenance-preserving memory turns)
  -> clients.py (fixed embedding encoder)
  -> index.py (deterministic exact IP / optional FAISS FlatIP)
  -> retriever.py
       clustering.py: effective rank + deterministic spherical KMeans
       math_utils.py: bottleneck, thin-SVD path conditioning, log-det margin
       types.py: real tree, virtual probe branches, selection certificates
  -> clients.py (one final generation call)
  -> experiment.py + metrics.py (baselines, ablations, answer/cost/certificate metrics)
  -> training.py + module_metrics.py
       persona-disjoint split -> configuration trials -> periodic validation
       -> module-level metrics -> validation selection -> held-out final test
```

The temporary tree and probe queue have different types. `TreeNode` always owns an original `Memory`; `Branch.probe` is a NumPy vector and cannot enter the output context. All deterministic choices use stable memory IDs as the final tie-breaker.

The default exact index is the reference/proof backend. Optional `IndexFlatIP` preserves exact inner-product search while improving throughput. Approximate HNSW/IVF can be added for scale experiments, but those index states must be frozen and reported because the theorem is relative to a deterministic induced search tree.

The code has no dependency on the parent datacenter package. Paths are configuration values, model endpoints can be remote or local, and runtime outputs never mix with source or raw data.

The training runner does not mutate model weights. Its modules communicate through `RetrievalResult` plus numeric vectors, and every module metric group is independently serializable. The fixed validation probe is used only for progress diagnostics; the complete validation split selects the retrieval configuration, and the test split is not read until selection has finished.
