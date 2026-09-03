from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml


@dataclass(frozen=True, init=False)
class RetrievalConfig:
    """One runtime configuration for every BridgeTree module combination.

    ``first_hop_width`` remains an accepted constructor keyword for source
    compatibility, but ``initial_width`` is the canonical serialized name.
    """

    initial_width: int = 12
    branch_width: int = 8
    context_size: int = 5
    search_budget: int = 64
    max_ann_calls: int | None = None
    max_candidate_exposure: int | None = None
    max_depth: int = 2
    cluster_mode: str = "fixed"
    cluster_count: int = 4
    max_clusters: int = 8
    min_cluster_size: int = 1
    search_order: str = "best_first"
    feature_mode: str = "rho"
    selection_mode: str = "rho_logdet"
    stop_mode: str = "budget"
    diagnostic_level: str = "light"
    root_anchor_weight: float = 0.0
    mmr_lambda: float = 0.7
    index_backend: str = "exact"
    faiss_exclusion_margin: int = 32
    tie_tolerance: float = 1e-12

    def __init__(
        self,
        initial_width: int = 12,
        branch_width: int = 8,
        context_size: int = 5,
        search_budget: int = 64,
        max_ann_calls: int | None = None,
        max_candidate_exposure: int | None = None,
        max_depth: int = 2,
        cluster_mode: str = "fixed",
        cluster_count: int = 4,
        max_clusters: int = 8,
        min_cluster_size: int = 1,
        search_order: str = "best_first",
        feature_mode: str = "rho",
        selection_mode: str = "rho_logdet",
        stop_mode: str = "budget",
        diagnostic_level: str = "light",
        root_anchor_weight: float = 0.0,
        mmr_lambda: float = 0.7,
        index_backend: str = "exact",
        faiss_exclusion_margin: int = 32,
        tie_tolerance: float = 1e-12,
        first_hop_width: int | None = None,
    ):
        if first_hop_width is not None:
            if initial_width != 12 and initial_width != first_hop_width:
                raise ValueError("initial_width and legacy first_hop_width disagree")
            initial_width = first_hop_width
        values = locals()
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, values[name])

    @property
    def first_hop_width(self) -> int:
        """Deprecated read-only alias for older integrations."""
        return self.initial_width

    def validate(self) -> None:
        positive = {
            "initial_width": self.initial_width,
            "branch_width": self.branch_width,
            "context_size": self.context_size,
            "search_budget": self.search_budget,
            "max_depth": self.max_depth,
            "cluster_count": self.cluster_count,
            "max_clusters": self.max_clusters,
            "min_cluster_size": self.min_cluster_size,
            "faiss_exclusion_margin": self.faiss_exclusion_margin,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"retrieval.{name} must be positive")
        if self.max_ann_calls is not None and self.max_ann_calls <= 0:
            raise ValueError("retrieval.max_ann_calls must be positive when set")
        if self.max_candidate_exposure is not None and self.max_candidate_exposure <= 0:
            raise ValueError("retrieval.max_candidate_exposure must be positive when set")
        if self.initial_width > self.search_budget:
            raise ValueError("retrieval.initial_width must be <= retrieval.search_budget")
        if self.context_size > self.search_budget:
            raise ValueError("retrieval.context_size must be <= retrieval.search_budget")
        if self.max_candidate_exposure is not None and self.context_size > self.max_candidate_exposure:
            raise ValueError("retrieval.context_size must be <= retrieval.max_candidate_exposure")
        if self.max_candidate_exposure is not None and self.initial_width > self.max_candidate_exposure:
            raise ValueError("retrieval.initial_width must be <= retrieval.max_candidate_exposure")
        choices = {
            "cluster_mode": (self.cluster_mode, {"none", "fixed", "effective_rank"}),
            "search_order": (self.search_order, {"best_first", "bfs"}),
            "feature_mode": (self.feature_mode, {"rho", "path_conditioned"}),
            "selection_mode": (
                self.selection_mode,
                {"rho_topk", "mmr", "rho_logdet", "path_logdet"},
            ),
            "stop_mode": (self.stop_mode, {"budget", "certificate_or_budget"}),
            "diagnostic_level": (self.diagnostic_level, {"off", "light", "full"}),
            "index_backend": (self.index_backend, {"exact", "faiss"}),
        }
        for name, (value, allowed) in choices.items():
            if value not in allowed:
                raise ValueError(f"retrieval.{name} must be one of {sorted(allowed)}")
        if self.selection_mode == "path_logdet" and self.feature_mode != "path_conditioned":
            raise ValueError("retrieval.path_logdet requires feature_mode=path_conditioned")
        if self.selection_mode == "rho_logdet" and self.feature_mode != "rho":
            raise ValueError("retrieval.rho_logdet requires feature_mode=rho")
        if self.stop_mode == "certificate_or_budget" and self.selection_mode not in {
            "rho_logdet",
            "path_logdet",
        }:
            raise ValueError("retrieval.certificate_or_budget requires a logdet selection mode")
        if not 0.0 <= self.root_anchor_weight <= 1.0:
            raise ValueError("retrieval.root_anchor_weight must be in [0, 1]")
        if not 0.0 <= self.mmr_lambda <= 1.0:
            raise ValueError("retrieval.mmr_lambda must be in [0, 1]")


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
        "Instruct: Retrieve past personal interactions that help answer the current request\nQuery: "
    )


