# PDF requirement matrix

| Design requirement | Implementation evidence | Verification |
| --- | --- | --- |
| Unit embeddings and nonnegative cosine, Eq. 9–11 | `math_utils.py`, `index.py`, `retriever.py` | `test_math.py`, `test_retriever.py` |
| First-hop top `b0`, Eq. 12–13 | `BridgeTreeRetriever.retrieve` | `test_retriever.py` |
| Gram effective rank and spherical KMeans, Eq. 14–15 | `clustering.py` | `test_clustering.py` |
| Reachability-weighted probe and medoid fallback, Eq. 16–20 | `cluster_siblings` | `test_clustering.py` |
| Probe ANN and real-parent projection, Eq. 21–24 | `_expand_one`; probes and nodes use distinct types | `test_retriever.py` |
| Bottleneck path and bridge diagnostic, Eq. 25–26 | `_expand_one`, `TreeNode.bridge_lift` | `test_retriever.py` |
| Best-first frontier and `U_rho`, Eq. 27–29 | heap priority and `Branch.path_upper_bound` | `test_retriever.py` |
| Thin-SVD path-conditioned innovation, Eq. 30–36, 58 | `path_conditioned_innovation` | `test_math.py` |
| PSD log-det target and exact marginal, Eq. 37–42 | `logdet_value`, `logdet_marginal` | `test_math.py` |
| Unknown marginal bound, Eq. 43–47 | `Branch.marginal_upper_bound = log1p(U_rho^2)` | `test_retriever.py` |
| Exact commit `g >= u`, Eq. 48 | certified branch in `retrieve` | `test_retriever.py` |
| Budget freeze, per-step epsilon and weighted `Epost`, Eq. 49–56 | `SelectionStep`, `RetrievalResult.posterior_error` | `test_retriever.py`, `test_math.py` |
| Chronological final serialization and one generator call | `GeneratorClient.answer` and selected memory ordering | `test_clients.py` |
| Zero retrieval LLM calls | retriever only accepts vectors; experiment reports call counts | architecture inspection/tests |
| PersonaMem main experiment | pinned downloader, normalized split, experiment runner | `test_personamem.py`, data manifest |
| Required baselines/ablations | `baselines.py`, `experiment.METHODS` | `test_baselines.py` |
| Answer, recall, bridge, innovation, cost, certificate and gap metrics | `metrics.py`, experiment summaries | `test_metrics.py` |
| Independent gold bridge definition | optional external annotations + direct-rank partition | `test_metrics.py` |
| Code/data separation and 910B portability | project layout, config overlay, dependency files | `README.md`, `check-ascend`, `scripts/run_ascend.sh` |

Scope is intentionally faithful to the paper boundary: mathematical claims apply to the deterministic induced tree and `F_q`; answer quality is evaluated separately and is not claimed to inherit the proxy certificate.
