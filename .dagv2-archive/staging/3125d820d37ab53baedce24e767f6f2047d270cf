"""Read-only archived R14 repair reconstruction; optional tokenization only.

Never print source/question/option text, credentials, or raw request payloads.
Report creation is exclusive; archived experiment files are never modified.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

ROOT = Path('/Users/mao/projects/dagv2-personamem-v4-reconcile')
RELEASE = Path('/Users/mao/projects/dagv2-personamem-v4')
REPORTS = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
OLD_COMMIT = '25fc3849ab8d4b7ab85cf5efdeafddf2d685c58b'
RUN = RELEASE / 'outputs/v4_validation_r14'
ATTEMPT = RUN / 'personamem/dagbt_residual_memory_v2/attempts/7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0/attempt-001'
sys.path.insert(0, str(ROOT))

from dagbt.budget import Ledger
from dagbt.config import DEFAULTS
from dagbt.evidence_spans import build_source_spans
from dagbt.fact_state import FactState
from dagbt.joint_reading import JointReader
from dagbt.model_runtime import prepare_request
from dagbt.personal_task import PERSONAL_HISTORY_GUIDANCE
from dagbt.reasoning import Reasoner
from dagbt.resources import personamem_document
from dagbt.token_counting import DeploymentTokenCounter, _digest


def load(path):
    return json.loads(path.read_text())


def unpack(record):
    data = json.loads(record['payload']['messages'][1]['content'])
    columns = data.pop('source_span_columns', None)
    if columns:
        data['source_spans'] = [dict(zip(columns, row)) for row in data['source_spans']]
    documents = data.pop('source_documents', None)
    if documents:
        for source in data['source_spans']:
            metadata = documents[source['doc_id']]
            source['doc_id'] = metadata['doc_id']
            source['time_metadata'] = metadata['time_metadata']
    assert 'known_observation_columns' not in data, 'Unsupported archived observation packing'
    restored = {}
    for key, value in data.items():
        restored[key] = value
        if key == 'phase':
            restored['personal_task_instruction'] = PERSONAL_HISTORY_GUIDANCE
    return restored


old_code = subprocess.run(
    ['git', '-C', str(ROOT), 'show', OLD_COMMIT + ':dagbt/joint_reading.py'],
    check=True, capture_output=True, text=True).stdout
old_module = ModuleType('dagbt._r14_archived_joint_reading')
old_module.__package__ = 'dagbt'
sys.modules[old_module.__name__] = old_module
exec(compile(old_code, '<archived-r14-joint-reading>', 'exec'), old_module.__dict__)
OldJointReader = old_module.JointReader

events = [json.loads(line) for line in (ATTEMPT / 'fusion_events.jsonl').read_text().splitlines()]
requests = [load(path) for path in (ATTEMPT / 'requests').glob('*.json')]
request = next(item for item in requests if item['stage'] == ['joint_read_repair', '7'])
initial_request = next(item for item in requests if item['stage'] == ['joint_read', '6'])
plan = next(item['plan'] for item in events if item['event'] == 'plan_frozen')
config = load(RUN / 'manifest.json')['config']
if config.get('credentials_file') and not Path(config['credentials_file']).is_absolute():
    config['credentials_file'] = str(RELEASE / config['credentials_file'])
settings = {**deepcopy(DEFAULTS), **deepcopy(config['fusion'])}
settings['algorithm_version'] = 'dagbt_residual_memory_v2'
ledger = Ledger({'llm': 24, 'json_repairs': 6})
reasoner = Reasoner(None, None, config, settings, ledger, lambda event: None)
data = unpack(request)
initial_data = unpack(initial_request)


def wire(selected, reader_class=JointReader):
    packed = reader_class._wire_data(selected)
    payload = reasoner._payload('joint_read_repair', reader_class._system(packed), packed,
                                reader_class._schema(selected))
    return prepare_request(('joint_read_repair', 'replay'), reasoner.url, payload, config)[1]


old_wire = wire(data, OldJointReader)
old_wire_hash = _digest(old_wire)
assert old_wire_hash == _digest(request['payload']), 'Archived complete repair wire roundtrip differs'
saved = {item['tokenization_wire_sha256']: item for item in events
         if item['event'] == 'tokenization_count' and item.get('status') == 'ok'}
assert old_wire_hash in saved, 'Archived exact repair wire lacks an authoritative saved count'

if '--reconstruct-only' in sys.argv:
    print(json.dumps({'original_call7_wire_roundtrip': True,
                      'original_call7_wire_sha256': old_wire_hash,
                      'original_call7_input_tokens': saved[old_wire_hash]['count'],
                      'generation_calls': 0, 'new_network_tokenization_calls': 0}))
    sys.exit(0)

doc_ids = {source['doc_id'] for source in data['source_spans']}
records = {}
with (RELEASE / 'data/personamem/corpus.jsonl').open() as handle:
    for line in handle:
        record = json.loads(line)
        if record['docid'] in doc_ids:
            records[record['docid']] = record
assert set(records) == doc_ids, 'Archived sources require unavailable original documents'
docs = {identifier: personamem_document(record) for identifier, record in records.items()}
originals = {identifier: build_source_spans(identifier, document, min(400, settings['max_quote_chars']))
             for identifier, document in docs.items()}
sources = {}
source_aliases = {}
for saved_source in data['source_spans']:
    matches = [source for source in originals[saved_source['doc_id']]
               if all(source.get(key) == value for key, value in saved_source.items() if key != 'id')]
    assert len(matches) == 1, 'Archived source does not uniquely match authoritative original'
    source = matches[0]
    alias = saved_source['id']
    assert alias not in sources and source['id'] not in source_aliases
    sources[alias] = {**deepcopy(source), 'source_id': source['id'], 'id': alias}
    source_aliases[source['id']] = alias


def stable(value):
    if isinstance(value, dict):
        return {key: [sources[alias]['source_id'] for alias in item] if key == 'source_ids'
                else deepcopy(item) if key in ('value', 'output') else stable(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [stable(item) for item in value]
    return deepcopy(value)


state = FactState(plan['program'], plan['output_contract'], plan['steps'], plan['final_node_id'])
state.routes = {row['id']: stable(row) for row in data['known_observations']}
state.revision = data['program_revision']
for variable, contract in data.get('summary_revision_contracts', {}).items():
    state.versions[variable] = contract['previous_version']
for variable, parent in data.get('supported_parents', {}).items():
    state.versions[variable] = parent['version']
state.pending = {item['variable'] for item in data.get('evidence_obligations', [])}
engine = SimpleNamespace(s=settings, ledger=ledger, reasoner=reasoner, event=lambda event: None,
                         mapper=SimpleNamespace(sources=sources, source_aliases=source_aliases),
                         steps=plan['steps'], docs=docs, spans={}, personal_response_selection=True)
reader = JointReader(engine, state)
reader.evidence_obligations = {item['id']: stable(item) for item in data.get('evidence_obligations', [])}
state_before = deepcopy(state.public_dict())
obligations_before = deepcopy(reader.evidence_obligations)
initial_response = json.loads(initial_request['response']['choices'][0]['message']['content'])
assert len(initial_response['slots']) == 1
slot = initial_response['slots'][0]
assert len(data['repair_scope']['failed']) == 1
entry = data['repair_scope']['failed'][0]
assert entry['id'] == '*' and _digest(entry['slot']) == _digest(slot)
assert len(slot['observations']) == 1
visible = {source['id']: source for source in data['source_spans']}
valid = [reader._observation(row, slot['variable'], visible, data['task'], allow_summary_revision=True)
         for row in slot['observations']]
frozen = {(row['variable'], row['id']) for row in valid}
failures = {}
reviews = {slot['variable']: slot}
feedback = reader._update_evidence_obligations(reviews, valid, initial_data, failures,
                                              data['request_context']['query_identity'])
feedback = reader._current_obligation_feedback(feedback, reviews, failures)
assert set(feedback) == {slot['variable']}
assert failures == {(entry['variable'], '*'): entry['feedback']}
assert state.public_dict() == state_before and reader.evidence_obligations == obligations_before
current = deepcopy(data)
current_entry = current['repair_scope']['failed'][0]
current_entry['obligation_review_sources'] = deepcopy(feedback[slot['variable']]['sources'])
offered = reader._offer_frozen_reviews(current, valid, frozen, feedback)
assert set(offered) == frozen
review_offer = current_entry['frozen_observation_reviews']
assert review_offer['slot_observation_ids'] == [valid[0]['id']] and not review_offer['observations']
source_feedback = current_entry['obligation_review_sources']
assert len(source_feedback) == 1
assert [len(source_feedback[0][key]) for key in
        ('required_source_ids', 'covered_source_ids', 'missing_source_ids')] == [53, 3, 50]
new_wire = wire(current)
new_wire_hash = _digest(new_wire)
report = {
    'run': 'archived_v4_validation_r14',
    'scope': 'Reconstruct the exact archived call7 wire, then invoke current production coverage feedback and frozen-offer helpers. Optional deployment tokenization only; no generation, labels, experiment writes, or raw text output.',
    'reader_source_sha256': hashlib.sha256((ROOT / 'dagbt/joint_reading.py').read_bytes()).hexdigest(),
    'original_call7_wire_roundtrip': True,
    'original_call7_wire_sha256': old_wire_hash,
    'original_call7_input_tokens': saved[old_wire_hash]['count'],
    'original_call7_total_tokens': saved[old_wire_hash]['count'] + 4096 + 264,
    'new_repair_wire_sha256': new_wire_hash,
    'source_count': len(data['source_spans']),
    'required_source_count': 53, 'covered_source_count': 3, 'missing_source_count': 50,
    'frozen_slot_reference_count': len(review_offer['slot_observation_ids']),
    'frozen_full_row_fallback_count': len(review_offer['observations']),
    'production_helpers_used': ['_observation', '_update_evidence_obligations', '_current_obligation_feedback',
                                '_offer_frozen_reviews', '_wire_data', '_system', '_schema'],
    'state_and_obligations_unchanged': True,
    'generation_calls': 0,
}
if '--tokenize' not in sys.argv:
    print(json.dumps({**report, 'new_network_tokenization_calls': 0}, indent=2))
    sys.exit(0)

output = REPORTS / 'r14_obligation_repair_tokenization.json'
assert not output.exists(), 'Refusing to overwrite an existing report'
token_events = []
counter = DeploymentTokenCounter(config, token_events.append)
count = counter.count(new_wire)
assert count['token_count_is_estimate'] is False
total = count['count'] + settings['reasoning_output_tokens'] + settings['input_margin'] + 8
report.update({
    'new_repair_input_tokens': count['count'],
    'output_token_reserve': settings['reasoning_output_tokens'],
    'input_margin': settings['input_margin'], 'safety_margin': 8,
    'new_repair_total_tokens': total,
    'context_tokens': settings['context_tokens'],
    'fits_actual_repair_context': total <= settings['context_tokens'],
    'remaining_context_tokens': settings['context_tokens'] - total,
    'new_input_token_delta': count['count'] - saved[old_wire_hash]['count'],
    'new_tokenization_count_calls': len(token_events),
    'tokenizer_http_attempts': sum(item.get('http_attempts', 0) for item in token_events),
    'tokenizer_successful_http_requests': sum(item.get('successful_http_requests', 0) for item in token_events),
    'tokenizer_cache_hits': sum(bool(item.get('cache_hit')) for item in token_events),
    'interpretation': 'Exact capacity evidence for the archived failed window with the current new repair fields. This does not predict generation, semantic success, different earlier prefix choices, or full smoke completion.',
})
with output.open('x') as handle:
    handle.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
