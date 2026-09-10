from __future__ import annotations

from dataclasses import dataclass

import pytest

from bridgetree.dependency_retrieval import DependencyRetriever, ProposalBatch, ProposalHit
from bridgetree.dependency_search import (
    DependencySearcher,
    DynamicBundleSelector,
    EvidenceBundle,
)
from bridgetree.types import Memory


class FakeBudgetError(RuntimeError):
    pass


class MappingScorer:
    def __init__(self, values, default=0.0):
        self.values = {frozenset(key): value for key, value in values.items()}
        self.default = default
        self.seen = set()
        self.limit = None

    @property
    def scored_sets(self):
        return len(self.seen)

    def set_budget(self, limit):
        if limit is not None and limit < self.scored_sets:
            raise ValueError("cannot lower budget below scored sets")
        self.limit = limit

    def preflight(self, sets):
        new = {frozenset(ids) for ids in sets}.difference(self.seen)
        if self.limit is not None and self.scored_sets + len(new) > self.limit:
            raise FakeBudgetError("set scoring budget exhausted")

    def score_sets(self, sets):
        self.preflight(sets)
        result = []
        for ids in sets:
            key = frozenset(ids)
            self.seen.add(key)
            result.append(self.values.get(key, self.default))
        return result

    def feasible(self, ids):
        return True


@dataclass
class ScriptedRetriever:
    scripts: dict
    visible_ids: tuple[str, ...]
    fixed_pool: bool = False
    ann_calls: int = 0

    def propose(self, target_id, premise_ids=(), fixed_pool=False):
        assert target_id not in premise_ids
        key = (target_id, tuple(sorted(premise_ids)))
        values = tuple(self.scripts.get(key, ()))
        self.ann_calls += 1
        return ProposalBatch(
            probe_id=f"probe:{self.ann_calls}",
            stage="conditional",
            probe_text="fake conditional probe",
            hits=tuple(ProposalHit(identifier, 1.0 - rank * 0.1, rank) for rank, identifier in enumerate(values)),
            target_id=target_id,
            premise_ids=tuple(sorted(premise_ids)),
            source_memory_ids=(target_id, *tuple(sorted(premise_ids))),
            domain_scope="fixed_initial_pool" if fixed_pool else "full_visible_bank",
            excluded_ids=(target_id, *tuple(sorted(premise_ids))),
            ann_call_index=self.ann_calls,
        )


def test_activation_is_four_term_difference_and_multistep_path_keeps_target_and_retests_candidate():
    # x is slightly negative at P=empty, then strongly positive after p has
    # been accepted.  A global tested-candidate ban would miss the second x.
    values = {
        (): 0.10,
        ("e",): 0.20,
        ("p",): 0.10,
        ("e", "p"): 0.50,
        ("x",): 0.30,
        ("e", "x"): 0.35,
        ("p", "x"): 0.20,
        ("e", "p", "x"): 0.90,
    }
    retriever = ScriptedRetriever(
        {("e", ()): ("p", "x"), ("e", ("p",)): ("x",)},
        ("e", "p", "x"),
    )
    archive = DependencySearcher(
        MappingScorer(values),
        retriever,
        pair_rescue_width=0,
        max_scored_sets=64,
    ).run(("e",))

    x_records = [record for record in archive.activations if record.group_ids == ("x",)]
    assert len(x_records) == 2
    assert x_records[0].premise_ids == ()
    assert x_records[0].activation == pytest.approx(-0.05)
    assert x_records[1].premise_ids == ("p",)
    assert x_records[1].activation == pytest.approx(0.30)
    assert x_records[1].accepted is True
    assert all(record.target_id == "e" for record in archive.activations)
    assert ("e", "p", "x") in archive.bundle_ids
    assert any(record.event == "expanded" for record in archive.state_records)

    p_record = next(record for record in archive.activations if record.group_ids == ("p",))
    telescoped = p_record.activation + x_records[1].activation
    expected = (values[("e", "p", "x")] - values[("p", "x")]) - (
        values[("e",)] - values[()]
    )
    assert telescoped == pytest.approx(expected)


def test_diamond_paths_measure_distinct_activations_but_queue_successor_once():
    values = {
        (): 0.0,
        ("e",): 0.0,
        ("a",): 0.0,
        ("b",): 0.0,
        ("a", "e"): 1.0,
        ("b", "e"): 0.9,
        ("a", "b"): 0.0,
        ("a", "b", "e"): 2.5,
    }
    retriever = ScriptedRetriever(
        {
            ("e", ()): ("a", "b"),
            ("e", ("a",)): ("b",),
            ("e", ("b",)): ("a",),
        },
        ("e", "a", "b"),
    )
    archive = DependencySearcher(
        MappingScorer(values), retriever, pair_rescue_width=0, max_scored_sets=64
    ).run(("e",))

    diamond_records = [
        record
        for record in archive.activations
        if (record.premise_ids, record.group_ids)
        in {(("a",), ("b",)), (("b",), ("a",))}
    ]
    assert {
        (record.premise_ids, record.group_ids) for record in diamond_records
    } == {(("a",), ("b",)), (("b",), ("a",))}
    assert all(record.accepted for record in diamond_records)
    assert sum(record.queued for record in diamond_records) == 1
    assert sum(
        record.state.premise_ids == ("a", "b") for record in archive.state_records
    ) == 1


