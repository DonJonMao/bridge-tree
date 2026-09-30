"""Small exported-run fixtures; no dependency on private multi-GB server logs."""

from __future__ import annotations

import hashlib
import json
import runpy
import urllib.request
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridgetree.clients import build_context_plan
from bridgetree.evidence_config import EvidenceSelectionConfig
from bridgetree.types import Memory

ROOT = Path(__file__).resolve().parents[1]


def module():
    return SimpleNamespace(**runpy.run_path(str(ROOT / "scripts/replay_evidence_v3.py")))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def requirement(identifier):
    return {"id": identifier, "description": "earlier personal preference", "necessary": True, "time_scope": "past"}


def fact(identifier="ev1", requirement_id="r1", memory_id="m1", **updates):
    return {"evidence_id": identifier, "requirement_id": requirement_id, "memory_id": memory_id,
            "claim": "PRIVATE_SOURCE_CLAIM", "kind": "inference", "relation": "support", "time_scope": "past",
            "role": "user", "observed_order": 1.0, "time_metadata": {},
            "fragments": [{"span_id": "s1", "quote": "PRIVATE_MEMORY_TEXT", "role": "user"}], **updates}


def fixture_run(tmp_path):
    run = tmp_path / "export/run"
    config = {"evidence_bridge": {"selection": asdict(EvidenceSelectionConfig())},
              "models": {"generator": {"context_token_budget": 8192, "api_key": "DO_NOT_COPY_CREDENTIAL"}}}
    write(run / "resolved_config.json", {"config": config})
    (run / "modules").mkdir()
    (run / "modules/context.jsonl").write_text("")
    return run


def add_case(run, question, evidence, *, error=True):
    task = {"task_id": question + "-eb", "question_id": question,
            "persona_id": "1", "method_id": "evidence_bridge"}
    outcome = {"task": task, "status": "error" if error else "success", "selected_ids": [],
               "error_type": "EvidenceValidationError" if error else None,
               "diagnostics": {"evidence_bridge_summary": {"reliability": {"reliability_status": "normal"}}}}
    write(run / "outcomes" / f"{task['task_id']}.json", outcome)
    write(run / "candidate_pool" / f"{task['task_id']}.json", {"task_id": task["task_id"],
                                                           "evidence_selection": evidence})
    return outcome


def add_empty_mapping_normal(run):
    memory = Memory("m1", "PRIVATE_MEMORY_TEXT", 1.0, "q1:1", {"source_segments": [
        {"role": "user", "start": 0, "end": 19, "source_message_indices": [1]}]})
    query = "PRIVATE_QUERY"
    plan = build_context_plan(query, [memory], '["(a) OPTION_SENTINEL", "(b) Other"]',
                              token_budget=8192, max_tokens=512)
    evidence = {"requirements": [requirement("r1")], "mappings": [], "candidate_ids": ["m1"],
                "exposures": [{"status": "mapped"}], "fully_mapped_ids": ["m1"],
                "requests": [{"operation": "evidence_plan", "messages": [
                    {"role": "system", "content": "plan"},
                    {"role": "user", "content": json.dumps({"query": query})}]}]}
    add_case(run, "q1", evidence, error=False)
    write(run / "visible_memories/q1-visible.json", {
        "persona_id": "1", "question_id": "q1", "visible_memories": [asdict(memory)]})
    write(run / "outcomes/q1-dense.json", {"task": {"task_id": "q1-dense", "question_id": "q1",
          "persona_id": "1", "method_id": "dense"}, "status": "success", "selected_ids": ["m1"]})
    (run / "modules/context.jsonl").write_text(json.dumps({
        "task_id": "q1-dense", "method_id": "dense", "context_plan": plan.public_dict()}) + "\n")


