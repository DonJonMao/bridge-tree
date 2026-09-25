"""Boundary and end-to-end acceptance of the deployed evidence method."""

import json
from dataclasses import replace

import numpy as np
import pytest

from bridgetree.clients import GeneratorClient
from bridgetree.config import GeneratorConfig
from bridgetree.dependency_config import load_dependency_config
from bridgetree.dependency_retrieval import DependencyRetriever
from bridgetree.evidence_config import EvidenceSearchConfig, EvidenceSelectionConfig
from bridgetree.metrics import extract_option_label
from bridgetree.types import Memory


def test_new_config_is_active_strict_and_hashed(tmp_path):
    config = load_dependency_config("configs/evidence_bridge.yaml")
    assert config.methods == ("dense", "activation", "evidence_bridge")
    assert config.evidence_bridge.search.root_selection == "diverse"
    assert config.evidence_bridge.selection.max_llm_calls == 24
    assert "evidence_bridge" in config.resolved_dict()
    changed = replace(config, evidence_bridge=replace(config.evidence_bridge, gap_ann_calls=1))
    assert changed.config_hash() != config.config_hash()
    override = tmp_path / "override.yaml"
    override.write_text("evidence_bridge:\n  search:\n    mystery: 1\n")
    with pytest.raises(ValueError, match="unknown evidence_bridge.search"):
        load_dependency_config("configs/evidence_bridge.yaml", override)
    with pytest.raises(ValueError):
        EvidenceSearchConfig(quantum_new_sets=3)
    with pytest.raises(ValueError):
        EvidenceSelectionConfig(max_llm_calls=True)
    with pytest.raises(ValueError):
        EvidenceSelectionConfig(map_batch_token_budget=20000)


def test_evidence_transport_preserves_messages_and_separates_output_budget(monkeypatch):
    from bridgetree import clients

    calls = []

    def post(endpoint, payload, timeout, headers):
        calls.append((endpoint, payload, timeout, headers))
        return {"choices": [{"message": {"content": '{"requirements": []}'}}]}

    monkeypatch.setattr(clients, "_post_json", post)
    client = GeneratorClient(
        GeneratorConfig(endpoint="http://fixture.invalid/chat", model="frozen", max_tokens=512, api_key="fixture-key")
    )
    messages = [
        {"role": "system", "content": "Return an evidence plan."},
        {"role": "user", "content": "Why did my preference change?"},
    ]
    result = client.complete_messages(messages, operation="evidence_plan", max_tokens=4096)
    assert json.loads(result) == {"requirements": []}
    assert calls[0][1]["messages"] == messages
    assert calls[0][1]["max_tokens"] == 4096
    assert "Answer options" not in json.dumps(calls[0][1])
    assert client.config.max_tokens == 512
    with pytest.raises(ValueError, match="evidence_"):
        client.complete_messages(messages, operation="generation", max_tokens=4096)


def test_gap_probes_use_same_ann_budget_and_only_unseen_visible_memories():
    class Embedder:
        def __init__(self):
            self.queries = []

        def encode_query(self, text, instruction=None):
            self.queries.append(text)
            return np.array([1.0, 0.0])

    memories = [Memory("a", "earlier reason", 0, "a", {}), Memory("b", "later state", 1, "b", {})]
    backend = Embedder()
    retriever = DependencyRetriever(
        "query",
        memories,
        backend,
        memory_vectors=np.eye(2),
        max_ann_calls=2,
        initial_width=1,
        initial_expansion_width=0,
    )
    retriever.retrieve_dense()
    requirements = [{"id": "r1", "description": "Earlier reason", "time_scope": "past"}]
    retriever.set_information_needs(requirements)
    batch = retriever.retrieve_missing(requirements, exclude=("a",), width=1)
    assert batch.ids == ("b",)
    assert batch.stage == "evidence_gap"
    assert retriever.ann_calls == 2
    exhausted = retriever.retrieve_missing(requirements, width=1)
    assert exhausted.budget_exhausted
    assert len(backend.queries) == 2
    assert "Earlier reason" in backend.queries[1]
    assert "Answer options" not in backend.queries[1]


def test_plural_options_refusal_is_not_a_label():
    assert extract_option_label("None of the options accurately reflect this. The best option is not listed.") == ""
    assert extract_option_label("The best option b is justified.") == "(b)"


