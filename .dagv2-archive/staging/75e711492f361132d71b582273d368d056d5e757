"""The fixed-corpus runner keeps labels, retries, and process ownership bounded."""
from argparse import Namespace
import json
from pathlib import Path
import subprocess

import pytest

from dagbt import browsecomp_runner as runner
from dagbt.methods import JOINT, RESIDUAL_V2
from dagbt.transport import save


def arguments(tmp_path):
    return Namespace(config=str(runner.ROOT / 'configs/browsecomp-plus-v4.json'),
                     data=str(tmp_path / 'data'), output=str(tmp_path / 'output'),
                     arms=[JOINT, RESIDUAL_V2], limit=2, after_personamem=None)


def fake_generation(monkeypatch, tmp_path):
    questions = [{'id': 'fixture-' + str(index), 'question': 'Which invented signal is enabled?'}
                 for index in range(2)]
    identity = {'path': str(tmp_path / 'data/corpus.sqlite3'), 'sha256': 'fixture-corpus',
                'size': 0, 'mtime_ns': 0}
    monkeypatch.setattr(runner, 'load_questions', lambda path: (questions, {
        'questions_sha256': 'fixture-questions', 'corpus_sha256': 'fixture-corpus'}))
    monkeypatch.setattr(runner, 'verify_corpus', lambda path: identity)
    calls = []

    def one(output, question, arm, config, timeout, **kwargs):
        assert set(question) == {'id', 'question'}
        assert kwargs['corpus_identity'] == identity
        calls.append((question['id'], arm))
        row = {'unit_id': question['id'], 'method': arm,
               'answer': {'status': 'budget_exhausted', 'prediction': None},
               'diagnostics': {'ledger': {'used': {'llm': 23}}, 'corpus_search': {'actions': 2}}}
        save(runner.task_path(output, question['id'], arm) / 'result.json', row)
        return row

    monkeypatch.setattr(runner, 'run_one', one)
    return calls


def test_generation_never_opens_labels_and_freezes_both_arms_and_corpus(monkeypatch, tmp_path):
    calls = fake_generation(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, 'load_references', lambda path: pytest.fail('Generation read reference labels'))
    args = arguments(tmp_path)
    result = runner.run(args)
    assert result['progress']['state'] == 'complete'
    assert result['progress']['completed'] == result['progress']['total'] == 4
    assert result['progress']['failed_tasks'] == 4
    assert calls == [('fixture-0', JOINT), ('fixture-0', RESIDUAL_V2),
                     ('fixture-1', RESIDUAL_V2), ('fixture-1', JOINT)]
    summary = json.loads((Path(args.output) / 'generation_summary.json').read_text())
    assert all(row['corpus_search_calls_completed_traces'] == 4 for row in summary.values())
    assert all(row['backend'] == 'sqlite_fts5_bm25' for row in summary.values())
    monkeypatch.setattr(runner, 'generation_sources', lambda: {'changed.py': 'changed'})
    with pytest.raises(ValueError, match='manifest differs'):
        runner.run(args)


def test_reference_loader_waits_for_terminal_generation_and_result_integrity(monkeypatch, tmp_path):
    args = arguments(tmp_path)
    save(Path(args.output) / 'progress.json', {'state': 'running'})
    monkeypatch.setattr(runner, 'load_references', lambda path: pytest.fail('Labels opened before integrity gate'))
    with pytest.raises(RuntimeError, match='terminal'):
        runner.score(args)
    fake_generation(monkeypatch, tmp_path)
    runner.run(args)
    result = runner.task_path(args.output, 'fixture-0', JOINT) / 'result.json'
    row = json.loads(result.read_text())
    row['answer']['prediction'] = 'tampered'
    save(result, row)
    with pytest.raises(ValueError, match='changed or is missing'):
        runner.score(args)


def test_unanswered_tasks_remain_in_score_denominator_without_judge_calls(monkeypatch, tmp_path):
    fake_generation(monkeypatch, tmp_path)
    args = arguments(tmp_path)
    runner.run(args)
    monkeypatch.setattr(runner, 'load_references', lambda path: {
        'fixture-0': {'answer': 'toy answer'}, 'fixture-1': {'answer': 'toy answer'}})
    monkeypatch.setattr(runner, 'Transport', lambda *a, **k: pytest.fail('Unanswered task used judge'))
    report = runner.score(args)
    assert all(row['questions'] == 2 and row['accuracy'] == 0 for row in report['arms'].values())


def test_question_timeout_reaps_owned_worker_and_never_retries_terminal_task(monkeypatch, tmp_path):
    question = {'id': 'fixture-0', 'question': 'Which toy flag is true?'}

    class Child:
        pid = 234567
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

        def wait(self, timeout=None):
            if not self.stopped:
                raise subprocess.TimeoutExpired('fixture worker', timeout)
            return 0

    child = Child()
    monkeypatch.setattr(runner.subprocess, 'Popen', lambda *a, **k: child)

    def terminate(pid, signum):
        assert pid == child.pid
        child.stopped = True

    monkeypatch.setattr(runner.os, 'killpg', terminate)
    kwargs = {'data_dir': str(tmp_path / 'data'), 'corpus_identity': {}}
    row = runner.run_one(tmp_path, question, JOINT, {}, 0.01, **kwargs)
    assert row['failure']['error_type'] == 'QuestionTimeout' and child.stopped
    monkeypatch.setattr(runner.subprocess, 'Popen', lambda *a, **k: pytest.fail('Terminal attempt retried'))
    assert runner.run_one(tmp_path, question, JOINT, {}, 1, **kwargs) == row


def test_stale_pid_is_not_signalled_and_config_cannot_expand_retrieval_budget(monkeypatch, tmp_path):
    save(tmp_path / 'pid.json', {'pid': 12345})
    monkeypatch.setattr(runner.os, 'kill', lambda *a: pytest.fail('Stale PID signalled'))
    assert not runner.stop(tmp_path)['stopped']
    config = json.loads((runner.ROOT / 'configs/browsecomp-plus-v4.json').read_text())
    config['browsecomp_plus']['max_actions'] = 37
    path = tmp_path / 'bad.json'
    save(path, config)
    with pytest.raises(ValueError, match='max_actions'):
        runner.effective_config(path)
