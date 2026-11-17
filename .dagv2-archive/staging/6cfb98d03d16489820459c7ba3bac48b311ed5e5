"""Ordinary-Web scope dispositions through real scripted Reasoner requests."""
from copy import deepcopy

import pytest

from dagbt.evidence_spans import build_source_spans
from dagbt.joint_reading import JointReader
from dagbt.webwalker_reading import WebJointReader, _WEB_COMMON_REPLACEMENTS
from test_webwalker_source_recheck import fixture as event_fixture, read, row, slot


OTHER = 'The Vega charter was approved in 2037 at Cedar House.'
INCOMPLETE = ('The Orion charter approval took place in a hall. '
              'The hall name in this approval record is illegible.')
SCOPE_OLD = ('Use its\nentity_scope and time_scope strings exactly only when that scope actually applies;\n'
             'otherwise return unknown/irrelevant.')
DRAFT_OLD = ('Correct that draft under the same ID or preserve sourced partial/unknown evidence;\n'
             'do not delete it or add other IDs unless a wildcard or replacement list permits it.')
CAPACITY_OLD = 'proof, or partial/unresolved if no such proof exists.'


def replace_original(engine, alias, text):
    old_source = engine.mapper.sources[alias]
    document = engine.docs[old_source['doc_id']]
    document.passage = text
    source, = build_source_spans(document.doc_id, document, 400)
    del engine.mapper.source_aliases[old_source['source_id']]
    engine.mapper.sources[alias] = {**source, 'id': alias, 'source_id': source['id']}
    engine.mapper.source_aliases[source['id']] = alias


def fixture(respond, original=OTHER, **settings):
    reader, engine, state, calls = event_fixture(respond, **settings)
    replace_original(engine, 's1', original)
    return reader, engine, state, calls


def output(*rows, **claims):
    return {'slots': [slot('approval_place', *rows, **claims)]}


def read_place(reader, document='drafting-note'):
    return read(reader, document, ('approval_place',))


def assert_reconciled_actual_system(calls):
    replacements = dict(_WEB_COMMON_REPLACEMENTS['SYSTEM'])
    for request in calls.requests:
        system = request['payload']['messages'][0]['content']
        for old in (SCOPE_OLD, DRAFT_OLD, CAPACITY_OLD):
            assert old not in system
            assert replacements[old] in system


def test_other_entity_without_applicable_fact_is_completed_empty_read():
    reader, engine, state, calls = fixture(lambda i, data: output())
    originals = deepcopy(engine.mapper.sources)
    read_place(reader)
    assert_reconciled_actual_system(calls)
    assert calls.requests[0]['data']['source_spans'][0]['text'] == OTHER
    assert len(calls.requests) == engine.ledger.used['llm'] == 1
    assert engine.ledger.used['json_repairs'] == 0
    assert not state.routes and not state.pending and not reader.evidence_obligations
    assert not reader.failed_batch_reviews and reader.batches[-1]['complete']
    assert reader.web_navigation_reads[0]['reading_status'] == 'no_relevant_evidence'
    assert engine.mapper.sources == originals


@pytest.mark.parametrize('stance', ['partial', 'unknown'])
def test_genuine_target_incomplete_original_retains_its_scoped_source_issue(stance):
    incomplete = row('genuine-target-gap', None, ['s1'], stance)
    incomplete['reason'] = 'This record describes the target approval, but its hall name is illegible.'
    reader, engine, state, calls = fixture(lambda i, data: output(incomplete), INCOMPLETE)
    read_place(reader)
    assert_reconciled_actual_system(calls)
    assert len(calls.requests) == 1 and engine.ledger.used['json_repairs'] == 0
    assert not state.valid()[0] and state.pending == {'approval_place'}
    issue, = reader.evidence_obligations.values()
    assert issue['source_ids'] == [engine.mapper.sources['s1']['source_id']]
    assert not reader.web_navigation_reads and not reader.failed_batch_reviews


def test_required_source_free_draft_is_corrected_as_same_id_sourced_irrelevant():
    draft = row('required-draft', None, [], 'unknown')
    draft['reason'] = 'This original describes the Vega approval, not the requested Orion approval.'
    def respond(index, data):
        if index == 1:
            return output(draft)
        required = data['web_repair_edit_scope']['slots'][0]['required_observation_ids']
        assert required == ['required-draft']
        assert data['web_reading_protocol_diagnostics']['errors'][0]['observation_id'] == 'required-draft'
        assert any(entry.get('observation') == draft for entry in data['repair_scope']['failed'])
        return output({**draft, 'stance': 'irrelevant', 'source_ids': ['s1']})
    reader, engine, state, calls = fixture(respond, max_repairs_per_request=1)
    originals = deepcopy(engine.mapper.sources)
    read_place(reader)
    assert_reconciled_actual_system(calls)
    assert len(calls.requests) == engine.ledger.used['llm'] == 2
    assert engine.ledger.used['json_repairs'] == 1
    assert reader.batches[-1]['complete'] and not reader.failed_batch_reviews
    assert not state.routes and not state.pending and not reader.evidence_obligations
    assert engine.mapper.sources == originals


