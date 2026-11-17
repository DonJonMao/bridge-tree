#!/usr/bin/env python3
"""Finalize revision 3 only after its real, installed eight-task run terminates.

This is an external release script, not part of the experiment payload. It never
starts generation/scoring or parses official reference answers. It hashes the
complete payload only after checking terminal progress and released OS owners.
Do not run it while the real suite is active. Revisions 1 and 2 are read-only.
"""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET


STAGE = Path(__file__).resolve().parent
WORKSPACE = Path('/Users/mao/projects/dagv2-webwalker-v4')
INSTALLED = STAGE / 'installed_validation_v3'
RUN = STAGE / 'real_smoke_v3'
RELEASE = STAGE / 'release_v3'
NAME = 'dagbt_benchmarks_v4_experiment'
BUNDLE = RELEASE / NAME
PAYLOAD = BUNDLE / 'payload'
ARCHIVE = RELEASE / (NAME + '.tar.gz')
CHECKSUM = ARCHIVE.with_suffix(ARCHIVE.suffix + '.sha256')
VALIDATION = STAGE / 'validation_v3.json'
FREEZE = STAGE / 'generation_source_freeze_v3.json'
AUDIT = STAGE / 'audit_real_smoke_v3_final.json'
ARCHIVE_REPORT = STAGE / 'archive_verification_v3.json'
FINAL = STAGE / 'final_release_v3.json'
RUNTIME_CONFIGS = STAGE / 'runtime_configs'
AUTHORIZED_CREDENTIALS_PATH = Path('/Users/mao/projects/dagv2/configs/credentials.local.json')
BASELINE = 'e6677081cdfb33c01db3aaa274a497168f314f78'
DATASETS = ('webwalkerqa', 'browsecomp_plus')
ARMS = ('dagbt_joint_memory_v1', 'dagbt_residual_memory_v2')
SCHEDULE = ('webwalkerqa/run', 'browsecomp_plus/run',
            'webwalkerqa/score', 'browsecomp_plus/score')
SOURCE_PREFIXES = ('dagbt', 'dagv2', 'dagresolve', 'package', 'vendor')
WEBWALKER_SCRIPTS = ('scripts/install_webwalker_browser.py', 'scripts/run_webwalker.sh',
                     'scripts/webwalker_offline_smoke.py')
BROWSECOMP_SCRIPTS = ('scripts/run_browsecomp_plus.sh', 'scripts/run_benchmarks.sh',
                     'scripts/prepare_browsecomp_plus.py', 'scripts/browsecomp_offline_smoke.py')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.finalize.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


@contextmanager
def finalizer_lock():
    with (STAGE / '.finalize_release_v3.lock').open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def lock_held(directory):
    path = directory / 'writer.lock'
    if not path.exists():
        return False
    with path.open('a+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def writer_directories():
    # Match benchmark_suite.launch -> suite.run -> dataset run/score locking.
    return (RUN / '.launch', RUN, *(RUN / name for name in DATASETS),
            *(RUN / name / '.scorer' for name in DATASETS))


@contextmanager
def hold_terminal_writer_locks():
    """Keep all existing runner locks owned until ready/failed is published."""
    held = {}
    with ExitStack() as stack:
        for directory in writer_directories():
            path = directory / 'writer.lock'
            require(path.is_file() and not path.is_symlink(),
                    'Expected existing benchmark writer lock: ' + str(path))
            stream = stack.enter_context(path.open('r+'))
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('Benchmark restarted before finalization: ' + str(directory)) from exc
            held[directory.resolve()] = stream
        yield held


def check_held_writer_lock(directory, held):
    stream = held.get(directory.resolve())
    require(stream is not None and not stream.closed, 'Finalizer no longer owns a writer lock')
    opened = os.fstat(stream.fileno())
    current = (directory / 'writer.lock').stat()
    require((opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino),
            'Benchmark writer lock was replaced during finalization: ' + str(directory))
    # flock on the original open description verifies/retains our own lock;
    # a fresh open would report this finalizer as a live benchmark writer.
    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)


def process_command(pid):
    require(type(pid) is int and pid > 0, 'Malformed owner PID')
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'command='],
                            capture_output=True, text=True)
    require(result.returncode in (0, 1), 'Unable to inspect owner PID')
    return result.stdout.strip() if result.returncode == 0 else ''


