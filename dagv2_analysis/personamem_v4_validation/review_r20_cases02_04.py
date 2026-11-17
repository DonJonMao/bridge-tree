"""Offline structural review of two completed R20 rows; no labels or services."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path('/Users/mao/projects/dagv2-personamem-v4')
RUN = ROOT / 'outputs/v4_validation_r20'
OUT = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
sys.path.insert(0, str(ROOT))
from dagbt.history_wire import unpack as unpack_history
from dagbt.review_wire import unpack as unpack_review
from jsonschema import Draft202012Validator

STEMS = {
    2: '2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0',
    4: 'bfde6b00668a05e31ba730b0a046c42f56ee8840e8ea72e37f5b175270b19b4f',
}
reads = {}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read(path):
    raw = path.read_bytes()
    reads[str(path)] = sha(raw)
    return raw.decode()

def load(path):
    return json.loads(read(path))

def digest(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())

def observation(row):
    return {'id': row.get('id'), 'stance': row.get('stance'),
            'source_ids': row.get('source_ids', []), 'value_hash': digest(row.get('value')),
            'row_hash': digest(row), 'parent_versions': row.get('parent_versions'),
            'summary_revision': row.get('summary_revision') is not None}

def slot(row):
    return {'variable': row.get('variable'),
            'observations': [observation(x) for x in row.get('observations', [])],
            'unresolved_count': len(row.get('unresolved', [])),
            'unresolved_hashes': [digest(x) for x in row.get('unresolved', [])],
            'resolved_obligation_ids': row.get('resolved_obligation_ids', []),
            'reviewed_observation_ids': row.get('reviewed_observation_ids', []),
            'resolved_failed_batch_ids': row.get('resolved_failed_batch_ids', [])}

cases = {}
raw_cases = {}
for index, stem in STEMS.items():
    base = RUN / 'personamem/dagbt_residual_memory_v2'
    row = load(base / 'rows' / (stem + '.json'))
    attempt = base / 'attempts' / stem / 'attempt-001'
    events = [json.loads(x) for x in read(attempt / 'fusion_events.jsonl').splitlines()]
    diag = row['diagnostics']
    joint = diag['joint_reading']
    requests = []
    by_call = {}
    for path in sorted((attempt / 'requests').glob('*.json')):
        record = load(path)
        stage = record.get('stage', [])
        if len(stage) != 2 or stage[0] not in {
            'joint_read', 'joint_read_repair', 'semantic_compose',
            'semantic_compose_repair', 'audit_joint', 'audit_joint_repair'}:
            continue
        payload = record['payload']
        wire = json.loads(payload['messages'][1]['content'])
        data = unpack_history(unpack_review(wire))
        if 'source_span_columns' in data:
            data['source_spans'] = [dict(zip(data['source_span_columns'], x)) for x in data['source_spans']]
        response = json.loads(record['response']['choices'][0]['message']['content'])
        schema = json.loads(payload['messages'][0]['content'].rsplit(
            'Return one complete JSON object matching this schema:\n', 1)[1])
        errors = list(Draft202012Validator(schema).iter_errors(response))
        failed = data.get('repair_scope', {}).get('failed', [])
        offers = {}
        for entry in failed:
            offer = entry.get('frozen_observation_reviews', {})
            offers.setdefault(entry['variable'], []).extend([
                *offer.get('slot_observation_ids', []), *[x['id'] for x in offer.get('observations', [])]])
        obligations = []
        for issue in data.get('evidence_obligations', []):
            required = set(issue['source_ids'])
            citations = {s for x in response.get('slots', []) if x['variable'] == issue['variable']
                         for y in x['observations'] for s in y['source_ids']}
            obligations.append({'id': issue['id'], 'variable': issue['variable'],
                                'source_count': len(required), 'covered_count': len(required & citations),
                                'missing_count': len(required - citations)})
        record_out = {
            'call': int(stage[1]), 'operation': stage[0],
            'file': str(path.relative_to(RUN)), 'file_sha256': reads[str(path)],
            'task': data['task']['output_slot'], 'sources': len(data['source_spans']),
            'source_ids': [x['id'] for x in data['source_spans']],
            'input_tokens': record.get('tokenization_validation', {}).get('expected_prompt_tokens'),
            'output_cap': payload.get('max_tokens'),
            'usage_matched': record.get('tokenization_validation', {}).get('status') == 'matched',
            'finish_reason': record['response']['choices'][0].get('finish_reason'),
            'shared_history_texts': 'shared_history_texts' in wire,
            'shared_review_texts': 'shared_review_texts' in wire,
            'schema_valid': not errors,
            'schema_errors': [{'path': list(e.absolute_path), 'validator': e.validator} for e in errors],
            'schema_branches': schema['properties']['slots']['items'].get('oneOf', []),
            'frozen_offered_ids': offers,
            'repair_scope_keys': list(data.get('repair_scope', {})),
            'response_slots': [slot(x) for x in response.get('slots', [])],
            'obligation_coverage': obligations,
        }
        requests.append(record_out)
        by_call[int(stage[1])] = (data, response, record_out)
    requests.sort(key=lambda x: x['call'])
    selected = []
    names = {'joint_support_capacity_rejected', 'joint_support_handoff_deferred',
             'joint_repair_unchanged', 'joint_repair_input_unavailable', 'residual_action_incomplete'}
    for e in events:
        if e.get('event') in names:
            selected.append({k: e[k] for k in (
                'sequence', 'event', 'node_id', 'next_node_id', 'next_operation',
                'operation', 'source_spans', 'repair_attempt', 'input_tokens',
                'output_token_reserve', 'input_margin', 'context_tokens', 'type') if k in e})
    plan = next(e['plan'] for e in events if e.get('event') == 'plan_frozen')
    result = {
        'unit_id': row['unit_id'], 'status': row['answer']['status'],
        'audit_complete': diag['audit_complete'], 'versions': diag['fact_state']['versions'],
        'pending_variables': diag['fact_state']['pending_variables'],
        'ledger': {k: diag['ledger'][k] for k in ('limits', 'used', 'remaining')},
        'errors': diag['errors'],
        'plan': [{'task': s['output_slot'], 'inputs': s['inputs'], 'execution': s['execution'],
                  'question_hash': digest(s['question'])} for s in plan['steps']],
        'requests': requests, 'selected_events': selected,
        'event_counts': dict(Counter(e.get('event') for e in events)),
        'final_evidence_obligations': [{'id': x['id'], 'variable': x['variable'],
                                      'sources': len(x['source_ids'])} for x in joint['evidence_obligations']],
        'final_failed_reviews': [{'id': x['id'], 'variable': x['variable'],
                                 'sources': len(x['source_ids'])} for x in joint['failed_batch_reviews']],
        'hard_unread_by_variable': dict(Counter(v for x in joint['unread_obligations'] for v in x[2])),
        'hard_unread_count': len(joint['unread_obligations']),
    }
    cases[str(index)] = result
    raw_cases[index] = by_call

b = raw_cases[2]
getaway = {s['id'] for s in b[5][0]['source_spans']}
history = set(b[3][1]['slots'][0]['observations'][0]['source_ids'])
preferences = set(b[8][1]['slots'][0]['observations'][0]['source_ids'])
cases['2']['set_relations'] = {
    'getaway_retained': len(getaway), 'history_cited': len(history), 'preferences_cited': len(preferences),
    'getaway_union_history': len(getaway | history),
    'getaway_union_history_union_preferences': len(getaway | history | preferences),
    'preferences_new_beyond_retained_and_history': sorted(preferences - (getaway | history)),
    'getaway_observation_5_6_7_identical': b[5][1]['slots'][0]['observations'] == b[6][1]['slots'][0]['observations'] == b[7][1]['slots'][0]['observations'],
    'preference_observation_8_9_10_identical': b[8][1]['slots'][0]['observations'] == b[9][1]['slots'][0]['observations'] == b[10][1]['slots'][0]['observations'],
}
b = raw_cases[4]
def terminal_slot(response):
    return next(x for x in response['slots'] if x['variable'] == 'response')
support = terminal_slot(b[7][1])['observations'][0]
repair = b[8][1]
cases['4']['terminal_relationships'] = {
    'call7_support_value_equals_public_option': support['value'] in b[7][0]['public_options'],
    'call7_semantic_answer_equals_supported_value': b[7][1].get('semantic_answer') == support['value'],
    'call7_prediction_is_null': b[7][1].get('final_prediction') is None,
    'call8_slots_empty': repair.get('slots') == [],
    'call8_semantic_answer_equals_supported_value': repair.get('semantic_answer') == support['value'],
    'call8_prediction_is_legal': repair.get('final_prediction') in ['a', 'b', 'c', 'd'],
    'unknown_observation_9_10_11_identical': terminal_slot(b[9][1])['observations'] == terminal_slot(b[10][1])['observations'] == terminal_slot(b[11][1])['observations'],
    'call9_is_new_batch_so_old_route_id_not_initially_frozen': True,
    'call10_11_unknown_frozen_id_not_in_settled_offers': True,
}
sources = ['dagbt/joint_reading.py', 'dagbt/residual_control.py', 'dagbt/personal_task.py',
           'dagbt/review_wire.py', 'dagbt/reasoning.py']
for name in sources:
    read(ROOT / name)
comparisons = ['r20_case01_reader_failure_review.json', 'r20_case01_obligation_scope_review.json',
               'r20_case04_reader_failure_review.json', 'r20_case04_terminal_consistency.json']
comparison_hashes = {}
for name in comparisons:
    read(OUT / name)
    comparison_hashes[name] = reads[str(OUT / name)]
unchanged = all(sha(Path(path).read_bytes()) == old for path, old in reads.items())
assert unchanged, 'Evidence changed during analysis'
report = {
    'run': 'v4_validation_r20', 'source_commit': '6c046374008ce2e45f817d6bc9876b3ab927ab18',
    'scope': 'Read-only saved published rows, requests, events and source. No labels, scores, services, tokenizer calls or run/source mutations.',
    'cases': cases, 'comparison_reports_sha256': comparison_hashes,
    'files_sha256': reads, 'read_set_unchanged_after_analysis': unchanged,
    'design': {
        'field': 'repair_scope.frozen_observation_ids',
        'type': 'object mapping each currently requested failed variable to sorted current-batch frozen observation IDs',
        'schema_forbids': 'ordinary observations.id in F_v; output schema shape otherwise unchanged',
        'schema_allows_reference': 'reviewed_observation_ids only in R_v from current explicit settled offers; R_v subset of F_v',
        'construction_time': 'after summary revision, whole-value and handoff rejection thawing, before next repair preparation/count/selection',
        'never_import_ids_from': ['known_observations', 'durable failed records', 'other variables', 'previous batches'],
        'unknown_partial_review_authority_added': False,
        'runtime_guard_changed': False,
    },
}
path = OUT / 'r20_cases02_04_failure_review.json'
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'path': str(path), 'sha256': sha(path.read_bytes()),
                  'cases': {k: {'status': v['status'], 'requests': len(v['requests'])} for k, v in cases.items()},
                  'read_set_unchanged': unchanged}, ensure_ascii=False))
