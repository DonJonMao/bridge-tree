import math

import pytest

from bridgetree.chain_judge import Claim, JointScore, PublicQuery, Verification
from bridgetree.chain_search import ChainSearcher, EvidenceState, choose_terminal

QUERY = PublicQuery("fixture", "persona", "question", "question")


class RecordedJudge:
    def __init__(self, values, support=lambda ids: bool(ids)):
        self.values = values
        self.support = support
        self.requests = []

    def score(self, query, ids):
        self.requests.append(("score", ids))
        value = self.values.get(ids, .1)
        return JointScore.from_logits(math.log(value / (1 - value)), 0, input_hash=repr(ids))

    def claim(self, query, ids):
        self.requests.append(("claim", ids))
        return Claim("fixed relevant conclusion", ids, "fixture")

    def verify(self, query, claim, ids):
        self.requests.append(("verify", ids, claim.text))
        return Verification(self.support(ids))


def test_h1_stops_and_h2_rolls_past_first_horizon():
    values = {("a",): .50, ("a", "b"): .40, ("a", "b", "c"): .70,
              ("a", "b", "c", "d"): .95}
    proposals = {"a": ("b",), "b": ("c",), "c": ("d",)}
    h1 = ChainSearcher(QUERY, RecordedJudge(values), horizon=1).search(
        [EvidenceState(("a",))], proposals=proposals)
    h2 = ChainSearcher(QUERY, RecordedJudge(values), horizon=2).search(
        [EvidenceState(("a",))], proposals=proposals)
    assert choose_terminal(h1.observed_terminals).selected_ids == ("a",)
    assert {t.selected_ids for t in h1.observed_terminals} == {("a",), ("a", "b")}
    assert choose_terminal(h2.observed_terminals).selected_ids == ("a", "b", "c", "d")
    assert h2.probe_complete
    assert any(p["prefix"] == ("a", "b", "c") for p in h2.probes)


def test_real_parent_preserves_other_endpoint_and_existing_child_source():
    state = EvidenceState(("a", "x"))
    child = state.extend("b", parent="a")
    assert child.paths == (("a", "b"), ("x",))
    assert child.expandable_ids == ("b", "x")
    shared = child.extend("b", parent="x")
    assert shared.raw_ids == ("a", "b", "x")
    assert shared.paths == (("a", "b"), ("x", "b"))
    assert child.paths == (("a", "b"), ("x",))
    assert shared.extend("a", parent="b", source_path=("a", "b")) == shared


def test_join_preserves_expansion_from_both_sources():
    joined = EvidenceState(("a",)).join(EvidenceState(("x",)))
    archive = ChainSearcher(QUERY, RecordedJudge({("a", "x", "z"): .9})).search(
        [joined], proposals={"x": ("z",)})
    selected = choose_terminal(archive.observed_terminals)
    assert selected.selected_ids == ("a", "x", "z")
    assert ("x", "z") in selected.state.paths
    assert ("a", "z") not in selected.state.paths


@pytest.mark.parametrize("c_score,w_score,expected", [(.91, .55, ("a", "b")), (.55, .91, ("a",))])
def test_original_and_closed_terminal_keep_own_score(c_score, w_score, expected):
    judge = RecordedJudge({("a", "b"): c_score, ("a",): w_score}, lambda ids: "a" in ids)
    archive = ChainSearcher(QUERY, judge, horizon=0).search([EvidenceState(("a", "b"))], closure=True)
    terminals = {t.selected_ids: t for t in archive.verified_terminals}
    assert terminals[("a", "b")].score.u == pytest.approx(c_score)
    assert terminals[("a",)].score.u == pytest.approx(w_score)
    assert choose_terminal(archive.verified_terminals).selected_ids == expected
    assert not terminals[("a", "b")].selected_is_minimal
    assert terminals[("a",)].selected_is_minimal
    assert {r[2] for r in judge.requests if r[0] == "verify"} == {"fixed relevant conclusion"}


def test_verify_budget_is_shared_by_all_roots_and_zero_never_claims():
    for budget in (0, 1):
        judge = RecordedJudge({("a",): .4, ("b",): .6, ("c",): .9})
        searcher = ChainSearcher(QUERY, judge, horizon=0, max_verify_calls=budget)
        archive = searcher.search([EvidenceState((x,)) for x in "abc"], closure=True)
        assert len([r for r in judge.requests if r[0] == "verify"]) <= budget
        assert len([r for r in judge.requests if r[0] == "claim"]) <= budget
        assert len(archive.observed_terminals) == 3
        assert len(archive.verified_terminals) == budget


def test_joint_budget_one_preserves_root_and_marks_incomplete():
    judge = RecordedJudge({("a",): .6})
    archive = ChainSearcher(QUERY, judge, max_joint_contexts=1).search(
        [EvidenceState(("a",))], proposals={"a": ("b",)})
    assert choose_terminal(archive.observed_terminals).selected_ids == ("a",)
    assert not archive.probe_complete
    assert archive.stop_reason == "joint_budget_exhausted"
    assert all(p["reason"] != "local_no_improvement" for p in archive.probes)


def test_roots_receive_budget_before_first_root_descendants():
    judge = RecordedJudge({("a",): .6, ("x",): .7})
    archive = ChainSearcher(QUERY, judge, max_joint_contexts=2).search(
        [EvidenceState(("a",)), EvidenceState(("x",))], proposals={"a": ("b", "c", "d")})
    assert {t.selected_ids for t in archive.observed_terminals} == {("a",), ("x",)}


def test_reader_oversize_can_close_without_truncating_judge():
    judge = RecordedJudge({("a", "b"): .91, ("a",): .55}, lambda ids: "a" in ids)
    archive = ChainSearcher(QUERY, judge, horizon=0, reader_limit=1, judge_limit=2).search(
        [EvidenceState(("a", "b"))], closure=True)
    assert ("score", ("a", "b")) in judge.requests
    assert choose_terminal(archive.verified_terminals).selected_ids == ("a",)
    assert all(len(t.selected_ids) <= 1 for t in archive.observed_terminals)


def test_closed_rescore_exhaustion_preserves_verified_original():
    judge = RecordedJudge({("a", "b"): .91}, lambda ids: "a" in ids)
    archive = ChainSearcher(QUERY, judge, horizon=0, max_joint_contexts=1).search(
        [EvidenceState(("a", "b"))], closure=True)
    assert choose_terminal(archive.verified_terminals).selected_ids == ("a", "b")


def test_navigation_identity_distinguishes_actions_endpoints_and_history():
    state = EvidenceState(("a", "b"), (("a", "b"),))
    changed = EvidenceState(("b", "a"), (("a", "b"),), completed_actions=frozenset({"done"}))
    assert state.navigation_key != changed.navigation_key
    assert state.navigation_key == EvidenceState(("b", "a"), (("a", "b"),), graph_epoch=100).navigation_key


def test_model_error_is_not_converted_to_budget_stop():
    class Broken(RecordedJudge):
        def score(self, query, ids):
            raise ValueError("missing label")

    with pytest.raises(ValueError, match="missing label"):
        ChainSearcher(QUERY, Broken({})).search([EvidenceState(("a",))])
