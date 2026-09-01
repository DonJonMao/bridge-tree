from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass(frozen=True)
class RetrievalConfig:
    first_hop_width: int = 12
    branch_width: int = 8
    context_size: int = 5
    search_budget: int = 64
    index_backend: str = "exact"
    tie_tolerance: float = 1e-12

    def validate(self) -> None:
        values = {
            "first_hop_width": self.first_hop_width,
            "branch_width": self.branch_width,
            "context_size": self.context_size,
            "search_budget": self.search_budget,
        }
        for name, value in values.items():
            if value <= 0:
                raise ValueError(f"retrieval.{name} must be positive")
        if self.search_budget < self.first_hop_width:
            raise ValueError("retrieval.search_budget must be >= retrieval.first_hop_width")
        if self.index_backend not in {"exact", "faiss"}:
            raise ValueError("retrieval.index_backend must be exact or faiss")


@dataclass(frozen=True)
class EndpointConfig:
    endpoint: str
    model: str = ""
    timeout_seconds: float = 60.0


@dataclass(frozen=True)
class EmbeddingConfig(EndpointConfig):
    backend: str = "remote"
    batch_size: int = 32
    local_model_path: str = ""
    query_instruction: str = (
        "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
    )


@dataclass(frozen=True)
class GeneratorConfig(EndpointConfig):
    api_key: str = "Aa@11111"
    api_key_env: str = "BRIDGETREE_CHAT_API_KEY"
    temperature: float = 0.0
    max_tokens: int = 512

    def resolved_api_key(self) -> str:
        return os.environ.get(self.api_key_env, self.api_key)


@dataclass(frozen=True)
class ModelsConfig:
    embedding: EmbeddingConfig
    reranker: EndpointConfig
    generator: GeneratorConfig


@dataclass(frozen=True)
class DataConfig:
    raw_dir: str = "data/raw/personamem-v1"
    processed_dir: str = "data/processed/personamem-v1"
    split: str = "32k"
    include_system_persona: bool = True


@dataclass(frozen=True)
class RuntimeConfig:
    device: str = "cpu"
    cache_dir: str = "outputs/cache"
    output_dir: str = "outputs/runs"


@dataclass(frozen=True)
class AppConfig:
    seed: int
    retrieval: RetrievalConfig
    models: ModelsConfig
    data: DataConfig = field(default_factory=DataConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    def validate(self) -> None:
        self.retrieval.validate()
        if self.models.embedding.backend not in {"remote", "local"}:
            raise ValueError("models.embedding.backend must be remote or local")
        if self.data.split not in {"32k", "128k", "1M"}:
            raise ValueError("data.split must be one of 32k, 128k, 1M")


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"configuration root must be a mapping: {path}")
    return loaded


def load_config(path: str | Path, override_path: str | Path | None = None) -> AppConfig:
    raw = _read_yaml(Path(path))
    if override_path is not None:
        raw = _deep_merge(raw, _read_yaml(Path(override_path)))

    retrieval = RetrievalConfig(**raw.get("retrieval", {}))
    models_raw = raw.get("models", {})
    embedding = EmbeddingConfig(**models_raw.get("embedding", {}))
    reranker = EndpointConfig(**models_raw.get("reranker", {}))
    generator = GeneratorConfig(**models_raw.get("generator", {}))
    config = AppConfig(
        seed=int(raw.get("seed", 42)),
        retrieval=retrieval,
        models=ModelsConfig(embedding=embedding, reranker=reranker, generator=generator),
        data=DataConfig(**raw.get("data", {})),
        runtime=RuntimeConfig(**raw.get("runtime", {})),
    )
    config.validate()
    return config
