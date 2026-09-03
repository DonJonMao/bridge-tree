import numpy as np

from bridgetree.offline_validation import OfflineDeterministicEmbedder


def test_offline_full_validation_embedder_is_deterministic_normalized_and_explicitly_small():
    embedder = OfflineDeterministicEmbedder()
    first = embedder.encode(["alpha", "beta"])
    second = embedder.encode(["alpha", "beta"])

    assert first.shape == (2, 16)
    assert np.array_equal(first, second)
    assert np.allclose(np.linalg.norm(first, axis=1), 1.0)
    assert not np.array_equal(first[0], embedder.encode_query("alpha"))
