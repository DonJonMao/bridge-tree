"""Single paid fresh-window reads with exact offline counters and real validators."""
from copy import deepcopy

import pytest

from dagbt.reasoning import InputOverflow
from dagbt.transport import digest
from dagbt.webwalker_reading import WebJointReader
from test_webwalker_reading import (ExactCounts, gap_response, observation, read,
                                    response, retained_failure_fixture, visible, web_fixture)


def fixture(respond=None, **settings):
    _, engine, state, calls = web_fixture(respond, reasoning_output_tokens=4096, **settings)
    return WebJointReader(engine, state), engine, state, calls


def test_primary_request_succeeds_without_synthetic_worst_case_repair_room():
    reader, engine, state, calls = fixture(lambda i, data: response(observation()))
    calls.count_reasoning_tokens = ExactCounts(9000)
    settings, limits, originals = deepcopy(engine.s), deepcopy(engine.ledger.limits), deepcopy(engine.mapper.sources)
    read(reader)
    assert state.valid()[0]['history'] == ['piano'] and not state.pending
    assert len(calls.requests) == engine.ledger.used['llm'] == 1
    assert engine.ledger.used['json_repairs'] == 0 and reader.batches[-1]['complete']
    selection, = reader.web_single_shot_reads
    assert selection['actual_total_tokens'] <= 16384
    assert selection['rejected_full_forecast']['forecast_total_tokens'] > 16384
    assert selection['additional_local_repairs_allowed'] == 0
    assert selection['new_source_ids'] == [engine.mapper.sources['s1']['source_id']]
    assert selection['status'] == 'response_received'
    assert calls.requests[0]['payload']['max_tokens'] == 4096
    assert engine.s == settings and engine.ledger.limits == limits and engine.mapper.sources == originals


def test_invalid_single_response_preserves_old_issue_and_new_protected_counter_without_repair():
    old = observation('old-ambiguity', ['s1'], stance='unknown')
    old['value'] = None
    reader, engine, state, calls = fixture(lambda i, data: response(old))
    read(reader, 'piano', 'old-issue')
    old_issues = deepcopy(reader.evidence_obligations)
    state.integrate([reader._observation(observation('prior', ['s1']), 'history', visible(reader),
                                        engine.steps[0])], {'history'})
    route = next(iter(state.routes))
    counter = observation('new-protected-counter', ['s2'], stance='contradiction', retract_ids=[route])
    counter['value'] = None
    malformed = response(counter)
    del malformed['slots'][0]['reading_status']
    calls.respond = lambda i, data: deepcopy(malformed)
    calls.count_reasoning_tokens = ExactCounts(9000)
    before_calls, before_repairs = len(calls.requests), engine.ledger.used['json_repairs']
    originals, settings, limits = deepcopy(engine.mapper.sources), deepcopy(engine.s), deepcopy(engine.ledger.limits)
    read(reader, 'painting', 'new-source')
    assert len(calls.requests) == before_calls + 1
    assert engine.ledger.used['json_repairs'] == before_repairs
    assert reader.evidence_obligations == old_issues and state.pending == {'history'}
    assert not state.routes[route]['revoked'] and reader.failed_batch_reviews
    protected = [draft for record in reader.failed_batch_reviews.values() for failure in record['failed']
                 for draft in failure.get('required_counter_observations', [])]
    assert any(draft['id'] == counter['id'] and draft['retract_ids'] == [route] for draft in protected)
    assert {source['id'] for source in calls.requests[-1]['data']['source_spans']} == {'s1', 's2'}
    assert reader.web_single_shot_reads[-1]['local_repair_blocked'] is True
    assert not reader.batches[-1]['complete'] and not reader.web_navigation_reads
    assert engine.mapper.sources == originals and engine.s == settings and engine.ledger.limits == limits
    assert reader._active_web_single_shot is None and reader._selected_web_single_shot is None


@pytest.mark.parametrize('rename_alias', [False, True])
def test_query_rename_and_alias_change_cannot_rebuy_an_already_attempted_source(rename_alias):
    reader, engine, _, calls = fixture(lambda i, data: gap_response())
    calls.count_reasoning_tokens = ExactCounts(9000)
    read(reader, 'piano', 'first-query')
    if rename_alias:
        source = engine.mapper.sources.pop('s1')
        source['id'] = 'different-alias'
        engine.mapper.sources['different-alias'] = source
        engine.mapper.source_aliases[source['source_id']] = 'different-alias'
    before_budget = deepcopy(engine.ledger.public_dict())
    with pytest.raises(InputOverflow):
        read(reader, 'piano', 'entirely-renamed-query')
    assert len(calls.requests) == 1 and engine.ledger.public_dict() == before_budget
    assert len(reader.web_single_shot_reads) == 1


