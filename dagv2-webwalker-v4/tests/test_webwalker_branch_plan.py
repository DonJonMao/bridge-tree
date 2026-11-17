"""Paid, source-bound alternate routes on invented sites and exact wire counters."""
from copy import deepcopy
import json

import pytest

from dagbt.budget import BudgetExceeded
from dagbt.evidence_spans import build_source_spans
from dagbt.reasoning import ProtocolError
from dagbt.transport import digest
from dagbt.webwalker_assessment import candidate_identity
from dagbt.webwalker_browser import PageParser, WebBridge
from dagbt.webwalker_control import WebResidualControl
from test_webwalker_navigation_refill import assert_original_coordinates, fixture, offered
from test_webwalker_reading import gap_response, observation, response, web_fixture


QUERY = 'Read historical activities'
IDENTITY = 'invented-history-route'


def planned(data, primary=0, alternative=1):
    return {'link_id': data['links'][primary]['id'], 'exploration_plan': {
        'intent': 'intermediate_branch', 'reason': 'This original points to an activity collection.',
        'alternative_link_id': data['links'][alternative]['id'] if alternative is not None else None,
        'alternative_reason': 'This distinct original offers a records route.' if alternative is not None else None}}


def site_fixture(*, fail_primary=False, fail_alternative=False):
    reader, engine, state, calls = web_fixture(context_tokens=65536, reasoning_output_tokens=1024)
    root = 'https://invented.example/'
    bodies = {
        root: '<title>Activity archive</title><main><a href="/collection">Collection</a>'
              '<a href="/records">Original records route</a></main>',
        root + 'collection': '<title>Collection</title><main><p>I played piano last year.</p>'
              '<a href="/records">Records repeated on a new page</a></main>',
        root + 'records': '<title>Records</title><main><a href="/records/entry-17">Activity entry</a></main>',
        root + 'records/entry-17': '<title>Entry</title><main>I played piano last year.</main>'}
    fetched = []

    class Store:
        settings, events = {}, []
        def get(self, url):
            fetched.append(url)
            if ((fail_primary and url == root + 'collection')
                    or (fail_alternative and url == root + 'records')):
                raise ConnectionError('Invented unavailable branch')
            parser = PageParser(url)
            parser.feed(bodies[url])
            document = parser.result()
            return {'url': url, 'document': document, 'document_hash': digest(document),
                    'raw_sha256': digest(bodies[url]), 'fetched_unix': 1}

    calls.read_response = lambda data: gap_response('Try another observed branch.')
    calls.nav_response = lambda data: planned(data, alternative=1 if len(data['links']) > 1 else None)
    calls.respond = lambda index, data: (calls.nav_response(data) if 'links' in data
                                       else calls.read_response(data))
    calls.counts = []
    def count(stage, url, payload):
        wire = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        calls.counts.append(wire)
        return {'count': len(wire), 'token_estimator_id': 'offline_exact_wire_characters_fixture'}
    calls.count_reasoning_tokens = count
    engine.navigation_provenance = {}
    engine.fact_state = state
    engine.residual_control = WebResidualControl(engine)
    engine.residual_control.reader = reader
    bridge = WebBridge(engine, root, Store(), {'max_actions': 36, 'link_window': 128})
    engine.bridge = bridge
    bridge.step(QUERY, 'history', identity=IDENTITY)
    return bridge, reader, engine, state, calls, fetched, root


def step(bridge):
    return bridge.step(QUERY, 'history', identity=IDENTITY)


def read_page(bridge, reader, doc_id=None):
    doc_id = doc_id or bridge.sessions[IDENTITY]['delivered'][-1]
    engine = reader.e
    for source in build_source_spans(doc_id, engine.docs[doc_id], 400):
        if source['id'] not in engine.mapper.source_aliases:
            alias = 's' + str(len(engine.mapper.sources) + 1)
            engine.mapper.sources[alias] = {**source, 'id': alias, 'source_id': source['id']}
            engine.mapper.source_aliases[source['id']] = alias
    return reader.read(engine.steps[0], QUERY, ['history'], [doc_id], IDENTITY,
                       discovery_doc_ids=[doc_id])


def nav_requests(calls):
    return [row for row in calls.requests if row['stage'][0] == 'web_navigate']


