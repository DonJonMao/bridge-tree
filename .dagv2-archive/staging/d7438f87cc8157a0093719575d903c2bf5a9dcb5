"""Generic offline navigation progress, using only invented source material.

The counter fixture measures exact serialized wire characters, not real tokens.
No model, tokenizer, dataset labels, external site, scoring or preparation is used.
"""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from dagbt.reasoning import InputOverflow, ProtocolError
from dagbt.transport import digest
from dagbt.webwalker_assessment import (PAUSED, candidate_identity, context_identity,
                                       current_assessment)
from dagbt.webwalker_control import WebResidualControl
from test_webwalker_navigation_refill import fixture, offered, assert_original_coordinates
from test_webwalker_reading import (gap_response, observation, read, response, web_fixture)


QUERY = 'Find the project details.'


def null_fixture(**options):
    bridge, engine, calls, fetched, events, feedback, identity = fixture(
        null=True, required_size=0, gap_size=0, **options)
    # Admit two complete 12-link windows, independent of tokenizer compression.
    engine.s['context_tokens'] = 50000
    bridge.settings['link_window'] = 12
    return bridge, engine, calls, fetched, events, feedback, identity


def until_pause(bridge, identity, node='project', query=QUERY):
    for _ in range(12):
        result = bridge.step(query, node, identity=identity)
        if result['trace']['search_status'] == PAUSED:
            return result
    pytest.fail('A complete unchanged null frontier did not pause within its original budget')


def test_two_null_fingerprints_then_one_distinct_reconsideration_do_not_burn_eight_cached_turns():
    bridge, engine, calls, fetched, _, _, identity = null_fixture()
    pages, frontier, limits = deepcopy(bridge.pages), deepcopy(bridge._observed_links(bridge.sessions[identity])), deepcopy(engine.ledger.limits)
    result = until_pause(bridge, identity)
    wires = [digest(payload) for payload in calls.requests]
    assert len(wires) == len(set(wires)) == engine.ledger.used['llm'] == 3
    data = [json.loads(payload['messages'][1]['content']) for payload in calls.requests]
    assert [len(row['links']) for row in data] == [12, 12, 12]
    assert set(link['url'] for link in data[0]['links']).isdisjoint(link['url'] for link in data[1]['links'])
    assert 'navigation_assessment' not in data[0] and 'navigation_assessment' not in data[1]
    assert data[2]['navigation_assessment']['phase'] == 'one_bounded_reconsideration'
    assert 'No branch is forced' in calls.requests[2]['messages'][0]['content']
    before = deepcopy(engine.ledger.public_dict()), len(calls.counts)
    for _ in range(8):
        assert bridge.step(QUERY, 'project', identity=identity)['trace']['search_status'] == PAUSED
    assert (engine.ledger.public_dict(), len(calls.counts)) == before
    diagnostic = result['trace']['navigation_assessment']
    assert diagnostic['complete_null_sweep'] and diagnostic['reconsideration_used']
    assert diagnostic['absence_claim'] is False
    assert not bridge.has_actionable_links('project', identity)
    assert bridge.has_unvisited_links('project', identity)
    assert bridge.pages == pages and bridge._observed_links(bridge.sessions[identity]) == frontier
    assert bridge.sessions[identity]['skipped'] == [] and fetched == ['https://fixture.example/']
    assert engine.ledger.limits == limits and not engine.ledger.used.get('json_repairs', 0)


def test_only_the_actual_final_admitted_null_window_counts_and_partial_sweep_stays_live():
    bridge, engine, calls, _, _, _, identity = fixture(null=True)
    original = deepcopy(bridge._observed_links(bridge.sessions[identity]))
    result = bridge.step(QUERY, 'project', identity=identity)
    assert result['trace']['search_status'] == 'empty_probe'
    data = offered(calls)
    assert len(data['links']) < len(original)
    _, record = current_assessment(bridge, bridge.sessions[identity])
    assert set(record['null_candidates']) == {candidate_identity(link) for link in data['links']}
    assert len(record['null_candidates']) < len(original) and not record['reconsideration_used']
    assert bridge.has_actionable_links('project', identity)
    assert any(len(count['data']['links']) > len(data['links']) for count in calls.counts)
    assert len(record['null_windows']) == 1
    assert all('text' not in source and source['source_record_sha256'] and source['excerpt_sha256']
               for source in record['null_windows'][0]['source_pages'])
    assert_original_coordinates(engine, data)
    assert bridge._observed_links(bridge.sessions[identity]) == original


