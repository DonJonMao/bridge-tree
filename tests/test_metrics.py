import numpy as np

from bridgetree.metrics import (
    answer_accuracy,
    answer_parse_failed,
    bridge_recall_at_k,
    direct_ranks,
    paired_bootstrap_interval,
    recall_at_k,
)


def test_answer_and_recall_metrics():
    assert answer_accuracy("The answer is (C).", "(c)") == 1.0
    assert recall_at_k(["a", "b"], ["b", "c"], 2) == 0.5


def test_bridge_gold_is_external_gold_partitioned_by_direct_rank():
    ids = ["direct", "other", "bridge"]
    vectors = np.eye(3)
    ranks = direct_ranks(np.array([1.0, 0.5, 0.1]), ids, vectors)
    assert ranks["bridge"] == 3
    assert bridge_recall_at_k(["bridge"], ["direct", "bridge"], ranks, k=2) == 1.0
    assert bridge_recall_at_k(["direct"], ["direct"], ranks, k=2) is None


def test_answer_parser_supports_official_and_common_label_forms():
    for response in ("(a)", "A", "A.", "option A", "选A", "The answer is A"):
        assert answer_accuracy(response, "(a)") == 1.0
        assert answer_parse_failed(response) == 0.0
    assert answer_parse_failed("I cannot determine the option") == 1.0


def test_paired_bootstrap_is_deterministic_and_paired():
    first = paired_bootstrap_interval([1, 1, 0, 1], [0, 1, 0, 0], seed=7, resamples=100)
    second = paired_bootstrap_interval([1, 1, 0, 1], [0, 1, 0, 0], seed=7, resamples=100)
    assert first == second
    assert first["mean_difference"] == 0.5
