import copy
import json
from dataclasses import replace

import pytest

from bridgetree.chain_judge import HTTPJointJudge, PublicQuery, chat_label_pair, preflight_joint_backend
from bridgetree.config import GeneratorConfig


def response(label="A"):
    return {"choices": [{"message": {"content": label}, "logprobs": {"content": [
        {"token": label, "top_logprobs": [{"token": "A", "logprob": -.2},
                                         {"token": "B", "logprob": -1.2}]}]}}],
        "usage": {"prompt_tokens": 30, "completion_tokens": 1}}


def setup_judge(tmp_path, **kwargs):
    requests = []

    def transport(url, payload, timeout, headers=None):
        requests.append(copy.deepcopy(payload))
        if "response_format" in payload:
            return {"choices": [{"message": {"content": json.dumps({
                "text": "The user needs a quiet place.", "source_ids": ["a"]})}}]}
        return response()

    records = {
        "a": {"text": "User: I need quiet.", "timestamp": 1,
              "metadata": {"roles": ["user"], "gold": "secret", "time": {"observed_start": 1}}},
        "b": {"text": "Assistant: A library may suit.", "timestamp": 2,
              "metadata": {"roles": ["assistant"]}},
        "future": {"text": "FUTURE_SENTINEL", "timestamp": 999, "metadata": {}},
    }
    config = GeneratorConfig(endpoint="http://fixture.invalid/chat", model="frozen", api_key="private-test")
    judge = HTTPJointJudge(config, records, transport=transport, backend="fixture", cache_dir=tmp_path, **kwargs)
    query = PublicQuery("revision", "persona", "question", "Where should I work?", "A: library B: club",
                        end_index=3, visible_memories=("a", "b"))
    return judge, query, requests, records


def test_production_adapter_full_original_text_and_fixed_claim(tmp_path):
    judge, query, requests, records = setup_judge(tmp_path)
    assert requests == []
    score = judge.score(query, ("b", "a"))
    assert score.raw_difference == pytest.approx(1)
    assert judge.score(query, ("a", "b")).input_hash == score.input_hash
    assert len(requests) == 1
    public = json.loads(requests[0]["messages"][1]["content"])
    assert [r["text"] for r in public["records"]] == [records[x]["text"] for x in ("a", "b")]
    assert [r["roles"] for r in public["records"]] == [["user"], ["assistant"]]
    assert "secret" not in json.dumps(requests)
    assert "FUTURE_SENTINEL" not in json.dumps(requests)
    assert requests[0]["logprobs"] is True and requests[0]["max_tokens"] == 1
    claim = judge.claim(query, ("a", "b"))
    assert judge.verify(query, claim, ("a", "b")).supported
    assert judge.verify(query, claim, ("a",)).supported
    assert [json.loads(r["messages"][1]["content"])["fixed_claim"] for r in requests[-2:]] == [claim.text] * 2
    assert judge.cost["score"]["requests"] == 1
    assert judge.cost["score"]["cache_hits"] == 1


def test_adapter_disk_cache_and_original_preflight_logprobs(tmp_path):
    judge, query, requests, _ = setup_judge(tmp_path)
    first = judge.score(query, ("a",))
    other, _, other_requests, _ = setup_judge(tmp_path)
    assert other.score(query, ("a",)).input_hash == first.input_hash
    assert other_requests == []
    report = preflight_joint_backend(judge)
    assert report["sufficient_logprob"] == -.2
    assert report["insufficient_logprob"] == -1.2


def test_visibility_and_changed_original_text(tmp_path):
    judge, query, requests, records = setup_judge(tmp_path)
    with pytest.raises(ValueError, match="non-visible"):
        judge.score(query, ("future",))
    assert not requests
    old = judge.score(query, ("a",)).input_hash
    records["a"]["text"] += " I changed my preference."
    assert judge.score(query, ("a",)).input_hash != old
    assert judge.score(replace(query, end_index=2), ("a",)).input_hash != old


@pytest.mark.parametrize("variant", ["missing", "cross_position", "number", "preamble", "nan"])
def test_label_contract_rejects_invalid_response(variant):
    data = response()
    positions = data["choices"][0]["logprobs"]["content"]
    if variant in {"missing", "cross_position"}:
        removed = positions[0]["top_logprobs"].pop()
        if variant == "cross_position":
            positions.append({"token": "B", "top_logprobs": [removed]})
    elif variant == "number":
        data = {"choices": [{"message": {"content": "0.9"}}]}
    elif variant == "preamble":
        positions[0]["token"] = "Thinking"
    else:
        positions[0]["top_logprobs"][0]["logprob"] = float("nan")
    with pytest.raises(ValueError):
        chat_label_pair(data)


def test_failed_transport_cannot_fallback_or_cache(tmp_path):
    judge, query, _, _ = setup_judge(tmp_path)

    def broken(*args, **kwargs):
        raise OSError("fixture transport unavailable")

    judge.transport = broken
    with pytest.raises(OSError):
        judge.score(query, ("a",))
    assert not list(tmp_path.glob("*.json"))


def test_repeat_and_backend_are_cache_identity(tmp_path):
    judge, query, _, _ = setup_judge(tmp_path)
    first = judge.score(query, ("a",)).input_hash
    repeated, _, requests, _ = setup_judge(tmp_path, repeat_id="repeat2")
    assert repeated.score(query, ("a",)).input_hash != first
    assert len(requests) == 1
