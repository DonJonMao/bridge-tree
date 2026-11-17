"""Ordinary Web instruction reconciliation; invented evidence, no external calls."""
from copy import deepcopy
from itertools import product

import pytest

from dagbt import joint_reading as common
from dagbt.reasoning import ProtocolError
from dagbt import webwalker_reading as web
from dagbt.webwalker_reading import WebJointReader
from test_webwalker_reading import observation, read, response, web_fixture


def legacy_system(data):
    """Frozen v11 Web composition, independent of the reconciliation helper."""
    system = common.JointReader._system(data) + web.WEB_ENTAILMENT_INSTRUCTION
    if WebJointReader._search_gap_scope(data):
        system += web.WEB_READING_INSTRUCTION
        if data.get('web_reading_context'):
            system += web.WEB_WINDOW_INSTRUCTION
        if data.get('web_review_checklist'):
            system += web.WEB_REVIEW_CHECKLIST_INSTRUCTION
        if data.get('web_repair_edit_scope'):
            system += web.WEB_REPAIR_EDIT_SCOPE_INSTRUCTION
        if data.get('repair_scope') or data.get('evidence_obligations'):
            system += web.WEB_REPAIR_INSTRUCTION
        if data.get('repair_scope'):
            if WebJointReader._empty_repair_allowed(data):
                system += web.WEB_EMPTY_REPAIR_INSTRUCTION
    if 'audit_instruction' in data:
        system += ('\nAudit must cover EVERY attribute requested by original_question and each '
                   'output_contract.fields entry. Correct individual facts do not establish a '
                   'complete terminal answer; withhold supported if an attribute is missing.\n')
    return system


def ordinary(**changes):
    return {'task': {'execution': 'retrieval', 'output_slot': 'history'},
            'variables': {'history': {'type': 'set', 'demand': 'history'}},
            'requested_slots': ['history'], **changes}


def selected_data(flags):
    columnar, frozen, obligation, whole, failed, table = flags
    data = ordinary()
    if columnar:
        data['source_span_columns'] = ['id', 'text']
    if frozen:
        data.setdefault('repair_scope', {})['frozen_observation_ids'] = {'history': ['immutable']}
    if obligation:
        data.setdefault('repair_scope', {})['failed'] = [{
            'variable': 'history', 'id': '*', 'obligation_review_sources': {'required': ['s1']}}]
    if whole:
        data.setdefault('repair_scope', {})['whole_value_reviews'] = [{
            'variable': 'history', 'known_observation_ids': ['known-route'],
            'draft_observations': [observation('draft-a'), observation('draft-b', ['s2'])]}]
    if failed:
        data['failed_batch_reviews'] = [{'id': 'failed-review', 'review_allowed': True,
            'failed': [{'id': 'required-draft', 'observation': observation('required-draft')}],
            'whole_value_reviews': [{'variable': 'history'}]}]
    if table:
        data['known_observation_columns'] = ['id', 'value']
    return data


@pytest.mark.parametrize('flags', list(product([False, True], repeat=6)))
def test_selected_common_segments_are_preserved_except_exact_guarded_replacements(flags):
    data = selected_data(flags)
    before = deepcopy(data)
    expected = legacy_system(data)
    common_before = common.JointReader._system(data)
    for name, pairs in web._WEB_COMMON_REPLACEMENTS.items():
        for old, new in pairs:
            # Whole-value instructions may occur twice; each selected segment is guarded.
            expected = expected.replace(old, new)
    actual = WebJointReader._system(data)
    assert actual == expected
    assert actual.count(web.WEB_READING_INSTRUCTION) == 1
    assert 'and unresolved descriptions.' not in actual
    assert 'or slot.unresolved\ndescriptions.' not in actual
    assert 'preserve it in slot.unresolved' not in actual
    assert 'named sourced partial/unknown' in actual
    assert 'value=null' in actual
    assert data == before
    assert common.JointReader._system(data) == common_before


@pytest.mark.parametrize('boundary', [
    {'task': {'execution': 'compose'}},
    {'audit_instruction': 'Original-source audit.'},
    {'public_output_question': 'Return the final answer.'},
    {'terminal_repair': {'expected_value': 'unchanged'}},
])
@pytest.mark.parametrize('flags', [tuple([False] * 6), tuple([True] * 6)])
def test_compose_terminal_and_audit_system_output_is_byte_identical(boundary, flags):
    data = selected_data(flags)
    data.update(boundary)
    before = deepcopy(data)
    assert not WebJointReader._search_gap_scope(data)
    assert WebJointReader._system(data).encode() == legacy_system(data).encode()
    assert data == before