def test_real_empty_reads_keep_paid_original_alternative_and_reach_a_deeper_page():
    bridge, reader, engine, state, calls, fetched, root = site_fixture()
    read_page(bridge, reader)
    step(bridge)
    session = bridge.sessions[IDENTITY]
    pending = deepcopy(session['pending_branch_plan'])
    assert pending['primary_attempted'] and fetched[-1] == root + 'collection'
    # A newly fetched body occurrence becomes the normal URL representative.
    current = next(link for link in bridge._observed_links(session) if link['url'] == root + 'records')
    assert candidate_identity(current) != pending['candidate_identity']
    read_page(bridge, reader)
    assert reader.batches[-1]['complete'] and not state.routes and not state.pending
    before = deepcopy(bridge.snapshot()), deepcopy(engine.ledger.public_dict()), len(calls.counts)
    assert bridge.has_actionable_links('history', IDENTITY)
    assert not bridge.navigation_paused('history', IDENTITY)
    assert (bridge.snapshot(), engine.ledger.public_dict(), len(calls.counts)) == before
    paid_before, actions_before = engine.ledger.used['llm'], engine.ledger.used['web_actions']
    result = step(bridge)
    assert fetched[-1] == root + 'records' and len(result['local_candidate_ids']) == 1
    assert engine.ledger.used['llm'] == paid_before
    assert engine.ledger.used['web_actions'] == actions_before + 1
    assert 'pending_branch_plan' not in session and len(nav_requests(calls)) == 1
    consumed = next(event for event in engine.events if event['event'] == 'web_branch_plan_consumed')
    assert consumed['paid_plan_ref'] == pending['paid_plan_ref']
    assert consumed['link'] == pending['link'] and not consumed['new_navigation_model_call']
    assert consumed['request_identity'] == digest(nav_requests(calls)[0]['data'])
    assert consumed['logical_call_index'] == 2
    assert_original_coordinates(engine, nav_requests(calls)[0]['data'])
    read_page(bridge, reader)
    step(bridge)
    assert fetched == [root, root + 'collection', root + 'records', root + 'records/entry-17']
    assert len(nav_requests(calls)) == 2 and engine.ledger.used['llm'] == 5
    assert engine.ledger.limits == {'llm': 24, 'json_repairs': 6, 'web_actions': 36}
    assert not state.routes and not reader.evidence_obligations


@pytest.mark.parametrize('change', ['support', 'partial', 'unknown', 'counter'])
def test_real_fact_partial_unknown_or_counter_invalidates_the_paid_alternative(change):
    bridge, reader, engine, state, calls, _, _ = site_fixture()
    if change == 'counter':
        state.integrate([{**observation('prior', [engine.mapper.sources['s1']['source_id']]),
                          'variable': 'history'}])
    step(bridge)
    paid = deepcopy(bridge.sessions[IDENTITY]['pending_branch_plan'])
    def reading(data):
        alias = data['source_spans'][-1]['id']
        row = observation('new-original', [alias], stance='contradiction' if change == 'counter' else change)
        if change != 'support':
            row['value'] = None
        if change == 'counter':
            row['retract_ids'] = list(state.routes)
        return response(row)
    calls.read_response = reading
    read_page(bridge, reader)
    assert reader.batches[-1]['complete']
    if change == 'support':
        assert state.valid()[0]['history'] == ['piano']
    elif change in ('partial', 'unknown'):
        assert reader.evidence_obligations and state.pending == {'history'}
    else:
        assert not state.valid()[0] and any(route['revoked'] for route in state.routes.values())
    assert bridge._planned_branch(bridge.sessions[IDENTITY], bridge._observed_links(bridge.sessions[IDENTITY])) is None
    calls.nav_response = lambda data: {'link_id': None}
    step(bridge)
    assert len(nav_requests(calls)) == 2 and 'pending_branch_plan' not in bridge.sessions[IDENTITY]
    invalidated = [event for event in engine.events if event['event'] == 'web_branch_plan_invalidated']
    assert len(invalidated) == 1 and invalidated[0]['paid_plan_ref'] == paid['paid_plan_ref']
    assert not any(event['event'] == 'web_branch_plan_consumed' for event in engine.events)


def test_failed_review_new_original_authority_invalidates_without_rewriting_the_old_review():
    bridge, reader, engine, _, calls, _, _ = site_fixture()
    record = {'id': 'old-failed-batch', 'variable': 'history', 'task_id': 'history', 'phase': 'history',
              'source_ids': [engine.mapper.sources['s1']['source_id']], 'failed': [],
              'seen_source_ids': [engine.mapper.sources['s1']['source_id']],
              'seen_parent_signatures': [reader._failed_parent_signature('history')]}
    reader.failed_batch_reviews[record['id']] = record
    engine.residual_control.local_pools['history'] = ['piano']
    step(bridge)
    before = deepcopy(reader.failed_batch_reviews)
    engine.residual_control.local_pools['history'].append('painting')
    calls.nav_response = lambda data: {'link_id': None}
    step(bridge)
    assert len(nav_requests(calls)) == 2 and reader.failed_batch_reviews == before
    assert any(event['event'] == 'web_branch_plan_invalidated' for event in engine.events)


