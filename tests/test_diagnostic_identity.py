from dataclasses import replace

import pytest

from bridgetree.clients import GenerationCache, GeneratorClient, RerankItem, RerankerClient, build_context_plan
from bridgetree.config import EmbeddingConfig, GeneratorConfig, RerankerConfig
from bridgetree.dependency_scoring import SetReranker
from bridgetree.diagnostic_identity import DeploymentIdentity, deployment_fingerprint, deployment_public, execution_hash, request_hash
from bridgetree.request_audit import request_audit_scope
from bridgetree.types import Memory


def identity(revision="weights-a"):
    return {"model_id": "fixture", "checkpoint_revision": revision,
            "quantization": "int8", "identity_source": "operator_declared"}


def test_declared_identity_cache_stable_but_revision_and_quantization_isolate():
    config = RerankerConfig("http://private", deployment_identity=identity())
    assert isinstance(config.deployment_identity, DeploymentIdentity)
    with request_audit_scope({"run_identity": "run-a"}):
        a = deployment_fingerprint(config)
    with request_audit_scope({"run_identity": "run-b"}):
        assert deployment_fingerprint(config) == a
    assert deployment_fingerprint(replace(config, deployment_identity=identity("weights-b"))) != a
    assert deployment_fingerprint(replace(config, deployment_identity={**identity(), "quantization": "bf16"})) != a
    # Verification provenance is not a computation/cache identity.
    verified = replace(config, deployment_identity={**identity(), "identity_source": "verified", "verification_evidence_id": "ticket-1"})
    assert deployment_fingerprint(verified) == a
    assert deployment_public(verified)["identity_source"] == "verified"


def test_unknown_identity_uses_run_local_namespace():
    config = RerankerConfig("http://private")
    with request_audit_scope({"run_identity": "run-a"}):
        a = deployment_fingerprint(config)
        assert a == deployment_fingerprint(config)
    with request_audit_scope({"run_identity": "run-b"}):
        assert a != deployment_fingerprint(config)
    assert not deployment_public(config)["identity_declared"]


def test_unknown_client_identity_resolves_in_run_not_construction_scope():
    client = RerankerClient(RerankerConfig("http://private"))
    outside = client.model_fingerprint
    with request_audit_scope({"run_identity": "one", "task_id": "a"}):
        one = client.model_fingerprint
    with request_audit_scope({"run_identity": "one", "task_id": "b"}):
        assert client.model_fingerprint == one
    with request_audit_scope({"run_identity": "two"}):
        assert client.model_fingerprint != one
    assert client.model_fingerprint == outside


def test_concrete_config_positional_arguments_remain_legacy_compatible():
    embedding = EmbeddingConfig("http://private", "m", 2, "remote", 4)
    assert embedding.backend == "remote" and embedding.batch_size == 4
    reranker = RerankerConfig("http://private", "m", 2, "cache", "unit_interval", "pointwise", "instruction")
    assert reranker.cache_dir == "cache" and reranker.task_instruction == "instruction"
    generator = GeneratorConfig("http://private", "m", 2, "key", "TEST_API_KEY", 0, 30, 300)
    assert generator.api_key == "key" and generator.max_tokens == 30


def test_deployment_public_identity_rejects_secret_or_endpoint_values():
    with pytest.raises(ValueError):
        RerankerConfig("http://private", deployment_identity={"model_id": "http://private"})
    with pytest.raises(ValueError):
        GeneratorConfig("http://private", deployment_identity={"deployment_revision": "Bearer private-key"})


