"""Read-only closed-run receipt; no label reads, scoring, or service calls."""
import json
import subprocess
import sys
from pathlib import Path

RELEASE = Path('/Users/mao/projects/dagv2-personamem-v4')
RUN = RELEASE / 'outputs/v4_validation_r21'
REPORTS = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
COMMIT = 'e6677081cdfb33c01db3aaa274a497168f314f78'
sys.dont_write_bytecode = True
sys.path.insert(0, str(RELEASE))
from dagbt import runner
from dagbt.methods import RESIDUAL_V2
from dagbt.personamem import load_questions, parse_choice

status = runner.status(RUN)
progress = status.get('progress') or {}
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

receipt={
    'run':'v4_validation_r21','source_commit':head,
    'live_writer':status['live_writer'],'state':progress.get('state'),
    'pid':(status.get('pid') or {}).get('pid'),
    'runtime_source_hashes_verified':len(manifest['source_hashes']),
    'source_tracked_files_clean':True,'config_matches_current_release':True,
    'fixed_question_ids_match':True,'planned_questions':len(ids),
    'public_question_digest_matches':True,'dataset_manifest_matches':True,
    'analysis_labels_read':False,'analysis_scores_read':False,
    'scope':'Initial read-only binding check, not a completion or accuracy gate.'
}
path=REPORTS/'r21_reader_initial_binding_receipt.json'
path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(receipt,ensure_ascii=False))
