"""Web feedback and real controller scheduling, using only invented sources."""
import ast
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import inspect
import json
from threading import Thread
import textwrap
from types import SimpleNamespace

import numpy as np
import pytest

from dagbt.methods import JOINT, RESIDUAL_V2
from dagbt.evidence_spans import build_source_spans
from dagbt.budget import BudgetExceeded
from dagbt.reasoning import InputOverflow
from dagbt.residual_control import ResidualControl
from dagbt.webwalker_control import WebResidualControl
from dagbt.webwalker_engine import WebEngine
from test_webwalker import demo
from test_webwalker_reading import (expand_wire_data, gap_response, observation, read,
                                   response, web_fixture)
from test_webwalker_navigation import bridge_fixture


def test_web_run_preserves_common_control_except_documented_scheduling_hooks():
    common = inspect.getsource(ResidualControl.run)
    expected = common.replace('for step in self.e.steps:', 'for step in self._web_step_order():')
    expected = expected.replace('self.read_progress(step,query,variables,local_docs,key,',
                                'self.web_read_existing(step,query,variables,local_docs,key,')
    expected = expected.replace('executed=True;break', 'self._web_completed_turn(nid);executed=True;break')
    expected = expected.replace('if key in self.exhausted:',
                                'if key in self.exhausted and self._web_correction_ticket(step, variables) is None:')
    expected = expected.replace('                try:\n                    before_read=',
                                '                navigation_operation = False\n                resume_before = key in self._web_resume_required\n                try:\n                    before_read=')
    expected = expected.replace('                    self.forced_demands.discard(nid)\n                    if step',
                                '                    read_yielded = not resume_before and key in self._web_resume_required\n                    self.forced_demands.discard(nid)\n                    if step')
    expected = expected.replace('                        found=self.e.bridge.step(',
                                "                        navigation_operation = True\n                        navigation_calls_before = self.e.ledger.used.get('llm', 0)\n                        found=self.e.bridge.step(")
    expected = expected.replace('                        self.e.discoveries.append(deepcopy(found));',
                                '                        navigation_operation = False\n                        self.e.discoveries.append(deepcopy(found));')
    expected = expected.replace("                            if found['trace'].get('search_status')=='empty_probe':",
                                "                            if found['trace'].get('search_status') == PAUSED:\n                                if read_yielded or self.e.ledger.used.get('llm', 0) > navigation_calls_before:\n                                    self._web_completed_turn(nid);executed=True;break\n                                continue\n                            if found['trace'].get('search_status')=='empty_probe':")
    expected = expected.replace('                    self.error(nid,exc);self.exhausted.add(key)',
                                "                    self.error(nid,exc)\n                    if navigation_operation and getattr(self.e.bridge, 'navigation_paused',\n                            lambda *args: False)(nid, key):\n                        if read_yielded or self.e.ledger.used.get('llm', 0) > navigation_calls_before:\n                            self._web_completed_turn(nid);executed=True;break\n                        continue\n                    self.exhausted.add(key)")
    assert ast.dump(ast.parse(textwrap.dedent(inspect.getsource(WebResidualControl.run)))) == ast.dump(
        ast.parse(textwrap.dedent(expected)))


