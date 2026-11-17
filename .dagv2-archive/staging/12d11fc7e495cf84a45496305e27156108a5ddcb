"""Invented corpus integration: paid search, scoped originals and finite control."""
from copy import deepcopy
from hashlib import sha256
import json

import numpy as np
import pytest

from dagbt.browsecomp_engine import BrowseCompEngine, settings
from dagbt.methods import JOINT, RESIDUAL_V2
from test_webwalker import Model, demo, plan


class Corpus:
    def __init__(self, documents, results, snippets=None):
        self.documents, self.results, self.snippets = documents, results, snippets or {}
        self.searches, self.reads = [], []

    def search(self, query, top_k=5, *, offset=0, exclude_doc_ids=()):
        self.searches.append((query, top_k, offset, tuple(exclude_doc_ids)))
        identifiers = [identifier for identifier in self.results.get(query, ())
                       if identifier not in exclude_doc_ids][offset:offset + top_k]
        result = []
        for identifier in identifiers:
            text = self.documents[identifier]
            start, end = self.snippets.get(identifier, (0, min(200, len(text))))
            result.append({'docid': identifier, 'url': 'https://invented.example/' + identifier,
                           'score': -1.0, 'snippet': text[start:end], 'start': start, 'end': end})
        return result

    def get(self, identifier):
        self.reads.append(identifier)
        text = self.documents[identifier]
        return {'docid': identifier, 'url': 'https://invented.example/' + identifier,
                'text': text, 'text_sha256': sha256(text.encode()).hexdigest()}


def leaf_plan():
    return {'steps': [demo.step('primary', 'Find the primary package')],
            'final_node_id': 'primary', 'output_contract': demo.contract('value', 'entity', 'package'),
            'program': {'variables': {'p': {'type': 'entity', 'demand': 'primary'}},
                        'expression': demo.var('p')}}


def reply(value):
    return {'response': {'choices': [{'finish_reason': 'stop',
                                     'message': {'content': json.dumps(value)}}]}}


def originals(data):
    sources = data['source_spans']
    if 'source_span_columns' in data:
        sources = [dict(zip(data['source_span_columns'], source)) for source in sources]
    return sources


class SourceModel(Model):
    def __init__(self, initial=None, queries=None, reading=None, review=None):
        super().__init__()
        self.initial, self.queries = initial or plan(), queries or {}
        self.reading, self.review, self.query_counts = reading, review, {}

    def get(self, stage, url, payload):
        operation = stage[0]
        assert not url.endswith('/embeddings') and 'rerank' not in url
        data = json.loads(payload['messages'][1]['content'])
        if operation == 'planner':
            value = self.initial
        elif operation == 'corpus_search':
            node = data['task_id']
            default = 'backup' if 'backup' in data['subproblem'].lower() else 'offline' if node == 'offline' else 'primary'
            choices = self.queries.get(node, [default])
            index = self.query_counts.get(node, 0)
            self.query_counts[node] = index + 1
            value = {'query': choices[min(index, len(choices) - 1)],
                     'reason': 'Use these keywords for this grounded factual subproblem.'}
        elif self.reading and operation.startswith('joint_read'):
            value = self.reading(operation, data)
        elif self.review and operation == 'web_grounding_review':
            value = self.review(data)
        else:
            return super().get(stage, url, payload)
        self.requests.append((operation, deepcopy(payload)))
        return reply(value)


def engine(corpus, model=None, method=RESIDUAL_V2, options=None):
    model = model or SourceModel()
    tokenizer = demo.Tokenizer()
    config = {'_test_transport': True, 'llm_base_url': 'http://fixture/v1', 'llm_model': 'fixture',
              'browsecomp_plus': options or {},
              'fusion': {'initial_width': 1, 'proposal_width': 1, 'max_feedback_rounds': 0}}
    result = BrowseCompEngine({'id': 'invented', 'question': 'Use primary if offline, otherwise backup.'},
        ({}, [], np.empty((0, 0), dtype=np.float32), None, tokenizer), model, config, method, corpus=corpus)

    def count(stage, url, payload):
        # Exact only for this scripted whitespace-chat model, never production.
        prompt = tokenizer.apply_chat_template(payload['messages'], tokenize=False, add_generation_prompt=True)
        return {'count': len(tokenizer.encode(prompt, add_special_tokens=False)),
                'token_count_is_estimate': False, 'tokenizer_id': 'demo_whitespace_v1',
                'token_estimator_id': 'fixture_whitespace_chat_v1'}
    result.calls.count_reasoning_tokens = count
    return result, model


@pytest.mark.parametrize('method, searches', [(RESIDUAL_V2, ['primary', 'offline']),
                                             (JOINT, ['primary', 'offline', 'backup'])])