def test_reconsideration_may_select_an_original_intermediate_link_without_forcing_it():
    bridge, engine, calls, fetched, _, _, identity = null_fixture()
    original_get = calls.get
    def choose(stage, url, payload, **options):
        result = original_get(stage, url, payload, **options)
        data = json.loads(payload['messages'][1]['content'])
        if 'navigation_assessment' in data:
            result['response']['choices'][0]['message']['content'] = json.dumps({'link_id': data['links'][-1]['id']})
        return result
    calls.get = choose
    for _ in range(2):
        assert bridge.step(QUERY, 'project', identity=identity)['trace']['search_status'] == 'empty_probe'
    result = bridge.step(QUERY, 'project', identity=identity)
    assert len(result['local_candidate_ids']) == 1 and fetched[-1] == offered(calls)['links'][-1]['url']
    assert_original_coordinates(engine, offered(calls))
    assert engine.ledger.used['llm'] == 3 and not engine.ledger.used.get('json_repairs', 0)


def test_paid_repair_overflow_records_no_null_and_cannot_buy_another_attempt():
    bridge, engine, calls, fetched, _, _, identity = fixture(paid_repair_overflow=True)
    with pytest.raises(InputOverflow):
        bridge.step(QUERY, 'project', identity=identity)
    _, record = current_assessment(bridge, bridge.sessions[identity])
    assert not record['null_candidates'] and not record['null_windows']
    assert record['pause_reason'] == 'paid_navigation_repair_unavailable'
    before = deepcopy(engine.ledger.public_dict()), len(calls.requests), len(calls.counts)
    assert bridge.step(QUERY, 'project', identity=identity)['trace']['search_status'] == PAUSED
    assert (engine.ledger.public_dict(), len(calls.requests), len(calls.counts)) == before
    assert len(calls.requests) == 1 and fetched == ['https://fixture.example/']
    assert engine.s['max_repairs_per_request'] == 2 and engine.ledger.limits['json_repairs'] == 6


def test_invalid_navigation_keeps_original_two_repairs_and_does_not_count_as_null():
    bridge, engine, calls, _, _, _, identity = null_fixture()
    original_get = calls.get
    def invalid(stage, url, payload, **options):
        result = original_get(stage, url, payload, **options)
        result['response']['choices'][0]['message']['content'] = json.dumps({'link_id': 'unobserved'})
        return result
    calls.get = invalid
    with pytest.raises(ProtocolError):
        bridge.step(QUERY, 'project', identity=identity)
    _, record = current_assessment(bridge, bridge.sessions[identity])
    assert not record['null_candidates'] and not record['null_windows']
    assert len(calls.requests) == engine.ledger.used['llm'] == 3 and engine.ledger.used['json_repairs'] == 2
    assert bridge.step(QUERY, 'project', identity=identity)['trace']['search_status'] == PAUSED
    assert len(calls.requests) == 3 and bridge.sessions[identity]['skipped'] == []


