#!/usr/bin/env python3
"""Approve exact reviewed source only after real offline and smoke evidence passes.

Does not run tests/models, score answers, build a tar, install, or clean up.
The reviewed candidate supplies test execution provenance; the actual log,
current source/config and production smoke gate are independently rechecked.
Only a new external output file may be created. No approval is written on a
failed check; this script must not be used with fabricated passing receipts.
"""
import argparse
from datetime import datetime, timezone
from fnmatch import fnmatchcase
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.dont_write_bytecode = True
BASE_COMMIT = 'a5b993a7d23cdd92c34b7ca45ebfb97b652a43e1'


class ApprovalError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ApprovalError(message)


def git(root, *args):
    result = subprocess.run(['git', '--no-optional-locks', *args], cwd=root,
                            capture_output=True, check=False)
    require(result.returncode == 0, 'Git source verification failed')
    return result.stdout.decode().strip()


def clean_commit(root, expected):
    require(re.fullmatch(r'[0-9a-f]{40}', expected) is not None,
            'Expected commit must be the complete 40-character commit')
    require(Path(git(root, 'rev-parse', '--show-toplevel')).resolve() == root,
            'Source root is not the Git checkout root')
    require(git(root, 'rev-parse', 'HEAD') == expected, 'HEAD differs from expected commit')
    require(not git(root, 'status', '--porcelain', '--untracked-files=normal'),
            'Source checkout is not clean')
    git(root, 'merge-base', '--is-ancestor', BASE_COMMIT, expected)


def fingerprint(path):
    require(path.is_file() and not path.is_symlink(), 'Evidence must be an existing regular file')
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
            'Evidence changed while hashing')
    return {'path': str(path), 'bytes': after.st_size, 'sha256': digest.hexdigest()}


def repo_path(root, value):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def install_read_guard(output, writer_lock):
    """Prevent labels/network and writes other than output or the existing lock probe."""
    def guard(event, args):
        if event in ('socket.connect', 'socket.sendto', 'socket.getaddrinfo'):
            raise ApprovalError('Network access is forbidden during source approval')
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        require(path.name != 'evaluation_only.json' and not path.name.endswith('.local.json'),
                'Labels and private credentials must not be opened during source approval')
        flags = args[2]
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            # Production runner.status opens its already-existing lock with a+;
            # it only probes flock and never writes file content.
            lock_probe = path == writer_lock and path.is_file() and not flags & os.O_TRUNC
            new_output = path == output and flags & os.O_EXCL and flags & os.O_CREAT
            require(lock_probe or new_output, 'Unexpected write attempted during source approval')
    sys.addaudithook(guard)


def verify_test_command(recorded_command, root=None):
    """Accept exact whole-suite commands, never selectors or file subsets."""
    command = shlex.split(recorded_command)
    require(len(command) in (4, 5) and Path(command[0]).name in ('python', 'python3')
            and command[1:4] == ['-m', 'pytest', '-q']
            and (len(command) == 4 or command[4] == 'tests'),
            'Candidate does not describe the full test command')
    if len(command) == 5:
        require(root is not None, 'Explicit tests command needs its source checkout')
        require(not git(root, 'status', '--porcelain', '--untracked-files=normal'),
                'Explicit tests command requires a clean source checkout')
        tracked = git(root, 'ls-tree', '-r', '--name-only', '-z', 'HEAD').split('\0')
        test_files = [name for name in tracked if
                      fnmatchcase(Path(name).name, 'test_*.py')
                      or fnmatchcase(Path(name).name, '*_test.py')]
        require(test_files and all(name.startswith('tests/') for name in test_files),
                'Explicit tests command omits tracked test files outside tests/')


def verify_test_log(candidate, full_test_log, root=None):
    tests = candidate['offline_tests']
    verify_test_command(tests['command'], root)
    require(tests.get('exit_code') == 0 and tests.get('runtime_matches_release') is True,
            'Candidate does not attest a successful matching-source full test run')
    require(Path(tests['report']).resolve() == full_test_log, 'Test report path differs from candidate')
    evidence = fingerprint(full_test_log)
    require(evidence['sha256'] == tests.get('report_sha256'), 'Full test log SHA256 differs from candidate')
    lines = full_test_log.read_text().splitlines()
    last = next((line.strip().strip('= ').strip() for line in reversed(lines) if line.strip()), '')
    match = re.fullmatch(r'(\d+) passed(?:, (\d+) warnings?)? in (\d+(?:\.\d+)?)s(?: \([^\n)]+\))?', last)
    require(match is not None, 'Full test log does not end with an all-passed pytest summary')
    passed, warnings, seconds = int(match[1]), int(match[2] or 0), float(match[3])
    require(passed > 0 and passed == tests.get('passed') and warnings == tests.get('warnings')
            and seconds == tests.get('seconds'), 'Full test summary differs from candidate')
    require(fingerprint(full_test_log) == evidence, 'Full test log changed during verification')
    return {**tests, 'report': str(full_test_log), 'report_sha256': evidence['sha256'],
            'verified_summary': last, 'provenance': 'Reviewed candidate execution record plus verified log; tests not rerun here'}