def test_failed_single_shot_attempt_is_not_undone_by_query_rename():
    invalid = response(observation('invalid-draft', ['inexistent']))
    reader, engine, state, calls = fixture(lambda i, data: deepcopy(invalid))
    calls.count_reasoning_tokens = ExactCounts(9000)
    read(reader, 'piano', 'paid-once')
    archive = deepcopy(reader.web_source_attempts)
    failures = deepcopy(reader.failed_batch_reviews)
    assert failures and state.pending == {'history'} and len(calls.requests) == 1
    read(reader, 'piano', 'renamed-failed-query')
    assert len(calls.requests) == 1 and reader.web_source_attempts == archive
    assert reader.failed_batch_reviews == failures and engine.ledger.used['json_repairs'] == 0


def test_actual_mandatory_closure_overflow_remains_rejected_with_every_old_original():
    old = observation('old-partial', ['s1'], stance='partial')
    old['value'] = None
    reader, engine, state, calls = fixture(lambda i, data: response(old))
    read(reader, 'piano', 'initial')
    old_issues, sources = deepcopy(reader.evidence_obligations), deepcopy(engine.mapper.sources)
    class TooLarge(ExactCounts):
        def __call__(self, stage, url, payload):
            result = super().__call__(stage, url, payload)
            if not self.records[-1][1]:
                result['count'] = 12025  # +4096+256+8 = 16385, one over original limit.
            return result
    calls.count_reasoning_tokens = TooLarge(9000)
    with pytest.raises(InputOverflow):
        read(reader, 'painting', 'too-large')
    assert len(calls.requests) == 1 and not reader.web_single_shot_reads
    assert reader.evidence_obligations == old_issues and state.pending == {'history'}
    assert engine.mapper.sources == sources
    offered = calls.count_reasoning_tokens.records[-1][0]
    assert all(text in offered['messages'][1]['content'] for text in ('I played piano', 'I enjoyed painting'))


@pytest.mark.parametrize('edge', ['audit', 'semantic', 'terminal', 'compose', 'llm_reserved', 'estimated'])
def test_fresh_fallback_does_not_grant_unavailable_or_terminal_permission(edge):
    reader, engine, _, calls = fixture()
    reader.current_identity = 'scope-check'
    calls.count_reasoning_tokens = ExactCounts(9000)
    operation, semantic, audit = 'joint_read', False, False
    step = deepcopy(engine.steps[0])
    if edge == 'audit':
        operation, audit = 'audit_joint', True
    elif edge == 'semantic':
        operation, semantic = 'semantic_compose', True
    elif edge == 'terminal':
        reader.current_terminal_output = True
    elif edge == 'compose':
        step['execution'] = 'compose'
    elif edge == 'llm_reserved':
        engine.ledger.reserve('llm', 'other-work', engine.ledger.remaining('llm') - engine.s['reserved_audit_calls'])
    else:
        class Estimate(ExactCounts):
            def __call__(self, stage, url, payload):
                result = super().__call__(stage, url, payload)
                result['token_count_is_estimate'] = True
                return result
        calls.count_reasoning_tokens = Estimate(9000)
    data = reader._payload(step, 'query', ['history'], ['s1'], semantic, audit=audit)
    reader._web_headroom_candidates = {digest(data): {'within_budget': False}}
    before = deepcopy(engine.ledger.public_dict())
    assert reader._single_shot_prefix(operation, step, 'query', ['history'], [['s1']], semantic, audit) == ([], 0)
    assert engine.ledger.public_dict() == before and not calls.requests and not reader.web_single_shot_reads


