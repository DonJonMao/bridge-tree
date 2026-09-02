from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, Sequence

import numpy as np

from .config import EmbeddingConfig, EndpointConfig, GeneratorConfig
from .math_utils import normalize_rows
from .types import Memory

GENERATOR_SYSTEM_PROMPT = (
    "Answer the user using only relevant personal memories. Respect the latest preference when "
    "memories evolve. Do not mention retrieval internals."
)
GENERATOR_USER_TEMPLATE = (
    "User query:\n{query}\n\nRetrieved personal memories (chronological):\n{context}"
    "\n\nAnswer options:\n{answer_options}\nReturn the best option label and a concise answer."
)


def estimate_tokens(text: str) -> int:
    """Deterministic tokenizer-independent accounting used for method matching."""
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def context_token_count(memories: Sequence[Memory]) -> int:
    return sum(estimate_tokens(memory.text) for memory in memories)


def fit_context_budget(memories: Sequence[Memory], token_budget: int) -> List[Memory]:
    selected: List[Memory] = []
    used = 0
    for memory in memories:
        tokens = estimate_tokens(memory.text)
        if selected and used + tokens > token_budget:
            continue
        if not selected and tokens > token_budget:
            continue
        selected.append(memory)
        used += tokens
    return selected


def build_generation_messages(
    query: str,
    memories: Sequence[Memory],
    answer_options: str = "",
) -> List[Dict[str, str]]:
    context = "\n\n".join(
        f"[Memory {index}; source={memory.source_id}; time={memory.timestamp}]\n{memory.text}"
        for index, memory in enumerate(memories, start=1)
    )
    user_content = GENERATOR_USER_TEMPLATE.format(
        query=query,
        context=context,
        answer_options=answer_options,
    )
    return [
        {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def generation_prompt_hash() -> str:
    payload = GENERATOR_SYSTEM_PROMPT + "\n" + GENERATOR_USER_TEMPLATE
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Embedder(Protocol):
    def encode(self, texts: Sequence[str]) -> np.ndarray: ...

    def encode_query(self, text: str) -> np.ndarray: ...


def _post_json(url: str, payload: Dict[str, Any], timeout: float, headers: Dict[str, str] | None = None) -> Any:
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    last_error: Exception | None = None
    # Match datacenter's `curl --noproxy '*'`: these model IPs are private
    # service routes and must not be sent through an ambient HTTP(S) proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(3):
        try:
            with opener.open(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.25 * (2**attempt))
    raise RuntimeError(f"request failed after 3 attempts: {url}: {last_error}")


class RemoteEmbeddingClient:
    def __init__(self, config: EmbeddingConfig):
        self.config = config

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float64)
        rows: List[List[float]] = []
        batch_size = max(1, self.config.batch_size)
        for start in range(0, len(texts), batch_size):
            batch = list(texts[start : start + batch_size])
            response = _post_json(
                self.config.endpoint,
                {"model": self.config.model, "input": batch},
                self.config.timeout_seconds,
            )
            data = response.get("data") if isinstance(response, dict) else None
            if not isinstance(data, list):
                raise ValueError("embedding response must contain a data list")
            ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
            rows.extend(item["embedding"] for item in ordered)
        if len(rows) != len(texts):
            raise ValueError(f"embedding response count mismatch: expected {len(texts)}, got {len(rows)}")
        return normalize_rows(np.asarray(rows, dtype=np.float64))

    def encode_query(self, text: str) -> np.ndarray:
        return self.encode([self.config.query_instruction + text])[0]


class LocalSentenceTransformerEmbedder:
    def __init__(self, model_path: str, device: str = "cpu", query_instruction: str = ""):
        if not model_path:
            raise ValueError("local embedding backend requires local_model_path")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("install the local-models extra to use local embeddings") from exc
        self.model = SentenceTransformer(model_path, device=device)
        self.query_instruction = query_instruction

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = self.model.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)
        return normalize_rows(np.asarray(vectors, dtype=np.float64))

    def encode_query(self, text: str) -> np.ndarray:
        return self.encode([self.query_instruction + text])[0]


def build_embedder(config: EmbeddingConfig, device: str = "cpu") -> Embedder:
    if config.backend == "remote":
        return RemoteEmbeddingClient(config)
    return LocalSentenceTransformerEmbedder(
        config.local_model_path or config.model,
        device=device,
        query_instruction=config.query_instruction,
    )


@dataclass(frozen=True)
class RerankItem:
    index: int
    score: float


class RerankerClient:
    def __init__(self, config: EndpointConfig):
        self.config = config

    def rerank(self, query: str, documents: Sequence[str], top_n: int) -> List[RerankItem]:
        payload: Dict[str, Any] = {
            "query": query,
            "documents": list(documents),
            "top_n": min(top_n, len(documents)),
            "return_documents": False,
        }
        if self.config.model:
            payload["model"] = self.config.model
        response = _post_json(self.config.endpoint, payload, self.config.timeout_seconds)
        raw_results = response.get("results", response.get("data")) if isinstance(response, dict) else None
        if not isinstance(raw_results, list):
            raise ValueError("rerank response must contain results or data")
        items = [
            RerankItem(
                index=int(item["index"]),
                score=float(item.get("relevance_score", item.get("score", 0.0))),
            )
            for item in raw_results
        ]
        return sorted(items, key=lambda item: (-item.score, item.index))[:top_n]


class GeneratorClient:
    def __init__(self, config: GeneratorConfig):
        self.config = config

    def answer(self, query: str, memories: Sequence[Memory], answer_options: str = "") -> str:
        memories = fit_context_budget(memories, self.config.context_token_budget)
        payload = {
            "model": self.config.model,
            "messages": build_generation_messages(query, memories, answer_options),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = _post_json(
            self.config.endpoint,
            payload,
            self.config.timeout_seconds,
            headers={"Authorization": f"Bearer {self.config.resolved_api_key()}"},
        )
        choices = response.get("choices") if isinstance(response, dict) else None
        if not choices:
            raise ValueError("chat response has no choices")
        return str(choices[0]["message"]["content"]).strip()
