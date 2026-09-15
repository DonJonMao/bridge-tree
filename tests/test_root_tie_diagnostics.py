from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass

import pytest

from bridgetree.dependency_config import DependencyConfig, load_dependency_config
from bridgetree.dependency_retrieval import ProposalBatch, ProposalHit
from bridgetree.dependency_scoring import SetReranker
from bridgetree.dependency_search import DependencySearcher, DynamicBundleSelector
from bridgetree.root_tie_diagnostics import compare_root_tie_runs, root_tie_order
from bridgetree.types import Memory


class FakeBudgetError(RuntimeError):
    pass


class MappingScorer:
    def __init__(self, values):
        self.values = {frozenset(key): value for key, value in values.items()}
        self.seen = set()
        self.limit = None

    @property
    def scored_sets(self):
        return len(self.seen)

    def set_budget(self, limit):
        self.limit = limit

    def preflight(self, sets):
        new = {frozenset(ids) for ids in sets} - self.seen
        if self.limit is not None and len(self.seen) + len(new) > self.limit:
            raise FakeBudgetError("set scoring budget exhausted")

    def score_sets(self, sets):
        self.preflight(sets)
        keys = [frozenset(ids) for ids in sets]
        self.seen.update(keys)
        return [self.values.get(key, 0.0) for key in keys]

    def feasible(self, ids):
        return True


@dataclass
class ScriptedRetriever:
    scripts: dict
    visible_ids: tuple[str, ...] = ("a", "b", "x", "z")
    fixed_pool: bool = False
    ann_calls: int = 0
    ann_limit: int | None = None

    def propose(self, target_id, premise_ids=(), fixed_pool=False):
        premises = tuple(sorted(premise_ids))
        blocked = self.ann_limit is not None and self.ann_calls >= self.ann_limit
        values = () if blocked else tuple(self.scripts.get((target_id, premises), ()))
        if not blocked:
            self.ann_calls += 1
        return ProposalBatch(
            probe_id=f"probe:{self.ann_calls}", stage="conditional",
            probe_text="fake conditional probe",
            hits=tuple(ProposalHit(value, 1.0 - rank * .1, rank) for rank, value in enumerate(values)),
            target_id=target_id, premise_ids=premises,
            source_memory_ids=(target_id, *premises),
            domain_scope="fixed_initial_pool" if fixed_pool else "full_visible_bank",
            excluded_ids=(target_id, *premises),
            ann_call_index=None if blocked else self.ann_calls,
            stop_reason="ann_budget_exhausted" if blocked else None,
        )


def _fixture(*, ann_limit=None, score_limit=64, **kwargs):
    scorer = MappingScorer({
        (): 0.0, ("a",): .1, ("b",): .2, ("x",): .1, ("z",): .1,
        ("a", "x"): .8, ("a", "z"): .8, ("b", "x"): .7,
    })
    retriever = ScriptedRetriever({
        ("a", ()): ("x", "z"), ("a", ("x",)): ("z",),
        ("a", ("z",)): ("x",), ("b", ()): ("x",),
    }, ann_limit=ann_limit)
    searcher = DependencySearcher(scorer, retriever, pair_rescue_width=0, max_scored_sets=score_limit, **kwargs)
    return searcher, scorer, retriever


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@pytest.mark.parametrize("explicit", [False, True])
def test_disabled_mode_matches_pre_change_archive_and_selection_goldens(explicit):
    # Captured from the unmodified legacy implementation before PR4.
    options = {"root_tie_break": "legacy_lexical", "root_tie_seed": None} if explicit else {}
    searcher, scorer, _ = _fixture(**options)
    archive = searcher.run(("b", "a"))
    selection = DynamicBundleSelector(scorer, max_selection_sets=64).select(archive)
    assert _digest(archive.public_dict()) == "f8d90c3ce796747749367a45e01238d87ddd1f948eba3199034981871aafb04c"
    assert _digest(selection.public_dict()) == "12dcd5603fc7bef18a1cfe511d1edad021be0d19f19a1d2406e8b81382f140dd"
    trace = searcher.root_tie_diagnostics(selection.selected_ids)
    assert trace["initial_candidate_order"] == ["b", "a"]
    assert trace["root_pop_order"] == ["a", "b"]
    assert trace["logical_unique_sets_charged_delta"] == archive.final_scored_sets - archive.initial_scored_sets
    assert trace["logical_unique_sets_charged_delta"] == 11  # excludes selection's twelfth set


