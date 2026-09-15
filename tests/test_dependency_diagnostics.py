"""Independent offline fixtures; no real model, network, or private dataset."""
import hashlib
import io
import json
import socket
import subprocess
import sys
import tarfile

import pytest

from bridgetree.dependency_diagnostics import (
    DEFAULT_DIAGNOSTIC_CASES, MissingDiagnosticScores, RecordedSetScorer,
    analyze_reachability, audit_diagnostic_cases, case_universe,
    enumerate_case_subsets, replay_selector,
)
from bridgetree.diagnostic_import import (
    DiagnosticImportError, HistoricalScoreConflict, import_historical_scores,
    load_diagnostic_archive,
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("diagnostic attempted network access")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr("bridgetree.clients._post_json", forbidden)


def comparison(current, bundle, base, combined, accepted=False, feasible=True):
    union = sorted(set(current) | set(bundle))
    return {"current_ids": current, "bundle_ids": bundle, "union_ids": union,
            "feasible": feasible, "base_score": base, "combined_score": combined,
            "marginal": combined - base if combined is not None and base is not None else None,
            "accepted": accepted}


@pytest.fixture
def historical():
    # Literal independent fixture: choose a (.5) then reject b (.45 < .5).
    # Search already measured all four sets, so selection adds zero charges.
    return {"task_id": "task", "method_id": "activation", "search": {
        "activations": [{"premise_ids": [], "target_id": "a", "group_ids": ["b"],
                         "P": .1, "Pe": .5, "PG": .4, "PGe": .45,
                         "activation": -.35, "context_marginal": -.05}],
        "bundles": [{"memory_ids": ["a"]}, {"memory_ids": ["b"]}]},
        "selection": {"selected_ids": ["a"], "initial_scored_sets": 4,
                      "final_scored_sets": 4,
                      "stop": {"reason": "no_positive_marginal"},
                      "rounds": [
                          {"current_ids": [], "accepted_bundle_ids": ["a"],
                           "selected_ids_after": ["a"], "comparisons": [
                               comparison([], ["a"], .1, .5, True),
                               comparison([], ["b"], .1, .4)]},
                          {"current_ids": ["a"], "accepted_bundle_ids": None,
                           "selected_ids_after": ["a"], "comparisons": [
                               comparison(["a"], ["b"], .5, .45)]}]}}


def score_view(values):
    return {"origin": "synthetic", "records": [{"ids": list(ids), "score": score}
                                                 for ids, score in values.items()]}


def tar_bytes(members):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, content in members:
            raw = content if isinstance(content, bytes) else json.dumps(content).encode()
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            archive.addfile(member, io.BytesIO(raw))
    return output.getvalue()


def test_literal_import_retains_provenance_and_empty(historical):
    result = import_historical_scores(historical, provenance={"source_sha256": "a" * 64,
                                                            "member": "candidate_pool/task.json"})
    assert result["unique_score_count"] == 4
    empty = next(row for row in result["records"] if row["ids"] == [])
    assert empty["score"] == .1
    assert len(empty["observations"]) == 3
    assert empty["observations"][0]["json_pointer"] == "/search/activations/0/P"
    assert all(row["origin"] == "historical_literal" for row in empty["observations"])
    assert empty["observations"][0]["source_sha256"] == "a" * 64
    assert len(result["search_seen_ids"]) == 4
    json.dumps(result, allow_nan=False)


def test_duplicate_score_conflict_not_last_write_wins(historical):
    historical["selection"]["rounds"][0]["comparisons"][0]["combined_score"] = .6
    with pytest.raises(HistoricalScoreConflict):
        import_historical_scores(historical)


def test_labels_not_imported_or_used_and_source_cannot_override_literal(historical):
    first = import_historical_scores(historical)
    historical["correct_answer"] = "GOLD_SENTINEL"
    historical["metadata"] = {"label": "another private evaluation label"}
    second = import_historical_scores(historical)
    assert first == second
    assert "GOLD_SENTINEL" not in json.dumps(second)
    third = import_historical_scores(historical, provenance={"origin": "online", "score": -99,
                                                           "json_pointer": "fabricated"})
    observation = third["records"][0]["observations"][0]
    assert observation["origin"] == "historical_literal"
    assert observation["score"] == .1
    assert observation["json_pointer"] == "/search/activations/0/P"


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), True, "0.1", -.1, 1.1])
def test_invalid_literal_rejected(historical, value):
    historical["search"]["activations"][0]["P"] = value
    with pytest.raises(DiagnosticImportError):
        import_historical_scores(historical)