def test_full_runner_evidence_path_persists_live_events_and_resumes_without_calls(tmp_path):
    from test_dependency_experiment import FakeEmbedder, FakeReranker, extended_example, fake_config
    from test_evidence_selection import ScriptedBackend

    from bridgetree.dependency_experiment import run_dependency_experiment

    class Reader(ScriptedBackend):
        def __init__(self):
            super().__init__()
            self.reader_requests = []

        def answer_plan(self, plan):
            self.reader_requests.append(plan.public_dict())
            return "(a) Test-only answer supported by the supplied memories."

    config = fake_config(tmp_path, methods=("dense", "evidence_bridge"))
    config = replace(config, dependency=replace(config.dependency, max_ann_calls=12, max_scored_sets=96))
    reader = Reader()
    embedder, reranker = FakeEmbedder(), FakeReranker()
    item = replace(extended_example(), all_options='["(a) OPTION_PRIVATE_SENTINEL", "(b) Another"]')
    root = tmp_path / "run"
    run_dependency_experiment(config, root, examples=[item], embedder=embedder, reranker=reranker, generator=reader)
    outcomes = [json.loads(p.read_text()) for p in (root / "outcomes").glob("*.json")]
    assert len(outcomes) == 2
    assert all(o["status"] == "success" for o in outcomes), [(o.get("error")) for o in outcomes]
    output = next(o for o in outcomes if o["task"]["method_id"] == "evidence_bridge")
    assert output["costs"]["generator_calls"] == 1
    assert output["costs"]["evidence_calls"] >= 3
    assert output["costs"]["ann_calls"] <= 12
    assert output["costs"]["scored_sets"] <= 96
    assert "OPTION_PRIVATE_SENTINEL" not in json.dumps(reader.requests)
    assert "OPTION_PRIVATE_SENTINEL" in json.dumps(reader.reader_requests)
    summary = output["diagnostics"]["evidence_bridge_summary"]
    assert summary["search"]["visited_initial_roots"] >= 2
    assert summary["selection"]["coverage_counts"]["covered"] == 1
    artifact = json.loads((root / "candidate_pool" / f"{output['task']['task_id']}.json").read_text())
    selection = artifact["evidence_selection"]
    assert set(selection["candidate_ids"]) == set(selection["mapped_candidate_ids"])
    assert selection["requests"][0]["operation"] == "evidence_plan"
    assert all("raw_response" in request for request in selection["requests"])
    live = [json.loads(line) for line in (root / "modules" / "events.jsonl").read_text().splitlines()]
    assert {e["module"] for e in live} >= {"planner", "evidence", "scheduler", "target", "selection", "archive"}
    assert any(e.get("event") == "evidence_response_validated" for e in live)
    assert all(e["record_kind"] == "live" for e in live)
    selection_stop = next(e for e in live if e["event"] == "evidence_selection_stop")
    operations = selection_stop["costs"]["evidence_calls_by_operation"]
    assert operations["evidence_plan"] == 1
    assert operations["evidence_map"] >= 1
    assert operations["evidence_select"] >= 1
    assert selection_stop["costs"]["token_count_is_estimate"] is True
    live_snapshot = json.loads((root / "evidence_live" / f"{output['task']['task_id']}.json").read_text())
    assert all("raw_response" in r for r in live_snapshot["evidence_selection"]["requests"])
    counts = (len(reader.requests), len(reader.reader_requests), len(embedder.calls), len(reranker.calls))
    resumed = run_dependency_experiment(
        config, root, resume=True, examples=[item], embedder=embedder, reranker=reranker, generator=reader
    )
    assert resumed["resume_noop"] is True
    assert counts == (len(reader.requests), len(reader.reader_requests), len(embedder.calls), len(reranker.calls))


def test_invalid_evidence_response_keeps_partial_artifacts_and_never_calls_reader(tmp_path):
    from test_dependency_experiment import FakeEmbedder, FakeReranker, example, fake_config

    from bridgetree.dependency_experiment import run_dependency_experiment

    class InvalidReasoner:
        def __init__(self):
            self.calls = 0

        def complete_messages(self, messages, *, operation, max_tokens):
            self.calls += 1
            return "not valid JSON"

        def answer_plan(self, plan):
            raise AssertionError("must not silently fall back to reader or dense")

    config = fake_config(tmp_path, methods=("evidence_bridge",))
    generator = InvalidReasoner()
    root = tmp_path / "failed"
    run_dependency_experiment(
        config, root, examples=[example()], embedder=FakeEmbedder(), reranker=FakeReranker(), generator=generator
    )
    output = json.loads(next((root / "outcomes").glob("*.json")).read_text())
    assert output["status"] == "error"
    assert output["infrastructure_failure"] is False
    assert generator.calls == 2
    artifact = json.loads(next((root / "candidate_pool").glob("*.json")).read_text())
    assert len(artifact["evidence_selection"]["requests"]) == 2
    assert all(r["validation_status"] == "invalid" for r in artifact["evidence_selection"]["requests"])
    assert output["diagnostics"]["evidence_bridge_summary"]["selection"]["available"] is True


