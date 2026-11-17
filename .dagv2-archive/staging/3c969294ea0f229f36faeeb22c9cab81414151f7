"""Offline comparison of production preparation with previously counted wires."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--reconstruction', type=Path, required=True)
    parser.add_argument('--counts', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError('Receipt already exists')
    sys.path.insert(0, str(args.root))
    from dagbt.config import DEFAULTS
    from dagbt.joint_reading import JointReader
    from dagbt.model_runtime import prepare_request
    from dagbt.reasoning import Reasoner
    from dagbt.token_counting import _digest

    old = json.loads(args.reconstruction.read_text())
    measured = json.loads(args.counts.read_text())
    config = json.loads((args.release / 'outputs/v4_validation_r16/manifest.json').read_text())['config']
    settings = {**deepcopy(DEFAULTS), **deepcopy(config['fusion']),
                'algorithm_version': 'dagbt_residual_memory_v2'}
    reasoner = Reasoner(None, None, config, settings, None, lambda event: None)
    reader = object.__new__(JointReader)
    watched = [args.root / 'dagbt' / name for name in
               ('history_wire.py','joint_reading.py','reasoning.py','model_runtime.py')]
    watched += [args.reconstruction, args.counts, Path(__file__)]
    hashes = {str(p):sha(p) for p in watched}
    rows = []
    for previous in measured['requests']:
        operation = previous['operation']
        wire = old['wires'][operation]
        assert _digest(wire) == previous['original_wire_sha256']
        data = json.loads(wire['messages'][1]['content'])
        # Independent inverse of the two old source encodings. The measured
        # fixture has five ordinary known rows, so no known-table decoder here.
        assert 'known_observation_columns' not in data
        columns = data.pop('source_span_columns', None)
        if columns is not None:
            assert all(len(row) == len(columns) for row in data['source_spans'])
            data['source_spans'] = [dict(zip(columns, row)) for row in data['source_spans']]
        documents = data.pop('source_documents', None)
        if documents is not None:
            for source in data['source_spans']:
                source.update(deepcopy(documents[source['doc_id']]))
        canonical_before = deepcopy(data)
        old_packed = reader._wire_data(data)
        old_request = reasoner._payload(operation, reader._system(old_packed), old_packed,
                                        reader._schema(data))
        _, old_prepared, _ = prepare_request((operation, '13'), reasoner.url, old_request, config)
        assert _digest(old_prepared) == previous['original_wire_sha256'], 'old production wire not reconstructed'
        packed, system = reader._prepare_wire(data)
        request = reasoner._payload(operation, system, packed, reader._schema(data))
        _, prepared, _ = prepare_request((operation, '13'), reasoner.url, request, config)
        assert _digest(prepared) == previous['candidate_wire_sha256'], 'integrated wire differs from measured prototype'
        assert data == canonical_before
        rows.append({'operation': operation, 'original_wire_sha256': _digest(old_prepared),
            'candidate_wire_sha256': _digest(prepared), 'matches_measured_wire': True,
            'canonical_data_unchanged': True, 'previously_measured_candidate_total': previous['candidate_total']})
    assert all(sha(Path(p)) == h for p,h in hashes.items())
    result = {'schema': 'integrated_shared_text_archived_wire_verification_v1',
        'source_sha256': hashes, 'requests': rows, 'network_calls': 0, 'generation_calls': 0,
        'labels_read': False, 'production_model_validation': False, 'release_ready': False,
        'scope': 'Uncommitted reconcile preparation matches the two exact previously counted candidate wires. '
                 'Only representation/admission evidence; no complete task or model comprehension claim.'}
    args.receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'receipt': str(args.receipt), 'requests_matched': len(rows),
                      'network_calls': 0, 'generation_calls': 0}))


if __name__ == '__main__':
    main()
