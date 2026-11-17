"""PrefEval provenance, isolation and complete original/residual worker integration.

All model calls in this file go to a scripted loopback HTTP server. Scripted
scores prove plumbing only, never benchmark accuracy.
"""
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import urllib.request

import numpy as np
import pytest

from dagbt import prefeval, runner
from dagbt.methods import RESIDUAL_V2, capabilities
from dagbt.resources import scope_resources, ensure_index, inspect_index
from test_v4_personal_task import plan as personal_plan
from test_bt_profile_system import scripted_bt_models

ROOT = runner.ROOT


def script_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_full_pinned_public_dataset_and_runtime_never_open_labels_or_raw(monkeypatch):
    actual = Path.open
    def guarded(path, *args, **kwargs):
        if 'evaluation_only.json' in str(path) or 'third_party/prefeval' in str(path):
            raise AssertionError('Generation opened raw/gold artifact: ' + str(path))
        return actual(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded)
    report = prefeval.validate_dataset(ROOT)
    questions = runner.load_questions('prefeval')
    assert report['questions'] == len(questions) == 12000
    assert report['topics'] == 20 and report['documents'] == 10410
    assert report['by_turns'] == {str(n): 3000 for n in prefeval.TURNS}
    assert report['labels_read'] is False
    assert capabilities(RESIDUAL_V2).residual_control
    assert capabilities(RESIDUAL_V2).joint_reading


def test_all_forms_options_and_gold_follow_official_mcq_permutation():
    qs = prefeval.load_questions(ROOT)
    public = {q['id']: q for q in qs}
    labels = {r['id']: r['correct_answer'] for r in prefeval.load(ROOT / 'data/prefeval/evaluation_only.json')}
    raw = ROOT / 'third_party/prefeval/benchmark_dataset'
    for topic in sorted({q['topic'] for q in qs}):
        rng = random.Random(41)
        rows = prefeval.load(raw / 'mcq_options' / (topic + '.json'))
        for i, row in enumerate(rows):
            order = rng.sample(range(4), 4)
            for form in prefeval.FORMS:
                for turns in prefeval.TURNS:
                    q = public[f'prefeval-{topic}-{i:04d}-{form}-t{turns:03d}']
                    assert q['options'] == [row['classification_task_options'][j] for j in order]
                    assert labels[q['id']] == chr(97 + order.index(0))
                    assert q['user_question'] == row['question']
                    assert set(q) == prefeval.FIELDS
    assert set(Counter(labels.values())) == set('abcd')


def test_implicit_never_injects_explicit_annotations_and_scope_shrinks_safely():
    sentinel = {'preference': 'SECRET_EXPLICIT_GOLD', 'persona': 'SECRET_PERSONA',
                'explanation': 'SECRET_EXPLANATION', 'aligned_op': 'SECRET_OPTION',
                'conversation': {'query': 'q', 'assistant_options': 'choices',
                                 'user_selection': 'selection', 'assistant_acknowledgment': 'ack'}}
    assert 'SECRET' not in json.dumps(prefeval.preference_messages(sentinel, 'implicit_choice'))
    sentinel['conversation'] = {'0': {'user': 'said', 'assistant': 'replied'}}
    assert 'SECRET' not in json.dumps(prefeval.preference_messages(sentinel, 'implicit_persona'))
    questions = prefeval.load_questions(ROOT)
    first = questions[0]
    qs = [next(q for q in questions if q['shared_context_id'] == first['shared_context_id'] and q['inter_turns'] == t)
          for t in (300, 0)]
    other = next(q for q in questions if q['question_type'] == 'implicit_choice' and q['inter_turns'] == 0)
    scopes = prefeval.load_scopes(ROOT)
    ids = list(dict.fromkeys(d for q in [*qs, other] for d in scopes[q['scope_id']]))
    docs = {d: SimpleNamespace(doc_id=d) for d in ids}
    vectors = np.ones((len(ids), 2), np.float32)
    resources = (docs, ids, vectors, SimpleNamespace(lock=threading.Lock()), object())
    large = scope_resources(resources, scopes[qs[0]['scope_id']])
    large[3]._v2_matrix = large[2]
    small = scope_resources(resources, scopes[qs[1]['scope_id']])
    different = scope_resources(resources, scopes[other['scope_id']])
    assert set(small[1]) < set(large[1])
    assert not hasattr(small[3], '_v2_matrix')
    assert set(small[1]).isdisjoint(different[1])


