from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Protocol, Sequence

import numpy as np

from .config import EmbeddingConfig, EndpointConfig, GeneratorConfig
from .information import StateBasisProvider
from .math_utils import normalize_rows
from .types import (
    ContextPlan,
    Memory,
    _strict_float_value,
    _strict_int_value,
    context_plan_hash,
)

# Shared reader instruction for every retrieval method.  It is deliberately
# question-time aware and does not encode a keyword-specific latest-wins
# branch; historical state and reasons for change remain available when the
# question asks for them.
GENERATOR_SYSTEM_PROMPT = (
    "Answer the user using only relevant personal memories. Assess evidence "
    "for the time or period asked in the question. Earlier statements may be "
    "necessary for historical states or reasons for change. Distinguish user "
    "statements from assistant suggestions. Do not mention retrieval internals."
)
GENERATOR_USER_TEMPLATE = (
    "User query:\n{query}\n\nRetrieved personal memories (chronological):\n{context}"
    "\n\nAnswer options:\n{answer_options}\nReturn the best option label and a concise answer."
)


def estimate_tokens(text: str) -> int:
    """Deterministic tokenizer-independent accounting used for method matching."""
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def context_token_count(memories: Sequence[Memory]) -> int:
    return sum(estimate_tokens(memory.text) for memory in memories)


def fit_context_budget(memories: Sequence[Memory], token_budget: int) -> List[Memory]:
    if isinstance(memories, (str, bytes)) or not isinstance(memories, Sequence):
        raise ValueError("memories must be a sequence")
    token_budget = _strict_int_value(token_budget, "context token budget", nonnegative=True)
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
    if not isinstance(query, str) or not isinstance(answer_options, str):
        raise ValueError("query and answer_options must be strings")
    if isinstance(memories, (str, bytes)) or not isinstance(memories, Sequence):
        raise ValueError("memories must be a sequence")
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


class ContextPlanError(ValueError):
    """Raised when an exact selected context cannot satisfy its budget."""