def test_pair_diamond_measures_duplicate_successor_interaction_without_requeueing():
    values = {
        (): 0.0,
        ("e",): 0.0,
        ("a",): 0.0,
        ("b",): 0.0,
        ("a", "e"): 1.0,
        ("b", "e"): 0.9,
        ("a", "b"): 0.0,
        ("a", "b", "e"): 0.0,
        ("c",): 0.0,
        ("a", "c"): 0.0,
        ("a", "c", "e"): 0.0,
        ("b", "c"): 0.0,
        ("b", "c", "e"): 0.0,
        ("a", "b", "c"): 0.0,
        ("a", "b", "c", "e"): 3.0,
    }
    retriever = ScriptedRetriever(
        {
            ("e", ()): ("a", "b"),
            ("e", ("a",)): ("b", "c"),
            ("e", ("b",)): ("a", "c"),
        },
        ("e", "a", "b", "c"),
    )
    archive = DependencySearcher(
        MappingScorer(values), retriever, pair_rescue_width=2, max_scored_sets=128
    ).run(("e",))

    diamond_pairs = [
        record
        for record in archive.activations
        if (record.premise_ids, record.group_ids)
        in {(("a",), ("b", "c")), (("b",), ("a", "c"))}
    ]
    assert {
        (record.premise_ids, record.group_ids) for record in diamond_pairs
    } == {(("a",), ("b", "c")), (("b",), ("a", "c"))}
    assert all(record.accepted for record in diamond_pairs)
    assert sum(record.queued for record in diamond_pairs) == 1
    assert sum(
        record.state.premise_ids == ("a", "b", "c")
        for record in archive.state_records
    ) == 1


def test_root_activation_provenance_tracks_each_merged_candidate_source():
    retriever = ScriptedRetriever(
        {("e", ()): ("conditional_only", "both")},
        ("e", "conditional_only", "both", "initial_only"),
    )
    archive = DependencySearcher(
        MappingScorer({}), retriever, pair_rescue_width=0, max_scored_sets=128
    ).run(("e", "both", "initial_only"))

    root_batch = next(
        batch
        for batch in archive.proposal_batches
        if batch.target_id == "e" and not batch.premise_ids
    )
    sources = {
        record.group_ids[0]: record.proposal_sources
        for record in archive.activations
        if record.target_id == "e" and not record.premise_ids
    }
    assert sources == {
        "conditional_only": (root_batch.probe_id,),
        "both": (root_batch.probe_id, "initial_pool"),
        "initial_only": ("initial_pool",),
    }


def test_positive_successor_runs_before_remaining_zero_priority_roots():
    class RecordingRetriever(ScriptedRetriever):
        def __post_init__(self):
            self.requests = []

        def propose(self, target_id, premise_ids=(), fixed_pool=False):
            self.requests.append((target_id, tuple(sorted(premise_ids))))
            return super().propose(target_id, premise_ids, fixed_pool=fixed_pool)

    retriever = RecordingRetriever(
        {("e", ()): ("p",), ("e", ("p",)): ()},
        ("e", "p", "z"),
    )
    retriever.__post_init__()
    scorer = MappingScorer(
        {(): 0.1, ("e",): 0.2, ("p",): 0.1, ("e", "p"): 0.6}
    )

    DependencySearcher(
        scorer, retriever, pair_rescue_width=0, max_scored_sets=32
    ).run(("e", "z"))

    assert retriever.requests[:2] == [("e", ()), ("e", ("p",))]


def test_required_numeric_activation_example_is_point_four():
    values = {(): 0.10, ("e",): 0.25, ("p",): 0.35, ("e", "p"): 0.90}
    retriever = ScriptedRetriever({("e", ()): ("p",)}, ("e", "p"))
    archive = DependencySearcher(
        MappingScorer(values), retriever, pair_rescue_width=0, max_scored_sets=16
    ).run(("e",))
    record = archive.activations[0]
    assert pytest.approx(0.10) == record.P
    assert record.Pe == pytest.approx(0.25)
    assert pytest.approx(0.35) == record.PG
    assert record.PGe == pytest.approx(0.90)
    assert record.activation == pytest.approx(0.40)
    assert record.public_dict()["PGe"] == pytest.approx(0.90)
    assert record.public_dict()["sets"] == {
        "P": [],
        "Pe": ["e"],
        "PG": ["p"],
        "PGe": ["e", "p"],
    }