@pytest.mark.parametrize('change', ['label', 'context', 'document_hash', 'failed_url', 'visited_url', 'scope'])
def test_original_source_or_scope_changes_cannot_be_replaced_by_a_same_url_occurrence(change):
    bridge, _, engine, state, calls, _, root = site_fixture()
    step(bridge)
    session = bridge.sessions[IDENTITY]
    plan = session['pending_branch_plan']
    page = bridge.pages[plan['link']['source_doc_id']]
    if change == 'label':
        next(link for link in page['document']['links'] if link['url'] == root + 'records')['text'] += ' changed'
    elif change == 'context':
        page['document']['link_contexts'][root + 'records']['start'] += 1
    elif change == 'document_hash':
        page['document_hash'] = digest('changed original')
    elif change == 'failed_url':
        bridge.failed.add(root + 'records')
    elif change == 'visited_url':
        doc_id = bridge._visit(root + 'records')
        session['delivered'].append(doc_id)
    else:
        state.contract = {**state.contract, 'time_scope': 'changed_scope'}
    assert bridge._planned_branch(session, bridge._observed_links(session)) is None
    calls.nav_response = lambda data: {'link_id': None}
    step(bridge)
    assert 'pending_branch_plan' not in session
    assert any(event['event'] == 'web_branch_plan_invalidated' for event in engine.events)


@pytest.mark.parametrize('primary_failure', [False, True])
def test_access_failure_consumes_each_selected_alternative_once(primary_failure):
    bridge, _, engine, _, calls, fetched, root = site_fixture(
        fail_primary=primary_failure, fail_alternative=True)
    step(bridge)
    assert bridge.sessions[IDENTITY]['pending_branch_plan']['primary_attempted']
    paid_before = engine.ledger.used['llm']
    assert step(bridge)['trace']['search_status'] == 'empty_probe'
    assert 'pending_branch_plan' not in bridge.sessions[IDENTITY]
    assert engine.ledger.used['llm'] == paid_before and len(nav_requests(calls)) == 1
    assert fetched.count(root + 'records') == 1 and engine.ledger.used['web_actions'] == 3
    calls.nav_response = lambda data: {'link_id': None}
    step(bridge)
    assert fetched.count(root + 'records') == 1
    assert len([event for event in engine.events if event['event'] == 'web_branch_plan_consumed']) == 1


@pytest.mark.parametrize('limit', ['llm', 'web_actions'])
def test_consumption_requires_normal_followup_read_and_web_budgets_before_popping(limit):
    bridge, _, engine, _, calls, fetched, _ = site_fixture()
    step(bridge)
    before = deepcopy(bridge.sessions[IDENTITY]['pending_branch_plan'])
    engine.ledger.used[limit] = engine.ledger.limits[limit] - (1 if limit == 'llm' else 0)
    used = deepcopy(engine.ledger.used)
    with pytest.raises(BudgetExceeded):
        step(bridge)
    assert bridge.sessions[IDENTITY]['pending_branch_plan'] == before
    assert engine.ledger.used == used and len(fetched) == 2 and len(nav_requests(calls)) == 1


def test_a_paid_alternative_can_use_the_last_ordinary_call_without_a_second_navigation():
    bridge, _, engine, _, calls, fetched, root = site_fixture()
    step(bridge)
    engine.ledger.used['llm'] = 22  # One ordinary reader call and the audit reserve remain.
    step(bridge)
    assert fetched[-1] == root + 'records' and engine.ledger.used['llm'] == 22
    assert len(nav_requests(calls)) == 1


@pytest.mark.parametrize('invalid', [[], {}, True, 3, 'unobserved', 'same', 'no-primary', 'no-reason', 'intent'])
def test_invalid_plan_keeps_the_original_paid_two_repair_bound(invalid):
    bridge, _, engine, _, calls, fetched, root = site_fixture()
    def bad(data):
        value = planned(data)
        if invalid == 'same':
            value['exploration_plan']['alternative_link_id'] = value['link_id']
        elif invalid == 'no-primary':
            value['link_id'] = None
        elif invalid == 'no-reason':
            value['exploration_plan']['alternative_reason'] = ' '
        elif invalid == 'intent':
            value['exploration_plan']['intent'] = 'no_plausible_branch'
        else:
            value['exploration_plan']['alternative_link_id'] = invalid
        return value
    calls.nav_response = bad
    with pytest.raises(ProtocolError):
        step(bridge)
    assert len(nav_requests(calls)) == engine.ledger.used['llm'] == 3
    assert engine.ledger.used['json_repairs'] == 2 and fetched == [root]
    assert 'pending_branch_plan' not in bridge.sessions[IDENTITY]


@pytest.mark.parametrize('primary', [[], {}, True, 3])
def test_invalid_primary_id_is_a_paid_protocol_error(primary):
    bridge, _, engine, _, calls, fetched, root = site_fixture()
    calls.nav_response = lambda data: {'link_id': primary}
    with pytest.raises(ProtocolError):
        step(bridge)
    assert len(nav_requests(calls)) == engine.ledger.used['llm'] == 3
    assert engine.ledger.used['json_repairs'] == 2 and fetched == [root]


