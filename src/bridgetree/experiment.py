from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
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
from .index import ExactInnerProductIndex, build_index
from .metrics import answer_accuracy, bridge_recall_at_k, direct_ranks, path_innovation_gain, recall_at_k
from .personamem import PERSONAMEM_REVISION, PersonaMemExample, iter_examples, messages_to_memories
from .retriever import BridgeTreeRetriever
from .types import Memory, RetrievalResult

METHODS = (
    "bridgetree",
    "dense",
    "dense_rerank",
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
    def __init__(self, root: str | Path, embedder: Embedder, model_name: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder
        self.model_name = model_name

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.model_name.encode("utf-8")).hexdigest()

    def _cached(self, texts: Sequence[str], purpose: str, encode) -> np.ndarray:
        payload = json.dumps(
            {"model": self.model_name, "purpose": purpose, "texts": list(texts)},
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

    def encode_query(self, text: str) -> np.ndarray:
        method = getattr(self.embedder, "encode_query", None)
        encode = (lambda: np.asarray([method(text)])) if callable(method) else (lambda: self.embedder.encode([text]))
        return self._cached([text], "query", encode)[0]


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
                "ids": list(ids),
                "vectors": vector_fingerprint,
                "exclusion_margin": exclusion_margin,
            },
            sort_keys=True,
        )
        key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if key in self._indexes:
            return self._indexes[key], 0.0, True
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
) -> Tuple[List[str], List[Memory], Dict[str, Any], RetrievalResult | None]:
    if method not in METHODS:
        raise ValueError(f"unknown method {method}; choose from {METHODS}")
    ids = [memory.memory_id for memory in memories]
    memory_by_id = {memory.memory_id: memory for memory in memories}
    k = config.retrieval.context_size
    current_budget = budget or SearchBudget.from_config(config.retrieval)
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
        diagnostics["path_innovation_gain"] = path_innovation_gain(bridge_result, k)
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
    elif method == "dense_rerank":
        if reranker is None:
            raise ValueError("dense_rerank requires a reranker client")
        initial_k = min(len(memories), max(config.retrieval.initial_width, 4 * k))
        initial = dense_retrieval(
            ids,
            memory_vectors,
            query_vector,
            initial_k,
            index=index,
            budget=current_budget,
            cost_tracker=tracker,
        )
        items = reranker.rerank(example.query, [memory_by_id[item].text for item in initial.selected_ids], k)
        baseline = BaselineResult([initial.selected_ids[item.index] for item in items], tracker)
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
    raw_root = Path(config.data.raw_dir)
    split = config.data.split
    question_path = raw_root / f"questions_{split}.csv"
    context_path = raw_root / f"shared_contexts_{split}.jsonl"
    if not question_path.exists() or not context_path.exists():
        raise FileNotFoundError("PersonaMem raw data is missing; run `bridgetree download-personamem` first")

    label = re.sub(r"[^a-zA-Z0-9_.-]+", "_", run_label or method).strip("._") or method
    run_root = Path(output_dir or config.runtime.output_dir) / f"{label}_{time.time_ns()}"
    run_root.mkdir(parents=True, exist_ok=False)
    cache = EmbeddingCache(config.runtime.cache_dir, embedder, config.models.embedding.model)
    index_cache = IndexCache()
    generator = GeneratorClient(config.models.generator) if generate else None
    reranker = RerankerClient(config.models.reranker) if method == "dense_rerank" else None
    bridge_gold = load_bridge_gold(bridge_gold_path)

    resolved = config.resolved_dict()
    config_hash = config.config_hash()
    with (run_root / "resolved_config.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {"config_hash": config_hash, "config": resolved}, handle, ensure_ascii=False, indent=2, sort_keys=True
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
    recall_sum = 0.0
    bridge_recall_sum = 0.0
    annotated = 0
    bridge_results: List[RetrievalResult] = []
    latencies: List[float] = []
    cost_records: List[Dict[str, Any]] = []
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
                )
                tracker = diagnostics.pop("_cost_tracker")
                selected = fit_context_budget(selected, config.models.generator.context_token_budget)
                retained_ids = {memory.memory_id for memory in selected}
                selected_ids = [memory_id for memory_id in selected_ids if memory_id in retained_ids]
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
                if accuracy is not None:
                    accuracy_sum += accuracy
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
                if bridge_result is not None:
                    bridge_results.append(bridge_result)
                    diagnostics = bridge_result.to_dict(include_text=False)
                    diagnostics["path_innovation_gain"] = path_innovation_gain(
                        bridge_result, config.retrieval.context_size
                    )
                else:
                    diagnostics["cost"] = tracker.snapshot().to_dict()
                diagnostics["index_cache_hit"] = index_cache_hit
                cost = tracker.snapshot().to_dict()
                cost_records.append(cost)
                outcome = {
                    "answer_accuracy": accuracy,
                    "recall_at_k": recall,
                    "bridge_recall_at_k": bridge_recall,
                }
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
                    "diagnostic": diagnostics,
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

    summary: Dict[str, Any] = {
        "method": method,
        "split": split,
        "queries": total,
        "attempted_queries": attempted,
        "failed_queries": failures,
        "generated": generate,
        "answer_accuracy": accuracy_sum / total if generate and total else None,
        "annotated_queries": annotated,
        "recall_at_k": recall_sum / annotated if annotated else None,
        "bridge_recall_at_k": bridge_recall_sum / annotated if annotated else None,
        "cost": {"mean": mean_cost, "stop_reason_counts": stop_reasons},
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
