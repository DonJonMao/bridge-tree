# PDF requirement matrix

| Design requirement | Implementation evidence | Verification |
| --- | --- | --- |
| Unit embeddings and nonnegative cosine, Eq. 9–11 | `math_utils.py`, `index.py`, `retriever.py` | `test_math.py`, `test_retriever.py` |
| First-hop top `b0`, Eq. 12–13 | runtime `initial_width` in `BridgeTreeRetriever.retrieve` | `test_retriever.py`, `test_config.py` |
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
| PersonaMem main experiment | pinned protocol, configurable memory granularity, common prompt/token budget | `test_personamem.py`, `test_experiment.py` |
| Required baselines/ablations | `baselines.py`, `experiment.METHODS` | `test_baselines.py` |
| External-outcome-only, zero-failure tuning without an inert train loop | `training.py`, `configs/train.yaml` | `test_training.py` |
| Decoupled module metrics and ablation deltas | `module_metrics.py`, per-module JSONL outputs | `test_training.py` |
| Answer, recall, bridge, innovation, cost, certificate and gap metrics | `metrics.py`, experiment summaries | `test_metrics.py` |
| Independent gold bridge definition | optional external annotations + direct-rank partition | `test_metrics.py` |
| One runtime implementation and script-controlled module combinations | `config.py`, `retriever.py`, `run_personamem.sh`, `ablation.sh` | `test_cli.py`, `test_retriever.py` |
| Matched unique-node/ANN/candidate budgets and separate diagnostic cost | `budget.py`, dynamic baselines, `sweep` | `test_budget_index.py` |
| Exact argpartition and adaptive FAISS over-fetch | `index.py` | `test_budget_index.py` |
| Multi-seed paired bootstrap aggregation | `aggregation.py`, `main_table.sh`, `ablation.sh` | `test_aggregation.py` |
| Resolved config/hash, source checksums, commit, data/model/prompt provenance and failure log | `experiment.py`, `training.py` | `test_experiment.py`, `test_training.py` |
| Offline q→m1→m2 smoke | `smoke.py`, `smoke_synthetic.sh` | executed smoke + `test_retriever.py` |
| Hashed worktree bundle and one-command server portability | `server_bundle.py`, config overlay, dependency files | extracted-bundle test, `scripts/package_server.sh`, `scripts/train_32k.sh` |
| Independent persisted-run audit for 16 trials, 23 events, 1,855 examples, common questions and budgets | `run_audit.py`, `offline_validation.py` | `audit-tuning-run`, `scripts/validate_full_32k_offline.sh`, `test_training.py` |
| Shared leakage-safe PersonaMem rerank query and time-aware memory formatting | `ranking.py`; options are normalized and gold is never read | `test_ranking.py` |
| Instruction-aware batched embedding cache | `clients.py`, `experiment.EmbeddingCache` | `test_clients.py`, `test_experiment.py` |
| Dense floor, real-anchor guided bridge discovery, per-path filtering and final union rerank | `guided_retriever.py`, `GuidedCandidatePool` | `test_guided_retriever.py`, `test_experiment.py` |
| No duplicate Dense ANN and no legacy rho/log-det final selection in effect-first methods | reusable `initial_hits`, candidate exclusions, reranker-owned final IDs | `test_experiment.py` |
| Separate ANN/rerank/bridge-embedding accounting and traceable candidate provenance | `budget.py`, `module_metrics.py`, prediction artifacts | `test_budget_index.py`, `test_training.py` |
| Validation-only six-method matrix, point-estimate selection, report-only paired bootstrap | `run_effect_first_validation`, effect-first config/script | `test_training.py`, `test_cli.py` |

## TMIC and confirmatory-protocol requirements

| Design requirement | Implementation evidence | Verification |
| --- | --- | --- |
| T: angular-rank transition with explicit temporal overlap, `K_q` and row-stochastic `P_q` | `temporal.py`, `build_transition_matrix`, `TransitionCache` | temporal-kernel regression and cache tests; `audit-tmic` |
| Time metadata distinguishes instant, durative and unknown marks; missing time is neutral and observable | `TimeMark`, `build_time_marks`, `temporal_overlap_kernel`, `Memory.time_metadata` | time-mark/overlap tests; serialized temporal diagnostics |
| Message index is an observation order, never an implicit calendar/recency weight | `messages_to_memories`, `TimeMark.time_source=message_index` | data-schema review and temporal diagnostics |
| M: real-member mass normalization and transition propagation | `measure.py` (`branch_measure`, `normalize_member_mass`, `propagate_mass`) | posterior/mass tests; `predictions_A2+` provenance |
| M proposals use real member vectors, deterministic round-robin, and never centroids/probes | `retriever._retrieve_tmic` | proposal-vector and provenance audit |
| All positive parent posteriors and posterior-normalized path hypotheses are retained | `parent_posterior`, `enumerate_path_hypotheses`, `merge_path_hypotheses`, `RetrievalResult.path_hypotheses` | multi-parent/path audit in `run_audit.py` |
| I: frozen option-contrast basis with identity fallback and PSD path atoms | `information.py` (`StateBasisProvider`, `InformationAtom`) | basis freeze, finite/shape, PSD and log-det tests |
| I objective is fixed `logdet(I + ΣQ)` and does not fit answer labels | `InformationObjective`, `aggregate_path_atoms` | information-objective tests; protocol inspection |
| C: certificate only for explicit finite, non-overlapping exact domains with auditable bounds | `rebuild_domains_and_bounds`, `certificate_status` | `audit-tmic`; unavailable-domain regression |
| Certificate failure is explicit (`certificate_unavailable`) and budget/depth search continues | `retriever.py`, `budget.py` | C/ANN/backend and `stop_mode=budget` tests |
| A0–A4 fixed module matrix, train-free, with shared A3/A4 basis/cache and conditional generation identity | CLI `run-tmic-matrix`, `experiment.py`, `run_audit.py` | matrix smoke run and `audit-tmic` |
| Per-row provenance includes transitions, masses, paths, atoms, domains, gaps, context hash and layered cost | `RetrievalResult`, prediction serializers, `CostTracker` | persisted-artifact audit |
| Leakage-safe `confirmatory_v1` initialization, audit, freeze and phase gate | `protocol.py`, CLI `protocol` commands, `training.py` | `protocol audit`; confirmatory gate tests |
| Development-only answer-effect oracle; no logprob means `oracle_unavailable` | `oracle.py`, training/evaluation integration | oracle status tests and phase-gate checks |

TMIC claims are limited to the deterministic induced tree, transition/path
provenance, and the finite-domain search bound.  The PSD/log-det objective is a
query-state surrogate; it is not an answer-label mutual-information estimate.
Answer quality and any oracle result remain separate outcome fields.  A
certificate is never inferred from an ANN-only or otherwise incomplete domain.

Scope is intentionally faithful to the paper boundary: mathematical claims apply to the deterministic induced tree and `F_q`; answer quality is evaluated separately and is not claimed to inherit the proxy certificate.