def test_explicit_stop_plan_is_audited_without_creating_an_alternative():
    bridge, _, engine, _, calls, fetched, root = site_fixture()
    calls.nav_response = lambda data: {'link_id': None, 'exploration_plan': {
        'intent': 'no_plausible_branch', 'reason': 'Neither original is a plausible route.',
        'alternative_link_id': None, 'alternative_reason': None}}
    assert step(bridge)['trace']['search_status'] == 'empty_probe'
    event = next(event for event in engine.events if event['event'] == 'web_navigation_plan_decided')
    assert event['selected_link_id'] is None and event['plan']['reason']
    assert event['request_identity'] == digest(nav_requests(calls)[0]['data'])
    assert 'pending_branch_plan' not in bridge.sessions[IDENTITY] and fetched == [root]


def test_repaired_paid_plan_references_the_actual_repair_wire_and_can_only_follow_primary_attempt():
    bridge, _, engine, _, calls, fetched, root = site_fixture()
    calls.nav_response = lambda data: ({'link_id': 'unoffered'} if len(nav_requests(calls)) == 1
                                       else planned(data))
    step(bridge)
    session = bridge.sessions[IDENTITY]
    pending = session['pending_branch_plan']
    repair = nav_requests(calls)[-1]
    assert 'validation_feedback' in repair['data']
    assert pending['request_identity'] == digest(repair['data'])
    assert pending['logical_call_index'] == 2 and engine.ledger.used['json_repairs'] == 1
    pending['primary_attempted'] = False
    assert bridge._planned_branch(session, bridge._observed_links(session)) is None
    pending['primary_attempted'] = True
    # Durable snapshot restoration retains exactly one use, not a new decision.
    bridge.sessions = json.loads(json.dumps(bridge.sessions))
    step(bridge)
    assert fetched[-1] == root + 'records' and len(nav_requests(calls)) == 2
    assert engine.ledger.used['llm'] == 2 and 'pending_branch_plan' not in bridge.sessions[IDENTITY]


def test_admitted_exact_wire_window_alone_can_supply_both_chosen_branches():
    bridge, engine, calls, fetched, events, _, identity = fixture(required_size=3000)
    original_get = calls.get
    def choose(stage, url, payload, **options):
        result = original_get(stage, url, payload, **options)
        data = json.loads(payload['messages'][1]['content'])
        result['response']['choices'][0]['message']['content'] = json.dumps(planned(data))
        return result
    calls.get = choose
    bridge.step('Find the project details.', 'project', identity=identity)
    data = offered(calls)
    wire = json.dumps(calls.requests[-1], ensure_ascii=False, separators=(',', ':'))
    assert 1 < len(data['links']) < 24 and len(wire) <= 12024
    assert_original_coordinates(engine, data)
    pending = deepcopy(bridge.sessions[identity]['pending_branch_plan'])
    assert pending['link'] == data['links'][1] and pending['request_identity'] == digest(data)
    bridge.step('Find the project details.', 'project', identity=identity)
    assert fetched[-1] == data['links'][1]['url']
    assert len(calls.requests) == engine.ledger.used['llm'] == 1
    assert engine.ledger.used['web_actions'] == 3
    assert any(event['event'] == 'web_branch_plan_consumed' for event in events)


def test_600_character_explanations_use_the_admitted_exact_wire_without_paid_repair():
    bridge, engine, calls, fetched, events, _, identity = fixture()
    original_get = calls.get
    explanation = ('This invented archive may lead to a more specific record. ' * 20)[:600]
    def choose(stage, url, payload, **options):
        result = original_get(stage, url, payload, **options)
        data = json.loads(payload['messages'][1]['content'])
        value = planned(data)
        value['exploration_plan']['reason'] = explanation
        value['exploration_plan']['alternative_reason'] = explanation
        result['response']['choices'][0]['message']['content'] = json.dumps(value)
        return result
    calls.get = choose
    bridge.step('Find the project details.', 'project', identity=identity)
    payload = calls.requests[-1]
    data = offered(calls)
    assert 'Each non-null reason/alternative_reason: one short sentence <=300 chars.' in payload['messages'][0]['content']
    assert payload['messages'][0]['content'].count('"maxLength": 1000') == 2
    assert 1 < len(data['links']) and len(json.dumps(payload, ensure_ascii=False, separators=(',', ':'))) <= 12024
    assert_original_coordinates(engine, data)
    assert len(calls.requests) == engine.ledger.used['llm'] == 1
    assert not engine.ledger.used['json_repairs']
    pending = bridge.sessions[identity]['pending_branch_plan']
    assert len(pending['link']['url']) and pending['request_identity'] == digest(data)
    decided = next(event for event in events if event['event'] == 'web_navigation_plan_decided')
    assert len(decided['plan']['reason']) == len(decided['plan']['alternative_reason']) == 600
    bridge.step('Find the project details.', 'project', identity=identity)
    assert fetched[-1] == data['links'][1]['url'] and engine.ledger.used['llm'] == 1


