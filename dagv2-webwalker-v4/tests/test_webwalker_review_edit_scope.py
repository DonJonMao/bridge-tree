"""Web review projection checks with invented evidence and no external calls."""
from copy import deepcopy

import pytest

from dagbt.webwalker_reading import WebJointReader
from test_webwalker_reading import expand_wire_data, observation, read, response, web_fixture


def fixture(respond=None, **settings):
    _, engine, state, calls = web_fixture(respond, **settings)
    return WebJointReader(engine, state), engine, state, calls


def wildcard_data(reader, engine):
    data = reader._payload(engine.steps[0], 'query', ['history'], ['s1', 's2', 's3'])
    data['evidence_obligations'] = [{'id': 'history-issue', 'variable': 'history', 'source_ids': ['s1']}]
    data['repair_scope'] = {'failed': [{'variable': 'history', 'id': '*', 'observation': None,
        'slot': {'variable': 'history', 'observations': [], 'unresolved': [],
                 'resolved_obligation_ids': ['history-issue']}}]}
    return data


def test_empty_new_window_need_not_claim_settlement_of_existing_source_issue():
    old = observation('old-incomplete', ['s1'], stance='partial',
                      reason='Original historical statement remains incomplete.')
    old['value'] = None
    reader, engine, state, calls = fixture(
        lambda index, data: response(old) if index == 1 else response())
    read(reader, 'piano', 'same-query')
    old_issues = deepcopy(reader.evidence_obligations)
    originals = deepcopy(engine.mapper.sources)
    read(reader, 'painting', 'same-query')
    assert len(calls.requests) == 2 and engine.ledger.used['json_repairs'] == 0
    assert reader.batches[-1]['complete'] and reader.batches[-1]['valid_rows'] == 0
    assert reader.evidence_obligations == old_issues and state.pending == {'history'}
    assert not state.routes and not state.valid()[0] and not reader.failed_batch_reviews
    assert engine.mapper.sources == originals
    current = calls.requests[-1]['data']
    obligation, = current['web_review_checklist']['obligations']
    assert obligation['new_review_required_only_if_settlement_claimed'] is True
    assert obligation['sources_requiring_new_model_review'] == ['s1']
    assert {source['id'] for source in current['source_spans']} == {'s1', 's2'}


def test_wire_projection_preserves_every_source_raw_draft_counter_and_global_issue_without_mutation():
    reader, engine, state, calls = fixture()
    data = wildcard_data(reader, engine)
    partial = observation('frozen-partial', ['s1'], stance='partial')
    partial['value'] = None
    data['repair_scope']['frozen_observation_ids'] = {'history': ['frozen-partial']}
    data['repair_scope']['failed'][0]['slot']['observations'] = [partial]
    counter = observation('retained-counter', ['s3'], stance='contradiction')
    data['known_observations'] = [counter]
    data['global_issues'] = [{'id': 'global-open', 'source_ids': ['s3'], 'reason': 'Retain this issue.'}]
    data['failed_batch_reviews'] = [{'id': 'blocked-batch', 'variable': 'history',
        'review_allowed': False, 'source_ids': ['s2', 's3'],
        'failed': [{'id': 'required-draft', 'observation': observation('required-draft', ['s2']),
                    'required_counter_observations': [counter]}],
        'invalid_response': '  {"original": "unaltered raw text"}\n'}]
    before = deepcopy(data)
    state_before = deepcopy(state.__dict__)
    reader_before = deepcopy(reader.obligation_snapshot())
    sources_before = deepcopy(engine.mapper.sources)
    limits_before = deepcopy(engine.ledger.public_dict())
    wire = expand_wire_data(reader._wire_candidates(data)[0][0])
    for field in ('source_spans', 'repair_scope', 'known_observations',
                  'global_issues', 'evidence_obligations', 'failed_batch_reviews'):
        assert wire[field] == before[field], field
    checklist = wire['web_review_checklist']
    assert checklist['grants_review_authority'] is False
    assert checklist['empty_withdrawal_edit_scope']['controller_evidence_and_issues_unchanged'] is True
    assert 'invented_response_examples' not in checklist
    assert data == before and state.__dict__ == state_before
    assert reader.obligation_snapshot() == reader_before and engine.mapper.sources == sources_before
    assert engine.ledger.public_dict() == limits_before and not calls.requests
    # A caller may mutate the wire projection without changing any retained input.
    wire['repair_scope']['failed'][0]['slot']['observations'].clear()
    wire['failed_batch_reviews'][0]['failed'].clear()
    wire['web_review_checklist']['empty_withdrawal_edit_scope']['variables'].append('alien')
    assert data == before and state.__dict__ == state_before


