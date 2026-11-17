"""A deduplicated URL retains one real occurrence's label and provenance."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from dagbt.budget import Ledger
from dagbt.reasoning import Reasoner
from dagbt.transport import digest
from dagbt.webwalker_assessment import candidate_identity
from dagbt.webwalker_browser import PageParser, WebBridge


ROOT = 'https://fixture.example/'
TARGET = ROOT + 'record'


def parse(html, url=ROOT):
    parser = PageParser(url)
    parser.feed(html)
    return parser.result()


@pytest.mark.parametrize('first,second,expected,region,navigation', [
    ('<nav><a href="/record">Menu</a></nav>',
     '<main><a href="/record">Technical record</a></main>', 'Technical record', 'main', True),
    ('<aside hidden><a href="/record">Hidden control</a></aside>',
     '<div><a href="/record">Technical record</a></div>', 'Technical record', 'content', False),
    ('<main><a href="/record">Technical record</a></main>',
     '<footer><a href="/record">Menu</a></footer>', 'Technical record', 'main', True),
    ('<div><a href="/record">First content</a></div>',
     '<main><a href="/record">Second content</a></main>', 'First content', 'content', False),
    ('<nav><a href="/record">First menu</a></nav>',
     '<footer><a href="/record">Second menu</a></footer>', 'First menu', 'navigation', True),
    ('<nav><a href="/record">Menu</a></nav>',
     '<article><a href="/record" aria-label="Accessible" title="Record">Visible</a></article>',
     'Accessible Record Visible', 'main', True),
])
def test_same_page_label_and_context_select_the_same_structural_occurrence(first, second, expected, region, navigation):
    page = parse('<title>Index</title>' + first + second)
    assert page['links'] == [{'url': TARGET, 'text': expected}]
    assert page['link_contexts'][TARGET]['region'] == region
    # Both occurrences and their ordering remain in the complete source text.
    first_text, second_text = parse(first)['text'], parse(second)['text']
    assert first_text in page['text'] and second_text in page['text']
    assert page['text'].index(first_text) < page['text'].index(second_text)
    context = page['link_contexts'][TARGET]
    assert context['start'] < context['end'] <= len(page['text'])
    visible_label = 'Visible' if expected == 'Accessible Record Visible' else expected
    assert visible_label in page['text'][context['start']:context['end']]
    assert page['navigation_urls'] == ([TARGET] if navigation else [])
    bridge = WebBridge.__new__(WebBridge)
    bridge.root, bridge.url_ids = ROOT, {ROOT: 'root'}
    bridge.pages = {'root': {'document': deepcopy(page)}}
    assert bridge._root_navigation() == ('root', {TARGET} if navigation else set())
    del bridge.pages['root']['document']['navigation_urls']
    assert bridge._root_navigation() == ('root', {TARGET} if region == 'navigation' else set())


def bridge_fixture(older, newer, *, null=False):
    pages = {ROOT: parse(older), ROOT + 'later': parse(newer, ROOT + 'later')}
    for document in list(pages.values()):
        for link in document['links']:
            pages.setdefault(link['url'], parse('<main>Original destination body.</main>', link['url']))
    ledger = Ledger({'llm': 24, 'json_repairs': 6})
    events, requests, counts = [], [], []

    class Store:
        settings, events = {}, []

        def get(self, url):
            document = pages[url]
            return {'url': url, 'document': document, 'document_hash': digest(document),
                    'raw_sha256': digest(['synthetic-raw', url]), 'fetched_unix': 1}

    class Calls:
        def count_reasoning_tokens(self, stage, url, payload):
            # The production Reasoner constructs the entire wire; the offline
            # counter deliberately assigns one token to each serialized char.
            wire = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
            counts.append((wire, len(wire)))
            return {'count': len(wire), 'token_estimator_id': 'offline_wire_characters'}

        def get(self, stage, url, payload, **options):
            ledger.reserve('llm', stage)
            requests.append(deepcopy(payload))
            data = json.loads(payload['messages'][1]['content'])
            selected = None if null else data['links'][0]['id']
            return {'response': {'choices': [{'finish_reason': 'stop',
                    'message': {'content': json.dumps({'link_id': selected})}}]}}

    settings = {'algorithm_version': 'dagbt_residual_memory_v2', 'reasoning_output_tokens': 4096,
                'context_tokens': 16384, 'input_margin': 256, 'reserved_audit_calls': 1,
                'max_repairs_per_request': 2, 'response_format': 'plain'}
    engine = SimpleNamespace(docs={}, ledger=ledger, s=settings, event=events.append,
                             navigation_provenance={})
    engine.reasoner = Reasoner(Calls(), None, {'llm_base_url': 'https://unused.invalid'},
                               settings, ledger, events.append)
    bridge = WebBridge(engine, ROOT, Store(), {'max_actions': 36, 'link_window': 128})
    identity = 'fixed-task-identity'
    bridge.step('Find the technical record.', 'task', identity=identity)
    old_id = next(iter(bridge.pages))
    new_id = bridge._visit(ROOT + 'later')
    bridge.sessions[identity]['delivered'].append(new_id)
    return bridge, engine, requests, counts, identity, old_id, new_id


@pytest.mark.parametrize('body', ['main', 'div'])
def test_older_body_occurrence_survives_newer_menu_without_losing_urls_or_aliases(body):
    bridge, engine, _, _, identity, old_id, new_id = bridge_fixture(
        '<title>Earlier index</title><' + body + '>Technical report. '
        '<a href="/record">Primary technical record</a><a href="/older-only">Older branch</a></' + body + '>',
        '<title>Later page</title><nav><a href="/newer-only">Newer branch</a>'
        '<a href="/record">Menu overview</a></nav><main>Unrelated latest body.</main>')
    originals = deepcopy(bridge.pages)
    used = dict(engine.ledger.used)
    links = bridge._observed_links(bridge.sessions[identity])
    assert [link['url'] for link in links] == [ROOT + 'newer-only', TARGET, ROOT + 'older-only']
    assert [link['id'] for link in links] == ['l0', 'l1', 'l2']
    record = links[1]
    assert record['source_doc_id'] == old_id != new_id
    assert record['text'] == 'Primary technical record'
    assert record['source_region'] == ('main' if body == 'main' else 'content')
    context = record['source_context']
    assert context['text'] == engine.docs[old_id].passage[context['start']:context['end']]
    assert 'Technical report.' in context['text']
    assert bridge._observed_links(bridge.sessions[identity]) == links
    assert bridge.pages == originals and dict(engine.ledger.used) == used


@pytest.mark.parametrize('older,newer,expected', [
    ('<nav><a href="/record">Old menu</a></nav>',
     '<main><a href="/record">New body</a></main>', 'New body'),
    ('<main><a href="/record">Old body</a></main>',
     '<main><a href="/record">New body</a></main>', 'New body'),
    ('<nav><a href="/record">Old menu</a></nav>',
     '<nav><a href="/record">New menu</a></nav>', 'New menu'),
])
def test_cross_page_ties_keep_existing_page_order(older, newer, expected):
    bridge, _, _, _, identity, _, new_id = bridge_fixture(older, newer)
    link, = bridge._observed_links(bridge.sessions[identity])
    assert link['text'] == expected and link['source_doc_id'] == new_id
    assert link['id'] == 'l0'


def test_missing_or_unknown_context_does_not_override_an_explicit_body_occurrence():
    bridge, _, _, _, identity, old_id, new_id = bridge_fixture(
        '<main><a href="/record">Old body</a></main>',
        '<nav><a href="/record">New menu</a></nav>')
    document = bridge.pages[new_id]['document']
    for contexts in ({}, {TARGET: {**document['link_contexts'][TARGET], 'region': 'future_role'}}):
        document['link_contexts'] = contexts
        link, = bridge._observed_links(bridge.sessions[identity])
        assert link['source_doc_id'] == old_id and link['text'] == 'Old body'


@pytest.mark.parametrize('filtered', ['visited', 'failed', 'skipped'])
def test_duplicate_body_occurrence_cannot_restore_an_ineligible_url(filtered):
    bridge, _, _, _, identity, _, _ = bridge_fixture(
        '<main><a href="/record">Old body</a><a href="/sibling">Sibling</a></main>',
        '<nav><a href="/record">New menu</a></nav>')
    if filtered == 'visited':
        bridge.url_ids[TARGET] = 'already-visited'
    elif filtered == 'failed':
        bridge.failed.add(TARGET)
    else:
        bridge.sessions[identity]['skipped'].append(TARGET)
    assert [link['url'] for link in bridge._observed_links(bridge.sessions[identity])] == [ROOT + 'sibling']


def test_admitted_shortened_wire_keeps_real_body_provenance_and_one_paid_navigation():
    older = '<title>Original report index</title><main>' + ''.join(
        '<p>Original report branch %d. <a href="/record-%d">Technical record %d %s</a></p>'
        % (i, i, i, 'Original label ' * 40) for i in range(24)) + '</main>'
    newer = '<title>Recent menu</title><nav>' + ''.join(
        '<a href="/record-%d">Menu %d</a>' % (i, i) for i in range(24)) + '</nav><main>Unrelated page.</main>'
    bridge, engine, requests, counts, identity, old_id, _ = bridge_fixture(older, newer)
    originals = deepcopy(bridge.pages)
    frontier = bridge._observed_links(bridge.sessions[identity])
    bridge.step('Find the technical record.', 'task', identity=identity)
    assert len(requests) == engine.ledger.used['llm'] == 1
    data = json.loads(requests[0]['messages'][1]['content'])
    assert 0 < len(data['links']) < len(frontier)
    assert data['links'] == frontier[:len(data['links'])]
    assert {link['source_doc_id'] for link in data['links']} == {old_id}
    assert all(link['text'].startswith('Technical record ') for link in data['links'])
    for link in data['links']:
        context = link['source_context']
        assert context['text'] == engine.docs[old_id].passage[context['start']:context['end']]
    for source in data['source_pages']:
        for interval in source['source_ranges']:
            assert source['text'][interval['excerpt_start']:interval['excerpt_end']] == (
                engine.docs[source['doc_id']].passage[interval['start']:interval['end']])
    admitted = json.dumps(requests[0], ensure_ascii=False, separators=(',', ':'))
    assert len(admitted) + 4096 + 256 + 8 <= 16384
    assert any(count + 4096 + 256 + 8 > 16384 for _, count in counts)
    assert any(wire == admitted for wire, _ in counts)
    assert all(bridge.pages[doc_id] == original for doc_id, original in originals.items())
    followed = data['links'][0]['url']
    assert {link['url'] for link in bridge._observed_links(bridge.sessions[identity])} | {followed} == {link['url'] for link in frontier}
    assert engine.ledger.limits == {'llm': 24, 'json_repairs': 6, 'web_actions': 36}


def test_null_assessments_of_body_representative_are_stable_and_keep_original_bound():
    bridge, engine, requests, _, identity, old_id, _ = bridge_fixture(
        '<main><a href="/record">Original technical record</a></main>',
        '<nav><a href="/record">Menu overview</a></nav>', null=True)
    frontier = bridge._observed_links(bridge.sessions[identity])
    original_identity = candidate_identity(frontier[0])
    for _ in range(2):
        bridge.step('Find the technical record.', 'task', identity=identity)
    result = bridge.step('Find the technical record.', 'task', identity=identity)
    assert result['trace']['search_status'] == 'navigation_assessment_paused'
    assert len(requests) == engine.ledger.used['llm'] == 2
    assert bridge._observed_links(bridge.sessions[identity]) == frontier
    assert candidate_identity(frontier[0]) == original_identity
    assert all(json.loads(payload['messages'][1]['content'])['links'][0]['source_doc_id'] == old_id
               for payload in requests)
