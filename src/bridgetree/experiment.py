from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from copy import copy
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

from .baselines import BaselineResult, cluster_prf, dense_retrieval, rfmem, rfmem_recollection
from .budget import CostTracker, SearchBudget
from .clients import (
    Embedder,
    GeneratorClient,
    RerankerClient,
    context_token_count,
    fit_context_budget,
    generation_prompt_hash,
)
from .config import AppConfig
from .guided_retriever import RerankerGuidedBridgeRetriever, cached_rerank_all
from .index import ExactInnerProductIndex, build_index
from .metrics import (
    answer_accuracy,
    answer_parse_failed,
    bridge_recall_at_k,
    direct_ranks,
    path_objective_advantage,
    recall_at_k,
)
from .personamem import PERSONAMEM_REVISION, PersonaMemExample, iter_examples, messages_to_memories
from .ranking import RerankCache, build_personamem_rank_query, format_memory_document, stable_union
from .retriever import BridgeTreeRetriever
from .types import Memory, RetrievalResult

METHODS = (
    "bridgetree",
    "dense",
    "dense_rerank",
    "dense_rerank_20",
    "dense_rerank_28",
    "bridgetree_union_rerank",
    "bridgetree_guided_rerank",
    "bridgetree_guided_pathfilter",
    "full_pool_rerank",
    "rfmem_familiarity",
    "rfmem_recollection",
    "rfmem",
    "cluster_prf",
    "ablation_no_cluster",
    "ablation_bfs",
    "ablation_fixed_depth",
    "ablation_topk",
    "ablation_rho_dpp",
    "ablation_direct_path",
)

RERANK_METHODS = {
    "dense_rerank",
    "dense_rerank_20",
    "dense_rerank_28",
    "bridgetree_union_rerank",
    "bridgetree_guided_rerank",
    "bridgetree_guided_pathfilter",
    "full_pool_rerank",
}

GUIDED_METHODS = {"bridgetree_guided_rerank", "bridgetree_guided_pathfilter"}
BRIDGE_RERANK_METHODS = GUIDED_METHODS | {"bridgetree_union_rerank"}
EFFECT_FIRST_METHODS = RERANK_METHODS - {"dense_rerank"}


ABLATION_OPTIONS = {
    "bridgetree": {},
    "ablation_no_cluster": {"cluster_mode": "none"},
    "ablation_bfs": {"search_order": "bfs"},
    "ablation_fixed_depth": {"max_depth": 3, "stop_mode": "budget"},
    "ablation_topk": {"selection_mode": "rho_topk", "stop_mode": "budget"},
    "ablation_rho_dpp": {
        "feature_mode": "rho",
        "selection_mode": "rho_logdet",
        "stop_mode": "budget",
    },
    "ablation_direct_path": {
        "feature_mode": "rho",
        "selection_mode": "rho_topk",
        "stop_mode": "budget",
    },
}