def test_seeded_mode_changes_only_root_ties_and_preserves_positive_successor_ties():
    legacy, _, _ = _fixture()
    seeded, _, _ = _fixture(root_tie_break="seeded_hash", root_tie_seed=0)
    a, b = legacy.run(("b", "a")), seeded.run(("b", "a"))
    assert legacy.root_tie_diagnostics()["root_pop_order"] == ["a", "b"]
    assert seeded.root_tie_diagnostics()["root_pop_order"] == ["b", "a"]
    assert [(r.state.target_id, r.state.premise_ids) for r in b.state_records] == [
        ("b", ()), ("b", ("x",)), ("a", ()), ("a", ("x",)), ("a", ("z",)),
    ]
    # Positive b/x is still popped before the unvisited zero-priority a root.
    assert b.state_records[1].priority > b.state_records[2].priority
    # Equal-priority positive a/x and a/z still use the legacy premise ordering.
    assert b.state_records[3].priority == b.state_records[4].priority
    assert b.initial_target_ids == a.initial_target_ids == ("a", "b")
    assert b.bundle_ids == a.bundle_ids
    assert seeded.root_tie_diagnostics()["initial_candidate_order"] == ["b", "a"]
    # The root's initial-pool fallback measurement sequence is NOT shuffled.
    for target in ("a", "b"):
        assert [r.group_ids for r in a.activations if r.target_id == target and not r.premise_ids] == [
            r.group_ids for r in b.activations if r.target_id == target and not r.premise_ids
        ]


def test_stable_root_order_across_process_hash_seeds_and_input_permutations():
    code = (
        "import json; from bridgetree.root_tie_diagnostics import root_tie_order; "
        "print(json.dumps(root_tie_order(set(['q:m00003','q:m00001','q:m00002']), "
        "mode='seeded_hash', seed=17)))"
    )
    results = []
    for process_seed in ("0", "42", "random"):
        env = dict(os.environ, PYTHONHASHSEED=process_seed)
        results.append(subprocess.check_output([sys.executable, "-c", code], env=env, text=True))
    assert len(set(results)) == 1
    expected = root_tie_order(("q:m00002", "q:m00003", "q:m00001"), mode="seeded_hash", seed=17)
    assert json.loads(results[0]) == list(expected)
    assert root_tie_order(reversed(expected), mode="seeded_hash", seed=17) == expected


@pytest.mark.parametrize("ids", ["a", ("a", ""), ("a", 1)])
def test_root_order_does_not_silently_coerce_invalid_ids(ids):
    with pytest.raises(ValueError, match="root target IDs"):
        root_tie_order(ids)


@pytest.mark.parametrize("mode,seed", [
    ("round_robin", None), ([], None), ("legacy_lexical", 0),
    ("seeded_hash", None), ("seeded_hash", True), ("seeded_hash", -1), ("seeded_hash", 1.5),
])
def test_invalid_or_ineffective_root_settings_are_rejected(mode, seed):
    with pytest.raises(ValueError, match="root_tie"):
        DependencyConfig(root_tie_break=mode, root_tie_seed=seed)
    with pytest.raises(ValueError, match="root_tie"):
        _fixture(root_tie_break=mode, root_tie_seed=seed)


def test_opt_in_config_and_default_protocol_identity_are_explicit():
    base = load_dependency_config("configs/chain_full.yaml")
    enabled = load_dependency_config("configs/diagnostic_root_ties.yaml")
    assert base.dependency.root_tie_break == "legacy_lexical"
    assert base.dependency.root_tie_seed is None
    assert "root_tie_break" not in base.resolved_dict()["dependency"]
    old_fields = asdict(base.dependency)
    old_fields.pop("root_tie_break")
    old_fields.pop("root_tie_seed")
    assert base.resolved_dict()["dependency"] == old_fields
    assert enabled.resolved_dict()["dependency"]["root_tie_break"] == "seeded_hash"
    assert enabled.resolved_dict()["dependency"]["root_tie_seed"] == 0
    assert enabled.config_hash() != base.config_hash()
    for name in old_fields:
        assert getattr(enabled.dependency, name) == getattr(base.dependency, name)


