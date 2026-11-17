"""Invented-source, offline navigation-hint projection boundaries.

Capacity units use the existing explicit full-wire character counter fixture,
not a real-model tokenizer claim. Production exact counting stays unchanged.
"""
from copy import deepcopy
import json

import pytest

from dagbt.reasoning import InputOverflow, ProtocolError
from dagbt.webwalker_browser import WebBridge
from test_webwalker_navigation_refill import fixture, offered, assert_original_coordinates
from test_webwalker_reading import web_fixture, read, gap_response, response, observation


def accepted_reader():
    reader, engine, state, calls = web_fixture(lambda i, data: gap_response('Try the observed archive.'))
    engine.docs['piano'].title = 'Original activity page'
    engine.docs['piano'].metadata['url'] = 'https://fictional.example/activity'
    read(reader, 'piano', 'same-query')
    return reader, engine, state, calls


def test_projection_groups_one_actual_exposure_with_exact_original_ranges_without_changing_archive():
    reader, engine, state, _ = accepted_reader()
    row = deepcopy(reader.web_navigation_reads[0])
    # Three requested variables sharing the same accepted source exposure.
    reader.web_navigation_reads = [{**deepcopy(row), 'variable': variable}
                                   for variable in ('activity', 'date', 'duration')]
    raw = reader.navigation_feedback('history', identity='same-query')
    signature, obligations = reader.material_signature(), deepcopy(reader.obligation_snapshot())
    projection = reader.navigation_feedback_projection('history', identity='same-query')
    assert projection['protocol'] == 'web_reading_feedback_projection_v2'
    assert projection['accepted_empty_read_count'] == 3
    assert projection['projected_empty_exposure_count'] == 1
    group, = projection['accepted_empty_reads']
    assert group['raw_empty_read_record_count'] == 3
    assert [item['variable'] for item in group['variable_hints']] == ['activity', 'date', 'duration']
    assert all(item['search_gaps'] == ['Try the observed archive.'] for item in group['variable_hints'])
    source = engine.mapper.sources['s1']
    assert group['documents'] == [{'doc_id':'piano', 'url':'https://fictional.example/activity',
        'title':'Original activity page', 'source_ranges':[[source['start'],source['end']]], 'source_count':1}]
    assert group['unique_source_count'] == 1 and group['unmapped_source_count'] == 0
    assert 'source_ids' not in group and group['grants_review_authority'] is False
    assert projection['grants_review_authority'] is False
    assert projection['evidence_semantics'] == 'navigation_hints_not_facts'
    projection['accepted_empty_reads'][0]['variable_hints'][0]['search_gaps'].append('caller mutation')
    assert reader.navigation_feedback('history', identity='same-query') == raw
    assert reader.material_signature() == signature and reader.obligation_snapshot() == obligations
    assert not state.routes and not state.pending


def test_projection_isolates_queries_tasks_and_distinct_paid_exposures():
    reader, _, _, _ = accepted_reader()
    row = deepcopy(reader.web_navigation_reads[0])
    reader.web_navigation_reads.extend([
        {**deepcopy(row), 'query_identity':'other-query'},
        {**deepcopy(row), 'task_id':'other-task'},
        {**deepcopy(row), 'request_identity':'different-paid-request', 'logical_call_index':2}])
    projection = reader.navigation_feedback_projection('history', identity='same-query')
    assert projection['accepted_empty_read_count'] == projection['projected_empty_exposure_count'] == 2
    assert {group['request_identity'] for group in projection['accepted_empty_reads']} == {
        row['request_identity'], 'different-paid-request'}
    assert reader.navigation_feedback_projection('history', identity='not-this-query')['accepted_empty_reads'] == []
    assert reader.navigation_feedback_projection('unknown-task', identity='same-query')['accepted_empty_reads'] == []


def test_unmapped_archived_sources_are_declared_without_inventing_ranges_or_titles():
    reader, _, _, _ = accepted_reader()
    reader.web_navigation_reads[0]['source_ids'].append('missing-archived-source')
    group, = reader.navigation_feedback_projection('history', identity='same-query')['accepted_empty_reads']
    assert group['unique_source_count'] == 2 and group['unmapped_source_count'] == 1
    assert sum(doc['source_count'] for doc in group['documents']) == 1
    assert len(group['documents']) == 1


