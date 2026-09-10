import http.client
import io
import urllib.error

import numpy as np
import pytest

from bridgetree.clients import (
    ContextPlanError,
    GenerationCache,
    GeneratorClient,
    HTTPTransportError,
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

    def fake_post(url, payload, timeout, headers=None, *, on_attempt=None):
        if on_attempt is not None:
            on_attempt(1)
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
    sleeps = []
    monkeypatch.setattr("bridgetree.clients.urllib.request.build_opener", lambda *args: opener)
    monkeypatch.setattr("bridgetree.clients.time.sleep", sleeps.append)
    with pytest.raises(HTTPTransportError, match="after 4 transport attempts") as caught:
        _post_json("http://model", {"input": ["x"]}, 1)
    assert caught.value.attempts == 4
    assert caught.value.status_code is None
    assert caught.value.retryable
    assert opener.calls == 4
    assert sleeps == [0.5, 1.0, 2.0]


@pytest.mark.parametrize("failure_kind", ["incomplete_read", "invalid_utf8"])
def test_http_client_retries_a_truncated_or_malformed_response_body(
    monkeypatch, failure_kind
):
    class Response:
        def __init__(self, payload=None):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            if failure_kind == "incomplete_read" and self.payload is None:
                raise http.client.IncompleteRead(b'{"ok":', 1)
            if failure_kind == "invalid_utf8" and self.payload is None:
                return b"\xff"
            return self.payload

    class RecoveringOpener:
        calls = 0

        def open(self, request, timeout):
            self.calls += 1
            return Response(None if self.calls == 1 else b'{"ok": true}')

    opener = RecoveringOpener()
    sleeps = []
    monkeypatch.setattr(
        "bridgetree.clients.urllib.request.build_opener", lambda *args: opener
    )
    monkeypatch.setattr("bridgetree.clients.time.sleep", sleeps.append)

    assert _post_json("http://model", {"input": ["x"]}, 1) == {"ok": True}
    assert opener.calls == 2
    assert sleeps == [0.5]


def test_http_client_retries_500_with_exponential_backoff_then_recovers(monkeypatch):
    class JsonResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"ok": true}'

    class RecoveringOpener:
        calls = 0

        def open(self, request, timeout):
            self.calls += 1
            if self.calls < 3:
                raise urllib.error.HTTPError(
                    request.full_url,
                    500,
                    "Internal Server Error",
                    None,
                    None,
                )
            return JsonResponse()

    opener = RecoveringOpener()
    sleeps = []
    attempts = []
    monkeypatch.setattr("bridgetree.clients.urllib.request.build_opener", lambda *args: opener)
    monkeypatch.setattr("bridgetree.clients.time.sleep", sleeps.append)

    assert _post_json(
        "http://model",
        {"input": ["x"]},
        1,
        on_attempt=attempts.append,
    ) == {"ok": True}
    assert attempts == [1, 2, 3]
    assert sleeps == [0.5, 1.0]


def test_http_client_does_not_retry_401_or_expose_body_or_credentials(monkeypatch):
    class UnauthorizedOpener:
        calls = 0

        def open(self, request, timeout):
            self.calls += 1
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                None,
                io.BytesIO(b"response-secret"),
            )

    opener = UnauthorizedOpener()
    sleeps = []
    monkeypatch.setattr("bridgetree.clients.urllib.request.build_opener", lambda *args: opener)
    monkeypatch.setattr("bridgetree.clients.time.sleep", sleeps.append)

    with pytest.raises(HTTPTransportError) as caught:
        _post_json(
            "https://user:url-secret@example.invalid/model?api_key=query-secret",
            {"api_key": "payload-secret"},
            1,
        )
    message = str(caught.value)
    assert caught.value.attempts == 1
    assert caught.value.status_code == 401
    assert not caught.value.retryable
    assert opener.calls == 1
    assert sleeps == []
    assert "response-secret" not in message
    assert "url-secret" not in message
    assert "query-secret" not in message
    assert "payload-secret" not in message


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


def test_reranker_bisects_exhausted_5xx_batch_and_restores_global_indices(monkeypatch):
    scores = {"a": 0.1, "b": 0.5, "c": 0.7, "d": 0.8, "e": 0.9}
    batch_sizes = []

    def fake_post(
        _url,
        payload,
        _timeout,
        headers=None,
        *,
        on_attempt=None,
        max_attempts=4,
    ):
        documents = payload["documents"]
        batch_sizes.append(len(documents))
        if len(documents) > 2:
            if on_attempt is not None:
                for attempt in range(1, max_attempts + 1):
                    on_attempt(attempt)
            raise HTTPTransportError(
                attempts=max_attempts,
                status_code=500,
                retryable=True,
                cause_type="HTTPError",
            )
        if on_attempt is not None:
            on_attempt(1)
        ranked = sorted(
            enumerate(documents),
            key=lambda pair: (-scores[pair[1]], pair[0]),
        )[: payload["top_n"]]
        # A backend may return score order rather than document order.
        return {
            "results": [
                {"index": index, "relevance_score": scores[document]}
                for index, document in ranked
            ]
        }

    monkeypatch.setattr("bridgetree.clients._post_json", fake_post)
    client = RerankerClient(EndpointConfig(endpoint="http://rerank"))

    result = client.rerank("question", ["a", "b", "c", "d", "e"], 3)

    assert [(item.index, item.score) for item in result] == [
        (4, 0.9),
        (3, 0.8),
        (2, 0.7),
    ]
    assert batch_sizes == [5, 2, 3, 1, 2]
    assert client.transport_stats == {
        "logical_calls": 1,
        "logical_documents": 5,
        "batch_requests": 5,
        "batch_documents": 13,
        "transport_attempts": 8,
        "transport_document_attempts": 28,
        "failed_batch_requests": 2,
        "split_events": 2,
        "split_recovered_calls": 1,
        "failed_calls": 0,
    }