def terminal_gate(held=None):
    """This must precede every operation that reads payloads or terminal traces."""
    progress = read(RUN / 'progress.json')
    require(progress.get('state') == 'complete', 'Suite is not complete; do not finalize')
    stages = progress.get('stages', {})
    require(set(stages) == set(SCHEDULE), 'Suite stage set differs')
    for name in SCHEDULE:
        require(stages[name].get('state') == 'complete' and stages[name].get('returncode') == 0,
                'Suite stage did not exit successfully: ' + name)
        require(type(stages[name].get('ended_unix')) in (int, float)
                and stages[name]['ended_unix'] > 0, 'Suite stage terminal timestamp is missing')
    for earlier, later in zip(SCHEDULE, SCHEDULE[1:]):
        require(stages[earlier].get('ended_unix', 0) <= stages[later].get('ended_unix', 0),
                'Suite stage completion order differs')
    owners = []
    if held is not None:
        require(set(held) == {path.resolve() for path in writer_directories()},
                'Finalizer must retain every suite/dataset/scorer writer lock')
    for directory in writer_directories():
        if held is None:
            require(not lock_held(directory), 'Live OS writer: ' + str(directory))
        else:
            check_held_writer_lock(directory, held)
        record = directory / 'pid.json'
        if record.is_file():
            owner = read(record)
            require(owner.get('output') == str(directory.resolve()), 'Owner output identity differs')
            command = process_command(owner['pid'])
            require(not command or command != owner.get('process_command'),
                    'Recorded owner still runs the same command: ' + str(directory))
            require(not (command and str(directory.resolve()) in command and
                         any(module in command for module in ('dagbt.benchmark_suite',
                              'dagbt.webwalker_runner', 'dagbt.browsecomp_runner'))),
                    'An owned benchmark command remains live')
            owners.append({'directory': str(directory), 'pid': owner['pid'],
                           'benchmark_writer_lock_released': True,
                           'held_by_release_finalizer': held is not None,
                           'owned_command_alive': False})
    for name in DATASETS:
        dataset = read(RUN / name / 'progress.json')
        require(dataset.get('state') == 'complete' and dataset.get('completed') == 4
                and dataset.get('total') == 4, 'Dataset must have four terminal tasks: ' + name)
        for record in (RUN / name / 'tasks').glob('*/*/worker_pid.json'):
            command = process_command(read(record)['pid'])
            require(not (command and str(record.parent.resolve()) in command and
                         ('dagbt.webwalker_runner' in command or 'dagbt.browsecomp_runner' in command)),
                    'An owned task worker remains live')
    return progress, owners


def run_logged(command, logfile, *, cwd=None):
    with Path(logfile).open('w') as stream:
        result = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT)
    require(result.returncode == 0, 'Verification command failed; inspect ' + str(logfile))