def test_paid_corpus_multihop_preserves_full_dag_and_method_difference(method, searches):
    corpus = Corpus({'a': 'Primary package: Star E3.', 'b': 'Star E3 can run offline: true.',
                     'c': 'Backup package: Moon B2.'},
                    {'primary': ['a'], 'offline': ['b'], 'backup': ['c']})
    e, model = engine(corpus, method=method)
    row = e.run()
    assert row['answer']['status'] == 'ok' and row['answer']['prediction'] == 'Star E3'
    assert row['answer']['completion_kind'] == 'certified_symbolic'
    assert e.steps == plan()['steps'] and len(e.steps) == 4
    assert [query for query, *_ in corpus.searches] == searches
    operations = [operation for operation, _ in model.requests]
    assert operations[0:2] == ['planner', 'corpus_search']
    assert 'web_grounding_review' in operations and operations[-1] == 'audit_joint'
    assert e.events.index(next(event for event in e.events if event['event'] == 'plan_frozen')) < e.events.index(
        next(event for event in e.events if event['event'] == 'corpus_search_step'))
    assert e.ledger.used['llm'] == len(model.requests)
    assert e.ledger.used['search_actions'] == len(searches)
    assert not e.ledger.used['ann'] and not e.ledger.used['rerank_http'] and not e.ledger.used['set_score']
    assert e.s['context_tokens'] == 16384 and e.s['reasoning_output_tokens'] == 4096
    assert e.ledger.limits['llm'] == 24 and e.ledger.limits['json_repairs'] == 6
    assert e.ledger.limits['search_actions'] == 36 and e.s['reserved_audit_calls'] == 1
    assert e.navigation_provenance['b']['source_doc_ids'] == ['a']
    assert all(item['dependency_claim'] is False for item in e.navigation_provenance.values())
    assert not e.errors and row['diagnostics']['cost']['corpus_search_calls'] == len(searches)


def slot(data, observation=None):
    return {'slots': [{'variable': 'p', 'observations': [observation] if observation else [],
                      'unresolved': [], 'reading_status': 'evidence_assessment' if observation else 'no_relevant_evidence'}]}


def observation(data, identifier, value, sources, stance='support'):
    return {'id': identifier, 'stance': stance, 'value': value, 'source_ids': sources,
            **data['requested_scopes']['p'], 'parent_versions': {}, 'retract_ids': [],
            'reason': 'Judge only the exact cited original at the requested package scope.'}


def test_wrong_entity_is_vetoed_then_same_draft_corrected_without_fact_or_permission_injection():
    def reading(operation, data):
        sources = originals(data)
        if 'repair_scope' in data:
            failed = data['repair_scope']['failed'][0]
            assert failed['id'] == 'wrong-package' and failed['observation']['value'] == 'Moon B2'
            return slot(data, observation(data, failed['id'], None, [sources[0]['id']], 'irrelevant'))
        source = next((source for source in sources if 'Primary package: Star E3' in source['text']), None)
        return slot(data, observation(data, 'correct-package', 'Star E3', [source['id']]) if source else
                    observation(data, 'wrong-package', 'Moon B2', [sources[0]['id']]))

    def review(data):
        return {'reviews': [{'candidate_id': candidate['candidate_id'],
            'verdict': 'not_entailed' if candidate['observation']['value'] == 'Moon B2' else 'entailed',
            'reason': 'The other package original does not establish the requested primary package.'}
            for candidate in data['candidates']]}

    corpus = Corpus({'wrong': 'Other package: Moon B2.', 'right': 'Primary package: Star E3.'},
                    {'other package': ['wrong'], 'primary': ['right']})
    model = SourceModel(leaf_plan(), {'primary': ['other package', 'primary']}, reading, review)
    e, _ = engine(corpus, model)
    row = e.run()
    assert row['answer']['status'] == 'ok' and row['answer']['prediction'] == 'Star E3'
    assert e.ledger.used['json_repairs'] == 1 and not e.residual_control.reader.failed_batch_reviews
    assert not e.residual_control.reader.evidence_obligations
    assert all(route['value'] != 'Moon B2' for route in e.fact_state.routes.values())
    assert [operation for operation, _ in model.requests][2:6] == [
        'joint_read', 'web_grounding_review', 'joint_read_repair', 'web_grounding_review']


def test_exact_snippet_prioritizes_original_window_without_discarding_body_or_offsets():
    noise = 'An invented unrelated catalogue entry is filed here.\n' * 6000
    text = noise + 'Primary package: Star E3.'
    corpus = Corpus({'long': text}, {'primary': ['long']}, {'long': (len(noise), len(text))})
    e, _ = engine(corpus, SourceModel(leaf_plan()))
    row = e.run()
    assert row['answer']['status'] == 'ok'
    assert e.docs['long'].passage == text
    sources = list(e.mapper.sources.values())
    assert ''.join(source['text'] for source in sources) == text
    assert all(source['text'] == text[source['start']:source['end']] for source in sources)
    first = e.residual_control.reader.source_exposures[0]
    assert any('Primary package: Star E3' in e.mapper.sources[source['source_alias']]['text']
               for source in first['sources'])
    assert e.residual_control.reader.discovery_frontier  # Unoffered originals remain archived.