@pytest.mark.parametrize('repair', ['irrelevant', 'partial', 'unknown', 'empty'])
def test_citation_capacity_review_keeps_required_id_and_does_not_force_unknown(repair):
    original = OTHER if repair in ('irrelevant', 'empty') else INCOMPLETE
    support = row('required-proof', 'Cedar House', ['s1'])
    def respond(index, data):
        if index == 1:
            return output(support)
        assert any(entry['feedback'].startswith('citation_capacity:')
                   for entry in data['repair_scope']['failed'])
        assert data['repair_scope']['failed'][0]['observation']['id'] == 'required-proof'
        assert data['source_spans'][0]['text'] == original
        if repair == 'empty':
            return output()
        review = row('required-proof', None, ['s1'], repair)
        review['reason'] = ('The original describes a different charter approval.' if repair == 'irrelevant'
                            else 'The target approval is explicit, but its hall name is illegible.')
        return output(review)
    reader, engine, state, calls = fixture(respond, original, max_repairs_per_request=1)
    def capacity_feedback(rows, rejectable, *args, **kwargs):
        # Only the mandatory downstream-capacity decision is injected. The full
        # request, draft capture, repair schema and validation use production code.
        return {(entry['variable'], entry['id']): 'citation_capacity: invented mandatory handoff boundary'
                for entry in rows if entry['stance'] == 'support'
                and (entry['variable'], entry['id']) in rejectable}
    reader._handoff_failures = capacity_feedback
    read_place(reader)
    assert_reconciled_actual_system(calls)
    assert len(calls.requests) == engine.ledger.used['llm'] == 2
    assert engine.ledger.used['json_repairs'] == 1 and not state.routes
    if repair == 'empty':
        assert reader.failed_batch_reviews and not reader.batches[-1]['complete']
        assert state.pending == {'approval_place'}
        assert any(failure['id'] == 'required-proof' for record in reader.failed_batch_reviews.values()
                   for failure in record['failed'])
    else:
        assert not reader.failed_batch_reviews and reader.batches[-1]['complete']
        assert bool(reader.evidence_obligations) == (repair != 'irrelevant')
        assert state.pending == ({'approval_place'} if repair != 'irrelevant' else set())


def test_new_unrelated_window_does_not_clear_a_genuine_old_source_issue():
    gap = row('target-gap', None, ['s1'], 'partial')
    reader, engine, state, calls = fixture(lambda i, data: output(gap) if i == 1 else output(), INCOMPLETE)
    replace_original(engine, 's2', OTHER)
    read_place(reader)
    old_issue = deepcopy(reader.evidence_obligations)
    read_place(reader, 'approval-record')
    assert_reconciled_actual_system(calls)
    actual = calls.requests[-1]['data']
    assert {source['id'] for source in actual['source_spans']} == {'s1', 's2'}
    assert actual['web_source_review']['cards'][0]['original_source']['text'] == INCOMPLETE
    assert reader.evidence_obligations == old_issue and state.pending == {'approval_place'}
    assert not state.routes and not reader.failed_batch_reviews
    assert len(calls.requests) == 2 and engine.ledger.used['json_repairs'] == 0


def test_old_misclassified_source_still_needs_explicit_original_review_to_settle():
    def respond(index, data):
        if index == 1:
            return output(row('old-model-issue', None, ['s1'], 'unknown'))
        issue, = data['evidence_obligations']
        return output(row('target-place', 'Pine Hall', ['s2']),
                      row('old-original-review', None, ['s1'], 'irrelevant'),
                      resolved_obligation_ids=[issue['id']])
    reader, engine, state, calls = fixture(respond)
    read_place(reader)
    assert reader.evidence_obligations
    read_place(reader, 'approval-record')
    assert_reconciled_actual_system(calls)
    assert len(calls.requests) == 2 and engine.ledger.used['json_repairs'] == 0
    assert not reader.evidence_obligations and not state.pending and not reader.failed_batch_reviews
    assert state.valid()[0]['approval_place'] == 'Pine Hall'


