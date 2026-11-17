"""Offline saved-wire schema-expression replay; never changes a run or calls services."""
import hashlib
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path('/Users/mao/projects/dagv2-personamem-v4-reconcile')
RELEASE = Path('/Users/mao/projects/dagv2-personamem-v4')
RUN = RELEASE / 'outputs/v4_validation_r20'
BASE = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
EXPECTED_JOINT = '263972a81e76672b313b5a68b580887599310be0ce77eaec404ea88dede23a5a'
OUT = BASE / 'r20_case04_frozen_schema_replay.json'
assert not OUT.exists(), 'Preserve existing replay evidence'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert file_hash(ROOT / 'dagbt/joint_reading.py') == EXPECTED_JOINT
release_manifest = json.loads((RUN / 'manifest.json').read_text())
release_joint_hash = release_manifest['source_hashes']['dagbt/joint_reading.py']
assert file_hash(RELEASE / 'dagbt/joint_reading.py') == release_joint_hash
sys.path.insert(0, str(ROOT))
from dagbt.joint_reading import JointReader
from dagbt.history_wire import unpack as unpack_history
from dagbt.review_wire import unpack as unpack_review
from jsonschema import Draft202012Validator

prior = json.loads((BASE / 'r20_case04_reader_failure_review.json').read_text())
unit = prior['unit_id']
canonical_path = next(path for path in (RUN / 'personamem/dagbt_residual_memory_v2/rows').glob('*.json')
                      if json.loads(path.read_text())['unit_id'] == unit)
canonical = json.loads(canonical_path.read_text())
retained = canonical['diagnostics']['joint_reading']['failed_batch_reviews']
validated = [row for record in retained if record['variable'] == 'response'
             for row in record.get('validated_observations', []) if row['variable'] == 'response']
assert len(validated) == 1
assert validated[0]['stance'] == 'unknown' and validated[0]['value'] is None
frozen_ids = {'response': sorted({row['id'] for row in validated})}


def canonical_data(wire):
    data = unpack_history(unpack_review(wire))
    if 'source_span_columns' in data:
        columns = data.pop('source_span_columns')
        data['source_spans'] = [dict(zip(columns, row)) for row in data['source_spans']]
    documents = data.pop('source_documents', {})
    for span in data.get('source_spans', []):
        alias = span.get('doc_id')
        if alias in documents:
            span.update(deepcopy(documents[alias]))
    return data


def leaves(error):
    if not error.context:
        return [error]
    return [leaf for child in error.context for leaf in leaves(child)]


def changes(old, new, prefix=()):
    if type(old) is not type(new):
        return [list(prefix)]
    if isinstance(old, dict):
        return [item for key in sorted(set(old) | set(new)) for item in
                ([list(prefix + (key,))] if key not in old or key not in new else
                 changes(old[key], new[key], prefix + (key,)))]
    if isinstance(old, list) and len(old) == len(new):
        return [item for index, (left, right) in enumerate(zip(old, new))
                for item in changes(left, right, prefix + (index,))]
    return [] if old == new else [list(prefix)]