def test_projection_preserves_unknown_and_required_fields_verbatim(monkeypatch):
    reader, _, _, _ = accepted_reader()
    raw = reader.navigation_feedback('history', identity='same-query')
    raw.update(required_context={'original':'keep every required byte'}, future_field={'unknown':'not optional'})
    monkeypatch.setattr(reader, 'navigation_feedback', lambda *a, **k: deepcopy(raw))
    projection = reader.navigation_feedback_projection('history', identity='same-query')
    assert projection['required_context'] == raw['required_context']
    assert projection['future_field'] == raw['future_field']


def test_projection_and_omission_do_not_authorize_or_change_existing_fact_and_issue_state():
    invalid_partial = observation('source-question', ['s2'], stance='partial', value=None,
                                  reason='This original statement remains incomplete.')
    invalid_partial['value'] = None
    reader, engine, state, _ = web_fixture(lambda i,data: response(observation()) if i==1 else response(invalid_partial))
    read(reader, 'piano', 'same-query')
    read(reader, 'painting', 'same-query')
    before = deepcopy(reader.obligation_snapshot()), reader.material_signature(), deepcopy(state.public_dict())
    projection = reader.navigation_feedback_projection('history', identity='same-query')
    data = {'reading_feedback':projection, 'local_exploration':{
        'visited_doc_ids':[], 'failed_urls':[], 'omitted_visited_doc_id_count':0, 'omitted_failed_url_count':0}}
    while WebBridge._reduce_optional_navigation_hints(data):
        pass
    assert before == (reader.obligation_snapshot(), reader.material_signature(), state.public_dict())
    assert reader.evidence_obligations and state.valid()[0]['history'] == ['piano']
    assert projection['grants_review_authority'] is False


def test_group_omission_counts_raw_records_and_exposures_truthfully():
    data = {'reading_feedback': {'protocol':'web_reading_feedback_projection_v2',
        'accepted_empty_reads':[{'query_identity':'query', 'task_id':'task',
            'request_identity':str(count), 'logical_call_index':count,
            'raw_empty_read_record_count':count, 'variable_hints':[],
            'unique_source_count':0, 'unmapped_source_count':0, 'documents':[],
            'grants_review_authority':False} for count in (3,2,1)],
        'accepted_empty_read_count':6, 'projected_empty_exposure_count':3,
        'omitted_accepted_empty_read_count':0, 'omitted_empty_exposure_count':0,
        'assessed_doc_ids':['a','b'], 'assessed_doc_count':2,
        'required_context':{'original':'unchanged'}, 'future_field':['keep']},
        'local_exploration':{'visited_doc_ids':[], 'failed_urls':[],
            'omitted_visited_doc_id_count':0, 'omitted_failed_url_count':0}}
    while WebBridge._reduce_optional_navigation_hints(data):
        feedback = data['reading_feedback']
        assert (sum(row['raw_empty_read_record_count'] for row in feedback['accepted_empty_reads'])
                + feedback['omitted_accepted_empty_read_count']) == 6
        assert len(feedback['accepted_empty_reads']) + feedback['omitted_empty_exposure_count'] == 3
        assert len(feedback['assessed_doc_ids']) + feedback.get('omitted_assessed_doc_id_count',0) == 2
        assert feedback['required_context'] == {'original':'unchanged'} and feedback['future_field'] == ['keep']
    assert data['reading_feedback']['accepted_empty_reads'] == []


def test_large_optional_history_keeps_latest_complete_hint_while_broad_prefix_survives():
    bridge, engine, calls, fetched, events, feedback, identity = fixture(required_size=0, gap_size=240)
    feedback['accepted_empty_reads'] *= 24
    original_feedback = deepcopy(feedback)
    original_frontier = deepcopy(bridge._observed_links(bridge.sessions[identity]))
    bridge.step('Find project details.', 'project', identity=identity)
    data = offered(calls)
    assert len(data['links']) >= 8
    assert data['links'] == original_frontier[:len(data['links'])]
    for counted in calls.counts:
        if len(counted['data']['links']) < len(original_frontier):
            assert counted['data']['reading_feedback']['accepted_empty_reads'] == [original_feedback['accepted_empty_reads'][-1]]
            assert counted['data']['reading_feedback']['assessed_doc_ids'] == []
    assert feedback == original_feedback
    assert data['reading_feedback']['omitted_accepted_empty_read_count'] == len(original_feedback['accepted_empty_reads']) - 1
    assert_original_coordinates(engine, data)
    assert len(calls.requests) == engine.ledger.used['llm'] == 1
    remaining = {link['url'] for link in bridge._observed_links(bridge.sessions[identity])}
    assert remaining | {fetched[-1]} == {link['url'] for link in original_frontier}
    assert not bridge.sessions[identity]['skipped']