def test_unfittable_remaining_original_cannot_replay_already_null_fit_siblings():
    bridge, engine, calls, _, _, _, identity = fixture(null=True, oversized_first=True, required_size=0, gap_size=0)
    original = deepcopy(bridge._observed_links(bridge.sessions[identity]))
    while True:
        result = bridge.step(QUERY, 'project', identity=identity)
        if result['trace']['search_status'] == PAUSED:
            break
        assert result['trace']['search_status'] == 'empty_probe'
        assert engine.ledger.used['llm'] < 10
    diagnostic = result['trace']['navigation_assessment']
    assert diagnostic['reason'] == 'no_admissible_unassessed_window'
    assert diagnostic['eligible_candidates'] == len(original)
    assert diagnostic['assessed_candidates'] == len(original) - 1
    assert not diagnostic['complete_null_sweep'] and not diagnostic['reconsideration_used']
    capacity = diagnostic['capacity_unavailable']
    assert capacity['error_type'] == 'InputOverflow' and capacity['preflight_overflows'] > 0
    assert capacity['paid_calls_in_failed_window'] == 0
    assert capacity['unassessed_original_links'] == original[:1]
    _, record = current_assessment(bridge, bridge.sessions[identity])
    assert len(record['null_candidates']) == len(original) - 1
    assert candidate_identity(original[0]) not in record['null_candidates']
    before = len(calls.requests), len(calls.counts), deepcopy(engine.ledger.public_dict())
    for _ in range(8):
        repeated = bridge.step(QUERY, 'project', identity=identity)
        assert repeated['trace']['search_status'] == PAUSED
        assert repeated['trace']['navigation_assessment'] == diagnostic
    assert (len(calls.requests), len(calls.counts), engine.ledger.public_dict()) == before
    assert bridge._observed_links(bridge.sessions[identity]) == original and bridge.sessions[identity]['skipped'] == []


@pytest.mark.parametrize('change', ['source', 'capacity', 'material'])
def test_material_original_or_capacity_change_reopens_while_presentation_and_history_do_not(change):
    bridge, engine, calls, _, _, feedback, identity = null_fixture()
    until_pause(bridge, identity)
    session = bridge.sessions[identity]
    old_context = context_identity(bridge, session)
    session['link_presentations'] = {url: count + 100 for url, count in session['link_presentations'].items()}
    session['history_only'] = ['ordinary log'] * 50
    engine.ledger.used['llm'] += 1
    feedback['accepted_empty_reads'].append(deepcopy(feedback['accepted_empty_reads'][0]))
    assert context_identity(bridge, session) == old_context
    assert not bridge.has_actionable_links('project', identity)
    if change == 'source':
        page = next(iter(bridge.pages.values()))
        page['document_hash'] = digest(['genuinely_changed_original', page['document_hash']])
    elif change == 'capacity':
        engine.s['context_tokens'] += 1000
    else:
        engine.residual_control.navigation_material = {'new_bound_parent_version': 1}
    assert context_identity(bridge, session) != old_context
    before = len(calls.requests)
    assert bridge.has_actionable_links('project', identity)
    assert bridge.step(QUERY, 'project', identity=identity)['trace']['search_status'] == 'empty_probe'
    assert len(calls.requests) == before + 1


def test_candidate_failure_removal_does_not_renew_reconsideration_or_destroy_originals():
    bridge, _, calls, _, _, _, identity = null_fixture()
    until_pause(bridge, identity)
    session = bridge.sessions[identity]
    context = context_identity(bridge, session)
    links = bridge._observed_links(session)
    bridge.failed.add(links[0]['url'])
    assert context_identity(bridge, session) == context
    assert not bridge.has_actionable_links('project', identity)
    assert bridge.step(QUERY, 'project', identity=identity)['trace']['search_status'] == PAUSED
    assert len(calls.requests) == 3 and len(next(iter(bridge.pages.values()))['document']['links']) == 24


def attach_material(bridge, engine, *, unknown=False):
    def respond(index, data):
        row = observation('ordinary-name-' + str(index), ['s1'], stance='unknown', value=None,
                          reason='Restated local uncertainty ' + str(index))
        row['value'] = None
        return response(row)
    reader, source_engine, state, _ = web_fixture(respond)
    if unknown:
        read(reader, identity='history-query')
    engine.mapper, engine.fact_state, engine.steps = source_engine.mapper, state, source_engine.steps
    engine.residual_control = SimpleNamespace(state=state, reader=reader, local_pools={})
    identity = 'history-query'
    bridge.step('Read historical activities', 'history', identity=identity)
    return reader, state, identity