def test_missing_literal_not_reconstructed(historical):
    del historical["search"]["activations"][0]["Pe"]
    with pytest.raises(DiagnosticImportError, match="malformed"):
        import_historical_scores(historical)


def test_bad_marginal_rejected(historical):
    historical["selection"]["rounds"][1]["comparisons"][0]["marginal"] = .2
    with pytest.raises(DiagnosticImportError, match="marginal"):
        import_historical_scores(historical)


def test_cases_enumerate_28_and_three_distinct_empty_queries():
    rows = [enumerate_case_subsets(case) for case in DEFAULT_DIAGNOSTIC_CASES]
    assert list(map(len, rows)) == [8, 16, 4]
    assert sum(map(len, rows)) == 28
    assert len({row[0]["question_id"] for row in rows}) == 3
    assert all(row[0]["ids"] == [] for row in rows)
    assert [ids.rsplit(":", 1)[1] for ids in case_universe(DEFAULT_DIAGNOSTIC_CASES[1])] == [
        "m00005", "m00006", "m00008", "m00027"]


def test_bad_case_duplicate_or_cross_question_rejected():
    with pytest.raises(DiagnosticImportError, match="duplicate"):
        case_universe({"universe_ids": ["a", "a"]})
    with pytest.raises(DiagnosticImportError, match="another question"):
        case_universe({"question_id": "q", "universe_ids": ["different:m00001"]})


def test_true_bundle_union_not_intersection():
    case = {"universe_ids": ["a", "b"]}
    values = score_view({(): 0, ("a",): .5, ("b",): .6, ("a", "b"): .8})
    result = analyze_reachability(case, [["a", "outside"], ["b"]], values, feasibility=lambda _: True)
    rows = {tuple(row["ids"]): row for row in result["subsets"]}
    assert result["eligible_bundle_ids"] == [["b"]]
    assert rows[("a",)]["constructible"] is False
    assert rows[("a", "b")]["positive_path_reachable"] is False


def test_constructible_but_not_positive_and_zero_is_not_positive():
    values = score_view({(): .5, ("a",): .5, ("b",): .4, ("a", "b"): .3})
    result = analyze_reachability({"universe_ids": ["a", "b"]}, [["a"], ["b"]],
                                  values, feasibility=lambda _: True)
    rows = {tuple(row["ids"]): row for row in result["subsets"]}
    assert rows[("a", "b")]["constructible"] is True
    assert rows[("a",)]["positive_path_reachable"] is False
    assert rows[("a", "b")]["positive_path_reachable"] is False


def test_missing_score_edge_is_unknown_not_false():
    result = analyze_reachability({"universe_ids": ["a", "b"]}, [["a"], ["b"]],
                                  score_view({(): 0, ("a",): .5, ("b",): .4}),
                                  feasibility=lambda _: True)
    row = next(row for row in result["subsets"] if row["ids"] == ["a", "b"])
    assert row["positive_path_reachable"] is None
    assert row["optimistic_positive_path"]
    assert result["unknown_score_edge_count"] > 0


def test_unknown_feasibility_is_unknown_not_assumed_fit():
    result = analyze_reachability({"universe_ids": ["a"]}, [["a"]],
                                  score_view({(): 0, ("a",): .5}))
    row = result["subsets"][1]
    assert row["constructible"] is True
    assert row["feasible_constructible"] is None
    assert row["positive_path_reachable"] is None


def test_explicit_capacity_blocks_positive_path():
    result = analyze_reachability({"universe_ids": ["a"]}, [["a"]],
                                  score_view({(): 0, ("a",): .5}), feasibility=lambda _: False)
    assert result["subsets"][1]["positive_path_reachable"] is False


def test_positive_path_exists_but_greedy_does_not_follow_it(historical):
    imported = import_historical_scores(historical)
    reach = analyze_reachability({"universe_ids": ["a", "b"]}, historical["search"]["bundles"],
                                imported, feasibility=lambda _: True)
    target = reach["subsets"][-1]
    assert target["positive_path_reachable"] is True  # empty -> b (.4) -> ab (.45)
    replay = replay_selector(historical, imported)
    assert replay["result"]["selected_ids"] == ["a"]
    assert replay["historical_match"] is True