def test_actual_visited_url_and_title_are_readable_not_generated_facts():
    bridge, engine, calls, _, _, _, identity = fixture(required_size=0)
    bridge.step('Find project details.', 'project', identity=identity)
    data = offered(calls)
    pages = data['local_exploration']['visited_pages']
    assert [page['doc_id'] for page in pages] == data['local_exploration']['visited_doc_ids']
    for page in pages:
        assert page['url'] == bridge.pages[page['doc_id']]['url']
        assert page['title'] == engine.docs[page['doc_id']].title
        assert set(page) == {'doc_id','url','title'}


def test_paid_protocol_overflow_still_cannot_gain_a_fresh_projection_attempt():
    bridge, engine, calls, fetched, _, feedback, identity = fixture(
        paid_repair_overflow=True, required_size=0, gap_size=240)
    raw = deepcopy(feedback)
    with pytest.raises(InputOverflow):
        bridge.step('Find project details.', 'project', identity=identity)
    assert len(calls.requests) == engine.ledger.used['llm'] == 1
    assert fetched == ['https://fixture.example/']
    assert not bridge.sessions[identity]['link_presentations']
    assert feedback == raw
    assert offered(calls)['reading_feedback']['accepted_empty_reads'] == raw['accepted_empty_reads'][-1:]


def test_invalid_navigation_keeps_the_original_two_protocol_repair_limit(monkeypatch):
    bridge, engine, calls, fetched, _, _, identity = fixture(required_size=0, gap_size=240)
    bridge.settings['link_window'] = 2
    get = calls.get
    def invalid(*args, **kwargs):
        result = get(*args, **kwargs)
        result['response']['choices'][0]['message']['content'] = '{"link_id":"never-offered"}'
        return result
    monkeypatch.setattr(calls, 'get', invalid)
    with pytest.raises(ProtocolError):
        bridge.step('Find project details.', 'project', identity=identity)
    assert len(calls.requests) == engine.ledger.used['llm'] == 3
    assert engine.ledger.used['json_repairs'] == 2
    assert fetched == ['https://fixture.example/']


def test_unknown_raw_row_fields_are_preserved_without_grouping_or_optional_omission(monkeypatch):
    reader, _, _, _ = accepted_reader()
    raw = reader.navigation_feedback('history', identity='same-query')
    protected = {**deepcopy(raw['accepted_empty_reads'][0]),
                 'required_context': {'original': 'keep required row bytes'},
                 'future_field': {'unknown': ['retain recursively']}}
    raw['accepted_empty_reads'].append(protected)
    monkeypatch.setattr(reader, 'navigation_feedback', lambda *a, **k: deepcopy(raw))
    projection = reader.navigation_feedback_projection('history', identity='same-query')
    assert projection['accepted_empty_read_count'] == 2
    assert projection['projected_empty_exposure_count'] == 1
    assert projection['passthrough_empty_read_count'] == 1
    assert projection['accepted_empty_reads'][1] == protected
    data = {'reading_feedback': projection, 'local_exploration': {
        'visited_doc_ids': [], 'failed_urls': [],
        'omitted_visited_doc_id_count': 0, 'omitted_failed_url_count': 0}}
    while WebBridge._reduce_optional_navigation_hints(data):
        assert projection['accepted_empty_reads'][-1] == protected
    assert projection['accepted_empty_reads'] == [protected]
    assert projection['omitted_accepted_empty_read_count'] == 1
    assert projection['omitted_empty_exposure_count'] == 1
    assert reader.navigation_feedback('history', identity='same-query') == raw