def build_context_plan(
    query: str,
    memories: Sequence[Memory],
    answer_options: str = "",
    *,
    token_budget: int | None = None,
    strict: bool = True,
    selected_ids: Sequence[str] | None = None,
    model: str = "",
    endpoint: str = "",
    temperature: float = 0.0,
    max_tokens: int | None = None,
    response_format: Any | None = None,
    request_params: Mapping[str, Any] | None = None,
    generator_config: GeneratorConfig | None = None,
) -> ContextPlan:
    """Build the one authoritative generation request without truncation."""

    # Validate the control flags before resolving a config.  In particular,
    # ``strict=1`` must not silently opt a caller into a different budget
    # contract, and NumPy booleans should not be accepted as a wire-level
    # boolean by accident.
    if not isinstance(strict, bool):
        raise ValueError("ContextPlan strict must be boolean")
    if isinstance(memories, (str, bytes)) or not isinstance(memories, Sequence):
        raise ValueError("ContextPlan memories must be a sequence")
    if not isinstance(query, str) or not isinstance(answer_options, str):
        raise ValueError("ContextPlan query and answer_options must be strings")

    # Callers may provide a GeneratorConfig directly; explicit keyword values
    # remain useful for lightweight tests and custom HTTP adapters.  Resolve
    # this before hashing so the plan identity is exactly the final request
    # identity rather than a later client-side mutation.
    if generator_config is not None:
        def config_value(name: str, default: Any = None) -> Any:
            if isinstance(generator_config, Mapping):
                return generator_config.get(name, default)
            return getattr(generator_config, name, default)

        model_value = config_value("model", model)
        endpoint_value = config_value("endpoint", endpoint)
        if not isinstance(model_value, str) or not isinstance(endpoint_value, str):
            raise ValueError("GeneratorConfig model and endpoint must be strings")
        model = model_value
        endpoint = endpoint_value
        temperature = _strict_float_value(
            config_value("temperature", temperature),
            "ContextPlan temperature",
            nonnegative=True,
        )
        if max_tokens is None:
            max_tokens = _strict_int_value(
                config_value("max_tokens", 0),
                "ContextPlan max_tokens",
                nonnegative=True,
            )
        if token_budget is None:
            configured_budget = config_value("context_token_budget", None)
            token_budget = (
                None
                if configured_budget is None
                else _strict_int_value(
                    configured_budget,
                    "ContextPlan token_budget",
                    nonnegative=True,
                )
            )
    # Apply the same strict contract to explicit arguments.  Avoid ``int`` /
    # ``float`` coercions here: they turn booleans, fractions, and NaN into
    # plausible-looking request fields that later audits cannot distinguish
    # from the caller's intended values.
    temperature = _strict_float_value(
        temperature,
        "ContextPlan temperature",
        nonnegative=True,
    )
    max_tokens = (
        None
        if max_tokens is None
        else _strict_int_value(max_tokens, "ContextPlan max_tokens", nonnegative=True)
    )
    token_budget = (
        None
        if token_budget is None
        else _strict_int_value(token_budget, "ContextPlan token_budget", nonnegative=True)
    )

    # The reader contract always receives chronology, even if a selector
    # returns IDs in greedy order.  Ties use memory_id so the same selected
    # set produces one canonical request across methods and processes.
    def chronology_key(memory: Memory) -> tuple[float, str]:
        try:
            stamp = float(memory.timestamp)
            if not np.isfinite(stamp):
                stamp = float("inf")
        except (TypeError, ValueError):
            stamp = float("inf")
        return stamp, str(memory.memory_id)

    ordered = sorted(list(memories), key=chronology_key)
    chronological_ids = tuple(memory.memory_id for memory in ordered)
    if len(set(chronological_ids)) != len(chronological_ids):
        raise ValueError("ContextPlan memory IDs must be unique")
    if selected_ids is not None:
        supplied_ids = tuple(str(value) for value in selected_ids)
        if len(supplied_ids) != len(set(supplied_ids)):
            raise ValueError("ContextPlan selected_ids must be unique")
        if set(supplied_ids) != set(chronological_ids):
            raise ValueError(
                "ContextPlan selected_ids must contain exactly the memories represented in the request"
            )
    messages = tuple(build_generation_messages(query, ordered, answer_options))
    serialized_context = messages[1]["content"] if len(messages) > 1 else ""
    # This is a deterministic estimate, not a claim about a service tokenizer.
    token_count = sum(estimate_tokens(message["content"]) for message in messages)
    budget_status = "within_budget" if token_budget is None or token_count <= token_budget else "exceeds_budget"
    if strict and budget_status == "exceeds_budget":
        raise ContextPlanError(
            f"selected context uses {token_count} estimated tokens, exceeding budget {token_budget}"
        )
    prompt_hash = generation_prompt_hash()
    request = {
        # ``endpoint`` is transport provenance.  It is retained in the frozen
        # plan/hash but stripped by GeneratorClient before sending JSON.
        "endpoint": str(endpoint),
        "model": str(model),
        "messages": [dict(message) for message in messages],
        "temperature": temperature,
        "max_tokens": 0 if max_tokens is None else max_tokens,
    }
    if response_format is not None:
        request["response_format"] = response_format
    if request_params is not None:
        if not isinstance(request_params, Mapping):
            raise ValueError("ContextPlan request_params must be a mapping")
        # Custom parameters are part of the exact request and may not replace
        # the canonical fields above.  Rejecting collisions prevents a plan
        # hash from describing a value that the HTTP client later overwrites.
        for key, value in request_params.items():
            key = str(key)
            if key.lower() in {
                "api_key",
                "api_key_env",
                "authorization",
                "token",
                "password",
                "secret",
            }:
                raise ValueError("request_params may not contain credentials")
            if key in request and key not in {"endpoint"} and request[key] != value:
                raise ValueError(f"request_params conflicts with ContextPlan field {key}")
            request[key] = value
    effective_selected = tuple(
        str(value) for value in (chronological_ids if selected_ids is None else selected_ids)
    )
    context_hash = context_plan_hash(
        selected_ids=effective_selected,
        chronological_ids=chronological_ids,
        serialized_context=serialized_context,
        messages=messages,
        token_count=token_count,
        token_count_is_estimate=True,
        budget=token_budget,
        budget_status=budget_status,
        prompt_hash=prompt_hash,
        request=request,
    )
    return ContextPlan(
        selected_ids=effective_selected,
        chronological_ids=chronological_ids,
        serialized_context=serialized_context,
        messages=messages,
        token_count=token_count,
        token_count_is_estimate=True,
        budget=token_budget,
        budget_status=budget_status,
        prompt_hash=prompt_hash,
        context_hash=context_hash,
        request=request,
    )