@pytest.mark.parametrize('stance', ['partial', 'unknown'])
def test_legal_empty_claim_withdrawal_preserves_valid_incomplete_row_and_old_pending_issue(stance):
    old = observation('old-incomplete', ['s1'], stance=stance,
                      reason='Original historical statement remains incomplete.')
    old['value'] = None
    current = {**deepcopy(old), 'id': 'current-incomplete'}
    def respond(index, data):
        if index == 1:
            return response(old)
        if index == 2:
            value = response(current)
            value['slots'][0]['resolved_obligation_ids'] = [data['evidence_obligations'][0]['id']]
            return value
        assert data['web_review_checklist']['empty_withdrawal_edit_scope']['variables'] == ['history']
        assert 'invented_response_examples' not in data['web_review_checklist']
        return response()
    reader, engine, state, calls = fixture(respond, max_repairs_per_request=1)
    read(reader, 'piano', 'unchanged-query')
    old_issues = deepcopy(reader.evidence_obligations)
    originals = deepcopy(engine.mapper.sources)
    read(reader, 'painting', 'unchanged-query')
    assert len(calls.requests) == 3 and engine.ledger.used['json_repairs'] == 1
    assert reader.batches[-1]['complete'] is True and reader.batches[-1]['valid_rows'] == 1
    assert reader.evidence_obligations == old_issues
    assert state.pending == {'history'} and not state.routes and not state.valid()[0]
    assert not reader.failed_batch_reviews and not reader.web_navigation_reads
    assert engine.mapper.sources == originals
    repair = calls.requests[-1]['data']
    assert repair['repair_scope']['failed'][0]['slot']['observations'] == [current]
    assert repair['repair_scope']['frozen_observation_ids'] == {'history': ['current-incomplete']}
    assert {source['id'] for source in repair['source_spans']} == {'s1', 's2'}


@pytest.mark.parametrize('blocker', [
    'named_id', 'observation', 'observations', 'invalid_response', 'whole_value_reviews',
    'replacement_observations', 'required_counter_observations', 'paid_review'])
def test_no_empty_field_scope_when_existing_guard_protects_required_work(blocker):
    reader, engine, _, calls = fixture()
    data = wildcard_data(reader, engine)
    failed = data['repair_scope']['failed'][0]
    required = observation('required', ['s1'])
    if blocker == 'named_id':
        failed['id'] = 'required'
    elif blocker in ('observation', 'observations', 'replacement_observations', 'required_counter_observations'):
        failed[blocker] = required if blocker == 'observation' else [required]
    elif blocker == 'paid_review':
        data['failed_batch_reviews'] = [{'id': 'paid', 'variable': 'history', 'review_allowed': True}]
    else:
        data['repair_scope'][blocker] = 'raw invalid envelope' if blocker == 'invalid_response' else [required]
    before = deepcopy(data)
    assert reader._empty_repair_allowed(data) is False
    wire = expand_wire_data(reader._wire_candidates(data)[0][0])
    assert 'empty_withdrawal_edit_scope' not in wire['web_review_checklist']
    assert data == before and not calls.requests


