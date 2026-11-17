"""Fixed first two PersonaMem questions, production worker, no evaluation labels."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path('/Users/mao/projects/dagv2-personamem-a48')
sys.path.insert(0, str(ROOT))
from dagbt import runner
from dagbt.methods import RESIDUAL
from dagbt.resources import inspect_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/residual-memory.example.json')
    args = parser.parse_args()
    os.chdir(ROOT)
    config = runner.validate_config(runner.load(args.config))
    os.environ['NO_PROXY'] = os.environ['no_proxy'] = '111.19.156.30,111.19.156.74'
    output = args.output.resolve()
    questions = runner.load_questions('personamem', 2)
    manifest = {'kind': 'fixed_two_personamem_patch_validation', 'datasets': ['personamem'],
        'arms': ['original', RESIDUAL], 'config': config, 'labels_read': False,
        'question_ids': {'personamem': [q['id'] for q in questions]},
        'questions_digest': runner.digest(questions), 'source_hashes': runner.frozen_sources(),
        'question_attempts': 1}
    with runner.writer_lock(output):
        if (output / 'manifest.json').exists():
            raise ValueError('Use a new validation directory')
        runner.save(output / 'manifest.json', manifest)
        runner.save(output / 'original_integrity.json', runner.verify_originals())
        index = inspect_index(config, 'personamem')
        if index['status'] != 'ready':
            raise ValueError('Compatible complete index required; no implicit rebuild')
        runner.save(output / 'index_artifacts.json', {'personamem': index})
        counts = runner.generate_dataset(output, 'personamem', questions, manifest['arms'], config)
        report = {'counts': counts, 'labels_read': False, 'question_attempts': 1,
            'source_hashes': manifest['source_hashes']}
        runner.save(output / 'smoke_summary.json', report)
        runner.save(output / 'progress.json', {'state': 'validation_finished', 'updated_unix': time.time()})
        print(json.dumps({'counts': counts, 'labels_read': False}), flush=True)


if __name__ == '__main__':
    main()