def test_finite_ann_budget_still_archives_a_discovered_nonempty_premise_state():
    class TinyEmbedder:
        vectors = {"target": [1.0, 0.0], "premise": [0.9, 0.1]}

        def encode(self, texts):
            import numpy as np

            return np.asarray([self.vectors[text] for text in texts], dtype=np.float32)

        def encode_query(self, _text, instruction=None):
            import numpy as np

            return np.asarray([1.0, 0.0], dtype=np.float32)

    memories = (
        Memory("e", "target", 0, "source:e", {"roles": ["user"]}),
        Memory("p", "premise", 1, "source:p", {"roles": ["user"]}),
    )
    # One dense call plus one bridge call per root consumes all three calls.
    # The first root can still measure its already exposed root-pool premise;
    # the positive successor must be archived before the global ANN stop.
    retriever = DependencyRetriever(
        "question",
        memories,
        TinyEmbedder(),
        initial_width=2,
        initial_expansion_width=1,
        proposal_width=1,
        max_ann_calls=3,
    )
    pool = retriever.build_initial_pool()
    assert retriever.remaining_ann_calls == 0
    scorer = MappingScorer({(): 0.1, ("e",): 0.25, ("p",): 0.35, ("e", "p"): 0.9})
    archive = DependencySearcher(
        scorer, retriever, pair_rescue_width=0, max_scored_sets=16
    ).run(pool)
    assert ("e", "p") in archive.bundle_ids
    assert archive.stop_reason == "ann_budget_exhausted"
    assert archive.activations[0].queued is True


def test_pair_rescue_finds_joint_signal_when_both_singletons_are_nonpositive():
    values = {
        (): 0.10,
        ("e",): 0.20,
        ("a",): 0.20,
        ("e", "a"): 0.30,
        ("b",): 0.20,
        ("e", "b"): 0.30,
        ("a", "b"): 0.20,
        ("e", "a", "b"): 0.80,
    }
    retriever = ScriptedRetriever({("e", ()): ("a", "b")}, ("e", "a", "b"))
    archive = DependencySearcher(
        MappingScorer(values), retriever, pair_rescue_width=2, max_scored_sets=32
    ).run(("e",))

    singles = [record for record in archive.activations if len(record.group_ids) == 1]
    pair = next(record for record in archive.activations if len(record.group_ids) == 2)
    assert all(record.activation <= 0.0 for record in singles)
    assert pair.group_ids == ("a", "b")
    assert pair.activation == pytest.approx(0.50)
    assert pair.accepted and pair.queued
    assert ("a", "b", "e") in archive.bundle_ids


def test_one_oversize_singleton_does_not_suppress_a_feasible_pair_rescue():
    class CapacityScorer(MappingScorer):
        def preflight(self, sets):
            if any("oversize" in ids for ids in sets):
                raise RuntimeError("reranker input capacity exceeded")
            super().preflight(sets)

    values = {
        (): 0.10,
        ("e",): 0.20,
        ("a",): 0.20,
        ("a", "e"): 0.30,
        ("b",): 0.20,
        ("b", "e"): 0.30,
        ("a", "b"): 0.20,
        ("a", "b", "e"): 0.80,
    }
    retriever = ScriptedRetriever(
        {("e", ()): ("oversize", "a", "b")},
        ("e", "oversize", "a", "b"),
    )
    archive = DependencySearcher(
        CapacityScorer(values), retriever, pair_rescue_width=3, max_scored_sets=32
    ).run(("e",))

    pair = next(record for record in archive.activations if record.group_ids == ("a", "b"))
    assert pair.accepted and pair.queued
    assert ("a", "b", "e") in archive.bundle_ids
    assert archive.state_records[0].event == "expanded"
    assert "input_capacity" in archive.state_records[0].detail
    assert archive.stop_reason == "input_capacity"


def test_context_marginal_control_uses_same_four_scores_but_different_acceptance_signal():
    # Activation is positive (.10), while adding p to the target context
    # decreases the total score (-.10).
    values = {(): 0.50, ("e",): 0.80, ("p",): 0.10, ("e", "p"): 0.70}
    activation_retriever = ScriptedRetriever({("e", ()): ("p",)}, ("e", "p"))
    activation = DependencySearcher(
        MappingScorer(values), activation_retriever, signal="activation", pair_rescue_width=0
    ).run(("e",))
    assert activation.activations[0].activation == pytest.approx(0.30)
    assert activation.activations[0].context_marginal == pytest.approx(-0.10)
    assert activation.activations[0].accepted is True

    marginal_retriever = ScriptedRetriever({("e", ()): ("p",)}, ("e", "p"))
    marginal = DependencySearcher(
        MappingScorer(values), marginal_retriever, signal="context_marginal", pair_rescue_width=0
    ).run(("e",))
    assert marginal.activations[0].activation == pytest.approx(0.30)
    assert marginal.activations[0].accepted is False


