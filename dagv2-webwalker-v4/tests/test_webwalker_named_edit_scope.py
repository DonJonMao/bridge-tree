"""Offline scope/validator agreement using invented sources, no services."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import jsonschema
import pytest

from dagbt.joint_reading import JointReader
from test_webwalker_reading import observation, read, response, web_fixture, expand_wire_data

PREVIEW = Path(__file__).resolve().parents[1] / 'dagbt/webwalker_reading.py'
spec = importlib.util.spec_from_file_location('dagbt._named_scope_preview', PREVIEW)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Reader = module.WebJointReader


def fixture(respond=None, **settings):
    _, engine, state, calls = web_fixture(respond, **settings)
    return Reader(engine, state), engine, state, calls


def request(reader, engine, failed):
    data = reader._payload(engine.steps[0], 'Current ordinary question', ['history'], ['s1'])
    data['repair_scope'] = {'failed': failed, 'attempt': 1, 'previous_response_identity': '0' * 64}
    return data


def validator(data):
    schema = Reader._schema(data)
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def named(identifier='required'):
    return {'variable': 'history', 'id': identifier, 'observation': observation(identifier)}


def test_named_schema_rejects_extra_id_that_common_runtime_rejects_and_retains():
    bad = observation('required', ['unoffered-source'])
    def respond(index, data):
        if index == 1:
            return response(bad)
        legal = response(observation('required'), observation('unrequested-support'))
        assert list(validator(data).iter_errors(legal))
        assert data['web_repair_edit_scope']['slots'][0]['writable_observation_ids'] == ['required']
        return legal
    reader, engine, state, calls = fixture(respond, max_repairs_per_request=1)
    read(reader)
    assert len(calls.requests) == 2 and engine.ledger.used['json_repairs'] == 1
    assert any('Repair invented an unrequested observation' in item['error']
               for item in reader.batches[-1]['failed_slots'])
    assert any(failure['id'] == 'unrequested-support'
               for record in reader.failed_batch_reviews.values() for failure in record['failed'])
    assert state.pending == {'history'}


def test_named_counter_can_be_corrected_without_new_support_or_marker_authority():
    def respond(index, data):
        if index == 1:
            return response(observation('old'))
        route = data['known_observations'][0]['id']
        counter = observation('counter', ['s2'], stance='contradiction', retract_ids=[route])
        counter['value'] = ['painting'] if index == 2 else None
        if index == 3:
            validator(data).validate(response(counter))
            assert list(validator(data).iter_errors(response(counter, observation('replacement', ['s2']))))
            edit = data['web_repair_edit_scope']['slots'][0]
            assert edit['new_support_requires_later_ordinary_read'] is True
        return response(counter)
    reader, engine, state, calls = fixture(respond, max_repairs_per_request=1)
    read(reader, 'piano', 'same')
    read(reader, 'painting', 'same')
    assert len(calls.requests) == 3 and not reader.failed_batch_reviews
    assert reader.batches[-1]['complete'] and not state.valid()[0]
    assert all(route.get('revoked') for route in state.routes.values())
    assert engine.ledger.limits == {'llm': 24, 'json_repairs': 6}


def test_wildcard_authority_is_per_variable_and_required_named_rows_still_remain():
    reader, engine, _, _ = fixture()
    data = request(reader, engine, [named(), {'variable': 'history', 'id': '*'}])
    data['variables']['other'] = deepcopy(data['variables']['history'])
    data['requested_slots'].append('other')
    data['requested_scopes']['other'] = deepcopy(data['requested_scopes']['history'])
    data['repair_scope']['failed'].append({'variable': 'other', 'id': 'only-other'})
    value = response(observation('required'), observation('new-review'))
    value['slots'].append({**deepcopy(value['slots'][0]), 'variable': 'other',
                           'observations': [observation('only-other')]})
    validator(data).validate(value)
    value['slots'][1]['observations'].append(observation('alien'))
    assert list(validator(data).iter_errors(value))
    value['slots'][1]['observations'].pop()
    value['slots'][0]['observations'] = [observation('new-review')]
    assert list(validator(data).iter_errors(value))
    assert Reader._repair_edit_scope(data)[0]['additional_unique_observation_ids_allowed']
    assert not Reader._repair_edit_scope(data)[1]['additional_unique_observation_ids_allowed']


def test_duplicate_replacement_ids_are_preserved_and_frozen_rows_cannot_return():
    reader, engine, _, _ = fixture()
    first, second = observation('dup~one'), observation('dup~two')
    data = request(reader, engine, [{'variable': 'history', 'id': 'dup',
        'observations': [observation('dup'), observation('dup', value=['painting'])],
        'replacement_observations': [first, second]}])
    validator(data).validate(response(first, second))
    for rows in [[first], [first, second, observation('dup')], [first, second, observation('extra')]]:
        assert list(validator(data).iter_errors(response(*rows)))
    data['repair_scope']['frozen_observation_ids'] = {'history': ['dup~one']}
    validator(data).validate(response(second))
    assert list(validator(data).iter_errors(response(first, second)))
    edit = Reader._repair_edit_scope(data)[0]
    assert edit['writable_observation_ids'] == edit['required_observation_ids'] == ['dup~two']
    assert edit['frozen_observation_ids'] == ['dup~one']


def test_protected_counter_is_lossless_and_core_rejects_reclassification():
    def respond(index, data):
        if index == 1:
            return response(observation('old'))
        route = data['known_observations'][0]['id']
        counter = observation('counter', ['s2'], stance='contradiction', retract_ids=[route])
        counter['value'] = None
        if index == 2:
            value = response(counter)
            value['unexpected_envelope'] = True
            return value
        edit = data['web_repair_edit_scope']['slots'][0]
        protected = next(entry['required_counter_observations'] for entry in data['repair_scope']['failed']
                         if entry.get('required_counter_observations'))
        assert edit['protected_counter_observations'] == protected
        assert edit['protected_counter_observations'] == [counter]
        changed = {**deepcopy(counter), 'stance': 'irrelevant', 'retract_ids': []}
        # This extension changes only ID edit permissions; all protected-counter
        # runtime checks remain authoritative and must reject semantic erasure.
        return response(changed)
    reader, _, state, calls = fixture(respond, max_repairs_per_request=1)
    read(reader, 'piano', 'same')
    read(reader, 'painting', 'same')
    assert len(calls.requests) == 3 and reader.failed_batch_reviews
    assert any('counter' in item['error'].lower() for item in reader.batches[-1]['failed_slots'])
    assert state.valid()[0]['history'] == ['piano'] and state.pending == {'history'}


def test_projection_is_lossless_and_never_reopens_old_failed_marker():
    reader, engine, state, calls = fixture()
    data = request(reader, engine, [named()])
    data['evidence_obligations'] = [{'id': 'pending', 'variable': 'history', 'source_ids': ['s1']}]
    data['failed_batch_reviews'] = [{'id': 'blocked', 'variable': 'history', 'review_allowed': False,
        'source_ids': ['s1'], 'failed': [named()], 'invalid_response': '  exact raw draft\n'}]
    before, facts, ledger = deepcopy(data), deepcopy(state.__dict__), deepcopy(engine.ledger.public_dict())
    wire = expand_wire_data(reader._wire_candidates(data)[0][0])
    for field, value in before.items():
        assert wire[field] == value, field
    assert wire['web_repair_edit_scope']['read_only'] and not wire['web_repair_edit_scope']['grants_review_authority']
    assert data == before and state.__dict__ == facts and engine.ledger.public_dict() == ledger
    assert not calls.requests
    value = response(observation('required'))
    value['slots'][0]['resolved_failed_batch_ids'] = ['blocked']
    assert list(validator(data).iter_errors(value))
    wire['web_repair_edit_scope']['slots'][0]['writable_observation_ids'].append('alien')
    assert data == before


@pytest.mark.parametrize('flag', ['audit_instruction', 'public_output_question', 'terminal_repair'])
def test_terminal_and_audit_schema_and_prompt_are_unchanged(flag):
    reader, engine, _, _ = fixture()
    data = request(reader, engine, [named()]); data[flag] = 'ordinary retained instruction'
    if flag == 'terminal_repair':
        data[flag] = {'expected_value': 'fixture'}
    assert Reader._repair_edit_scope(data) == []
    assert Reader._schema(data) == JointReader._schema(data)
    wire = expand_wire_data(reader._wire_candidates(data)[0][0])
    assert 'web_repair_edit_scope' not in wire


def test_real_duplicate_repair_uses_every_offered_replacement_without_new_ids():
    def respond(index, data):
        if index == 1:
            return response(observation('duplicate', reason='First sourced explanation.'),
                            observation('duplicate', reason='Second sourced explanation.'))
        drafts = [row for entry in data['repair_scope']['failed']
                  for row in entry.get('replacement_observations', [])]
        assert len(drafts) == 2
        validator(data).validate(response(*drafts))
        assert list(validator(data).iter_errors(response(drafts[0])))
        return response(*drafts)
    reader, engine, state, calls = fixture(respond, max_repairs_per_request=1)
    read(reader)
    assert len(calls.requests) == 2 and reader.batches[-1]['complete']
    assert not reader.failed_batch_reviews and state.valid()[0]['history'] == ['piano']
    assert engine.ledger.used['json_repairs'] == 1


def test_real_wildcard_plus_named_repair_still_requires_named_draft():
    def respond(index, data):
        if index == 1:
            value = response(observation('required', ['unoffered-source']))
            value['slots'][0]['unresolved'] = ['Retain a scoped issue.']
            return value
        entries = data['repair_scope']['failed']
        assert {entry['id'] for entry in entries} == {'required', '*'}
        extra = observation('allowed-new-review')
        validator(data).validate(response(observation('required'), extra))
        assert list(validator(data).iter_errors(response(extra)))
        return response(extra)
    reader, _, state, calls = fixture(respond, max_repairs_per_request=1)
    read(reader)
    assert len(calls.requests) == 2
    assert any(failure['id'] == 'required' and 'Required failed observation' in failure['error']
               for failure in reader.batches[-1]['failed_slots'])
    assert state.pending == {'history'} and reader.failed_batch_reviews


def test_projected_fields_and_dynamic_schema_are_in_the_counted_request_wire():
    import json
    counted = []
    def respond(index, data):
        return response(observation('required', ['unoffered-source'])) if index == 1 else response(observation('required'))
    # Character units deliberately over-count real model tokens. Increase only
    # this offline fixture's context so capacity admission cannot mask the wire
    # identity assertion; no production context or repair budget is changed.
    reader, engine, _, calls = fixture(respond, max_repairs_per_request=1,
                                       context_tokens=131072)
    def counter(stage, url, payload):
        size = len(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
        counted.append((deepcopy(payload), size))
        return {'count': size, 'token_count_is_estimate': False,
                'token_estimator_id': 'offline_exact_wire_characters_fixture'}
    calls.count_reasoning_tokens = counter
    read(reader)
    actual = calls.requests[-1]['payload']
    assert 'web_repair_edit_scope' in json.loads(actual['messages'][1]['content'])
    assert 'writable_observation_ids' in actual['messages'][1]['content']
    schema = json.loads(actual['messages'][0]['content'].rsplit(
        '\n\nReturn one complete JSON object matching this schema:\n', 1)[1])
    branch = next(branch['properties']['observations']
                  for branch in schema['properties']['slots']['items']['oneOf']
                  if branch['properties']['variable']['const'] == 'history')
    assert {'properties': {'id': {'enum': ['required']}}} in branch['items']['allOf']
    assert {'contains': {'properties': {'id': {'const': 'required'}},
                         'required': ['id']}} in branch['allOf']
    assert any(payload == actual and count == engine.reasoner.requests[-1]['input_tokens_local']
               for payload, count in counted)
    assert engine.ledger.used['llm'] == 2 and engine.ledger.used['json_repairs'] == 1


def test_plain_wildcard_adds_no_redundant_projection_or_instruction():
    reader, engine, state, calls = fixture()
    data = request(reader, engine, [{'variable': 'history', 'id': '*'}])
    before, facts, ledger = deepcopy(data), deepcopy(state.__dict__), deepcopy(engine.ledger.public_dict())
    assert Reader._repair_edit_scope(data) == []
    wire = expand_wire_data(reader._wire_candidates(data)[0][0])
    assert 'web_repair_edit_scope' not in wire
    assert module.WEB_REPAIR_EDIT_SCOPE_INSTRUCTION not in Reader._system(wire)
    # Ordinary whole-slot edit freedom is already in the base Web schema.
    validator(data).validate(response(observation('new-one'), observation('new-two')))
    for field, value in before.items():
        assert wire[field] == value, field
    assert data == before and state.__dict__ == facts and engine.ledger.public_dict() == ledger
    assert not calls.requests


@pytest.mark.parametrize('restriction', ['named', 'frozen', 'replacement', 'protected_counter'])
def test_wildcard_with_concrete_restriction_retains_complete_projection(restriction):
    reader, engine, _, _ = fixture()
    failed = [{'variable': 'history', 'id': '*'}]
    if restriction == 'named':
        failed.append(named('required'))
    elif restriction == 'replacement':
        failed[0]['replacement_observations'] = [observation('required')]
    elif restriction == 'protected_counter':
        counter = observation('counter', stance='contradiction', retract_ids=['old-route'])
        counter['value'] = None
        failed[0]['required_counter_observations'] = [counter]
    data = request(reader, engine, failed)
    if restriction == 'frozen':
        data['repair_scope']['frozen_observation_ids'] = {'history': ['immutable']}
    edits = Reader._repair_edit_scope(data)
    assert len(edits) == 1 and edits[0]['mode'] == 'whole_slot'
    assert edits[0]['additional_unique_observation_ids_allowed'] is True
    if restriction in {'named', 'replacement'}:
        assert edits[0]['required_observation_ids'] == ['required']
    if restriction == 'replacement':
        assert edits[0]['replaced_duplicate_ids'] == ['*']
    if restriction == 'frozen':
        assert edits[0]['frozen_observation_ids'] == ['immutable']
    if restriction == 'protected_counter':
        assert edits[0]['protected_counter_observations'] == [counter]
    wire = expand_wire_data(reader._wire_candidates(data)[0][0])
    assert wire['web_repair_edit_scope']['slots'] == edits
    assert module.WEB_REPAIR_EDIT_SCOPE_INSTRUCTION in Reader._system(wire)


def test_projection_omits_only_unrestricted_variable():
    reader, engine, _, _ = fixture()
    data = request(reader, engine, [{'variable': 'history', 'id': '*'}])
    data['variables']['other'] = deepcopy(data['variables']['history'])
    data['requested_slots'].append('other')
    data['requested_scopes']['other'] = deepcopy(data['requested_scopes']['history'])
    data['repair_scope']['failed'].append({'variable': 'other', 'id': 'required'})
    edits = Reader._repair_edit_scope(data)
    assert [row['variable'] for row in edits] == ['other']
    assert edits[0]['writable_observation_ids'] == ['required']
    value = response(observation('any-new-id'))
    value['slots'].append({**deepcopy(value['slots'][0]), 'variable': 'other',
                          'observations': [observation('required')]})
    validator(data).validate(value)
    value['slots'][1]['observations'].append(observation('alien'))
    assert list(validator(data).iter_errors(value))
