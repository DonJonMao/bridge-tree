#!/usr/bin/env python3
"""Freeze a local repair candidate without changing an earlier trial."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


STAGE = Path(__file__).resolve().parent
WORK = Path('/Users/mao/projects/dagv2-webwalker-v4')
BASE = Path('/Users/mao/projects/dagv2_deploy/20261016_webwalker_v4_access_v13_experiment/current_validation/final_install/installed')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    trial = STAGE / 'candidate_occurrence_feedback'
    trial.mkdir(exist_ok=False)
    source = trial / 'source'
    shutil.copytree(BASE, source, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache',
                                                 '*credentials*.json', '.env', '.env.*'))
    changes = ['dagbt/webwalker_browser.py', 'dagbt/webwalker_reading.py',
               'tests/test_webwalker_link_context.py',
               'tests/test_webwalker_slot_navigation_feedback.py',
               'tests/test_webwalker_protocol_diagnostics.py']
    for name in changes:
        shutil.copy2(WORK / name, source / name)
    config_source = STAGE / 'baseline_v13/runtime_config.json'
    shutil.copy2(config_source, trial / 'runtime_config.json')
    declaration = json.loads((STAGE / 'baseline_v13/declaration.json').read_text())
    base_hashes = declaration['payload_sha256']
    for name, expected in base_hashes.items():
        if name not in changes:
            assert sha(source / name) == expected, name
    hashes = {name: sha(source / name) for name in sorted(set(base_hashes) | set(changes))}
    assert sha(trial / 'runtime_config.json') == declaration['runtime_config_sha256']
    declaration.update(
        created_utc=datetime.now(timezone.utc).isoformat(),
        source_root=str(source),
        trial_identity='local_occurrence_and_slot_feedback_repair_v1',
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WORK, text=True).strip(),
        changed_payload_files=changes,
        baseline_trial=str(STAGE / 'baseline_v13'),
        payload_sha256=hashes,
        fixes=['Keep same-page URL label and context from one observed occurrence',
               'Keep earlier body occurrence when a newer page repeats a URL in its menu',
               'Keep completed independent empty-slot feedback in mixed/repaired batches',
               'Explain missing observation source references in actual repair wires without relaxing validation'],
        new_output=True, previous_page_snapshots_reused=False,
        labels_read_before_generation=True,
        label_knowledge_note='Previous history and the now-terminal baseline evaluation are known; no raw reference files were opened to devise repairs. Fixes use generation logs and invented fixtures only.',
        baseline_evaluation_viewed_before_candidate_generation=True,
        reference_labels_opened_for_repair=False,
        source_immutable_after_freeze=True)
    (trial / 'declaration.json').write_text(json.dumps(declaration, ensure_ascii=False, indent=2) + '\n')
    patch = subprocess.check_output(['git', 'diff', '--', *changes], cwd=WORK)
    (trial / 'tracked_source.patch').write_bytes(patch)
    print(json.dumps({'trial': str(trial), 'source': str(source),
                      'changed_payload_files': changes,
                      'payload_files': len(hashes)}, indent=2))


if __name__ == '__main__':
    main()