def test_old_issue_new_window_and_frozen_repair_have_readonly_structural_metadata():
    issue = observation('old-partial', ['s1'], stance='partial',
                        reason='The activity is explicit but its date remains incomplete.')
    issue['value'] = None
    repeated = {**deepcopy(issue), 'id': 'current-partial'}
    def respond(index, data):
        if index == 1:
            return response(issue)
        if index == 2:
            result = response(repeated)
            result['slots'][0]['resolved_obligation_ids'] = [data['evidence_obligations'][0]['id']]
            return result
        return response()
    reader, engine, state, calls = web_fixture(respond, max_repairs_per_request=1)
    read(reader, 'piano', 'same-query')
    original = deepcopy(reader.evidence_obligations)
    sources = deepcopy(engine.mapper.sources)
    read(reader, 'painting', 'same-query')

    initial, repair = calls.requests[1:]
    context = initial['data']['web_reading_context']
    assert context['window_source_ids'] == context['new_window_source_ids'] == ['s2']
    assert context['retained_mandatory_source_ids'] == ['s1']
    assert context['pending_source_issues'] == [
        {'obligation_id': next(iter(original)), 'source_ids': ['s1'],
         'state': 'unresolved_controller_owned', 'ordinary_restatement_needed': False}]
    assert context['grants_review_authority'] is False
    assert 'repair_scope' not in initial['data']
    assert 'WEB REPAIR FIELD CHECK' in initial['payload']['messages'][0]['content']
    frozen = repair['data']['web_reading_context']['frozen_observations']
    assert frozen == [{'variable': 'history', 'id': 'current-partial',
                       'immutable': True, 'grants_review_authority': False}]
    assert not any(entry.get('frozen_observation_reviews') for entry in repair['data']['repair_scope']['failed'])
    assert reader.evidence_obligations == original and state.pending == {'history'}
    assert not state.routes and not reader.failed_batch_reviews
    assert engine.mapper.sources == sources
    assert engine.ledger.used['llm'] == 3 and engine.ledger.used['json_repairs'] == 1
    # The final empty repair withdraws a resolution claim; it does not erase the
    # valid partial frozen earlier in this same batch or authorize a page yield.
    assert reader.batches[-1]['complete'] and reader.batches[-1]['valid_rows'] == 1
    assert reader.web_search_gaps and not reader.web_navigation_reads


def test_accepted_empty_feedback_is_same_query_readonly_and_never_fact_progress():
    reader, engine, state, calls = web_fixture(lambda index, data: gap_response('Try the observed archive.'))
    read(reader, 'piano', 'one-query')
    signature, checkpoint = reader.material_signature(), deepcopy(reader.obligation_snapshot())
    feedback = reader.navigation_feedback('history', identity='one-query')
    assert feedback['evidence_semantics'] == 'navigation_hints_not_facts'
    assert feedback['assessed_doc_ids'] == ['piano']
    assert feedback['accepted_empty_reads'][0]['search_gaps'] == ['Try the observed archive.']
    assert feedback['accepted_empty_reads'][0]['source_ids'] == [engine.mapper.sources['s1']['source_id']]
    assert reader.navigation_feedback('other', identity='one-query')['accepted_empty_reads'] == []
    assert reader.navigation_feedback('history', identity='changed-parents')['accepted_empty_reads'] == []
    feedback['accepted_empty_reads'][0]['search_gaps'].append('Mutated caller copy.')
    assert reader.navigation_feedback('history', identity='one-query')['accepted_empty_reads'][0]['search_gaps'] == [
        'Try the observed archive.']
    assert reader.material_signature() == signature and reader.obligation_snapshot() == checkpoint
    assert not state.routes and not state.pending and len(calls.requests) == 1


def test_incomplete_read_cannot_publish_accepted_empty_navigation_feedback():
    invalid = gap_response()
    invalid['bad_envelope'] = True
    reader, _, state, _ = web_fixture(lambda index, data: invalid, max_repairs_per_request=0)
    read(reader, 'piano', 'failed-query')
    assert reader.failed_batch_reviews and state.pending == {'history'}
    assert reader.navigation_feedback('history', identity='failed-query')['accepted_empty_reads'] == []


def test_rejected_empty_repair_is_not_accepted_when_final_repair_has_evidence():
    invalid = response(observation('required-draft', ['invented-source']))
    corrected = response(observation('required-draft', ['s1']))
    reader, _, state, calls = web_fixture(
        lambda index, data: invalid if index == 1 else gap_response() if index == 2 else corrected,
        max_repairs_per_request=2)
    read(reader, 'piano', 'corrected-evidence')
    assert len(calls.requests) == 3 and reader.batches[-1]['complete']
    assert state.valid()[0]['history'] == ['piano']
    assert reader.web_search_gaps  # Raw typed disposition remains archived.
    assert reader.navigation_feedback('history', identity='corrected-evidence')['accepted_empty_reads'] == []