def test_same_source_unknown_restatement_new_name_reason_and_duplicate_issue_do_not_renew_ticket():
    bridge, engine, calls, _, _, _, _ = null_fixture()
    reader, state, identity = attach_material(bridge, engine, unknown=True)
    until_pause(bridge, identity, 'history', 'Read historical activities')
    session = bridge.sessions[identity]
    before_context = context_identity(bridge, session)
    originals = deepcopy(reader.evidence_obligations)
    read(reader, identity=identity)
    issue = next(iter(reader.evidence_obligations.values()))
    issue['descriptions'].append('Another ordinary description of the same original source gap.')
    duplicate = {**deepcopy(issue), 'id': 'fresh-operational-name', 'origins': ['different-log-name']}
    reader.evidence_obligations[duplicate['id']] = duplicate
    assert context_identity(bridge, session) == before_context
    assert not bridge.has_actionable_links('history', identity)
    assert bridge.step('Read historical activities', 'history', identity=identity)['trace']['search_status'] == PAUSED
    assert len(calls.requests) == 3 and state.pending == {'history'} and not state.routes
    assert originals and len(reader.evidence_obligations) == 2  # Originals are never rewritten or erased.


@pytest.mark.parametrize('change', ['scope', 'new_issue_source', 'binding_version', 'counter', 'unread', 'discovery', 'review_authority'])
def test_real_relevant_material_changes_create_a_fresh_local_assessment(change):
    bridge, engine, _, _, _, _, _ = null_fixture()
    reader, state, identity = attach_material(bridge, engine, unknown=True)
    until_pause(bridge, identity, 'history', 'Read historical activities')
    before_context = context_identity(bridge, bridge.sessions[identity])
    issue = next(iter(reader.evidence_obligations.values()))
    if change == 'scope':
        issue['time_scope'] = 'new_actual_scope'
    elif change == 'new_issue_source':
        issue['source_ids'].append(engine.mapper.sources['s2']['source_id'])
    elif change == 'binding_version':
        state.versions['history'] += 1
    elif change == 'counter':
        state.routes['real-proof'] = {'id': 'real-proof', 'variable': 'history', 'stance': 'support',
            'value': ['piano'], 'source_ids': [engine.mapper.sources['s1']['source_id']],
            'entity_scope': 'user', 'time_scope': 'history', 'parent_versions': {},
            'retract_ids': [], 'reason': 'Actual original.',
            'revoked': [{'source_ids': [engine.mapper.sources['s2']['source_id']], 'reason': 'Actual counter.'}]}
    elif change == 'unread':
        reader.unread_obligations[identity, 's2'] = {'history'}
    elif change == 'discovery':
        reader.discovery_frontier[identity, 's2'] = reader._frontier_entry(engine.steps[0], ['history'], 's2', identity)
    else:
        record = {'id': 'failed-original', 'variable': 'history', 'task_id': 'history', 'phase': 'history',
                  'source_ids': [engine.mapper.sources['s1']['source_id']], 'failed': [],
                  'seen_source_ids': [engine.mapper.sources['s1']['source_id']],
                  'seen_parent_signatures': [reader._failed_parent_signature('history')]}
        reader.failed_batch_reviews[record['id']] = record
        engine.residual_control.local_pools['history'] = ['piano']
        before_context = context_identity(bridge, bridge.sessions[identity])
        engine.residual_control.local_pools['history'].append('painting')
    assert context_identity(bridge, bridge.sessions[identity]) != before_context
    assert bridge.has_actionable_links('history', identity)


def test_session_record_json_roundtrip_preserves_spent_ticket_and_scopes_are_separate():
    bridge, _, calls, _, _, _, identity = null_fixture()
    until_pause(bridge, identity)
    before_context = context_identity(bridge, bridge.sessions[identity])
    bridge.sessions = json.loads(json.dumps(bridge.sessions))
    assert context_identity(bridge, bridge.sessions[identity]) == before_context
    assert bridge.step(QUERY, 'project', identity=identity)['trace']['search_status'] == PAUSED
    assert len(calls.requests) == 3
    for key, node, query in [('other-query', 'project', 'Another subproblem'),
                             ('other-node', 'other', QUERY)]:
        bridge.step(query, node, identity=key)  # Deliver originals to that independent session.
        assert bridge.step(query, node, identity=key)['trace']['search_status'] == 'empty_probe'
    assert len(calls.requests) == 5


