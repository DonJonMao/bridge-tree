"""Read actual saved shared-history requests; never call a service or print text."""
import hashlib
import json
import sys
from pathlib import Path

RELEASE = Path('/Users/mao/projects/dagv2-personamem-v4')
RUN = RELEASE / 'outputs/v4_validation_r17'
OUT = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r17_history_wire_review.json')
sys.dont_write_bytecode = True
sys.path.insert(0, str(RELEASE))
from dagbt.history_wire import INSTRUCTION, normalize_known_table, unpack


def load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


prior = load(OUT) or {}
seen = {row['request_file'] for row in prior.get('requests', [])}
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
    if not isinstance(data, dict) or 'shared_history_texts' not in data:
        continue
    row = {'request_file': str(path.relative_to(RUN)), 'stage': request.get('stage'),
           'shared_text_count': len(data['shared_history_texts']),
           'has_response': 'response' in request,
           'decode_instruction_present': INSTRUCTION in messages[0]['content']}
    try:
        normalized = normalize_known_table(data)
        decoded = unpack(data)
        before = list(normalized.get('supported_parents', {}).values()) + normalized.get('known_observations', [])
        after = list(decoded.get('supported_parents', {}).values()) + decoded.get('known_observations', [])
        row.update({'decode_succeeded': True,
                    'value_reference_count': sum('value_ref' in item for item in before),
                    'query_reference_count': sum(isinstance(item, dict) for item in data.get('grounded_subquestion_parts', [])),
                    'source_spans_unchanged': decoded.get('source_spans') == data.get('source_spans'),
                    'nonvalue_row_fields_unchanged': len(before) == len(after) and all(
                        {k: v for k, v in old.items() if k not in ('value', 'value_ref')}
                        == {k: v for k, v in new.items() if k != 'value'}
                        for old, new in zip(before, after)),
                    'scope_and_contract_unchanged': all(data.get(key) == decoded.get(key) for key in
                        ('requested_scopes', 'request_context', 'variables', 'output_contract', 'repair_scope')),
                    'decoded_data_hash': digest(decoded)})
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        row.update({'decode_succeeded': False, 'decode_error_type': type(exc).__name__})
    records.append(row)
records.sort(key=lambda row: row['request_file'])
report = {'run': 'v4_validation_r17', 'source_commit': 'bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94',
          'scope': 'Read-only saved request decoding with the frozen release codec. Counts and hashes only; no labels, text export, model generation or network tokenization.',
          'requests': records}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'shared_history_request_count': len(records),
                  'decode_failures': sum(not row['decode_succeeded'] for row in records),
                  'missing_decode_instruction': sum(not row['decode_instruction_present'] for row in records),
                  'structure_mismatches': sum(row.get('decode_succeeded') and not all(row.get(key) for key in
                      ('source_spans_unchanged', 'nonvalue_row_fields_unchanged', 'scope_and_contract_unchanged')) for row in records),
                  'new_requests': [row for row in records if row['request_file'] not in seen]}, ensure_ascii=False))
