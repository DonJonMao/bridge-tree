from bridgetree.chain_judge import Claim, JointScore, PublicQuery, Verification
from bridgetree.chain_search import ChainSearcher, EvidenceState, choose_terminal
from bridgetree.chain_support import close_support


class Judge:
    def __init__(self):
        self.calls = []

    def score(self, q, ids):
        # Deliberate valley: a -> a,b is worse, a,b,c is best.
        values = {("a",): .60, ("a", "b"): .55, ("a", "b", "c"): .91}
        u = values.get(ids, .4)
        import math
        d = math.log(u / (1 - u))
        return JointScore.from_logits(d, 0, input_hash="x")

    def claim(self, q, ids):
        return Claim("fixed", tuple(ids), "x")

    def verify(self, q, claim, ids):
        return Verification(set(ids) >= {"a", "b"}, input_hash="x")


def test_h2_keeps_a_lower_intermediate_and_finds_best_terminal():
    judge = Judge()
    archive = ChainSearcher(PublicQuery("d", "p", "q", "question"), judge, horizon=2).search(
        [EvidenceState(("a",), paths=(("a",),), expandable_ids=("a",))],
        proposals={"a": ("b",), "b": ("c",)},
    )
    assert choose_terminal(archive.observed_terminals).selected_ids == ("a", "b", "c")


def test_support_uses_one_fixed_claim_and_restarts_after_each_delete():
    result = close_support(PublicQuery("d", "p", "q", "question"), ("a", "b", "c"), Judge())
    assert result.status == "single_deletion_minimal"
    assert result.retained_ids == ("a", "b")
    assert all(entry["removed"] != "b" or entry["supported"] is False for entry in result.deletion_trace)


def test_budget_exhaustion_keeps_initially_supported_terminal():
    judge = Judge()
    archive = ChainSearcher(PublicQuery("d", "p", "q", "question"), judge,
                            horizon=0, max_verify_calls=1).search(
        [EvidenceState(("a", "b"), paths=(("a", "b"),))], closure=True
    )
    assert len(archive.verified_terminals) == 1
    assert archive.verified_terminals[0].selected_ids == ("a", "b")