def generation_prompt_hash() -> str:
    payload = GENERATOR_SYSTEM_PROMPT + "\n" + GENERATOR_USER_TEMPLATE
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Embedder(Protocol):
    def encode(self, texts: Sequence[str]) -> np.ndarray: ...

    def encode_query(self, text: str, instruction: str | None = None) -> np.ndarray: ...

    def encode_queries(self, texts: Sequence[str], instruction: str | None = None) -> np.ndarray: ...


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
        if isinstance(texts, (str, bytes)) or not isinstance(texts, Sequence):
            raise ValueError("embedding texts must be a sequence of strings")
        if any(not isinstance(text, str) for text in texts):
            raise ValueError("embedding texts must be a sequence of strings")
        if not texts:
            return np.empty((0, 0), dtype=np.float64)
        rows: List[List[float]] = []
        batch_size = _strict_int_value(self.config.batch_size, "embedding batch_size", positive=True)
        expected_dimension: int | None = None
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
            if len(data) != len(batch):
                raise ValueError(
                    f"embedding response count mismatch for batch: expected {len(batch)}, got {len(data)}"
                )
            ordered: list[tuple[int, Any]] = []
            seen_indices: set[int] = set()
            for item in data:
                if not isinstance(item, Mapping) or "index" not in item or "embedding" not in item:
                    raise ValueError("embedding response items must contain index and embedding")
                index = _strict_int_value(item["index"], "embedding response index", nonnegative=True)
                if index >= len(batch) or index in seen_indices:
                    raise ValueError("embedding response contains an unknown or duplicate index")
                vector = item["embedding"]
                if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence):
                    raise ValueError("embedding response vector must be a sequence")
                try:
                    values = [float(value) for value in vector]
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError("embedding response vector must contain numeric values") from exc
                if not values or not np.all(np.isfinite(values)):
                    raise ValueError("embedding response vector must be non-empty and finite")
                if expected_dimension is None:
                    expected_dimension = len(values)
                elif len(values) != expected_dimension:
                    raise ValueError("embedding response vectors have inconsistent dimensions")
                seen_indices.add(index)
                ordered.append((index, values))
            if seen_indices != set(range(len(batch))):
                raise ValueError("embedding response indices must cover the complete batch")
            rows.extend(vector for _index, vector in sorted(ordered, key=lambda pair: pair[0]))
        if len(rows) != len(texts):
            raise ValueError(f"embedding response count mismatch: expected {len(texts)}, got {len(rows)}")
        return normalize_rows(np.asarray(rows, dtype=np.float64))

    def encode_queries(self, texts: Sequence[str], instruction: str | None = None) -> np.ndarray:
        if instruction is not None and not isinstance(instruction, str):
            raise ValueError("embedding instruction must be a string or None")
        prefix = self.config.query_instruction if instruction is None else instruction
        return self.encode([prefix + text for text in texts])

    def encode_query(self, text: str, instruction: str | None = None) -> np.ndarray:
        return self.encode_queries([text], instruction=instruction)[0]


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
        if isinstance(texts, (str, bytes)) or not isinstance(texts, Sequence):
            raise ValueError("embedding texts must be a sequence of strings")
        if any(not isinstance(text, str) for text in texts):
            raise ValueError("embedding texts must be a sequence of strings")
        if not texts:
            return np.empty((0, 0), dtype=np.float64)
        vectors = self.model.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)
        matrix = np.asarray(vectors, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[0] != len(texts) or matrix.shape[1] == 0:
            raise ValueError("local embedding model returned an invalid vector matrix")
        if not np.all(np.isfinite(matrix)):
            raise ValueError("local embedding model returned non-finite vectors")
        return normalize_rows(matrix)

    def encode_queries(self, texts: Sequence[str], instruction: str | None = None) -> np.ndarray:
        if instruction is not None and not isinstance(instruction, str):
            raise ValueError("embedding instruction must be a string or None")
        prefix = self.query_instruction if instruction is None else instruction
        return self.encode([prefix + text for text in texts])

    def encode_query(self, text: str, instruction: str | None = None) -> np.ndarray:
        return self.encode_queries([text], instruction=instruction)[0]


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "index", _strict_int_value(self.index, "rerank index", nonnegative=True))
        score = _strict_float_value(self.score, "rerank score")
        object.__setattr__(self, "score", score)