def test_failed_whole_value_and_frozen_repair_preserve_drafts_counters_and_authority():
    data = selected_data(tuple([True] * 6))
    counter = observation('protected-counter', ['s3'], stance='contradiction', retract_ids=['real-route'])
    counter['value'] = None
    data['repair_scope']['failed'][0]['required_counter_observations'] = [counter]
    data['repair_scope']['failed'][0]['replacement_observations'] = [
        observation('required-a', ['s1']), observation('required-b', ['s2'])]
    data['source_spans'] = [{'id': f's{i}', 'text': f'Unchanged original {i}'} for i in range(1, 4)]
    data['evidence_obligations'] = [{'id': 'real-issue', 'source_ids': ['s1', 's2']}]
    before = deepcopy(data)
    system = WebJointReader._system(data)
    assert data == before
    assert 'retaining EACH draft ID and its original source_ids' in system
    assert 'Keep every original counter and' in system
    assert 'protected stance, sources, scopes, actual parents and retraction targets' in system
    assert 'Do not restate or edit a frozen observation' in system
    assert 'review all required sources' in system
    assert 'Failed-format recovery need not settle' in system
    assert 'controller source issue stays pending' in system
    assert 'resolved_failed_batch_ids' in system
    assert 'partial/unknown observations cannot settle evidence obligations' in system
    assert 'retain each required draft ID and original source' in system


@pytest.mark.parametrize('change', ['modified', 'missing', 'unknown'])
def test_changed_missing_or_unknown_common_composition_fails_closed(monkeypatch, change):
    data = ordinary(source_span_columns=['id'])
    original = common.JointReader._system(data)
    if change == 'modified':
        monkeypatch.setattr(common, 'SYSTEM', common.SYSTEM + '\nUnreviewed common rule.\n')
    elif change == 'missing':
        monkeypatch.setattr(common.JointReader, '_system', staticmethod(lambda unused: original.replace(
            common.COLUMNAR_INSTRUCTION, '', 1)))
    else:
        monkeypatch.setattr(common.JointReader, '_system', staticmethod(lambda unused: original + '\nUnknown segment.\n'))
    with pytest.raises(ProtocolError, match='common instruction'):
        WebJointReader._system(data)


def test_missing_exact_replacement_pattern_fails_closed(monkeypatch):
    replacements = deepcopy(web._WEB_COMMON_REPLACEMENTS)
    replacements['SYSTEM'] += (('A nonexistent old sentence.', 'replacement'),)
    monkeypatch.setattr(web, '_WEB_COMMON_REPLACEMENTS', replacements)
    with pytest.raises(ProtocolError, match='replacement count changed'):
        WebJointReader._system(ordinary())


@pytest.mark.parametrize('unexpected', [
    {'personal_response_selection': True}, {'public_options': {'A': 'unexpected choice'}}])
def test_unexpected_ordinary_common_branch_fails_closed(unexpected):
    with pytest.raises(ProtocolError, match='Unexpected common branch'):
        WebJointReader._system(ordinary(**unexpected))


def test_empty_new_evidence_remains_empty_and_real_source_issue_stays_pending():
    row = observation('genuine-ambiguity', ['s1'], stance='partial',
                      reason='The original states a genuine incomplete historical activity.')
    row['value'] = None
    reader, engine, state, calls = web_fixture(lambda i, data: response(row) if i == 1 else response())
    sources, program, steps = deepcopy(engine.mapper.sources), deepcopy(state.program), deepcopy(engine.steps)
    read(reader, 'piano', 'initial-real-partial')
    issues = deepcopy(reader.evidence_obligations)
    assert issues and state.pending == {'history'}
    read(reader, 'painting', 'new-answer-free-window')
    assert len(calls.requests) == 2 and engine.ledger.used['llm'] == 2
    assert engine.ledger.used['json_repairs'] == 0
    assert reader.evidence_obligations == issues and state.pending == {'history'}
    assert not state.valid()[0] and not reader.failed_batch_reviews
    assert engine.mapper.sources == sources and state.program == program and engine.steps == steps
    for call in calls.requests:
        system = call['payload']['messages'][0]['content']
        assert 'and unresolved descriptions.' not in system
        assert 'BOTH statuses require unresolved=[]' in system
