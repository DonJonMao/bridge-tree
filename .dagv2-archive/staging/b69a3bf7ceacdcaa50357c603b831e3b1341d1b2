"""Zero-service structural/byte probe of the external, unintegrated codec."""
import argparse
import hashlib
import json
from pathlib import Path
import prototype_shared_history_text as codec


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(',', ':'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run', default='outputs/v4_validation_r16')
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError('receipt already exists')
    prototype = Path(codec.__file__)
    code_hash = sha(prototype.read_bytes())
    out = args.root / args.run
    manifest = json.loads((out / 'manifest.json').read_text())
    ids = manifest['question_ids']['personamem']
    case_by_digest = {sha(json.dumps(u, ensure_ascii=False, sort_keys=True).encode()): i + 1
                      for i, u in enumerate(ids)}
    operations = {'joint_read', 'joint_read_repair', 'semantic_compose',
                  'semantic_compose_repair', 'audit_joint', 'audit_joint_repair'}
    receipts = []
    for path in sorted((out / 'personamem/dagbt_residual_memory_v2/attempts').glob(
            '*/attempt-001/fusion_events.jsonl')):
        case = case_by_digest[path.parent.parent.name]
        with path.open() as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    if not line.endswith('\n'):
                        continue
                    raise
                if event.get('event') != 'reasoning_response' or event.get('operation') not in operations:
                    continue
                message = next((m for m in event.get('messages', []) if m.get('role') == 'user'), None)
                if message is None:
                    continue
                data = json.loads(message['content'])
                original = canonical(data)
                candidate = codec.pack(data)
                assert canonical(data) == original, 'input changed'
                applied = 'shared_history_texts' in candidate and 'shared_history_texts' not in data
                exact = (canonical(codec.unpack(candidate)) == canonical(codec.normalize_known_table(data))
                         if applied else canonical(candidate) == original)
                assert exact, 'roundtrip failed'
                old, new = codec.byte_size(data), codec.byte_size(candidate)
                instruction = len(codec.INSTRUCTION.encode()) if applied else 0
                receipts.append({'case_one_based': case, 'operation': event['operation'],
                    'logical_call_index': event.get('logical_call_index'), 'applied': applied,
                    'input_unchanged': True, 'exact_roundtrip': exact,
                    'original_user_json_bytes': old, 'candidate_user_json_bytes': new,
                    'additional_instruction_bytes': instruction,
                    'net_serialized_bytes_reduced': old - new - instruction,
                    'original_user_text_matches_serialized_byte_size': len(message['content'].encode()) == old,
                    'original_user_sha256': sha(message['content'].encode())})
    assert sha(prototype.read_bytes()) == code_hash, 'prototype changed during probe'
    result = {'schema': 'unintegrated_shared_history_text_archived_probe_v1',
        'run': str(out), 'manifest_sha256': sha((out / 'manifest.json').read_bytes()),
        'prototype_sha256': code_hash, 'probe_sha256': sha(Path(__file__).read_bytes()),
        'labels_read': False, 'services_called': 0, 'token_savings_measured': False,
        'release_ready': False,
        'scope': 'Saved input structural roundtrips and UTF-8 sizes only; no candidate model request was sent.',
        'requests': receipts}
    args.receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    applied = [r for r in receipts if r['applied']]
    print(json.dumps({'receipt': str(args.receipt), 'prototype_sha256': code_hash,
        'requests_checked': len(receipts), 'applied': len(applied),
        'all_exact_roundtrip': all(r['exact_roundtrip'] for r in receipts),
        'maximum_byte_reduction': max((r['net_serialized_bytes_reduced'] for r in applied), default=0),
        'services_called': 0, 'token_savings_measured': False}))


if __name__ == '__main__':
    main()
