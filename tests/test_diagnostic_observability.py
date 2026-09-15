"""Offline observer acceptance: visibility, privacy and algorithm invariance."""
import asyncio
import json

import numpy as np
import pytest

from bridgetree.clients import RerankItem
from bridgetree.config import RerankerConfig
from bridgetree.dependency_retrieval import DependencyRetriever, ProposalBatch
from bridgetree.dependency_scoring import SetReranker
from bridgetree.dependency_search import (
    ActivationRecord, DependencySearcher, DynamicBundleSelector, SearchStateRecord, SelectionRound,
)
from bridgetree.diagnostic_observability import ModuleEventRecorder, observation_scope, observe
from bridgetree.request_audit import AuditWriteError, request_audit_scope
from bridgetree.types import Memory


class FixtureEmbedder:
    def __init__(self):
        self.calls = []

    def encode(self, texts):
        self.calls.append(("memory", tuple(texts)))
        return np.asarray([[1.0, 0.0], [.8, .2], [.2, .8]], dtype=np.float32)

    def encode_query(self, text, instruction=None):
        self.calls.append(("query", text, instruction))
        return np.asarray([1.0, 0.0], dtype=np.float32)


class FixtureReranker:
    score_contract = "pointwise"
    score_space = "unit_interval"
    model_fingerprint = "observer-fixture-v1"

    def __init__(self, *, fail_after=None):
        self.config = RerankerConfig(endpoint="http://fixture.invalid/rerank", model="fixture")
        self.calls = []
        self.fail_after = fail_after

    def rerank_all(self, query, documents):
        self.calls.append((query, tuple(documents)))
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise RuntimeError("server failed with private response text")
        values = {(): .0, ("a",): .15, ("b",): .1, ("c",): .05,
                  ("a", "b"): .75, ("a", "c"): .1, ("b", "c"): .05,
                  ("a", "b", "c"): .65}
        return [RerankItem(index=i, score=values[tuple(
            key for key in ("a", "b", "c") if f'"memory_id":"{key}"' in document
        )]) for i, document in enumerate(documents)]


def fixture(*, cache_dir=None, batch_size=4, max_ann_calls=6, fail_after=None):
    records = {key: Memory(key, f"PRIVATE_MEMORY_{key}", index, f"source:{key}", {})
               for index, key in enumerate(("a", "b", "c"))}
    embedder = FixtureEmbedder()
    client = FixtureReranker(fail_after=fail_after)
    scorer = SetReranker("PRIVATE_QUERY", records, client, cache_dir=cache_dir,
                         batch_size=batch_size, max_input_tokens=8192)
    retriever = DependencyRetriever("PRIVATE_QUERY", list(records.values()), embedder,
                                    initial_width=2, initial_expansion_width=1,
                                    proposal_width=2, max_ann_calls=max_ann_calls)
    return scorer, retriever, client, embedder


def run_fixture(recorder, *, cache_dir=None):
    with observation_scope(recorder):
        scorer, retriever, client, embedder = fixture(cache_dir=cache_dir)
        pool = retriever.build_initial_pool()
        archive = DependencySearcher(scorer, retriever, max_scored_sets=32, pair_rescue_width=2).run(pool)
        selection = DynamicBundleSelector(scorer, max_selection_sets=32).select(archive)
    return {
        "archive": archive.public_dict(), "selection": selection.public_dict(),
        "events": scorer.events, "reranker_calls": client.calls, "embedding_calls": embedder.calls,
        "counts": (scorer.scored_sets, scorer.reranker_adapter_requests,
                   scorer.memory_cache_hits, scorer.persistent_cache_hits, retriever.ann_calls),
    }


def read_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_disabled_observer_does_not_serialize_or_validate():
    class PoisonRecord:
        def public_dict(self):
            raise AssertionError("disabled observer must not serialize")

    observe("deliberately_invalid_module", PoisonRecord())
    with observation_scope(None):
        observe("scoring", PoisonRecord())