def test_route_clarification_is_on_the_actual_wire_without_changing_evidence_or_review_authority():
    bridge, reader, engine, state, calls, _, _ = site_fixture()
    def authority():
        return deepcopy((state.program, state.contract, state.versions, state.routes, state.pending,
            reader.obligation_snapshot(), reader.failed_batch_reviews, engine.mapper.sources,
            engine.mapper.source_aliases, engine.residual_control.local_pools, engine.ledger.limits))
    before = authority()
    step(bridge)
    payload = nav_requests(calls)[0]['payload']
    system = payload['messages'][0]['content']
    assert 'Match exact subject/relation.' in system
    assert 'Broad overviews need not name the target.' in system
    assert 'Known other-entity details need an observed route to target in reason' in system
    assert 'shared organization/category/funding is insufficient' in system
    assert 'prefer independent relevant section' in system
    assert authority() == before
    assert not state.routes and not reader.evidence_obligations
    assert_original_coordinates(engine, nav_requests(calls)[0]['data'])
    assert json.dumps(payload, ensure_ascii=False, separators=(',', ':')) in calls.counts
    # This scripted fixture verifies the admitted instruction and unchanged
    # authority only. It makes no claim about real-model semantic improvement.


@pytest.mark.parametrize('field', ['reason', 'alternative_reason'])
def test_explanations_over_1000_characters_keep_the_original_paid_repair_bound(field):
    bridge, _, engine, _, calls, fetched, root = site_fixture()
    def overlong(data):
        value = planned(data)
        value['exploration_plan'][field] = 'Invented bounded explanation. ' * 35
        assert len(value['exploration_plan'][field]) > 1000
        return value
    calls.nav_response = overlong
    with pytest.raises(ProtocolError):
        step(bridge)
    assert len(nav_requests(calls)) == engine.ledger.used['llm'] == 3
    assert engine.ledger.used['json_repairs'] == 2 and fetched == [root]
    assert 'pending_branch_plan' not in bridge.sessions[IDENTITY]


def exploration_fixture(*, same_group=False):
    reader, engine, state, calls = web_fixture(context_tokens=65536, reasoning_output_tokens=1024)
    root, fetched = 'https://review.example/', []
    menu = '<nav><a href="/overview">Overview</a><a href="/registry">Registry</a></nav>'
    prefix = 'archive/path-' if same_group else 'path-'
    if same_group:
        menu = ('<nav><a href="/archive">Archive</a>'
                '<a href="/registry/deep">Detailed registry</a><a href="/registry">Registry</a>'
                '<a href="/workbench">Workbench</a>'
                '<a href="https://outside.example/records">External records</a></nav>')
    bodies = {root: '<title>Root</title>' + menu + '<main><a href="/%s1">Collection</a></main>' % prefix}
    for number in range(1, 7):
        bodies[root + prefix + str(number)] = (
            '<title>Collection %d</title>' % number + menu + '<main><p>Collection introduction.</p>'
            + '<a href="/%s%d">Next collection</a>' % (prefix, number + 1)
            + ''.join('<a href="/detail-%d">Record %d</a>' % (i, i) for i in range(8)) + '</main>')
    class Store:
        settings, events = {}, []
        def get(self, url):
            fetched.append(url)
            parser = PageParser(url)
            parser.feed(bodies.get(url, '<title>Record</title><main>A separate original record.</main>'))
            document = parser.result()
            return {'url': url, 'document': document, 'document_hash': digest(document),
                    'raw_sha256': digest(document), 'fetched_unix': 1}
    calls.read_response = lambda data: gap_response()
    calls.respond = lambda index, data: calls.nav_response(data) if 'links' in data else calls.read_response(data)
    calls.counts = []
    def count(stage, url, payload):
        wire = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        calls.counts.append(wire)
        return {'count': len(wire), 'token_estimator_id': 'offline_exact_wire_characters_fixture'}
    calls.count_reasoning_tokens = count
    engine.navigation_provenance, engine.fact_state = {}, state
    engine.residual_control = WebResidualControl(engine)
    engine.residual_control.reader = reader
    bridge = WebBridge(engine, root, Store(), {'max_actions': 36, 'link_window': 4})
    engine.bridge = bridge
    step(bridge)
    read_page(bridge, reader)
    return bridge, reader, engine, state, calls, fetched, root