@contextmanager
def prefeval_models():
    """Script the two real solver protocols; never consult evaluation labels."""
    requests, errors = [], []
    with scripted_bt_models('fixture') as (upstream, original_requests, original_errors):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def send(self, value, status=200):
                raw = json.dumps(value).encode(); self.send_response(status)
                self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw)))
                self.end_headers(); self.wfile.write(raw)
            def do_GET(self):
                self.send({'data': [{'id': 'deepseek-v4-flash'}, {'id': 'qwen3-embedding-8b'}]})
            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length'])); payload = json.loads(raw)
                requests.append({'path': self.path, 'payload': payload})
                try:
                    if self.path == '/tokenize':
                        self.send({'count': 11, 'max_model_len': 120000}); return
                    messages = payload.get('messages', [])
                    system = messages[0]['content'] if messages else ''
                    if system.startswith('You are a long-document QA reader'):
                        self.send({'choices': [{'message': {'content': 'Answer: (a)'}, 'finish_reason': 'stop'}],
                                   'usage': {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18}})
                        return
                    if system.startswith('Plan an executable dependency DAG'):
                        question = json.loads(messages[1]['content'])
                        value = personal_plan()
                        value['steps'][0]['question'] = "Find the user's recorded preferences relevant to the current request"
                        value['steps'][-1]['question'] = question
                        if 'PERSONAMEM RESPONSE-SELECTION CONTRACT' not in system:
                            del value['program']['variables']['history']['evidence_semantics']
                    elif system.startswith('Read source text as evidence'):
                        data = json.loads(messages[1]['content'])
                        if 'source_span_columns' in data:
                            data['source_spans'] = [dict(zip(data['source_span_columns'], row)) for row in data['source_spans']]
                        terminal = 'public_options' in data and 'terminal_candidate' not in data
                        audit = 'terminal_candidate' in data
                        options = data.get('public_options')
                        if audit:
                            semantic = data['terminal_candidate']['value']
                        elif terminal:
                            semantic = options[0]
                        rows = []
                        for variable in data['requested_slots']:
                            observations = []
                            if not audit and (variable == 'response' or not terminal):
                                observations = [{'id': variable + '-source', 'stance': 'support',
                                    'value': semantic if variable == 'response' else 'The user has a recorded preference relevant to this request.',
                                    'source_ids': [data['source_spans'][0]['id']], **data['requested_scopes'][variable],
                                    'parent_versions': ({'history': data['supported_parents']['history']['version']} if variable == 'response' else {}),
                                    'retract_ids': [], 'reason': 'Scripted fixture only, not a model quality claim'}]
                            rows.append({'variable': variable, 'observations': observations, 'unresolved': []})
                        value = {'slots': rows}
                        if terminal: value.update(final_prediction='a', semantic_answer=semantic)
                        if audit: value['audit_verdict'] = 'supported'
                    else:
                        request = urllib.request.Request(upstream + self.path, data=raw, headers={'Content-Type': 'application/json'})
                        with opener.open(request, timeout=20) as response:
                            self.send(json.load(response)); return
                    self.send({'choices': [{'message': {'content': json.dumps(value)}, 'finish_reason': 'stop'}],
                               'usage': {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18}})
                except Exception as exc:
                    errors.append(repr(exc)); self.send({'fixture_error': repr(exc)}, 400)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}', requests, errors, original_errors
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)


