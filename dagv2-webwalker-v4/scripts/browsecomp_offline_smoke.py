#!/usr/bin/env python3
"""Exercise both BrowseComp arms with invented SQLite sources and loopback HTTP.

This deterministic installation check is not a benchmark score. Its fixture
defines its own exact chat tokenizer; no deployment tokenizer or model is used.
"""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dagbt.browsecomp_data import Corpus, load_questions, prepare, verify_corpus
from dagbt.browsecomp_engine import BrowseCompEngine
from dagbt.methods import JOINT, RESIDUAL_V2
from dagbt.model_runtime import BTTokenAccounting


QUESTION = 'Use the primary package if it runs offline, otherwise choose the backup.'
DOCUMENTS = {
    'invented-primary': 'Primary package: Star E3.',
    'invented-offline': 'Star E3 can run offline: true.',
    'invented-backup': 'Backup package: Moon B2.',
}
FACTS = {
    'p': ('Primary package: Star E3.', 'Star E3'),
    's': ('Star E3 can run offline: true.', True),
    'b': ('Backup package: Moon B2.', 'Moon B2'),
}


def plan():
    def step(slot, question, parents=(), execution='retrieval'):
        return {'output_slot': slot, 'question': question, 'inputs': list(parents),
                'execution': execution, 'answer_type': 'fact'}

    return {
        'steps': [step('primary', 'Find the primary package'),
                  step('offline', 'Can {primary} run offline?', ['primary']),
                  step('backup', 'Find the backup package after checking {offline}', ['offline']),
                  step('selection', 'Select primary if offline else backup',
                       ['primary', 'offline', 'backup'], 'compose')],
        'final_node_id': 'selection',
        'output_contract': {'mode': 'value', 'result_type': 'entity',
                            'entity_scope': 'package', 'time_scope': 'fixture',
                            'explanation': 'none'},
        'program': {
            'variables': {'p': {'type': 'entity', 'demand': 'primary'},
                          's': {'type': 'bool', 'demand': 'offline'},
                          'b': {'type': 'entity', 'demand': 'backup'}},
            'expression': {'op': 'if', 'args': [{'op': 'var', 'id': 's'},
                                             {'op': 'var', 'id': 'p'},
                                             {'op': 'var', 'id': 'b'}]}}}


