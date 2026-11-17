"""Observe the existing R20 writer until natural exit; never stop or mutate it."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
RUN = Path('/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r20')
SCRIPTS = ('monitor_r20_structural.py', 'review_r20_closure.py',
           'review_r20_history_wire.py', 'review_r20_frontier.py', 'review_r20_tokenization.py')


def read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def alive():
    pid = read(RUN / 'pid.json').get('pid')
    if not isinstance(pid, int):
        return None
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


while True:
    observed = {}
    for script in SCRIPTS:
        result = subprocess.run([sys.executable, str(BASE / script)], capture_output=True, text=True)
        if result.returncode:
            # Never export uncontrolled exception text from a source-data reader.
            observed[script] = {'script_exit': result.returncode, 'review_incomplete': True}
            continue
        try:
            observed[script] = json.loads(result.stdout.splitlines()[-1])
        except (ValueError, IndexError):
            observed[script] = {'review_incomplete': True}
    progress = read(RUN / 'progress.json')
    live = alive()
    monitor = observed.get(SCRIPTS[0], {})
    wire = observed.get(SCRIPTS[2], {})
    print(json.dumps({'observed_unix': time.time(), 'live_pid': live,
        'progress': {key: progress.get(key) for key in ('state', 'question_index', 'arm', 'failed_arm_tasks')},
        'completed_residual_rows': monitor.get('completed'), 'status_counts': monitor.get('status_counts'),
        'new_cases': monitor.get('new_cases'), 'active': monitor.get('active'),
        'new_active_failures': monitor.get('new_active_failures'),
        'mandatory': observed.get(SCRIPTS[1]),
        'wire': {key: wire.get(key) for key in ('shared_history_request_count', 'decode_failures',
                                               'missing_decode_instruction', 'structure_mismatches')},
        'frontier': observed.get(SCRIPTS[3]),
        'both_arm_tokenization':observed.get(SCRIPTS[4]),
        'review_script_failures': [name for name, value in observed.items() if value.get('review_incomplete')]},
        ensure_ascii=False), flush=True)
    if progress.get('state') in {'complete', 'complete_with_failures'} and live is False:
        break
    time.sleep(45)
