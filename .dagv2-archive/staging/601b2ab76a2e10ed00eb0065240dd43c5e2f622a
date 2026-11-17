"""Network-free validation of the pasteable interim scorer using real v2 score()."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

STAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE / 'installed_webwalker_only_v2'))
from dagbt import webwalker_runner as ww

INLINE = STAGE / 'webwalker_inline_score.txt'


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def file_bytes(directory):
    return {str(p.relative_to(directory)): p.read_bytes()
            for p in directory.rglob('*') if p.is_file()}


def execute_inline():
    namespace = {'__name__': '__main__', '__file__': str(INLINE)}
    try:
        exec(compile(INLINE.read_text(), str(INLINE), 'exec'), namespace)
        return namespace
    finally:
        # stdin Python exits after each invocation; simulate that fd lifecycle.
        if namespace.get('lock') is not None:
            namespace['lock'].close()


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('DAGBT_WEBWALKER_JUDGE_CONFIG', raising=False)
    monkeypatch.delenv('DAGBT_WEBWALKER_CONFIG', raising=False)
    questions = [
        {'id': f'fictional-{i}', 'question': f'Invented question {i}?',
         'root_url': f'https://fictional.invalid/{i}'} for i in range(3)
    ]
    data = {'questions_sha256': 'synthetic-dataset', 'questions': len(questions)}
    sources = {'dagbt/frozen_core.py': 'synthetic-source-hash'}
    config = {'llm_model': 'synthetic-no-network-judge'}
    monkeypatch.setattr(ww, 'effective_config', lambda path: config)
    monkeypatch.setattr(ww, 'load_questions', lambda path: (questions, data))
    monkeypatch.setattr(ww, 'load_references', lambda path:
                        {q['id']: {'answer': 'invented reference'} for q in questions})
    monkeypatch.setattr(ww, 'generation_sources', lambda: sources)
    monkeypatch.setattr(ww, 'configure_model_network', lambda config: None)
    monkeypatch.setattr(ww, 'resolve', lambda config, arm: {})
    monkeypatch.setattr(ww, 'load_tokenizer', lambda config: object())
    calls = []
    behavior = {'mode': 'normal'}

    class FakeTransport:
        def __init__(self, unit, directory, config, ledger, tokenizer):
            self.unit, self.directory = unit, Path(directory)

    class FakeReasoner:
        def __init__(self, transport, tokenizer, config, settings, ledger, emit):
            self.transport = transport

        def json(self, stage, system, judge_input, validate, schema, **kwargs):
            assert stage == 'audit_web_judge'
            calls.append({'unit': self.transport.unit, 'directory': self.transport.directory,
                          'input': judge_input})
            if behavior['mode'] == 'fail':
                raise RuntimeError('synthetic judge outage')
            verdict = {'correct': ww.JOINT in str(self.transport.directory),
                       'reason': 'synthetic judgement'}
            return validate(verdict)

    monkeypatch.setattr(ww, 'Transport', FakeTransport)
    monkeypatch.setattr(ww, 'Reasoner', FakeReasoner)
    source = tmp_path / 'outputs' / 'webwalkerqa_v4_access_v13_full'
    base = source.with_name(source.name + '_inline_scores')
    manifest = {'protocol': ww.VERSION, 'access_policy': ww.ACCESS_POLICY,
                'core_release': ww.CORE_RELEASE, 'data': data,
                'generation_source_hashes': sources,
                'config_identity': ww.digest(config),
                'arms': list(ww.ARMS), 'question_ids': [q['id'] for q in questions],
                'tasks': len(questions) * len(ww.ARMS)}
    write_json(source / 'manifest.json', manifest)
    write_json(source / 'progress.json', {'state': 'running', 'completed': 0, 'total': 6})

    def publish(qid, arm, status='ok', prediction='invented prediction', **extra):
        row = {'unit_id': qid, 'method': arm, 'dataset': 'webwalkerqa',
               'answer': {'status': status, 'prediction': prediction}, **extra}
        write_json(ww.task_path(source, qid, arm) / 'result.json', row)
        return row

    def report():
        return json.loads((base / 'report.json').read_text())

    def cache_task(qid, arm):
        path = ww.task_path(source, qid, arm) / 'result.json'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return base / ww.digest({'generation': manifest, 'judge': ww.digest(config)}) / qid / arm / digest

    return SimpleNamespace(source=source, base=base, manifest=manifest, config=config,
                           questions=questions, calls=calls, behavior=behavior,
                           publish=publish, report=report, cache_task=cache_task)


def test_joint_and_residual_valid_answers_use_real_full_scorer_gates(run):
    run.publish('fictional-0', ww.JOINT)
    run.publish('fictional-0', ww.RESIDUAL)
    run.publish('fictional-1', ww.JOINT, 'budget_exhausted', None)
    run.publish('fictional-1', ww.RESIDUAL, 'ok', '   ')
    before = file_bytes(run.source)
    execute_inline()
    assert len(run.calls) == 2
    report = run.report()
    assert report['arms'][ww.JOINT]['valid_answers'] == 1
    assert report['arms'][ww.JOINT]['accuracy'] == 1.0
    assert report['arms'][ww.RESIDUAL]['valid_answers'] == 1
    assert report['arms'][ww.RESIDUAL]['accuracy'] == 0.0
    assert file_bytes(run.source) == before
    for arm in ww.ARMS:
        directory = run.cache_task('fictional-0', arm)
        snap = json.loads((directory / 'manifest.json').read_text())
        assert snap['tasks'] == 1
        assert snap['question_ids'] == ['fictional-0']
        assert snap['arms'] == [arm]
        records = json.loads((directory / 'generation_records.json').read_text())
        assert len(records) == 1
        assert json.loads((directory / 'progress.json').read_text())['state'] == 'complete'
        # These files pass the unmodified ww.score validation, including record hashes.
        assert (directory / 'evaluation.json').exists()


def test_successful_cache_is_reused_without_another_model_call(run):
    run.publish('fictional-0', ww.JOINT)
    execute_inline()
    first = run.report()
    execute_inline()
    assert len(run.calls) == 1
    assert run.report()['arms'] == first['arms']
    assert run.report()['rows'] == first['rows']


def test_failed_full_score_verdict_stays_unknown_and_is_not_automatically_retried(run):
    run.publish('fictional-0', ww.JOINT)
    run.behavior['mode'] = 'fail'
    execute_inline()
    assert len(run.calls) == 1
    report = run.report()
    group = report['arms'][ww.JOINT]
    assert group == {'valid_answers': 1, 'judged': 0, 'correct': 0, 'unknown': 1, 'accuracy': None}
    assert report['rows'][0]['correct'] is None
    evaluation = json.loads((run.cache_task('fictional-0', ww.JOINT) / 'evaluation.json').read_text())
    assert evaluation['rows'][0]['judge_status'] == 'failed'
    # A now healthy service does not imply permission to repeat the paid attempt.
    run.behavior['mode'] = 'normal'
    execute_inline()
    assert len(run.calls) == 1
    assert run.report()['arms'][ww.JOINT] == group


def test_attempt_marker_without_evaluation_prevents_repeating_uncertain_paid_call(run):
    run.publish('fictional-0', ww.JOINT)
    directory = run.cache_task('fictional-0', ww.JOINT)
    write_json(directory / 'attempt_started.json', {'question_id': 'fictional-0', 'arm': ww.JOINT})
    execute_inline()
    assert not run.calls
    assert not (directory / 'evaluation.json').exists()
    group = run.report()['arms'][ww.JOINT]
    assert group['valid_answers'] == 1
    assert group['unknown'] == 1
    assert group['accuracy'] is None


def test_later_mate_environment_skip_removes_previously_eligible_answer(run):
    run.publish('fictional-0', ww.JOINT)
    execute_inline()
    assert run.report()['arms'][ww.JOINT]['valid_answers'] == 1
    run.publish('fictional-0', ww.RESIDUAL, 'skipped_environment', None,
                environment_exclusion={'scope': 'root_page', 'url': 'https://fictional.invalid/0',
                                       'reason': 'http_status', 'http_status': 503})
    before = file_bytes(run.source)
    execute_inline()
    assert len(run.calls) == 1
    assert run.report()['rows'] == []
    for arm in ww.ARMS:
        assert run.report()['arms'][arm]['valid_answers'] == 0
        assert run.report()['arms'][arm]['accuracy'] is None
    assert file_bytes(run.source) == before
    # Historical judgement remains in independent cache for auditability.
    assert (run.cache_task('fictional-0', ww.JOINT) / 'evaluation.json').exists()


def test_source_identity_mismatch_is_rejected_before_any_judgement(run):
    run.publish('fictional-0', ww.JOINT)
    run.manifest['generation_source_hashes'] = {'dagbt/frozen_core.py': 'wrong-deployment'}
    write_json(run.source / 'manifest.json', run.manifest)
    before = file_bytes(run.source)
    with pytest.raises(SystemExit, match='源码或数据'):
        execute_inline()
    assert not run.calls
    assert file_bytes(run.source) == before
    assert not (run.base / 'report.json').exists()


def test_final_generation_hash_mismatch_is_rejected_before_any_judgement(run):
    run.publish('fictional-0', ww.JOINT)
    relative = str((ww.task_path(run.source, 'fictional-0', ww.JOINT) / 'result.json').relative_to(run.source))
    write_json(run.source / 'generation_records.json', {relative: 'incorrect-hash'})
    with pytest.raises(SystemExit, match='哈希不一致'):
        execute_inline()
    assert not run.calls
    assert not (run.base / 'report.json').exists()