class RerankerClient:
    def __init__(self, config: EndpointConfig):
        self.config = config
        raw_space = str(getattr(config, "score_space", "unit_interval")).strip().lower().replace("-", "_")
        self.score_space = {
            "probability": "unit_interval",
            "probabilities": "unit_interval",
            "unit": "unit_interval",
            "sigmoid": "unit_interval",
            "logit": "logit_difference",
            "logit_diff": "logit_difference",
            "raw_logit_difference": "logit_difference",
        }.get(raw_space, raw_space)
        if self.score_space not in {"unit_interval", "logit_difference"}:
            raise ValueError("reranker score_space must be unit_interval or logit_difference")
        self.score_contract = str(getattr(config, "score_contract", "pointwise")).strip().lower()
        if self.score_contract not in {"pointwise", "listwise"}:
            raise ValueError("reranker score_contract must be pointwise or listwise")
        self.model_fingerprint = str(
            getattr(config, "model_fingerprint", "") or getattr(config, "model", "") or getattr(config, "endpoint", "")
        )

    def rerank(self, query: str, documents: Sequence[str], top_n: int) -> List[RerankItem]:
        if not isinstance(query, str):
            raise ValueError("rerank query must be a string")
        if isinstance(documents, (str, bytes)) or not isinstance(documents, Sequence):
            raise ValueError("rerank documents must be a sequence of strings")
        if any(not isinstance(document, str) for document in documents):
            raise ValueError("rerank documents must be a sequence of strings")
        top_n = _strict_int_value(top_n, "top_n", nonnegative=True)
        if self.score_contract != "pointwise":
            raise ValueError("listwise reranker contracts cannot be used as pointwise scores")
        if not documents or top_n == 0:
            return []
        payload: Dict[str, Any] = {
            "query": query,
            "documents": list(documents),
            "top_n": min(top_n, len(documents)),
            "return_documents": False,
        }
        if self.config.model:
            payload["model"] = self.config.model
        response = _post_json(self.config.endpoint, payload, self.config.timeout_seconds)
        if isinstance(response, dict):
            raw_results = response.get("results", response.get("data"))
        elif isinstance(response, list):
            raw_results = response
        else:
            raw_results = None
        if not isinstance(raw_results, list):
            raise ValueError("rerank response must contain results or data")
        items = []
        seen: set[int] = set()
        for item in raw_results:
            if isinstance(item, Mapping):
                if "index" not in item:
                    raise ValueError("rerank response item is missing index")
                position = _strict_int_value(item["index"], "rerank response index", nonnegative=True)
                raw_score = item.get("relevance_score", item.get("score"))
            else:
                try:
                    position = _strict_int_value(item.index, "rerank response index", nonnegative=True)
                    raw_score = item.score
                except (AttributeError, TypeError, ValueError, OverflowError) as exc:
                    raise ValueError("rerank response item must contain index and score") from exc
            if raw_score is None:
                raise ValueError("rerank response item is missing score")
            score = _strict_float_value(raw_score, "rerank response score")
            if position < 0 or position >= len(documents) or position in seen:
                raise ValueError("rerank response contains an unknown or duplicate index")
            if not np.isfinite(score):
                raise ValueError("rerank response contains a non-finite score")
            normalized_space = self.score_space.strip().lower().replace("-", "_")
            if normalized_space in {"unit_interval", "probability", "sigmoid", "unit"} and not 0.0 <= score <= 1.0:
                raise ValueError("unit-interval rerank score is outside [0, 1]")
            seen.add(position)
            items.append(RerankItem(index=position, score=score))
        return sorted(items, key=lambda item: (-item.score, item.index))[:top_n]

    def rerank_all(self, query: str, documents: Sequence[str]) -> List[RerankItem]:
        """Return a complete deterministic ranking so callers can cache once and slice later."""
        return self.rerank(query, documents, len(documents))