def audit_generation():
    run_logged([sys.executable, str(STAGE / 'audit_real_smoke_v2.py'),
                '--root', str(RUN), '--output', str(AUDIT), '--expected-tasks', '8',
                '--require-terminal'], STAGE / 'audit_real_smoke_v3_final.log')
    audit = read(AUDIT)
    summary = audit['summary']
    require(summary.get('error_findings') == 0 and summary.get('generation_complete') is True
            and summary.get('terminal_tasks') == summary.get('discovered_tasks') == 8,
            'Generation audit is not complete and error-free')
    tasks = audit['tasks']
    identities = [(row['dataset'], row['question_id'], row['arm']) for row in tasks]
    require(len(identities) == len(set(identities)) == 8, 'Duplicate task audit identities')
    for dataset in DATASETS:
        rows = [row for row in tasks if row['dataset'] == dataset]
        counts = Counter(row['arm'] for row in rows)
        require(counts == Counter({arm: 2 for arm in ARMS}), 'Dataset arm coverage differs')
        question_ids = read(RUN / dataset / 'manifest.json')['question_ids']
        require(len(question_ids) == len(set(question_ids)) == 2
                and {(row['question_id'], row['arm']) for row in rows}
                    == {(qid, arm) for qid in question_ids for arm in ARMS},
                'Audit identities do not cover the same two questions in both arms')
    totals = Counter()
    exact = Counter()
    classified = {}
    for task in tasks:
        require(task.get('terminal') is True, 'A task is not terminal')
        for category, kinds in task['classified_errors'].items():
            classified.setdefault(category, Counter()).update(kinds)
            require(not kinds or category in ('controlled_budget_or_input_guard',
                                              'model_protocol_or_content'),
                    'Program, worker, service or unclassified failure: ' + category)
        require(not task['tokens']['tokenizer_errors'], 'Tokenizer service errors remain')
        require(task['calls']['attempts_without_success_response'] == 0,
                'A physical model attempt has no successful response')
        require(task['calls']['physical_charge_balance'] == 0, 'Physical model charges differ')
        require(task['tokens']['successful_responses_missing_usage'] == 0,
                'Successful responses lack token usage')
        validations = task['tokens']['exact_usage_validation_counts']
        required_validations = task['tokens']['successful_llm_responses'] + task['calls']['cache_hit_starts']
        require(set(validations) <= {'matched'}
                and validations.get('matched', 0) == required_validations
                and not task['tokens']['missing_validation_at_snapshot'],
                'Exact token validation differs from successful responses/cache verification')
        require(task['worker_log']['traceback_count'] == 0 and
                not task['worker_log']['fatal_signatures'], 'A worker crashed')
        for key in ('logical_reasoning_requests', 'call_journal_starts', 'cache_hit_starts',
                    'cached_attempt_charges', 'physical_model_http_attempts',
                    'successful_model_http_responses', 'repair_reservations'):
            totals[key] += task['calls'][key]
        totals['llm_budget_reservations'] += task['budget']['journal_used'].get('llm', 0)
        totals['tokenizer_http_attempts'] += task['tokens']['tokenizer_http_attempts']
        totals['prompt_tokens'] += task['tokens']['successful_response_usage_totals'].get('prompt_tokens', 0)
        totals['completion_tokens'] += task['tokens']['successful_response_usage_totals'].get('completion_tokens', 0)
        exact.update(task['tokens']['exact_usage_validation_counts'])
    require(set(exact) <= {'matched'} and exact['matched'] == totals['successful_model_http_responses']
            + totals['cache_hit_starts'],
            'Exact token validation coverage differs from successful responses/cache verification')
    # A call-start can precede an unissued, controlled budget reservation;
    # successful HTTP responses and cache verifications require exact usage.
    totals['unissued_call_journal_starts'] = (totals['call_journal_starts']
                                            - totals['successful_model_http_responses']
                                            - totals['cache_hit_starts'])
    require(totals['unissued_call_journal_starts'] >= 0, 'Successful calls exceed call journal starts')
    require(totals['llm_budget_reservations'] == totals['physical_model_http_attempts']
            + totals['cached_attempt_charges'], 'LLM physical/cache charge reconciliation differs')
    return audit, dict(totals), dict(exact), {key: dict(value) for key, value in classified.items()}


