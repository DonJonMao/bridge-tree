from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from bridgetree.config import load_config
from bridgetree.dependency_config import (
    DEFAULT_DEPENDENCY_METHODS,
    DependencyConfig,
    DependencyExecutionConfig,
    load_dependency_config,
    parse_dependency_config,
)

BASE_CONFIG = Path("configs/default.yaml").resolve()


def write_yaml(path, value):
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return path


def test_canonical_chain_config_loads_deployment_and_new_resources():
    config = load_dependency_config("configs/chain_full.yaml")

    assert config.models.embedding.model == "qwen3-embedding-8b"
    assert config.models.reranker.score_contract == "pointwise"
    assert config.dependency == DependencyConfig()
    assert config.execution.methods == DEFAULT_DEPENDENCY_METHODS
    assert config.execution.log_every_questions == 10
    assert config.execution.evaluate_every_questions == 25
    assert config.execution.heartbeat_seconds == 30.0
    assert "retrieval" not in config.resolved_dict()
    assert "bridge_rerank" not in config.resolved_dict()
    assert "api_key" not in config.resolved_dict()["models"]["generator"]
    assert len(config.config_hash()) == 64


@pytest.mark.parametrize("legacy", ["chain", "retrieval", "bridge_rerank"])
def test_dependency_overlay_rejects_legacy_algorithm_sections(tmp_path, legacy):
    overlay = write_yaml(tmp_path / "overlay.yaml", {legacy: {"max_depth": 99}})

    with pytest.raises(ValueError, match="legacy section"):
        load_dependency_config(BASE_CONFIG, overlay)


def test_strict_unknown_and_resource_values_fail(tmp_path):
    unknown = write_yaml(tmp_path / "unknown.yaml", {"dependency": {"max_depth": 3}})
    with pytest.raises(ValueError, match="unknown dependency"):
        load_dependency_config(BASE_CONFIG, unknown)

    for field, value in (
        ("initial_width", True),
        ("proposal_width", 1.5),
        ("max_scored_sets", 0),
        ("pair_rescue_width", -1),
    ):
        overlay = write_yaml(tmp_path / f"{field}.yaml", {"dependency": {field: value}})
        with pytest.raises(ValueError, match=field):
            load_dependency_config(BASE_CONFIG, overlay)


def test_inherited_dependency_overlay_is_partial_not_reset(tmp_path):
    parent = write_yaml(
        tmp_path / "parent.yaml",
        {
            "base_config": str(BASE_CONFIG),
            "dependency": {"initial_width": 7, "proposal_width": 3},
            "execution": {"heartbeat_seconds": 0.5},
        },
    )
    child = write_yaml(
        tmp_path / "child.yaml",
        {
            "base_config": parent.name,
            "dependency": {"proposal_width": 2},
            "execution": {"log_every_questions": 4},
        },
    )

    config = load_dependency_config(child)
    assert config.dependency.initial_width == 7
    assert config.dependency.proposal_width == 2
    assert config.execution.heartbeat_seconds == 0.5
    assert config.execution.log_every_questions == 4


def test_command_line_overlay_can_extend_the_canonical_chain_config(tmp_path):
    overlay = write_yaml(
        tmp_path / "resource.yaml",
        {"dependency": {"proposal_width": 2}},
    )

    config = load_dependency_config("configs/chain_full.yaml", overlay)
    assert config.dependency.initial_width == 12
    assert config.dependency.proposal_width == 2
    assert config.execution.methods == DEFAULT_DEPENDENCY_METHODS


def test_methods_are_explicit_unique_and_supported():
    assert DependencyExecutionConfig(methods=["dense", "activation_no_pairs"]).methods == (
        "dense",
        "activation_no_pairs",
    )
    with pytest.raises(ValueError, match="duplicate"):
        DependencyExecutionConfig(methods=["dense", "dense"])
    with pytest.raises(ValueError, match="unsupported"):
        DependencyExecutionConfig(methods=["made_up_method"])
    with pytest.raises(ValueError, match="cannot be empty"):
        DependencyExecutionConfig(methods=[])


def test_dependency_run_requires_pointwise_reranker():
    app = load_config(BASE_CONFIG)
    listwise = replace(
        app,
        models=replace(
            app.models,
            reranker=replace(app.models.reranker, score_contract="listwise"),
        ),
    )
    with pytest.raises(ValueError, match="pointwise"):
        parse_dependency_config({}, app=listwise)


def test_runtime_frequency_compatibility_is_canonicalized_to_execution(tmp_path):
    overlay = write_yaml(
        tmp_path / "runtime.yaml",
        {
            "runtime": {
                "output_dir": "out/dependency",
                "log_every_questions": 3,
                "evaluate_every_questions": 7,
                "heartbeat_seconds": 0.25,
            }
        },
    )

    config = load_dependency_config(BASE_CONFIG, overlay)
    assert config.runtime.output_dir == "out/dependency"
    assert config.execution.log_every_questions == 3
    assert config.execution.evaluate_every_questions == 7
    assert config.execution.heartbeat_seconds == 0.25