def test_nested_unknown_projection_fields_are_not_optional_or_removed():
    reader, _, _, _ = accepted_reader()
    projection = reader.navigation_feedback_projection('history', identity='same-query')
    protected_hint = deepcopy(projection['accepted_empty_reads'][0])
    protected_hint['variable_hints'][0]['required_context'] = {'original': 'keep this hint field'}
    protected_source = deepcopy(projection['accepted_empty_reads'][0])
    protected_source['documents'][0]['future_coordinates'] = {'unknown': [1, 2, 3]}
    projection['accepted_empty_reads'] = [protected_hint, protected_source]
    before = deepcopy(projection['accepted_empty_reads'])
    data = {'reading_feedback': projection, 'local_exploration': {
        'visited_doc_ids': [], 'failed_urls': [],
        'omitted_visited_doc_id_count': 0, 'omitted_failed_url_count': 0}}
    while WebBridge._reduce_optional_navigation_hints(data):
        assert projection['accepted_empty_reads'] == before
    assert projection['accepted_empty_reads'] == before
    assert projection['omitted_accepted_empty_read_count'] == 0
    assert projection['omitted_empty_exposure_count'] == 0


def test_unknown_required_history_can_block_admission_without_paid_call_or_frontier_loss():
    bridge, engine, calls, fetched, _, feedback, identity = fixture(required_size=0)
    feedback['accepted_empty_reads'].append({
        'source_ids': ['original-source'], 'search_gaps': ['still only a hint'],
        'required_context': {'original': 'X' * 40000}})
    original = deepcopy(feedback)
    frontier = deepcopy(bridge._observed_links(bridge.sessions[identity]))
    result = bridge.step('Find project details.', 'project', identity=identity)
    assert result['trace']['search_status'] == 'navigation_assessment_paused'
    diagnostic = result['trace']['navigation_assessment']
    assert diagnostic['reason'] == 'no_admissible_unassessed_window'
    assert not diagnostic['complete_null_sweep'] and not diagnostic['absence_claim']
    assert diagnostic['assessed_candidates'] == 0 and not diagnostic['reconsideration_used']
    assert diagnostic['eligible_candidates'] == len(frontier)
    capacity = diagnostic['capacity_unavailable']
    assert capacity['error_type'] == 'InputOverflow' and capacity['preflight_overflows'] > 0
    assert capacity['paid_calls_in_failed_window'] == 0
    assert capacity['unassessed_original_links'] == frontier
    assert calls.requests == [] and engine.ledger.used.get('llm', 0) == 0
    assert all(any(row.get('required_context') == original['accepted_empty_reads'][-1]['required_context']
                   for row in counted['data']['reading_feedback']['accepted_empty_reads'])
               for counted in calls.counts)
    assert bridge._observed_links(bridge.sessions[identity]) == frontier
    assert feedback == original
    assert fetched == ['https://fixture.example/']
    assert not bridge.sessions[identity]['skipped']


@pytest.mark.parametrize('field', ['variable', 'query_identity', 'task_id', 'request_identity', 'logical_call_index'])
def test_future_nested_values_in_known_raw_scalar_fields_are_preserved(monkeypatch, field):
    reader, _, _, _ = accepted_reader()
    raw = reader.navigation_feedback('history', identity='same-query')
    raw['accepted_empty_reads'][0][field] = {'required_context': 'future structure must survive'}
    monkeypatch.setattr(reader, 'navigation_feedback', lambda *a, **k: deepcopy(raw))
    projection = reader.navigation_feedback_projection('history', identity='same-query')
    assert projection['accepted_empty_reads'] == raw['accepted_empty_reads']
    assert projection['passthrough_empty_read_count'] == 1
    assert projection['projected_empty_exposure_count'] == 0
    assert not WebBridge._optional_navigation_history_record(projection['accepted_empty_reads'][0], projection['protocol'])
    assert not WebBridge._optional_navigation_history_record(raw['accepted_empty_reads'][0], raw['protocol'])


@pytest.mark.parametrize('location,field', [
    ('group','query_identity'), ('group','task_id'), ('group','request_identity'),
    ('group','logical_call_index'), ('group','unique_source_count'), ('group','unmapped_source_count'),
    ('hint','variable'), ('document','doc_id'), ('document','url'), ('document','title'),
    ('document','source_count')])
def test_future_nested_values_in_known_projection_scalar_fields_are_nonoptional(location, field):
    reader, _, _, _ = accepted_reader()
    projection = reader.navigation_feedback_projection('history', identity='same-query')
    group = projection['accepted_empty_reads'][0]
    target = (group if location == 'group' else group['variable_hints'][0] if location == 'hint'
              else group['documents'][0])
    target[field] = {'required_context': 'future structure must survive'}
    before = deepcopy(group)
    projection['assessed_doc_ids'] = []
    data = {'reading_feedback': projection, 'local_exploration': {
        'visited_doc_ids': [], 'failed_urls': [],
        'omitted_visited_doc_id_count': 0, 'omitted_failed_url_count': 0}}
    assert not WebBridge._reduce_optional_navigation_hints(data)
    assert projection['accepted_empty_reads'] == [before]


