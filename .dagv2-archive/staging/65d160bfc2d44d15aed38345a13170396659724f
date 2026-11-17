"""Measure an external codec on archived wires; never generates or edits a run."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

import prototype_shared_history_text as codec


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--run', default='outputs/v4_validation_r16')
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--tokenize', action='store_true')
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError('receipt already exists')
    sys.path.insert(0, str(args.root))
    from dagbt.joint_reading import JointReader
    from dagbt.token_counting import DeploymentTokenCounter, _digest

    run = args.root / args.run
    manifest_path = run / 'manifest.json'
    manifest_hash = sha(manifest_path.read_bytes())
    manifest = json.loads(manifest_path.read_text())
    config = deepcopy(manifest['config'])
    if config.get('credentials_file') and not Path(config['credentials_file']).is_absolute():
        config['credentials_file'] = str(args.root / config['credentials_file'])
    assert config['fusion'].get('response_format', 'plain') == 'plain'
    ids = manifest['question_ids']['personamem']
    cases = {sha(json.dumps(u, ensure_ascii=False, sort_keys=True).encode()): i+1
             for i, u in enumerate(ids)}
    watched = [Path(codec.__file__), Path(__file__),
               args.root / 'dagbt/joint_reading.py',
               args.root / 'dagbt/reasoning.py',
               args.root / 'dagbt/token_counting.py']
    hashes = {str(p): sha(p.read_bytes()) for p in watched}
    events = []
    counter = DeploymentTokenCounter(config, events.append) if args.tokenize else None
    marker = '\n\nReturn one complete JSON object matching this schema:\n'
    operations = {'joint_read', 'joint_read_repair', 'semantic_compose',
                  'semantic_compose_repair', 'audit_joint', 'audit_joint_repair'}
    rows = []
    requests_checked = 0
    for attempt in sorted((run / 'personamem/dagbt_residual_memory_v2/attempts').glob('*/attempt-001')):
        saved = {}
        journal = attempt / 'tokenization_events.jsonl'
        if journal.is_file():
            for line in journal.read_text().splitlines(keepends=True):
                if not line.endswith('\n'):
                    continue
                event = json.loads(line)
                if event.get('status') == 'ok':
                    saved[event['tokenization_wire_sha256']] = event
        for path in sorted((attempt / 'requests').glob('*.json')):
            record = json.loads(path.read_text())
            stage = record.get('stage')
            if not isinstance(stage, list) or stage[0] not in operations:
                continue
            payload = record['payload']
            assert set(m['role'] for m in payload['messages']) == {'system', 'user'}
            assert len(payload['messages']) == 2
            user = next(m for m in payload['messages'] if m['role'] == 'user')
            system = next(m for m in payload['messages'] if m['role'] == 'system')
            data = json.loads(user['content'])
            before = canonical(data)
            candidate = codec.pack(data)
            requests_checked += 1
            assert canonical(data) == before
            applied = 'shared_history_texts' in candidate and 'shared_history_texts' not in data
            if not applied:
                assert canonical(candidate) == before
                continue
            assert canonical(codec.unpack(candidate)) == canonical(codec.normalize_known_table(data))
            expected_system = JointReader._system(data)
            assert system['content'].startswith(expected_system + marker), 'saved system differs from current source'
            schema_tail = system['content'][len(expected_system):]
            json.loads(schema_tail[len(marker):])
            changed = deepcopy(payload)
            for message in changed['messages']:
                if message['role'] == 'user':
                    message['content'] = json.dumps(candidate, ensure_ascii=False,
                        allow_nan=False, separators=(',', ':'))
                else:
                    message['content'] = JointReader._system(candidate) + codec.INSTRUCTION + schema_tail
            old_hash = _digest(payload)
            observed = saved[old_hash]
            assert observed['token_count_is_estimate'] is False
            row = {'case_one_based': cases[attempt.parent.name], 'stage': stage,
                'original_wire_sha256': old_hash, 'candidate_wire_sha256': _digest(changed),
                'saved_original_input_tokens': observed['count'], 'exact_structural_roundtrip': True,
                'output_schema_unchanged': True, 'generation_parameters_unchanged': True,
                'original_request_sha256': sha(path.read_bytes()),
                'net_messages_utf8_bytes_reduced': sum(len(m['content'].encode()) for m in payload['messages'])
                    - sum(len(m['content'].encode()) for m in changed['messages'])}
            if counter is not None:
                original_count = counter.count(payload)
                assert original_count['count'] == observed['count'], 'server count changed since saved run'
                candidate_count = counter.count(changed)
                row.update(original_count=original_count, candidate_count=candidate_count,
                    input_tokens_reduced=original_count['count'] - candidate_count['count'])
            rows.append(row)
    assert sha(manifest_path.read_bytes()) == manifest_hash
    assert all(sha(Path(p).read_bytes()) == h for p, h in hashes.items())
    result = {'schema': 'external_shared_history_text_wire_measurement_v1',
        'run': str(run), 'manifest_sha256': manifest_hash, 'source_sha256': hashes,
        'scope': 'Archived actual completed request wires only; candidate is unintegrated. '
                 'Counts do not prove rejected handoff fits, future trajectory, output comprehension or accuracy.',
        'requests_checked': requests_checked, 'applied_requests': len(rows),
        'labels_read': False, 'generation_calls': 0,
        'tokenizer_http_attempts': sum(e.get('http_attempts', 0) for e in events),
        'tokenizer_count_calls': len(events), 'release_ready': False,
        'requests': rows, 'tokenization_events': events}
    args.receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    savings = [r['input_tokens_reduced'] for r in rows if 'input_tokens_reduced' in r]
    print(json.dumps({'receipt': str(args.receipt), 'requests_checked': requests_checked,
        'applied_requests': len(rows), 'minimum_input_tokens_reduced': min(savings, default=None),
        'maximum_input_tokens_reduced': max(savings, default=None),
        'tokenizer_http_attempts': result['tokenizer_http_attempts'], 'generation_calls': 0}))


if __name__ == '__main__':
    main()