class GeneratorClient:
    def __init__(self, config: GeneratorConfig):
        self.config = config

    def answer(self, query: str, memories: Sequence[Memory], answer_options: str = "") -> str:
        if not isinstance(query, str) or not isinstance(answer_options, str):
            raise ValueError("generator query and answer_options must be strings")
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

    def answer_plan(self, plan: ContextPlan) -> str:
        """Send exactly the messages in a frozen :class:`ContextPlan`."""

        if not plan.within_budget:
            raise ContextPlanError("cannot send a ContextPlan that exceeds its declared budget")
        if plan.prompt_hash != generation_prompt_hash():
            raise ContextPlanError("ContextPlan prompt hash differs from GeneratorClient prompt contract")
        request_payload = plan.request_dict()
        # ``ContextPlan`` is the sole source of truth.  Endpoint is transport
        # metadata (and therefore not part of the provider JSON), but every
        # other field must already be final in the plan.  In particular,
        # ``max_tokens=0`` is an explicit value, not a sentinel to replace
        # with the client's configuration.
        declared_endpoint = request_payload.pop("endpoint", None)
        declared_endpoint_hash = request_payload.pop("endpoint_sha256", None)
        configured_endpoint_hash = hashlib.sha256(
            str(self.config.endpoint).encode("utf-8")
        ).hexdigest()
        if declared_endpoint not in (None, "", self.config.endpoint, configured_endpoint_hash):
            raise ContextPlanError("ContextPlan endpoint differs from GeneratorClient configuration")
        if declared_endpoint_hash not in (None, "", configured_endpoint_hash):
            raise ContextPlanError("ContextPlan endpoint identity differs from GeneratorClient configuration")
        declared_model = request_payload.get("model")
        if declared_model != self.config.model:
            raise ContextPlanError("ContextPlan model differs from GeneratorClient configuration")
        declared_temperature = request_payload.get("temperature")
        try:
            declared_temperature = _strict_float_value(
                declared_temperature, "ContextPlan request temperature", nonnegative=True
            )
            configured_temperature = _strict_float_value(
                self.config.temperature, "generator temperature", nonnegative=True
            )
        except ValueError as exc:
            raise ContextPlanError("ContextPlan temperature is invalid") from exc
        if declared_temperature != configured_temperature:
            raise ContextPlanError("ContextPlan temperature differs from GeneratorClient configuration")
        declared_max_tokens = request_payload.get("max_tokens")
        try:
            declared_max_tokens = _strict_int_value(
                declared_max_tokens, "ContextPlan request max_tokens", nonnegative=True
            )
            configured_max_tokens = _strict_int_value(
                self.config.max_tokens, "generator max_tokens", positive=True
            )
        except ValueError as exc:
            raise ContextPlanError("ContextPlan max_tokens is invalid") from exc
        if declared_max_tokens != configured_max_tokens:
            raise ContextPlanError("ContextPlan max_tokens differs from GeneratorClient configuration")
        if request_payload.get("messages") != [dict(message) for message in plan.messages]:
            raise ContextPlanError("ContextPlan messages differ from its declared request")
        response = _post_json(
            self.config.endpoint,
            request_payload,
            self.config.timeout_seconds,
            headers={"Authorization": f"Bearer {self.config.resolved_api_key()}"},
        )
        choices = response.get("choices") if isinstance(response, dict) else None
        if not choices:
            raise ValueError("chat response has no choices")
        return str(choices[0]["message"]["content"]).strip()


