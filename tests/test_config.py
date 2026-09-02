from dataclasses import asdict

import pytest

from bridgetree.config import RetrievalConfig, apply_runtime_overrides, load_config


def test_default_config_matches_datacenter_services():
    config = load_config("configs/default.yaml")
    assert config.models.embedding.model == "qwen3-embedding-8b"
    assert config.models.embedding.query_instruction.endswith("Query: ")
    assert config.models.reranker.endpoint.endswith(":8002/rerank")
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