def catalogue_review_fixture(respond, **settings):
    reader, engine, state, calls = web_fixture(respond, **settings)
    engine.docs.clear(); engine.mapper.sources.clear(); engine.mapper.source_aliases.clear()
    for alias, identifier, text in [
        ('s9', 'catalogue', 'Fictional activity catalogue: link to the sample activity specification.'),
        ('s10', 'specification', 'The sample user recorded origami as the historical activity.')]:
        document = engine.docs[identifier] = SimpleNamespace(doc_id=identifier, passage=text, metadata={})
        source, = build_source_spans(identifier, document, 400)
        engine.mapper.sources[alias] = {**source, 'id': alias, 'source_id': source['id']}
        engine.mapper.source_aliases[source['id']] = alias
    return reader, engine, state, calls


@pytest.mark.parametrize('review_original', [True, False])
def test_checklist_preserves_source_deficit_after_frozen_restatement_and_requires_original_review(review_original):
    unknown = observation('catalogue-question', ['s9'], stance='unknown',
                          reason='This catalogue is only a link and states no historical activity.')
    unknown['value'] = None
    support = observation('new-fact', ['s10'], value=['origami'])
    original_review = observation('catalogue-review', ['s9'], stance='irrelevant',
                                  reason='The original is only a navigation link with no activity claim or ambiguity.')
    original_review['value'] = None
    def respond(index, data):
        if index == 1:
            return response(unknown)
        result = response(support) if index in (2, 3) else response(original_review) if review_original else response()
        result['slots'][0]['resolved_obligation_ids'] = [data['evidence_obligations'][0]['id']]
        if index >= 3:
            result['slots'][0]['reviewed_observation_ids'] = ['new-fact']
        # The final negative case is a well-typed offered reference that still
        # omits the old original, exactly the failed live-fixture repair shape.
        if index == 4 and not review_original:
            result['slots'][0]['reading_status'] = 'evidence_assessment'
        return result
    reader, engine, state, calls = catalogue_review_fixture(respond, max_repairs_per_request=2)
    read(reader, 'catalogue', 'same-query')
    old_issue = deepcopy(reader.evidence_obligations)
    read(reader, 'specification', 'same-query')
    assert len(calls.requests) == 4
    for request in calls.requests[1:]:
        data = request['data']
        checklist = data['web_review_checklist']
        assert checklist['grants_review_authority'] is False
        issue, = checklist['obligations']
        assert issue['required_original_source_ids'] == issue['sources_requiring_new_model_review'] == ['s9']
        assert issue['source_ids_covered_only_if_frozen_rows_explicitly_referenced'] == []
        assert 'sample_catalogue' not in {source['id'] for source in data['source_spans']}
    first, repair, restatement_repair = [request['data'] for request in calls.requests[1:]]
    assert first['web_review_checklist']['offered_frozen_observations'] == []
    for data in (repair, restatement_repair):
        assert data['web_review_checklist']['offered_frozen_observations'] == [
            {'variable': 'history', 'id': 'new-fact', 'stance': 'support', 'source_ids': ['s10'],
             'can_contribute_to_settled_source_coverage': True}]
        assert data['web_review_checklist']['frozen_ids_without_reference_permission'] == []
    assert 'remain frozen' in restatement_repair['repair_scope']['failed'][0]['feedback']
    assert 'obligation_review_sources' not in restatement_repair['repair_scope']['failed'][0]
    # The new checklist derives the deficit again from actual current offers,
    # without restoring removed common feedback or granting additional review.
    assert engine.ledger.used['llm'] == 4 and engine.ledger.used['json_repairs'] == 2
    assert state.valid()[0]['history'] == ['origami']
    if review_original:
        assert reader.batches[-1]['complete'] and not state.pending
        assert not reader.evidence_obligations and not reader.failed_batch_reviews
    else:
        assert not reader.batches[-1]['complete'] and state.pending == {'history'}
        assert reader.evidence_obligations == old_issue and reader.failed_batch_reviews
        assert reader.batches[-1]['failed_slots'][0]['error'].startswith('Evidence obligation resolution requires')