class StateEmbeddingCache:
    """Content-addressed cache for frozen option/path state embeddings.

    The key intentionally includes every identity that can change a state
    coordinate system; this prevents accidental reuse across models, options,
    queries, or posterior path orderings.
    """

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root is not None else None
        if self.root is not None:
            self.root.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, np.ndarray] = {}
        self.hits = 0
        self.misses = 0

    def key_for(
        self,
        *,
        endpoint: str = "",
        model: str = "",
        embedding_fingerprint: str = "",
        query_hash: str = "",
        ordered_path_ids: Sequence[str] = (),
        options_hash: str = "",
    ) -> str:
        payload = {
            "schema": 1,
            "endpoint": str(endpoint),
            "model": str(model),
            "embedding_fingerprint": str(embedding_fingerprint),
            "query_hash": str(query_hash),
            "ordered_path_ids": list(ordered_path_ids),
            "options_hash": str(options_hash),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def get(self, key: str) -> np.ndarray | None:
        if key in self._memory:
            self.hits += 1
            return self._memory[key].copy()
        if self.root is None:
            return None
        path = self.root / f"{key}.npy"
        if not path.is_file():
            return None
        try:
            value = np.load(path, allow_pickle=False)
            result = np.asarray(value, dtype=np.float64)
            if result.ndim != 2 or not np.all(np.isfinite(result)):
                return None
            self._memory[key] = result.copy()
            self.hits += 1
            return result
        except (OSError, ValueError):
            return None

    def put(self, key: str, value: np.ndarray) -> None:
        result = np.asarray(value, dtype=np.float64).copy()
        if result.ndim != 2 or not np.all(np.isfinite(result)):
            raise ValueError("state embedding cache values must be a finite 2-D matrix")
        self._memory[key] = result
        if self.root is None:
            return
        path = self.root / f"{key}.npy"
        temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        with temporary.open("wb") as handle:
            np.save(handle, result, allow_pickle=False)
        temporary.replace(path)

    def get_or_encode(self, key: str, encode) -> tuple[np.ndarray, bool]:
        cached = self.get(key)
        if cached is not None:
            return cached, True
        value = np.asarray(encode(), dtype=np.float64)
        self.misses += 1
        self.put(key, value)
        return value, False

    make_key = key_for
    get_or_build = get_or_encode

    @property
    def stats(self) -> dict[str, int]:
        return {"hits": int(self.hits), "misses": int(self.misses)}


class GenerationCache:
    """Deterministic text cache keyed by the complete generation request."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root is not None else None
        if self.root is not None:
            self.root.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, str] = {}
        self.hits = 0
        self.misses = 0

    def key_for(
        self,
        query: str,
        ordered_ids: Sequence[str],
        serialized_context: str,
        *,
        generator: str = "",
        endpoint: str = "",
        temperature: float = 0.0,
        max_tokens: int = 0,
        prompt_hash: str | None = None,
        answer_options: str = "",
    ) -> str:
        payload = {
            "schema": 1,
            "prompt_hash": prompt_hash or generation_prompt_hash(),
            "query": query,
            "ordered_ids": list(ordered_ids),
            "serialized_context": serialized_context,
            "generator": str(generator),
            "endpoint": str(endpoint),
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "answer_options": answer_options,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        if key in self._memory:
            self.hits += 1
            return self._memory[key]
        if self.root is None:
            return None
        path = self.root / f"{key}.json"
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            response = str(value["response"])
            self._memory[key] = response
            self.hits += 1
            return response
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def put(self, key: str, response: str) -> None:
        value = str(response)
        self._memory[key] = value
        if self.root is None:
            return
        path = self.root / f"{key}.json"
        temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps({"response": value}, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(path)

    def answer(
        self,
        client: GeneratorClient,
        query: str,
        memories: Sequence[Memory],
        answer_options: str = "",
    ) -> tuple[str, bool]:
        # The generator applies the context-token budget before constructing
        # its request.  Build the cache key from that exact effective request,
        # including source/time headers, so two memories with equal text but
        # different provenance cannot collide.  This also makes direct uses of
        # GenerationCache obey the same semantics as experiment callers.
        effective_memories = fit_context_budget(memories, client.config.context_token_budget)
        messages = build_generation_messages(query, effective_memories, answer_options)
        serialized = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        key = self.key_for(
            query,
            [memory.memory_id for memory in effective_memories],
            serialized,
            generator=client.config.model,
            endpoint=client.config.endpoint,
            temperature=client.config.temperature,
            max_tokens=client.config.max_tokens,
            answer_options=answer_options,
        )
        cached = self.get(key)
        if cached is not None:
            return cached, True
        response = client.answer(query, effective_memories, answer_options)
        self.misses += 1
        self.put(key, response)
        return response, False

    def answer_plan(self, client: GeneratorClient, plan: ContextPlan) -> tuple[str, bool]:
        """Cache and send the exact frozen request represented by ``plan``."""

        payload = {
            "request": plan.request_dict(),
            # The transport endpoint is not part of the JSON request but is
            # part of cache identity.  Include it separately so two services
            # with identical models/prompts cannot share a response.
            "endpoint": client.config.endpoint,
            "client_model": client.config.model,
            "context_hash": plan.context_hash,
        }
        key = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        cached = self.get(key)
        if cached is not None:
            return cached, True
        response = client.answer_plan(plan)
        self.misses += 1
        self.put(key, response)
        return response, False

    make_key = key_for
    get_or_generate = answer

    @property
    def stats(self) -> dict[str, int]:
        return {"hits": int(self.hits), "misses": int(self.misses)}


__all__ = [
    "Embedder",
    "RemoteEmbeddingClient",
    "LocalSentenceTransformerEmbedder",
    "RerankItem",
    "RerankerClient",
    "GeneratorClient",
    "StateBasisProvider",
    "StateEmbeddingCache",
    "GenerationCache",
    "estimate_tokens",
    "context_token_count",
    "fit_context_budget",
    "ContextPlan",
    "ContextPlanError",
    "build_context_plan",
    "build_generation_messages",
    "generation_prompt_hash",
]