def test_replay_real_selector_and_unique_accounting(historical):
    imported = import_historical_scores(historical)
    result = replay_selector(historical, imported, max_selection_sets=0)
    assert result["status"] == "complete"
    assert result["historical_match"] is True
    assert result["result"]["initial_scored_sets"] == 4
    assert result["result"]["scored_sets"] == 0
    assert result["network_calls"] == 0
    assert all(event["new_unique_sets"] == 0 for event in result["score_events"])


def test_budget_exhaustion_never_commits_partial_round(historical):
    imported = import_historical_scores(historical)
    historical["selection"]["initial_scored_sets"] = 0
    result = replay_selector(historical, imported, initial_seen=[], max_selection_sets=2)
    assert result["status"] == "resource_stopped"
    assert result["reason"] == "score_budget_exhausted"
    assert result["result"]["selected_ids"] == []
    assert result["result"]["rounds"][0]["complete"] is False
    assert result["result"]["scored_sets"] == 0


def test_missing_full_round_score_no_online_fallback(historical):
    imported = import_historical_scores(historical)
    imported["records"] = [row for row in imported["records"] if row["ids"] != ["b"]]
    result = replay_selector(historical, imported)
    assert result["status"] == "incomplete"
    assert result["reason"] == "incomplete_score_coverage"
    assert result["missing_ids"] == [["b"]]
    assert result["result"]["selected_ids"] == []
    assert result["score_events"] == []


def test_missing_initial_charged_identities_are_explicit(historical):
    imported = import_historical_scores(historical)
    imported["search_seen_ids"] = []
    result = replay_selector(historical, imported)
    assert result["reason"] == "initial_charged_identity_coverage"
    assert result["historical_match"] is None


def test_unknown_feasibility_stops_replay(historical):
    imported = import_historical_scores(historical)
    imported["historical_feasibility"] = []
    result = replay_selector(historical, imported)
    assert result["reason"] == "unknown_input_feasibility"
    assert result["result"]["selected_ids"] == []


def test_restricted_does_not_keep_outside_bundle(historical):
    imported = import_historical_scores(historical)
    historical["search"]["bundles"].append({"memory_ids": ["a", "outside"]})
    result = replay_selector(historical, imported, scope="restricted_universe",
                             case={"universe_ids": ["a", "b"]})
    assert result["original_bundle_count"] == 3
    assert result["active_bundle_count"] == 2
    assert result["historical_match"] is None


def test_restricted_can_explicitly_use_fresh_budget(historical):
    imported = import_historical_scores(historical)
    result = replay_selector(historical, imported, scope="restricted_universe",
                             case={"universe_ids": ["a", "b"]},
                             initial_seen=[], max_selection_sets=2)
    assert result["budget_initialization"] == "explicit_seen_ids"
    assert result["status"] == "resource_stopped"
    assert result["result"]["selected_ids"] == []


def test_recorded_scorer_checks_all_missing_before_charging():
    scorer = RecordedSetScorer({(): 0, ("a",): .5})
    with pytest.raises(MissingDiagnosticScores):
        scorer.score_sets([[], ["a"], ["missing"]])
    assert scorer.scored_sets == 0


def test_tar_hash_and_read_only_directory(historical, tmp_path):
    packed = tar_bytes([("candidate_pool/task.json", historical)])
    path = tmp_path / "case.tgz"
    path.write_bytes(packed)
    sha = hashlib.sha256(packed).hexdigest()
    result = load_diagnostic_archive(path, expected_sha256=sha)
    assert result["source_sha256"] == sha
    assert result["artifacts"][0]["artifact"] == historical
    assert path.read_bytes() == packed
    with pytest.raises(DiagnosticImportError, match="SHA-256 mismatch"):
        load_diagnostic_archive(path, expected_sha256="0" * 64)
    directory = tmp_path / "raw"
    directory.mkdir()
    source = directory / "task.json"
    source.write_text(json.dumps(historical))
    first = load_diagnostic_archive(directory)
    second = load_diagnostic_archive(directory, expected_sha256=first["source_sha256"])
    assert first == second
    assert list(directory.iterdir()) == [source]


