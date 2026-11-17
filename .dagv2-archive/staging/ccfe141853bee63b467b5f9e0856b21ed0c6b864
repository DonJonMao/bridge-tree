"""Read-only closed-run receipt; no label reads, scoring, or service calls."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

RELEASE = Path('/Users/mao/projects/dagv2-personamem-v4')
RUN = RELEASE / 'outputs/v4_validation_r17'
REPORTS = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
COMMIT = 'bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94'
sys.dont_write_bytecode = True
sys.path.insert(0, str(RELEASE))
from dagbt import runner
from dagbt.methods import RESIDUAL_V2
from dagbt.personamem import load_questions, parse_choice

status = runner.status(RUN)
assert not status['live_writer'], 'Run is still live'
progress = status.get('progress') or {}
assert progress.get('state') in {'complete', 'complete_with_failures'}
head = subprocess.check_output(['git', '-C', str(RELEASE), 'rev-parse', 'HEAD'], text=True).strip()
assert head == COMMIT
assert not subprocess.check_output(
    ['git', '-C', str(RELEASE), 'status', '--porcelain', '--untracked-files=no'], text=True)
manifest = runner.load(RUN / 'manifest.json')
assert manifest['source_hashes'] == runner.frozen_sources()
config = RELEASE / 'configs/personamem-v4.json'
assert manifest['config'] == runner.validate_config(runner.load(config))
assert manifest['question_ids'] == runner.load(RELEASE / 'configs/personamem-v4-smoke-ids.json')
assert manifest['arms'] == ['original', RESIDUAL_V2]
ids = manifest['question_ids']['personamem']
assert len(ids) == len(set(ids)) == 14
questions = {q['id']: q for q in load_questions(RELEASE)}
assert runner.digest([questions[unit] for unit in ids]) == manifest['questions_digest']['personamem']
assert runner.file_hash(RELEASE / 'data/personamem/manifest.json') == manifest['dataset_manifests']['personamem']

canonical_rows = successful_residual = successful_legal_choices = 0
for arm in manifest['arms']:
    paths = list((RUN / 'personamem' / arm / 'rows').glob('*.json'))
    assert len(paths) == 14
    for unit in ids:
        path = runner.result_path(RUN, 'personamem', arm, unit)
        assert path in paths
        row = runner.validate_result(runner.load(path), unit)
        assert row.get('runner', {}).get('dataset') == 'personamem'
        assert row.get('runner', {}).get('arm') == arm
        canonical_rows += 1
        answer = row['answer']
        if answer['status'] != 'ok':
            continue
        choice = parse_choice(answer.get('prediction'), questions[unit]['options'])
        assert choice is not None
        successful_legal_choices += 1
        if arm != RESIDUAL_V2:
            continue
        diagnostic = row['diagnostics']
        assert row.get('method') == RESIDUAL_V2
        assert row.get('algorithm_version') == RESIDUAL_V2
        assert answer.get('completion_kind') == 'semantic_assessment'
        assert answer.get('certificate') is None
        assert diagnostic.get('audit_complete')
        assert answer.get('semantic_answer') == questions[unit]['options'][ord(choice) - 97]
        assert (diagnostic.get('terminal_input') or {}).get('validation_complete')
        successful_residual += 1

spec = importlib.util.spec_from_file_location('release_personamem_v4_receipt', RELEASE / 'scripts/personamem_v4.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    module.check_smoke(RUN, config)
except ValueError as error:
    # A closed run with failures is expected to hit this fixed first guard.
    fixed = 'Smoke 尚未全部成功结束；查看 status / launcher.log，不要启动全量。'
    assert str(error) == fixed, 'Unexpected gate error; review without emitting dynamic text'
    gate = {'passed': False, 'reason': fixed}
else:
    gate = {'passed': True}

receipt = {
    'run': 'v4_validation_r17', 'source_commit': head,
    'live_writer': status['live_writer'], 'state': progress['state'],
    'failed_arm_tasks': progress.get('failed_arm_tasks'),
    'validated_canonical_rows': canonical_rows,
    'successful_legal_choices_verified': successful_legal_choices,
    'successful_residual_terminal_contracts_verified': successful_residual,
    'frozen_source_hashes_verified': len(manifest['source_hashes']),
    'config_matches_current_release': True, 'fixed_question_ids_match': True,
    'public_question_digest_matches': True, 'dataset_manifest_matches': True,
    'strict_check': gate, 'labels_read': False, 'accuracy_scored': False,
    'scope': 'Read-only frozen release and canonical-row verification. Public choice/terminal structure only; no labels or question/options/answer text exported.'
}
path = REPORTS / 'r17_reader_closed_run_receipt.json'
path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'receipt': str(path), **receipt}, ensure_ascii=False))
