"""Check a new input codec against saved requests without calling any service.

This measures JSON/UTF-8 bytes, never tokens, admissibility, or answer quality.
The saved run and all production inputs remain unchanged.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Choose a new receipt path')
    def guard(event, values):
        if event in ('socket.connect', 'socket.sendto', 'socket.getaddrinfo'):
            raise RuntimeError('Network is forbidden during saved-wire replay')
        if event == 'open' and isinstance(values[0], (str, bytes)):
            name = Path(values[0].decode() if isinstance(values[0], bytes) else values[0]).name
            if name == 'evaluation_only.json' or name == 'summary.json' or name.endswith('.local.json'):
                raise RuntimeError('Labels, scores and credentials are outside this replay')
    sys.addaudithook(guard)
    module_path = args.source_root.resolve() / 'dagbt/review_wire.py'
    source_before = module_path.read_bytes()
    spec = importlib.util.spec_from_file_location('_review_wire_replay', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for path in sorted((args.attempt / 'requests').glob('*.json')):
        original_record = path.read_bytes()
        record = json.loads(original_record)
        messages = record.get('payload', {}).get('messages', [])
        if (len(messages) != 2 or messages[0].get('role') != 'system'
                or messages[1].get('role') != 'user'):
            continue
        try:
            original = json.loads(messages[1]['content'])
        except (TypeError, ValueError):
            continue
        if not isinstance(original, dict) or 'source_spans' not in original:
            continue
        before = encoded(original)
        packed, applied = module.pack_with_status(original)
        after = encoded(packed)
        assert encoded(original) == before, 'Input mutation'
        if applied:
            assert encoded(module.unpack(packed)) == before, 'Exact ordered inverse failed'
            assert len(after) + len(module.INSTRUCTION.encode('utf-8')) < len(before)
        else:
            assert after == before, 'Fallback changed the wire'
        assert path.read_bytes() == original_record, 'Saved request mutated'
        rows.append({
            'request_file': path.name,
            'request_file_sha256': hashlib.sha256(original_record).hexdigest(),
            'applied': applied,
            'ordered_type_sensitive_roundtrip': True,
            'old_user_json_bytes': len(before),
            'new_user_json_bytes': len(after),
            'additional_instruction_bytes': len(module.INSTRUCTION.encode('utf-8')) if applied else 0,
            'net_json_and_instruction_byte_reduction': len(before) - len(after)
                - (len(module.INSTRUCTION.encode('utf-8')) if applied else 0),
            'old_user_json_sha256': hashlib.sha256(before).hexdigest(),
            'new_user_json_sha256': hashlib.sha256(after).hexdigest(),
        })
    assert rows, 'No actual saved Reader request inspected'
    assert module_path.read_bytes() == source_before, 'Codec changed during replay'
    result = {
        'scope': 'Saved input-wire representation only; not a token count or model execution',
        'codec_sha256': hashlib.sha256(source_before).hexdigest(),
        'source_root': str(args.source_root.resolve()),
        'attempt': str(args.attempt.resolve()),
        'requests_inspected': len(rows),
        'requests_encoded': sum(row['applied'] for row in rows),
        'labels_or_scores_read': False,
        'network_calls': 0,
        'source_or_run_mutated': False,
        'token_savings_measured': False,
        'case_success_established': False,
        'requests': rows,
    }
    with args.output.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'requests'}, indent=2))


if __name__ == '__main__':
    main()