@pytest.mark.parametrize('new_source', [False, True])
def test_any_retained_failed_batch_must_use_existing_durable_recovery_authority(new_source):
    reader, engine, _, calls = retained_failure_fixture()
    calls.count_reasoning_tokens = ExactCounts(9000)
    reader.current_identity = 'old-failure-is-not-fresh'
    alias = 's2' if new_source else 's1'
    data = reader._payload(engine.steps[0], 'query', ['history'], [alias])
    assert data['failed_batch_reviews']
    reader._web_headroom_candidates = {digest(data): {'within_budget': False}}
    before, issues = deepcopy(reader.failed_batch_reviews), deepcopy(reader.evidence_obligations)
    assert reader._single_shot_prefix('joint_read', engine.steps[0], 'query', ['history'], [[alias]], False, False) == ([], 0)
    assert len(calls.requests) == 3 and reader.failed_batch_reviews == before
    assert reader.evidence_obligations == issues and not reader.web_single_shot_reads


def test_selection_is_pure_and_cannot_be_used_for_a_different_payload():
    reader, engine, state, calls = fixture()
    calls.count_reasoning_tokens = ExactCounts(9000)
    reader.current_identity = 'selected'
    before = deepcopy(engine.ledger.public_dict())
    pending = [['s1'], ['s2']]
    selected, count = reader._fitting_prefix('joint_read', engine.steps[0], 'query', ['history'], pending, False, False)
    assert selected == ['s1'] and count == 1 and pending == [['s1'], ['s2']]
    assert not calls.requests and engine.ledger.public_dict() == before
    assert not reader.web_source_attempts and not reader.source_exposures and not state.routes
    changed = reader._payload(engine.steps[0], 'changed-query', ['history'], ['s1'])
    wire, system = reader._wire_candidates(changed)[0]
    with pytest.raises(InputOverflow):
        reader._request_with_exposure('joint_read', changed, 'selected', wire, system,
                                      schema=reader._schema(changed))
    assert not calls.requests and engine.ledger.public_dict() == before and not reader.web_source_attempts


def test_single_shot_mode_does_not_leak_into_later_normal_batches_or_audit():
    reader, engine, _, calls = fixture(lambda i, data: response())
    calls.count_reasoning_tokens = ExactCounts(9000)
    read(reader, 'piano', 'one-shot')
    assert reader._active_web_single_shot is None
    audit = reader._payload(engine.steps[0], 'audit', ['history'], ['s1'], audit=True)
    assert reader._repair_fits('audit_joint_repair', audit, engine.steps[0], 'one-shot', 1)
    calls.count_reasoning_tokens = ExactCounts(1000)
    invalid = response(observation('later-draft', ['inexistent']))
    calls.respond = lambda index, data: invalid if index == 2 else response(observation('later-draft', ['s2']))
    read(reader, 'painting', 'later-normal')
    assert len(calls.requests) == 3 and engine.ledger.used['json_repairs'] == 1
    assert len(reader.web_single_shot_reads) == 1 and reader.batches[-1]['complete']



@pytest.mark.parametrize('restore_legacy', [False, True])
def test_ordinary_read_exposure_blocks_renamed_reordered_window_even_after_legacy_restore(restore_legacy):
    reader, engine, state, calls = fixture(lambda i, data: gap_response())
    calls.count_reasoning_tokens = ExactCounts(1000)
    reader.read(engine.steps[0], 'original query', ['history'], ['piano', 'painting'],
                'ordinary-query', discovery_doc_ids=['piano', 'painting'])
    assert len(calls.requests) == 1 and not reader.web_single_shot_reads
    assert {source['source_id'] for source in reader.source_exposures[0]['sources']} == {
        engine.mapper.sources[alias]['source_id'] for alias in ('s1', 's2')}
    if restore_legacy:
        snapshot = reader.obligation_snapshot()
        reader = WebJointReader(engine, state)
        reader.restore_obligations(snapshot)
        assert reader.source_exposures and not reader.web_source_attempts
    calls.count_reasoning_tokens = ExactCounts(9000)
    before = deepcopy(engine.ledger.public_dict())
    with pytest.raises(InputOverflow):
        reader.read(engine.steps[0], 'entirely renamed query', ['history'], ['painting', 'piano'],
                    'renamed-and-reordered', discovery_doc_ids=['painting', 'piano'])
    assert len(calls.requests) == 1 and engine.ledger.public_dict() == before
    assert not reader.web_single_shot_reads