def test_reader_failure_keeps_evidence_and_counts_attempted_reader_separately(tmp_path):
    from test_dependency_experiment import FakeEmbedder, FakeReranker, example, fake_config
    from test_evidence_selection import ScriptedBackend

    from bridgetree.dependency_experiment import run_dependency_experiment

    class FailingReader(ScriptedBackend):
        def answer_plan(self, plan):
            raise ValueError("fixture reader failure")

    root = tmp_path / "reader_failed"
    config = fake_config(tmp_path, methods=("evidence_bridge",))
    run_dependency_experiment(
        config,
        root,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=FailingReader(),
    )
    output = json.loads(next((root / "outcomes").glob("*.json")).read_text())
    assert output["status"] == "error"
    assert output["costs"]["generator_calls"] == 1
    assert output["costs"]["evidence_calls"] >= 3
    summary = output["diagnostics"]["evidence_bridge_summary"]
    assert summary["costs"]["reader_calls"] == 1
    assert summary["costs"]["evidence_calls"] == output["costs"]["evidence_calls"]
    assert summary["selection"]["coverage_counts"]["covered"] == 1
    artifact = json.loads(next((root / "candidate_pool").glob("*.json")).read_text())
    assert artifact["evidence_selection"]["stop_reason"] == "requirements_covered"
    assert all("raw_response" in r for r in artifact["evidence_selection"]["requests"])


def test_mid_evidence_interrupt_flushes_final_live_snapshot_and_remains_pending(tmp_path):
    from test_dependency_experiment import FakeEmbedder, FakeReranker, example, fake_config
    from test_evidence_selection import ScriptedBackend

    from bridgetree.dependency_experiment import run_dependency_experiment

    class InterruptedMapper(ScriptedBackend):
        def complete_messages(self, messages, *, operation, max_tokens):
            if operation == "evidence_map":
                raise KeyboardInterrupt()
            return super().complete_messages(messages, operation=operation, max_tokens=max_tokens)

        def answer_plan(self, plan):
            raise AssertionError("interrupted evidence must not invoke reader")

    root = tmp_path / "evidence_interrupted"
    config = fake_config(tmp_path, methods=("evidence_bridge",))
    result = run_dependency_experiment(
        config,
        root,
        examples=[example()],
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
        generator=InterruptedMapper(),
    )
    assert result["status"] == "interrupted"
    assert result["summary"]["pending_tasks"] == 1
    assert result["summary"]["failed_tasks"] == 0
    snapshot = json.loads(next((root / "evidence_live").glob("*.json")).read_text())
    evidence = snapshot["evidence_selection"]
    assert snapshot["event"] == "evidence_method_failed"
    assert evidence["stop_reason"] == "interrupted"
    assert evidence["costs"]["evidence_llm_calls"] == 2
    assert evidence["requests"][-1]["error_type"] == "KeyboardInterrupt"
    assert evidence["requests"][-1]["elapsed_ms"] >= 0
    assert evidence["requests"][0]["raw_response"]
    artifact = json.loads(next((root / "candidate_pool").glob("*.json")).read_text())
    assert artifact["evidence_selection"]["stop_reason"] == "interrupted"
    events = [json.loads(line) for line in (root / "modules" / "events.jsonl").read_text().splitlines()]
    assert events[-1]["event"] == "evidence_method_failed"
    assert events[-1]["stop_reason"] == "interrupted"


def test_live_mapping_preserves_temporal_provenance_and_repaired_call_counts():
    from test_evidence_selection import ScriptedBackend, make_selector, records

    from bridgetree.diagnostic_observability import observation_scope, observe

    values = records("I previously found flashcards unsuitable for deep learning.")
    temporal = {
        "observed_start": 3,
        "observed_end": 4,
        "event_start": None,
        "event_end": None,
        "validity": "unknown",
        "time_source": "message_index",
    }
    memory = next(iter(values.values()))
    values[memory.memory_id] = replace(memory, metadata={**memory.metadata, "time": temporal})

    class RepairOnce(ScriptedBackend):
        def complete_messages(self, messages, *, operation, max_tokens):
            if operation == "evidence_plan":
                return "invalid JSON"
            return super().complete_messages(messages, operation=operation, max_tokens=max_tokens)

    events = []
    selector = make_selector(RepairOnce(), sink=lambda row: observe(row["module"], row))
    with observation_scope(events.append):
        selector.select("Why did my preference change?", values, tuple(values))
    mapping = next(row for row in events if row["event"] == "evidence_mapping_batch_completed")
    assert mapping["mappings"][0]["time_metadata"] == temporal
    counts = events[-1]["costs"]["evidence_calls_by_operation"]
    assert counts == {"evidence_plan": 1, "evidence_plan_repair": 1, "evidence_map": 1, "evidence_select": 1}