def test_actual_same_proof_and_counter_replays_do_not_renew_but_first_counter_does():
    bridge, engine, _, _, _, _, _ = null_fixture()
    reader, state, identity = attach_material(bridge, engine)
    first_source, second_source = [engine.mapper.sources[alias]['source_id'] for alias in ('s1', 's2')]
    proof = {**observation('first-model-name', [first_source]), 'variable': 'history'}
    state.integrate([proof])
    until_pause(bridge, identity, 'history', 'Read historical activities')
    session = bridge.sessions[identity]
    before = context_identity(bridge, session), deepcopy(state.versions)
    state.integrate([{**proof, 'id': 'new-model-name', 'reason': 'Same original, differently worded.'}])
    assert (context_identity(bridge, session), state.versions) == before
    assert not bridge.has_actionable_links('history', identity)
    route_id, = state.routes
    counter = {**observation('first-counter', [second_source], stance='contradiction', retract_ids=[route_id]),
               'variable': 'history', 'value': None}
    state.integrate([counter])
    assert context_identity(bridge, session) != before[0]
    assert bridge.has_actionable_links('history', identity) and not state.valid()[0]
    until_pause(bridge, identity, 'history', 'Read historical activities')
    before = context_identity(bridge, session), deepcopy(state.versions)
    state.integrate([{**counter, 'id': 'renamed-counter', 'reason': 'Same sourced counter restated.'}])
    assert (context_identity(bridge, session), state.versions) == before
    assert not bridge.has_actionable_links('history', identity)
    assert len(state.routes[route_id]['revoked']) == 2  # The full record remains intact.


def test_failed_obligation_batch_identity_is_not_a_source_alias_or_a_renewal_nonce():
    bridge, engine, _, _, _, _, _ = null_fixture()
    reader, state, identity = attach_material(bridge, engine)
    reader.e.s['max_repairs_per_request'] = 0
    reader.e.reasoner.calls.respond = lambda index, data: response(observation('invalid-source', ['unoffered']))
    read(reader, identity=identity)
    assert reader.failed_batch_reviews and reader.failed_obligations and state.pending == {'history'}
    session = bridge.sessions[identity]
    before = context_identity(bridge, session)
    assert all(batch not in engine.mapper.sources for _, batch in reader.failed_obligations)
    reader.failed_obligations[identity, 'ordinary-batch-log-name'] = {'history'}
    assert context_identity(bridge, session) == before
    assert len(reader.failed_obligations) == 2


def reading_control(respond=None, **settings):
    reader, engine, state, calls = web_fixture(respond, **settings)
    engine.fact_state = state
    engine.ledger.limits['web_actions'] = 36
    control = WebResidualControl(engine)
    control.reader = reader
    engine.residual_control = control
    engine.bridge = SimpleNamespace(has_actionable_links=lambda node_id, identity=None: True)
    identity = 'local-unknown-window'
    reader.discovery_frontier[identity, 's2'] = reader._frontier_entry(engine.steps[0], ['history'], 's2', identity)
    return control, reader, engine, state, calls, identity


def sourced_unknown(index, data):
    alias = data.get('web_reading_context', {}).get('new_window_source_ids', ['s1'])[0]
    row = observation('local-uncertainty-' + str(index), [alias], stance='unknown',
                      reason='This original leaves the historical date ambiguous.')
    row['value'] = None
    return response(row)


def test_valid_sourced_unknown_yields_to_live_branch_without_settling_or_absence_claim():
    control, reader, engine, state, calls, identity = reading_control(sourced_unknown)
    limits, sources, program = deepcopy(engine.ledger.limits), deepcopy(engine.mapper.sources), deepcopy(state.program)
    control.read_progress(engine.steps[0], 'Find activity evidence', ['history'], ['piano'], identity,
                          discovery_doc_ids=['piano'])
    assert reader.batches[-1]['complete'] and not reader.batches[-1]['failed_slots']
    assert state.pending == {'history'} and not state.valid()[0] and reader.evidence_obligations
    assert not reader.web_navigation_reads
    before = deepcopy(reader.obligation_snapshot()), len(calls.requests)
    assert not control.web_read_existing(engine.steps[0], 'Find activity evidence', ['history'], ['piano'], identity)
    assert (reader.obligation_snapshot(), len(calls.requests)) == before
    assert identity in control._web_resume_required and (identity, 's2') in reader.discovery_frontier
    assert engine.ledger.limits == limits and engine.mapper.sources == sources and state.program == program
    event = next(event for event in engine.events if event['event'] == 'web_document_window_yielded')
    assert event['reason'] == 'completed_window_without_binding_progress_with_live_link_frontier'