def test_named_failed_draft_cannot_be_discarded_by_empty_model_response():
    draft = observation('required-draft', ['invented-source'])
    reader, engine, state, calls = fixture(
        lambda index, data: response(draft) if index == 1 else response(), max_repairs_per_request=1)
    read(reader)
    assert len(calls.requests) == 2
    repair = calls.requests[-1]['data']
    assert reader._empty_repair_allowed(repair) is False
    assert 'empty_withdrawal_edit_scope' not in repair.get('web_review_checklist', {})
    assert reader.failed_batch_reviews and not reader.batches[-1]['complete']
    assert state.pending == {'history'} and not state.valid()[0]
    assert any(failure['id'] == 'required-draft' and failure['observation'] == draft
               for record in reader.failed_batch_reviews.values() for failure in record['failed'])
    assert engine.ledger.used['json_repairs'] == 1


def test_frozen_offer_example_and_source_coverage_authority_are_isolated_per_variable():
    reader, engine, _, calls = fixture()
    data = wildcard_data(reader, engine)
    data['requested_slots'] = ['history', 'other']
    data['variables']['other'] = deepcopy(data['variables']['history'])
    data['evidence_obligations'].append({'id': 'other-issue', 'variable': 'other', 'source_ids': ['s1']})
    data['repair_scope']['frozen_observation_ids'] = {'history': ['shared-id'], 'other': ['shared-id']}
    # The same spelled ID/source grants only the explicitly offered variable authority.
    support = observation('shared-id', ['s1'])
    data['repair_scope']['failed'].extend([
        {'variable': 'other', 'id': '*', 'observation': None,
         'frozen_observation_reviews': {'slot_observation_ids': [], 'observations': [support]}},
        {'variable': 'unrequested', 'id': '*', 'observation': None}])
    before = deepcopy(data)
    wire = expand_wire_data(reader._wire_candidates(data)[0][0])
    checklist = wire['web_review_checklist']
    history, other = checklist['obligations']
    assert history['sources_requiring_new_model_review'] == ['s1']
    assert history['source_ids_covered_only_if_frozen_rows_explicitly_referenced'] == []
    assert other['sources_requiring_new_model_review'] == []
    assert other['source_ids_covered_only_if_frozen_rows_explicitly_referenced'] == ['s1']
    assert checklist['frozen_ids_without_reference_permission'] == [{'variable': 'history', 'id': 'shared-id'}]
    assert checklist['invented_response_examples']['applicable_variables'] == ['other']
    assert checklist['empty_withdrawal_edit_scope']['variables'] == ['history', 'other']
    assert data == before and not calls.requests


@pytest.mark.parametrize('offer_kind', ['no_offer', 'frozen_id_only', 'partial', 'other_variable'])
def test_no_hypothetical_support_example_without_actual_same_variable_support_offer(offer_kind):
    reader, engine, _, _ = fixture()
    data = wildcard_data(reader, engine)
    if offer_kind != 'no_offer':
        data['repair_scope']['frozen_observation_ids'] = {'history': ['sample-current']}
    if offer_kind in ('partial', 'other_variable'):
        row = observation('sample-current', ['s1'], stance='partial' if offer_kind == 'partial' else 'support')
        if offer_kind == 'partial':
            row['value'] = None
        data['repair_scope']['failed'].append({'variable': 'history' if offer_kind == 'partial' else 'other',
            'id': '*', 'frozen_observation_reviews': {'slot_observation_ids': [], 'observations': [row]}})
    reader._add_review_checklist(data)
    assert 'invented_response_examples' not in data['web_review_checklist']
    assert 'empty_withdrawal_edit_scope' in data['web_review_checklist']


def test_empty_edit_scope_is_not_added_to_terminal_or_audit_requests():
    reader, engine, _, _ = fixture()
    for key in ('audit_instruction', 'public_output_question', 'terminal_repair'):
        data = wildcard_data(reader, engine)
        data[key] = 'retained terminal instruction'
        reader._add_review_checklist(data)
        assert 'web_review_checklist' not in data

