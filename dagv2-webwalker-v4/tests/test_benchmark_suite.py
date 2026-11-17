from argparse import Namespace
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

import pytest

from dagbt import benchmark_suite as suite
from dagbt.transport import save


def args(tmp_path):
    for name in suite.DATASETS:
        save(tmp_path / name / 'manifest.json', {'dataset': name})
    save(tmp_path / 'config.json', {'fixture': True})
    return Namespace(command='run', output=str(tmp_path / 'output'),
                     webwalker_config=str(tmp_path / 'config.json'),
                     webwalker_judge_config=str(tmp_path / 'config.json'),
                     browsecomp_config=str(tmp_path / 'config.json'),
                     browsecomp_judge_config=str(tmp_path / 'config.json'),
                     webwalker_data=str(tmp_path / 'webwalkerqa'),
                     browsecomp_data=str(tmp_path / 'browsecomp_plus'),
                     after_personamem=None, limit=2, offline=False)


def test_suite_finishes_both_generations_before_either_score_and_resumes_through_runners(tmp_path, monkeypatch):
    a = args(tmp_path)
    seen = []
    def run_stage(options, dataset, stage):
        if stage == 'score':
            assert all(json.loads((Path(a.output) / name / 'progress.json').read_text())['state'] == 'complete'
                       for name in suite.DATASETS)
        seen.append((dataset, stage))
        if stage == 'run':
            save(Path(a.output) / dataset / 'progress.json', {'state': 'complete'})
        return 0
    monkeypatch.setattr(suite, 'run_stage', run_stage)
    assert suite.run(a) == 0
    expected = [('webwalkerqa', 'run'), ('browsecomp_plus', 'run'),
                ('webwalkerqa', 'score'), ('browsecomp_plus', 'score')]
    assert seen == expected
    assert suite.status(a.output)['progress']['state'] == 'complete'
    assert suite.run(a) == 0
    assert seen == expected * 2  # runner, rather than the suite, verifies terminal task identity
    save(tmp_path / 'config.json', {'fixture': 'changed'})
    with pytest.raises(ValueError, match='manifest differs'):
        suite.run(a)


def test_stopping_a_generation_never_starts_scoring_or_the_next_dataset(tmp_path, monkeypatch):
    a = args(tmp_path)
    seen = []
    def interrupted(options, dataset, stage):
        seen.append((dataset, stage))
        raise KeyboardInterrupt('fixture stop')
    monkeypatch.setattr(suite, 'run_stage', interrupted)
    with pytest.raises(KeyboardInterrupt):
        suite.run(a)
    assert seen == [('webwalkerqa', 'run')]
    state = suite.status(a.output)
    assert state['progress']['state'] == 'stopped'
    assert not state['live_writer']


def test_score_command_refuses_references_until_both_generations_complete(tmp_path, monkeypatch):
    a = args(tmp_path)
    a.command = 'score'
    save(Path(a.output) / 'webwalkerqa' / 'progress.json', {'state': 'complete'})
    save(Path(a.output) / 'browsecomp_plus' / 'progress.json', {'state': 'running'})
    monkeypatch.setattr(suite, 'run_stage', lambda *a: pytest.fail('Scorer started before both generations finished'))
    with pytest.raises(RuntimeError, match='Both dataset generations'):
        suite.run(a)


def test_interrupted_child_gets_graceful_process_group_cleanup(tmp_path, monkeypatch):
    a = args(tmp_path)
    class Child:
        pid = 123456
        stopped = False
        def poll(self):
            return 0 if self.stopped else None
        def wait(self, timeout=None):
            if self.stopped:
                return 0
            raise KeyboardInterrupt('fixture stop')
    child = Child()
    calls = []
    def kill(pid, number):
        calls.append((pid, number))
        child.stopped = True
    monkeypatch.setattr(suite.subprocess, 'Popen', lambda *a, **k: child)
    monkeypatch.setattr(suite.os, 'killpg', kill)
    with pytest.raises(KeyboardInterrupt):
        suite.run_stage(a, 'webwalkerqa', 'run')
    assert calls == [(child.pid, signal.SIGTERM)]