def source_and_payload_checks(validation):
    freeze = read(FREEZE)
    require(len(freeze) == 127 and sha(FREEZE) == validation['generation_source_freeze_sha256'],
            'Declared revision 3 source freeze differs')
    common_sources = {path: digest for path, digest in freeze.items()
                      if Path(path).parts[0] in SOURCE_PREFIXES and path.endswith('.py')}
    require(len(common_sources) == 120 and set(freeze) == (set(common_sources)
            | set(WEBWALKER_SCRIPTS) | set(BROWSECOMP_SCRIPTS)),
            'Frozen generation source path set differs')
    dataset_sources = {
        'webwalkerqa': {path: freeze[path] for path in (*common_sources, *WEBWALKER_SCRIPTS)},
        'browsecomp_plus': freeze,
    }
    for root in (WORKSPACE, INSTALLED, PAYLOAD):
        for relative, expected in freeze.items():
            require(sha(root / relative) == expected, 'Frozen source differs: ' + str(root / relative))
    manifest = read(BUNDLE / 'bundle_manifest.json')
    require(manifest.get('bundle_revision') == 3 and manifest.get('baseline_commit') == BASELINE,
            'Not the authorized revision 3 bundle')
    require(manifest.get('default_target') == '~/dagbt_runs/20261016_dual_benchmark_v4_v3/dagv2',
            'Revision 3 deployment target differs')
    expected = manifest['payload_sha256']
    require(len(expected) == 175, 'Expected the authorized 175-file payload')
    actual_paths = {str(path.relative_to(PAYLOAD)) for path in PAYLOAD.rglob('*') if path.is_file()}
    require(actual_paths == set(expected), 'Unexpected or missing bundle payload files')
    require(not any(path.is_symlink() for path in BUNDLE.rglob('*')), 'Bundle contains a symlink')
    for relative, digest in expected.items():
        require(not any(piece in ('credentials.local.json', '__pycache__', '.git', 'outputs')
                        for piece in Path(relative).parts), 'Private/cache/output payload member')
        for root in (WORKSPACE, INSTALLED, PAYLOAD):
            require(sha(root / relative) == digest, 'Payload differs: ' + str(root / relative))
    core = {}
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASELINE],
                                    cwd=WORKSPACE, text=True).splitlines()
    for relative in paths:
        if relative.endswith('.py') and relative.split('/')[0] in SOURCE_PREFIXES:
            raw = subprocess.check_output(['git', 'show', BASELINE + ':' + relative], cwd=WORKSPACE)
            core[relative] = hashlib.sha256(raw).hexdigest()
    require(len(core) == 107 and manifest['baseline_source_sha256'] == core,
            'Public baseline differs from independent git reference')
    require(all(expected.get(path) == digest for path, digest in core.items()), 'Public core payload changed')
    require(sha(BUNDLE / manifest['pdf_wheel']) == manifest['pdf_wheel_sha256'], 'PDF wheel differs')
    for dataset in DATASETS:
        generated = read(RUN / dataset / 'manifest.json')
        require(generated.get('generation_source_hashes') == dataset_sources[dataset],
                'Executed dataset source manifest differs: ' + dataset)
        require(generated.get('tasks') == 4 and set(generated.get('arms', [])) == set(ARMS),
                'Executed dataset task/arm set differs')
        require(generated.get('core_release') == BASELINE
                and generated.get('data') == manifest['datasets'][dataset]
                and len(generated.get('question_ids', [])) == 2
                and len(set(generated['question_ids'])) == 2,
                'Executed dataset baseline/data/question scope differs: ' + dataset)
    suite = read(RUN / 'manifest.json')
    require(suite.get('limit') == 2 and suite.get('datasets') == list(DATASETS)
            and suite.get('schedule') == [[name, stage] for name, stage in
                                          (item.split('/') for item in SCHEDULE)]
            and suite.get('after_personamem') is None, 'Executed suite scope differs')
    require(suite.get('source_sha256') == common_sources,
            'Executed suite source manifest differs')
    configs = {}
    for name in ('webwalker-v4.json', 'browsecomp-plus-v4.json'):
        relative = 'configs/' + name
        runtime_path = RUNTIME_CONFIGS / name
        require(runtime_path.is_file() and not runtime_path.is_symlink(),
                'Expected the authorized external runtime configuration')
        default = read(PAYLOAD / relative)
        installed_default = read(INSTALLED / relative)
        runtime = read(runtime_path)
        require(installed_default == default
                and default.get('credentials_file') == 'configs/credentials.local.json'
                and runtime.get('credentials_file') == str(AUTHORIZED_CREDENTIALS_PATH),
                'Runtime configuration credential path differs from the authorized local path')
        normalized = dict(runtime)
        normalized['credentials_file'] = default['credentials_file']
        require(normalized == default,
                'Runtime configuration differs beyond the credential path: ' + name)
        # Hash the config only. Never open or hash the referenced credential file.
        configs[str(runtime_path.resolve())] = sha(runtime_path)
    require(suite.get('configuration_sha256') == configs, 'Executed suite configurations differ')
    data = {dataset: {'directory': str(INSTALLED / 'data' / dataset),
                     'manifest_sha256': expected['data/' + dataset + '/manifest.json']}
            for dataset in DATASETS}
    require(suite.get('data') == data, 'Executed suite dataset identity differs')
    return manifest


def log_objects(path):
    text = Path(path).read_text()
    require('Traceback (most recent call last):' not in text and 'Fatal Python error:' not in text,
            'Verification log contains a traceback: ' + str(path))
    decoder, objects, offset = json.JSONDecoder(), [], 0
    while offset < len(text):
        start = text.find('{', offset)
        if start < 0:
            break
        value, consumed = decoder.raw_decode(text[start:])
        require(isinstance(value, dict), 'Expected verification JSON object')
        objects.append(value)
        offset = start + consumed
    require(objects, 'No verification publication in ' + str(path))
    return objects