def explore(bridge, reader, calls, root, number, *, backup=False, prefix='path-'):
    def choose(data):
        primary = next(i for i, link in enumerate(data['links']) if link['url'] == root + prefix + str(number))
        return planned(data, primary, next(i for i in range(len(data['links'])) if i != primary) if backup else None)
    calls.nav_response = choose
    step(bridge)
    read_page(bridge, reader)


def test_root_navigation_lane_spreads_observed_path_groups_without_dropping_siblings():
    seed, root = 'https://seed.example/', 'https://structure.example/'
    paths = ['https://outside.example/alpha/one', '/archive/deep/one', '/archive/two',
             '/archive', '/archive?view=second', 'https://outside.example/beta/two',
             '/directory/one', '/directory', '/community/one', '/calendar/one']
    parser = PageParser(root)
    parser.feed('<title>Structure</title><nav>'
        + ''.join('<a href="%s">Entry %d</a>' % (path, i) for i, path in enumerate(paths))
        + '</nav><main>'
        + ''.join('<a href="/record-%d">Record %d</a>' % (i, i) for i in range(4)) + '</main>')
    document = parser.result()
    bridge = WebBridge.__new__(WebBridge)
    bridge.root, bridge.url_ids = seed, {seed: 'root', root: 'root'}
    bridge.pages = {'root': {'url': root, 'document': document, 'document_hash': digest(document)}}
    links = [{'id': 'l' + str(i), 'source_doc_id': 'root', **link}
             for i, link in enumerate(document['links'])]
    before = deepcopy(links)
    ordered = bridge._review_frontier(links)
    anchors = [links[i]['url'] for i in (3, 7, 8, 9)]
    assert [ordered[i]['url'] for i in (0, 4, 8, 12)] == anchors
    assert len(ordered) == len(links) and {link['url'] for link in ordered} == {link['url'] for link in links}
    assert [link for link in ordered if link['url'] not in anchors] == [
        link for link in links if link['url'] not in anchors]
    assert links == before
    reduced = [link for i, link in enumerate(links) if i not in (8, 9)]
    assert bridge._root_navigation_anchors(reduced) == [links[i] for i in (3, 7, 0)]
    data = {'links': ordered[:9], 'exploration_review': {}}
    bridge._refresh_exploration_review(data)
    assert data['exploration_review']['root_navigation']['link_ids'] == [links[i]['id'] for i in (3, 7, 8, 0)]


@pytest.mark.parametrize('typed', [False, True])
def test_exploration_review_uses_three_settled_docs_without_relabeling_and_preserves_wire_null_sweep(typed):
    bridge, reader, engine, state, calls, fetched, root = exploration_fixture()
    empty_reads = deepcopy(reader.web_navigation_reads)
    if typed:
        calls.read_response = lambda data: response({**observation('other-record',
            [data['source_spans'][-1]['id']], stance='irrelevant'), 'value': None})
    for number in (1, 2, 3):
        explore(bridge, reader, calls, root, number)
        assert reader.source_exposures[-1]['status'] == 'batch_assessed'
    if typed:
        assert reader.web_navigation_reads == empty_reads
        assert all(batch['rows'][0]['stance'] == 'irrelevant' for batch in state.history[-3:])
    assert all('exploration_review' not in request['data'] for request in nav_requests(calls))
    before = {link['url']: deepcopy(link) for link in bridge._observed_links(bridge.sessions[IDENTITY])}
    authority = deepcopy((state.public_dict(), reader.obligation_snapshot(), reader.failed_batch_reviews))
    calls.nav_response = lambda data: {'link_id': None}
    engine.s['context_tokens'] = 16384
    step(bridge)
    request = nav_requests(calls)[-1]
    data = request['data']
    assert 'exploration_review' in data
    assert_original_coordinates(engine, data)
    assert json.dumps(request['payload'], ensure_ascii=False, separators=(',', ':')) in calls.counts
    assert len(calls.counts[-1]) + 1024 + 256 <= 16384
    assert (state.public_dict(), reader.obligation_snapshot(), reader.failed_batch_reviews) == authority
    review = data['exploration_review']
    assert len({window['doc_id'] for window in review['completed_assessments']}) == 3
    assert 'completed_empty_windows' not in review
    origin = review['root_navigation']
    assert origin['source_doc_id'] == bridge.url_ids[root]
    assert origin['document_hash'] == bridge.pages[origin['source_doc_id']]['document_hash']
    assert origin['link_ids'] and data['links'][0]['id'] in origin['link_ids']
    for link in data['links']:
        assert candidate_identity(link) == candidate_identity(before[link['url']])
        if link['id'] in origin['link_ids']:
            context = bridge.pages[origin['source_doc_id']]['document']['link_contexts'][link['url']]
            assert context['region'] == 'navigation'
    assert 'Never claim a page names the target unless supplied originals do.' in request['payload']['messages'][0]['content']
    visits = len(fetched)
    bridge.settings['link_window'] = 1
    small_start = len(nav_requests(calls))
    for _ in range(14):
        if bridge.navigation_paused('history', IDENTITY):
            break
        step(bridge)
    small = nav_requests(calls)[small_start:]
    assert small[0]['data']['exploration_review']['root_navigation']['link_ids']
    assert not small[1]['data']['exploration_review']['root_navigation']['link_ids']
    assert bridge.navigation_paused('history', IDENTITY) and len(fetched) == visits
    assert sum('navigation_assessment' in request['data'] for request in nav_requests(calls)) == 1
    assert engine.ledger.used['json_repairs'] == 0 and engine.ledger.used['llm'] <= 23
    assert {link['url'] for link in bridge._observed_links(bridge.sessions[IDENTITY])} == set(before)


