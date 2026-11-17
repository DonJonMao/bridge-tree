"""Independent grounding vetoes use invented sources and the paid Reasoner path."""
from copy import deepcopy
import json

from test_webwalker_source_recheck import OLD, NEW, fixture, read, row, slot


def verdicts(data, verdict='entailed'):
    return {'reviews': [{'candidate_id': candidate['candidate_id'], 'verdict': verdict,
                         'reason': 'Check the requested approval event against the actual original.'}
                        for candidate in data['candidates']]}


def test_wrong_event_is_vetoed_and_only_model_can_correct_the_same_named_draft():
    def respond(index, data):
        if 'candidates' in data:
            candidate, = data['candidates']
            assert data['source_spans'][0]['text'] == OLD
            assert 'reason' not in candidate['observation']
            assert not data['retraction_targets']
            assert (('establish the complete proposed value' in candidate['claim_to_check'])
                    if index == 2 else all(text in candidate['claim_to_check'] for text in (
                        'Assess that inapplicability claim, not whether they support an answer',
                        'This claim concerns these cited spans',
                        'unrelated text is inapplicable here',
                        'when the originals still concern the requested scope',
                        'Mere answer absence does not prove inapplicability',
                        'genuine scoped support, partial evidence or counterevidence')))
            return verdicts(data, 'not_entailed' if index == 2 else 'entailed')
        if index == 1:
            return {'slots': [slot('approval_year', row('named-year', 2032, ['s1']))]}
        failed, = data['repair_scope']['failed']
        assert failed['id'] == 'named-year' and failed['observation']['value'] == 2032
        return {'slots': [slot('approval_year', row('named-year', None, ['s1'], 'irrelevant'))]}

    reader, engine, state, calls = fixture(respond, grounding_review=True, max_repairs_per_request=1)
    read(reader, 'drafting-note', ('approval_year',))
    assert not state.routes and not reader.evidence_obligations and not reader.failed_batch_reviews
    assert [record['operation'] for record in engine.reasoner.requests] == [
        'joint_read', 'web_grounding_review', 'joint_read_repair', 'web_grounding_review']
    assert ('An independent grounding review veto or uncertain verdict concerns proposed '
            'entailment, never itself scoped partial/unknown evidence.' in ' '.join(
                calls.requests[2]['payload']['messages'][0]['content'].split()))
    assert [exposure['logical_call_index'] for exposure in reader.source_exposures] == [1, 3]
    assert engine.ledger.used['llm'] == len(calls.requests) == 4
    assert engine.ledger.used['json_repairs'] == 1 and reader.batches[-1]['complete']
    assert json.loads(engine.reasoner.requests[0]['raw_output'])['slots'][0]['observations'][0]['value'] == 2032
    assert not reader.web_navigation_reads  # No automatic conversion to an empty read.


def test_correct_candidates_share_one_review_with_all_offered_original_context():
    def respond(index, data):
        if 'candidates' in data:
            assert len(data['candidates']) == 2
            assert data['source_spans'][0]['text'] == NEW
            return verdicts(data)
        return {'slots': [slot('approval_year', row('year', 2041, ['s2'])),
                          slot('approval_place', row('place', 'Pine Hall', ['s2']))]}

    reader, engine, state, calls = fixture(respond, grounding_review=True)
    read(reader, 'approval-record')
    assert state.valid()[0] == {'approval_year': 2041, 'approval_place': 'Pine Hall'}
    assert engine.reasoner.sequence == engine.ledger.used['llm'] == len(calls.requests) == 2
    exposure, = reader.source_exposures
    assert exposure['logical_call_index'] == 1 and exposure['operation'] == 'joint_read'
    review = engine.reasoner.requests[1]
    actual = calls.requests[1]['payload']
    assert review['input_tokens_local'] == engine.reasoner._count_payload('web_grounding_review', actual)['count']
    assert actual['max_tokens'] <= engine.s['reasoning_output_tokens']
    assert not engine.ledger.used['json_repairs']
    assert engine.reasoner.last_response is engine.reasoner.requests[0]
    assert reader.batches[-1]['input_tokens'] == engine.reasoner.requests[0]['input_tokens_local']
    assert reader.batches[-1]['read_logical_call_index'] == 1