def test_review_checklist_projects_only_actual_offers_and_paid_failed_batch_permissions():
    reader, engine, state, _ = web_fixture()
    data = reader._payload(engine.steps[0], 'query', ['history'], ['s1'])
    data['evidence_obligations'] = [{'id': 'issue', 'variable': 'history', 'source_ids': ['s1', 's2']}]
    data['repair_scope'] = {'frozen_observation_ids': {'history': ['settled', 'partial']},
        'failed': [{'variable': 'history', 'id': '*',
                    'slot': {'observations': [observation('settled', ['s1'])]},
                    'frozen_observation_reviews': {'slot_observation_ids': ['settled'], 'observations': []}}]}
    data['failed_batch_reviews'] = [{'id': 'paid-current', 'variable': 'history', 'review_allowed': True},
                                  {'id': 'retained-only', 'variable': 'history', 'review_allowed': False}]
    canonical, state_before = deepcopy(data), deepcopy(reader.obligation_snapshot())
    wire = expand_wire_data(reader._wire_candidates(data)[0][0])
    checklist = wire['web_review_checklist']
    assert checklist['claimable_failed_batch_ids'] == ['paid-current']
    assert checklist['blocked_failed_batch_ids'] == ['retained-only']
    assert checklist['frozen_ids_without_reference_permission'] == [{'variable': 'history', 'id': 'partial'}]
    assert checklist['obligations'][0]['source_ids_covered_only_if_frozen_rows_explicitly_referenced'] == ['s1']
    assert checklist['obligations'][0]['sources_requiring_new_model_review'] == ['s2']
    assert data == canonical and reader.obligation_snapshot() == state_before and not state.routes


@pytest.mark.parametrize('stance', ['partial', 'unknown'])
def test_review_checklist_never_treats_unsettled_row_as_original_source_coverage(stance):
    reader, engine, _, _ = web_fixture()
    data = reader._payload(engine.steps[0], 'query', ['history'], ['s1'])
    row = observation('unsettled', ['s1'], stance=stance)
    row['value'] = None
    data['evidence_obligations'] = [{'id': 'issue', 'variable': 'history', 'source_ids': ['s1']}]
    # Current common code offers only settled stances. Even a prospective or
    # externally supplied unsettled offer must not erase the original deficit.
    data['repair_scope'] = {'frozen_observation_ids': {'history': ['unsettled']},
        'failed': [{'variable': 'history', 'id': '*',
                    'frozen_observation_reviews': {'slot_observation_ids': [], 'observations': [row]}}]}
    reader._add_review_checklist(data)
    checklist = data['web_review_checklist']
    assert checklist['offered_frozen_observations'][0]['can_contribute_to_settled_source_coverage'] is False
    assert checklist['obligations'][0]['sources_requiring_new_model_review'] == ['s1']
    assert checklist['obligations'][0]['source_ids_covered_only_if_frozen_rows_explicitly_referenced'] == []


def test_dom_priority_reorders_only_unoffered_discovery_and_keeps_every_original():
    reader, engine, state, _ = web_fixture()
    reader.current_identity = 'dom-priority'
    for alias, role in [('s1', 'utility_ui'), ('s2', 'main'), ('s3', 'hidden_ui')]:
        source = engine.mapper.sources[alias]
        engine.docs[source['doc_id']].metadata['web_regions'] = [
            {'start': source['start'], 'end': source['end'], 'role': role}]
        reader.discovery_frontier['dom-priority', alias] = reader._frontier_entry(
            engine.steps[0], ['history'], alias, 'dom-priority')
    sources, frontier = deepcopy(engine.mapper.sources), deepcopy(reader.discovery_frontier)
    pending = [['s1'], ['s2'], ['s3']]
    reader._prioritize_discovery_regions(pending)
    assert pending == [['s2'], ['s1'], ['s3']]
    assert engine.mapper.sources == sources and reader.discovery_frontier == frontier and not state.routes
    # Mandatory/unowned work retains its position even if it is UI text.
    reader.discovery_frontier.pop(('dom-priority', 's1'))
    pending = [['s1'], ['s3'], ['s2']]
    reader._prioritize_discovery_regions(pending)
    assert pending == [['s1'], ['s2'], ['s3']]


