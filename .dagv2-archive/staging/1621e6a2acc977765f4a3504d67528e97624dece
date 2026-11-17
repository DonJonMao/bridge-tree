"""Offline complete-wire admission tests; no tokenizer/model/network service.

The controlled deployment counter assigns one token per serialized wire
character. Production Reasoner still constructs, counts and admits every exact
payload. These units test capacity control, not a real tokenizer's compression.
"""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from dagbt.budget import BudgetExceeded, Ledger
from dagbt.reasoning import InputOverflow, Reasoner
from dagbt.transport import digest
from dagbt.webwalker_browser import PageParser, WebBridge


def fixture(*, cross_page=False, null=False, paid_repair_overflow=False,
            llm_limit=24, required_size=6500, oversized_first=False, gap_size=7000):
    root = 'https://fixture.example/'
    archive = root + 'archive'

    def parse(html, url):
        parser = PageParser(url)
        parser.feed(html)
        return parser.result()

    def index(label, start, count):
        return ('<title>' + label + '</title><main><p>'
                + ('Unchanged ' + label + ' original paragraph. ') * 55 + '</p>'
                + ''.join('<a href="/branch-%d">Original branch %d</a> Nearby original phrase. '
                          % (i, i) for i in range(start, start + count)) + '</main>')

    pages = {root: parse(index('Root', 0, 2 if cross_page else 24), root)}
    if cross_page:
        pages[archive] = parse(index('Archive', 2, 2), archive)
    for document in list(pages.values()):
        for link in document['links']:
            pages[link['url']] = parse('<main>Unchanged branch body.</main>', link['url'])
    ledger = Ledger({'llm': llm_limit, 'json_repairs': 6})
    events, fetched = [], []
    feedback = {
        'protocol': 'web_reading_feedback_v1', 'evidence_semantics': 'navigation_hints_not_facts',
        'query_identity': 'fixed-project-query',
        'required_context': {'issue': 'Retain this required field.', 'original': 'R' * required_size},
        'accepted_empty_reads': [
            {'source_ids': ['unchanged-source-' + str(i)], 'doc_ids': ['unchanged-page-' + str(i)],
             'search_gaps': ['Unchanged prior local gap ' + str(i) + ' ' + 'g' * gap_size]}
            for i in range(2)],
        'assessed_doc_ids': ['unchanged-page-0', 'unchanged-page-1']}

    class Store:
        settings, events = {}, []
        def get(self, url):
            fetched.append(url)
            doc = pages[url]
            return {'url': url, 'document': doc, 'document_hash': digest(doc),
                    'raw_sha256': digest(['raw', url]), 'fetched_unix': 1}

    class Calls:
        def __init__(self):
            self.counts, self.requests = [], []

        def count_reasoning_tokens(self, stage, url, payload):
            data = json.loads(payload['messages'][1]['content'])
            wire = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
            count = len(wire)
            if paid_repair_overflow and 'validation_feedback' in data:
                count += 50000
            if oversized_first and any(link['url'].endswith('/branch-0') for link in data['links']):
                count += 50000
            self.counts.append({'data': deepcopy(data), 'wire': wire, 'count': count})
            return {'count': count, 'token_estimator_id': 'offline_exact_wire_characters_fixture'}

        def get(self, stage, url, payload, **options):
            ledger.reserve('llm', stage)
            self.requests.append(deepcopy(payload))
            data = json.loads(payload['messages'][1]['content'])
            selected = ('not-an-offered-id' if paid_repair_overflow else
                        None if null else data['links'][-1]['id'])
            return {'response': {'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps({'link_id': selected})}}]}}

    settings = {'algorithm_version': 'dagbt_residual_memory_v2', 'reasoning_output_tokens': 4096,
                'context_tokens': 16384, 'input_margin': 256, 'reserved_audit_calls': 1,
                'max_repairs_per_request': 2, 'response_format': 'plain'}
    calls = Calls()
    reasoner = Reasoner(calls, None, {'llm_base_url': 'https://unused.invalid'}, settings, ledger, events.append)
    reader = SimpleNamespace(navigation_feedback=lambda *args, **kwargs: deepcopy(feedback))
    engine = SimpleNamespace(docs={}, ledger=ledger, s=settings, event=events.append,
        navigation_provenance={}, reasoner=reasoner, residual_control=SimpleNamespace(reader=reader))
    bridge = WebBridge(engine, root, Store(), {'max_actions': 36, 'link_window': 128})
    identity = 'fixed-project-query'
    bridge.step('Find the project details.', 'project', identity=identity)
    if cross_page:
        doc_id = bridge._visit(archive)
        bridge.sessions[identity]['delivered'].append(doc_id)
    return bridge, engine, calls, fetched, events, feedback, identity


def offered(calls):
    return json.loads(calls.requests[-1]['messages'][1]['content'])


def assert_original_coordinates(engine, data):
    assert {source['doc_id'] for source in data['source_pages']} == {
        link['source_doc_id'] for link in data['links']}
    for source in data['source_pages']:
        original = engine.docs[source['doc_id']].passage
        for interval in source['source_ranges']:
            assert source['text'][interval['excerpt_start']:interval['excerpt_end']] == (
                original[interval['start']:interval['end']])
    for link in data['links']:
        context = link['source_context']
        assert context['text'] == engine.docs[link['source_doc_id']].passage[context['start']:context['end']]


def test_feedback_reduction_refills_same_page_frontier_and_sends_the_admitted_wire_once():
    bridge, engine, calls, fetched, events, feedback, identity = fixture()
    original_pages = deepcopy(bridge.pages)
    original_frontier = bridge._observed_links(bridge.sessions[identity])
    bridge.step('Find the project details.', 'project', identity=identity)
    data = offered(calls)
    assert 1 < len(data['links']) < len(original_frontier)
    assert data['links'] == original_frontier[:len(data['links'])]
    assert data['reading_feedback']['required_context'] == feedback['required_context']
    assert data['reading_feedback']['evidence_semantics'] == feedback['evidence_semantics']
    kept = len(data['reading_feedback']['accepted_empty_reads'])
    assert kept + data['reading_feedback']['omitted_accepted_empty_read_count'] == 2
    assert engine.residual_control.reader.navigation_feedback('project', identity) == feedback
    assert len(calls.requests) == engine.ledger.used['llm'] == 1
    assert fetched[-1] == data['links'][-1]['url']
    assert_original_coordinates(engine, data)
    # The selected response and decode are tied to the final admitted request,
    # including when a larger refill candidate failed its exact wire check.
    actual = json.dumps(calls.requests[0], ensure_ascii=False, separators=(',', ':'))
    assert any(row['wire'] != actual and len(row['data']['links']) > len(data['links'])
               and row['count'] > 12024 for row in calls.counts)
    assert len(actual) <= 12024
    for doc_id, page in original_pages.items():
        assert bridge.pages[doc_id] == page
    remaining = bridge._observed_links(bridge.sessions[identity])
    assert {link['url'] for link in remaining} | {fetched[-1]} == {link['url'] for link in original_frontier}
    presented = bridge.sessions[identity]['link_presentations']
    assert presented == {link['url']: 1 for link in data['links']}
    assert engine.ledger.limits == {'llm': 24, 'json_repairs': 6, 'web_actions': 36}


def test_refill_combines_old_pages_in_the_existing_frontier_order_with_exact_offsets():
    bridge, engine, calls, fetched, events, feedback, identity = fixture(cross_page=True, required_size=3000)
    original_frontier = bridge._observed_links(bridge.sessions[identity])
    assert len({link['source_doc_id'] for link in original_frontier}) == 2
    bridge.step('Find the project details.', 'project', identity=identity)
    data = offered(calls)
    assert data['links'] == original_frontier
    assert len(data['source_pages']) == 2
    assert_original_coordinates(engine, data)
    assert len(calls.requests) == engine.ledger.used['llm'] == 1


def test_null_refilled_windows_rotate_only_actual_presentations_and_preserve_frontier():
    bridge, engine, calls, fetched, events, feedback, identity = fixture(null=True)
    original_frontier = deepcopy(bridge._observed_links(bridge.sessions[identity]))
    for _ in range(2):
        result = bridge.step('Find the project details.', 'project', identity=identity)
        assert result['trace']['search_status'] == 'empty_probe'
    windows = [json.loads(payload['messages'][1]['content'])['links'] for payload in calls.requests]
    assert all(len(window) > 1 for window in windows)
    assert {link['url'] for link in windows[0]}.isdisjoint({link['url'] for link in windows[1]})
    assert bridge._observed_links(bridge.sessions[identity]) == original_frontier
    assert bridge.has_unvisited_links('project', identity)
    assert fetched == ['https://fixture.example/']
    assert len(calls.requests) == engine.ledger.used['llm'] == 2


def test_refill_does_not_reopen_a_paid_protocol_repair_or_fetch_without_a_read_call():
    bridge, engine, calls, fetched, events, feedback, identity = fixture(paid_repair_overflow=True)
    with pytest.raises(InputOverflow):
        bridge.step('Find the project details.', 'project', identity=identity)
    assert len(offered(calls)['links']) > 1
    assert len(calls.requests) == engine.ledger.used['llm'] == 1
    assert fetched == ['https://fixture.example/']
    assert bridge.sessions[identity]['link_presentations'] == {}
    assert engine.residual_control.reader.navigation_feedback('project', identity) == feedback


def test_unfittable_first_link_remains_archived_while_sibling_prefix_can_refill():
    bridge, engine, calls, fetched, events, feedback, identity = fixture(oversized_first=True)
    original_frontier = bridge._observed_links(bridge.sessions[identity])
    bridge.step('Find the project details.', 'project', identity=identity)
    data = offered(calls)
    assert len(data['links']) > 1
    assert data['links'] == original_frontier[1:1 + len(data['links'])]
    assert any(link['url'].endswith('/branch-0') for link in bridge._observed_links(bridge.sessions[identity]))
    assert bridge.sessions[identity]['skipped'] == []
    assert len(calls.requests) == engine.ledger.used['llm'] == 1
    assert_original_coordinates(engine, data)


def test_required_feedback_cannot_be_discarded_to_force_a_navigation_request():
    bridge, engine, calls, fetched, events, feedback, identity = fixture(required_size=20000)
    original_pages = deepcopy(bridge.pages)
    original_frontier = bridge._observed_links(bridge.sessions[identity])
    result = bridge.step('Find the project details.', 'project', identity=identity)
    assert result['trace']['search_status'] == 'navigation_assessment_paused'
    diagnostic = result['trace']['navigation_assessment']
    assert diagnostic['reason'] == 'no_admissible_unassessed_window'
    assert not diagnostic['complete_null_sweep'] and not diagnostic['absence_claim']
    assert diagnostic['assessed_candidates'] == 0
    capacity = diagnostic['capacity_unavailable']
    assert capacity['error_type'] == 'InputOverflow' and capacity['paid_calls_in_failed_window'] == 0
    assert capacity['preflight_overflows'] > 0
    assert capacity['unassessed_original_links'] == original_frontier
    assert not calls.requests and engine.ledger.used['llm'] == 0
    assert bridge.pages == original_pages
    assert bridge._observed_links(bridge.sessions[identity]) == original_frontier
    assert engine.residual_control.reader.navigation_feedback('project', identity) == feedback


def test_navigation_still_reserves_both_navigation_and_followup_read_calls():
    bridge, engine, calls, fetched, events, feedback, identity = fixture(llm_limit=2)
    with pytest.raises(BudgetExceeded, match='web_navigation_and_followup_read'):
        bridge.step('Find the project details.', 'project', identity=identity)
    assert not calls.requests and not calls.counts and engine.ledger.used['llm'] == 0
