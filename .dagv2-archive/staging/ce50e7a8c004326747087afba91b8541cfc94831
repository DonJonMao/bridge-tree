"""Source rechecking uses invented events and the actual offline Reasoner path."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from dagbt.evidence_spans import build_source_spans
from dagbt.fact_state import FactState
from dagbt.joint_reading import JointReader
from dagbt.reasoning import InputOverflow
from dagbt.webwalker_reading import (WEB_ENTAILMENT_INSTRUCTION,
                                     WEB_SOURCE_REVIEW_INSTRUCTION, WebJointReader)
from test_webwalker_reading import expand_wire_data, web_fixture


OLD = ('The Orion charter drafting workflow began in 2032. Its working venue was '
       'Lake Depot. This note concerns drafting; it does not describe charter approval.')
NEW = 'The Orion charter was approved in 2041 in Pine Hall.'


def fixture(respond, **settings):
    _, engine, _, calls = web_fixture(respond, **settings)
    steps = [
        {'output_slot': 'approval', 'question': 'When and where was the Orion charter approved?',
         'inputs': [], 'execution': 'retrieval', 'answer_type': 'fact'},
        {'output_slot': 'answer', 'question': 'Use {approval_year} and {approval_place}',
         'inputs': ['approval'], 'execution': 'compose', 'answer_type': 'fact'}]
    program = {'variables': {
        'approval_year': {'type': 'number', 'demand': 'approval'},
        'approval_place': {'type': 'text', 'demand': 'approval'},
        'answer': {'type': 'text', 'demand': 'answer'}},
        'expression': {'op': 'var', 'id': 'answer'}}
    contract = {'mode': 'semantic', 'result_type': 'text', 'entity_scope': 'Orion charter',
                'time_scope': 'charter approval', 'explanation': 'semantic'}
    state = FactState(program, contract, steps, 'answer')
    engine.steps = steps
    engine.q = {'question': steps[0]['question']}
    engine.docs = {}
    engine.mapper.sources.clear()
    engine.mapper.source_aliases.clear()
    for doc_id, text in [('drafting-note', OLD), ('approval-record', NEW)]:
        document = engine.docs[doc_id] = SimpleNamespace(doc_id=doc_id, passage=text, metadata={})
        for source in build_source_spans(doc_id, document, 400):
            alias = 's' + str(len(engine.mapper.sources) + 1)
            engine.mapper.sources[alias] = {**source, 'id': alias, 'source_id': source['id']}
            engine.mapper.source_aliases[source['id']] = alias
    return WebJointReader(engine, state), engine, state, calls


def row(identifier, value, sources, stance='support', retract_ids=()):
    return {'id': identifier, 'stance': stance, 'value': value, 'source_ids': list(sources),
            'entity_scope': 'Orion charter', 'time_scope': 'charter approval',
            'parent_versions': {}, 'retract_ids': list(retract_ids),
            'reason': ('Assess this original for the charter approval event, '
                       'which differs from the drafting workflow.')}


def slot(variable, *rows, **claims):
    return {'variable': variable, 'reading_status': 'evidence_assessment' if rows or claims
            else 'no_relevant_evidence', 'observations': list(rows), 'unresolved': [], **claims}


def read(reader, document, variables=('approval_year', 'approval_place')):
    return reader.read(reader.e.steps[0], reader.e.q['question'], list(variables),
                       [document], 'invented-approval-query', discovery_doc_ids=[document])


def old_judgments():
    return {'slots': [slot('approval_year', row('old-year', 2032, ['s1'])),
                      slot('approval_place', row('old-place-issue', None, ['s1'], 'unknown'))]}


def test_first_read_pairs_exact_scopes_and_visible_original_before_context():
    def respond(index, data):
        review = data['web_source_review']
        assert review['cards'] == []
        assert review['document_scope_review'] == {
            'requested_scopes': data['requested_scopes'],
            'documents': [{'doc_id': data['source_spans'][0]['doc_id'],
                           'earliest_visible_original': data['source_spans'][0]}]}
        return {'slots': [slot(variable) for variable in data['requested_slots']]}

    reader, engine, state, calls = fixture(respond)
    originals = deepcopy(engine.mapper.sources)
    read(reader, 'drafting-note')
    actual_wire = json.loads(calls.requests[0]['payload']['messages'][1]['content'])
    assert next(iter(actual_wire)) == 'web_source_review'
    assert 'Shared\nsite, partner, topic or question context alone establishes no identity bridge.' in (
        calls.requests[0]['payload']['messages'][0]['content'])
    assert not state.routes and not reader.evidence_obligations
    assert engine.mapper.sources == originals and reader.batches[-1]['complete']


def test_document_scope_uses_only_current_earliest_visible_original_and_stable_ties():
    reader, engine, _, _ = fixture(lambda i, data: old_judgments())
    data = reader._payload(engine.steps[0], 'Review approval', ['approval_year'], ['s2'])
    current = data['source_spans'][0]
    data['source_spans'] = [
        {**current, 'id': 'visible-later', 'start': 900, 'end': 980},
        {**current, 'id': 'visible-earliest', 'start': 400, 'end': 480,
         'future_source_field': {'nested': ['preserve', 23]}},
        {**current, 'id': 'visible-tie', 'start': 400, 'end': 490},
        {**current, 'id': 'other-doc', 'doc_id': 'second-doc', 'start': 700, 'end': 780}]
    canonical = deepcopy(data)
    for wire, _ in reader._wire_candidates(data):
        review = wire['web_source_review']['document_scope_review']
        assert review['requested_scopes'] == canonical['requested_scopes']
        assert review['documents'] == [
            {'doc_id': current['doc_id'], 'earliest_visible_original': canonical['source_spans'][1]},
            {'doc_id': 'second-doc', 'earliest_visible_original': canonical['source_spans'][3]}]
        assert all(entry['earliest_visible_original']['start'] > 0 for entry in review['documents'])
    assert data == canonical


@pytest.mark.parametrize('correct', [False, True])
def test_new_original_rechecks_prior_judgment_without_automatic_fact_changes(correct):
    def respond(index, data):
        if index == 1:
            return old_judgments()
        source_by_id = {source['id']: source for source in data['source_spans']}
        assert source_by_id['s1']['text'] == OLD and source_by_id['s2']['text'] == NEW
        card, = data['web_source_review']['cards']
        assert card['original_source'] == source_by_id['s1']
        assert data['web_source_review']['document_scope_review'] == {
            'requested_scopes': data['requested_scopes'], 'documents': [
                {'doc_id': source_by_id['s1']['doc_id'],
                 'earliest_visible_original': {'card_original_source_id': 's1'}},
                {'doc_id': source_by_id['s2']['doc_id'],
                 'earliest_visible_original': source_by_id['s2']}]}
        assert {'doc_id', 'start', 'end', 'text'} <= card['original_source'].keys()
        known, = card['known_observation_refs']
        assert known['variable'] == 'approval_year' and known['semantic_status'] == 'model_judgment'
        issue, = card['obligation_refs']
        assert issue == {'variable': 'approval_place', 'id': data['evidence_obligations'][0]['id']}
        assert card['offered_frozen_refs'] == []
        if not correct:
            return {'slots': [slot(variable) for variable in data['requested_slots']]}
        return {'slots': [
            slot('approval_year',
                 row('counter-old-year', None, ['s1', 's2'], 'contradiction', [known['id']]),
                 row('approval-year', 2041, ['s2'])),
            slot('approval_place', row('approval-place', 'Pine Hall', ['s2']),
                 row('drafting-place-review', None, ['s1'], 'irrelevant'),
                 resolved_obligation_ids=[issue['id']])]}

    reader, engine, state, calls = fixture(respond)
    read(reader, 'drafting-note')
    old_route, = state.routes
    issues = deepcopy(reader.evidence_obligations)
    originals = deepcopy(engine.mapper.sources)
    limits = deepcopy(engine.ledger.limits)
    read(reader, 'approval-record')
    assert len(calls.requests) == engine.ledger.used['llm'] == 2
    assert engine.ledger.used['json_repairs'] == 0 and not reader.failed_batch_reviews
    assert engine.mapper.sources == originals and engine.ledger.limits == limits
    actual = calls.requests[-1]['payload']['messages'][0]['content']
    assert WEB_SOURCE_REVIEW_INSTRUCTION in actual
    assert 'within this current batch are frozen during its' in actual
    if correct:
        assert state.routes[old_route]['revoked']
        assert state.valid()[0]['approval_year'] == 2041
        assert state.valid()[0]['approval_place'] == 'Pine Hall'
        assert not reader.evidence_obligations and not state.pending
    else:
        assert not state.routes[old_route]['revoked']
        assert state.valid()[0]['approval_year'] == 2032
        assert 'approval_place' not in state.valid()[0]
        assert reader.evidence_obligations == issues and state.pending == {'approval_place'}


def test_repair_reviews_missing_old_original_and_deduplicates_actual_frozen_sources():
    frozen_rows = [row('place-support-a', 'Pine Hall', ['s2']),
                   row('place-support-b', 'Pine Hall', ['s2'])]
    def respond(index, data):
        if index == 1:
            return {'slots': [slot('approval_place', row('old-issue', None, ['s1'], 'unknown'))]}
        issue = data['evidence_obligations'][0]['id']
        if index == 2:
            # The new source alone does not review the old obligated original.
            return {'slots': [slot('approval_place', *frozen_rows, resolved_obligation_ids=[issue])]}
        checklist = data['web_review_checklist']
        assert checklist['obligations'][0]['sources_requiring_new_model_review'] == ['s1']
        assert checklist['obligations'][0][
            'source_ids_covered_only_if_frozen_rows_explicitly_referenced'] == []
        cards = data['web_source_review']['cards']
        assert [card['original_source']['id'] for card in cards] == ['s1', 's2']
        assert cards[0]['original_source']['text'] == OLD
        assert cards[0]['obligation_refs'] == [{'variable': 'approval_place', 'id': issue}]
        assert cards[0]['offered_frozen_refs'] == []
        offered = cards[1]['offered_frozen_refs']
        assert {entry['id'] for entry in offered} == {'place-support-a', 'place-support-b'}
        assert all(entry['source_ids'] == ['s2'] for entry in offered)
        assert all(entry['can_contribute_to_settled_source_coverage'] for entry in offered)
        assert offered == checklist['offered_frozen_observations']
        return {'slots': [slot('approval_place',
            row('old-original-review', None, ['s1'], 'irrelevant'),
            reviewed_observation_ids=[entry['id'] for entry in offered], resolved_obligation_ids=[issue])]}

    reader, engine, state, calls = fixture(respond, max_repairs_per_request=1)
    read(reader, 'drafting-note', ('approval_place',))
    read(reader, 'approval-record', ('approval_place',))
    assert len(calls.requests) == engine.ledger.used['llm'] == 3
    assert engine.ledger.used['json_repairs'] == 1
    assert not reader.evidence_obligations and not reader.failed_batch_reviews and not state.pending
    assert state.valid()[0]['approval_place'] == 'Pine Hall'
    assert reader.batches[-1]['complete'] and reader.batches[-1]['valid_rows'] == 3
    repair_response = json.loads(engine.reasoner.requests[-1]['raw_output'])['slots'][0]
    assert [entry['id'] for entry in repair_response['observations']] == ['old-original-review']


def test_wire_cards_preserve_canonical_state_unknown_fields_and_permissions():
    reader, engine, state, calls = fixture(lambda i, data: old_judgments())
    read(reader, 'drafting-note')
    data = reader._payload(engine.steps[0], 'Review approval',
                           ['approval_year', 'approval_place'], ['s2'])
    data['source_spans'][0]['future_source_field'] = {'nested': ['keep', 23]}
    data['future_mandatory_field'] = {'nested': {'raw': 'preserve exactly'}}
    data['repair_scope'] = {'failed': [], 'future_repair_field': {'do_not_drop': [1, 2]}}
    canonical = deepcopy(data)
    before = (deepcopy(state.public_dict()), deepcopy(reader.obligation_snapshot()),
              deepcopy(engine.mapper.sources), deepcopy(engine.ledger.public_dict()))
    schema = reader._schema(data)
    candidates = reader._wire_candidates(data)
    for wire, system in candidates:
        expanded = expand_wire_data(wire)
        for key in ('source_spans', 'repair_scope', 'future_mandatory_field', 'evidence_obligations'):
            assert expanded[key] == canonical[key]
        assert expanded['web_source_review']['cards'][0]['original_source'] == canonical['source_spans'][0]
        assert expanded['web_source_review']['grants_review_authority'] is False
        assert expanded['web_source_review']['existing_permissions_unchanged'] is True
        assert reader._schema(expanded) == schema
        assert WEB_SOURCE_REVIEW_INSTRUCTION in system
    assert data == canonical
    assert before == (state.public_dict(), reader.obligation_snapshot(),
                      engine.mapper.sources, engine.ledger.public_dict())
    assert len(calls.requests) == 1


@pytest.mark.parametrize('change', ['source_removed', 'offer_removed', 'slot_changed', 'boundary'])
def test_reused_wire_cards_are_rebuilt_from_current_sources_slots_and_offers(change):
    reader, engine, _, calls = fixture(lambda i, data: old_judgments())
    data = reader._payload(engine.steps[0], 'Review approval', ['approval_place'], ['s2'])
    offered = row('frozen-place', 'Pine Hall', ['s2'])
    data['repair_scope'] = {
        'frozen_observation_ids': {'approval_place': ['frozen-place']},
        'failed': [{'variable': 'approval_place', 'id': '*', 'observation': None,
                    'frozen_observation_reviews': {'slot_observation_ids': [], 'observations': [offered]}}]}
    previous = expand_wire_data(reader._wire_candidates(data)[0][0])
    assert previous['web_source_review']['cards'][0]['offered_frozen_refs'][0]['id'] == 'frozen-place'
    if change == 'source_removed':
        previous['source_spans'] = []
    elif change == 'offer_removed':
        previous.pop('repair_scope')
    elif change == 'slot_changed':
        previous['requested_slots'] = ['approval_year']
        previous['variables'] = {'approval_year': {'type': 'number', 'demand': 'approval'}}
    else:
        previous['audit_instruction'] = 'Audit originals.'
    before = deepcopy(previous)
    for wire, system in reader._wire_candidates(previous):
        if change in ('source_removed', 'boundary'):
            assert 'web_source_review' not in wire
            assert WEB_SOURCE_REVIEW_INSTRUCTION not in system
        else:
            assert wire['web_source_review']['cards'] == []
            assert wire['web_source_review']['document_scope_review']['requested_scopes'] == (
                previous['requested_scopes'])
            assert WEB_SOURCE_REVIEW_INSTRUCTION in system
    assert previous == before and not calls.requests


def test_source_card_overhead_is_counted_by_production_reasoner_and_admission():
    reader, engine, _, calls = fixture(lambda i, data: old_judgments())
    read(reader, 'drafting-note')
    data = reader._payload(engine.steps[0], 'Review approval',
                           ['approval_year', 'approval_place'], ['s2'])
    wire, system, accounting = reader._select_wire(
        'joint_read', reader._wire_candidates(data), reader._schema(data))
    expected_payload = engine.reasoner._payload('joint_read', system, wire, reader._schema(data))
    assert accounting == engine.reasoner._count_payload('joint_read', expected_payload)
    without_cards = deepcopy(wire)
    del without_cards['web_source_review']
    without_system = system.replace(WEB_SOURCE_REVIEW_INSTRUCTION, '', 1)
    smaller = engine.reasoner.estimate('joint_read', without_system, without_cards, reader._schema(data))
    assert smaller < accounting['count']
    engine.s['context_tokens'] = smaller + engine.s['reasoning_output_tokens'] + engine.s['input_margin'] + 8
    with pytest.raises(InputOverflow):
        engine.reasoner.request('joint_read', system, wire, schema=reader._schema(data))
    assert reader._fits('joint_read', data) is False
    assert len(calls.requests) == 1 and engine.ledger.used['llm'] == 1


@pytest.mark.parametrize('boundary', [
    {'task': {'execution': 'compose'}}, {'audit_instruction': 'Audit originals.'},
    {'public_output_question': 'Compose answer.'}, {'terminal_repair': {'expected_value': 'unchanged'}}])
def test_source_review_is_not_injected_into_compose_audit_or_terminal(boundary):
    reader, engine, _, _ = fixture(lambda i, data: old_judgments())
    read(reader, 'drafting-note')
    data = reader._payload(engine.steps[0], 'Review approval', ['approval_year', 'approval_place'], ['s2'])
    data.update(boundary)
    for wire, system in reader._wire_candidates(data):
        assert 'web_source_review' not in wire
        assert WEB_SOURCE_REVIEW_INSTRUCTION not in system
    assert reader._system(data) == JointReader._system(data) + WEB_ENTAILMENT_INSTRUCTION + (
            '\nAudit must cover EVERY attribute requested by original_question and each '
            'output_contract.fields entry. Correct individual facts do not establish a '
            'complete terminal answer; withhold supported if an attribute is missing.\n'
            if 'audit_instruction' in data else '')