def flag_plan():
    return {'steps': [demo.step('first', 'Find the first flag.'),
                      demo.step('second', 'Find the second flag.'),
                      demo.step('decision', 'Are both flags true?', ['first', 'second'], 'compose')],
            'final_node_id': 'decision', 'output_contract': demo.contract('value', 'bool', 'flags'),
            'program': {'variables': {'a': {'type': 'bool', 'demand': 'first'},
                                      'b': {'type': 'bool', 'demand': 'second'}},
                        'expression': demo.op('and', demo.var('a'), demo.var('b'))}}


@pytest.mark.parametrize('method', [JOINT, RESIDUAL_V2])
@pytest.mark.parametrize('ui_only', [False, True])
def test_real_web_control_rotates_independent_leaves_and_yields_then_resumes_long_page(method, ui_only, tmp_path):
    long_text = ' '.join('Archive entry %d describes an unrelated project.' % index for index in range(1800))
    class Handler(BaseHTTPRequestHandler):
        hits = []
        def do_GET(self):
            self.hits.append(self.path)
            pages = {'/': '<main><p>Second flag is true.</p><a href="/long">Archive</a></main>',
                     '/long': '<main><a href="/side">Appendix</a><a href="/target">Flag report</a>'
                              + ('</main><div role="dialog"><p>' if ui_only else '<p>')
                              + long_text + ('</p></div>' if ui_only else '</p></main>'),
                     '/side': '<main><p>Appendix lists unrelated archive projects.</p></main>',
                     '/target': '<main><p>First flag is true.</p></main>'}
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
            self.wfile.write(pages[self.path].encode())
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    class Model:
        def __init__(self):
            self.requests = []
            self.navigations = 0
        def get(self, stage, url, payload):
            data = json.loads(payload['messages'][1]['content'])
            if isinstance(data, dict): data = expand_wire_data(data)
            self.requests.append((stage[0], deepcopy(data)))
            if stage[0] == 'planner':
                value = flag_plan()
            elif stage[0] == 'web_navigate':
                target = ['/long', '/side', '/target'][self.navigations]
                self.navigations += 1
                value = {'link_id': next(link['id'] for link in data['links'] if link['url'].endswith(target))}
            elif stage[0] == 'web_grounding_review':
                sources = {source['id']: source for source in data['source_spans']}
                reviews = []
                for candidate in data['candidates']:
                    row = candidate['observation']
                    marker = {'a': 'First flag is true.', 'b': 'Second flag is true.'}.get(row['variable'])
                    grounded = (marker and row['stance'] == 'support' and row['value'] is True
                        and row['source_ids'] and all(identifier in sources and marker in sources[identifier]['text']
                            for identifier in row['source_ids'])
                        and all(row[key] == value for key, value in data['requested_scopes'][row['variable']].items()))
                    reviews.append({'candidate_id': candidate['candidate_id'],
                        'verdict': 'entailed' if grounded else 'not_entailed',
                        'reason': 'Check this flag against its cited original and requested scope.'})
                value = {'reviews': reviews}
            else:
                slots = []
                for variable in data['variables']:
                    marker = 'First flag is true.' if variable == 'a' else 'Second flag is true.'
                    cited = [source['id'] for source in data['source_spans'] if marker in source['text']]
                    rows = []
                    if cited and not stage[0].startswith('audit_joint'):
                        rows = [{'id': variable + '-fact', 'stance': 'support', 'value': True,
                                 'source_ids': cited, **data['requested_scopes'][variable],
                                 'parent_versions': {}, 'retract_ids': [], 'reason': 'Explicit invented source statement.'}]
                    slot = {'variable': variable, 'observations': rows, 'unresolved': []}
                    if data['task']['execution'] == 'retrieval' and not stage[0].startswith('audit_joint'):
                        slot['reading_status'] = 'evidence_assessment' if rows else 'no_relevant_evidence'
                    slots.append(slot)
                value = {'slots': slots}
                if stage[0].startswith('audit_joint'): value['audit_verdict'] = 'supported'
            return {'response_ref': 'offline-' + str(len(self.requests)),
                    'response': {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}]}}
    try:
        model = Model()
        config = {'_test_transport': True, 'llm_base_url': 'http://fixture/v1', 'llm_model': 'fixture',
                  'fusion': {'max_quote_chars': 80},
                  'webwalker': {'max_actions': 36, 'http_attempts': 1}}
        engine = WebEngine({'id': 'fair-frontier', 'question': 'Are the first and second flags both true?'},
                           ({}, [], np.empty((0, 0), dtype=np.float32), None, demo.Tokenizer()), model, config,
                           method, root_url='http://127.0.0.1:' + str(server.server_port),
                           page_cache=tmp_path, allow_local=True)
        result = engine.run()
        assert isinstance(engine.residual_control, WebResidualControl)
        assert any(op == 'web_grounding_review' for op, data in model.requests)
        assert engine.steps == flag_plan()['steps']
        reading = [data for op, data in model.requests if op == 'joint_read']
        assert [data['task']['output_slot'] for data in reading[:2]] == ['first', 'second']
        events = result['diagnostics']['events']
        yielded = [event for event in events if event['event'] == 'web_document_window_yielded']
        resumed = [event for event in events if event['event'] == 'web_document_window_resumed']
        assert yielded
        if ui_only:
            assert len([event for event in yielded
                        if event['reason'] == 'unoffered_dom_ui_with_live_link_frontier']) >= 2
            assert not resumed
        else:
            assert resumed and yielded[0]['sequence'] < resumed[0]['sequence']
        assert Handler.hits == ['/', '/long', '/side', '/target']
        assert result['answer']['status'] == 'ok' and result['answer']['prediction'] == 'true'
        reader = engine.residual_control.reader
        assert reader.discovery_frontier  # Deferred raw archive text was never deleted or called irrelevant.
        assert all(entry['status'] == 'unoffered' for entry in reader.discovery_frontier.values())
        assert not reader.failed_batch_reviews and not reader.evidence_obligations
        assert engine.s['context_tokens'] == 16384 and engine.s['reasoning_output_tokens'] == 4096
        assert engine.ledger.limits['llm'] == 24 and engine.ledger.limits['web_actions'] == 36
        assert engine.ledger.used['llm'] < 24 and not engine.ledger.used['json_repairs']
        assert next(doc for doc in engine.docs.values() if doc.metadata.get('url', '').endswith('/long')).passage.endswith(
            'Archive entry 1799 describes an unrelated project.')
    finally:
        server.shutdown(); server.server_close(); thread.join()


