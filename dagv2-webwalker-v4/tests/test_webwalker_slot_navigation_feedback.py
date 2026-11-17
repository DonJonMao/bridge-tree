"""Independent empty-slot navigation hints survive mixed evidence and repairs.

Only invented originals and scripted responses are used. No model or website
is contacted, and accepted hints never add evidence or review authority.
"""
from copy import deepcopy

import pytest

from dagbt.fact_state import FactState
from dagbt.webwalker_reading import WebJointReader
from test_webwalker_reading import observation, web_fixture


IDENTITY = 'invented-mixed-slot-window'


def empty(variable, direction=None):
    return {'variable': variable, 'observations': [], 'unresolved': [],
            'reading_status': 'no_relevant_evidence',
            'search_gaps': [direction or 'Inspect another observed branch for ' + variable]}


def evidence(variable, row):
    return {'variable': variable, 'observations': [row], 'unresolved': [],
            'reading_status': 'evidence_assessment'}


def fixture(respond, **settings):
    _, engine, old_state, calls = web_fixture(respond, **settings)
    program = deepcopy(old_state.program)
    program['variables']['other'] = {'type': 'set', 'demand': 'history'}
    state = FactState(program, old_state.contract, engine.steps, old_state.final_node_id)
    return WebJointReader(engine, state), engine, state, calls


def read(reader, doc='piano', variables=('history', 'other'), identity=IDENTITY):
    return reader.read(reader.e.steps[0], 'Read the invented activity attributes',
                       list(variables), [doc], identity, discovery_doc_ids=[doc])


@pytest.mark.parametrize('stance', ['support', 'partial', 'unknown', 'irrelevant'])
def test_complete_mixed_batch_keeps_only_the_independent_empty_slot_hint(stance):
    row = observation(stance=stance)
    if stance != 'support':
        row['value'] = None
    reader, engine, state, calls = fixture(lambda i, data: {
        'slots': [evidence('history', row), empty('other')]})
    read(reader)
    assert reader.batches[-1]['complete'] and reader.batches[-1]['valid_rows'] == 1
    feedback = reader.navigation_feedback('history', identity=IDENTITY)
    hint, = feedback['accepted_empty_reads']
    assert hint['variable'] == 'other' and hint['logical_call_index'] == 1
    assert hint['source_ids'] == [engine.mapper.sources['s1']['source_id']]
    assert hint['doc_ids'] == ['piano'] and len(calls.requests) == 1
    assert 'other' not in state.valid()[0]
    before = (reader.material_signature(), deepcopy(reader.obligation_snapshot()),
              deepcopy(state.public_dict()), deepcopy(engine.mapper.sources))
    projected = reader.navigation_feedback_projection('history', identity=IDENTITY)
    assert projected['grants_review_authority'] is False
    projected['accepted_empty_reads'][0]['variable_hints'][0]['search_gaps'].append('caller mutation')
    assert before == (reader.material_signature(), reader.obligation_snapshot(),
                      state.public_dict(), engine.mapper.sources)
    assert 'caller mutation' not in reader.web_navigation_reads[0]['search_gaps']


def test_already_completed_empty_slot_keeps_its_actual_exposure_when_other_slot_is_repaired():
    def respond(index, data):
        if index == 1:
            return {'slots': [empty('history'), evidence('other', observation('other-draft', ['not-offered']))]}
        return {'slots': [evidence('other', observation('other-draft', ['s1']))]}
    reader, _, state, calls = fixture(respond)
    read(reader)
    assert len(calls.requests) == 2 and set(calls.requests[1]['data']['variables']) == {'other'}
    assert reader.batches[-1]['complete'] and state.valid()[0]['other'] == ['piano']
    hint, = reader.web_navigation_reads
    assert hint['variable'] == 'history' and hint['logical_call_index'] == 1
    assert hint['request_identity'] == reader.web_search_gaps[0]['request_identity']


def test_final_empty_repair_cannot_relabel_same_slot_frozen_partial_as_an_empty_read():
    old = observation('old-partial', ['s1'], stance='partial')
    old['value'] = None
    current = {**deepcopy(old), 'id': 'current-partial'}
    def respond(index, data):
        if index == 1:
            return {'slots': [evidence('history', old)]}
        if index == 2:
            slot = evidence('history', current)
            slot['resolved_obligation_ids'] = [data['evidence_obligations'][0]['id']]
            return {'slots': [slot, empty('other')]}
        return {'slots': [empty('history')]}
    reader, _, state, calls = fixture(respond, max_repairs_per_request=1)
    read(reader, variables=('history',), identity='earlier-original-issue')
    original_issue = deepcopy(reader.evidence_obligations)
    read(reader, doc='painting')
    assert len(calls.requests) == 3 and reader.batches[-1]['complete']
    assert reader.batches[-1]['valid_rows'] == 1 and state.pending == {'history'}
    assert set(reader.evidence_obligations) == set(original_issue)
    for issue_id, old_issue in original_issue.items():
        assert {key: value for key, value in reader.evidence_obligations[issue_id].items() if key != 'origins'} == {
            key: value for key, value in old_issue.items() if key != 'origins'}
    assert [hint['variable'] for hint in reader.web_navigation_reads] == ['other']
    assert reader.web_navigation_reads[0]['logical_call_index'] == 2
    assert any(gap['variable'] == 'history' and gap['logical_call_index'] == 3
               for gap in reader.web_search_gaps)