def collect_run_files(runner, smoke, manifest, arms):
    ids = manifest['question_ids']['personamem']
    require(manifest.get('datasets') == ['personamem'] and len(ids) == 14
            and len(set(ids)) == 14 and manifest.get('arms') == arms,
            'Smoke must contain exactly the fixed 14-question two-arm PersonaMem run')
    rows = []
    for arm in arms:
        expected = {runner.result_path(smoke, 'personamem', arm, unit) for unit in ids}
        directory = smoke / 'personamem' / arm / 'rows'
        require(directory.is_dir() and not directory.is_symlink()
                and set(directory.iterdir()) == expected, 'Current rows contain missing or unexpected files')
        rows.extend(sorted(expected))
    paths = [smoke / 'manifest.json', smoke / 'progress.json', smoke / 'writer.lock', *rows]
    require(all(path.resolve() == path and smoke in path.parents for path in paths),
            'Smoke evidence contains symlinked or out-of-run paths')
    return {str(path.relative_to(smoke)): fingerprint(path) for path in paths}


def prepare(args):
    root = args.root.expanduser().resolve()
    config, smoke = repo_path(root, args.config), repo_path(root, args.smoke_output)
    candidate_path, full_test_log = args.candidate.expanduser().resolve(), args.full_test_log.expanduser().resolve()
    output = args.output.expanduser().absolute()
    require(output == output.resolve() and not output.exists() and output.parent.is_dir(),
            'Output must be a new canonical path in an existing directory')
    require(root not in output.parents and smoke not in output.parents,
            'Approval output must be outside the source checkout and smoke run')
    require(root in config.parents and root in smoke.parents, 'Config and smoke must belong to the source checkout')
    clean_commit(root, args.expected_commit)
    install_read_guard(output, smoke / 'writer.lock')
    candidate_evidence = fingerprint(candidate_path)
    candidate = json.loads(candidate_path.read_text())
    require(candidate.get('source_commit') == args.expected_commit and candidate.get('release_ready') is False,
            'Candidate must identify this exact unapproved source commit')
    planned = candidate['model_smoke']
    require(repo_path(root, planned['output']) == smoke and repo_path(root, planned['config']) == config
            and planned.get('questions') == 14 and planned.get('labels_used_for_selection') is False,
            'Candidate smoke/config/label-free selection identity differs')
    config_evidence = fingerprint(config)
    require(candidate.get('config_sha256') == config_evidence['sha256'], 'Config SHA256 differs from candidate')
    offline = verify_test_log(candidate, full_test_log, root)

    os.chdir(root)
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location('_personamem_v4_approval_gate', root / 'scripts/personamem_v4.py')
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    runner = gate.runner
    require(runner.ROOT.resolve() == root and gate.ROOT.resolve() == root, 'Imported gate is from another checkout')
    sources = runner.frozen_sources()
    require(candidate.get('source_hashes') == sources, 'Frozen source hashes differ from candidate')
    state = runner.status(smoke)
    require(state.get('live_writer') is False and (state.get('progress') or {}).get('state') == 'complete'
            and state['progress'].get('failed_arm_tasks') == 0, 'Smoke is live, incomplete or has failed tasks')
    manifest = runner.load(smoke / 'manifest.json')
    require(manifest.get('source_hashes') == sources, 'Smoke sources differ from candidate/current source')
    evidence = collect_run_files(runner, smoke, manifest, gate.ARMS)
    check = gate.check_smoke(smoke, config=config)
    require(check.get('status') == 'passed' and check.get('questions') == 14 and check.get('arms') == gate.ARMS,
            'Production smoke gate did not pass')

    # Re-read every binding after the actual gate so a changing input cannot
    # borrow an older pass. No raw prompts, predictions or label files are saved.
    require(collect_run_files(runner, smoke, manifest, gate.ARMS) == evidence,
            'Smoke evidence changed during the production gate')
    require(runner.status(smoke) == state, 'Smoke writer/progress changed during approval')
    require(runner.frozen_sources() == sources and fingerprint(config) == config_evidence
            and fingerprint(candidate_path) == candidate_evidence,
            'Source, config or candidate changed during approval')
    require(verify_test_log(candidate, full_test_log, root) == offline, 'Offline evidence changed during approval')
    clean_commit(root, args.expected_commit)
    result = {
        'schema': 'dagv2_source_model_approval_v1',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Exact source/offline tests/model execution gate passed; permits packaging only, not final delivery or an accuracy claim',
        'source_commit': args.expected_commit, 'release_ready': True,
        'source_worktree_clean': True, 'source_hashes': sources,
        'config_sha256': config_evidence['sha256'], 'candidate_evidence': candidate_evidence,
        'offline_tests': offline,
        'model_smoke': {'output': str(smoke), 'config': str(config), 'questions': 14,
                        'arms': gate.ARMS, 'state': 'complete', 'live_writer': False, 'passed': True,
                        'labels_used_for_selection': False, 'check': check,
                        'evidence_files': evidence, 'current_rows': 28},
        'verification': {'read_only_inputs': True, 'labels_read': False, 'network_requests': 0,
                         'tests_or_models_run': False, 'new_output_mode': 'x'},
        'release_pending': ['final_package_install', 'obsolete_package_cleanup'],
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    with output.open('x') as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
    return {'approval': str(output), 'source_commit': args.expected_commit, 'release_ready': True,
            'scope': 'Source/model approval only; final tar installation and cleanup remain pending'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--full-test-log', type=Path, required=True)
    parser.add_argument('--smoke-output', required=True, help='Absolute path or path relative to --root')
    parser.add_argument('--config', required=True, help='Absolute path or path relative to --root')
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--output', type=Path, required=True, help='New external JSON approval path; never overwritten')
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        message = str(exc) if isinstance(exc, ApprovalError) else 'Verification failed; no approval granted'
        print(json.dumps({'release_ready': False, 'error_type': type(exc).__name__, 'error': message}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