@dataclass(frozen=True)
class RerankerConfig(EndpointConfig):
    cache_dir: str = "outputs/rerank_cache"


@dataclass(frozen=True)
class GeneratorConfig(EndpointConfig):
    api_key: str = "Aa@11111"
    api_key_env: str = "BRIDGETREE_CHAT_API_KEY"
    temperature: float = 0.0
    max_tokens: int = 512
    context_token_budget: int = 8192

    def resolved_api_key(self) -> str:
        return os.environ.get(self.api_key_env, self.api_key)


@dataclass(frozen=True)
class ModelsConfig:
    embedding: EmbeddingConfig
    reranker: RerankerConfig
    generator: GeneratorConfig


@dataclass(frozen=True)
class BridgeRerankConfig:
    """Effect-first candidate discovery followed by task-aware reranking."""

    dense_pool_width: int = 20
    anchor_width: int = 12
    expand_branch_count: int = 2
    branch_overfetch_width: int = 8
    branch_keep_width: int = 4
    probe_mode: str = "query_anchor"
    path_filter: bool = True
    use_answer_options: bool = True
    include_time_metadata: bool = True
    bridge_query_instruction: str = (
        "Instruct: Retrieve a distinct past personal interaction that complements an anchor "
        "for answering the current request\nQuery: "
    )
    final_rerank_instruction: str = (
        "Rank past user interactions by how useful they are for selecting the best personalized answer. "
        "Prioritize explicit user preferences, constraints, experiences, and the latest state when preferences "
        "evolve. A passage that is merely topically related but cannot distinguish the answer choices should "
        "rank low."
    )
    path_filter_instruction: str = (
        "Rank candidate interactions by whether they add distinct, independently usable personal evidence "
        "beyond the anchor for answering the current request. Avoid anchor paraphrases and merely topical "
        "passages."
    )

    def validate(self, retrieval: RetrievalConfig) -> None:
        positive = {
            "dense_pool_width": self.dense_pool_width,
            "anchor_width": self.anchor_width,
            "expand_branch_count": self.expand_branch_count,
            "branch_overfetch_width": self.branch_overfetch_width,
            "branch_keep_width": self.branch_keep_width,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"bridge_rerank.{name} must be positive")
        if retrieval.context_size > self.dense_pool_width:
            raise ValueError("retrieval.context_size must be <= bridge_rerank.dense_pool_width")
        if self.anchor_width > self.dense_pool_width:
            raise ValueError("bridge_rerank.anchor_width must be <= bridge_rerank.dense_pool_width")
        if self.branch_keep_width > self.branch_overfetch_width:
            raise ValueError("bridge_rerank.branch_keep_width must be <= bridge_rerank.branch_overfetch_width")
        if self.expand_branch_count > retrieval.cluster_count:
            raise ValueError("bridge_rerank.expand_branch_count must be <= retrieval.cluster_count")
        if self.probe_mode not in {"centroid", "query_anchor"}:
            raise ValueError("bridge_rerank.probe_mode must be centroid or query_anchor")
        for name in ("bridge_query_instruction", "final_rerank_instruction", "path_filter_instruction"):
            if not getattr(self, name).strip():
                raise ValueError(f"bridge_rerank.{name} cannot be empty")


