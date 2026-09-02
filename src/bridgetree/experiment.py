from __future__ import annotations

import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

from .baselines import BaselineResult, cluster_prf, dense_retrieval, rfmem, rfmem_recollection
from .clients import Embedder, GeneratorClient, RerankerClient
from .config import AppConfig
from .metrics import answer_accuracy, bridge_recall_at_k, direct_ranks, path_innovation_gain, recall_at_k
from .personamem import PersonaMemExample, iter_examples, messages_to_memories
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
                return np.asarray(value, dtype=np.float64)
        value = np.asarray(encode(), dtype=np.float64)
        np.save(path, value, allow_pickle=False)
        return value

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._cached(texts, "document", lambda: self.embedder.encode(texts))

    def encode_query(self, text: str) -> np.ndarray:
        method = getattr(self.embedder, "encode_query", None)
        encode = (lambda: np.asarray([method(text)])) if callable(method) else (lambda: self.embedder.encode([text]))
        return self._cached([text], "query", encode)[0]


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
) -> Tuple[List[str], List[Memory], Dict[str, Any], RetrievalResult | None]:
    if method not in METHODS:
        raise ValueError(f"unknown method {method}; choose from {METHODS}")
    ids = [memory.memory_id for memory in memories]
    memory_by_id = {memory.memory_id: memory for memory in memories}
    k = config.retrieval.context_size

    if method in ABLATION_OPTIONS:
        retrieval_config = replace(config.retrieval, **ABLATION_OPTIONS[method])
        retrieval_config.validate()
        bridge_result = BridgeTreeRetriever(retrieval_config).retrieve(
            example.query, query_vector, memories, memory_vectors
        )
        diagnostics = bridge_result.to_dict(include_text=False)
        diagnostics["path_innovation_gain"] = path_innovation_gain(bridge_result, k)
        return (
            bridge_result.selected_in_greedy_order,
            bridge_result.selected,
            diagnostics,
            bridge_result,
        )

    if method == "dense":
        baseline = dense_retrieval(ids, memory_vectors, query_vector, k)
    elif method == "dense_rerank":
        if reranker is None:
            raise ValueError("dense_rerank requires a reranker client")
        initial_k = min(len(memories), max(config.retrieval.first_hop_width, 4 * k))
        initial = dense_retrieval(ids, memory_vectors, query_vector, initial_k)
        items = reranker.rerank(example.query, [memory_by_id[item].text for item in initial.selected_ids], k)
        baseline = BaselineResult([initial.selected_ids[item.index] for item in items], ann_calls=1)
    elif method == "rfmem_familiarity":
        raw = dense_retrieval(ids, memory_vectors, query_vector, k)
        query_norm = query_vector / np.linalg.norm(query_vector)
        normalized_memory = memory_vectors / np.linalg.norm(memory_vectors, axis=1, keepdims=True)
        score_by_id = {
            memory_id: float(np.dot(normalized_memory[index], query_norm)) for index, memory_id in enumerate(ids)
        }
        baseline = BaselineResult([memory_id for memory_id in raw.selected_ids if score_by_id[memory_id] >= 0.3], 1)
    elif method == "rfmem_recollection":
        baseline = rfmem_recollection(ids, memory_vectors, query_vector, k)
    elif method == "rfmem":
        baseline = rfmem(ids, memory_vectors, query_vector, k)
    elif method == "cluster_prf":
        baseline = cluster_prf(ids, memory_vectors, query_vector, k, config.retrieval.first_hop_width)
    else:  # pragma: no cover - METHODS and branches stay synchronized
        raise AssertionError(method)

    selected = _selected_memories(baseline.selected_ids, memory_by_id, chronological=True)
    return baseline.selected_ids, selected, {"ann_calls": baseline.ann_calls, **baseline.diagnostics}, None


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
) -> Dict[str, Any]:
    raw_root = Path(config.data.raw_dir)
    split = config.data.split
    question_path = raw_root / f"questions_{split}.csv"
    context_path = raw_root / f"shared_contexts_{split}.jsonl"
    if not question_path.exists() or not context_path.exists():
        raise FileNotFoundError("PersonaMem raw data is missing; run `bridgetree download-personamem` first")

    run_root = Path(output_dir or config.runtime.output_dir) / f"{method}_{time.time_ns()}"
    run_root.mkdir(parents=True, exist_ok=False)
    cache = EmbeddingCache(config.runtime.cache_dir, embedder, config.models.embedding.model)
    generator = GeneratorClient(config.models.generator) if generate else None
    reranker = RerankerClient(config.models.reranker) if method == "dense_rerank" else None
    bridge_gold = load_bridge_gold(bridge_gold_path)

    output_path = run_root / "predictions.jsonl"
    total = 0
    accuracy_sum = 0.0
    recall_sum = 0.0
    bridge_recall_sum = 0.0
    annotated = 0
    bridge_results: List[RetrievalResult] = []
    latencies: List[float] = []
    with output_path.open("w", encoding="utf-8") as output:
        for example in iter_examples(question_path, context_path):
            if limit is not None and total >= limit:
                break
            memories = messages_to_memories(
                example.messages,
                source_prefix=example.question_id,
                include_system_persona=config.data.include_system_persona,
            )
            if not memories:
                continue
            query_vector = cache.encode_query(example.query)
            memory_vectors = cache.encode_documents([memory.text for memory in memories])
            started = time.perf_counter()
            selected_ids, selected, diagnostics, bridge_result = retrieve_method(
                method,
                config,
                example,
                memories,
                query_vector,
                memory_vectors,
                reranker=reranker,
            )
            response = generator.answer(example.query, selected, example.all_options) if generator else ""
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
                bridge_recall = bridge_recall_at_k(selected_ids, gold_ids, ranks, config.retrieval.context_size)
                recall_sum += recall
                bridge_recall_sum += bridge_recall
            if bridge_result is not None:
                bridge_results.append(bridge_result)
            record = {
                "persona_id": example.persona_id,
                "question_id": example.question_id,
                "question_type": example.question_type,
                "topic": example.topic,
                "query": example.query,
                "correct_answer": example.correct_answer,
                "selected_memory_ids": selected_ids,
                "response": response,
                "accuracy": accuracy,
                "recall_at_k": recall,
                "bridge_recall_at_k": bridge_recall,
                "latency_seconds": latency,
                "diagnostics": diagnostics,
            }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            total += 1

    summary: Dict[str, Any] = {
        "method": method,
        "split": split,
        "queries": total,
        "generated": generate,
        "answer_accuracy": accuracy_sum / total if generate and total else None,
        "annotated_queries": annotated,
        "recall_at_k": recall_sum / annotated if annotated else None,
        "bridge_recall_at_k": bridge_recall_sum / annotated if annotated else None,
        "mean_retrieval_and_generation_latency_seconds": sum(latencies) / len(latencies) if latencies else 0.0,
        "model_calls_per_query": {"retrieval_llm": 0, "generator": int(generate)},
    }
    if bridge_results:
        from .metrics import summarize_bridge_results

        summary.update(summarize_bridge_results(bridge_results))
    with (run_root / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return {"run_dir": str(run_root), "summary": summary}
