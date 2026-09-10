from dataclasses import replace

import pytest

from bridgetree.chain_experiment import DEFAULT_CHAIN_METHODS, ChainTask, ChainTaskExecutor
from bridgetree.chain_fixture import FixtureTransport
from bridgetree.config import load_config
from bridgetree.personamem import PersonaMemExample


def example(gold="(a)"):
    return PersonaMemExample("p", "q", "", "", "Where can I work quietly?", gold,
                             '["(a) Library", "(b) Club"]', "context", 4,
                             [{"role": "user", "content": "I need quiet places to work."},
                              {"role": "assistant", "content": "Consider a library."},
                              {"role": "user", "content": "I also need a desk."},
                              {"role": "assistant", "content": "Libraries have desks."}])


def config_for(path):
    config = load_config("configs/chain_full.yaml")
    return replace(config, runtime=replace(config.runtime, cache_dir=str(path)),
                   chain=replace(config.chain, initial_width=2, max_joint_contexts=16,
                                 max_claim_calls=2, max_verify_calls=8, max_proposal_calls=4))


@pytest.mark.parametrize("method", DEFAULT_CHAIN_METHODS)
def test_each_production_method_reaches_reader_and_evaluator(tmp_path, method):
    config = config_for(tmp_path)
    transport = FixtureTransport()
    executor = ChainTaskExecutor(config, transport=transport, backend="fixture")
    task = ChainTask("fixture", "seen", "p", "q", method, config.config_hash())
    result = executor.execute(task, example())
    assert result["status"] == "success"
    assert result["prediction"].startswith("(a)")
    assert result["correct"] is True
    assert result["backend"] == "fixture"
    assert result["context_hash"]
    if method == "semantic_s2":
        assert result["diagnostics"]["routed_method"] == "semantic_path"


def test_gold_changes_only_evaluation_not_any_request(tmp_path):
    records = []
    for i, gold in enumerate(("(a)", "(b)")):
        config = config_for(tmp_path / str(i))
        transport = FixtureTransport()
        executor = ChainTaskExecutor(config, transport=transport, backend="fixture")
        task = ChainTask("fixture", "seen", "p", "q", "chain_full", config.config_hash())
        result = executor.execute(task, example(gold))
        assert result["correct"] == (gold == "(a)")
        records.append(transport.requests)
    assert records[0] == records[1]
