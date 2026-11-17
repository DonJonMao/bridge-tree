#!/usr/bin/env python3
"""Revalidate archived unresolved plans offline, without labels or model calls.

This establishes early rejection of impossible contracts only. It does not
assert repaired predictions, achieved accuracy, or solved capacity failures.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import socket
import sys

sys.dont_write_bytecode = True
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

def denied(*args, **kwargs):
    raise RuntimeError('Network is forbidden during archived plan validation')
socket.create_connection = denied
socket.socket.connect = denied
socket.socket.connect_ex = denied
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=Path('/Users/mao/projects/dagv2-personamem-v4'))
parser.add_argument('--analysis', type=Path, default=Path('/Users/mao/projects/dagv2_analysis/personamem_v3_1_full_20261013'))
args = parser.parse_args()
sys.path.insert(0, str(args.source))
from dagbt.engine import legacy_modules
from dagbt.residual_plan import validate_plan
_, repair, _ = legacy_modules()
features = [json.loads(line) for line in (args.analysis / 'failure_features.jsonl').read_text().splitlines() if line.strip()]
results = []
for feature in features:
    if feature['status'] != 'unresolved_or_exhausted':
        continue
    with gzip.open(args.analysis / feature['path'], 'rt') as stream:
        row = json.load(stream)
    event = next(event for event in row['diagnostics']['events'] if event.get('event') == 'typed_dag_initialized')
    plan = {'steps': event['dag'], 'final_node_id': event['final_node_id'],
            'program': event['F'], 'output_contract': event['output_contract']}
    result = {'unit_id': feature['unit_id'], 'path': feature['path'],
              'mode': plan['output_contract']['mode'],
              'result_type': plan['output_contract']['result_type'],
              'rules_complete': plan['program'].get('rules_complete', True)}
    try:
        validate_plan(plan, repair.validate_plan)
    except Exception as exc:
        result.update(accepted=False, error_type=type(exc).__name__, error=str(exc))
    else:
        result['accepted'] = True
    results.append(result)
    del row
summary = dict(Counter('accepted_contract' if result['accepted'] else 'rejected_before_retrieval' for result in results))
assert len(results) == 23
assert summary == {'rejected_before_retrieval': 13, 'accepted_contract': 10}, summary
assert sum(not r['accepted'] and r['mode'] in ('one_reason', 'all_failures') for r in results) == 12
assert all(r['accepted'] for r in results if r['mode'] == 'semantic')
report = {'scope': '23 archived unresolved rows; full initial plan revalidation; no labels or model calls',
          'limitation': 'Plan rejection does not prove a repaired plan will succeed or be accurate.',
          'source_directory': str(args.source.resolve()),
          'source_sha256': {name: hashlib.sha256((args.source / name).read_bytes()).hexdigest()
                            for name in ['dagbt/residual.py', 'dagbt/residual_plan.py', 'dagbt/fact_state.py',
                                         'dagbt/local_terminal.py', 'dagv2/repair_planner.py']},
          'summary': summary, 'rows': results}
print(json.dumps(report, ensure_ascii=False, indent=2))