def score_process_gate(audit):
    """Inspect score stdout/status counts, never references/evaluation/requests."""
    safe_fields = ('judge_failures', 'planned_questions', 'questions', 'environment_excluded')
    summaries = {}
    summary_counts = Counter()
    launcher = RUN / 'launcher.log'
    text = launcher.read_text()
    require('Traceback (most recent call last):' not in text and 'Fatal Python error:' not in text,
            'Suite launcher log contains a traceback')
    decoder, offset = json.JSONDecoder(), 0
    while offset < len(text):
        match = re.search(r'(?m)^[ \t]*\{', text[offset:])
        if match is None:
            break
        start = offset + match.start()
        while text[start].isspace():
            start += 1
        try:
            value, consumed = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            # A historical interruption may leave one partial stdout object;
            # later complete score summaries still have to pass every gate.
            offset = start + 1
            continue
        offset = start + consumed
        if not isinstance(value, dict) or value.get('protocol') != 'reference_complete_nonconflicting_llm_judge_v1':
            continue
        is_webwalker = value.get('access_policy') == 'paired_root_unavailable_exclusion_v1'
        is_browsecomp = isinstance(value.get('retriever'), dict)
        require(is_webwalker != is_browsecomp, 'Cannot identify a score stdout dataset')
        dataset = 'webwalkerqa' if is_webwalker else 'browsecomp_plus'
        arms = value.get('arms')
        require(isinstance(arms, dict) and set(arms) == set(ARMS), 'Score stdout arm set differs')
        # The launcher log is append-only across a legal resume. Use the last
        # summary for each dataset, projecting away correctness/accuracy fields.
        summaries[dataset] = {arm: {key: arms[arm][key] for key in safe_fields if key in arms[arm]}
                              for arm in ARMS}
        summary_counts[dataset] += 1
    require(set(summaries) == set(DATASETS), 'Both score stdout summaries are required')
    task_states = {}
    for task in audit['tasks']:
        dataset, qid, arm = task['dataset'], task['question_id'], task['arm']
        result = read(RUN / dataset / 'tasks' / qid / arm / 'result.json')
        require(result.get('unit_id') == qid and result.get('method') == arm,
                'Generation task identity changed before score inspection')
        answer = result['answer']
        require(answer.get('status') == task['answer_status'],
                'Generation answer status changed after the telemetry audit')
        prediction = answer.get('prediction')
        # Match shared.has_prediction exactly; do not coerce arbitrary values
        # with bool(), and never retain or emit the prediction itself.
        present = prediction is not None and (not isinstance(prediction, str) or bool(prediction.strip()))
        task_states[dataset, qid, arm] = (answer['status'], present)
    excluded_questions = {qid for (dataset, qid, _), (status, _) in task_states.items()
                          if dataset == 'webwalkerqa' and status == 'skipped_environment'}
    datasets = {}
    eligible_total = 0
    for dataset in DATASETS:
        excluded = len(excluded_questions) if dataset == 'webwalkerqa' else 0
        eligible = Counter()
        for (name, qid, arm), (status, present) in task_states.items():
            if name == dataset and status == 'ok' and present and not (name == 'webwalkerqa' and qid in excluded_questions):
                eligible[arm] += 1
        projected = summaries[dataset]
        for arm in ARMS:
            row = projected[arm]
            require(type(row.get('judge_failures')) is int and row['judge_failures'] == 0,
                    'Scoring reported a failed judgement: ' + dataset + '/' + arm)
            require(type(row.get('planned_questions')) is int and row['planned_questions'] == 2
                    and type(row.get('questions')) is int and row['questions'] == 2 - excluded,
                    'Scoring question coverage differs: ' + dataset + '/' + arm)
            if dataset == 'webwalkerqa':
                require(type(row.get('environment_excluded')) is int and row['environment_excluded'] == excluded,
                        'Scoring paired environment exclusions differ')
            else:
                require('environment_excluded' not in row or
                        (type(row['environment_excluded']) is int and row['environment_excluded'] == 0),
                        'BrowseComp scoring cannot exclude environment questions')
                row['environment_excluded'] = 0
        count = sum(eligible.values())
        eligible_total += count
        datasets[dataset] = {
            'arms': projected, 'stdout_summaries_observed': summary_counts[dataset],
            'eligible_judge_tasks': count,
            'eligible_judge_tasks_by_arm': {arm: eligible[arm] for arm in ARMS},
            'environment_excluded_tasks': excluded * len(ARMS),
            'judge_api_coverage': ('not_exercised_no_eligible_predictions' if count == 0
                                   else 'eligible_predictions_present_physical_calls_not_measured'),
        }
    return {'state': 'passed', 'datasets': datasets, 'eligible_judge_tasks': eligible_total,
            'judge_api_coverage': ('not_exercised_no_eligible_predictions' if eligible_total == 0
                                   else 'eligible_predictions_present_physical_calls_not_measured'),
            'note': 'Zero eligible predictions do not exercise the judge API; eligible predictions may use valid cached verdicts.',
            'launcher_log_sha256': sha(launcher),
            'official_references_evaluation_or_request_payloads_read': False}