def ui_control_fixture():
    reader, engine, state, _ = web_fixture()
    engine.ledger.limits['web_actions'] = 36
    engine.bridge = SimpleNamespace(has_unvisited_links=lambda node_id, identity=None: True)
    control = WebResidualControl.__new__(WebResidualControl)
    control.e, control.reader, control.state = engine, reader, state
    control._web_yield_ready, control._web_resume_required = set(), set()
    control._web_turn_clock, control._web_last_turn, control._web_budget_block = 0, {}, None
    source = engine.mapper.sources['s1']
    engine.docs[source['doc_id']].metadata['web_regions'] = [
        {'start': source['start'], 'end': source['end'], 'role': 'utility_ui'}]
    identity = 'current-query'
    reader.discovery_frontier[identity, 's1'] = reader._frontier_entry(
        engine.steps[0], ['history'], 's1', identity)
    reads = []
    control.read_progress = lambda *args, **kwargs: reads.append((args, kwargs)) or True
    return control, reader, engine, reads, identity


def test_pure_ui_pause_is_readonly_scope_exact_and_falls_back_without_links_or_budget():
    control, reader, engine, reads, identity = ui_control_fixture()
    reader.current_identity = 'stale-other-node'
    reader.clues['stale-other-node'] = ['s1']
    before_sources, before_frontier = deepcopy(engine.mapper.sources), deepcopy(reader.discovery_frontier)
    for _ in range(2):
        assert not control.web_read_existing(engine.steps[0], 'query', ['history'], ['piano'], identity)
    assert not reads and reader.current_identity == 'stale-other-node'
    assert reader.discovery_frontier == before_frontier and engine.mapper.sources == before_sources
    reader.clues[identity] = ['s1']
    assert control.web_read_existing(engine.steps[0], 'query', ['history'], ['piano'], identity)
    reader.clues.pop(identity)
    engine.bridge.has_unvisited_links = lambda node_id, identity=None: False
    assert control.web_read_existing(engine.steps[0], 'query', ['history'], ['piano'], identity)
    engine.bridge.has_unvisited_links = lambda node_id, identity=None: True
    engine.ledger.used['llm'] = 22  # Two total calls remain, one reserved for audit.
    assert control.web_read_existing(engine.steps[0], 'query', ['history'], ['piano'], identity)
    assert len(reads) == 3 and reader.discovery_frontier == before_frontier
    assert not control._web_resume_required and reader.current_identity == 'stale-other-node'


