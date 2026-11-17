#!/usr/bin/env python3
"""Offline replay of the 23 unresolved rows; stdout only, no model or labels.

Run with the repository venv. Imports the actual checked-in planner validators,
evaluator and certificate function. Does not modify programs on disk, load gold
labels, instantiate an engine, or call a model. A labelled hypothetical copy of
one program isolates the rules_complete guard; it is not a proposed repair.
"""
import argparse
from collections import Counter
from copy import deepcopy
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


def deny_network(*args, **kwargs):
    raise RuntimeError('This reproduction is offline; network connections are forbidden')


socket.create_connection = deny_network
socket.socket.connect = deny_network
socket.socket.connect_ex = deny_network

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=Path('/Users/mao/projects/dagv2-personamem-a48'))
parser.add_argument('--analysis', type=Path, default=Path(__file__).resolve().parent)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

from dagbt.engine import legacy_modules
from dagbt.residual import (validate_program, validate_output_contract,
                           possible_outputs, certify_output)
from dagbt.residual_plan import validate_plan, validate_bindings

_, legacy_repair, _ = legacy_modules()


def check(function, *positional, **keywords):
    try:
        function(*positional, **keywords)
    except Exception as exc:
        return {'accepted': False, 'exception': type(exc).__name__, 'message': str(exc)}
    return {'accepted': True}


def certify(state, program=None):
    return certify_output(
        state['program'] if program is None else program,
        state['facts'], state['contract'],
        program_revision=state['program_revision'],
        versions=state['versions'], sources=state['sources'],
        pending_variables=state['pending_variables'])


secrecy_units = {
    '57154824-9041-47ce-ae17-27b93e7cd1ce',
    '112eeb1b-84d0-47b2-a983-4cb3a0b8287f',
}
selected = [json.loads(line) for line in (args.analysis / 'failure_features.jsonl').read_text().splitlines()
            if line.strip()]
selected = [feature for feature in selected if feature['status'] == 'unresolved_or_exhausted']
rows = []
for feature in selected:
    path = args.analysis / feature['path']
    with gzip.open(path, 'rt') as stream:
        row = json.load(stream)
    state = row['diagnostics']['fact_state']
    program, contract = state['program'], state['contract']
    initial = next(event for event in row['diagnostics']['events']
                   if event.get('event') == 'typed_dag_initialized')
    initial_plan = {'steps': initial['dag'], 'final_node_id': initial['final_node_id'],
                    'program': initial['F'], 'output_contract': initial['output_contract']}
    validators = {
        'full_initial_plan': check(validate_plan, deepcopy(initial_plan), legacy_repair.validate_plan),
        'current_program': check(validate_program, program),
        'current_contract': check(validate_output_contract, contract),
        'current_bindings': check(validate_bindings, program, initial['dag'],
                                  initial['final_node_id'], contract=contract),
    }
    outcome = possible_outputs(program, state['facts'])
    certificate = certify(state)
    expected_op = {'one_reason': 'one_reason', 'all_failures': 'failures'}.get(contract['mode'])
    mismatch = expected_op is not None and program['expression']['op'] != expected_op
    overflow = any(error.get('type') == 'InputOverflow' for error in feature['errors'])
    if mismatch and outcome['status'] == 'determined':
        cause = 'determined_static_mode_expression_mismatch'
    elif (outcome['status'] == 'determined' and not program.get('rules_complete', True)
          and not program.get('rule_binding')):
        cause = 'determined_incomplete_rules_without_completion_route'
    elif overflow:
        cause = 'local_input_overflow'
    elif feature['unit_id'] == '8823918d-36cc-4caa-87f7-075f846a0be5':
        cause = 'compose_rejected_missing_original_sources'
    elif feature['unit_id'] in secrecy_units:
        cause = 'secrecy_plan_compose_unresolved'
    else:
        raise AssertionError(f'Unclassified unit: {feature["unit_id"]}')
    result = {
        'unit_id': feature['unit_id'], 'path': feature['path'],
        'mode': contract['mode'], 'result_type': contract['result_type'],
        'expression': program['expression'],
        'rules_complete': program.get('rules_complete', True),
        'rule_binding_present': program.get('rule_binding') is not None,
        'program_revision': state['program_revision'],
        'validators': validators,
        'facts_bound': sorted(state['facts']),
        'pending_variables': state['pending_variables'],
        'possible_outputs_status': outcome['status'],
        'nonempty_proven': outcome['nonempty_proven'],
        'live_variables': outcome['live_variables'],
        'logged_active_demands': feature['last_residual_state']['active_demands'],
        'logged_outcome_matches_replay': feature['last_residual_state']['outcome'] == outcome['status'],
        'certificate_is_none': certificate is None,
        'mode_expression_mismatch': mismatch,
        'primary_observed_cause': cause,
        'errors': feature['errors'], 'failed_slots': feature['failed_slots'],
        'llm_used': feature['ledger']['used']['llm'],
        'ann_used': feature['ledger']['used']['ann'],
        'terminal_choice_legal': feature.get('terminal_check', {}).get('choice_legal'),
    }
    if cause == 'determined_incomplete_rules_without_completion_route':
        hypothetical = deepcopy(program)
        hypothetical['rules_complete'] = True
        result['hypothetical_guard_isolation_only'] = {
            'changed_field_on_in_memory_copy': 'rules_complete=True',
            'certificate_exists': certify(state, hypothetical) is not None,
            'warning': 'Does not establish rule completeness; never applied to production or a result row',
        }
    rows.append(result)