def installation_evidence(validation):
    installed = read(STAGE / 'install_validation_v3.log')
    idem = read(STAGE / 'install_idempotence_v3.log')
    for row, count in ((installed, 236), (idem, 0)):
        require(row.get('installed') is True and row.get('new_files') == count
                and row.get('core_overwrites') == 0 and row.get('target') == str(INSTALLED),
                'Installation/idempotence publication differs')
    browser = read(STAGE / 'installed_browser_v3.log')
    require(browser.get('browser_ready') is True and browser.get('system_packages_changed') is False,
            'Installed Chromium was not verified')
    offline = log_objects(STAGE / 'installed_offline_v3.log')
    fixture_objects = [row for row in offline if 'offline_http_smoke' in row]
    require(len(fixture_objects) == 2, 'Both installed HTTP fixture datasets are required')
    for row in fixture_objects:
        arms = row['offline_http_smoke']
        require(row.get('external_network_used') is False and len(arms) == 2
                and {entry['arm'] for entry in arms} == set(ARMS)
                and all(entry.get('status') == 'ok' and entry.get('completion_kind') == 'certified_symbolic'
                        for entry in arms), 'Installed fixture did not certify both arms')
    require(offline[-1] == {'preflight': 'passed', 'offline': True}, 'Installed offline entry did not finish')
    online = log_objects(STAGE / 'real_smoke_installed_preflight_v3.log')
    require(online[-1] == {'preflight': 'passed', 'offline': False}, 'Installed online preflight did not finish')
    for rows in (offline, online):
        require({row.get('questions') for row in rows if 'questions' in row} == {680, 830},
                'Both prepared datasets were not checked')
        corpus = next(row for row in rows if row.get('questions') == 830)
        require(corpus.get('retrieval', {}).get('ready') is True
                and corpus.get('retrieval', {}).get('probe_hits', 0) > 0,
                'Installed corpus FTS probe failed')
    require(all(row.get('model', {}).get('ready') is True for row in online if 'questions' in row),
            'Installed model preflight failed')
    junit = ET.parse(STAGE / 'tests_v3.xml').getroot()
    suites = [junit] if junit.tag == 'testsuite' else list(junit)
    require(sum(int(row.get('tests', 0)) for row in suites) == 3050
            and all(int(row.get(key, 0)) == 0 for row in suites for key in ('failures', 'errors', 'skipped')),
            'Revision 3 full test evidence differs')
    require(sha(STAGE / 'tests_v3.xml') == validation['tests']['junit_sha256']
            and sha(STAGE / 'tests_v3.log') == validation['tests']['log_sha256'],
            'Full test evidence hashes differ')
    require(re.search(r'3050 passed, 69 warnings in 107\.53s',
                      (STAGE / 'tests_v3.log').read_text()) is not None,
            'Full test terminal summary differs')
    return installed, idem, fixture_objects