def test_reranker_singleton_500_still_fails_without_retry_storm(monkeypatch):
    batch_sizes = []

    def fail_post(_url, payload, _timeout, headers=None, *, on_attempt=None):
        batch_sizes.append(len(payload["documents"]))
        if on_attempt is not None:
            for attempt in range(1, 5):
                on_attempt(attempt)
        raise HTTPTransportError(
            attempts=4,
            status_code=500,
            retryable=True,
            cause_type="HTTPError",
        )

    monkeypatch.setattr("bridgetree.clients._post_json", fail_post)
    client = RerankerClient(EndpointConfig(endpoint="http://rerank"))

    with pytest.raises(HTTPTransportError) as caught:
        client.rerank_all("question", ["only document"])

    assert caught.value.status_code == 500
    assert batch_sizes == [1]
    assert client.transport_stats == {
        "logical_calls": 1,
        "logical_documents": 1,
        "batch_requests": 1,
        "batch_documents": 1,
        "transport_attempts": 4,
        "transport_document_attempts": 4,
        "failed_batch_requests": 1,
        "split_events": 0,
        "split_recovered_calls": 0,
        "failed_calls": 1,
    }


@pytest.mark.parametrize("status_code", [413, 422])
def test_reranker_splits_batch_rejected_for_size_or_shape(monkeypatch, status_code):
    batch_sizes = []

    def fake_post(
        _url,
        payload,
        _timeout,
        headers=None,
        *,
        on_attempt=None,
        max_attempts=4,
    ):
        documents = payload["documents"]
        batch_sizes.append(len(documents))
        if on_attempt is not None:
            on_attempt(1)
        if len(documents) > 1:
            raise HTTPTransportError(
                attempts=1,
                status_code=status_code,
                retryable=False,
                cause_type="HTTPError",
            )
        return {"results": [{"index": 0, "relevance_score": 0.5}]}

    monkeypatch.setattr("bridgetree.clients._post_json", fake_post)
    client = RerankerClient(EndpointConfig(endpoint="http://rerank"))

    result = client.rerank_all("question", ["a", "b"])

    assert [item.index for item in result] == [0, 1]
    assert batch_sizes == [2, 1, 1]
    assert client.transport_stats["split_events"] == 1
    assert client.transport_stats["split_recovered_calls"] == 1


@pytest.mark.parametrize("status_code", [429, 502, 503, 504])
def test_reranker_does_not_split_endpoint_wide_failures(monkeypatch, status_code):
    batch_sizes = []

    def fail_post(_url, payload, _timeout, headers=None, *, on_attempt=None):
        batch_sizes.append(len(payload["documents"]))
        if on_attempt is not None:
            for attempt in range(1, 5):
                on_attempt(attempt)
        raise HTTPTransportError(
            attempts=4,
            status_code=status_code,
            retryable=True,
            cause_type="HTTPError",
        )

    monkeypatch.setattr("bridgetree.clients._post_json", fail_post)
    client = RerankerClient(EndpointConfig(endpoint="http://rerank"))

    with pytest.raises(HTTPTransportError) as caught:
        client.rerank_all("question", ["a", "b", "c", "d"])

    assert caught.value.status_code == status_code
    assert batch_sizes == [4]
    assert client.transport_stats["split_events"] == 0


def test_rerank_all_requires_complete_document_coverage(monkeypatch):
    def fake_post(_url, _payload, _timeout, headers=None, *, on_attempt=None):
        return {"results": [{"index": 0, "relevance_score": 0.8}]}

    monkeypatch.setattr("bridgetree.clients._post_json", fake_post)
    client = RerankerClient(EndpointConfig(endpoint="http://rerank"))

    with pytest.raises(ValueError, match="cover every document"):
        client.rerank_all("question", ["a", "b"])


def test_reranker_rejects_explicit_backend_truncation(monkeypatch):
    monkeypatch.setattr(
        "bridgetree.clients._post_json",
        lambda *_args, **_kwargs: {
            "results": [{"index": 0, "relevance_score": 0.8}],
            "meta": {"input_truncated": True},
        },
    )
    client = RerankerClient(EndpointConfig(endpoint="http://rerank"))
    with pytest.raises(ValueError, match="truncation"):
        client.rerank_all("question", ["full document"])


def test_reranker_rejects_per_document_truncation_flags(monkeypatch):
    monkeypatch.setattr(
        "bridgetree.clients._post_json",
        lambda *_args, **_kwargs: {
            "results": [{"index": 0, "relevance_score": 0.8}],
            "usage": {"documents_truncated": [False, True]},
        },
    )
    client = RerankerClient(EndpointConfig(endpoint="http://rerank"))
    with pytest.raises(ValueError, match="truncation"):
        client.rerank_all("question", ["full document"])


def test_reranker_rejects_explicit_length_termination(monkeypatch):
    monkeypatch.setattr(
        "bridgetree.clients._post_json",
        lambda *_args, **_kwargs: {
            "results": [{"index": 0, "relevance_score": 0.8}],
            "finish_reason": "length",
        },
    )
    client = RerankerClient(EndpointConfig(endpoint="http://rerank"))
    with pytest.raises(ValueError, match="truncation"):
        client.rerank_all("question", ["full document"])
