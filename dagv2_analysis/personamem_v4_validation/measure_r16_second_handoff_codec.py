"""Read-only deployment counting of two independently reconstructed wires."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

import prototype_shared_history_text as codec


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reconstruction', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError('Receipt already exists')
    sys.path.insert(0, str(args.root))
    from dagbt.joint_reading import JointReader
    from dagbt.token_counting import DeploymentTokenCounter, _digest

    reconstruction = json.loads(args.reconstruction.read_text())
    assert all(sha(Path(path)) == h for path, h in reconstruction['artifact_sha256'].items())
    config = json.loads((args.root / 'outputs/v4_validation_r16/manifest.json').read_text())['config']
    if config.get('credentials_file') and not Path(config['credentials_file']).is_absolute():
        config['credentials_file'] = str(args.root / config['credentials_file'])
    watched = [args.reconstruction, Path(codec.__file__), Path(__file__)]
    hashes = {str(p): sha(p) for p in watched}
    events = []
    counter = DeploymentTokenCounter(config, events.append)
    marker = '\n\nReturn one complete JSON object matching this schema:\n'
    rows = []
    for comparison in reconstruction['comparisons']:
        operation = comparison['operation']
        wire = reconstruction['wires'][operation]
        assert _digest(wire) == comparison['saved_hash'] == comparison['reconstructed_hash']
        data = json.loads(wire['messages'][1]['content'])
        candidate = codec.pack(data)
        assert 'shared_history_texts' in candidate and 'shared_history_texts' not in data
        assert canonical(codec.unpack(candidate)) == canonical(codec.normalize_known_table(data))
        expected_system = JointReader._system(data)
        assert wire['messages'][0]['content'].startswith(expected_system + marker)
        tail = wire['messages'][0]['content'][len(expected_system):]
        json.loads(tail[len(marker):])
        changed = deepcopy(wire)
        changed['messages'][0]['content'] = JointReader._system(candidate) + codec.INSTRUCTION + tail
        changed['messages'][1]['content'] = json.dumps(candidate, ensure_ascii=False,
            allow_nan=False, separators=(',', ':'))
        old_count = counter.count(wire)
        assert old_count['count'] == comparison['saved_input_tokens']
        new_count = counter.count(changed)
        reserve = wire['max_tokens'] + config['fusion']['input_margin'] + 8
        rows.append({'operation': operation, 'original_wire_sha256': _digest(wire),
            'candidate_wire_sha256': _digest(changed), 'original_count': old_count,
            'candidate_count': new_count, 'input_tokens_reduced': old_count['count']-new_count['count'],
            'unchanged_output_margin_safety': reserve,
            'original_total': old_count['count']+reserve,
            'candidate_total': new_count['count']+reserve,
            'exact_typed_roundtrip': True, 'schema_and_generation_parameters_unchanged': True})
    assert all(sha(Path(path)) == h for path, h in hashes.items())
    context = config['fusion']['context_tokens']
    candidate_total = max(r['candidate_total'] for r in rows)
    result = {'schema': 'external_shared_history_text_handoff_count_v1',
        'source_sha256': hashes, 'reconstruction_inputs_rechecked': True,
        'scope': 'Counterfactual representation of exact archived 39-source mandatory handoff; '
                 'not production integration, generated answer or a recovered task.',
        'labels_read': False, 'generation_calls': 0,
        'context_limit_unchanged': context, 'candidate_fits_ordinary_admission': candidate_total <= context,
        'candidate_headroom_tokens': context-candidate_total,
        'requests': rows, 'tokenization_events': events,
        'tokenizer_http_attempts': sum(e.get('http_attempts', 0) for e in events), 'release_ready': False}
    args.receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'receipt': str(args.receipt),
        'requests': [{k:r[k] for k in ('operation','input_tokens_reduced','original_total','candidate_total')}
                     for r in rows], 'candidate_fits_ordinary_admission': candidate_total <= context,
        'candidate_headroom_tokens': context-candidate_total, 'generation_calls': 0}))


if __name__ == '__main__':
    main()