def test_scopes_restore_after_disable_and_exception():
    events = []
    with observation_scope(events.append):
        observe("execution", "first")
        with observation_scope(None):
            observe("execution", "disabled")
        with pytest.raises(RuntimeError):
            with observation_scope(lambda event: None):
                raise RuntimeError("scope cleanup")
        observe("execution", "last")
    observe("execution", "outside")
    assert [event["event"] for event in events] == ["first", "last"]


def test_async_contexts_do_not_cross_contaminate():
    async def worker(identifier):
        events = []
        with request_audit_scope({"task_id": identifier}), observation_scope(events.append):
            await asyncio.sleep(0)
            observe("execution", "task_started")
        return events

    async def main():
        return await asyncio.gather(worker("a"), worker("b"))

    left, right = asyncio.run(main())
    assert left[0]["task_id"] == "a"
    assert right[0]["task_id"] == "b"


def test_events_are_flushed_before_scope_exit_and_metadata_survives(tmp_path):
    recorder = ModuleEventRecorder(tmp_path, run_identity="run:observer", metadata={"condition_id": "base"})
    with request_audit_scope({"task_id": "t1", "question_id": "q1", "task_attempt": 2, "phase": "score"}):
        with observation_scope(recorder):
            observe("scoring", "set_score", ids=("a",), score=.75, query="PRIVATE_QUERY")
            combined = read_events(tmp_path / "modules/events.jsonl")
            separate = read_events(tmp_path / "modules/scoring.jsonl")
            assert combined == separate
            assert combined[0]["run_identity"] == "run:observer"
            assert combined[0]["question_id"] == "q1"
            assert combined[0]["task_id"] == "t1"
            assert combined[0]["task_attempt"] == 2
            assert combined[0]["condition_id"] == "base"
            assert combined[0]["phase"] == "score"
            assert combined[0]["sequence"] == 1
            assert "query" not in combined[0]
    assert "not causal proof" in combined[0]["interpretation"]


def test_strict_recursive_filter_excludes_text_credentials_and_freeform_errors(tmp_path):
    recorder = ModuleEventRecorder(tmp_path)
    with observation_scope(recorder):
        observe("activation", "activation_measured", sets={"P": ["a"], "probe_text": "PRIVATE_PROBE"},
                query="PRIVATE_QUERY", document="PRIVATE_DOCUMENT", options=["PRIVATE_OPTION"],
                response="PRIVATE_RESPONSE", endpoint="http://private.invalid", api_key="PRIVATE_KEY",
                detail="private exception response", reason="score_budget_exhausted",
                source="Bearer super-secret", target_id="https://private.invalid",
                premise_ids=["sk-abcdefgh123456"], P=.1, Pe=.2, PG=.3, PGe=.8)
    event = read_events(recorder.path)[0]
    raw = recorder.path.read_text()
    assert "PRIVATE_" not in raw
    assert "private.invalid" not in raw and "super-secret" not in raw and "sk-abcdefgh" not in raw
    assert event["sets"] == {"P": ["a"]}
    assert event["detail"] == "[redacted]"
    assert event["reason"] == "score_budget_exhausted"
    assert event["PGe"] == .8


def test_unknown_single_token_reason_is_not_treated_as_safe_error_text(tmp_path):
    recorder = ModuleEventRecorder(tmp_path, metadata={"run_identity": "metadata-run"})
    with observation_scope(recorder):
        observe("stop", "selection_stop", reason="PRIVATE", detail="generator_input_capacity: PRIVATE")
    event = read_events(recorder.path)[0]
    assert event["reason"] == "[redacted]"
    assert event["detail"] == "generator_input_capacity"
    assert event["run_identity"] == "metadata-run"
    assert "PRIVATE" not in recorder.path.read_text()


