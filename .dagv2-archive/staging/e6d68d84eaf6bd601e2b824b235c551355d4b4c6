"""Read actual saved review-wire requests; no services, labels, or text export."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path('/Users/mao/projects/dagv2-personamem-v4')
RUN = ROOT / 'outputs/v4_validation_r20'
OUT = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r20_review_wire_review.json')
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from dagbt.review_wire import INSTRUCTION, POOL, REF_FIELDS, _rows, pack_with_status, unpack
from dagbt.history_wire import unpack as unpack_history


def serialized(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


records = []
for path in (RUN / 'personamem/dagbt_residual_memory_v2/attempts').glob('*/attempt-*/requests/*.json'):
    request = load(path)
    if not request:
        continue
    try:
        messages = request['payload']['messages']
        data = json.loads(messages[1]['content'])
    except (ValueError, KeyError, TypeError, IndexError):
        continue
    if not isinstance(data, dict) or POOL not in data:
        continue
    row = {'request_file': str(path.relative_to(RUN)), 'stage': request.get('stage'),
           'pool_literal_count': len(data[POOL]), 'has_response': 'response' in request,
           'decode_instruction_present': INSTRUCTION in messages[0]['content']}
    try:
        decoded = unpack(data)
        combined = unpack_history(decoded)
        before_rows, after_rows = list(_rows(data)), list(_rows(decoded))
        before_shape = [{k: v for k, v in item.items() if k not in set(fields) | set(REF_FIELDS.values())}
                        for item, fields in before_rows]
        after_shape = [{k: v for k, v in item.items() if k not in fields} for item, fields in after_rows]
        repacked, applied = pack_with_status(decoded)
        keys = ('source_spans', 'source_documents', 'requested_scopes', 'request_context',
                'variables', 'output_contract', 'known_observation_columns', 'known_observation_values',
                'invalid_response')
        row.update(decode_succeeded=True,
                   reference_count=sum(ref in item for item, _ in before_rows for ref in REF_FIELDS.values()),
                   registered_row_metadata_unchanged=before_shape == after_shape,
                   external_scope_contract_source_fields_unchanged=all(data.get(key) == decoded.get(key) for key in keys),
                   deterministic_repack_applied=applied,
                   deterministic_repack_bytes_match=serialized(repacked) == serialized(data),
                   decoded_combined_data_sha256=hashlib.sha256(serialized(combined)).hexdigest(),
                   encoded_bytes=len(serialized(data)), decoded_review_bytes=len(serialized(decoded)))
    except Exception as exc:
        row.update(decode_succeeded=False, decode_error_type=type(exc).__name__)
    records.append(row)
records.sort(key=lambda row: row['request_file'])
report = {'run': RUN.name, 'source_commit': '6c046374008ce2e45f817d6bc9876b3ab927ab18',
          'scope': 'Actual saved review codec requests, safe counts/hash/metadata only. Decoding and deterministic repacking do not independently prove equality to an unavailable pre-encoding runtime object or model comprehension. No labels/scores/services/run mutation.',
          'requests': records}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'review_wire_request_count': len(records),
                  'decode_failures': sum(not row['decode_succeeded'] for row in records),
                  'missing_decode_instruction': sum(not row['decode_instruction_present'] for row in records),
                  'structure_mismatches': sum(row.get('decode_succeeded') and not all(row.get(key) for key in
                      ('registered_row_metadata_unchanged', 'external_scope_contract_source_fields_unchanged',
                       'deterministic_repack_applied', 'deterministic_repack_bytes_match')) for row in records)},
                 ensure_ascii=False))
