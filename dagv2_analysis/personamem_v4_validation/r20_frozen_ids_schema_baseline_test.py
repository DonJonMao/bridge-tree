"""Independent offline contract review of current-batch frozen ID schemas.

Real Reader validation, repair construction, schema serialization and state
retention are exercised with synthetic observations and local replies only.
"""
from copy import deepcopy
import json
import socket

import pytest
from jsonschema import Draft202012Validator

from test_personamem_joint_protocol import fixture, observation


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Frozen-ID review must not contact services")
    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    monkeypatch.setattr("urllib.request.build_opener", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr("dagbt.reasoning.estimate_evidence_tokens", lambda value: 0)


def response_schema(payload):
    return json.loads(payload["messages"][0]["content"].rsplit(
        "Return one complete JSON object matching this schema:\n", 1)[1])


@pytest.mark.parametrize("stance", ["unknown", "partial"])
def test_current_batch_unsettled_row_is_schema_frozen_without_reference_permission(stance):
    reader, engine, state, calls = fixture(max_repairs_per_request=1)
    calls.count_reasoning_tokens = lambda *args: {"count": 100, "token_count_is_estimate": False}
    stable = engine.mapper.sources["s1"]["source_id"]
    reader.evidence_obligations["original-issue"] = {
        "id": "original-issue", "variable": "history", "entity_scope": "user",
        "time_scope": "history", "source_ids": [stable],
        "descriptions": ["A specific historical relation is not yet established."],
        "origins": ["older-query"],
    }
    draft = observation("frozen-unsettled", stance=stance)
    draft["value"] = None
    replay = {"slots": [{"variable": "history", "observations": [draft],
                          "unresolved": [], "resolved_obligation_ids": ["original-issue"]}]}
    seen = []
    def respond(index, data):
        if index == 2:
            schema = response_schema(calls.requests[-1]["payload"])
            # This is the same saved shape the runtime already forbids. It
            # must be rejected even though unsettled rows cannot be referenced.
            assert not Draft202012Validator(schema).is_valid(replay), (
                "repair schema still permits ordinary restatement of a current-batch " + stance)
            assert data["repair_scope"]["frozen_observation_ids"] == {"history": [draft["id"]]}
            assert all("frozen_observation_reviews" not in entry for entry in data["repair_scope"]["failed"])
            forbidden_reference = {"slots": [{"variable": "history", "observations": [],
                "unresolved": ["Still unknown"], "reviewed_observation_ids": [draft["id"]]}]}
            assert not Draft202012Validator(schema).is_valid(forbidden_reference)
            seen.append(deepcopy(data))
        # Deliberately ignore the schema: the unchanged runtime must still
        # reject the repair and retain the original responsibility.
        return deepcopy(replay)
    calls.respond = respond
    reader.read(engine.steps[0], "Read the scoped historical relation", ["history"],
                ["piano"], "current-batch-query")
    assert len(seen) == 1 and len(calls.requests) == 2
    assert engine.ledger.used["llm"] == 2 and engine.ledger.used["json_repairs"] == 1
    assert "original-issue" in reader.evidence_obligations
    assert "history" in reader.pending_variables() and not state.valid()[0]
    failures = [entry for record in reader.failed_batch_reviews.values() for entry in record["failed"]]
    assert any("Already validated observations remain frozen" in entry["feedback"] for entry in failures)
    assert any(record["validated_observations"][0]["stance"] == stance
               for record in reader.failed_batch_reviews.values())