def test_bounded_readable_route_survives_hint_reduction_and_initial_link_resizing():
    bridge, engine, calls, _, _, feedback, identity = fixture(required_size=0)
    feedback['accepted_empty_reads'] *= 24
    bridge.step('Find project details.', 'project', identity=identity)
    actual = offered(calls)
    assert actual['local_exploration']['visited_pages']
    assert actual['local_exploration']['omitted_visited_doc_id_count'] == 0
    # The latest hint and readable route remain while candidates/excerpts can
    # shrink; only a one-candidate/minimal-excerpt overflow allows their loss.
    for counted in calls.counts:
        if len(counted['data']['links']) > 1:
            assert counted['data']['local_exploration']['visited_pages']


def test_incomplete_projected_shape_is_never_reclassified_as_optional():
    assert not WebBridge._optional_navigation_history_record(
        {'raw_empty_read_record_count':1}, 'web_reading_feedback_projection_v2')


def reduction_data(protocol, records):
    return {'reading_feedback': {'protocol': protocol, 'accepted_empty_reads': deepcopy(records),
        'assessed_doc_ids': [], 'omitted_accepted_empty_read_count': 0,
        'omitted_empty_exposure_count': 0}, 'local_exploration': {
        'visited_doc_ids': [], 'failed_urls': [],
        'omitted_visited_doc_id_count': 0, 'omitted_failed_url_count': 0}}


def test_latest_projected_exposure_stays_whole_with_unknown_rows_on_both_sides():
    reader, engine, state, _ = accepted_reader()
    frozen = (deepcopy(reader.web_navigation_reads), deepcopy(engine.mapper.sources),
              reader.material_signature(), deepcopy(reader.obligation_snapshot()), deepcopy(state.public_dict()))
    group = reader.navigation_feedback_projection('history', identity='same-query')['accepted_empty_reads'][0]
    group['raw_empty_read_record_count'] = 3
    group['variable_hints'] *= 3
    older = {**deepcopy(group), 'logical_call_index': 0, 'request_identity': 'older-request'}
    unknown_before = {**deepcopy(group), 'future_field': {'required_context': 'keep'}}
    unknown_after = {**deepcopy(group), 'future_field': {'required_context': 'newest unknown stays'}}
    data = reduction_data('web_reading_feedback_projection_v2', [older, unknown_before, group, unknown_after])
    before = deepcopy(data)
    while WebBridge._reduce_optional_navigation_hints(data, preserve_latest_exposure=True):
        pass
    assert data['reading_feedback']['accepted_empty_reads'] == [unknown_before, group, unknown_after]
    assert data['reading_feedback']['omitted_accepted_empty_read_count'] == 3
    assert data['reading_feedback']['omitted_empty_exposure_count'] == 1
    assert before['reading_feedback']['accepted_empty_reads'] == [older, unknown_before, group, unknown_after]
    # Only the explicit final fallback can discard the last recognized group.
    assert WebBridge._reduce_optional_navigation_hints(data)
    assert data['reading_feedback']['accepted_empty_reads'] == [unknown_before, unknown_after]
    assert data['reading_feedback']['omitted_accepted_empty_read_count'] == 6
    assert frozen == (reader.web_navigation_reads, engine.mapper.sources, reader.material_signature(),
                      reader.obligation_snapshot(), state.public_dict())