def test_empty_reads_and_compose_audit_boundaries_make_no_independent_call():
    reader, engine, state, calls = fixture(
        lambda index, data: {'slots': [slot(variable) for variable in data['requested_slots']]},
        grounding_review=True)
    read(reader, 'drafting-note')
    assert engine.ledger.used['llm'] == len(calls.requests) == 1 and not state.routes
    data = reader._payload(engine.steps[0], 'Review approval', ['approval_year'], ['s1'])
    reader._web_grounding_decisions = {}
    response = {'slots': [slot('approval_year', row('year', 2032, ['s1']))]}
    for boundary in ({'task': {'execution': 'compose'}}, {'audit_instruction': 'Audit'},
                     {'public_output_question': 'Answer'}, {'terminal_repair': {}}):
        reader._review_grounding_candidates(response, {**deepcopy(data), **boundary}, 1)
    assert engine.ledger.used['llm'] == len(calls.requests) == 1


def test_unavailable_budget_or_invalid_review_holds_drafts_and_preserves_audit_call():
    for limited_budget in (True, False):
        def respond(index, data):
            if 'candidates' in data:
                return {'reviews': []}  # Malformed review never grants acceptance.
            return {'slots': [slot('approval_year', row('held-year', 2041, ['s2']))]}
        reader, engine, state, calls = fixture(respond, grounding_review=True, max_repairs_per_request=0)
        if limited_budget:
            engine.ledger.limits['llm'] = 2
        read(reader, 'approval-record', ('approval_year',))
        assert not state.routes and state.versions['approval_year'] == 0
        assert reader.failed_batch_reviews and not reader.batches[-1]['complete']
        record, = reader.failed_batch_reviews.values()
        failed, = record['failed']
        assert failed['id'] == 'held-year'
        assert failed['observation']['id'] == 'held-year' and failed['observation']['value'] == 2041
        assert engine.reasoner.last_response is engine.reasoner.requests[0]
        assert json.loads(engine.reasoner.last_response['raw_output'])['slots'][0]['observations'][0]['id'] == 'held-year'
        assert reader.source_exposures[0]['logical_call_index'] == 1
        assert engine.ledger.used['llm'] == len(calls.requests) == (1 if limited_budget else 2)
        if limited_budget:
            assert engine.ledger.remaining('llm') == engine.s['reserved_audit_calls']


def test_unwarranted_counter_is_vetoed_before_protection_without_new_target_authority():
    def respond(index, data):
        if 'candidates' in data:
            candidate, = data['candidates']
            if candidate['observation']['stance'] == 'contradiction':
                target, = data['retraction_targets']
                assert candidate['observation']['retract_ids'] == [target['id']]
                assert {source['text'] for source in data['source_spans']} == {OLD, NEW}
                return verdicts(data, 'not_entailed')
            return verdicts(data)
        if index == 1:
            return {'slots': [slot('approval_year', row('year', 2041, ['s2']))]}
        if index == 3:
            target, = data['known_observations']
            return {'slots': [slot('approval_year', row('counter', None, ['s1'],
                'contradiction', [target['id']]))]}
        failed, = data['repair_scope']['failed']
        assert failed['id'] == 'counter' and not failed.get('required_counter_observations')
        return {'slots': [slot('approval_year', row('counter', None, ['s1'], 'irrelevant'))]}

    reader, engine, state, _ = fixture(respond, grounding_review=True, max_repairs_per_request=1)
    read(reader, 'approval-record', ('approval_year',))
    target, = state.routes
    read(reader, 'drafting-note', ('approval_year',))
    assert state.valid()[0]['approval_year'] == 2041 and not state.routes[target]['revoked']
    assert not reader.failed_batch_reviews and reader.batches[-1]['complete']
    assert [exposure['logical_call_index'] for exposure in reader.source_exposures] == [1, 3, 5]
    assert engine.ledger.used['llm'] == 6 and engine.ledger.used['json_repairs'] == 1
