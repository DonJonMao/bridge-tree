"""Only unambiguous complete objects reach the evidence semantic validators."""

import json
from dataclasses import replace

import pytest

from bridgetree.dependency_config import load_dependency_config
from bridgetree.evidence_config import EvidenceSelectionConfig
from bridgetree.evidence_protocol import EvidenceJSONError, evidence_response_schema, parse_evidence_object


@pytest.mark.parametrize("wrapper", [
    "{}", " \t\n{}\r\n ", "\ufeff{}", " \ufeff {} ",
    "```json\n{}\n```", "```JSON \r\n{}\r\n```", "```\n{}\n```",
    "Here is the JSON result:\n{}", "{}\nThis is the complete result.", "结果：{} 已完成。",
])
def test_complete_objects_with_controlled_wrappers(wrapper):
    data = {"text": "I changed my mind. 否定；🫖", "nested": [{"source": 1}], "number": 1.25}
    assert parse_evidence_object(wrapper.format(json.dumps(data, ensure_ascii=False))) == data


def test_json_string_content_is_never_treated_as_wrapper_syntax():
    data = {"text": '```json\n{}[]\n```; quote="yes"; escaped newline=\n', "literal": "NaN Infinity"}
    wire = json.dumps(data)
    assert parse_evidence_object(wire) == data
    assert parse_evidence_object(f"```json\n{wire}\n```") == data


@pytest.mark.parametrize("raw", [
    "", " ", "null", "false", "42", '"text"', "[]", '[{"a":1}]',
    '"{}"', '"a {} b"', '"quoted prefix" {}', '{} "quoted suffix"',
    "{} {}", "{} explanation {}", '{} [1]', '[1] {}', "}{}", "{}]", "{} {", "[{}",
    "Here is {broken: true, nested: {}}", '{"outer": {}}}', '{"outer": {"ok": 1}',
    "null {}", "{} true", "1 {}", "{} -2", "(){}", "{};", "{}:", "({})", "{},",
    "NaN {}", "{} NaN", "Infinity {}", "{} -Infinity",
    '{"n":NaN}', '{"n":Infinity}', '{"n":-Infinity}', '{"n":1e999}', '{"n":-1e999}',
    '{"a":1,"a":2}', '{"nested":{"a":1,"a":2}}',
    '```json\n{}', '{}\n```', '```json\n{}\n```\n```json\n{}\n```',
    'Result:\n```json\n{}\n```', '```javascript\n{}\n```',
    '{"x": "unterminated}', '{"x":1,}',
])
def test_rejects_incomplete_ambiguous_or_nonfinite_objects(raw):
    with pytest.raises(EvidenceJSONError):
        parse_evidence_object(raw)


@pytest.mark.parametrize("raw", [None, 1, True, [], {}, b"{}"])
def test_nontext_responses_are_not_coerced(raw):
    with pytest.raises(EvidenceJSONError, match="response must be text"):
        parse_evidence_object(raw)


def test_extreme_model_output_gets_a_recoverable_parse_error():
    with pytest.raises(EvidenceJSONError, match="parser limit"):
        parse_evidence_object('{"nested":' + "[" * 1500 + "0" + "]" * 1500 + "}")


@pytest.mark.parametrize("operation", ["evidence_plan", "evidence_map", "evidence_select"])
def test_wire_schemas_are_closed_required_objects_and_repair_uses_same_contract(operation):
    schema = evidence_response_schema(operation)
    assert schema == evidence_response_schema(operation + "_repair")

    def walk(node):
        if node["type"] == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
            for child in node["properties"].values():
                walk(child)
        elif node["type"] == "array":
            walk(node["items"])
        else:
            assert node["type"] in {"string", "boolean"}

    walk(schema)
    # Callers can construct wire copies without contaminating future schemas.
    schema["properties"].clear()
    assert evidence_response_schema(operation)["properties"]


def test_mapping_schema_uses_source_ids_and_selection_uses_evidence_ids():
    map_unit = evidence_response_schema("evidence_map")["properties"]["units"]["items"]
    assessment = map_unit["properties"]["assessments"]["items"]["properties"]
    assert "span_ids" in assessment
    assert "quote" not in assessment
    assert "start" not in assessment
    assert assessment["relation"]["enum"] == ["support", "contradiction", "partial"]
    coverage = evidence_response_schema("evidence_select")["properties"]["coverage"]["items"]["properties"]
    assert coverage["status"]["enum"] == ["covered", "partial", "missing", "ambiguous"]
    assert "evidence_ids" in coverage


@pytest.mark.parametrize("operation", [
    "generation", "evidence_planner", "evidence_mapping", "evidence_selection", "evidence_plan_bad", None, [],
])
def test_unknown_schema_operation_is_rejected(operation):
    with pytest.raises(ValueError, match="unknown evidence operation"):
        evidence_response_schema(operation)


@pytest.mark.parametrize("field", [
    name for name in EvidenceSelectionConfig.__dataclass_fields__ if name != "response_format"
])
@pytest.mark.parametrize("bad_value", [True, 1.5, float("nan"), -1, "2"])
def test_evidence_numeric_settings_are_strict(field, bad_value):
    with pytest.raises(ValueError):
        EvidenceSelectionConfig(**{field: bad_value})


@pytest.mark.parametrize("mode", [None, True, [], {}, "auto", "JSON_OBJECT"])
def test_evidence_protocol_mode_is_explicit_and_strict(mode):
    with pytest.raises(ValueError):
        EvidenceSelectionConfig(response_format=mode)


def test_evidence_budget_boundaries_and_protocol_affect_frozen_identity():
    config = EvidenceSelectionConfig(map_batch_token_budget=1024, input_token_budget=1024, selection_input_margin=0)
    assert config.map_batch_token_budget == config.input_token_budget
    with pytest.raises(ValueError, match="map_batch_token_budget"):
        replace(config, map_batch_token_budget=1025)
    with pytest.raises(ValueError, match="selection_input_margin"):
        replace(config, selection_input_margin=1024)
    run = load_dependency_config("configs/evidence_bridge.yaml")
    changed = replace(run, evidence_bridge=replace(
        run.evidence_bridge, selection=replace(run.evidence_bridge.selection, response_format="json_object"),
    ))
    assert changed.config_hash() != run.config_hash()


def test_selection_can_repair_using_calls_reserved_before_mapping():
    from test_evidence_selection import ScriptedBackend, make_selector, records

    def select_response(payload, attempt):
        return "invalid JSON" if attempt == 1 else ScriptedBackend.select_all(payload)

    backend = ScriptedBackend(select_response=select_response)
    settings = replace(EvidenceSelectionConfig(), max_llm_calls=5, max_selection_revisions=2)
    selector = make_selector(backend, settings)
    bank = records("I learned that jasmine tea is my favorite.")
    result = selector.select("Which tea do I prefer?", bank, list(bank))
    assert result.selected_ids == tuple(bank)
    assert result.costs["evidence_llm_calls"] == 4
    assert result.costs["evidence_json_repairs"] == 1
    assert [operation for operation, _, _ in backend.requests] == [
        "evidence_plan", "evidence_map", "evidence_select", "evidence_select_repair",
    ]