def test_exploration_material_cutoff_and_incomplete_reads_cannot_reuse_old_assessments():
    bridge, reader, _, state, calls, _, root = exploration_fixture()
    for number in (1, 2, 3):
        explore(bridge, reader, calls, root, number)
    session = bridge.sessions[IDENTITY]
    assert len(bridge._exploration_windows(session)) == 3
    session['_exploration_progress']['cross_group_used'] = True
    old = deepcopy(state.__dict__)
    state.integrate([{**observation('fact-reset', [reader.e.mapper.sources['s1']['source_id']]),
                      'variable': 'history'}])
    assert state.versions['history'] == 1
    assert bridge._exploration_windows(session) == []
    assert not session['_exploration_progress']['cross_group_used']
    state.__dict__.clear()
    state.__dict__.update(old)
    assert bridge._exploration_windows(session) == []
    explore(bridge, reader, calls, root, 4)
    assert bridge._exploration_windows(session) == []
    assert len(session['_exploration_progress']['windows']) == 1
    calls.read_response = lambda data: response({**observation('incomplete-assessment',
        [data['source_spans'][-1]['id']], stance='partial'), 'value': None})
    explore(bridge, reader, calls, root, 5)
    assert state.pending and reader.source_exposures[-1]['status'] == 'incomplete'
    assert bridge._exploration_windows(session) == []
    assert session['_exploration_progress']['windows'] == []
    calls.read_response = lambda data: response(observation('failed-assessment',
        [data['source_spans'][-1]['id']], value='Invalid set shape'))
    explore(bridge, reader, calls, root, 6)
    assert not reader.batches[-1]['complete'] and reader.failed_batch_reviews
    assert reader.source_exposures[-1]['status'] == 'incomplete'
    assert bridge._exploration_windows(session) == []
    assert session['_exploration_progress']['windows'] == []


def test_exploration_review_cannot_displace_an_already_paid_valid_backup():
    bridge, reader, engine, _, calls, fetched, root = exploration_fixture(same_group=True)
    for number in (1, 2, 3):
        explore(bridge, reader, calls, root, number, backup=number == 3, prefix='archive/path-')
    session = bridge.sessions[IDENTITY]
    pending = deepcopy(session['pending_branch_plan'])
    paid_before, nav_before = engine.ledger.used['llm'], len(nav_requests(calls))
    step(bridge)
    assert fetched[-1] == pending['link']['url']
    assert engine.ledger.used['llm'] == paid_before and len(nav_requests(calls)) == nav_before
    assert 'pending_branch_plan' not in session and len(session['_exploration_progress']['windows']) == 3
    assert not any(event['event'] == 'web_branch_plan_invalidated' for event in engine.events)