def finalized_validation(old, progress, owners, audit, totals, exact, classified, scoring, installed, idem):
    value = dict(old)
    value.pop('remaining_required_validation', None)
    value['state'] = 'real_smoke_complete_local_verified'
    value['updated_utc'] = datetime.now(timezone.utc).isoformat()
    value['scope'] = 'Local macOS installed revision 3, two questions per dataset and two arms; no claim of Linux full-dataset execution.'
    value['actual_smoke'] = {
        'state': 'complete', 'questions_per_dataset': 2, 'arms_per_question': 2,
        'total_tasks': 8, 'completed_generation_tasks': 8,
        'model_generation_requests': totals['logical_reasoning_requests'],
        'generation_telemetry': totals, 'exact_usage_validation': exact,
        'terminal_status_counts': audit['summary']['terminal_status_counts'],
        'classified_diagnostic_errors': classified,
        'audit_summary': audit['summary'], 'audit': str(AUDIT), 'audit_sha256': sha(AUDIT),
        'suite_progress': progress, 'all_four_stage_returncodes_zero': True,
        'generation_before_scoring': True, 'os_owners': owners,
        'after_personamem': None, 'server_personamem_gate_claimed': False,
        'generation_telemetry_excludes_scoring_calls': True,
        'scoring_process_gate': scoring,
        'official_reference_answers_inspected_by_agent': False,
        'answer_accuracy_is_not_a_process_acceptance_gate': True,
        'interpretation': 'Model ProtocolError/content failures and bounded budget/nonanswers remain visible algorithm outcomes. They are distinct from program exceptions, worker crashes, API failures and token-accounting errors; those block this finalizer.',
    }
    value['archive'] = {
        'filename': ARCHIVE.name, 'checksum_file': CHECKSUM.name,
        'credentials_included': False, 'prepared_data_complete': True,
        'payload_files': 175, 'unchanged_public_python_files': 107,
        'external_final_verification_record': str(FINAL),
        'note': 'The archive checksum is recorded externally to avoid a self-referential archive hash.'}
    value['installation'] = {
        'exit_code': 0, 'target': str(INSTALLED), 'base': installed['base'],
        'baseline_files': 107, 'new_files': installed['new_files'],
        'core_overwrites': 0, 'credentials_copied': installed['local_credentials_reused'],
        'idempotent_reinstall_new_files': idem['new_files'],
        'log_sha256': sha(STAGE / 'install_validation_v3.log'),
        'idempotence_log_sha256': sha(STAGE / 'install_idempotence_v3.log'),
        'note': 'Parent observed successful command exits; this finalizer revalidates their success publications. Local Darwin installation, not Linux server execution.'}
    value['installed_browser'] = {'browser_ready': True,
        'log_sha256': sha(STAGE / 'installed_browser_v3.log'),
        'local_dependency_reuse': read(STAGE / 'local_runtime_dependencies_v3.json')}
    value['installed_offline_entry'] = {
        'command': 'DAGBT_PYTHON=<existing venv python> bash scripts/run_benchmarks.sh offline',
        'exit_code': 0, 'datasets': list(DATASETS), 'both_arms_each': 'ok/certified_symbolic',
        'real_corpus_hash_and_fts_probe_passed': True, 'external_network_used': False,
        'log': str(STAGE / 'installed_offline_v3.log'),
        'log_sha256': sha(STAGE / 'installed_offline_v3.log')}
    value['installed_online_preflight'] = {'exit_code': 0, 'model_and_tokenizer_ready': True,
        'log': str(STAGE / 'real_smoke_installed_preflight_v3.log'),
        'log_sha256': sha(STAGE / 'real_smoke_installed_preflight_v3.log')}
    value['offline_http_fixtures']['log_sha256'] = sha(STAGE / 'offline_dual_v3.log')
    value['generation_source_freeze_unchanged'] = True
    value['generation_source_files'] = 127
    value['payload_files'] = 175
    require('pending' not in json.dumps(value).lower(), 'Final validation still contains a pending claim')
    return value


def archive_and_verify():
    # Keep the final basenames inside a private same-filesystem directory so
    # the exact checked checksum can be published without rewriting its text.
    with tempfile.TemporaryDirectory(prefix='.finalize-v3-', dir=RELEASE) as temporary_name:
        candidate_directory = Path(temporary_name)
        candidate = candidate_directory / ARCHIVE.name
        candidate_checksum = candidate_directory / CHECKSUM.name
        candidate_report = candidate_directory / ARCHIVE_REPORT.name
        with tarfile.open(candidate, 'w:gz', compresslevel=3) as archive:
            archive.add(BUNDLE, arcname=NAME)
        digest = sha(candidate)
        candidate_checksum.write_text(digest + '  ' + ARCHIVE.name + '\n')
        run_logged([sys.executable, str(STAGE / 'verify_archive.py'), str(candidate),
                    '--report', str(candidate_report)], STAGE / 'archive_verification_v3.log')
        verified = read(candidate_report)
        require(verified.get('archive') == str(candidate) and verified.get('verified') is True
                and verified.get('regular_files') == 182 and verified.get('payload_files') == 175
                and verified.get('unchanged_public_python_files') == 107
                and verified.get('private_credentials_or_old_outputs') is False,
                'Independent streaming candidate archive verification failed')
        if shutil.which('sha256sum'):
            command = ['sha256sum', '-c', candidate_checksum.name]
        else:
            require(shutil.which('shasum') is not None, 'No external SHA256 checker available')
            command = ['shasum', '-a', '256', '-c', candidate_checksum.name]
        run_logged(command, STAGE / 'checksum_verification_v3.log', cwd=candidate_directory)
        require(candidate_checksum.read_text() == digest + '  ' + ARCHIVE.name + '\n',
                'Candidate checksum changed before publication')
        # Both checks passed. Each rename is atomic; FINAL remains finalizing
        # until both names and the final verification report are published.
        os.replace(candidate, ARCHIVE)
        os.replace(candidate_checksum, CHECKSUM)
        verified['archive'] = str(ARCHIVE)
        verified['archive_sha256'] = digest
        verified['verified_before_publication'] = True
        save(ARCHIVE_REPORT, verified)
        require(CHECKSUM.read_text() == digest + '  ' + ARCHIVE.name + '\n', 'Checksum publication changed')
    return digest, verified