def add_selection_error(run, question, *, wrong_requirement=False, unrelated_facts=0):
    facts = [fact()]
    if wrong_requirement or unrelated_facts:
        facts += [fact("ev2", "r2", "m2")]
    for index in range(unrelated_facts):
        facts.append(fact(f"extra{index}", "r2", "m2", claim="Unrelated old fact. " * 30))
    counts, ledger = {}, []
    for value in facts:
        req = value["requirement_id"]
        counts[req] = counts.get(req, 0) + 1
        ledger.append({**value, "evidence_id": f"{req}_e{counts[req]}"})
    requirements = [requirement("r1"), requirement("r2")]
    payload = {"query": "PRIVATE_QUERY", "requirements": requirements, "candidate_ids": ["m1", "m2"],
               "evidence_ledger": ledger, "candidate_costs": [], "empty_context": {"budget": 8192},
               "mapping_incomplete": False, "omitted_evidence_by_requirement": {"r1": 0, "r2": 0}}
    raw = {"selected_ids": ["m2"] if wrong_requirement else ["m1"], "conflicts": [], "reason": "PRIVATE_REASON",
           "coverage": [{"requirement_id": "r1", "status": "covered", "kind": "explicit",
                         "evidence_ids": ["r2_e1"] if wrong_requirement else ["r1_e1"],
                         "explanation": "PRIVATE_EXPLANATION"},
                        {"requirement_id": "r2", "status": "missing", "kind": "explicit",
                         "evidence_ids": [], "explanation": "No evidence"}]}
    request = {"call_index": 1, "operation": "evidence_select", "response_format": "plain",
               "messages": [{"role": "system", "content": "Recorded old selection prompt"},
                            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                                                      separators=(",", ":"))}],
               "raw_response": json.dumps(raw), "validation_status": "invalid", "local_repair_index": 0,
               "validation_error": "coverage r1: " + ("different requirement" if wrong_requirement
                                                       else "inferential mappings cannot become explicit coverage")}
    evidence = {"requirements": requirements, "mappings": facts, "exposures": [],
                "candidate_ids": ["m1", "m2"], "fully_mapped_ids": ["m1", "m2"], "requests": [request]}
    add_case(run, question, evidence)
    return evidence


def test_export_replay_preserves_sources_and_validates_without_models(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("replay contacted a service")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    run = fixture_run(tmp_path)
    add_empty_mapping_normal(run)
    add_selection_error(run, "q2")
    add_selection_error(run, "q3", wrong_requirement=True)
    original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in run.rglob("*") if p.is_file()}
    result = module().replay(run, tmp_path / "replay")
    assert result["summary"]["normal_tasks_all_baseline_visible"] == 1
    assert result["summary"]["raw_text_and_roles_exact"] is True
    assert result["summary"]["old_error_tasks_final_recorded_response_now_valid"] == 1
    assert result["summary"]["remaining_error_categories"] == {"wrong_requirement": 1}
    assert result["summary"]["valid_normalized_coverage_row_observations"] == 1
    assert result["new_model_calls"] == result["new_answers"] == 0
    assert result["skipped"] == []
    assert original == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in original}
    encoded = json.dumps(result)
    for value in ("PRIVATE_MEMORY_TEXT", "PRIVATE_SOURCE_CLAIM", "PRIVATE_QUERY", "PRIVATE_REASON",
                  "PRIVATE_EXPLANATION", "DO_NOT_COPY_CREDENTIAL", "OPTION_SENTINEL"):
        assert value not in encoded


def test_compact_repair_replays_legacy_budget_pressure_without_changing_citations(tmp_path):
    run = fixture_run(tmp_path)
    evidence = add_selection_error(run, "q2", unrelated_facts=50)
    tool = module()
    settings = EvidenceSelectionConfig()
    selector = tool.selector_for(evidence, settings)
    request = evidence["requests"][0]
    tokens = selector._tokens(request["messages"], "evidence_select")
    config = json.loads((run / "resolved_config.json").read_text())
    config["config"]["evidence_bridge"]["selection"]["input_token_budget"] = tokens + 30
    write(run / "resolved_config.json", config)
    result = tool.replay(run, tmp_path / "replay")
    repair = result["cases"][0]["response_replays"][0]["repair_budget"]
    assert repair["legacy_repair_over_budget"] is True
    assert repair["compact_repair_within_budget"] is True
    assert repair["selected_ids"] == ["m1"]
    assert repair["pending_requirement_ids"] == ["r1"]
    assert repair["evidence_records_after"] == 1
    assert result["summary"]["legacy_overflows_compact_within_budget"] == 1


def test_replay_reports_missing_artifacts_and_refuses_input_or_existing_output(tmp_path):
    run = fixture_run(tmp_path)
    add_empty_mapping_normal(run)
    next((run / "visible_memories").glob("*.json")).unlink()
    tool = module()
    result = tool.replay(run, tmp_path / "replay")
    assert result["summary"]["skipped_tasks"] == 1
    assert result["summary"]["raw_text_and_roles_exact"] is None
    assert result["skipped"][0]["task_id"] == "q1-eb"
    with pytest.raises(ValueError, match="fresh replay"):
        tool.replay(run, tmp_path / "replay")
    with pytest.raises(ValueError, match="outside"):
        tool.replay(run, run / "new-output")