@pytest.mark.parametrize('early_exit', [False, True])
def test_launch_never_reports_success_without_ready_and_reaps_its_timed_out_child(tmp_path, monkeypatch, early_exit):
    a = args(tmp_path)
    class Child:
        pid = 123456
        stopped = False
        def poll(self):
            return 1 if early_exit else 0 if self.stopped else None
        def wait(self, timeout=None):
            assert self.stopped
            return 0
    child = Child()
    calls = []
    def kill(pid, number):
        calls.append((pid, number))
        child.stopped = True
    ticks = iter((0, 16))
    monkeypatch.setattr(suite.subprocess, 'Popen', lambda *a, **k: child)
    monkeypatch.setattr(suite.os, 'killpg', kill)
    monkeypatch.setattr(suite.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(RuntimeError, match='failed to launch' if early_exit else 'validated readiness'):
        suite.launch(a)
    assert calls == ([] if early_exit else [(child.pid, signal.SIGTERM)])
    assert not suite.lock_is_held(Path(a.output) / '.launch')


def process_fixture(tmp_path):
    """Tiny local runners exercise the real coordinator without models or labels."""
    package = tmp_path / 'dagbt'
    package.mkdir()
    (package / '__init__.py').write_text('')
    shutil.copy2(Path(suite.__file__), package / 'benchmark_suite.py')
    (package / 'runner.py').write_text('''import fcntl
from pathlib import Path
def lock_is_held(output):
    path=Path(output)/'writer.lock'
    if not path.exists(): return False
    with path.open('a+') as stream:
        try: fcntl.flock(stream, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return True
    return False
''')
    (package / 'transport.py').write_text('''import json
from pathlib import Path
def save(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value)); temporary.replace(path)
''')
    (package / 'webwalker_runner.py').write_text(r'''from contextlib import contextmanager
import argparse, os, signal, subprocess, sys, time
from pathlib import Path
from .transport import save
@contextmanager
def registering_worker():
    handlers={number:signal.getsignal(number) for number in (signal.SIGINT,signal.SIGTERM)
              if callable(signal.getsignal(number))}; pending={}
    try:
        for number in handlers:
            signal.signal(number,lambda number,frame:pending.setdefault(number,frame))
        yield
    finally:
        for number,handler in handlers.items(): signal.signal(number,handler)
        for number,frame in pending.items(): handlers[number](number,frame)
def fixture_main(dataset):
    parser=argparse.ArgumentParser(); parser.add_argument('stage'); parser.add_argument('--output')
    args,_=parser.parse_known_args()
    directory=Path(args.output); directory.mkdir(parents=True,exist_ok=True)
    root=directory.parent
    with (root/'fixture_stages.log').open('a') as stream: stream.write(dataset+'/'+args.stage+'\n')
    if args.stage=='run':
        if dataset=='webwalkerqa' and not (root/'fixture_resume').exists():
            worker=None
            def interrupted(*unused): raise KeyboardInterrupt()
            signal.signal(signal.SIGTERM,interrupted)
            try:
                with registering_worker():
                    worker=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
                    (directory/'fixture_worker.pid').write_text(str(worker.pid))
                while True: time.sleep(.05)
            except KeyboardInterrupt: return 130
            finally:
                if worker is not None:
                    worker.terminate(); worker.wait(timeout=5)
                    (directory/'fixture_worker_reaped').write_text('yes')
        save(directory/'progress.json',{'state':'complete'})
    elif args.stage=='score':
        import json
        assert all(json.loads((root/name/'progress.json').read_text())['state']=='complete'
                   for name in ('webwalkerqa','browsecomp_plus'))
        (directory/'fixture_scored').write_text('yes')
    return 0
if __name__=='__main__': raise SystemExit(fixture_main('webwalkerqa'))
''')
    (package / 'browsecomp_runner.py').write_text(
        "from .webwalker_runner import fixture_main\nraise SystemExit(fixture_main('browsecomp_plus'))\n")
    a = args(tmp_path)
    flags = []
    for name in ('output', 'webwalker_config', 'webwalker_judge_config', 'browsecomp_config',
                 'browsecomp_judge_config', 'webwalker_data', 'browsecomp_data'):
        flags += ['--' + name.replace('_', '-'), getattr(a, name)]
    return a, [sys.executable, '-m', 'dagbt.benchmark_suite'], flags


def wait_stopped(output):
    deadline = time.monotonic() + 5
    while suite.lock_is_held(output) and time.monotonic() < deadline:
        time.sleep(.02)
    assert not suite.lock_is_held(output)


def test_real_background_stop_reaps_second_level_worker_and_never_starts_next_dataset(tmp_path):
    a, executable, flags = process_fixture(tmp_path)
    worker_pid = None
    suite_pid = None
    try:
        result = subprocess.run(executable + ['launch', *flags], cwd=tmp_path,
                                capture_output=True, text=True, timeout=10, check=True)
        suite_pid = json.loads(result.stdout)['pid']
        marker = Path(a.output) / 'webwalkerqa/fixture_worker.pid'
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert marker.is_file()
        worker_pid = int(marker.read_text())
        subprocess.run(executable + ['stop', '--output', a.output], cwd=tmp_path,
                       capture_output=True, text=True, timeout=5, check=True)
        wait_stopped(a.output)
        assert (marker.parent / 'fixture_worker_reaped').is_file()
        with pytest.raises(ProcessLookupError):
            os.kill(worker_pid, 0)
        state = json.loads((Path(a.output) / 'progress.json').read_text())
        assert state['state'] == 'stopped' and state['current'] == 'webwalkerqa/run'
        assert not (Path(a.output) / 'browsecomp_plus').exists()
    finally:
        for pid in (worker_pid, suite_pid):
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass


def test_launch_immediate_stop_then_resume_completes_both_datasets_and_scores(tmp_path):
    a, executable, flags = process_fixture(tmp_path)
    suite_pid = None
    try:
        started = subprocess.run(executable + ['launch', *flags], cwd=tmp_path,
                                 capture_output=True, text=True, timeout=10, check=True)
        suite_pid = json.loads(started.stdout)['pid']
        ready = json.loads((Path(a.output) / 'ready.json').read_text())
        assert ready['pid'] == suite_pid and ready['output'] == str(Path(a.output).resolve())
        # No worker marker wait: launch itself must establish stop-ready PID ownership.
        stopped = subprocess.run(executable + ['stop', '--output', a.output], cwd=tmp_path,
                                 capture_output=True, text=True, timeout=5, check=True)
        assert json.loads(stopped.stdout)['stopped'] is True
        wait_stopped(a.output)
        assert json.loads((Path(a.output) / 'progress.json').read_text())['state'] == 'stopped'
        marker = Path(a.output) / 'webwalkerqa/fixture_worker.pid'
        if marker.is_file():
            assert (marker.parent / 'fixture_worker_reaped').is_file()
            with pytest.raises(ProcessLookupError):
                os.kill(int(marker.read_text()), 0)
        (Path(a.output) / 'fixture_resume').write_text('resume the same output')
        resumed = subprocess.run(executable + ['launch', *flags], cwd=tmp_path,
                                 capture_output=True, text=True, timeout=10, check=True)
        suite_pid = json.loads(resumed.stdout)['pid']
        deadline = time.monotonic() + 5
        while suite.lock_is_held(a.output) and time.monotonic() < deadline:
            time.sleep(.02)
        report = subprocess.run(executable + ['status', '--output', a.output], cwd=tmp_path,
                                capture_output=True, text=True, timeout=5, check=True)
        state = json.loads(report.stdout)
        assert state['progress']['state'] == 'complete' and not state['live_writer']
        events = (Path(a.output) / 'fixture_stages.log').read_text().splitlines()
        assert events[-4:] == ['webwalkerqa/run', 'browsecomp_plus/run',
                               'webwalkerqa/score', 'browsecomp_plus/score']
        assert all((Path(a.output) / name / 'fixture_scored').is_file() for name in suite.DATASETS)
        # Changed configuration must be rejected by the foreground launcher,
        # rather than reported as a successful background start.
        save(tmp_path / 'config.json', {'fixture': 'incompatible'})
        rejected = subprocess.run(executable + ['launch', *flags], cwd=tmp_path,
                                  capture_output=True, text=True, timeout=5)
        assert rejected.returncode != 0 and 'Suite manifest differs' in rejected.stderr
        assert not suite.lock_is_held(a.output)
        assert (Path(a.output) / 'fixture_stages.log').read_text().splitlines() == events
    finally:
        if suite_pid:
            try:
                os.kill(suite_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
