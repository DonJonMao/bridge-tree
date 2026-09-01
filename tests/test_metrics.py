import numpy as np

from bridgetree.metrics import answer_accuracy, bridge_recall_at_k, direct_ranks, recall_at_k


def test_answer_and_recall_metrics():
    assert answer_accuracy("The answer is (C).", "(c)") == 1.0
    assert recall_at_k(["a", "b"], ["b", "c"], 2) == 0.5


def test_bridge_gold_is_external_gold_partitioned_by_direct_rank():
    ids = ["direct", "other", "bridge"]
    vectors = np.eye(3)
    ranks = direct_ranks(np.array([1.0, 0.5, 0.1]), ids, vectors)
    assert ranks["bridge"] == 3
    assert bridge_recall_at_k(["bridge"], ["direct", "bridge"], ranks, k=2) == 1.0