def test_generation_payload_hash_ignores_selector_order_but_not_thinking():
    config = GeneratorConfig("http://private", model="fixture", deployment_identity=identity(),
                             provider_request_params={"thinking": {"type": "disabled"}})
    memories = [Memory("a", "first", 1, "s"), Memory("b", "second", 2, "s")]
    first = build_context_plan("q", memories, selected_ids=("a", "b"), generator_config=config)
    reverse = build_context_plan("q", memories, selected_ids=("b", "a"), generator_config=config)
    assert first.context_hash != reverse.context_hash
    assert request_hash(first.request_dict()) == request_hash(reverse.request_dict())
    assert GenerationCache._cache_key_for_plan(first, GeneratorClient(config)) == GenerationCache._cache_key_for_plan(reverse, GeneratorClient(config))
    thinking = replace(config, provider_request_params={"thinking": {"type": "enabled"}})
    changed = build_context_plan("q", memories, generator_config=thinking)
    assert request_hash(first.request_dict()) != request_hash(changed.request_dict())
    assert GenerationCache._cache_key_for_plan(first, GeneratorClient(config)) != GenerationCache._cache_key_for_plan(first, GeneratorClient(replace(config, deployment_identity=identity("new"))))
    assert execution_hash(first.request_dict(), "one") != execution_hash(first.request_dict(), "two")


@pytest.mark.parametrize("params", [{"authorization": "secret"}, {"extra": {"api_key": "secret"}}, {"model": "override"}, {"temperature": 1}])
def test_provider_params_cannot_hide_credentials_or_override_canonical_fields(params):
    with pytest.raises(ValueError):
        GeneratorConfig("http://private", provider_request_params=params)


@pytest.mark.parametrize("sensitive", [
    "x-api-key", "api-key", "access_token", "client_secret", "refreshToken",
    "Proxy-Authorization", "extra_headers", "headers", "httpHeaders",
])
@pytest.mark.parametrize("entrypoint", ["config", "explicit", "explicit_with_config", "mapping_config"])
def test_nested_request_credentials_rejected_before_plan_serialization(sensitive, entrypoint):
    params = {"extra": [{"nested": {sensitive: "private-credential"}}]}
    with pytest.raises(ValueError, match="credentials or transport metadata"):
        if entrypoint == "config":
            GeneratorConfig("http://private", provider_request_params=params)
        elif entrypoint == "mapping_config":
            build_context_plan("q", [], generator_config={"provider_request_params": params})
        else:
            config = GeneratorConfig("http://private") if entrypoint == "explicit_with_config" else None
            build_context_plan("q", [], request_params=params, generator_config=config)


def test_request_params_preserve_tools_formats_and_same_canonical_values():
    params = {
        "tools": [{"type": "function", "function": {
            "name": "lookup", "parameters": {"type": "object", "properties": {
                "location": {"type": "string"}, "token_budget": {"type": "integer"},
            }},
        }}],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled", "budget_tokens": 32},
    }
    config = GeneratorConfig("http://private", model="fixture", provider_request_params=params)
    plan = build_context_plan("q", [], generator_config=config)
    explicit = build_context_plan("q", [], generator_config=config, request_params={
        **params, "model": "fixture", "temperature": config.temperature,
        "max_tokens": config.max_tokens, "messages": plan.request_dict()["messages"],
    })
    assert explicit.request_dict() == plan.request_dict()
    for key, value in params.items():
        assert plan.request_dict()[key] == value
    default = build_context_plan("q", [], generator_config=GeneratorConfig("http://private"))
    assert set(default.request_dict()) == {"endpoint", "model", "messages", "temperature", "max_tokens"}


def test_scorer_persistent_cache_is_deployment_aware_without_changing_score_budget(tmp_path):
    class Fake:
        score_space = "unit_interval"
        score_contract = "pointwise"
        def __init__(self, revision):
            self.config = RerankerConfig("http://private", deployment_identity=identity(revision))
            self.calls = 0
        def rerank_all(self, query, documents):
            self.calls += 1
            return [RerankItem(i, .7) for i in range(len(documents))]
    records = {"a": Memory("a", "real memory", 1, "s")}
    one, same, different = Fake("v1"), Fake("v1"), Fake("v2")
    scorers = [SetReranker("q", records, client, cache_dir=tmp_path, set_budget=1) for client in (one, same, different)]
    assert [s.score_set(["a"]) for s in scorers] == [.7, .7, .7]
    assert [c.calls for c in (one, same, different)] == [1, 0, 1]
    assert [s.scored_sets for s in scorers] == [1, 1, 1]