@pytest.mark.parametrize("raw", [b'{"search":', b'{"search":{},"search":{}}', b'{"value":NaN}'])
def test_truncated_or_ambiguous_json_rejected(tmp_path, raw):
    path = tmp_path / "broken.json"
    path.write_bytes(raw)
    with pytest.raises(DiagnosticImportError):
        load_diagnostic_archive(path)


def test_truncated_gzip_trailer_rejected(historical, tmp_path):
    path = tmp_path / "truncated.tgz"
    path.write_bytes(tar_bytes([("candidate_pool/task.json", historical)])[:-4])
    with pytest.raises(DiagnosticImportError, match="truncated"):
        load_diagnostic_archive(path)


@pytest.mark.parametrize("name", ["../candidate_pool/task.json", "/candidate_pool/task.json"])
def test_unsafe_tar_names_rejected(historical, tmp_path, name):
    path = tmp_path / "unsafe.tgz"
    path.write_bytes(tar_bytes([(name, historical)]))
    with pytest.raises(DiagnosticImportError, match="unsafe"):
        load_diagnostic_archive(path)


def test_duplicate_tar_members_rejected(historical, tmp_path):
    path = tmp_path / "duplicate.tgz"
    path.write_bytes(tar_bytes([("candidate_pool/task.json", historical)] * 2))
    with pytest.raises(DiagnosticImportError, match="duplicate"):
        load_diagnostic_archive(path)


def test_tar_symlink_rejected(tmp_path):
    path = tmp_path / "link.tgz"
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo("candidate_pool/link.json")
        member.type, member.linkname = tarfile.SYMTYPE, "/secret"
        archive.addfile(member)
    with pytest.raises(DiagnosticImportError, match="links"):
        load_diagnostic_archive(path)


def test_member_limit_enforced(historical, tmp_path):
    path = tmp_path / "large.tgz"
    path.write_bytes(tar_bytes([("candidate_pool/task.json", historical)]))
    with pytest.raises(DiagnosticImportError, match="size limit"):
        load_diagnostic_archive(path, max_member_bytes=10)


def test_synthetic_28_known_24_missing_4_end_to_end(tmp_path):
    members = []
    missing_by_case = {"painting": {(11, 39)}, "music": {(5, 6, 27), (5, 8, 27), (5, 6, 8, 27)},
                       "book_club": set()}
    for case in DEFAULT_DIAGNOSTIC_CASES:
        comparisons = []
        for row in enumerate_case_subsets(case):
            ids = row["ids"]
            indices = tuple(int(mid.rsplit("m", 1)[1]) for mid in ids)
            if not ids or indices in missing_by_case[case["case_id"]]:
                continue
            comparisons.append(comparison([], ids, .1, .1))
        artifact = {"task_id": case["task_id"], "method_id": "activation",
                    "search": {"activations": [], "bundles": [{"memory_ids": [mid]}
                                                              for mid in case_universe(case)]},
                    "selection": {"selected_ids": [], "initial_scored_sets": 0,
                                  "final_scored_sets": 0, "stop": {"reason": "no_positive_marginal"},
                                  "rounds": [{"current_ids": [], "accepted_bundle_ids": None,
                                              "selected_ids_after": [], "comparisons": comparisons}]}}
        members.append((f"candidate_pool/{case['task_id']}.json", artifact))
    path = tmp_path / "synthetic28.tgz"
    path.write_bytes(tar_bytes(members))
    result = audit_diagnostic_cases(str(path))
    assert (result["subset_count"], result["historical_score_count"], result["missing_score_count"]) == (28, 24, 4)
    assert [row["historical_score_count"] for row in result["cases"]] == [7, 13, 4]
    for row in result["cases"]:
        indices = {tuple(int(mid.rsplit("m", 1)[1]) for mid in ids) for ids in row["missing_ids"]}
        assert indices == missing_by_case[row["case_id"]]
    assert result["eligible_for_benchmark"] is False
    json.dumps(result, allow_nan=False)
    completed = subprocess.run(
        [sys.executable, "-m", "bridgetree.dependency_diagnostics", str(path),
         "--expected-sha256", hashlib.sha256(path.read_bytes()).hexdigest()],
        check=True, capture_output=True, text=True,
    )
    assert json.loads(completed.stdout) == result