records = []
for call in ('9', '10', '11'):
    rec = next(row for row in prior['requests'] if row['stage'][1] == call)
    path = RUN / rec['file']
    saved = json.loads(path.read_text())
    messages = saved['payload']['messages']
    wire = json.loads(messages[1]['content'])
    data = canonical_data(wire)
    original_data_digest = digest(data)
    response = json.loads(saved['response']['choices'][0]['message']['content'])
    old_schema = json.loads(messages[0]['content'].rsplit(
        'Return one complete JSON object matching this schema:\n', 1)[1])
    baseline_schema = JointReader._schema(data)
    assert baseline_schema == old_schema, 'Uninjected schema differs from actual saved schema'
    assert Draft202012Validator(old_schema).is_valid(response)
    new_data = deepcopy(data)
    if call == '9':
        assert 'frozen_observation_ids' not in new_data.get('repair_scope', {})
        row = next(o for slot in response['slots'] if slot['variable'] == 'response'
                   for o in slot['observations'])
        assert row['id'] == validated[0]['id'] and row['stance'] == 'unknown' and row['value'] is None
    else:
        assert 'repair_scope' in new_data and 'frozen_observation_ids' not in new_data['repair_scope']
        new_data['repair_scope']['frozen_observation_ids'] = deepcopy(frozen_ids)
    new_schema = JointReader._schema(new_data)
    errors = list(Draft202012Validator(new_schema).iter_errors(response))
    terminal_leaves = [leaf for error in errors for leaf in leaves(error)]
    forbidden_id_errors = [error for error in terminal_leaves if error.validator == 'not'
                           and list(error.absolute_path)[-1:] == ['id']]
    other_errors = [error for error in terminal_leaves if error not in forbidden_id_errors]
    if call == '9':
        assert not errors and new_schema == old_schema
    else:
        assert len(forbidden_id_errors) == 1 and not other_errors
    assert digest(data) == original_data_digest
    records.append({
        'stage': rec['stage'], 'request_file': rec['file'], 'request_sha256': file_hash(path),
        'actual_saved_schema_sha256': digest(old_schema), 'new_schema_sha256': digest(new_schema),
        'decoded_input_sha256': original_data_digest, 'source_span_count': len(data['source_spans']),
        'source_original_metadata_reconstructed': all('time_metadata' in item for item in data['source_spans']),
        'history_wire_decoded': 'shared_history_texts' in wire,
        'known_observation_rows_reconstructed': all(isinstance(item, dict) for item in data['known_observations']),
        'uninjected_new_schema_equals_saved_schema': baseline_schema == old_schema,
        'old_saved_response_schema_valid': True,
        'injected_frozen_ids': frozen_ids if call != '9' else {},
        'new_saved_response_schema_valid': not errors,
        'schema_difference_paths': changes(old_schema, new_schema),
        'forbidden_id_error_count': len(forbidden_id_errors), 'other_leaf_error_count': len(other_errors),
        'error_paths': [{'path': list(error.absolute_path), 'schema_path': list(error.absolute_schema_path),
                         'validator': error.validator} for error in terminal_leaves],
        'review_reference_permission_unchanged': old_schema['properties']['slots']['items']['properties'].get(
            'reviewed_observation_ids') == new_schema['properties']['slots']['items']['properties'].get(
            'reviewed_observation_ids'),
    })

assert file_hash(ROOT / 'dagbt/joint_reading.py') == EXPECTED_JOINT
assert file_hash(RELEASE / 'dagbt/joint_reading.py') == release_joint_hash
report = {
    'created_utc': datetime.now(timezone.utc).isoformat(), 'run': RUN.name, 'question_index': 4,
    'unit_id': unit, 'candidate_joint_reading_sha256': EXPECTED_JOINT,
    'frozen_release_commit': '6c046374008ce2e45f817d6bc9876b3ab927ab18',
    'canonical_row_file': str(canonical_path.relative_to(RUN)), 'canonical_row_sha256': file_hash(canonical_path),
    'current_batch_frozen_basis': {'retained_failed_batch_ids': [row['id'] for row in retained],
        'normalized_validated_row_count': len(validated), 'normalized_validated_row_hash': digest(validated[0]),
        'stance': 'unknown', 'value_is_null': True, 'source_count': len(validated[0]['source_ids']),
        'matching_actual_call9_response_id': True,
        'note': 'Call9 is a new batch with empty F. Its normalized unknown row is retained as validated evidence; F applies to subsequent scoped repairs10/11. Old known routes do not confer cross-batch freeze.'},
    'requests': records, 'passed': True, 'labels_read': False, 'scores_read': False,
    'services_called': False, 'source_or_run_modified': False,
    'scope': 'Offline schema-expression consistency only. Injected F comes from the actual saved normalized validated row; this is not a model rerun, runtime control-flow replay, proof of obligation discharge, or success/accuracy evidence.'
}
with OUT.open('x') as handle:
    json.dump(report, handle, ensure_ascii=False, indent=2)
    handle.write('\n')
print(json.dumps({'artifact': str(OUT), 'sha256': file_hash(OUT), 'passed': True,
                  'calls': [{key: row[key] for key in ('stage', 'new_saved_response_schema_valid',
                      'forbidden_id_error_count', 'other_leaf_error_count',
                      'uninjected_new_schema_equals_saved_schema')} for row in records]}))
