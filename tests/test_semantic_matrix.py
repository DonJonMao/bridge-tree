import json

import numpy as np
import pytest

from bridgetree.clients import ContextPlanError
from bridgetree.config import RetrievalConfig
from bridgetree.experiment import SEMANTIC_MATRIX_ARCHITECTURES, semantic_matrix_configs
from bridgetree.information import SemanticFeatureProvider
from bridgetree.measure import display_path_hypotheses, propagate_frozen_graph, shuffle_frozen_graph
from bridgetree.protocol import _legacy_split, init_protocol, protocol_examples
from bridgetree.semantic import (
    build_query_conditioned_representation_text,
    discover_frozen_graph,
    rho_squared_quality_records,
    semantic_retrieve,
)
from bridgetree.types import FrozenProposalGraph, Memory


def _memory_bank() -> list[Memory]:
    return [
        Memory(
            "m0",
            "The user prefers tea.",
            0.0,
            "source-0",
            metadata={"roles": ["user"], "time": {"observed_start": 0, "observed_end": 0}},
        ),
        Memory(
            "m1",
            "The user prefers coffee now.",
            1.0,
            "source-1",
            metadata={"roles": ["user", "assistant"], "time": {"observed_start": 1, "observed_end": 1}},
        ),
        Memory(
            "m2",
            "An unrelated fact.",
            2.0,
            "source-2",
            metadata={"roles": ["user"], "time": {"observed_start": 2, "observed_end": 2}},
        ),
    ]


def _frozen_chain() -> FrozenProposalGraph:
    return FrozenProposalGraph(
        memory_ids=("m0", "m1", "m2"),
        edges=(("m0", "m1"), ("m0", "m2")),
        edge_weights=(("m0", "m1", 1.0), ("m0", "m2", 1.0)),
        root_mass={"m0": 1.0},
        layers=(("m0",), ("m1", "m2")),
        parent_sources=(("m0", ()), ("m1", ("m0",)), ("m2", ("m0",))),
        proposal_records=(("m0", "m1", 2, 0, 1.0), ("m0", "m2", 2, 1, 0.5)),
    )


def test_semantic_matrix_declares_the_two_legacy_controls_and_shared_s_rows():
    configs = semantic_matrix_configs(
        RetrievalConfig(initial_width=2, branch_width=1, context_size=2, search_budget=3)
    )
    assert tuple(configs) == SEMANTIC_MATRIX_ARCHITECTURES
    assert SEMANTIC_MATRIX_ARCHITECTURES == ("L0", "L1", "S0", "S1", "S2", "S3", "S2-shuffle")
    assert configs["L0"].quality_mode == "rho"
    assert configs["L0"].path_mode == "none"
    assert configs["L1"].path_mode == "single_path"
    assert configs["S0"].selection_mode == "pure_rerank"
    assert configs["S3"].feature_mode == "query_conditioned"
    assert configs["S3"].representation_mode == "query_conditioned"
    assert configs["S2-shuffle"].path_mode == "shuffle"


def test_rho_squared_quality_requires_an_explicit_legacy_trace():
    measure = propagate_frozen_graph(_frozen_chain())
    with pytest.raises(ValueError, match="explicit legacy_rho"):
        rho_squared_quality_records(measure)

    records = rho_squared_quality_records(
        measure,
        legacy_rho={identifier: 0.8 for identifier in measure.graph.memory_ids},
    )
    assert set(records) == set(measure.graph.memory_ids)
    for _identifier, record in records.items():
        assert record.scorer_fingerprint == "legacy-rho2"
        assert record.value == pytest.approx(0.64)
        assert np.sqrt(record.value) == pytest.approx(0.8)


def test_explicit_legacy_rho_is_independent_of_random_path_access():
    measure = propagate_frozen_graph(_frozen_chain())
    records = rho_squared_quality_records(
        measure,
        legacy_rho={"m0": 0.8, "m1": 0.4, "m2": 0.25},
    )
    assert records["m0"].value == pytest.approx(0.64)
    assert records["m1"].value == pytest.approx(0.16)
    assert records["m2"].value == pytest.approx(0.0625)