def test_empty_repair_of_named_invalid_draft_is_never_accepted_as_a_search_hint():
    def respond(index, data):
        if index == 1:
            return {'slots': [evidence('history', observation('required-draft', ['not-offered'])), empty('other')]}
        if index == 2:
            return {'slots': [empty('history')]}
        return {'slots': [evidence('history', observation('required-draft', ['s1']))]}
    reader, _, state, calls = fixture(respond)
    read(reader)
    assert len(calls.requests) == 3 and reader.batches[-1]['complete']
    assert state.valid()[0]['history'] == ['piano']
    assert [hint['variable'] for hint in reader.web_navigation_reads] == ['other']
    assert any(gap['variable'] == 'history' for gap in reader.web_search_gaps)


def test_invalid_envelope_unresolved_draft_stays_separate_from_other_empty_slot():
    def respond(index, data):
        if index == 1:
            return {'slots': [{'variable': 'history', 'observations': [],
                              'unresolved': ['The original activity date is ambiguous.']}, empty('other')]}
        return {'slots': [empty(variable) for variable in data['variables']]}
    reader, _, state, calls = fixture(respond, max_repairs_per_request=1)
    read(reader)
    assert len(calls.requests) == 2 and reader.batches[-1]['complete']
    assert reader.evidence_obligations and state.pending == {'history'}
    assert [hint['variable'] for hint in reader.web_navigation_reads] == ['other']


def test_incomplete_mixed_batch_cannot_publish_even_its_other_empty_slot():
    reader, _, state, calls = fixture(lambda i, data: {'slots': [
        evidence('history', observation('bad-source', ['not-offered'])), empty('other')]},
        max_repairs_per_request=0)
    read(reader)
    assert len(calls.requests) == 1 and not reader.batches[-1]['complete']
    assert reader.failed_batch_reviews and state.pending
    assert reader.web_search_gaps and not reader.web_navigation_reads


def test_pure_empty_batch_retains_all_variable_hints_and_original_projection_group():
    reader, _, state, calls = fixture(lambda i, data: {'slots': [empty(variable) for variable in data['variables']]})
    read(reader)
    assert len(calls.requests) == 1 and reader.batches[-1]['valid_rows'] == 0
    assert {hint['variable'] for hint in reader.web_navigation_reads} == {'history', 'other'}
    projection = reader.navigation_feedback_projection('history', identity=IDENTITY)
    assert projection['accepted_empty_read_count'] == 2 and projection['projected_empty_exposure_count'] == 1
    assert not state.routes and not state.pending


def test_transient_nonempty_tracking_does_not_suppress_a_later_window_or_change_material():
    def respond(index, data):
        return {'slots': [evidence('history', observation()), empty('other')]} if index == 1 else {
            'slots': [empty(variable) for variable in data['variables']]}
    reader, _, _, calls = fixture(respond)
    read(reader)
    read(reader, doc='painting')
    assert len(calls.requests) == 2
    assert any(hint['variable'] == 'history' and hint['logical_call_index'] == 2
               for hint in reader.web_navigation_reads)
    signature, snapshot = reader.material_signature(), deepcopy(reader.obligation_snapshot())
    reader._web_navigation_nonempty_slots = {'measurement-only': {'history', 'other'}}
    reader._web_navigation_exposure_batches = {'measurement-only': 100}
    assert reader.material_signature() == signature and reader.obligation_snapshot() == snapshot


def test_repair_narrowing_sources_preserves_sibling_hint_and_same_slot_partial_barrier():
    def respond(index, data):
        if index == 1:
            row = observation('other-original-partial', ['s1'], stance='partial')
            row['value'] = None
            return {'slots': [evidence('other', row)]}
        if index == 2:
            row = observation('history-current-partial', ['s2'], stance='partial')
            row['value'] = None
            slot = evidence('history', row)
            slot['resolved_obligation_ids'] = ['invented-unoffered-id']
            return {'slots': [slot, empty('other')]}
        return {'slots': [empty('history')]}
    reader, _, state, calls = fixture(respond, max_repairs_per_request=1)
    read(reader, variables=('other',), identity='earlier-other-issue')
    read(reader, doc='painting')
    assert [[source['id'] for source in call['data']['source_spans']] for call in calls.requests] == [
        ['s1'], ['s1', 's2'], ['s2']]
    assert reader.batches[-1]['complete'] and reader.batches[-1]['valid_rows'] == 1
    assert state.pending == {'history', 'other'}
    hint, = reader.web_navigation_reads
    assert hint['variable'] == 'other' and hint['logical_call_index'] == 2
    assert hint['doc_ids'] == ['piano', 'painting']
    assert len(hint['source_ids']) == 2
    assert any(gap['variable'] == 'history' and gap['logical_call_index'] == 3
               for gap in reader.web_search_gaps)


def test_multiple_batches_in_one_read_keep_nonempty_barriers_local_to_each_batch(monkeypatch):
    def respond(index, data):
        return {'slots': [evidence('history', observation()), empty('other')]} if index == 1 else {
            'slots': [empty(variable) for variable in data['variables']]}
    reader, engine, _, calls = fixture(respond)
    monkeypatch.setattr(reader, '_fitting_prefix',
                        lambda operation, step, query, variables, pending, semantic, audit: (pending[0], 1))
    reader.read(engine.steps[0], 'Read the invented activity attributes', ['history', 'other'],
                ['piano', 'painting'], IDENTITY)
    assert len(calls.requests) == 2 and len(reader.batches) == 2
    assert reader.batches[0]['valid_rows'] == 1 and reader.batches[1]['valid_rows'] == 0
    assert any(hint['variable'] == 'history' and hint['logical_call_index'] == 2
               for hint in reader.web_navigation_reads)
    assert {hint['logical_call_index'] for hint in reader.web_navigation_reads
            if hint['variable'] == 'other'} == {1, 2}