def test_genuine_binding_progress_does_not_yield_before_its_remaining_original_window():
    control, reader, engine, state, calls, identity = reading_control()
    control.read_progress(engine.steps[0], 'Find activity evidence', ['history'], ['piano'], identity,
                          discovery_doc_ids=['piano'])
    assert state.valid()[0]['history'] == ['piano'] and state.versions['history'] > 0
    assert identity not in control._web_yield_ready and (identity, 's2') in reader.discovery_frontier


@pytest.mark.parametrize('later_complete', [False, None])
def test_earlier_complete_empty_cannot_hide_a_later_invalid_or_capacity_batch(later_complete):
    control, reader, engine, _, _, identity = reading_control(lambda index, data: gap_response())
    original_read = reader.read
    def later_failure(*args, **options):
        changed = original_read(*args, **options)
        reader.batches.append({'identity': identity, 'operation': 'joint_read',
            'complete': later_complete, 'failed_slots': [] if later_complete is None else ['history']})
        return changed
    reader.read = later_failure
    control.read_progress(engine.steps[0], 'Find activity evidence', ['history'], ['piano'], identity,
                          discovery_doc_ids=['piano'])
    assert reader.web_navigation_reads and identity not in control._web_yield_ready


@pytest.mark.parametrize('options', [{'audit': True}, {'source_scope': 'mandatory_closure'}, {'semantic': True}, {'terminal_output': True}])
def test_audit_mandatory_or_terminal_reads_never_gain_an_ordinary_yield_ticket(options):
    control, reader, engine, _, _, identity = reading_control(sourced_unknown)
    mandatory = options.get('source_scope') == 'mandatory_closure'
    docs, step, variables = ([], engine.steps[1], ['suggestion']) if mandatory else (['piano'], engine.steps[0], ['history'])
    control.read_progress(step, 'Find activity evidence', variables, docs, identity,
                          **options)
    assert identity not in control._web_yield_ready


def test_unfinished_failed_review_blocks_navigation_yield_and_preserves_mandatory_work():
    bad = response(observation('required-draft', ['nonexistent-source']))
    control, reader, engine, state, _, identity = reading_control(lambda index, data: bad, max_repairs_per_request=0)
    control.read_progress(engine.steps[0], 'Find activity evidence', ['history'], ['piano'], identity,
                          discovery_doc_ids=['piano'])
    assert reader.failed_batch_reviews and state.pending == {'history'}
    assert identity not in control._web_yield_ready
    control._web_yield_ready.add(identity)  # A stale earlier ticket grants no failed-review bypass.
    original = deepcopy(reader.failed_batch_reviews)
    control.web_read_existing(engine.steps[0], 'Find activity evidence', ['history'], ['piano'], identity)
    assert not control._web_resume_required and reader.failed_batch_reviews == original
    assert state.pending == {'history'}


def test_fresh_page_read_cannot_consume_the_deferred_old_window_resume_turn():
    control, reader, engine, _, calls, identity = reading_control(sourced_unknown)
    step = engine.steps[0]
    control.read_progress(step, 'Find activity evidence', ['history'], ['piano'], identity, discovery_doc_ids=['piano'])
    assert not control.web_read_existing(step, 'Find activity evidence', ['history'], ['piano'], identity)
    assert identity in control._web_resume_required
    control.read_progress(step, 'Find activity evidence', ['history'], ['advice'], identity, discovery_doc_ids=['advice'])
    assert identity in control._web_resume_required and (identity, 's2') in reader.discovery_frontier
    before = len(calls.requests)
    control.web_read_existing(step, 'Find activity evidence', ['history'], ['piano', 'painting', 'advice'], identity)
    assert len(calls.requests) > before and identity not in control._web_resume_required
    assert any('s2' in request['data'].get('web_reading_context', {}).get('new_window_source_ids', [])
               for request in calls.requests[before:])
    assert any(event['event'] == 'web_document_window_resumed' for event in engine.events)