def test_sink_failure_raises_existing_audit_error_and_scope_restores():
    def failing_sink(event):
        raise OSError("disk full")

    with pytest.raises(AuditWriteError, match="module observation failed"):
        with observation_scope(failing_sink):
            observe("execution", "task_started")
    observe("execution", "disabled_again")


@pytest.mark.parametrize("destination", ["events.jsonl", "scoring.jsonl"])
def test_each_destination_failure_is_fail_closed(tmp_path, destination):
    (tmp_path / "modules" / destination).mkdir(parents=True)
    with observation_scope(ModuleEventRecorder(tmp_path)), pytest.raises(AuditWriteError):
        observe("scoring", "set_score", score=.2)


def test_nonfinite_observation_is_rejected(tmp_path):
    with observation_scope(ModuleEventRecorder(tmp_path)), pytest.raises(AuditWriteError):
        observe("scoring", "set_score", score=float("nan"))


def test_off_on_algorithmic_artifacts_and_actual_model_invocations_are_identical(tmp_path):
    disabled = run_fixture(None)
    recorder = ModuleEventRecorder(tmp_path)
    enabled = run_fixture(recorder)
    assert enabled == disabled
    events = read_events(recorder.path)
    assert {event["module"] for event in events} == {"proposal", "scoring", "activation", "state", "selection", "stop"}
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert len({event["event_id"] for event in events}) == len(events)
    for module in {event["module"] for event in events}:
        assert read_events(tmp_path / "modules" / f"{module}.jsonl") == [event for event in events if event["module"] == module]
    assert "PRIVATE_" not in recorder.path.read_text()
    measurements = [event for event in events if event["event"] == "activation_measured"]
    assert measurements
    for event in measurements:
        assert event["activation"] == pytest.approx(event["PGe"] - event["PG"] - event["Pe"] + event["P"])
        assert event["accepted"] == (event["signal"] > 0)
        assert set(event["sets"]) == {"P", "Pe", "PG", "PGe"}
    assert any(event["event"] == "state_popped" and not event["completed"] for event in events)
    assert any(event["event"] == "state_completed" and event["completed"] for event in events)
    rounds = [event for event in events if event["event"] == "selection_round"]
    assert rounds and all("comparisons" in event for event in rounds)
    assert all(comparison["event"] == "selection_step" for event in rounds for comparison in event["comparisons"])


def test_disabled_algorithm_hooks_never_call_public_dict(monkeypatch):
    def poison(self):
        raise AssertionError("unnecessary observer serialization")

    for record_type in (ProposalBatch, ActivationRecord, SearchStateRecord, SelectionRound):
        monkeypatch.setattr(record_type, "public_dict", poison)
    scorer, retriever, _, _ = fixture()
    with observation_scope(None):
        archive = DependencySearcher(scorer, retriever, max_scored_sets=32).run()
        result = DynamicBundleSelector(scorer, max_selection_sets=32).select(archive)
    assert result.selected_ids


def test_custom_recorder_cannot_mutate_legacy_artifacts():
    def mutating_sink(event):
        event["score"] = -100
        event.get("ids", []).append("injected")
        event.get("candidate_ids", []).clear()
        event.get("comparisons", []).clear()

    assert run_fixture(mutating_sink) == run_fixture(None)


def test_memory_and_persistent_cache_observations_preserve_budgets_and_calls(tmp_path):
    events = []
    with observation_scope(events.append):
        cold, _, client, _ = fixture(cache_dir=tmp_path / "cache")
        assert cold.score_set(("a",)) == .15
        assert cold.score_set(("a",)) == .15
        warm, _, warm_client, _ = fixture(cache_dir=tmp_path / "cache")
        assert warm.score_set(("a",)) == .15
    lookups = [event for event in events if event["event"] == "cache_lookup"]
    assert [event["source"] for event in lookups] == ["cache_miss", "memory_cache", "persistent_cache"]
    assert cold.scored_sets == warm.scored_sets == 1
    assert len(client.calls) == 1 and warm_client.calls == []
    assert cold.memory_cache_hits == warm.persistent_cache_hits == 1