def test_legacy_latest_exposure_preserves_all_variable_rows_with_identical_complete_identity():
    common = {'reading_status': 'no_relevant_evidence', 'query_identity': 'query', 'task_id': 'task',
        'request_identity': 'latest-paid-request', 'logical_call_index': 3,
        'source_ids': ['s2', 's1'], 'doc_ids': ['page'], 'search_gaps': ['Try another section.']}
    latest = [{**deepcopy(common), 'variable': variable} for variable in ('date', 'place', 'duration')]
    latest[1]['source_ids'].reverse()
    older = {**deepcopy(common), 'variable': 'date', 'request_identity': 'older-paid-request'}
    different_sources = {**deepcopy(common), 'variable': 'other', 'source_ids': ['s3']}
    unknown = {**deepcopy(common), 'variable': 'date', 'future': {'must': 'remain unchanged'}}
    records = [older, latest[0], unknown, different_sources, latest[1], latest[2]]
    data = reduction_data('web_reading_feedback_v1', records)
    while WebBridge._reduce_optional_navigation_hints(data, preserve_latest_exposure=True):
        pass
    assert data['reading_feedback']['accepted_empty_reads'] == [latest[0], unknown, latest[1], latest[2]]
    assert data['reading_feedback']['omitted_accepted_empty_read_count'] == 2
    assert 'omitted_empty_exposure_count' in data['reading_feedback']
    assert data['reading_feedback']['omitted_empty_exposure_count'] == 0


def test_legacy_without_complete_group_identity_retains_latest_original_row_only():
    records = [{'variable': variable, 'search_gaps': ['Original hint ' + variable]}
               for variable in ('older', 'latest')]
    data = reduction_data('web_reading_feedback_v1', records)
    assert WebBridge._reduce_optional_navigation_hints(data, preserve_latest_exposure=True)
    assert not WebBridge._reduce_optional_navigation_hints(data, preserve_latest_exposure=True)
    assert data['reading_feedback']['accepted_empty_reads'] == records[-1:]


def test_last_hint_drops_only_after_exact_minimal_candidate_overflow_then_prefix_refills():
    bridge, engine, calls, fetched, _, feedback, identity = fixture()
    before = deepcopy(feedback)
    frontier = deepcopy(bridge._observed_links(bridge.sessions[identity]))
    bridge.step('Find project details.', 'project', identity=identity)
    actual = offered(calls)
    last_hint_overflow = [index for index, counted in enumerate(calls.counts)
        if len(counted['data']['links']) == 1
        and max(len(source['text']) for source in counted['data']['source_pages']) <= 256
        and counted['data']['reading_feedback']['accepted_empty_reads'] == before['accepted_empty_reads'][-1:]
        and counted['count'] > 12024]
    no_hint = [index for index, counted in enumerate(calls.counts)
               if not counted['data']['reading_feedback']['accepted_empty_reads']]
    assert last_hint_overflow and no_hint and min(no_hint) > min(last_hint_overflow)
    assert actual['reading_feedback']['accepted_empty_reads'] == []
    assert len(actual['links']) > 1 and actual['links'] == frontier[:len(actual['links'])]
    assert feedback == before and not bridge.sessions[identity]['skipped']
    assert len(calls.requests) == engine.ledger.used['llm'] == 1
    assert_original_coordinates(engine, actual)


def test_preserved_latest_hint_does_not_change_null_window_fairness_or_raw_history():
    bridge, engine, calls, fetched, _, feedback, identity = fixture(null=True, required_size=0, gap_size=240)
    feedback['accepted_empty_reads'] *= 24
    raw, frontier = deepcopy(feedback), deepcopy(bridge._observed_links(bridge.sessions[identity]))
    for _ in range(2):
        bridge.step('Find project details.', 'project', identity=identity)
    windows = [json.loads(payload['messages'][1]['content']) for payload in calls.requests]
    for window in windows:
        reading = window['reading_feedback']
        kept = reading['accepted_empty_reads']
        # A smaller unassessed candidate window may fit more original history.
        # Retention must preserve the exact recent suffix, including its latest
        # complete hint, and report every omitted raw record truthfully.
        assert kept and kept == raw['accepted_empty_reads'][-len(kept):]
        assert kept[-1] == raw['accepted_empty_reads'][-1]
        assert len(kept) + reading.get('omitted_accepted_empty_read_count', 0) == len(raw['accepted_empty_reads'])
    first_urls = {link['url'] for link in windows[0]['links']}
    never_offered = {link['url'] for link in frontier} - first_urls
    assert never_offered and {link['url'] for link in windows[1]['links'][:len(never_offered)]} == never_offered
    assert first_urls.isdisjoint(link['url'] for link in windows[1]['links'])
    assert feedback == raw and bridge._observed_links(bridge.sessions[identity]) == frontier
    assert fetched == ['https://fixture.example/'] and engine.ledger.used['llm'] == 2
    for window in windows:
        assert_original_coordinates(engine, window)