def main():
    with finalizer_lock():
        # Absolutely no official data hashing, audit trace reading or repacking
        # occurs until every generation/scoring stage and OS owner is terminal.
        terminal_gate()
        in_progress = {
            'state': 'finalizing', 'bundle_revision': 3,
            'started_utc': datetime.now(timezone.utc).isoformat(),
            'pid': os.getpid(), 'archive': str(ARCHIVE), 'checksum_file': str(CHECKSUM),
            'run': str(RUN),
            'note': 'Only a final verified_ready record authorizes use of this release.'}
        # Invalidate a previous successful marker before mutating any release
        # evidence/artifact. A failed or interrupted retry cannot leave it ready.
        save(FINAL, in_progress)
        with ExitStack() as held_stack:
            try:
                held = held_stack.enter_context(hold_terminal_writer_locks())
                progress, owners = terminal_gate(held)
                audit, totals, exact, classified = audit_generation()
                old = read(VALIDATION)
                manifest = source_and_payload_checks(old)
                scoring = score_process_gate(audit)
                installed, idem, _ = installation_evidence(old)
                terminal_gate(held)
                value = finalized_validation(old, progress, owners, audit, totals, exact, classified, scoring, installed, idem)
                save(VALIDATION, value)
                save(BUNDLE / 'validation.json', value)
                digest, archive_report = archive_and_verify()
                terminal_gate(held)
                require(sha(FREEZE) == value['generation_source_freeze_sha256'], 'Source freeze declaration changed')
                result = {
                    'state': 'verified_ready', 'bundle_revision': 3,
                    'verified_utc': datetime.now(timezone.utc).isoformat(),
                    'archive': str(ARCHIVE), 'sha256': digest, 'checksum_file': str(CHECKSUM),
                    'bytes': ARCHIVE.stat().st_size, 'payload_files': len(manifest['payload_sha256']),
                    'unchanged_public_python_files': 107, 'generation_source_files': 127,
                    'installation_new_files': 236, 'idempotent_reinstall_new_files': 0,
                    'installed_offline_exit_code': 0, 'installed_online_preflight_exit_code': 0,
                    'actual_generation_tasks': 8, 'model_generation_requests': totals['logical_reasoning_requests'],
                    'generation_telemetry': totals, 'exact_usage_validation': exact,
                    'terminal_status_counts': audit['summary']['terminal_status_counts'],
                    'classified_diagnostic_errors': classified,
                    'scoring_process_gate': scoring,
                    'real_smoke_state': 'complete', 'all_four_stage_returncodes_zero': True,
                    'runner_writer_locks_held_during_finalization': len(held),
                    'scope': value['scope'], 'answer_accuracy_is_not_a_process_acceptance_gate': True,
                    'validation': str(VALIDATION), 'validation_sha256': sha(VALIDATION),
                    'generation_audit': str(AUDIT), 'generation_audit_sha256': sha(AUDIT),
                    'archive_stream_verification': archive_report, 'checksum_verification': 'passed',
                    'datasets': {'webwalkerqa': 680, 'browsecomp_plus': 830},
                    'browsecomp_corpus_documents': 100195,
                    'previous_revision_archives_modified': False}
                save(FINAL, result)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            except BaseException as exc:
                failed = {**in_progress, 'state': 'failed',
                          'failed_utc': datetime.now(timezone.utc).isoformat(),
                          'error_type': type(exc).__name__, 'error': str(exc),
                          'note': 'Finalization failed; published files must not be treated as a verified release.'}
                save(FINAL, failed)
                raise


if __name__ == '__main__':
    main()
