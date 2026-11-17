"""Invented-source repair diagnostics, without external model or website calls."""
from copy import deepcopy
import json

from test_webwalker_reading import observation, read, response, web_fixture


def test_actual_repair_wire_explains_source_free_draft_and_preserves_its_identity():
    draft = observation('missing-original', [], stance='unknown', value=None,
                        reason='The activity date needs an original-source review.')
    draft['value'] = None
    initial = response(draft)
    repaired = response({**draft, 'source_ids': ['s1']})
    reader, engine, state, calls = web_fixture(
        lambda index, data: initial if index == 1 else repaired,
        max_repairs_per_request=1)

    read(reader)

    assert len(calls.requests) == 2
    repair = calls.requests[1]['data']
    diagnostic = repair['web_reading_protocol_diagnostics']
    assert diagnostic['read_only'] is True
    assert diagnostic['grants_review_authority'] is False
    error = diagnostic['errors'][0]
    assert error['variable'] == 'history'
    assert error['observation_id'] == 'missing-original'
    assert error['path'].endswith('.slot.observations[0].source_ids')
    assert 'non-empty' in error['error']
    captured = [entry for entry in repair['repair_scope']['failed']
                if entry.get('id') == 'missing-original']
    assert captured and captured[0]['observation'] == draft
    assert json.loads(engine.reasoner.requests[0]['raw_output']) == initial
    assert json.loads(engine.reasoner.requests[1]['raw_output']) == repaired
    assert engine.ledger.used == {'llm': 2, 'json_repairs': 1}
    assert not state.valid()[0] and state.pending == {'history'}
    assert not reader.failed_batch_reviews
    assert reader.evidence_obligations


def test_diagnostic_does_not_accept_repeated_invalid_draft_or_clear_its_failure():
    draft = observation('still-source-free', [], stance='unknown', value=None)
    draft['value'] = None
    original = response(draft)
    reader, engine, state, calls = web_fixture(
        lambda index, data: original, max_repairs_per_request=1)

    read(reader)

    assert len(calls.requests) == 2
    assert calls.requests[1]['data']['web_reading_protocol_diagnostics']['errors']
    assert engine.ledger.used == {'llm': 2, 'json_repairs': 1}
    assert state.pending == {'history'} and not state.valid()[0]
    assert any(entry.get('id') == 'still-source-free'
               for record in reader.failed_batch_reviews.values()
               for entry in record['failed'])
    assert all(json.loads(request['raw_output']) == original
               for request in engine.reasoner.requests)


def test_only_current_failed_slot_gets_wire_diagnostic_without_mutating_state():
    reader, engine, state, calls = web_fixture()
    data = reader._payload(engine.steps[0], 'Read invented source.', ['history'], ['s1'])
    draft = observation('no-citation', [], stance='unknown', value=None)
    draft['value'] = None
    malformed = response(draft)['slots'][0]
    data['repair_scope'] = {'failed': [
        {'variable': 'history', 'id': '*', 'feedback': 'Malformed slot',
         'observation': None, 'slot': malformed}], 'attempt': 1,
        'previous_response_identity': '0' * 64}
    before = deepcopy(data)
    before_budget = deepcopy(engine.ledger.public_dict())
    before_state = deepcopy(state.public_dict())

    wires = reader._wire_candidates(data)

    assert data == before and engine.ledger.public_dict() == before_budget
    assert state.public_dict() == before_state and not calls.requests
    for wire, _ in wires:
        errors = wire['web_reading_protocol_diagnostics']['errors']
        assert len(errors) == 1 and errors[0]['observation_id'] == 'no-citation'
        assert wire['repair_scope'] == before['repair_scope']
        assert not wire.get('web_review_checklist', {}).get('offered_frozen_observations')

    ordinary = deepcopy(before)
    ordinary.pop('repair_scope')
    assert all('web_reading_protocol_diagnostics' not in wire
               for wire, _ in reader._wire_candidates(ordinary))
    audit = {**before, 'audit_instruction': 'Audit the supplied invented evidence.'}
    assert all('web_reading_protocol_diagnostics' not in wire
               for wire, _ in reader._wire_candidates(audit))