@pytest.mark.parametrize('classification', ['main_overlap', 'unknown_role', 'unlabelled_text', 'no_dom', 'unread'])
def test_pure_ui_pause_never_skips_body_unknown_or_mandatory_originals(classification):
    control, reader, engine, reads, identity = ui_control_fixture()
    source = engine.mapper.sources['s1']
    regions = engine.docs[source['doc_id']].metadata['web_regions']
    if classification == 'main_overlap':
        regions.append({'start': source['end'] - 1, 'end': source['end'], 'role': 'main'})
    elif classification == 'unknown_role':
        regions[0]['role'] = 'unknown'
    elif classification == 'unlabelled_text':
        regions[0]['start'] += 1
    elif classification == 'no_dom':
        regions.clear()
    else:
        reader.unread_obligations[identity, 's1'] = {'history'}
    assert control.web_read_existing(engine.steps[0], 'query', ['history'], ['piano'], identity)
    assert len(reads) == 1 and reader.discovery_frontier


@pytest.mark.parametrize('dom', [False, True])
def test_pure_ui_pause_cannot_bypass_nonfrontier_current_query_unread_body_or_pdf(dom):
    control, reader, engine, reads, identity = ui_control_fixture()
    source = engine.mapper.sources['s2']
    if dom:
        engine.docs[source['doc_id']].metadata['web_regions'] = [
            {'start': source['start'], 'end': source['end'], 'role': 'main'}]
    reader.unread_obligations[identity, 's2'] = {'history'}
    original = deepcopy(reader.obligation_snapshot())
    for _ in range(2):
        assert control.web_read_existing(engine.steps[0], 'query', ['history'],
                                         ['piano', 'painting'], identity)
    assert len(reads) == 2 and reader.obligation_snapshot() == original


def test_web_terminal_status_reports_actual_two_call_budget_block_and_clears_on_progress(monkeypatch):
    bridge, engine, requests, fetched, events, identity = bridge_fixture('<main><a href="/next">Next</a></main>')
    engine.errors = []
    engine.ledger.used['llm'] = 22
    assert engine.ledger.remaining('llm') == 2 and engine.s['reserved_audit_calls'] == 1
    control = WebResidualControl.__new__(WebResidualControl)
    control.e, control._web_budget_block = engine, None
    control._web_turn_clock, control._web_last_turn = 0, {}
    with pytest.raises(BudgetExceeded) as failure:
        bridge.step('Continue', 'project', identity=identity)
    assert failure.value.kind == 'llm' and failure.value.stage == 'web_navigation_and_followup_read'
    control.error('project', failure.value)
    control.stop_reason = 'unresolved_or_exhausted'
    monkeypatch.setattr(ResidualControl, 'publish', lambda self: self.stop_reason)
    assert control.publish() == 'budget_exhausted'
    control._web_completed_turn('other-task')
    control.stop_reason = 'unresolved_or_exhausted'
    control.error('project', InputOverflow('Original sources do not fit.'))
    assert control.publish() == 'unresolved_or_exhausted'
    control.error('project', BudgetExceeded('web_actions', 'web_visit', 1, 0))
    assert control.publish() == 'budget_exhausted'
    control.stop_reason = 'audit_incomplete'
    assert control.publish() == 'audit_incomplete'
    assert not requests and len(fetched) == 1
