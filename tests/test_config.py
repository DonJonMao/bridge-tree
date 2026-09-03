from dataclasses import asdict

import pytest

from bridgetree.config import BridgeRerankConfig, RetrievalConfig, apply_runtime_overrides, load_config


def test_default_config_matches_datacenter_services():
    config = load_config("configs/default.yaml")
    assert config.models.embedding.model == "qwen3-embedding-8b"
    assert config.models.embedding.query_instruction.endswith("Query: ")
    assert config.models.reranker.endpoint.endswith(":8002/rerank")
    assert config.models.reranker.cache_dir == "outputs/rerank_cache"
    assert config.bridge_rerank.dense_pool_width == 20
    assert config.models.generator.model == "deepseek-v4-flash"
    assert config.models.generator.api_key == "Aa@11111"


def test_runtime_overrides_take_priority_and_serialize_canonical_names():
    base = load_config("configs/default.yaml")
    resolved = apply_runtime_overrides(
        base,
        {
            "initial_width": 7,
            "cluster_mode": "effective_rank",
            "feature_mode": "path_conditioned",
            "selection_mode": "path_logdet",
            "stop_mode": "certificate_or_budget",
            "seed": 99,
        },
    )
    assert resolved.seed == 99
    assert resolved.retrieval.initial_width == 7
    assert resolved.retrieval.cluster_mode == "effective_rank"
    assert "initial_width" in asdict(resolved.retrieval)
    assert "first_hop_width" not in asdict(resolved.retrieval)
    assert resolved.config_hash() == resolved.config_hash()


def test_bridge_rerank_runtime_overrides_and_validation():
    base = load_config("configs/default.yaml")
    resolved = apply_runtime_overrides(
        base,
        {
            "dense_pool_width": 24,
            "anchor_width": 10,
            "branch_overfetch_width": 6,
            "branch_keep_width": 3,
            "probe_mode": "centroid",
            "path_filter": False,
        },
    )

    assert resolved.bridge_rerank.dense_pool_width == 24
    assert resolved.bridge_rerank.anchor_width == 10
    assert resolved.bridge_rerank.probe_mode == "centroid"
    assert not resolved.bridge_rerank.path_filter

    with pytest.raises(ValueError, match="branch_keep_width"):
        BridgeRerankConfig(branch_overfetch_width=2, branch_keep_width=3).validate(base.retrieval)


@pytest.mark.parametrize(
    "values",
    [
        {"context_size": 5, "search_budget": 4},
        {"feature_mode": "rho", "selection_mode": "path_logdet"},
        {"feature_mode": "path_conditioned", "selection_mode": "rho_logdet"},
        {"selection_mode": "mmr", "stop_mode": "certificate_or_budget"},
    ],
)
def test_invalid_runtime_combinations_fail_fast(values):
    with pytest.raises(ValueError):
        RetrievalConfig(**values).validate()
