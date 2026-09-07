import pytest

from bridgetree.chain_judge import preflight_joint_backend, require_label_pair


def test_label_pair_requires_both_labels():
    with pytest.raises(ValueError, match="both configured labels"):
        require_label_pair({"logprobs": {"A": -1.0}})


def test_preflight_rejects_backend_without_probe():
    with pytest.raises(ValueError, match="probe"):
        preflight_joint_backend(object())


def test_preflight_accepts_same_position_probe():
    class Backend:
        def probe_label_scores(self, **_):
            return {"logprobs": {"A": -0.2, "B": -1.2}}

    result = preflight_joint_backend(Backend())
    assert result["same_position"] is True