def test_real_spawned_original_and_full_residual_detached_cli(tmp_path, monkeypatch):
    for name in ('DAG_LLM_API_KEY', 'DAG_EMBED_API_KEY', 'DAG_RERANK_API_KEY', 'BRIDGETREE_CHAT_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    config = runner.load(ROOT / 'configs/prefeval-v4.json')
    credentials = tmp_path / 'empty.json'; runner.save(credentials, {})
    wrapper = script_module('prefeval_v4')
    selection = wrapper.selected_ids([10], list(prefeval.FORMS), smoke=True)
    all_qs = prefeval.load_questions(ROOT)
    # A second smaller scope in the same persistent workers detects stale ANN caches.
    first = next(q for q in all_qs if q['id'] == selection['prefeval'][0])
    zero = next(q for q in all_qs if q['shared_context_id'] == first['shared_context_id'] and q['inter_turns'] == 0)
    selection['prefeval'].append(zero['id'])
    selected = tmp_path / 'selected.json'; runner.save(selected, selection)
    output = tmp_path / 'run'
    with prefeval_models() as (endpoint, requests, errors, original_errors):
        config.update(llm_base_url=endpoint + '/v1', embedding_base_url=endpoint + '/v1',
                      credentials_file=str(credentials), derived_index_dir=str(tmp_path / 'index'),
                      request_timeout_seconds=20, max_identical_attempts=1)
        config['tokenization']['endpoint'] = endpoint + '/tokenize'
        config['experiment'].update(question_timeout_seconds=90, worker_startup_timeout_seconds=90)
        config_path = tmp_path / 'config.json'; runner.save(config_path, config)
        launched = subprocess.run([sys.executable, '-m', 'dagbt.runner', 'launch', '--config', str(config_path),
            '--datasets', 'prefeval', '--arms', 'original', RESIDUAL_V2, '--output', str(output),
            '--question-ids-file', str(selected)], cwd=ROOT, capture_output=True, text=True, timeout=60)
        assert launched.returncode == 0, launched.stderr
        record = json.loads(launched.stdout)
        process = record['launched_pid']
        deadline = time.monotonic() + 160
        while time.monotonic() < deadline:
            state = runner.status(output)
            progress = state.get('progress') or {}
            if progress.get('state') in {'complete', 'complete_with_failures', 'failed', 'stopped'} and not state['live_writer']:
                break
            # Poll this exact PID; never restart on an observation timeout.
            subprocess.run(['ps', '-p', str(process), '-o', 'pid='], capture_output=True)
            time.sleep(.3)
        assert progress.get('state') == 'complete', (progress, (output / 'launcher.log').read_text()[-12000:])
        assert not errors and not original_errors, (errors, original_errors)
        status = wrapper.status(output)
        assert status['completed_tasks'] == status['total_tasks'] == 8
        report = wrapper.accuracy(output)
        assert report['paired']['同题含失败']['n'] == 4
        qs = {q['id']: q for q in all_qs}; scopes = prefeval.load_scopes(ROOT)
        for arm in wrapper.ARMS:
            for unit in selection['prefeval']:
                row = runner.load(runner.result_path(output, 'prefeval', arm, unit))
                assert row['answer']['status'] == 'ok', row['answer']
                visible = set(scopes[qs[unit]['scope_id']])
                assert set(row['diagnostics']['memory_scope']['visible_doc_ids']) == visible
                assert set(row['diagnostics'].get('candidate_doc_ids', [])) <= visible
                if arm == RESIDUAL_V2:
                    assert row['algorithm_version'] == RESIDUAL_V2 and row['method'] == RESIDUAL_V2
                    assert row['diagnostics']['audit_complete']
                    assert row['answer']['semantic_answer'] == qs[unit]['options'][0]
                    assert row['answer']['completion_kind'] == 'semantic_assessment'
        hashes = [runner.load(output / 'prefeval' / arm / 'resource_hashes.json') for arm in wrapper.ARMS]
        assert hashes[0] == hashes[1]
        wire = json.dumps(requests)
        assert all(marker not in wire for marker in ('correct_answer', 'evaluation_only.json', 'aligned_op', 'classification_task_options'))
        assert any(r['path'] == '/tokenize' for r in requests)
        assert any('Read source text as evidence' in str(r['payload']) for r in requests)
        summary = runner.load(output / 'prefeval/summary.json')
        assert len(summary['by_condition']) == 4
        assert all('persona_macro_accuracy_percent' not in v for v in summary['arms'].values())
        # Re-running exactly the same finished run must not generate/re-embed any question.
        before = len(requests)
        args = SimpleNamespace(config=str(config_path), datasets=['prefeval'], arms=wrapper.ARMS,
            output=str(output), limit=None, question_ids_file=str(selected), retry_failed=False, offline_preflight=False)
        runner.run_experiment(args)
        assert len(requests) == before


def test_prefeval_scores_failures_and_label_gate(tmp_path):
    qs = [dict(id='p1', options=['a','b','c','d'], persona_id='unused', question='Q',
               question_type='explicit', inter_turns=10)]
    opened = []
    for arm in ('original', RESIDUAL_V2):
        row = {'unit_id': 'p1', 'answer': {'status': 'ok', 'prediction': 'b'},
               'budgets': {str(k): {'selected_doc_ids': []} for k in (5,10,20)}, 'diagnostics': {}}
        if arm == RESIDUAL_V2:
            row.update(method=arm, algorithm_version=arm, budgets={})
            row['answer'].update(status='unresolved_or_exhausted', prediction=None,
                answer_source='dag_terminal', final_node_id='response', sources=None)
        runner.save(runner.result_path(tmp_path, 'prefeval', arm, 'p1'), row)
    with pytest.raises(ValueError, match='labels remain unread'):
        runner.score_all(tmp_path, {'prefeval': qs, 'hotpotqa': [{'id':'missing'}]},
            ['original', RESIDUAL_V2], label_loader=lambda d: opened.append(d))
    assert opened == []
    summary = runner.score_all(tmp_path, {'prefeval': qs}, ['original', RESIDUAL_V2],
        label_loader=lambda d: [{'id':'p1','correct_answer':'b'}])['prefeval']
    assert summary['arms']['original']['all_task_metrics_percent']['accuracy'] == 100
    assert summary['arms'][RESIDUAL_V2]['all_task_metrics_percent']['accuracy'] == 0
    assert summary['paired'][RESIDUAL_V2]['all_task_delta_percentage_points']['accuracy'] == -100


def test_official_rebuild_is_byte_identical_for_all_conditions(tmp_path):
    report = prefeval.prepare_dataset(ROOT / 'third_party/prefeval', tmp_path)
    assert report['questions'] == 12000
    for name in (*prefeval.PUBLIC_FILES, 'evaluation_only.json', 'manifest.json'):
        assert runner.file_hash(tmp_path / 'data/prefeval' / name) == runner.file_hash(ROOT / 'data/prefeval' / name)


def test_low_disk_stops_before_allocating_an_attempt(tmp_path, monkeypatch):
    import shutil
    calls = []
    class NoCalls:
        def __init__(self, *args): pass
        def run(self, *args): calls.append('run'); raise AssertionError('Should stop before model call')
        def close(self): calls.append('closed')
    monkeypatch.setattr(shutil, 'disk_usage', lambda _: SimpleNamespace(free=1024))
    with pytest.raises(RuntimeError, match='less than 2 GiB'):
        runner.generate_dataset(tmp_path, 'prefeval', [{'id':'disk-test'}],
            ['original', RESIDUAL_V2], {'experiment': {'max_question_attempts':1}}, worker_factory=NoCalls)
    assert calls == ['closed', 'closed']
    assert not list(tmp_path.glob('prefeval/*/attempts/*/attempt-*'))


def test_interrupted_single_attempt_publishes_failure_with_arm_identity(tmp_path):
    class NoCalls:
        def __init__(self, *args): pass
        def run(self, *args): raise AssertionError('Interrupted attempt cannot be rerun for free')
        def close(self): pass
    q = {'id':'interrupted'}
    for arm in ('original', RESIDUAL_V2):
        (tmp_path / 'prefeval' / arm / 'attempts' / runner.digest(q['id']) / 'attempt-001').mkdir(parents=True)
    runner.generate_dataset(tmp_path, 'prefeval', [q], ['original', RESIDUAL_V2],
        {'experiment': {'max_question_attempts':1}}, worker_factory=NoCalls)
    for arm in ('original', RESIDUAL_V2):
        row = runner.validate_result(runner.load(runner.result_path(tmp_path, 'prefeval', arm, q['id'])), q['id'])
        assert row['answer']['status'] == 'execution_failed'
        assert row['runner'] == {'arm':arm, 'dataset':'prefeval', 'attempt':1, 'recovered_interrupted_attempt':True}