def test_ordinary_empty_or_irrelevant_guidance_cannot_reclassify_a_protected_counter():
    counter = None
    def respond(index, data):
        nonlocal counter
        if index == 1:
            return output(row('known-place', 'Pine Hall', ['s2']))
        if index == 2:
            known, = data['known_observations']
            counter = row('protected-counter', None, ['s1'], 'contradiction', [known['id']])
            return {**output(counter), 'invalid_envelope': True}
        protected = [entry for failure in data['repair_scope']['failed']
                     for entry in failure.get('required_counter_observations', [])]
        assert counter in protected
        return output({**counter, 'stance': 'irrelevant', 'retract_ids': []})
    reader, engine, state, calls = fixture(respond, max_repairs_per_request=1)
    read_place(reader, 'approval-record')
    route, = state.routes
    read_place(reader)
    assert_reconciled_actual_system(calls)
    assert len(calls.requests) == 3 and engine.ledger.used['json_repairs'] == 1
    assert not state.routes[route]['revoked']
    assert state.pending == {'approval_place'} and reader.failed_batch_reviews
    protected = [entry for record in reader.failed_batch_reviews.values() for failure in record['failed']
                 for entry in failure.get('required_counter_observations', [])]
    assert any(entry['id'] == counter['id'] and entry['stance'] == 'contradiction'
               and entry['retract_ids'] == counter['retract_ids']
               and entry['source_ids'] == [engine.mapper.sources['s1']['source_id']] for entry in protected)


def test_empty_scope_guidance_cannot_discard_valid_frozen_partial_or_required_draft():
    partial = row('frozen-target-gap', None, ['s1'], 'partial')
    invalid = row('required-source-review', None, ['not-offered'], 'unknown')
    def respond(index, data):
        if index == 1:
            return output(partial, invalid)
        assert data['repair_scope']['frozen_observation_ids'] == {'approval_place': ['frozen-target-gap']}
        assert data['source_spans'][0]['text'] == INCOMPLETE
        return output()
    reader, engine, state, calls = fixture(respond, INCOMPLETE, max_repairs_per_request=1)
    read_place(reader)
    assert_reconciled_actual_system(calls)
    assert len(calls.requests) == 2 and engine.ledger.used['json_repairs'] == 1
    assert state.pending == {'approval_place'} and reader.evidence_obligations and reader.failed_batch_reviews
    assert not reader.batches[-1]['complete'] and not state.routes


@pytest.mark.parametrize('repair_valid', [False, True])
def test_mixed_empty_status_with_source_free_unknown_requires_explicit_same_id_correction(repair_valid):
    draft = row('required-absence-draft', None, [], 'unknown')
    mixed = output(draft)
    mixed['slots'][0]['reading_status'] = 'no_relevant_evidence'
    def respond(index, data):
        if index == 1:
            return mixed
        assert any(entry.get('observation') == draft for entry in data['repair_scope']['failed'])
        assert data['web_repair_edit_scope']['slots'][0]['required_observation_ids'] == [draft['id']]
        return output({**draft, 'stance': 'irrelevant', 'source_ids': ['s1']}) if repair_valid else mixed
    reader, engine, state, calls = fixture(respond, max_repairs_per_request=1)
    read_place(reader)
    assert_reconciled_actual_system(calls)
    assert len(calls.requests) == 2 and engine.ledger.used['json_repairs'] == 1
    assert not state.routes and not reader.evidence_obligations
    assert bool(reader.failed_batch_reviews) is (not repair_valid)
    assert reader.batches[-1]['complete'] is repair_valid
    assert state.pending == (set() if repair_valid else {'approval_place'})


@pytest.mark.parametrize('boundary', [
    {'task': {'execution': 'compose'}}, {'audit_instruction': 'Audit the originals.'},
    {'public_output_question': 'Compose the answer.'}, {'terminal_repair': {'expected_value': 'unchanged'}}])
def test_three_scope_reconciliations_leave_compose_audit_terminal_bytes_unchanged(boundary):
    reader, engine, _, calls = fixture(lambda i, data: output())
    data = reader._payload(engine.steps[0], 'Read approval place', ['approval_place'], ['s1'])
    data['future_mandatory_scope_field'] = {'nested': ['retain', {'original': True}]}
    data.update(boundary)
    before = deepcopy(data)
    common = JointReader._system(data)
    system = WebJointReader._system(data)
    assert system.startswith(common)
    for old in (SCOPE_OLD, DRAFT_OLD, CAPACITY_OLD):
        assert old in common
        assert old in system
        assert dict(_WEB_COMMON_REPLACEMENTS['SYSTEM'])[old] not in system
    for wire, _ in reader._wire_candidates(data):
        assert wire['future_mandatory_scope_field'] == before['future_mandatory_scope_field']
    assert data == before and not calls.requests