def test_long_document_yields_to_paid_search_and_resumes_its_original_frontier():
    text = 'An invented unrelated catalogue entry is filed here.\n' * 6000
    corpus = Corpus({'long': text, 'middle': 'An unrelated short catalogue.', 'answer': 'Primary package: Star E3.'},
                    {'long': ['long'], 'middle': ['middle'], 'primary': ['answer']})
    e, _ = engine(corpus, SourceModel(leaf_plan(), {'primary': ['long', 'middle', 'primary']}))
    row = e.run()
    assert row['answer']['status'] == 'ok'
    events = [event['event'] for event in e.events]
    assert 'corpus_document_window_yielded' in events and 'corpus_document_window_resumed' in events
    assert [query for query, *_ in corpus.searches] == ['long', 'middle', 'primary']
    assert e.docs['long'].passage == text
    assert e.ledger.used['search_actions'] == 3


@pytest.mark.parametrize('choice, calls, status', [(None, 1, 'unresolved_or_exhausted'),
                                                ('', 1, 'unresolved_or_exhausted'),
                                                ('missing', 2, 'unresolved_or_exhausted')])
def test_stop_empty_and_repeated_exhausted_queries_are_bounded(choice, calls, status):
    corpus = Corpus({}, {})
    e, model = engine(corpus, SourceModel(leaf_plan(), {'primary': [choice]}))
    row = e.run()
    assert row['answer']['status'] == status and row['answer']['prediction'] is None
    assert e.ledger.used['search_actions'] == calls
    assert e.ledger.used['llm'] == len(model.requests) == calls + 1
    assert len(corpus.searches) == (1 if choice else 0)


def test_search_action_budget_is_distinct_and_preserves_paid_audit_reservation():
    corpus = Corpus({}, {})
    e, model = engine(corpus, SourceModel(leaf_plan(), {'primary': ['missing']}), options={'max_actions': 1})
    row = e.run()
    assert row['answer']['status'] == 'budget_exhausted'
    assert e.ledger.used['search_actions'] == 1 and len(corpus.searches) == 1
    assert e.ledger.used['llm'] == len(model.requests) == 2 and not e.ledger.used['ann']
    assert e.ledger.remaining('llm') >= e.s['reserved_audit_calls']
    assert e.errors[-1]['type'] == 'BudgetExceeded'


def test_repeated_query_paginates_real_unseen_documents_with_separate_paid_actions():
    corpus = Corpus({'a': 'An unrelated catalogue entry.', 'b': 'Primary package: Star E3.'},
                    {'primary': ['a', 'b']})
    e, model = engine(corpus, SourceModel(leaf_plan()), options={'top_k': 1})
    row = e.run()
    assert row['answer']['status'] == 'ok'
    assert corpus.searches == [('primary', 1, 0, ()), ('primary', 1, 0, ('a',))]
    assert corpus.reads == ['a', 'b'] and e.ledger.used['search_actions'] == 2
    assert sum(operation == 'corpus_search' for operation, _ in model.requests) == 2
    assert set(e.docs) == {'a', 'b'}


def test_invalid_keyword_json_keeps_the_original_two_paid_repair_bound():
    class Invalid(SourceModel):
        def get(self, stage, url, payload):
            if stage[0] == 'corpus_search':
                self.requests.append((stage[0], deepcopy(payload)))
                return reply({'query': ['an invalid keyword list'], 'reason': 'Malformed proposal.'})
            return super().get(stage, url, payload)
    corpus = Corpus({}, {})
    e, model = engine(corpus, Invalid(leaf_plan()))
    row = e.run()
    assert row['answer']['status'] != 'ok' and not corpus.searches
    assert e.ledger.used['search_actions'] == 1 and e.ledger.used['json_repairs'] == 2
    assert e.ledger.used['llm'] == len(model.requests) == 4
    assert [operation for operation, _ in model.requests] == ['planner'] + ['corpus_search'] * 3
    assert e.errors[-1]['type'] == 'ProtocolError'


@pytest.mark.parametrize('broken', ['hash', 'snippet'])
def test_mutated_original_or_inexact_snippet_cannot_reach_fact_reading(broken):
    class Broken(Corpus):
        def get(self, identifier):
            record = super().get(identifier)
            if broken == 'hash':
                record['text_sha256'] = '0' * 64
            return record
        def search(self, *args, **kwargs):
            result = super().search(*args, **kwargs)
            if broken == 'snippet':
                result[0]['snippet'] = 'Fabricated evidence.'
            return result
    corpus = Broken({'a': 'Primary package: Star E3.'}, {'primary': ['a']})
    e, model = engine(corpus, SourceModel(leaf_plan()))
    row = e.run()
    assert row['answer']['status'] != 'ok' and not e.fact_state.routes
    assert [operation for operation, _ in model.requests] == ['planner', 'corpus_search']
    assert e.ledger.used['search_actions'] == 1 and e.errors[-1]['type'] == 'ProtocolError'


@pytest.mark.parametrize('options', [{'top_k': 0}, {'top_k': 21}, {'max_actions': 37},
                                    {'max_actions': True}, {'unknown': 1}])
def test_invalid_adapter_settings_are_rejected(options):
    with pytest.raises(ValueError):
        settings({'browsecomp_plus': options})