class EmbeddingCache:
    def __init__(
        self,
        root: str | Path,
        embedder: Embedder,
        model_name: str,
        embedding_identity: Mapping[str, Any] | None = None,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder
        self.model_name = model_name
        self.embedding_identity = dict(embedding_identity or {"model": model_name})

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.embedding_identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cached(self, texts: Sequence[str], purpose: str, encode, instruction: str | None = None) -> np.ndarray:
        payload = json.dumps(
            {
                "embedding": self.embedding_identity,
                "instruction": instruction,
                "purpose": purpose,
                "texts": list(texts),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        path = self.root / f"{key}.npy"
        if path.exists():
            value = np.load(path, allow_pickle=False)
            if len(value) == len(texts):
                return np.asarray(value, dtype=np.float32)
        value = np.asarray(encode(), dtype=np.float32)
        np.save(path, value, allow_pickle=False)
        return value

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._cached(texts, "document", lambda: self.embedder.encode(texts))

    def encode_query(
        self,
        text: str,
        instruction: str | None = None,
        purpose: str = "query",
    ) -> np.ndarray:
        if instruction is not None:
            return self.encode_queries([text], instruction=instruction, purpose=purpose)[0]
        method = getattr(self.embedder, "encode_query", None)
        encode = (lambda: np.asarray([method(text)])) if callable(method) else (lambda: self.embedder.encode([text]))
        return self._cached([text], purpose, encode, instruction=None)[0]

    def encode_queries(self, texts: Sequence[str], instruction: str, purpose: str) -> np.ndarray:
        method = getattr(self.embedder, "encode_queries", None)
        encode = (
            (lambda: method(texts, instruction=instruction))
            if callable(method)
            else (lambda: self.embedder.encode([instruction + text for text in texts]))
        )
        return self._cached(texts, purpose, encode, instruction=instruction)


class IndexCache:
    """Reuse an index for an identical context cut and embedding fingerprint."""

    def __init__(self):
        self._indexes: Dict[str, ExactInnerProductIndex] = {}

    def get(
        self,
        context_key: str,
        embedding_fingerprint: str,
        backend: str,
        ids: Sequence[str],
        vectors: np.ndarray,
        exclusion_margin: int,
    ) -> tuple[ExactInnerProductIndex, float, bool]:
        vector_fingerprint = hashlib.sha256(np.asarray(vectors, dtype=np.float32).tobytes()).hexdigest()
        payload = json.dumps(
            {
                "context": context_key,
                "embedding": embedding_fingerprint,
                "backend": backend,
                "vectors": vector_fingerprint,
                "exclusion_margin": exclusion_margin,
            },
            sort_keys=True,
        )
        key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if key in self._indexes:
            cached = self._indexes[key]
            if cached.ids == list(ids):
                return cached, 0.0, True
            aliased = copy(cached)
            aliased.ids = list(ids)
            aliased.position = {memory_id: index for index, memory_id in enumerate(ids)}
            return aliased, 0.0, True
        started = time.perf_counter()
        index = build_index(backend, ids, vectors, exclusion_margin=exclusion_margin)
        build_ms = (time.perf_counter() - started) * 1000.0
        self._indexes[key] = index
        return index, build_ms, False


def _selected_memories(ids: Iterable[str], memory_by_id: Mapping[str, Memory], chronological: bool) -> List[Memory]:
    selected = [memory_by_id[memory_id] for memory_id in ids]
    if chronological:
        selected.sort(key=lambda memory: (memory.timestamp, memory.memory_id))
    return selected


def _refresh_rerank_selection_diagnostics(
    diagnostics: Dict[str, Any],
    selected_ids: Sequence[str],
) -> None:
    """Make selection diagnostics describe the token-budget-retained context."""
    if "selected_source_by_id" not in diagnostics:
        return
    bridge_ids = set(diagnostics.get("bridge_kept_ids", ()))
    source_by_id = diagnostics.get("selected_source_by_id", {})
    diagnostics["selected_source_by_id"] = {
        memory_id: source_by_id.get(memory_id, "bridge" if memory_id in bridge_ids else "dense")
        for memory_id in selected_ids
    }
    selected_bridge_count = sum(memory_id in bridge_ids for memory_id in selected_ids)
    diagnostics["selected_bridge_count"] = selected_bridge_count
    diagnostics["selected_bridge_rate"] = selected_bridge_count / len(selected_ids) if selected_ids else 0.0
    dense_top_ids = diagnostics.get("dense_rerank_top_ids")
    if dense_top_ids is not None:
        dense_top = set(dense_top_ids)
        diagnostics["dense_rerank_top5_retention"] = (
            sum(memory_id in dense_top for memory_id in selected_ids) / len(dense_top) if dense_top else 0.0
        )


def retrieve_method(
    method: str,
    config: AppConfig,
    example: PersonaMemExample,
    memories: Sequence[Memory],
    query_vector: np.ndarray,
    memory_vectors: np.ndarray,
    reranker: RerankerClient | None = None,
    index: ExactInnerProductIndex | None = None,
    budget: SearchBudget | None = None,
    cost_tracker: CostTracker | None = None,
    index_build_ms: float = 0.0,
    embedding_cache: EmbeddingCache | None = None,
    rerank_cache: RerankCache | None = None,
) -> Tuple[List[str], List[Memory], Dict[str, Any], RetrievalResult | None]:
    if method not in METHODS:
        raise ValueError(f"unknown method {method}; choose from {METHODS}")
    ids = [memory.memory_id for memory in memories]
    memory_by_id = {memory.memory_id: memory for memory in memories}
    k = config.retrieval.context_size
    current_budget = budget or SearchBudget.from_config(config.retrieval)
    if method in RERANK_METHODS:
        if not config.models.reranker.endpoint:
            raise ValueError(f"{method} requires a configured reranker endpoint")
        if method in BRIDGE_RERANK_METHODS and config.retrieval.stop_mode == "certificate_or_budget":
            raise ValueError(f"{method} cannot use certificate_or_budget")
        if method in {"dense_rerank", "dense_rerank_20"}:
            required_nodes = config.bridge_rerank.dense_pool_width
        elif method == "dense_rerank_28":
            required_nodes = config.bridge_rerank.dense_pool_width + (
                config.bridge_rerank.expand_branch_count * config.bridge_rerank.branch_keep_width
            )
        elif method == "bridgetree_union_rerank":
            required_nodes = config.bridge_rerank.dense_pool_width + max(
                0,
                config.retrieval.search_budget - config.retrieval.initial_width,
            )
        elif method in GUIDED_METHODS:
            required_nodes = config.bridge_rerank.dense_pool_width + (
                config.bridge_rerank.expand_branch_count * config.bridge_rerank.branch_overfetch_width
            )
        else:
            required_nodes = len(memories)
        current_budget = SearchBudget(
            max_unique_nodes=max(1, min(len(memories), required_nodes)),
            max_ann_calls=current_budget.max_ann_calls,
            max_candidate_exposure=current_budget.max_candidate_exposure,
        )
        if cost_tracker is not None and cost_tracker.cost_unique_count == 0 and cost_tracker.ann_calls_core == 0:
            cost_tracker.budget = current_budget
    tracker = cost_tracker or CostTracker(current_budget)
    tracker.index_build_ms += index_build_ms
    if index is None:
        index_started = time.perf_counter()
        index = build_index(
            config.retrieval.index_backend,
            ids,
            memory_vectors,
            exclusion_margin=config.retrieval.faiss_exclusion_margin,
        )
        tracker.index_build_ms += (time.perf_counter() - index_started) * 1000.0

    if method in ABLATION_OPTIONS:
        retrieval_config = replace(config.retrieval, **ABLATION_OPTIONS[method])
        retrieval_config.validate()
        bridge_result = BridgeTreeRetriever(retrieval_config).retrieve(
            example.query,
            query_vector,
            memories,
            memory_vectors,
            index=index,
            budget=current_budget,
            cost_tracker=tracker,
        )
        diagnostics = bridge_result.to_dict(include_text=False)
        diagnostics["path_objective_advantage"] = path_objective_advantage(bridge_result, k)
        diagnostics["_cost_tracker"] = tracker
        return (
            bridge_result.selected_in_greedy_order,
            bridge_result.selected,
            diagnostics,
            bridge_result,
        )

    if method == "dense":
        baseline = dense_retrieval(
            ids,
            memory_vectors,
            query_vector,
            k,
            index=index,
            budget=current_budget,
            cost_tracker=tracker,
        )
    elif method in {"dense_rerank", "dense_rerank_20", "dense_rerank_28"}:
        if reranker is None:
            raise ValueError(f"{method} requires a reranker client")
        initial_k = config.bridge_rerank.dense_pool_width
        if method == "dense_rerank_28":
            initial_k += config.bridge_rerank.expand_branch_count * config.bridge_rerank.branch_keep_width
        initial_k = min(len(memories), initial_k)
        initial = dense_retrieval(
            ids,
            memory_vectors,
            query_vector,
            initial_k,
            index=index,
            budget=current_budget,
            cost_tracker=tracker,
        )
        max_timestamp = max((memory.timestamp for memory in memories), default=0.0)
        rank_query = build_personamem_rank_query(
            example,
            instruction=config.bridge_rerank.final_rerank_instruction,
            use_answer_options=config.bridge_rerank.use_answer_options,
        )
        documents = [
            format_memory_document(
                memory_by_id[item],
                max_timestamp,
                include_time_metadata=config.bridge_rerank.include_time_metadata,
            )
            for item in initial.selected_ids
        ]
        ranking, cache_hit = cached_rerank_all(reranker, rerank_cache, rank_query, documents, tracker)
        items = ranking[:k]
        baseline = BaselineResult([initial.selected_ids[item.index] for item in items], tracker)
        scores = {initial.selected_ids[item.index]: item.score for item in ranking}
        baseline.diagnostics.update(
            {
                "dense_pool_ids": initial.selected_ids,
                "anchor_ids": [],
                "bridge_raw_ids": [],
                "bridge_kept_ids": [],
                "candidate_union_ids": initial.selected_ids,
                "selected_source_by_id": {memory_id: "dense" for memory_id in baseline.selected_ids},
                "selected_bridge_count": 0,
                "selected_bridge_rate": 0.0,
                "dense_rerank_top5_retention": 1.0,
                "bridge_candidate_novelty": 0.0,
                "dense_rerank_top_ids": [
                    initial.selected_ids[item.index] for item in ranking[:k]
                ],
                "final_rerank_scores": scores,
                "rerank_cache_hits": int(cache_hit),
            }
        )
    elif method == "bridgetree_union_rerank":
        if reranker is None:
            raise ValueError("bridgetree_union_rerank requires a reranker client")
        if config.retrieval.stop_mode == "certificate_or_budget":
            raise ValueError("bridgetree_union_rerank cannot use certificate_or_budget")
        dense_hits = tracker.search_core(
            index,
            query_vector,
            min(config.bridge_rerank.dense_pool_width, len(memories)),
        )
        dense_ids = [memory_id for memory_id, _score in dense_hits]
        bridge_result = BridgeTreeRetriever(config.retrieval).retrieve(
            example.query,
            query_vector,
            memories,
            memory_vectors,
            index=index,
            budget=tracker.budget,
            cost_tracker=tracker,
            initial_hits=dense_hits,
            excluded_candidate_ids=dense_ids,
        )
        discovered_ids = list(bridge_result.nodes)
        bridge_ids = [memory_id for memory_id in discovered_ids if memory_id not in set(dense_ids)]
        candidate_ids = stable_union(dense_ids, discovered_ids)
        max_timestamp = max((memory.timestamp for memory in memories), default=0.0)
        rank_query = build_personamem_rank_query(
            example,
            instruction=config.bridge_rerank.final_rerank_instruction,
            use_answer_options=config.bridge_rerank.use_answer_options,
        )
        documents = [
            format_memory_document(
                memory_by_id[memory_id],
                max_timestamp,
                include_time_metadata=config.bridge_rerank.include_time_metadata,
            )
            for memory_id in candidate_ids
        ]
        ranking, cache_hit = cached_rerank_all(reranker, rerank_cache, rank_query, documents, tracker)
        final_scores = {candidate_ids[item.index]: item.score for item in ranking}
        selected_ids = [candidate_ids[item.index] for item in ranking[:k]]
        selected = _selected_memories(selected_ids, memory_by_id, chronological=True)
        dense_ranked = [candidate_ids[item.index] for item in ranking if candidate_ids[item.index] in set(dense_ids)]
        dense_top5 = set(dense_ranked[:k])
        bridge_set = set(bridge_ids)
        selected_bridge_count = sum(memory_id in bridge_set for memory_id in selected_ids)
        parent_by_bridge = {
            memory_id: node.parent_id
            for memory_id, node in bridge_result.nodes.items()
            if memory_id in bridge_set and node.parent_id is not None
        }
        diagnostics = {
            "dense_pool_ids": dense_ids,
            "anchor_ids": [],
            "bridge_raw_ids": bridge_ids,
            "bridge_kept_ids": bridge_ids,
            "candidate_union_ids": candidate_ids,
            "parent_by_bridge_id": parent_by_bridge,
            "selected_source_by_id": {
                memory_id: "bridge" if memory_id in bridge_set else "dense" for memory_id in selected_ids
            },
            "selected_bridge_count": selected_bridge_count,
            "selected_bridge_rate": selected_bridge_count / len(selected_ids) if selected_ids else 0.0,
            "dense_rerank_top5_retention": (
                sum(memory_id in dense_top5 for memory_id in selected_ids) / len(dense_top5) if dense_top5 else 0.0
            ),
            "bridge_candidate_novelty": len(bridge_set) / len(bridge_ids) if bridge_ids else 0.0,
            "dense_rerank_top_ids": list(dense_top5),
            "final_rerank_scores": final_scores,
            "rerank_cache_hits": int(cache_hit),
            "legacy_internal_selected_ids": list(bridge_result.selected_in_greedy_order),
            "tree_diagnostic": bridge_result.diagnostic_summary(),
            "cost": tracker.snapshot().to_dict(),
            "_cost_tracker": tracker,
        }
        return selected_ids, selected, diagnostics, None
    elif method in GUIDED_METHODS:
        if reranker is None or embedding_cache is None:
            raise ValueError(f"{method} requires reranker and embedding caches")
        selected_ids, selected, pool = RerankerGuidedBridgeRetriever(config).retrieve(
            example,
            memories,
            query_vector,
            memory_vectors,
            embed_query_batch=embedding_cache.encode_queries,
            reranker=reranker,
            rerank_cache=rerank_cache,
            index=index,
            cost_tracker=tracker,
            mode=method,
        )
        return (
            selected_ids,
            selected,
            {**pool.diagnostics, "cost": tracker.snapshot().to_dict(), "_cost_tracker": tracker},
            None,
        )
    elif method == "full_pool_rerank":
        if reranker is None:
            raise ValueError("full_pool_rerank requires a reranker client")
        tracker.mark_visited(ids)
        max_timestamp = max((memory.timestamp for memory in memories), default=0.0)
        rank_query = build_personamem_rank_query(
            example,
            instruction=config.bridge_rerank.final_rerank_instruction,
            use_answer_options=config.bridge_rerank.use_answer_options,
        )
        documents = [
            format_memory_document(
                memory,
                max_timestamp,
                include_time_metadata=config.bridge_rerank.include_time_metadata,
            )
            for memory in memories
        ]
        ranking, cache_hit = cached_rerank_all(reranker, rerank_cache, rank_query, documents, tracker)
        selected_ids = [ids[item.index] for item in ranking[:k]]
        selected = _selected_memories(selected_ids, memory_by_id, chronological=True)
        tracker.set_stop_reason("frontier_empty")
        diagnostics = {
            "dense_pool_ids": [],
            "anchor_ids": [],
            "bridge_raw_ids": [],
            "bridge_kept_ids": [],
            "candidate_union_ids": ids,
            "selected_source_by_id": {memory_id: "full_pool" for memory_id in selected_ids},
            "selected_bridge_count": 0,
            "selected_bridge_rate": 0.0,
            "dense_rerank_top5_retention": 0.0,
            "bridge_candidate_novelty": 0.0,
            "final_rerank_scores": {ids[item.index]: item.score for item in ranking},
            "rerank_cache_hits": int(cache_hit),
            "cost": tracker.snapshot().to_dict(),
            "_cost_tracker": tracker,
        }
        return selected_ids, selected, diagnostics, None
    elif method == "rfmem_familiarity":
        raw = dense_retrieval(
            ids,
            memory_vectors,
            query_vector,
            k,
            index=index,
            budget=current_budget,
            cost_tracker=tracker,
        )
        query_norm = query_vector / np.linalg.norm(query_vector)
        score_by_id = {memory_id: float(np.dot(index.vector(memory_id), query_norm)) for memory_id in raw.selected_ids}
        baseline = BaselineResult(
            [memory_id for memory_id in raw.selected_ids if score_by_id[memory_id] >= 0.3],
            tracker,
        )
    elif method == "rfmem_recollection":
        baseline = rfmem_recollection(
            ids,
            memory_vectors,
            query_vector,
            k,
            index=index,
            budget=current_budget,
            cost_tracker=tracker,
        )
    elif method == "rfmem":
        baseline = rfmem(
            ids,
            memory_vectors,
            query_vector,
            k,
            index=index,
            budget=current_budget,
            cost_tracker=tracker,
        )
    elif method == "cluster_prf":
        baseline = cluster_prf(
            ids,
            memory_vectors,
            query_vector,
            k,
            config.retrieval.initial_width,
            index=index,
            budget=current_budget,
            cost_tracker=tracker,
        )
    else:  # pragma: no cover - METHODS and branches stay synchronized
        raise AssertionError(method)

    selected = _selected_memories(baseline.selected_ids, memory_by_id, chronological=True)
    return (
        baseline.selected_ids,
        selected,
        {
            "ann_calls": baseline.ann_calls,
            "cost": baseline.cost.to_dict(),
            "_cost_tracker": tracker,
            **baseline.diagnostics,
        },
        None,
    )


def load_bridge_gold(path: str | Path | None) -> Dict[str, List[str]]:
    if path is None:
        return {}
    result: Dict[str, List[str]] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            result[str(item["question_id"])] = [str(value) for value in item["gold_memory_ids"]]
    return result


def run_personamem_experiment(
    config: AppConfig,
    method: str,
    embedder: Embedder,
    limit: int | None = None,
    generate: bool = False,
    bridge_gold_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    run_label: str | None = None,
) -> Dict[str, Any]:
    """Run one method under a fully resolved, recorded evaluation protocol."""
    if method in RERANK_METHODS and not config.models.reranker.endpoint:
        raise ValueError(f"{method} requires a configured reranker endpoint")
    if method in BRIDGE_RERANK_METHODS and config.retrieval.stop_mode == "certificate_or_budget":
        raise ValueError(f"{method} cannot use certificate_or_budget")
    raw_root = Path(config.data.raw_dir)
    split = config.data.split
    question_path = raw_root / f"questions_{split}.csv"
    context_path = raw_root / f"shared_contexts_{split}.jsonl"
    if not question_path.exists() or not context_path.exists():
        raise FileNotFoundError("PersonaMem raw data is missing; run `bridgetree download-personamem` first")

    label = re.sub(r"[^a-zA-Z0-9_.-]+", "_", run_label or method).strip("._") or method
    run_root = Path(output_dir or config.runtime.output_dir) / f"{label}_{time.time_ns()}"
    run_root.mkdir(parents=True, exist_ok=False)
    cache = EmbeddingCache(
        config.runtime.cache_dir,
        embedder,
        config.models.embedding.model,
        asdict(config.models.embedding),
    )
    index_cache = IndexCache()
    generator = GeneratorClient(config.models.generator) if generate else None
    reranker = RerankerClient(config.models.reranker) if method in RERANK_METHODS else None
    rerank_cache = (
        RerankCache(
            getattr(config.models.reranker, "cache_dir", "outputs/rerank_cache"),
            endpoint=config.models.reranker.endpoint,
            model=config.models.reranker.model,
        )
        if method in RERANK_METHODS
        else None
    )
    bridge_gold = load_bridge_gold(bridge_gold_path)

    resolved = {
        "app": config.resolved_dict(),
        "execution": {
            "method": method,
            "limit": limit,
            "generate": generate,
            "bridge_gold_path": str(bridge_gold_path) if bridge_gold_path is not None else None,
            "run_label": label,
        },
    }
    resolved_payload = json.dumps(resolved, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha256(resolved_payload.encode("utf-8")).hexdigest()
    with (run_root / "resolved_config.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "config_hash": config_hash,
                "app_config_hash": config.config_hash(),
                "config": resolved,
            },
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")
    repository_root = Path(__file__).resolve().parents[2]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest: Dict[str, Any] = {
        "status": "running",
        "method": method,
        "run_label": label,
        "config_hash": config_hash,
        "git_commit": commit or None,
        "data_revision": PERSONAMEM_REVISION,
        "data_split": split,
        "embedding_model": asdict(config.models.embedding),
        "generator_model": asdict(config.models.generator),
        "prompt_hash": generation_prompt_hash(),
        "seed": config.seed,
        "generate": generate,
        "limit": limit,
    }
    with (run_root / "run_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    output_path = run_root / "predictions.jsonl"
    failure_path = run_root / "failures.jsonl"
    total = 0
    attempted = 0
    failures = 0
    accuracy_sum = 0.0
    parse_failure_sum = 0.0
    recall_sum = 0.0
    bridge_recall_sum = 0.0
    annotated = 0
    bridge_annotated = 0
    bridge_results: List[RetrievalResult] = []
    latencies: List[float] = []
    cost_records: List[Dict[str, Any]] = []
    outcome_records: List[Dict[str, Any]] = []
    with (
        output_path.open("w", encoding="utf-8") as output,
        failure_path.open("w", encoding="utf-8") as failure_output,
    ):
        for example in iter_examples(question_path, context_path):
            if limit is not None and attempted >= limit:
                break
            attempted += 1
            try:
                memories = messages_to_memories(
                    example.messages,
                    source_prefix=example.question_id,
                    include_system_persona=config.data.include_system_persona,
                    memory_granularity=config.data.memory_granularity,
                )
                if not memories:
                    raise ValueError("no memories after the configured PersonaMem segmentation")
                query_vector = cache.encode_query(example.query)
                memory_vectors = cache.encode_documents([memory.text for memory in memories])
                context_key = (
                    f"{example.shared_context_id}:{example.end_index}:"
                    f"{config.data.memory_granularity}:{config.data.include_system_persona}"
                )
                index, index_build_ms, index_cache_hit = index_cache.get(
                    context_key,
                    cache.fingerprint,
                    config.retrieval.index_backend,
                    [memory.memory_id for memory in memories],
                    memory_vectors,
                    config.retrieval.faiss_exclusion_margin,
                )
                tracker = CostTracker(SearchBudget.from_config(config.retrieval))
                started = time.perf_counter()
                selected_ids, selected, diagnostics, bridge_result = retrieve_method(
                    method,
                    config,
                    example,
                    memories,
                    query_vector,
                    memory_vectors,
                    reranker=reranker,
                    index=index,
                    budget=tracker.budget,
                    cost_tracker=tracker,
                    index_build_ms=index_build_ms,
                    embedding_cache=cache,
                    rerank_cache=rerank_cache,
                )
                tracker = diagnostics.pop("_cost_tracker")
                selected = fit_context_budget(selected, config.models.generator.context_token_budget)
                retained_ids = {memory.memory_id for memory in selected}
                selected_ids = [memory_id for memory_id in selected_ids if memory_id in retained_ids]
                _refresh_rerank_selection_diagnostics(diagnostics, selected_ids)
                tracker.final_context_count = len(selected)
                tracker.final_context_tokens = context_token_count(selected)
                response = ""
                if generator:
                    generation_started = time.perf_counter()
                    response = generator.answer(example.query, selected, example.all_options)
                    tracker.generation_ms = (time.perf_counter() - generation_started) * 1000.0
                latency = time.perf_counter() - started
                latencies.append(latency)
                accuracy = answer_accuracy(response, example.correct_answer) if generator else None
                parse_failure = answer_parse_failed(response) if generator else None
                if accuracy is not None:
                    accuracy_sum += accuracy
                if parse_failure is not None:
                    parse_failure_sum += parse_failure
                gold_ids = bridge_gold.get(example.question_id, [])
                recall = None
                bridge_recall = None
                if gold_ids:
                    annotated += 1
                    ranks = direct_ranks(query_vector, [memory.memory_id for memory in memories], memory_vectors)
                    recall = recall_at_k(selected_ids, gold_ids, config.retrieval.context_size)
                    bridge_recall = bridge_recall_at_k(
                        selected_ids,
                        gold_ids,
                        ranks,
                        config.retrieval.context_size,
                    )
                    recall_sum += recall
                    if bridge_recall is not None:
                        bridge_recall_sum += bridge_recall
                        bridge_annotated += 1
                if bridge_result is not None:
                    bridge_results.append(bridge_result)
                    diagnostics = bridge_result.to_dict(include_text=False)
                    diagnostics["diagnostic"] = bridge_result.diagnostic_summary(list(gold_ids) if gold_ids else None)
                    diagnostics["path_objective_advantage"] = path_objective_advantage(
                        bridge_result, config.retrieval.context_size
                    )
                else:
                    diagnostics["cost"] = tracker.snapshot().to_dict()
                diagnostics["index_cache_hit"] = index_cache_hit
                cost = tracker.snapshot().to_dict()
                cost_records.append(cost)
                outcome = {
                    "answer_accuracy": accuracy,
                    "parse_failure_rate": parse_failure,
                    "recall_at_k": recall,
                    "bridge_recall_at_k": bridge_recall,
                }
                outcome_records.append(
                    {
                        **outcome,
                        "question_type": example.question_type,
                        "topic": example.topic,
                        "memory_scale": (
                            "small" if len(memories) < 16 else "medium" if len(memories) < 64 else "large"
                        ),
                    }
                )
                record = {
                    "persona_id": example.persona_id,
                    "question_id": example.question_id,
                    "question_type": example.question_type,
                    "topic": example.topic,
                    "query": example.query,
                    "correct_answer": example.correct_answer,
                    "selected_memory_ids": selected_ids,
                    "response": response,
                    "outcome": outcome,
                    "cost": cost,
                    **{
                        name: cost[name]
                        for name in (
                            "rerank_calls",
                            "rerank_documents",
                            "rerank_ms",
                            "bridge_embedding_calls",
                            "bridge_embedding_queries",
                            "bridge_embedding_ms",
                        )
                    },
                    "diagnostic": diagnostics,
                    **{
                        key: diagnostics.get(key)
                        for key in (
                            "dense_pool_ids",
                            "anchor_ids",
                            "bridge_raw_ids",
                            "bridge_kept_ids",
                            "candidate_union_ids",
                            "selected_source_by_id",
                            "selected_bridge_count",
                            "selected_bridge_rate",
                            "dense_rerank_top5_retention",
                            "bridge_candidate_novelty",
                            "dense_rerank_top_ids",
                            "parent_by_bridge_id",
                            "branch_by_bridge_id",
                            "raw_bridge_ids_by_branch",
                            "dense_rerank_scores",
                            "bridge_ann_scores",
                            "path_filter_scores",
                            "final_rerank_scores",
                            "rerank_cache_hits",
                        )
                        if key in diagnostics
                    },
                    # Compatibility fields for existing result readers.
                    "accuracy": accuracy,
                    "recall_at_k": recall,
                    "bridge_recall_at_k": bridge_recall,
                    "latency_seconds": latency,
                }
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                total += 1
            except Exception as exc:  # a failed query is explicit run evidence
                failures += 1
                failure_output.write(
                    json.dumps(
                        {
                            "question_id": example.question_id,
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    numeric_cost_names = [
        "ann_calls_core",
        "ann_calls_diagnostic",
        "candidates_returned",
        "candidates_returned_diagnostic",
        "unique_visited_nodes",
        "index_build_ms",
        "retrieval_core_ms",
        "diagnostic_ms",
        "rerank_calls",
        "rerank_documents",
        "rerank_ms",
        "bridge_embedding_calls",
        "bridge_embedding_queries",
        "bridge_embedding_ms",
        "generation_ms",
        "final_context_count",
        "final_context_tokens",
        "duplicate_proposals",
        "proposal_count",
        "new_unique_candidates_per_ann",
    ]
    mean_cost = {
        name: sum(float(record[name]) for record in cost_records) / len(cost_records) if cost_records else 0.0
        for name in numeric_cost_names
    }
    stop_reasons = {
        reason: sum(record["stop_reason"] == reason for record in cost_records)
        for reason in sorted({str(record["stop_reason"]) for record in cost_records})
    }

    def stratify(field: str) -> Dict[str, Any]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for record in outcome_records:
            groups.setdefault(str(record[field]), []).append(record)
        result: Dict[str, Any] = {}
        for name, records in sorted(groups.items()):
            result[name] = {"queries": len(records)}
            for metric in ("answer_accuracy", "parse_failure_rate", "recall_at_k", "bridge_recall_at_k"):
                values = [float(record[metric]) for record in records if record[metric] is not None]
                result[name][metric] = sum(values) / len(values) if values else None
        return result

    summary: Dict[str, Any] = {
        "method": method,
        "split": split,
        "queries": total,
        "attempted_queries": attempted,
        "failed_queries": failures,
        "generated": generate,
        "answer_accuracy": accuracy_sum / total if generate and total else None,
        "parse_failure_rate": parse_failure_sum / total if generate and total else None,
        "annotated_queries": annotated,
        "recall_at_k": recall_sum / annotated if annotated else None,
        "bridge_annotated_queries": bridge_annotated,
        "bridge_recall_at_k": bridge_recall_sum / bridge_annotated if bridge_annotated else None,
        "cost": {"mean": mean_cost, "stop_reason_counts": stop_reasons},
        "stratified": {
            "question_type": stratify("question_type"),
            "topic": stratify("topic"),
            "memory_scale": stratify("memory_scale"),
        },
        "mean_retrieval_and_generation_latency_seconds": sum(latencies) / len(latencies) if latencies else 0.0,
        "model_calls_per_query": {"retrieval_llm": 0, "generator": int(generate)},
    }
    if bridge_results:
        from .metrics import summarize_bridge_results

        summary.update(summarize_bridge_results(bridge_results))
    with (run_root / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    manifest.update({"status": "completed", "queries": total, "failed_queries": failures})
    with (run_root / "run_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return {"run_dir": str(run_root), "summary": summary}
