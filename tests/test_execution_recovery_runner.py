import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridgetree.config import RerankerConfig
from bridgetree.dependency_config import load_dependency_config
from bridgetree.diagnostic_identity import request_hash


@pytest.fixture
def scripts(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("reranker_regression"), importlib.import_module("repaired_chain_worker")


@pytest.mark.parametrize(
    "regression_ok,smoke_ok,expected_full", [(False, True, False), (True, False, False), (True, True, True)]
)
def test_formal_run_only_follows_both_acceptance_gates(
    scripts, monkeypatch, tmp_path, regression_ok, smoke_ok, expected_full
):
    regression, worker = scripts
    config = load_dependency_config("configs/chain_service_fixed.yaml")
    manifest = {
        "counts": {"singleton_500": 190, "batch_timeout": 3, "normal_control": 1},
        "smoke_question_ids": ["a", "b"],
    }
    dataset = SimpleNamespace(examples=[SimpleNamespace(question_id=q) for q in ["a", "b"]], public_dict=lambda: {})
    monkeypatch.setattr(worker, "load_dependency_config", lambda _: config)
    monkeypatch.setattr(worker, "load_dependency_dataset", lambda *a, **k: dataset)
    monkeypatch.setattr(worker, "read_bundle", lambda _: (manifest, []))
    monkeypatch.setattr(worker, "replay", lambda *a: {"passed": regression_ok})
    monkeypatch.setattr(worker.signal, "signal", lambda *a: None)
    calls = []

    def run(config, root, **kwargs):
        calls.append(kwargs)
        return {
            "status": "completed",
            "summary": {
                "successful_tasks": 10 if smoke_ok else 9,
                "failed_tasks": 0 if smoke_ok else 1,
                "pending_tasks": 0,
            },
        }

    monkeypatch.setattr(worker, "run_dependency_experiment", run)
    monkeypatch.setattr(
        "sys.argv", ["worker", "--config", "unused", "--bundle", "unused", "--output-dir", str(tmp_path / "run")]
    )
    result = worker.main()
    state = json.loads((tmp_path / "run/acceptance.json").read_text())
    assert calls[0]["preflight_only"]
    formal = [c for c in calls if not c.get("preflight_only") and c.get("require_full_32k")]
    assert bool(formal) == expected_full
    assert state["full_run_started"] == expected_full
    assert (result == 0) == expected_full
    if regression_ok:
        smoke = next(c for c in calls if "examples" in c)
        assert [e.question_id for e in smoke["examples"]] == ["a", "b"]


def test_regression_reuses_singleton_references_and_detects_batch_score_drift(scripts, monkeypatch, tmp_path):
    regression, _ = scripts

    def payload(docs):
        return {"query": "q", "documents": docs, "top_n": len(docs), "return_documents": False}

    rows = [
        {"payload": payload(docs), "request_hash": request_hash(payload(docs)), "kind": kind}
        for docs, kind in [(["a"], "singleton_500"), (["b"], "normal_control"), (["a", "b"], "batch_timeout")]
    ]
    manifest = {"absolute_tolerance": 1e-6, "relative_tolerance": 1e-4}
    monkeypatch.setattr(regression, "read_bundle", lambda _: (manifest, rows))

    class Client:
        def __init__(self, config):
            self.config, self.transport_stats = config, {}

        def verify_capacity_contract(self):
            return {"capacity_verification": "server_enforced"}

        def rerank_all(self, q, docs):
            return [SimpleNamespace(index=i, score=0.5 if len(docs) == 1 else 0.9) for i, d in enumerate(docs)]

    monkeypatch.setattr(regression, "RerankerClient", Client)
    config = SimpleNamespace(models=SimpleNamespace(reranker=RerankerConfig("http://test")), config_hash=lambda: "test")
    report = regression.replay("unused", config, tmp_path / "regression")
    assert not report["passed"]
    assert report["completed"] == 2
    assert len(report["results"]) == 3
    assert report["batch_consistency"][0]["max_absolute_difference"] == pytest.approx(0.4)


def test_repaired_config_preserves_methods_and_search_budgets():
    old = load_dependency_config("configs/chain_full.yaml")
    new = load_dependency_config("configs/chain_service_fixed.yaml")
    assert old.dependency == new.dependency
    assert old.execution == new.execution
    assert old.models.generator == new.models.generator
    assert old.models.embedding == new.models.embedding
    assert old.config_hash() != new.config_hash()
