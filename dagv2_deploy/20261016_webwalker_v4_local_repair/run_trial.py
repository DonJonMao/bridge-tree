#!/usr/bin/env python3
"""Persist a predeclared two-question generation/scoring pipeline."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--trial', required=True)
    a = p.parse_args()
    source, trial = Path(a.source).resolve(), Path(a.trial).resolve()
    config = trial / 'runtime_config.json'
    assert (trial / 'declaration.json').is_file() and config.is_file()
    assert not (trial / 'state.json').exists(), 'Do not replay a previously started trial'
    python = '/Users/mao/projects/dagv2/.venv/bin/python'
    common = [python, '-u', '-m', 'dagbt.webwalker_runner']
    commands = [
        ('preflight', common + ['preflight', '--config', str(config), '--output', str(trial / 'preflight')]),
        ('generation', common + ['run', '--config', str(config), '--limit', '2', '--output', str(trial / 'output')]),
        ('scoring', common + ['score', '--config', str(config), '--output', str(trial / 'output')]),
    ]
    env = dict(os.environ, PYTHONPATH='.', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    state = {'started_utc': now(), 'source': str(source), 'trial': str(trial),
             'driver_pid': os.getpid(), 'completed_stages': [], 'status': 'starting'}
    for name, argv in commands:
        state.update(status='running_' + name, updated_utc=now())
        save(trial / 'state.json', state)
        print(json.dumps({'stage': name, 'status': 'started', 'utc': now()}), flush=True)
        started = time.monotonic()
        with (trial / (name + '.log')).open('xb') as log:
            process = subprocess.Popen(argv, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT)
            state['child_pid'] = process.pid
            save(trial / 'state.json', state)
            code = process.wait()
        state['completed_stages'].append({'name': name, 'exit_code': code,
                                         'seconds': time.monotonic() - started,
                                         'log_sha256': hashlib.sha256((trial / (name + '.log')).read_bytes()).hexdigest()})
        print(json.dumps({'stage': name, 'exit_code': code, 'utc': now()}), flush=True)
        if code:
            state.update(status='failed_' + name, finished_utc=now())
            save(trial / 'state.json', state)
            raise SystemExit(code)
    state.update(status='complete', finished_utc=now())
    save(trial / 'state.json', state)
    print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
