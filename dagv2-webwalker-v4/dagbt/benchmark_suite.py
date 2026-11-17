"""One bounded background coordinator for the two v4 benchmark experiments.

The dataset runners retain their own immutable manifests, task attempts, cost
journals and scoring locks.  This module only orders them and owns shutdown.
Both generation phases finish before either scoring phase opens references.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from .runner import lock_is_held
from .transport import save

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'dual_benchmark_v4_sequential_v1'
DATASETS = ('webwalkerqa', 'browsecomp_plus')
MODULES = {'webwalkerqa': 'dagbt.webwalker_runner',
           'browsecomp_plus': 'dagbt.browsecomp_runner'}


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read_json(path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).is_file() else default


@contextmanager
def writer(output, *, record=True):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'writer.lock').open('a+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Benchmark suite already has a live writer') from exc
        if record:
            command = subprocess.check_output(
                ['ps', '-p', str(os.getpid()), '-o', 'command='], text=True).strip()
            save(output / 'pid.json', {'pid': os.getpid(), 'started_unix': time.time(),
                                      'output': str(output), 'process_command': command})
        yield


def options(args, dataset):
    if dataset == 'webwalkerqa':
        return args.webwalker_config, args.webwalker_judge_config, args.webwalker_data, '--data'
    return args.browsecomp_config, args.browsecomp_judge_config, args.browsecomp_data, '--data-dir'


def command(args, dataset, stage):
    config, judge, data, data_flag = options(args, dataset)
    value = [sys.executable, '-u', '-m', MODULES[dataset], stage,
             '--config', str(Path(judge if stage == 'score' else config).resolve()),
             data_flag, str(Path(data).resolve()),
             '--output', str((Path(args.output) / dataset).resolve())]
    if stage == 'run' and args.limit is not None:
        value += ['--limit', str(args.limit)]
    if stage in ('run', 'preflight') and args.after_personamem:
        value += ['--after-personamem', str(Path(args.after_personamem).resolve())]
    if stage == 'preflight' and args.offline:
        value.append('--offline')
    return value


def manifest(args):
    configs = {}
    data = {}
    for dataset in DATASETS:
        config, judge, directory, _ = options(args, dataset)
        for item in (config, judge):
            path = Path(item).resolve()
            if not path.is_file():
                raise ValueError('Configuration is missing: ' + str(path))
            configs[str(path)] = file_hash(path)
        directory = Path(directory).resolve()
        if not (directory / 'manifest.json').is_file():
            raise ValueError('Prepared dataset manifest is missing: ' + str(directory))
        data[dataset] = {'directory': str(directory),
                         'manifest_sha256': file_hash(directory / 'manifest.json')}
    sources = {str(p.relative_to(ROOT)): file_hash(p)
               for prefix in ('dagbt', 'dagv2', 'dagresolve', 'package', 'vendor')
               for p in sorted((ROOT / prefix).rglob('*.py'))}
    return {'protocol': VERSION, 'datasets': list(DATASETS), 'limit': args.limit,
            'configuration_sha256': configs, 'data': data,
            'source_sha256': sources,
            'after_personamem': str(Path(args.after_personamem).resolve()) if args.after_personamem else None,
            'schedule': [[name, 'run'] for name in DATASETS] + [[name, 'score'] for name in DATASETS]}


def check_previous_writer(output):
    for directory in (Path(output), *(Path(output) / name for name in DATASETS)):
        if lock_is_held(directory) or lock_is_held(directory / '.scorer'):
            raise RuntimeError('A live suite or dataset writer exists: ' + str(directory))


def terminate(process):
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def run_stage(args, dataset, stage):
    """The runner gets SIGTERM first so it can reap its own worker session."""
    from .webwalker_runner import registering_worker
    process = None
    try:
        with registering_worker():
            process = subprocess.Popen(command(args, dataset, stage), cwd=ROOT,
                                       start_new_session=True)
            save(Path(args.output) / 'current_child.json',
                 {'dataset': dataset, 'stage': stage, 'pid': process.pid,
                  'started_unix': time.time()})
        return process.wait()
    finally:
        terminate(process)


def run(args):
    output = Path(args.output).resolve()
    old = read_json(output / 'manifest.json')
    if args.command == 'score' and args.limit is None and old is not None:
        args.limit = old.get('limit')
    expected = manifest(args)
    with writer(output):
        old = read_json(output / 'manifest.json')
        if old is not None and old != expected:
            raise ValueError('Suite manifest differs; use another output directory')
        for name in DATASETS:
            if lock_is_held(output / name) or lock_is_held(output / name / '.scorer'):
                raise RuntimeError('Dataset already has an independent live writer: ' + name)
        save(output / 'manifest.json', expected)
        stages = read_json(output / 'progress.json', {}).get('stages', {})
        schedule = ([[name, 'score'] for name in DATASETS] if args.command == 'score'
                    else expected['schedule'])
        current = None
        try:
            save(output / 'progress.json', {'state': 'running', 'current': current,
                 'stages': stages, 'updated_unix': time.time()})
            owner = read_json(output / 'pid.json')
            # Only a validated owner publishes startup readiness. A lock alone
            # can be observed before pid.json or manifest checks finish.
            save(output / 'ready.json', {'pid': os.getpid(), 'output': str(output),
                 'writer_started_unix': owner['started_unix'],
                 'manifest_sha256': file_hash(output / 'manifest.json')})
            for dataset, stage in schedule:
                if stage == 'score':
                    for name in DATASETS:
                        state = read_json(output / name / 'progress.json', {}).get('state')
                        if state != 'complete' or lock_is_held(output / name):
                            raise RuntimeError('Both dataset generations must be terminal before scoring')
                current = dataset + '/' + stage
                save(output / 'progress.json', {'state': 'running', 'current': current,
                     'stages': stages, 'updated_unix': time.time()})
                # Re-entering a runner verifies its frozen manifest and reuses
                # terminal tasks; interrupted paid attempts are never replayed.
                code = run_stage(args, dataset, stage)
                stages[current] = {'state': 'complete' if code == 0 else 'failed',
                                   'returncode': code, 'ended_unix': time.time()}
                if code:
                    save(output / 'progress.json', {'state': 'failed', 'current': current,
                         'stages': stages, 'updated_unix': time.time()})
                    return 1
        except BaseException:
            save(output / 'progress.json', {'state': 'stopped', 'current': current,
                 'stages': stages, 'updated_unix': time.time()})
            raise
        finally:
            (output / 'current_child.json').unlink(missing_ok=True)
        save(output / 'progress.json', {'state': 'complete', 'current': None,
             'stages': stages, 'updated_unix': time.time()})
    return 0


def status(output):
    output = Path(output).resolve()
    return {'output': str(output), 'live_writer': lock_is_held(output),
            'progress': read_json(output / 'progress.json', {}),
            'datasets': {name: {'output': str(output / name),
                               'live_writer': lock_is_held(output / name),
                               'live_scorer': lock_is_held(output / name / '.scorer'),
                               'progress': read_json(output / name / 'progress.json', {}),
                               'evaluation_available': (output / name / 'evaluation.json').is_file()}
                         for name in DATASETS}}


def stop(output):
    output = Path(output).resolve()
    if not lock_is_held(output):
        return {'stopped': False, 'reason': 'no_live_suite_writer'}
    record = read_json(output / 'pid.json', {})
    if record.get('output') != str(output) or type(record.get('pid')) is not int:
        raise RuntimeError('Suite PID output identity differs; refusing to signal')
    command_text = subprocess.check_output(
        ['ps', '-p', str(record['pid']), '-o', 'command='], text=True).strip()
    if 'dagbt.benchmark_suite' not in command_text or command_text != record.get('process_command'):
        raise RuntimeError('Suite PID identity mismatch; refusing to signal unrelated process')
    os.kill(record['pid'], signal.SIGTERM)
    return {'stopped': True, 'pid': record['pid'], 'output': str(output)}


def launch(args):
    output = Path(args.output).resolve()
    # Serialize the short detach/lock handover so two simultaneous launch
    # commands cannot both report that they started the same experiment.
    with writer(output / '.launch', record=False):
        expected = manifest(args)
        check_previous_writer(output)
        old = read_json(output / 'manifest.json')
        if old is not None and old != expected:
            raise ValueError('Suite manifest differs; use another output directory')
        (output / 'ready.json').unlink(missing_ok=True)
        command_args = [sys.executable, '-u', '-m', 'dagbt.benchmark_suite', 'run']
        for name in ('output', 'webwalker_config', 'webwalker_judge_config', 'browsecomp_config',
                     'browsecomp_judge_config', 'webwalker_data', 'browsecomp_data', 'after_personamem'):
            value = getattr(args, name)
            if value is not None:
                command_args += ['--' + name.replace('_', '-'), str(Path(value).resolve())]
        if args.limit is not None:
            command_args += ['--limit', str(args.limit)]
        process = None
        try:
            from .webwalker_runner import registering_worker
            with (output / 'launcher.log').open('a') as log:
                with registering_worker():
                    process = subprocess.Popen(command_args, cwd=ROOT, stdout=log, stderr=log,
                                               stdin=subprocess.DEVNULL, start_new_session=True)
            deadline = time.monotonic() + 15
            while True:
                code = process.poll()
                ready = read_json(output / 'ready.json', {})
                if ready.get('pid') == process.pid:
                    owner = read_json(output / 'pid.json', {})
                    if (ready.get('output') != str(output) or owner.get('pid') != process.pid
                            or owner.get('output') != str(output)
                            or ready.get('writer_started_unix') != owner.get('started_unix')
                            or read_json(output / 'manifest.json') != expected
                            or ready.get('manifest_sha256') != file_hash(output / 'manifest.json')
                            or 'dagbt.benchmark_suite' not in owner.get('process_command', '')):
                        raise RuntimeError('Suite startup identity differs; inspect ' + str(output / 'launcher.log'))
                    if code is None and lock_is_held(output):
                        try:
                            observed = subprocess.check_output(
                                ['ps', '-p', str(process.pid), '-o', 'command='], text=True).strip()
                        except subprocess.CalledProcessError:
                            if (process.poll() == 0 and
                                    read_json(output / 'progress.json', {}).get('state') == 'complete'):
                                break
                            raise RuntimeError('Suite exited during startup identity verification') from None
                        if observed != owner['process_command']:
                            raise RuntimeError('Suite startup PID identity differs')
                        break
                    if code == 0 and read_json(output / 'progress.json', {}).get('state') == 'complete':
                        break  # A tiny experiment may finish before the parent polls.
                if code is not None:
                    raise RuntimeError('Suite failed to launch; inspect ' + str(output / 'launcher.log'))
                if time.monotonic() >= deadline:
                    raise RuntimeError('Suite did not publish validated readiness before startup deadline')
                time.sleep(0.05)
        except BaseException:
            terminate(process)
            raise
    return {'pid': process.pid, 'output': str(output), 'log': str(output / 'launcher.log')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('run', 'launch', 'score', 'preflight'):
        p = sub.add_parser(name)
        p.add_argument('--output', default='outputs/benchmarks_v4_full')
        p.add_argument('--webwalker-config', default='configs/webwalker-v4.json')
        p.add_argument('--webwalker-judge-config')
        p.add_argument('--browsecomp-config', default='configs/browsecomp-plus-v4.json')
        p.add_argument('--browsecomp-judge-config')
        p.add_argument('--webwalker-data', default='data/webwalkerqa')
        p.add_argument('--browsecomp-data', default='data/browsecomp_plus')
        p.add_argument('--after-personamem')
        p.add_argument('--limit', type=int)
        p.add_argument('--offline', action='store_true')
    for name in ('status', 'stop'):
        sub.add_parser(name).add_argument('--output', default='outputs/benchmarks_v4_full')
    args = parser.parse_args(argv)
    if args.command in ('run', 'score', 'launch'):
        stopping = False
        def interrupt(signum, frame):
            nonlocal stopping
            if not stopping:
                stopping = True
                raise KeyboardInterrupt('Benchmark suite stopped')
        signal.signal(signal.SIGTERM, interrupt)
        signal.signal(signal.SIGINT, interrupt)
    if args.command not in ('status', 'stop'):
        args.webwalker_judge_config = args.webwalker_judge_config or args.webwalker_config
        args.browsecomp_judge_config = args.browsecomp_judge_config or args.browsecomp_config
        if args.limit is not None and args.limit < 1:
            parser.error('--limit must be positive')
    if args.command in ('run', 'score'):
        try:
            code = run(args)
        except KeyboardInterrupt:
            return 130
        print(json.dumps(status(args.output), ensure_ascii=False, indent=2), flush=True)
        return code
    if args.command == 'launch':
        try:
            result = launch(args)
        except KeyboardInterrupt:
            return 130
    elif args.command == 'preflight':
        manifest(args)
        for dataset in DATASETS:
            code = run_stage(args, dataset, 'preflight')
            if code:
                return code
        result = {'preflight': 'passed', 'offline': args.offline}
    elif args.command == 'stop':
        result = stop(args.output)
    else:
        result = status(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