def fixture_token_count(messages):
    """Exact vocabulary rule of this invented service, including chat framing."""
    rendered = json.dumps(messages, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'))
    return len(re.findall(r'\w+|[^\w\s]', rendered)) + 3 * len(messages) + 1


def originals(data):
    """Decode reversible wire packing, then check every span against full text."""
    sources = deepcopy(data['source_spans'])
    if 'source_span_columns' in data:
        sources = [dict(zip(data['source_span_columns'], row)) for row in sources]
    for source in sources:
        if data.get('source_documents'):
            source.update(data['source_documents'][source['doc_id']])
        text = DOCUMENTS[source['doc_id']]
        assert 0 <= source['start'] < source['end'] <= len(text), source
        assert source['text'] == text[source['start']:source['end']], source
    assert len({source['id'] for source in sources}) == len(sources)
    return sources


class FixtureModel:
    """Generate observations only from offered originals; review them separately."""

    def __init__(self):
        self.requests, self.tokenizations, self.errors = [], [], []

    def answer(self, payload):
        assert payload['model'] == 'invented-corpus-fixture'
        assert 1 <= payload['max_tokens'] <= 4096
        assert 'schema' in payload['messages'][0]['content']
        data = json.loads(payload['messages'][1]['content'])
        if isinstance(data, str):
            assert data == QUESTION
            operation, value = 'planner', plan()
        elif 'candidates' in data:
            operation = 'web_grounding_review'
            sources = {source['id']: source for source in originals(data)}
            reviews = []
            for candidate in data['candidates']:
                observation = candidate['observation']
                variable = observation['variable']
                marker, answer = FACTS[variable]
                assert observation['stance'] == 'support'
                assert type(observation['value']) is type(answer)
                assert observation['value'] == answer
                assert all(observation[key] == data['requested_scopes'][variable][key]
                           for key in ('entity_scope', 'time_scope'))
                assert observation['source_ids'] and all(
                    marker in sources[source_id]['text']
                    for source_id in observation['source_ids'])
                reviews.append({'candidate_id': candidate['candidate_id'],
                                'verdict': 'entailed',
                                'reason': 'The exact cited original states this scoped package fact.'})
            assert reviews
            value = {'reviews': reviews}
        elif 'requested_search_needs' in data:
            operation = 'corpus_search'
            node = data['task_id']
            parents = data['supported_parent_bindings']
            if node == 'offline':
                assert parents['p']['value'] == 'Star E3'
            elif node == 'backup':
                assert parents['s']['value'] is True
            else:
                assert node == 'primary' and not parents
            value = {'query': node, 'reason': 'Search the invented corpus for this factual subproblem.'}
        else:
            assert 'variables' in data and 'source_spans' in data
            operation = 'audit_joint' if 'audit_instruction' in data else 'joint_read'
            sources = originals(data)
            slots = []
            for variable, declaration in data['variables'].items():
                marker, answer = FACTS[variable]
                cited = [source['id'] for source in sources if marker in source['text']]
                rows = []
                if cited and operation != 'audit_joint':
                    demand = next(step for step in plan()['steps']
                                  if step['output_slot'] == declaration['demand'])
                    parents = {name: parent['version']
                               for name, parent in data['supported_parents'].items()
                               if parent['demand'] in demand['inputs']}
                    if variable == 's':
                        assert data['supported_parents']['p']['value'] == 'Star E3'
                    rows = [{'id': variable + '-original', 'stance': 'support', 'value': answer,
                             'source_ids': cited, **data['requested_scopes'][variable],
                             'parent_versions': parents, 'retract_ids': [],
                             'reason': 'This exact original explicitly states the scoped fact.'}]
                slot = {'variable': variable, 'observations': rows, 'unresolved': []}
                if operation == 'joint_read' and data['task']['execution'] == 'retrieval':
                    slot['reading_status'] = ('evidence_assessment' if rows
                                              else 'no_relevant_evidence')
                slots.append(slot)
            value = {'slots': slots}
            if operation == 'audit_joint':
                value['audit_verdict'] = 'supported'
        self.requests.append((operation, deepcopy(payload)))
        return {'choices': [{'finish_reason': 'stop',
                             'message': {'content': json.dumps(value)}}]}


@contextmanager
def fixture_service(model):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                count = fixture_token_count(payload['messages'])
                if self.path == '/tokenize':
                    assert set(payload) == {'model', 'messages', 'add_generation_prompt'}
                    assert payload['add_generation_prompt'] is True
                    assert payload['model'] == 'invented-corpus-fixture'
                    model.tokenizations.append(deepcopy(payload))
                    value = {'count': count, 'max_model_len': 16384}
                else:
                    assert self.path == '/v1/chat/completions', self.path
                    value = model.answer(payload)
                    value['usage'] = {'prompt_tokens': count, 'completion_tokens': 50,
                                      'total_tokens': count + 50}
                raw, code = json.dumps(value).encode(), 200
            except Exception as exc:
                model.errors.append(type(exc).__name__ + ': ' + str(exc))
                raw, code = b'{"error":"invalid offline fixture request"}', 500
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@contextmanager
def loopback_only():
    """Reject accidental external connections and suppress ambient model keys."""
    original = socket.create_connection

    def connect(address, *args, **kwargs):
        assert address[0] == '127.0.0.1', 'Offline fixture attempted a non-loopback connection'
        return original(address, *args, **kwargs)

    # Bypass every ambient proxy so a stray external URL cannot escape the
    # direct socket guard through a proxy listening on localhost.
    environment = {'NO_PROXY': '*', 'no_proxy': '*',
                   'DAG_LLM_API_KEY': '', 'BRIDGETREE_CHAT_API_KEY': ''}
    with patch.dict(os.environ, environment), patch('socket.create_connection', connect):
        yield


def main():
    model, summaries = FixtureModel(), []
    with tempfile.TemporaryDirectory(prefix='dagbt-browsecomp-smoke-') as temporary:
        directory = Path(temporary)
        data = directory / 'invented-corpus'
        prepare([{'query_id': 'offline-invented', 'query': QUESTION,
                  'answer': 'Unused invented preparation placeholder.',
                  'evidence_doc_ids': [], 'gold_doc_ids': []}],
                [{'docid': docid, 'url': 'https://fixture.invalid/' + docid, 'text': text}
                 for docid, text in DOCUMENTS.items()], data, fixture=True)
        # Even fixture references are absent during generation.
        (data / 'evaluation_only.json').unlink()
        questions, manifest = load_questions(data, allow_fixture=True)
        assert manifest['fixture'] is True and len(questions) == 1
        receipt = verify_corpus(data, allow_fixture=True)
        with loopback_only(), fixture_service(model) as endpoint:
            for method in (RESIDUAL_V2, JOINT):
                before, token_before = len(model.requests), len(model.tokenizations)
                config = {
                    'model_profile': 'bridgetree', 'llm_base_url': endpoint + '/v1',
                    'llm_model': 'invented-corpus-fixture', 'request_timeout_seconds': 10,
                    'max_identical_attempts': 1,
                    'tokenization': {'mode': 'vllm_chat', 'endpoint': endpoint + '/tokenize',
                                     'timeout_seconds': 5},
                    'browsecomp_plus': {'top_k': 1, 'max_actions': 36},
                    'fusion': {'set_score_calls': 0, 'reader_calls': 0,
                               'initial_width': 1, 'proposal_width': 1}}
                with Corpus(data, allow_fixture=True, verify=False, receipt=receipt) as corpus:
                    engine = BrowseCompEngine(questions[0],
                        ({}, [], np.empty((0, 0), dtype=np.float32), None, BTTokenAccounting()),
                        SimpleNamespace(output=str(directory / method)), config, method, corpus=corpus)
                    row = engine.run()
                assert not model.errors, model.errors
                assert row['answer']['status'] == 'ok', row['answer']
                assert row['answer']['prediction'] == 'Star E3'
                assert row['answer']['completion_kind'] == 'certified_symbolic'
                assert engine.steps == plan()['steps'] and len(engine.steps) == 4
                operations = [operation for operation, _ in model.requests[before:]]
                expected = 2 if method == RESIDUAL_V2 else 3
                assert operations[:2] == ['planner', 'corpus_search']
                assert operations[-1] == 'audit_joint'
                assert operations.count('corpus_search') == expected
                assert operations.count('joint_read') >= expected
                reviews = operations.count('web_grounding_review')
                assert reviews >= expected
                assert engine.ledger.used['llm'] == len(operations) <= 24
                assert engine.ledger.used['search_actions'] == expected
                assert engine.ledger.used['json_repairs'] == 0
                assert all(engine.ledger.used[kind] == 0 for kind in
                           ('ann', 'embedding_http', 'rerank_http', 'set_score', 'reader'))
                assert engine.ledger.limits['llm'] == 24
                assert engine.ledger.limits['json_repairs'] == 6
                assert engine.ledger.limits['search_actions'] == 36
                assert engine.s['context_tokens'] == 16384
                assert engine.s['reasoning_output_tokens'] == 4096
                assert engine.s['reserved_audit_calls'] == 1
                assert engine.calls.token_counter is not None
                validations = [event for event in engine.ledger.events
                               if event['event'] == 'tokenization_usage_validation']
                assert len(validations) == len(operations)
                assert all(event['status'] == 'matched' for event in validations)
                tokenizations = len(model.tokenizations) - token_before
                assert tokenizations >= len(operations)
                assert set(engine.docs) == set(DOCUMENTS) - (
                    {'invented-backup'} if method == RESIDUAL_V2 else set())
                assert all(document.passage == DOCUMENTS[docid]
                           and document.metadata['corpus_text_sha256'] ==
                           sha256(DOCUMENTS[docid].encode()).hexdigest()
                           for docid, document in engine.docs.items())
                review_events = [event for event in engine.events
                                 if event['event'] == 'web_grounding_review_completed']
                assert len(review_events) == reviews
                assert all(event['error_type'] is None and all(
                    decision['verdict'] == 'entailed' for decision in event['decisions'].values())
                           for event in review_events)
                assert not engine.errors, engine.errors
                summaries.append({'arm': method, 'status': 'ok',
                                  'completion_kind': row['answer']['completion_kind'],
                                  'corpus_search_calls': expected, 'grounding_reviews': reviews,
                                  'llm_calls': engine.ledger.used['llm'],
                                  'tokenization_http_calls': tokenizations,
                                  'tokenization_usage_matches': len(validations),
                                  'embedding_calls': 0, 'rerank_calls': 0})
    print(json.dumps({'offline_http_smoke': summaries, 'external_network_used': False},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
