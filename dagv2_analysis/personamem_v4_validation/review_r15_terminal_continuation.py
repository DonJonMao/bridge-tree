"""Offline structural R15 terminal-continuation review; no services or labels."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path('/Users/mao/projects/dagv2-personamem-v4')
OUT = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
RUN = ROOT / 'outputs/v4_validation_r15'
ATTEMPT = RUN / 'personamem/dagbt_residual_memory_v2/attempts/d9d48b04702b51834134ede14838c50a172c2479f32c91af962094b9e8320cd0/attempt-001'
sys.path.insert(0, str(ROOT))
from dagbt.budget import Ledger
from dagbt.config import DEFAULTS
from dagbt.evidence_spans import build_source_spans
from dagbt.fact_state import FactState
from dagbt.joint_reading import JointReader
from dagbt.model_runtime import prepare_request
from dagbt.personal_task import PERSONAL_READING_GUIDANCE
from dagbt.reasoning import Reasoner
from dagbt.resources import personamem_document
from dagbt.token_counting import _digest


def load(path):
    return json.loads(path.read_text())


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode())


result = load(ATTEMPT / 'result.json')
diagnostic = result['diagnostics']
joint = diagnostic['joint_reading']
snapshot = diagnostic['fact_state']
events = [json.loads(line) for line in (ATTEMPT / 'fusion_events.jsonl').read_text().splitlines()]
requests = [load(path) for path in (ATTEMPT / 'requests').glob('*.json')]
request = next(item for item in requests if item['stage'] == ['semantic_compose', '11'])
plan = next(item['plan'] for item in events if item['event'] == 'plan_frozen')
config = load(RUN / 'manifest.json')['config']
settings = {**deepcopy(DEFAULTS), **deepcopy(config['fusion'])}
settings['algorithm_version'] = 'dagbt_residual_memory_v2'
ledger = Ledger({'llm': 24, 'json_repairs': 6})


class NoCalls:
    def count_reasoning_tokens(self, *args, **kwargs):
        raise AssertionError('No service or new token count is permitted')
    def get(self, *args, **kwargs):
        raise AssertionError('No model generation is permitted')


reasoner = Reasoner(NoCalls(), None, config, settings, ledger, lambda event: None)
data = json.loads(request['payload']['messages'][1]['content'])
columns = data.pop('source_span_columns')
data['source_spans'] = [dict(zip(columns, row)) for row in data['source_spans']]
documents = data.pop('source_documents')
for source in data['source_spans']:
    metadata = documents[source['doc_id']]
    source['doc_id'] = metadata['doc_id']
    source['time_metadata'] = metadata['time_metadata']
assert 'known_observation_columns' not in data
restored = {}
for key, value in data.items():
    restored[key] = value
    if key == 'phase':
        restored['personal_task_instruction'] = PERSONAL_READING_GUIDANCE
data = restored


def wire(selected, operation='semantic_compose'):
    packed = JointReader._wire_data(selected)
    payload = reasoner._payload(operation, JointReader._system(packed), packed, JointReader._schema(selected))
    return prepare_request((operation, 'offline-review'), reasoner.url, payload, config)[1]


assert _digest(wire(data)) == _digest(request['payload']), 'Last paid terminal wire roundtrip mismatch'
candidate_ids = diagnostic['candidate_doc_ids']
records = {}
with (ROOT / 'data/personamem/corpus.jsonl').open() as handle:
    for line in handle:
        record = json.loads(line)
        if record['docid'] in candidate_ids:
            records[record['docid']] = record
assert set(records) == set(candidate_ids)
docs = {doc_id: personamem_document(records[doc_id]) for doc_id in candidate_ids}
sources = {}
source_aliases = {}
for doc_id in candidate_ids:
    for source in build_source_spans(doc_id, docs[doc_id], min(400, settings['max_quote_chars'])):
        alias = 's' + str(len(sources) + 1)
        sources[alias] = {**deepcopy(source), 'source_id': source['id'], 'id': alias}
        source_aliases[source['id']] = alias
for source in data['source_spans']:
    assert all(sources[source['id']][key] == value for key, value in source.items()), 'Saved alias reconstruction mismatch'

state = FactState(snapshot['initial_program'], snapshot['contract'], plan['steps'], plan['final_node_id'])
state.program = deepcopy(snapshot['program'])
state.revision = snapshot['program_revision']
state.routes = {row['id']: deepcopy(row) for row in snapshot['routes']}
state.versions = deepcopy(snapshot['versions'])
state.pending = set(snapshot['pending_variables'])
state.rule_route_ids = deepcopy(snapshot['rule_route_ids'])
state.instantiations = deepcopy(snapshot['instantiations'])
assert state.valid()[0] == snapshot['facts']
assert state.program['expression']['op'] == 'var' and not state.initial_program.get('rule_binding')
engine = SimpleNamespace(s=settings, ledger=ledger, reasoner=reasoner, event=lambda event: None,
    mapper=SimpleNamespace(sources=sources, source_aliases=source_aliases), steps=plan['steps'],
    q={'question': data['original_question']}, personal_response_selection=True,
    reader_question=data['public_output_question'], output_options=deepcopy(data['public_options']),
    residual_control=SimpleNamespace(task_projection=lambda parent: None, rules_completion_needed=lambda: False))
reader = JointReader(engine, state)
reader.current_identity = data['request_context']['query_identity']
reader.current_terminal_output = True
reader.restore_obligations(joint)
assert not reader.evidence_obligations and not reader.failed_batch_reviews
answer = json.loads(request['response']['choices'][0]['message']['content'])
clues = list(dict.fromkeys(alias for slot in answer['slots'] for row in slot['observations']
                          if row['stance'] in ('support', 'partial', 'contradiction') for alias in row['source_ids']))
reader.clues[reader.current_identity] = clues
pending = joint['batches'][-1]['unread_source_aliases']
assert len(pending) == 101
saved = {event['tokenization_wire_sha256']: event for event in events
         if event['event'] == 'tokenization_count' and event.get('status') == 'ok'}
tail_events = [event for event in events if event['event'] == 'tokenization_count' and event['sequence'] > 391]
tail_hashes = {event['tokenization_wire_sha256'] for event in tail_events}
prefixes = []
payloads = {}
for prefix_size in range(1, len(pending) + 1):
    aliases = list(dict.fromkeys(alias for group in pending[:prefix_size] for alias in group))
    selected = reader._payload(data['task'], data['grounded_subquestion'], list(data['variables']), aliases, True)
    repair = {**selected, 'repair_scope': {
        'failed': [{'variable': variable, 'id': '*', 'feedback': 'x' * 240, 'observation': None}
                   for variable in selected['variables']],
        'attempt': 1, 'previous_response_identity': '0' * 64}}
    hashes = [_digest(wire(selected)), _digest(wire(repair, 'semantic_compose_repair'))]
    assert all(identity in tail_hashes for identity in hashes), 'Continuation prefix lacks exact archived wire match'
    base, repair_count = [saved[identity]['count'] for identity in hashes]
    total = max(base, repair_count) + settings['reasoning_output_tokens'] + settings['input_margin'] + 8
    prefixes.append({'prefix_groups': prefix_size, 'window_source_count': len(aliases),
        'visible_source_count': len(selected['source_spans']), 'base_input_tokens': base,
        'repair_envelope_input_tokens': repair_count, 'admission_total_tokens': total,
        'over_context_tokens': total - settings['context_tokens'], 'wire_sha256s': hashes})
    payloads[prefix_size] = selected

smallest = payloads[1]
minimum = min(prefixes, key=lambda item: item['admission_total_tokens'])
packed = JointReader._wire_data(smallest)
mandatory = reader._payload(data['task'], data['grounded_subquestion'], list(data['variables']), [], True)
source_rows = smallest['source_spans']
coords = [(source['doc_id'], source['start'], source['end']) for source in source_rows]
overlap_pairs = sum(left['doc_id'] == right['doc_id'] and max(left['start'], right['start']) < min(left['end'], right['end'])
                    for index, left in enumerate(source_rows) for right in source_rows[index + 1:])
known = smallest['known_observations']
value_occurrences = []
for variable, parent in smallest['supported_parents'].items():
    occurrences = sum(row['variable'] == variable and row['value'] == parent['value'] for row in known)
    value_occurrences.append({'variable': variable, 'parent_value_utf8_bytes': size(parent['value']),
        'identical_known_route_values': occurrences,
        'exact_string_embedded_in_grounded_query': isinstance(parent['value'], str) and parent['value'] in smallest['grounded_subquestion']})
terminal_rows = [row for row in known if row['variable'] == plan['final_node_id']]
report = {
    'run': 'v4_validation_r15', 'question_index_one_based': 3,
    'scope': 'Offline structural review using exact archived tokenization wire matches. No labels, source/question/option/answer text, model requests, new tokenization, source edits, or experiment mutations.',
    'reader_source_sha256': hashlib.sha256((ROOT / 'dagbt/joint_reading.py').read_bytes()).hexdigest(),
    'answer_status': result['answer']['status'],
    'llm_calls': diagnostic['cost']['llm_attempts'],
    'json_repair_reservations': diagnostic['cost']['json_repair_reservations'],
    'history_complete_batches': sum(row['operation'] == 'joint_read' and row.get('complete') is True for row in joint['batches']),
    'terminal_complete_batches': sum(row['operation'] == 'semantic_compose' and row.get('complete') is True for row in joint['batches']),
    'audit_calls': diagnostic['cost']['audit_calls'],
    'last_paid_terminal': {'logical_call': 11, 'input_tokens': saved[_digest(request['payload'])]['count'],
        'window_source_count': len(joint['batches'][-2]['source_aliases']),
        'visible_source_count': len(data['source_spans']), 'known_route_count': len(data['known_observations'])},
    'continuation_pending_groups': len(pending), 'unread_marker_count': len(joint['unread_obligations']),
    'evidence_obligation_count': len(joint['evidence_obligations']), 'failed_batch_count': len(joint['failed_batch_reviews']),
    'continuation_saved_tokenization_events': len(tail_events),
    'all_101_prefixes_exact_archived_wire_matched': True,
    'all_101_prefixes_exceed_context': all(item['over_context_tokens'] > 0 for item in prefixes),
    'best_recorded_prefix': minimum,
    'one_group_prefix': prefixes[0],
    'full_pending_prefix': prefixes[-1],
    'context_tokens': settings['context_tokens'], 'output_token_reserve': settings['reasoning_output_tokens'],
    'input_margin_and_safety': settings['input_margin'] + 8,
    'mandatory_zero_new_group_source_count': len(mandatory['source_spans']),
    'known_route_count_after_first_terminal': len(known),
    'active_known_route_count': sum(state.is_active_route(state.routes[row['id']]) for row in known),
    'terminal_known_route_count': len(terminal_rows),
    'terminal_known_value_matches_public_option_count': sum(row['value'] in smallest['public_options'] for row in terminal_rows),
    'source_transport_checks': {'unique_alias_count': len({source['id'] for source in source_rows}),
        'unique_original_source_count': len({sources[source['id']]['source_id'] for source in source_rows}),
        'unique_coordinate_count': len(set(coords)), 'source_rows': len(source_rows),
        'overlapping_same_document_span_pairs': overlap_pairs,
        'source_text_utf8_bytes': sum(len(source['text'].encode()) for source in source_rows),
        'packed_source_rows_utf8_bytes': size(packed['source_spans']),
        'packed_source_documents_utf8_bytes': size(packed.get('source_documents', {})),
        'columnar_source_packing': 'source_span_columns' in packed,
        'shared_document_metadata_packing': 'source_documents' in packed},
    'packed_field_utf8_bytes': {key: size(packed[key]) for key in ('grounded_subquestion','supported_parents','known_observations','public_options','variables','source_spans')},
    'parent_value_repetition': value_occurrences,
    'new_network_calls': 0,
    'generation_calls_in_review': 0,
    'prefixes': prefixes,
}
output = OUT / 'r15_terminal_continuation_review.json'
if '--no-write' not in sys.argv:
    with output.open('x') as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({key: value for key, value in report.items() if key != 'prefixes'}, ensure_ascii=False, indent=2))