def test_shuffle_moves_source_identity_without_changing_memory_vectors():
    graph = FrozenProposalGraph(
        memory_ids=("a", "c", "b", "d"),
        edges=(("a", "b"), ("c", "d")),
        edge_weights=(("a", "b", 1.0), ("c", "d", 1.0)),
        root_mass={"a": 0.5, "c": 0.5},
        layers=(("a", "c"), ("b", "d")),
    )
    measure = propagate_frozen_graph(graph)
    vectors = {
        "a": np.array([1.0, 0.0]),
        "c": np.array([0.0, 1.0]),
        "b": np.array([1.0, 0.0]),
        "d": np.array([0.0, 1.0]),
    }
    quality = {identifier: 1.0 for identifier in graph.memory_ids}
    provider = SemanticFeatureProvider(
        graph, measure, quality,
        records={identifier: {"vector": value} for identifier, value in vectors.items()},
        representation_provider=vectors,
        path_mode="shuffle",
        shuffle_seed=42,
    )
    baseline = SemanticFeatureProvider(
        graph, measure, quality,
        records={identifier: {"vector": value} for identifier, value in vectors.items()},
        representation_provider=vectors,
        path_mode="posterior_expected_scatter",
    )
    assert provider._ancestor_ids("b") == ("c",)
    assert np.linalg.norm(provider.materialize("b").feature) > np.linalg.norm(baseline.materialize("b").feature)
    shuffled = shuffle_frozen_graph(graph, seed=42)
    assert shuffled.layers == graph.layers
    assert set(shuffled.edges) == {("a", "d"), ("c", "b")}
    assert shuffled.proposal_config["shuffle_effective_nodes"] == 2


def test_truncated_display_path_keeps_local_parent_posterior():
    graph = FrozenProposalGraph(
        memory_ids=("a", "c", "b"),
        edges=(("a", "b"), ("c", "b")),
        edge_weights=(("a", "b", 1.0), ("c", "b", 1.0)),
        root_mass={"a": 0.5, "c": 0.5},
        layers=(("a", "c"), ("b",)),
    )
    measure = propagate_frozen_graph(graph)
    paths, truncated = display_path_hypotheses(measure, "b", max_paths=1)
    assert truncated
    assert paths[0].branch_id == "representative_local_parent"
    assert paths[0].posterior == pytest.approx(0.5)


def test_query_conditioned_representation_is_deterministic_and_redacts_gold_metadata():
    memory = _memory_bank()[1]
    first = build_query_conditioned_representation_text(
        "Which drink?",
        "['(a) tea', '(b) coffee']",
        memory,
        query_cutoff=1,
        query_metadata={"topic": "drink", "gold_answer": "(b)", "nested": {"label": "(b)"}},
        embedding_model="fake-embedding",
        embedding_fingerprint="abc",
    )
    second = build_query_conditioned_representation_text(
        "Which drink?",
        "['(a) tea', '(b) coffee']",
        memory,
        query_cutoff=1,
        query_metadata={"nested": {"label": "(b)"}, "gold_answer": "(b)", "topic": "drink"},
        embedding_model="fake-embedding",
        embedding_fingerprint="abc",
    )
    assert first == second
    assert "(b)" not in first.split("[Representation metadata:", 1)[1].split("\n\nTask:", 1)[0]
    assert "Which drink?" in first
    assert memory.text in first
    assert "fake-embedding" in first
    assert "abc" in first


def test_query_conditioned_semantic_retrieval_requires_an_explicit_representation_provider():
    memories = _memory_bank()
    vectors = np.eye(3, dtype=np.float64)
    config = RetrievalConfig(
        profile="semantic_path_v1",
        initial_width=2,
        branch_width=1,
        context_size=1,
        search_budget=3,
        feature_mode="query_conditioned",
        representation_mode="query_conditioned",
        quality_mode="direct_cosine",
        path_mode="posterior_expected_scatter",
        selection_mode="semantic_path_logdet",
    )
    with pytest.raises(ValueError, match="requires an explicit representation_provider"):
        semantic_retrieve(
            "Which?",
            np.array([1.0, 0.0, 0.0]),
            memories,
            vectors,
            config,
            frozen_graph=_frozen_chain(),
        )


