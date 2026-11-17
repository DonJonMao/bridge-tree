"""Synthetic, network-free checks for the separately delivered interim scorer.

These fixtures use invented questions and answers. No benchmark result or model
service is consulted, and no generation code is changed.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

STAGE = Path(__file__).resolve().parent
V2_ROOT = STAGE / 'installed_webwalker_only_v2'
sys.path.insert(0, str(V2_ROOT))
SCRIPT = Path('/Users/mao/projects/dagv2-webwalker-v4/webwalker_interim_score.py')
spec = importlib.util.spec_from_file_location('webwalker_interim_score_under_test', SCRIPT)
interim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = interim
spec.loader.exec_module(interim)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def native_result(qid, arm, status='ok', prediction='fictional answer'):
    return {'unit_id': qid, 'method': arm, 'dataset': 'webwalkerqa',
            'answer': {'status': status, 'prediction': prediction},
            'seconds': 0.25, 'diagnostics': {}}


@pytest.fixture
def fixture_run(tmp_path, monkeypatch):
    """Create a live partial run with the real v2 publication layout."""
    sources = {'dagbt/example.py': 'synthetic-source-identity'}
    monkeypatch.setattr(interim.ww, 'generation_sources', lambda: sources)
    arms = list(interim.ww.ARMS)
    questions = [
        {'id': f'fake-{i}', 'question': f'Invented question {i}?',
         'root_url': f'https://fictional.invalid/q{i}'}
        for i in range(4)
    ]
    data = {'questions_sha256': 'synthetic-data-identity', 'questions': 4}
    manifest = {
        'protocol': interim.ww.VERSION, 'access_policy': interim.ww.ACCESS_POLICY,
        'core_release': interim.ww.CORE_RELEASE,
        'generation_source_hashes': sources, 'data': data,
        'config_identity': interim.ww.digest({'llm_model': 'synthetic-judge'}),
        'arms': arms, 'question_ids': [q['id'] for q in questions], 'tasks': 8,
    }
    output = tmp_path / 'running-generation'
    write_json(output / 'manifest.json', manifest)
    write_json(output / 'progress.json', {'state': 'running', 'completed': 0, 'total': 8})

    def publish(qid, arm, status='ok', prediction='fictional answer', **extra):
        row = {**native_result(qid, arm, status, prediction), **extra}
        write_json(output / 'tasks' / qid / arm / 'result.json', row)
        return row

    return {'output': output, 'questions': questions, 'data': data,
            'manifest': manifest, 'arms': arms, 'publish': publish,
            'report': tmp_path / 'interim-report',
            'references': {q['id']: {'answer': 'fictional reference'} for q in questions},
            'text': {q['id']: q['question'] for q in questions},
            'config': {'llm_model': 'synthetic-judge'}}


def collect(run):
    return interim.collect_snapshot(run['output'], run['questions'], run['data'])


def evaluate(run, snapshot, judge, **kwargs):
    return interim.evaluate_snapshot(snapshot, run['references'], run['text'],
                                     run['config'], run['report'], judge_fn=judge, **kwargs)


def by_task(rows):
    return {(r['question_id'], r['arm']): r for r in rows}


def generation_bytes(output):
    return {str(p.relative_to(output)): p.read_bytes()
            for p in output.rglob('*') if p.is_file()}


def test_running_snapshot_reads_only_published_results_and_does_not_mutate_generation(fixture_run):
    run = fixture_run
    run['publish']('fake-0', run['arms'][0])
    # The next worker has not atomically published result.json yet.
    incomplete = run['output'] / 'tasks' / 'fake-0' / run['arms'][1] / 'result.json.tmp'
    incomplete.parent.mkdir(parents=True)
    incomplete.write_text('{"unfinished":')
    before = generation_bytes(run['output'])
    snap = collect(run)
    assert snap['progress']['state'] == 'running'
    assert len(snap['results']) == 1
    assert snap['missing_tasks'] == 7
    assert len(snap['result_hashes']) == 1
    relative, digest = next(iter(snap['result_hashes'].items()))
    assert digest == hashlib.sha256((run['output'] / relative).read_bytes()).hexdigest()
    assert generation_bytes(run['output']) == before


def test_snapshot_rejects_wrong_source_identity(fixture_run):
    run = fixture_run
    run['manifest']['generation_source_hashes'] = {'dagbt/example.py': 'changed'}
    write_json(run['output'] / 'manifest.json', run['manifest'])
    with pytest.raises((ValueError, RuntimeError), match='[Ss]ource|identity'):
        collect(run)


def test_snapshot_rejects_task_identity_mismatch(fixture_run):
    run = fixture_run
    run['publish']('fake-0', run['arms'][0], unit_id='another-question')
    with pytest.raises((ValueError, RuntimeError)):
        collect(run)


def test_only_ok_nonempty_predictions_are_sent_to_judge(fixture_run):
    run = fixture_run
    arm = run['arms'][0]
    run['publish']('fake-0', arm)
    run['publish']('fake-1', arm, 'budget_exhausted', None)
    run['publish']('fake-2', arm, 'ok', '   ')
    seen = []

    def judge(qid, directory, config, judge_input):
        seen.append((qid, judge_input))
        return {'correct': True, 'reason': 'synthetic equivalent'}

    before = generation_bytes(run['output'])
    snap = collect(run)
    rows = evaluate(run, snap, judge)
    assert [qid for qid, _ in seen] == ['fake-0']
    assert seen[0][1] == {'question': run['text']['fake-0'],
                          'reference': 'fictional reference',
                          'prediction': 'fictional answer'}
    tasks = by_task(rows)
    assert tasks['fake-0', arm]['judge_status'] == 'ok'
    assert tasks['fake-1', arm]['judge_status'] == 'not_answered'
    assert tasks['fake-2', arm]['judge_status'] == 'not_answered'
    summary = interim.summarize(snap, rows)[arm]
    assert summary['valid_answers'] == 1
    assert summary['accuracy_on_valid_answers'] == 1.0
    assert generation_bytes(run['output']) == before


def test_successful_verdict_is_cached_without_repeated_model_calls(fixture_run):
    run = fixture_run
    run['publish']('fake-0', run['arms'][0])
    calls = []

    def judge(qid, directory, config, judge_input):
        calls.append(directory)
        return {'correct': False, 'reason': 'fictional mismatch'}

    snap = collect(run)
    first = evaluate(run, snap, judge)
    second = evaluate(run, snap, judge)
    assert len(calls) == 1
    assert first[0]['input_identity'] == second[0]['input_identity']
    assert second[0]['correct'] is False
    assert second[0]['judge_status'] == 'ok'


def test_failed_judge_is_unknown_and_retried_only_when_explicit(fixture_run):
    run = fixture_run
    arm = run['arms'][0]
    run['publish']('fake-0', arm)
    calls = []

    def judge(qid, directory, config, judge_input):
        calls.append(directory)
        if len(calls) == 1:
            raise RuntimeError('synthetic judge outage')
        return {'correct': True, 'reason': 'synthetic recovery'}

    snap = collect(run)
    first = evaluate(run, snap, judge)
    second = evaluate(run, snap, judge)
    assert len(calls) == 1
    assert first[0]['correct'] is None
    assert second[0]['judge_status'] == 'failed'
    failed = interim.summarize(snap, second)[arm]
    assert failed['valid_answers'] == 1
    assert failed['judged_answers'] == 0
    assert failed['incorrect'] == 0
    assert failed['judge_failed'] == 1
    assert failed['accuracy_on_valid_answers'] is None
    assert failed['accuracy_lower_bound'] == 0.0
    assert failed['accuracy_upper_bound'] == 1.0
    recovered = evaluate(run, snap, judge, retry_failed=True)
    assert len(calls) == 2
    assert calls[0] != calls[1]  # Retry uses a fresh transport attempt directory.
    assert recovered[0]['correct'] is True


def test_answer_reference_and_judge_config_changes_invalidate_cached_verdict(fixture_run):
    run = fixture_run
    arm = run['arms'][0]
    run['publish']('fake-0', arm)
    calls = []

    def judge(qid, directory, config, judge_input):
        calls.append(copy.deepcopy(judge_input))
        return {'correct': True, 'reason': 'synthetic'}

    first = evaluate(run, collect(run), judge)
    run['publish']('fake-0', arm, prediction='changed fictional answer')
    second = evaluate(run, collect(run), judge)
    assert first[0]['input_identity'] != second[0]['input_identity']
    run['references']['fake-0']['answer'] = 'changed fictional reference'
    third = evaluate(run, collect(run), judge)
    assert second[0]['input_identity'] != third[0]['input_identity']
    run['config']['llm_model'] = 'different-synthetic-judge'
    fourth = evaluate(run, collect(run), judge)
    assert third[0]['input_identity'] != fourth[0]['input_identity']
    assert len(calls) == 4


def test_root_unavailable_excludes_both_arms_even_if_other_arm_has_answer(fixture_run):
    run = fixture_run
    run['publish']('fake-0', run['arms'][0], 'skipped_environment', None,
                   environment_exclusion={'scope': 'root_page',
                                          'url': 'https://fictional.invalid/q0',
                                          'reason': 'http_status', 'http_status': 503})
    run['publish']('fake-0', run['arms'][1])

    def no_judge(*args):
        pytest.fail('Environment excluded question must not incur judge calls')

    snap = collect(run)
    assert 'fake-0' in snap['environment_exclusions']
    rows = evaluate(run, snap, no_judge)
    assert len(rows) == 2
    assert {r['judge_status'] for r in rows} == {'excluded_environment'}
    for summary in interim.summarize(snap, rows).values():
        assert summary['valid_answers'] == 0
        assert summary['environment_excluded_tasks'] == 1
        assert summary['accuracy_on_valid_answers'] is None


def test_unknown_judgements_produce_bounds_without_counting_them_as_incorrect(fixture_run):
    run = fixture_run
    arm = run['arms'][0]
    run['publish']('fake-0', arm)
    run['publish']('fake-1', arm)

    def judge(qid, directory, config, judge_input):
        if qid == 'fake-1':
            raise RuntimeError('synthetic temporary failure')
        return {'correct': True, 'reason': 'synthetic'}

    snap = collect(run)
    rows = evaluate(run, snap, judge)
    summary = interim.summarize(snap, rows)[arm]
    assert summary['valid_answers'] == 2
    assert summary['judged_answers'] == 1
    assert summary['correct'] == 1
    assert summary['incorrect'] == 0
    assert summary['accuracy_on_judged_answers'] == 1.0
    assert summary['accuracy_on_valid_answers'] is None
    assert summary['accuracy_lower_bound'] == 0.5
    assert summary['accuracy_upper_bound'] == 1.0


def test_report_only_and_max_new_preserve_pending_unknowns(fixture_run):
    run = fixture_run
    arm = run['arms'][0]
    run['publish']('fake-0', arm)
    run['publish']('fake-1', arm)
    calls = []

    def judge(qid, directory, config, judge_input):
        calls.append(qid)
        return {'correct': True, 'reason': 'synthetic'}

    snap = collect(run)
    untouched = evaluate(run, snap, judge, report_only=True)
    assert not calls
    assert {r['judge_status'] for r in untouched} == {'pending'}
    partial = evaluate(run, snap, judge, max_new=1)
    assert len(calls) == 1
    assert sorted(r['judge_status'] for r in partial) == ['ok', 'pending']
    summary = interim.summarize(snap, partial)[arm]
    assert summary['judge_pending'] == 1
    assert summary['accuracy_on_valid_answers'] is None
    assert summary['accuracy_lower_bound'] == 0.5
    assert summary['accuracy_upper_bound'] == 1.0
    replay = evaluate(run, snap, judge, report_only=True)
    assert len(calls) == 1
    assert sorted(r['judge_status'] for r in replay) == ['ok', 'pending']


def test_malformed_judge_boolean_is_not_accepted_as_answer_verdict(fixture_run):
    run = fixture_run
    run['publish']('fake-0', run['arms'][0])

    def judge(*args):
        return {'correct': 'true', 'reason': 'synthetic invalid response'}

    rows = evaluate(run, collect(run), judge)
    assert rows[0]['judge_status'] == 'failed'
    assert rows[0]['correct'] is None


def test_root_level_delivery_does_not_change_v2_generation_source_identity(tmp_path, monkeypatch):
    # Use the real v2 scanner, with a small synthetic deployment tree.
    monkeypatch.setattr(interim.ww, 'ROOT', tmp_path)
    for prefix in ('dagbt', 'dagv2', 'dagresolve', 'package', 'vendor'):
        path = tmp_path / prefix / 'core.py'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# frozen synthetic core\n')
    for name in ('run_webwalker.sh', 'webwalker_offline_smoke.py', 'install_webwalker_browser.py'):
        path = tmp_path / 'scripts' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# frozen synthetic command\n')
    before = interim.ww.generation_sources()
    (tmp_path / 'webwalker_interim_score.py').write_bytes(SCRIPT.read_bytes())
    assert interim.ww.generation_sources() == before
    # Ensure the comparison could detect an actual addition to protected code.
    (tmp_path / 'dagbt' / 'new.py').write_text('# protected file\n')
    assert interim.ww.generation_sources() != before


def test_collect_snapshot_is_allowed_while_generation_writer_lock_is_held(fixture_run):
    import fcntl

    run = fixture_run
    run['publish']('fake-0', run['arms'][0])
    with (run['output'] / 'writer.lock').open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert len(collect(run)['results']) == 1


def test_interrupted_paid_attempt_is_not_implicitly_repeated(fixture_run):
    run = fixture_run
    arm = run['arms'][0]
    run['publish']('fake-0', arm)
    calls = []

    def interrupted(qid, directory, config, judge_input):
        calls.append(directory)
        raise KeyboardInterrupt('synthetic interruption')

    snap = collect(run)
    with pytest.raises(KeyboardInterrupt):
        evaluate(run, snap, interrupted)
    rows = evaluate(run, snap, interrupted)
    assert len(calls) == 1
    assert rows[0]['judge_status'] == 'interrupted'
    assert rows[0]['correct'] is None
    summary = interim.summarize(snap, rows)[arm]
    assert summary['judge_interrupted'] == 1
    assert summary['incorrect'] == 0
    assert summary['accuracy_on_valid_answers'] is None


def configure_fake_main(run, monkeypatch, judge):
    monkeypatch.setattr(interim.ww, 'effective_config', lambda path: run['config'])
    monkeypatch.setattr(interim.ww, 'load_questions', lambda path: (run['questions'], run['data']))
    monkeypatch.setattr(interim.ww, 'load_references', lambda path: run['references'])
    monkeypatch.setattr(interim.ww, 'configure_model_network', lambda config: None)
    monkeypatch.setattr(interim, 'judge_answer', judge)
    return ['--output', str(run['output']), '--report-dir', str(run['report']),
            '--config', 'synthetic-config.json',
            '--data', str(run['output'].parent / 'synthetic-data')]


def test_main_report_only_calls_no_model_and_writes_outside_generation(fixture_run, monkeypatch):
    run = fixture_run
    run['publish']('fake-0', run['arms'][0])
    run['publish']('fake-0', run['arms'][1])

    def forbidden(*args):
        pytest.fail('main --report-only must not call a model')

    argv = configure_fake_main(run, monkeypatch, forbidden)
    before = generation_bytes(run['output'])
    assert interim.main([*argv, '--report-only']) == 0
    report = json.loads((run['report'] / 'report.json').read_text())
    assert report['source_output'] == str(run['output'].resolve())
    assert len(report['rows']) == 2
    assert {r['judge_status'] for r in report['rows']} == {'pending'}
    assert generation_bytes(run['output']) == before
    assert not (run['output'] / 'evaluation.json').exists()


def test_main_judge_failure_returns_two_and_keeps_unknown_in_saved_report(fixture_run, monkeypatch):
    run = fixture_run
    arm = run['arms'][0]
    run['publish']('fake-0', arm)

    def unavailable(*args):
        raise RuntimeError('synthetic judge unavailable')

    argv = configure_fake_main(run, monkeypatch, unavailable)
    assert interim.main(argv) == 2
    report = json.loads((run['report'] / 'report.json').read_text())
    assert report['rows'][0]['correct'] is None
    assert report['rows'][0]['judge_status'] == 'failed'
    assert report['arms'][arm]['valid_answers'] == 1
    assert report['arms'][arm]['incorrect'] == 0
    assert report['arms'][arm]['accuracy_on_valid_answers'] is None
    assert report['arms'][arm]['accuracy_lower_bound'] == 0.0
    assert report['arms'][arm]['accuracy_upper_bound'] == 1.0


def test_main_checkpoints_keep_full_snapshot_denominator_before_later_judges_finish(fixture_run, monkeypatch):
    run = fixture_run
    arm = run['arms'][0]
    run['publish']('fake-0', arm)
    run['publish']('fake-1', arm)
    run['publish']('fake-2', arm)
    saved_reports = []
    original_save = interim.save

    def observe_save(path, value):
        if Path(path) == run['report'] / 'report.json':
            saved_reports.append(copy.deepcopy(value))
        return original_save(path, value)

    def judge(qid, directory, config, judge_input):
        return {'correct': qid != 'fake-2', 'reason': 'synthetic verdict'}

    argv = configure_fake_main(run, monkeypatch, judge)
    monkeypatch.setattr(interim, 'save', observe_save)
    assert interim.main(argv) == 0
    # Initial report, a checkpoint after each of three results, final report.
    assert len(saved_reports) == 5
    assert all(len(report['rows']) == 3 for report in saved_reports)
    assert all(report['arms'][arm]['valid_answers'] == 3 for report in saved_reports)
    after_first = saved_reports[1]['arms'][arm]
    assert after_first['judged_answers'] == 1
    assert after_first['judge_pending'] == 2
    assert after_first['accuracy_on_valid_answers'] is None
    assert after_first['accuracy_lower_bound'] == pytest.approx(1 / 3)
    assert after_first['accuracy_upper_bound'] == 1.0
    final = saved_reports[-1]['arms'][arm]
    assert final['judged_answers'] == 3
    assert final['accuracy_on_valid_answers'] == pytest.approx(2 / 3)


def test_report_lock_rejects_second_owner_and_releases_after_exit(tmp_path):
    directory = tmp_path / 'interim-reports'
    with interim.report_lock(directory):
        with pytest.raises(RuntimeError, match='[Aa]nother|running'):
            with interim.report_lock(directory):
                pytest.fail('Second lock owner was allowed')
    with interim.report_lock(directory):
        pass


def test_report_directory_protects_generation_data_and_frozen_code(tmp_path, monkeypatch):
    deployment = tmp_path / 'deployment'
    monkeypatch.setattr(interim.ww, 'ROOT', deployment)
    output = deployment / 'outputs' / 'generation'
    data = deployment / 'data' / 'webwalkerqa'
    forbidden = [
        output, output / 'interim', output.parent,
        data, data / 'reports', data.parent,
        *(deployment / prefix / 'interim' for prefix in
          ('dagbt', 'dagv2', 'dagresolve', 'package', 'vendor', 'scripts')),
    ]
    for directory in forbidden:
        with pytest.raises(ValueError):
            interim.validate_report_directory(directory, output, data)
    # A sibling output is the intended safe persistent cache location.
    interim.validate_report_directory(output.with_name('generation_interim_scores'), output, data)