def test_one_cross_group_window_null_keeps_unseen_frontier_and_original_reconsideration():
    grouped_root = 'https://grouped.example/'
    branches = ('registry', 'workbench', 'collection', 'directory', 'other')
    paths = ['/archive'] + [path for branch in branches for path in (
        '/' + branch + '/deep/detail', '/' + branch + '/first', '/' + branch,
        '/' + branch + '/second', '/' + branch + '/third', '/' + branch + '/fourth')]
    parser = PageParser(grouped_root)
    parser.feed('<nav>' + ''.join('<a href="%s">Entry %d</a>' % (path, index)
                                 for index, path in enumerate(paths))
                + '<a href="https://outside.example/registry/body-record">External</a></nav>'
                + '<main>' + ''.join('<a href="/%s/body-record">Body %s</a>' % (branch, branch)
                                    for branch in branches)
                + '<a href="/body-only">Body record</a></main>')
    document = parser.result()
    grouped = WebBridge.__new__(WebBridge)
    grouped.root, grouped.url_ids = grouped_root, {grouped_root: 'root'}
    grouped.pages = {'root': {'url': grouped_root, 'document': document},
                     'current': {'url': grouped_root + 'archive/read'}}
    originals = []
    for index, link in enumerate(document['links']):
        context = document['link_contexts'][link['url']]
        originals.append({'id': 'l' + str(index), 'source_doc_id': 'root', **link,
            'source_region': context['region'],
            'source_context': {'start': context['start'], 'end': context['end'],
                               'text': document['text'][context['start']:context['end']]}})
    before = deepcopy(originals)
    pool = grouped._cross_group_frontier({'delivered': ['root', 'current']}, originals)
    assert [link['url'] for link in pool] == [grouped_root + branch + suffix
        for suffix in ('', '/first', '/second', '/third', '/fourth', '/body-record', '/deep/detail')
        for branch in branches[:4]]
    assert len(pool) == 28 and originals == before
    assert all(link in originals for link in pool)
    body_members = [link for link in pool if link['url'].endswith('/body-record')]
    assert len(body_members) == 4
    assert all(link['source_region'] == 'main' and link['url'] not in document['navigation_urls']
               and link['source_context']['text'] == document['text'][
                   link['source_context']['start']:link['source_context']['end']]
               for link in body_members)

    bridge, reader, engine, state, calls, fetched, root = exploration_fixture(same_group=True)
    for number in (1, 2, 3):
        explore(bridge, reader, calls, root, number, prefix='archive/path-')
    frontier = {link['url'] for link in bridge._observed_links(bridge.sessions[IDENTITY])}
    visits, paid, nav = len(fetched), engine.ledger.used['llm'], len(nav_requests(calls))
    calls.nav_response = lambda data: {'link_id': None}
    bridge.settings['link_window'] = 1
    step(bridge)
    data = nav_requests(calls)[-1]['data']
    first, = data['links']
    assert first['url'] in {root + 'registry', root + 'workbench'}
    assert data['local_exploration']['frontier_links'] == 3
    assert data['local_exploration']['complete_frontier_count'] == len(frontier) > 3
    assert 'navigation_assessment' not in data
    assert_original_coordinates(engine, data)
    assert not bridge.navigation_paused('history', IDENTITY)

    step(bridge)
    ordinary = nav_requests(calls)[-1]['data']
    assert len(ordinary['links']) == 1 and ordinary['links'][0]['url'] != first['url']
    assert ordinary['local_exploration']['frontier_links'] == len(frontier) - 1
    assert 'navigation_assessment' not in ordinary
    for _ in range(len(frontier)):
        if bridge.navigation_paused('history', IDENTITY):
            break
        step(bridge)
    sweep = nav_requests(calls)[nav:]
    ordinary = [request['data'] for request in sweep if 'navigation_assessment' not in request['data']]
    assert len(ordinary) == len(frontier)
    assert {data['links'][0]['url'] for data in ordinary} == frontier
    reconsider, = [request['data'] for request in sweep if 'navigation_assessment' in request['data']]
    assert reconsider['local_exploration']['frontier_links'] == len(frontier)
    assert reconsider['navigation_assessment']['phase'] == 'one_bounded_reconsideration'
    assert bridge.navigation_paused('history', IDENTITY)
    step(bridge)
    assert len(nav_requests(calls)) == nav + len(frontier) + 1
    assert engine.ledger.used['llm'] == paid + len(frontier) + 1
    assert len(fetched) == visits and not state.routes and not reader.evidence_obligations
    assert not engine.ledger.used['json_repairs']


def test_unfittable_cross_group_pool_falls_back_to_full_frontier_before_any_paid_attempt():
    bridge, reader, engine, state, calls, fetched, root = exploration_fixture(same_group=True)
    for number in (1, 2, 3):
        explore(bridge, reader, calls, root, number, prefix='archive/path-')
    paid, nav, visits = engine.ledger.used['llm'], len(nav_requests(calls)), len(fetched)
    restricted = {root + 'registry', root + 'registry/deep', root + 'workbench'}
    denied = set()
    original_count = calls.count_reasoning_tokens

    def count(stage, url, payload):
        result = original_count(stage, url, payload)
        data = json.loads(payload['messages'][1]['content'])
        urls = {link['url'] for link in data.get('links', [])}
        if urls & restricted:
            assert engine.ledger.used['llm'] == paid
            if len(urls) == 1:
                denied.update(urls)
            return {**result, 'count': engine.s['context_tokens'] + 1}
        return result

    calls.count_reasoning_tokens = count
    calls.nav_response = lambda data: planned(data, alternative=None)
    step(bridge)
    data = nav_requests(calls)[-1]['data']
    assert denied == restricted  # Every restricted member failed local admission.
    assert not {link['url'] for link in data['links']} & restricted
    assert data['local_exploration']['frontier_links'] > 3
    assert_original_coordinates(engine, data)
    assert len(nav_requests(calls)) == nav + 1 and engine.ledger.used['llm'] == paid + 1
    assert len(fetched) == visits + 1 and not bridge.navigation_paused('history', IDENTITY)
    assert not engine.ledger.used['json_repairs'] and not state.routes