def synthetic(mode, kind, value, explanation):
    """Minimal accepted planner/contract pair that cannot certify sourced facts."""
    contract = {'mode': mode, 'result_type': kind, 'entity_scope': 'example user',
                'time_scope': 'past', 'explanation': explanation}
    program = {'variables': {'reason': {'type': kind, 'demand': 'reason', 'open': True}},
               'expression': {'op': 'var', 'id': 'reason'}, 'rules_complete': True}
    steps = [{'question': 'What reason does the example user report?', 'output_slot': 'reason',
              'answer_type': kind, 'inputs': [], 'execution': 'retrieval'}]
    plan = {'steps': steps, 'final_node_id': 'reason', 'program': program,
            'output_contract': contract}
    outcome = possible_outputs(program, {'reason': value})
    return {'mode': mode, 'result_type': kind, 'expression_op': 'var',
            'full_plan_validation': check(validate_plan, plan, legacy_repair.validate_plan),
            'possible_outputs_status': outcome['status'], 'live_variables': outcome['live_variables'],
            'certificate_is_none': certify_output(program, {'reason': value}, contract,
                                                   sources={'reason': ['synthetic_source']}) is None}


report = {
    'scope': '23 unresolved current rows; offline validation/evaluation; no gold labels or model calls',
    'source_directory': str(args.source.resolve()),
    'source_sha256': {name: hashlib.sha256((args.source / name).read_bytes()).hexdigest()
                      for name in ('dagbt/residual.py', 'dagbt/residual_plan.py',
                                   'dagbt/residual_control.py', 'dagbt/local_terminal.py',
                                   'dagv2/experiment.py', 'dagv2/repair_planner.py')},
    'summary': {
        'rows': len(rows),
        'modes': dict(Counter(row['mode'] for row in rows)),
        'result_types': dict(Counter(row['result_type'] for row in rows)),
        'outcomes': dict(Counter(row['possible_outputs_status'] for row in rows)),
        'all_validators_accept': all(all(v['accepted'] for v in row['validators'].values()) for row in rows),
        'all_certificates_none': all(row['certificate_is_none'] for row in rows),
        'all_replay_outcomes_match_logs': all(row['logged_outcome_matches_replay'] for row in rows),
        'determined_and_no_active_demands': sum(row['possible_outputs_status'] == 'determined'
                                               and not row['logged_active_demands'] for row in rows),
        'mode_expression_mismatches_including_latent': sum(row['mode_expression_mismatch'] for row in rows),
        'primary_observed_causes': dict(Counter(row['primary_observed_cause'] for row in rows)),
    },
    'synthetic_minimal_repros': [synthetic('one_reason', 'text', 'Reported explanation', 'one'),
                               synthetic('all_failures', 'set', ['Reported explanation'], 'all')],
    'rows': rows,
}
print(json.dumps(report, ensure_ascii=False, indent=2))