def test_semantic_retrieval_strict_context_plan_does_not_return_over_budget_context():
    memories = _memory_bank()
    vectors = np.eye(3, dtype=np.float64)
    config = RetrievalConfig(
        profile="semantic_path_v1",
        initial_width=2,
        branch_width=1,
        context_size=2,
        search_budget=3,
        feature_mode="cached_memory",
        quality_mode="direct_cosine",
        path_mode="posterior_expected_scatter",
        selection_mode="semantic_path_logdet",
        context_strict=True,
    )
    with pytest.raises(ContextPlanError, match="exceeding budget"):
        semantic_retrieve(
            "Which?",
            np.array([1.0, 0.0, 0.0]),
            memories,
            vectors,
            config,
            frozen_graph=_frozen_chain(),
            context_token_budget=1,
        )


def test_discovery_audits_duplicate_and_unadmitted_raw_exposure():
    memories = _memory_bank()
    from bridgetree.budget import SearchBudget

    budget = SearchBudget(max_unique_nodes=1, max_candidate_exposure=10)
    graph, diagnostics, tracker, _index = discover_frozen_graph(
        memories,
        np.eye(3, dtype=np.float64),
        np.array([1.0, 0.0, 0.0]),
        initial_width=2,
        branch_width=1,
        max_depth=1,
        budget=budget,
        initial_hits=[("m0", 0.9), ("m0", 0.8), ("m1", 0.7)],
    )
    assert graph.memory_ids == ("m0",)
    assert diagnostics["raw_exposure_count"] == 3
    assert diagnostics["unadmitted_unique_ids"] == ["m1"]
    assert tracker.snapshot().duplicate_proposals == 1


def test_legacy_manifest_reconstruction_keeps_historical_split_order(tmp_path):
    examples = []
    for index in range(12):
        examples.append(
            {
                "persona_id": f"p{index}",
                "question_id": f"q{index}",
                "question_type": "preference",
                "topic": "x",
                "query": f"query {index}",
                "correct_answer": "(a)",
                "all_options": "['(a)', '(b)']",
                "shared_context_id": f"c{index}",
                "end_index": 1,
                "messages": [{"role": "user", "content": f"memory {index}"}],
            }
        )
    from bridgetree.personamem import PersonaMemExample

    rows = [PersonaMemExample(**item) for item in examples]
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    contexts_path = raw_dir / "shared_contexts_32k.jsonl"
    contexts_path.write_text(
        "".join(json.dumps({row.shared_context_id: row.messages}) + "\n" for row in rows),
        encoding="utf-8",
    )
    questions_path = raw_dir / "questions_32k.csv"
    questions_path.write_text("", encoding="utf-8")
    # ``init_protocol`` only needs the question/context files when it loads
    # examples from disk; supply the in-memory rows while retaining the source
    # directory for provenance snapshots.
    splits = _legacy_split(rows, 17)
    legacy = {
        "seed": 17,
        "split": "32k",
        "validation": {"personas": list(splits.validation_personas)},
        "test": {"personas": list(splits.test_personas)},
        "train": {"personas": list(splits.train_personas)},
    }
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    manifest = init_protocol(
        output_path=tmp_path / "protocol.json",
        examples=rows,
        raw_dir=raw_dir,
        split="32k",
        seed=17,
        from_legacy_manifest=legacy_path,
    )
    expected_development = [str(item.question_id) for item in tuple(splits.validation) + tuple(splits.test)]
    expected_confirmatory = [str(item.question_id) for item in splits.train]
    assert manifest["roles"]["development-seen"]["question_ids"] == expected_development
    assert manifest["roles"]["confirmatory-test"]["question_ids"] == expected_confirmatory
    assert [item.question_id for item in protocol_examples(manifest, rows, "development")] == expected_development
    assert [item.question_id for item in protocol_examples(manifest, rows, "confirmatory")] == expected_confirmatory