@pytest.mark.parametrize('failure', ['transport', 'tokenizer'])
def test_attempt_failure_keeps_source_ownership_and_mandatory_unread_state(failure):
    reader, engine, state, calls = fixture(lambda i, data: gap_response())
    counter = ExactCounts(9000)
    if failure == 'transport':
        def respond(index, data):
            raise ConnectionError('Scripted transport failure after attempt registration')
        calls.respond = respond
        calls.count_reasoning_tokens = counter
    else:
        def count(stage, url, payload):
            if reader.source_exposures:
                raise ConnectionError('Scripted tokenizer failure after attempt registration')
            return counter(stage, url, payload)
        calls.count_reasoning_tokens = count
    read(reader, 'piano', 'attempt-failed')
    assert len(calls.requests) == (1 if failure == 'transport' else 0)
    assert engine.ledger.used['json_repairs'] == 0
    assert reader.web_source_attempts[0]['status'] == 'failed_or_not_sent'
    assert reader.web_source_attempts[0]['source_ids'] == [engine.mapper.sources['s1']['source_id']]
    assert reader.source_exposures and state.pending == {'history'} and reader.failed_batch_reviews
    exposure = reader.source_exposures[0]
    assert exposure['request_status'] == ('failed' if failure == 'transport' else 'not_sent')
    assert reader._active_web_single_shot is None and reader._selected_web_single_shot is None
    # A renamed request cannot make that original source fresh after failure.
    data = reader._payload(engine.steps[0], 'new query', ['history'], ['s1'])
    assert reader._single_shot_new_source_ids(data, ['s1']) == []
    calls.count_reasoning_tokens = ExactCounts(9000)
    before = deepcopy(engine.ledger.public_dict())
    read(reader, 'piano', 'renamed-after-failure')
    assert engine.ledger.public_dict() == before
    assert len(calls.requests) == (1 if failure == 'transport' else 0)


def test_actual_parent_binding_change_permits_same_source_under_new_grounding_only():
    from dagbt.fact_state import FactState
    _, engine, old_state, calls = fixture(
        lambda i, data: {'slots': [{'variable': variable, 'observations': [], 'unresolved': [],
                                   'reading_status': 'no_relevant_evidence'}
                                  for variable in data['variables']]})
    parent_step = {'output_slot': 'seed', 'question': 'Find target entity', 'inputs': [],
                   'execution': 'retrieval', 'answer_type': 'fact'}
    steps = [parent_step, *deepcopy(engine.steps)]
    steps[1]['inputs'] = ['seed']
    program = deepcopy(old_state.program)
    program['variables']['seed'] = {'type': 'entity', 'demand': 'seed'}
    state = FactState(program, old_state.contract, steps, 'suggestion')
    engine.steps = steps
    reader = WebJointReader(engine, state)
    def parent(value, source):
        return {'variable': 'seed', 'stance': 'support', 'value': value,
                'source_ids': [engine.mapper.sources[source]['source_id']],
                **state.scope('seed'), 'parent_versions': {}, 'retract_ids': [],
                'reason': 'Scripted original states target entity.'}
    state.integrate([parent('Entity A', 's3')])
    calls.count_reasoning_tokens = ExactCounts(9000)
    reader.read(steps[1], 'Read history for Entity A', ['history'], ['piano'],
                'entity-a-query', discovery_doc_ids=['piano'])
    first = deepcopy(reader.web_source_attempts[0]['context'])
    data = reader._payload(steps[1], 'renamed Entity A query', ['history'], ['s1'])
    assert reader._single_shot_new_source_ids(data, ['s1']) == []
    assert len(calls.requests) == 1
    previous_route = state.valid()[2]['seed'][0]
    counter = {'variable': 'seed', 'stance': 'contradiction', 'value': None,
               'source_ids': [engine.mapper.sources['s2']['source_id']],
               **state.scope('seed'), 'parent_versions': {}, 'retract_ids': [previous_route],
               'reason': 'Explicit scripted correction to target entity.'}
    state.integrate([counter, parent('Entity B', 's2')])
    data = reader._payload(steps[1], 'Read history for Entity B', ['history'], ['s1'])
    assert reader._single_shot_new_source_ids(data, ['s1']) == [engine.mapper.sources['s1']['source_id']]
    assert reader._single_shot_context(data)['parent_bindings']['seed']['version'] > first['parent_bindings']['seed']['version']
    reader.read(steps[1], 'Read history for Entity B', ['history'], ['piano'],
                'entity-b-query', discovery_doc_ids=['piano'])
    assert len(calls.requests) == 2 and len(reader.web_single_shot_reads) == 2
    assert reader.web_source_attempts[-1]['context']['parent_bindings']['seed']['value'] == 'Entity B'
    assert engine.ledger.used['json_repairs'] == 0 and not state.pending