@dataclass(frozen=True)
class DataConfig:
    raw_dir: str = "data/raw/personamem-v1"
    processed_dir: str = "data/processed/personamem-v1"
    split: str = "32k"
    include_system_persona: bool = True
    memory_granularity: str = "user_assistant_pair"


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
    bridge_rerank: BridgeRerankConfig = field(default_factory=BridgeRerankConfig)
    data: DataConfig = field(default_factory=DataConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    def validate(self) -> None:
        self.retrieval.validate()
        self.bridge_rerank.validate(self.retrieval)
        if self.models.embedding.backend not in {"remote", "local"}:
            raise ValueError("models.embedding.backend must be remote or local")
        if self.data.split not in {"32k", "128k", "1M"}:
            raise ValueError("data.split must be one of 32k, 128k, 1M")
        if self.data.memory_granularity not in {"user_only", "user_assistant_pair"}:
            raise ValueError("data.memory_granularity must be user_only or user_assistant_pair")
        if self.models.generator.max_tokens <= 0 or self.models.generator.context_token_budget <= 0:
            raise ValueError("generator token budgets must be positive")

    def resolved_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def config_hash(self) -> str:
        payload = json.dumps(self.resolved_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def _retrieval_from_mapping(raw: Mapping[str, Any]) -> RetrievalConfig:
    values = dict(raw)
    if "first_hop_width" in values:
        if "initial_width" in values and values["initial_width"] != values["first_hop_width"]:
            raise ValueError("retrieval.initial_width and first_hop_width disagree")
        values["initial_width"] = values.pop("first_hop_width")
    return RetrievalConfig(**values)


def load_config(path: str | Path, override_path: str | Path | None = None) -> AppConfig:
    raw = _read_yaml(Path(path))
    if override_path is not None:
        raw = _deep_merge(raw, _read_yaml(Path(override_path)))

    retrieval = _retrieval_from_mapping(raw.get("retrieval", {}))
    models_raw = raw.get("models", {})
    embedding = EmbeddingConfig(**models_raw.get("embedding", {}))
    reranker = RerankerConfig(**models_raw.get("reranker", {}))
    generator = GeneratorConfig(**models_raw.get("generator", {}))
    config = AppConfig(
        seed=int(raw.get("seed", 42)),
        retrieval=retrieval,
        models=ModelsConfig(embedding=embedding, reranker=reranker, generator=generator),
        bridge_rerank=BridgeRerankConfig(**raw.get("bridge_rerank", {})),
        data=DataConfig(**raw.get("data", {})),
        runtime=RuntimeConfig(**raw.get("runtime", {})),
    )
    config.validate()
    return config


def apply_runtime_overrides(config: AppConfig, overrides: Mapping[str, Any]) -> AppConfig:
    """Apply explicit CLI/script values after YAML resolution."""
    retrieval_fields = set(RetrievalConfig.__dataclass_fields__)
    retrieval_values = {key: value for key, value in overrides.items() if key in retrieval_fields and value is not None}
    current = config
    if retrieval_values:
        current = replace(current, retrieval=replace(current.retrieval, **retrieval_values))
    bridge_fields = set(BridgeRerankConfig.__dataclass_fields__)
    bridge_values = {key: value for key, value in overrides.items() if key in bridge_fields and value is not None}
    if bridge_values:
        current = replace(current, bridge_rerank=replace(current.bridge_rerank, **bridge_values))
    if overrides.get("seed") is not None:
        current = replace(current, seed=int(overrides["seed"]))
    data_values = {
        key: overrides[key]
        for key in ("memory_granularity", "include_system_persona")
        if overrides.get(key) is not None
    }
    if data_values:
        current = replace(current, data=replace(current.data, **data_values))
    current.validate()
    return current
