#!/usr/bin/env python3
"""Pin a new two-question local repair iteration, preserving previous runs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


STAGE = Path(__file__).resolve().parent
WORK = Path('/Users/mao/projects/dagv2-webwalker-v4')
CORE = 'e6677081cdfb33c01db3aaa274a497168f314f78'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=WORK)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--base-trial', default='candidate_occurrence_feedback')
    parser.add_argument('--fix', action='append', default=[])
    args = parser.parse_args()
    assert args.name and all(c.isalnum() or c in '_-' for c in args.name)
    base_trial = STAGE / args.base_trial
    declaration = json.loads((base_trial / 'declaration.json').read_text())
    previous_state = json.loads((base_trial / 'state.json').read_text()) if (base_trial / 'state.json').exists() else {}
    base_source = Path(declaration['source_root'])
    paths = git('ls-tree', '-r', '--name-only', CORE).decode().splitlines()
    core_paths = [p for p in paths if p.endswith('.py')
                  and p.split('/')[0] in ('dagbt', 'dagv2', 'dagresolve', 'package', 'vendor')]
    for name in core_paths:
        assert (WORK / name).read_bytes() == git('show', CORE + ':' + name), name
    assert (WORK / 'configs/webwalker-v4.json').read_bytes() == git('show', 'HEAD:configs/webwalker-v4.json')
    tracked = git('diff', '--name-only').decode().splitlines()
    untracked = git('ls-files', '--others', '--exclude-standard').decode().splitlines()
    changes = sorted({name for name in tracked + untracked
                      if name.endswith('.py') and
                      (name.startswith('dagbt/webwalker_') or name.startswith('tests/test_webwalker'))})
    assert changes
    trial = STAGE / args.name
    trial.mkdir(exist_ok=False)
    source = trial / 'source'
    shutil.copytree(base_source, source, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache',
                                                 '*credentials*.json', '.env', '.env.*'))
    for name in changes:
        shutil.copy2(WORK / name, source / name)
    names = sorted(set(declaration['payload_sha256']) | set(changes))
    for name in names:
        if name not in changes:
            assert sha(source / name) == declaration['payload_sha256'][name], name
    shutil.copy2(base_trial / 'runtime_config.json', trial / 'runtime_config.json')
    assert sha(trial / 'runtime_config.json') == declaration['runtime_config_sha256']
    declaration.update(
        created_utc=datetime.now(timezone.utc).isoformat(), source_root=str(source),
        source_commit=git('rev-parse', 'HEAD').decode().strip(), trial_identity=args.name,
        changed_payload_files=changes, payload_sha256={name: sha(source / name) for name in names},
        previous_trial=str(base_trial), new_output=True, previous_page_snapshots_reused=False,
        previous_trial_status_at_freeze=previous_state.get('status'),
        planned_generation_overlap_with_previous_trial=previous_state.get('status') == 'running_generation',
        overlap_note='If generation overlaps the previous trial, results are not a wall-clock speed comparison. No evaluation/reference artifacts from either trial will be read until both trials are terminal.',
        source_immutable_after_freeze=True, labels_read_before_generation=True,
        label_knowledge_note='These two development questions and previous completed evaluations are known. No reference answers or known target routes are encoded in the changes.',
        reference_labels_opened_for_repair=False, generalization_scope='Two known development questions, not a held-out accuracy estimate',
        fixes=args.fix or [
            'Model-selected primary and alternate observed navigation branches in one paid plan',
            'Explicit comparison of known model judgments with new originals and source-by-source issue review'],
        verified_unchanged_public_core_files=len(core_paths))
    (trial / 'declaration.json').write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + '\n')
    patch = git('diff', '--', *changes)
    for name in changes:
        if name in untracked:
            result = subprocess.run(['git', 'diff', '--no-index', '--', '/dev/null', name],
                                    cwd=WORK, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert result.returncode == 1, result.stderr
            patch += result.stdout
    (trial / 'repair.patch').write_bytes(patch)
    print(json.dumps({'trial': str(trial), 'source': str(source),
                      'payload_files': len(names), 'changed_files': changes,
                      'verified_unchanged_public_core_files': len(core_paths)}, indent=2))


if __name__ == '__main__':
    main()