def test_completed_score_batches_survive_later_batch_failure(tmp_path):
    recorder = ModuleEventRecorder(tmp_path)
    scorer, _, client, _ = fixture(batch_size=1, fail_after=1)
    with observation_scope(recorder), pytest.raises(RuntimeError, match="server failed"):
        scorer.score_sets([("a",), ("b",)], reason="selection")
    events = read_events(recorder.path)
    available = [event for event in events if event["event"] == "set_score_available"]
    assert [(event["ids"], event["score"]) for event in available] == [(["a"], .15)]
    assert len(client.calls) == 2
    assert scorer.events == []  # legacy whole-call completion artifact is unchanged
    assert "private response" not in recorder.path.read_text()


def test_incomplete_selection_round_is_visible_without_committing_winner():
    events = []
    scorer, _, client, _ = fixture()
    with observation_scope(events.append):
        result = DynamicBundleSelector(scorer, max_selection_sets=1).select([("a",), ("b",)])
    assert result.stop_reason == "score_budget_exhausted"
    assert result.selected_ids == () and client.calls == []
    logged = [event for event in events if event["event"] == "selection_round"]
    assert len(logged) == 1 and not logged[0]["complete"]
    assert logged[0]["accepted_bundle_ids"] is None
    assert all(not item["accepted"] and item["marginal"] is None for item in logged[0]["comparisons"])
    assert events[-1]["event"] == "selection_stop"


def test_observer_audit_error_is_not_converted_to_algorithm_budget_stop():
    scorer, _, client, _ = fixture()

    def sink(event):
        if event["module"] == "scoring":
            raise AuditWriteError("audit quota exhausted")

    with observation_scope(sink), pytest.raises(AuditWriteError, match="audit quota"):
        DynamicBundleSelector(scorer, max_selection_sets=32).select([("a",)])
    assert client.calls == []


def test_all_proposal_terminal_paths_are_observed_without_payloads():
    events = []
    with observation_scope(events.append):
        _, retriever, _, embedder = fixture(max_ann_calls=1)
        retriever.retrieve_dense()
        retriever.propose("a")
        retriever._run_probe(stage="empty", probe_text="PRIVATE_PROBE", width=0)
    completed = [event for event in events if event["event"] == "proposal_completed"]
    assert len(completed) == 4  # auto initial bridge, then conditional proposal, both capped
    assert completed[0]["candidate_ids"] == ["a", "b"]
    assert completed[0]["ann_call_index"] == 1
    assert all(event["stop_reason"] == "ann_budget_exhausted" for event in completed[1:-1])
    assert completed[-1]["stop_reason"] == "no_candidates"
    assert len(embedder.calls) == 2  # one bank embedding, one actual query
    assert "PRIVATE_" not in json.dumps(events)


def test_execute_item_does_not_swallow_or_retry_a_transient_observer_write_failure(tmp_path):
    from bridgetree.diagnostic_runner import _execute_item
    from bridgetree.request_audit import TransportBudget

    seen, calls = [], []

    def transient_sink(event):
        seen.append(event)
        if event["module"] == "scoring" and len(calls) == 1:
            raise OSError("transient disk failure")

    def action():
        calls.append("attempt")
        observe("scoring", "cache_lookup", ids=["a"], cache_hit=False)
        return {"score": .5}

    manifest = {"manifest_id": "observer-run", "task_max_attempts": 3}
    with observation_scope(transient_sink), pytest.raises(AuditWriteError):
        _execute_item(tmp_path, manifest, "score", "item1", TransportBudget(3), action,
                      {"question_id": "q1"})
    assert calls == ["attempt"]
    assert [event["event"] for event in read_events(tmp_path / "attempts.jsonl")] == ["task_attempt_started"]
    assert not (tmp_path / "score/item1.json").exists()
    assert not any(event["event"] == "task_attempt_failed" for event in seen)