@pytest.mark.parametrize("seed", [0, 1, 17])
@pytest.mark.parametrize("score_limit", [4, 64])
def test_seed_modes_preserve_budget_caps_and_exact_observed_cost_attribution(seed, score_limit):
    searcher, scorer, retriever = _fixture(
        root_tie_break="seeded_hash", root_tie_seed=seed, ann_limit=1, score_limit=score_limit,
    )
    archive = searcher.run(("b", "a"))
    trace = searcher.root_tie_diagnostics()
    assert retriever.ann_calls <= 1
    assert scorer.scored_sets <= score_limit
    assert sum(row["ann_calls_delta"] for row in trace["per_target"].values()) == archive.final_ann_calls - archive.initial_ann_calls
    assert sum(row["logical_unique_sets_charged_delta"] for row in trace["per_target"].values()) == archive.final_scored_sets - archive.initial_scored_sets
    assert trace["search_complete"] is True
    assert trace["final_selected_ids"] is None
    assert trace["final_selected_ids_hash"] is None
    assert trace["external_to_selected_rate"] is None


def test_compare_reports_actual_archive_and_selection_changes_without_inventing_outcomes():
    traces = []
    for seed in (0, 1):
        searcher, scorer, _ = _fixture(root_tie_break="seeded_hash", root_tie_seed=seed, ann_limit=1)
        archive = searcher.run(("b", "a"))
        selection = DynamicBundleSelector(scorer, max_selection_sets=64).select(archive)
        traces.append(searcher.root_tie_diagnostics(selection.selected_ids))
    result = compare_root_tie_runs(*traces)
    assert result["same_initial_targets"]["equal"] is True
    assert result["root_pop_order_equal"] is False
    assert result["archive"]["jaccard"] < 1
    assert result["final_selection"]["jaccard"] == pytest.approx(1 / 3)
    assert result["other_protocols_verified"] is False
    assert traces[0]["external_candidate_ids"] == ["x"]
    assert traces[1]["external_candidate_ids"] == ["x", "z"]
    assert traces[0]["external_selected_ids"] == ["x"]
    assert traces[1]["external_to_selected_rate"] == .5
    missing = compare_root_tie_runs({}, traces[1])
    assert missing["archive"] == {"available": False, "equal": None, "jaccard": None}
    assert missing["final_selection"]["jaccard"] is None
    assert missing["ann_calls_delta"]["baseline"] is None
    assert missing["ann_calls_delta"]["difference"] is None
    assert "correct" not in result


def test_partial_trace_uses_only_observed_counters_and_no_final_selection():
    class FailingScorer(MappingScorer):
        def score_sets(self, sets):
            super().score_sets(sets)  # a real logical charge occurred before the simulated failure
            raise RuntimeError("simulated infrastructure failure")

    scorer = FailingScorer({})
    searcher = DependencySearcher(scorer, ScriptedRetriever({("a", ()): ("x",)}), pair_rescue_width=0)
    assert searcher.root_tie_diagnostics() is None
    with pytest.raises(RuntimeError, match="simulated infrastructure"):
        searcher.run(("a",))
    trace = searcher.root_tie_diagnostics()
    assert trace["search_complete"] is False
    assert trace["search_stop_reason"] is None
    assert trace["final_selected_ids"] is None
    assert trace["states"][0]["completed"] is False
    assert trace["per_target"]["a"]["ann_calls_delta"] == 1
    assert trace["per_target"]["a"]["logical_unique_sets_charged_delta"] == scorer.scored_sets


def test_set_serialization_and_cold_warm_logical_budget_are_unchanged(tmp_path):
    class ConstantReranker:
        score_contract = "pointwise"
        score_space = "unit_interval"

        def __init__(self):
            self.calls = 0

        def rerank_all(self, query, documents):
            self.calls += 1
            return [{"index": i, "relevance_score": .1} for i in range(len(documents))]

    records = {
        key: Memory(key, f"memory {key}", timestamp=float(i), source_id=f"source:{key}")
        for i, key in enumerate(("a", "b", "x", "z"))
    }
    runs = []
    for warm in (False, True):
        client = ConstantReranker()
        scorer = SetReranker("question", records, client, cache_dir=tmp_path)
        searcher = DependencySearcher(
            scorer, ScriptedRetriever({}), root_tie_break="seeded_hash", root_tie_seed=0,
            pair_rescue_width=0, max_scored_sets=64,
        )
        before = scorer.serialize_set(("b", "a"))
        archive = searcher.run(("b", "a"))
        assert scorer.serialize_set(("a", "b")) == before
        runs.append((archive.public_dict(), scorer.scored_sets, client.calls, scorer.namespace_hash))
    assert runs[0][0] == runs[1][0]
    assert runs[0][1] == runs[1][1] > 0
    assert runs[0][2] > 0 and runs[1][2] == 0
    assert runs[0][3] == runs[1][3]
