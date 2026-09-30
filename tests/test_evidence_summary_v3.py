"""The operator's summary command must show v3 states, including empty cohorts."""

import json

import pytest


@pytest.mark.parametrize("state", ["pending", "legacy_unknown", "raw_unassessed"])
def test_terminal_summary_renders_both_v3_cohort_tables_and_zero_or_unknown(tmp_path, state):
    from test_evidence_bridge_operations import load_script

    module = load_script("summarize_evidence_bridge")
    task = {"task_id": "test-task", "method_id": "evidence_bridge"}
    (tmp_path / "planned_tasks.jsonl").write_text(json.dumps(task) + "\n")
    (tmp_path / "outcomes").mkdir()
    if state != "pending":
        diagnostics = {} if state == "legacy_unknown" else {
            "evidence_bridge_summary": {"reliability": {
                "reliability_status": "coverage_unassessed", "evidence_state": "raw_only",
                "coverage_validation_complete": False, "unassessed_requirement_count": 1,
            }},
        }
        (tmp_path / "outcomes/test-task.json").write_text(json.dumps({
            "task": task, "status": "success", "correct": False, "diagnostics": diagnostics,
            "costs": {"evidence_calls": 5},
        }))
    text = module.markdown(module.summarize(tmp_path))
    evidence = text.split("## 证据方法原文使用状态", 1)[1].split("## 证据方法覆盖验证状态", 1)[0]
    coverage = text.split("## 证据方法覆盖验证状态", 1)[1].split("## evidence_bridge 模块与成本", 1)[0]
    assert "| empty | 0 | 0 | 未产生 |" in evidence
    assert "| complete | 0 | 0 | 未产生 |" in coverage
    if state == "legacy_unknown":
        assert "| unknown | 1 | 0 | 0.00% |" in evidence
        assert "| unknown | 1 | 0 | 0.00% |" in coverage
    elif state == "raw_unassessed":
        assert "| raw_only | 1 | 0 | 0.00% |" in evidence
        assert "| unassessed | 1 | 0 | 0.00% |" in coverage
    else:
        assert "| unknown | 0 | 0 | 未产生 |" in evidence
        assert "| unknown | 0 | 0 | 未产生 |" in coverage
    assert "不可相加" in text
    assert "协议通过不等于证据语义充分或答案正确" in text
