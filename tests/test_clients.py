import http.client

import numpy as np
import pytest

from bridgetree.clients import (
    ContextPlanError,
    GenerationCache,
    GeneratorClient,
    RemoteEmbeddingClient,
    RerankerClient,
    _post_json,
)
from bridgetree.config import EmbeddingConfig, EndpointConfig, GeneratorConfig
from bridgetree.types import Memory


def test_generator_makes_exactly_one_http_call_and_serializes_chronologically(monkeypatch):
    calls = []

    def fake_post(url, payload, timeout, headers=None):
        calls.append((url, payload, headers))
        return {"choices": [{"message": {"content": "(a)"}}]}

    monkeypatch.setattr("bridgetree.clients._post_json", fake_post)
    client = GeneratorClient(GeneratorConfig(endpoint="http://chat", model="m", api_key="key"))
    memories = [Memory("m1", "first", 1.0, "s1"), Memory("m2", "second", 2.0, "s2")]
    assert client.answer("q", memories, "(a) yes") == "(a)"
    assert len(calls) == 1
    content = calls[0][1]["messages"][1]["content"]
    assert content.index("first") < content.index("second")
    assert calls[0][2]["Authorization"] == "Bearer key"


def test_generation_budget_failure_never_silently_drops_memories(monkeypatch, tmp_path):
    calls = []

    def fake_post(url, payload, timeout, headers=None):
        calls.append((url, payload, timeout, headers))
        return {"choices": [{"message": {"content": "(a)"}}]}

    monkeypatch.setattr("bridgetree.clients._post_json", fake_post)
    client = GeneratorClient(
        GeneratorConfig(endpoint="http://chat", model="m", api_key="key", context_token_budget=1)
    )
    memories = [Memory("m1", "first memory", 1.0, "s1"), Memory("m2", "second memory", 2.0, "s2")]

    with pytest.raises(ContextPlanError, match="exceeding budget"):
        client.answer("q", memories)
    cache = GenerationCache(tmp_path)
    with pytest.raises(ContextPlanError, match="exceeding budget"):
        cache.answer(client, "q", memories)
    assert calls == []


def test_embedding_and_reranker_protocols(monkeypatch):
    calls = []

    def fake_post(url, payload, timeout, headers=None):
        calls.append((url, payload))
        if "embedding" in url:
            if len(payload["input"]) == 1:
                return {"data": [{"index": 0, "embedding": [2.0, 0.0]}]}
            return {
                "data": [
                    {"index": 1, "embedding": [0.0, 3.0]},
                    {"index": 0, "embedding": [2.0, 0.0]},
                ]
            }
        return {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]}

    monkeypatch.setattr("bridgetree.clients._post_json", fake_post)
    embedder = RemoteEmbeddingClient(EmbeddingConfig(endpoint="http://embedding", model="embed", batch_size=2))
    vectors = embedder.encode(["a", "b"])
    np.testing.assert_allclose(vectors, np.eye(2))
    embedder.encode_query("question")
    reranked = RerankerClient(EndpointConfig(endpoint="http://rerank")).rerank("q", ["a", "b"], 2)
    assert [item.index for item in reranked] == [1, 0]
    assert calls[0][1] == {"model": "embed", "input": ["a", "b"]}
    assert calls[1][1]["input"][0].endswith("Query: question")


def test_http_client_retries_a_remote_disconnect(monkeypatch):
    class FailingOpener:
        calls = 0

        def open(self, request, timeout):
            self.calls += 1
            raise http.client.RemoteDisconnected("closed")

    opener = FailingOpener()
    monkeypatch.setattr("bridgetree.clients.urllib.request.build_opener", lambda *args: opener)
    monkeypatch.setattr("bridgetree.clients.time.sleep", lambda _seconds: None)
    with pytest.raises(RuntimeError, match="after 3 attempts"):
        _post_json("http://model", {"input": ["x"]}, 1)
    assert opener.calls == 3


def test_explicit_embedding_instruction_is_not_double_prefixed_and_batches_queries(monkeypatch):
    payloads = []

    def fake_post(_url, payload, _timeout, headers=None):
        payloads.append(payload)
        return {
            "data": [
                {"index": index, "embedding": [1.0, float(index)]}
                for index, _text in enumerate(payload["input"])
            ]
        }

    monkeypatch.setattr("bridgetree.clients._post_json", fake_post)
    client = RemoteEmbeddingClient(
        EmbeddingConfig(endpoint="http://embedding", query_instruction="DEFAULT: ", batch_size=8)
    )

    client.encode_query("question", instruction="SPECIAL: ")
    client.encode_queries(["bridge one", "bridge two"], instruction="BRIDGE: ")

    assert payloads[0]["input"] == ["SPECIAL: question"]
    assert "DEFAULT" not in payloads[0]["input"][0]
    assert payloads[1]["input"] == ["BRIDGE: bridge one", "BRIDGE: bridge two"]
    assert len(payloads) == 2