def bundle(*ids):
    return EvidenceBundle(tuple(ids), ("test",))


def test_positive_activation_with_lower_bundle_score_still_allows_singleton_to_win_selection():
    scorer = MappingScorer(
        {(): 0.10, ("e",): 0.80, ("p",): 0.10, ("e", "p"): 0.70}
    )
    result = DynamicBundleSelector(scorer, max_selection_sets=16).select(
        (bundle("e"), bundle("e", "p"), bundle("p"))
    )
    assert result.selected_ids == ("e",)
    assert result.rounds[0].accepted_bundle_ids == ("e",)
    assert result.stop_reason == "no_positive_marginal"


def test_selector_recomputes_every_bundle_marginal_after_each_union():
    scorer = MappingScorer(
        {
            (): 0.0,
            ("a",): 0.60,
            ("b",): 0.50,
            ("c",): 0.40,
            ("a", "b"): 0.61,
            ("a", "c"): 0.90,
            ("b", "c"): 0.55,
            ("a", "b", "c"): 0.89,
        }
    )
    result = DynamicBundleSelector(scorer, max_selection_sets=32).select(
        (bundle("a"), bundle("b"), bundle("c"))
    )
    assert result.rounds[0].accepted_bundle_ids == ("a",)
    # b ranked above c at S=empty, but c has the larger current marginal
    # after a enters the union.
    assert result.rounds[1].accepted_bundle_ids == ("c",)
    assert result.selected_ids == ("a", "c")


def test_incomplete_selection_round_commits_nothing():
    scorer = MappingScorer({(): 0.0, ("a",): 0.7, ("b",): 0.6})
    result = DynamicBundleSelector(scorer, max_selection_sets=2).select(
        (bundle("a"), bundle("b"))
    )
    assert result.selected_ids == ()
    assert result.stop_reason == "score_budget_exhausted"
    assert len(result.rounds) == 1
    assert result.rounds[0].complete is False
    assert result.rounds[0].accepted_bundle_ids is None
    assert all(not comparison.accepted for comparison in result.rounds[0].comparisons)


def test_selector_tie_break_is_deterministic_and_prefers_fewer_new_memories():
    scorer = MappingScorer({(): 0.0, ("a",): 0.5, ("b", "c"): 0.5}, default=0.5)
    result = DynamicBundleSelector(scorer, max_selection_sets=16).select(
        (bundle("b", "c"), bundle("a"))
    )
    assert result.rounds[0].accepted_bundle_ids == ("a",)


def test_search_exception_snapshot_preserves_completed_activations_and_states():
    class BrokenLaterScorer(MappingScorer):
        def score_sets(self, sets):
            if any("x" in ids for ids in sets):
                raise ValueError("fake backend failure")
            return super().score_sets(sets)

    retriever = ScriptedRetriever(
        {("e", ()): ("p",), ("e", ("p",)): ("x",)},
        ("e", "p", "x"),
    )
    searcher = DependencySearcher(
        BrokenLaterScorer(
            {(): 0.1, ("e",): 0.2, ("p",): 0.1, ("e", "p"): 0.6}
        ),
        retriever,
        pair_rescue_width=0,
        max_scored_sets=32,
    )

    with pytest.raises(ValueError, match="backend failure"):
        searcher.run(("e",))
    snapshot = searcher.partial_public_dict(detail="fake backend failure")
    assert snapshot is not None
    assert snapshot["partial"] is True
    assert len(snapshot["activations"]) == 1
    assert snapshot["activations"][0]["group_ids"] == ["p"]
    assert len(snapshot["states"]) == 1
    assert snapshot["stop"]["global_certificate"] is False


def test_selector_exception_snapshot_preserves_completed_rounds_and_union():
    class BrokenSecondRoundScorer(MappingScorer):
        def score_sets(self, sets):
            if self.seen and any(frozenset(ids) == frozenset(("a", "b")) for ids in sets):
                raise ValueError("fake selection backend failure")
            return super().score_sets(sets)

    selector = DynamicBundleSelector(
        BrokenSecondRoundScorer(
            {(): 0.0, ("a",): 0.6, ("b",): 0.5, ("a", "b"): 0.9}
        ),
        max_selection_sets=16,
    )

    with pytest.raises(ValueError, match="selection backend failure"):
        selector.select((bundle("a"), bundle("b")))
    snapshot = selector.partial_public_dict(detail="fake selection backend failure")
    assert snapshot is not None
    assert snapshot["selected_ids"] == ["a"]
    assert len(snapshot["rounds"]) == 1
    assert snapshot["rounds"][0]["accepted_bundle_ids"] == ["a"]
