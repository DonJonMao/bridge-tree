#!/usr/bin/env python3
"""Verify a final committed archive by isolated, offline installation twice.

Writes an installation-only receipt. Never approves a release, builds an index,
calls a model, modifies a source checkout, or retains temporary credentials.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

BASE_COMMIT = 'a5b993a7d23cdd92c34b7ca45ebfb97b652a43e1'
DEFAULT_BASE = Path('/Users/mao/projects/dagv2-personamem-a48')
DEFAULT_REPO = Path('/Users/mao/projects/dagv2-personamem-v4')
DEFAULT_PYTHON = '/Users/mao/projects/dagv2/.venv/bin/python'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inventory(root):
    """All local files, dirs and symlinks; no exclusions, no symlink traversal."""
    result = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        for path in [Path(directory), *(Path(directory) / name for name in dirs + names)]:
            relative = path.relative_to(root).as_posix()
            if relative in result:
                continue
            info = path.lstat()
            row = {'mode': stat.S_IMODE(info.st_mode), 'mtime_ns': info.st_mtime_ns,
                   'device': info.st_dev, 'inode': info.st_ino}
            if path.is_symlink():
                row.update(kind='symlink', target=os.readlink(path))
            elif path.is_file():
                row.update(kind='file', bytes=info.st_size, sha256=file_sha(path))
            elif path.is_dir():
                row.update(kind='directory')
            else:
                raise ValueError('Unsupported filesystem object in installation inventory')
            result[relative] = row
    return result


def installed_inventory(root):
    # Idempotent install creates/removes a private staging directory, changing
    # its parent's directory mtime. Actual files and symlinks must stay exact.
    return {relative: {key: value for key, value in row.items()
                       if not (row['kind'] == 'directory' and key == 'mtime_ns')}
            for relative, row in inventory(root).items()}


def private_values(value):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in ('api_key', 'authorization', 'access_token', 'secret') and isinstance(item, str) and item:
                found.append(item)
            found.extend(private_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(private_values(item))
    return found


def known_secrets(base, private_files):
    values = []
    paths = list((base / 'configs').glob('*.local.json')) + list(private_files)
    for path in paths:
        values.extend(private_values(json.loads(path.read_text())))
    tree = ast.parse((base / 'dagbt/model_runtime.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DEFAULT_BT_LLM_API_KEY' for t in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str) and value:
                values.append(value)
    require(bool(values), 'A nonempty known-secret set is required for exact leakage checks')
    return sorted({variant for value in values for variant in
                   (value.encode(), json.dumps(value, ensure_ascii=True)[1:-1].encode())})


def no_secrets(data, secrets, label):
    require(not any(value in data for value in secrets), 'Private credential detected in ' + label)


def safe_relative(value):
    require(isinstance(value, str) and bool(value) and '\\' not in value and '\x00' not in value
            and not PurePosixPath(value).is_absolute() and str(PurePosixPath(value)) == value
            and all(part not in ('', '.', '..') for part in value.split('/')), 'Unsafe archive/manifest path')
    return value


def unpack(archive, destination, secrets):
    files = {}
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        require(0 < len(members) <= 10000 and sum(m.size for m in members) <= 1024 ** 3,
                'Archive size/member count exceeds validation bounds')
        for member in members:
            require(member.isfile() and member.name.startswith('dagv2/')
                    and member.mode in (0o644, 0o755), 'Archive contains an unsupported member')
            relative = safe_relative(member.name[6:])
            require(relative not in files, 'Duplicate archive member')
            require(not relative.endswith(('.local.json', '.npy', '.tar.gz', '.tgz')),
                    'Archive contains a private/vector/nested archive artifact')
            data = tar.extractfile(member).read()
            require(len(data) == member.size, 'Archive member length mismatch')
            no_secrets(data, secrets, 'archive member')
            files[relative] = data
            target = destination / 'dagv2' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
            target.chmod(member.mode)
    return files


def git(repo, *args):
    result = subprocess.run(['git', *args], cwd=repo, capture_output=True)
    require(result.returncode == 0, 'Historical source Git verification failed')
    return result.stdout


def verify_package(files, repo, expected_commit):
    require({'DEPLOYMENT.json', 'VALIDATION_PERSONAMEM_V4.json'} <= set(files), 'Missing final release metadata')
    manifest = json.loads(files['DEPLOYMENT.json'])
    commit = manifest.get('source_commit', '')
    require(re.fullmatch('[0-9a-f]{40}', commit) is not None, 'Source must identify a real committed release')
    require(not expected_commit or commit == expected_commit, 'Archive differs from expected source commit')
    require(manifest.get('base_commit') == BASE_COMMIT, 'Wrong deployment baseline')
    git(repo, 'merge-base', '--is-ancestor', BASE_COMMIT, commit)
    metadata = manifest['files']
    require(set(files) == set(metadata) | {'DEPLOYMENT.json'}, 'Tar members differ from deployment manifest')
    for relative, expected in metadata.items():
        safe_relative(relative)
        require(expected == {'bytes': len(files[relative]), 'sha256': sha(files[relative])},
                'Deployment per-file size/hash mismatch')
    validation = json.loads(files['VALIDATION_PERSONAMEM_V4.json'])
    require(validation == manifest.get('validation') and validation.get('release_ready') is True
            and validation.get('source_commit') == commit, 'Final archive lacks approval for its exact commit')
    tracked = {}
    for entry in git(repo, 'ls-tree', '-rz', '--full-tree', commit).decode().split('\0'):
        if not entry:
            continue
        header, relative = entry.split('\t', 1)
        mode, kind, blob = header.split()
        require(kind == 'blob' and mode in ('100644', '100755'), 'Unsupported committed source object')
        tracked[relative] = blob
    require(set(tracked) == set(files) - {'DEPLOYMENT.json', 'VALIDATION_PERSONAMEM_V4.json'},
            'Committed source file set differs from archive')
    for relative, blob in tracked.items():
        require(git(repo, 'cat-file', 'blob', blob) == files[relative], 'Archive source bytes differ from named commit')
    return manifest


NETWORK_GUARD = '''import os, sys
def guard(event, args):
    if event in ('socket.connect', 'socket.sendto', 'socket.getaddrinfo'):
        with open(os.environ['DAGBT_INSTALL_NETWORK_GUARD'], 'a') as stream:
            stream.write('blocked network attempt\\n')
        raise PermissionError('Network disabled during extracted installation verification')
sys.addaudithook(guard)
'''


INDEX_PROBE = '''import json
from pathlib import Path
from dagbt import runner
from dagbt.resources import inspect_index
config=runner.validate_config(runner.load('configs/personamem-v4.json'))
report=inspect_index(config,'personamem')
assert report['status']=='ready'
print(json.dumps({k:report[k] for k in ('status','identity','documents','dimensions','index_dir','manifest_path','vectors_path')}))
'''


def run_check(label, command, cwd, env, secrets, commands):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=180)
    no_secrets(result.stdout + result.stderr, secrets, 'subprocess output')
    commands.append({'label': label, 'returncode': result.returncode,
                     'stdout_bytes': len(result.stdout), 'stdout_sha256': sha(result.stdout),
                     'stderr_bytes': len(result.stderr), 'stderr_sha256': sha(result.stderr)})
    require(result.returncode == 0, 'Extracted installation subprocess failed: ' + label)
    return result.stdout


def verify(args):
    started = time.time()
    archive, base, repo = args.archive.resolve(), args.base.resolve(), args.source_repo.resolve()
    evidence_path = args.output.resolve()
    require(not evidence_path.exists(), 'Choose a new receipt path; existing evidence is never overwritten')
    require(base.is_dir() and archive.is_file(), 'Missing base deployment or final archive')
    require(all(evidence_path != root and root not in evidence_path.parents for root in (base, repo)),
            'Receipt must be outside the base deployment and source checkout')
    evidence = {'schema': 'dagv2_final_archive_installation_review_v1',
                'scope': 'Final archive extraction and installation only; not model quality or release approval',
                'release_ready': False, 'passed': False, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                'archive': str(archive), 'base': str(base), 'commands': []}
    before = inventory(base)
    evidence['base_inventory_before_sha256'] = sha(json.dumps(before, sort_keys=True).encode())
    evidence['base_inventory_objects'] = len(before)
    base_config = json.loads((base / 'configs/residual-memory.personamem16k.json').read_text())
    cache = Path(base_config.get('derived_index_dir', 'data/derived'))
    cache = (cache if cache.is_absolute() else base / cache).resolve()
    require(evidence_path != cache and cache not in evidence_path.parents,
            'Receipt must be outside the shared index cache')
    shared_before = inventory(cache) if cache.is_dir() else {}
    secrets = known_secrets(base, args.private_credentials)
    temporary_path = None
    failure = None
    try:
        evidence.update(archive_bytes=archive.stat().st_size, archive_sha256=file_sha(archive),
                        secrets_scanned=len(secrets), private_literals_absent=True)
        checksum = archive.with_name(archive.name + '.sha256')
        parts = checksum.read_text().strip().split()
        require(parts == [evidence['archive_sha256'], archive.name], 'Adjacent archive checksum mismatch')
        with tempfile.TemporaryDirectory(prefix='personamem-v4-final-install-') as temporary:
            temporary_path = Path(temporary)
            files = unpack(archive, temporary_path, secrets)
            manifest = verify_package(files, repo, args.expected_commit)
            target = temporary_path / 'dagv2'
            evidence.update(source_commit=manifest['source_commit'], package_files=len(files),
                            tar_manifest_verified=True, committed_source_bytes_verified=True)
            guard_dir = temporary_path / 'network_guard'; guard_dir.mkdir()
            (guard_dir / 'sitecustomize.py').write_text(NETWORK_GUARD)
            guard_file = temporary_path / 'network_attempts'
            env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(guard_dir),
                   'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                   'DAGBT_PYTHON': str(args.python.resolve()), 'DAGBT_INSTALL_NETWORK_GUARD': str(guard_file)}
            for key in ('DAG_LLM_API_KEY', 'BRIDGETREE_CHAT_API_KEY', 'DAG_EMBED_API_KEY'):
                env.pop(key, None)
            wrapper = target / 'scripts/personamem_v4.sh'
            results = []
            first_install_inventory = None
            for index in range(2):
                raw = run_check('install_' + str(index + 1), ['bash', str(wrapper), 'install', '--base', str(base)],
                                temporary_path, env, secrets, evidence['commands'])
                result = json.loads(raw); result.pop('smoke_command', None)
                require(result['ready'] and result['network_requests'] == 0 and not result['base_modified'],
                        'Installer did not verify all local assets')
                require(result['reused_frozen_vectors'] == (3 if index == 0 else 0), 'Frozen vector copy/idempotence count mismatch')
                results.append(result)
                current = installed_inventory(target)
                if index == 0:
                    first_install_inventory = current
                else:
                    require(current == first_install_inventory, 'Second installation changed installed files or metadata')
            evidence.update(installer_runs=results, idempotent=True,
                idempotence_scope='All installed file/symlink content, identity, mode and mtime; directory mtime excludes temporary staging churn')
            rows = json.loads((target / 'original_manifest.json').read_text())['files']
            vectors = []
            for row in rows:
                path = target / safe_relative(row['path'])
                require(path.is_file() and path.stat().st_size == row['bytes'] and file_sha(path) == row['sha256'],
                        'Installed frozen artifact mismatch')
                if row['path'].endswith('.npy'):
                    actual, old = path.stat(), (base / row['path']).stat()
                    require((actual.st_dev, actual.st_ino) != (old.st_dev, old.st_ino), 'Frozen vector shares base inode')
                    vectors.append({**row, 'separate_from_base_inode': True})
            require(len(vectors) == 3, 'Expected three frozen vector artifacts')
            evidence.update(original_artifacts_verified=len(rows), frozen_vectors=vectors)
            credential_file = target / 'configs/credentials.local.json'
            credentials = json.loads(credential_file.read_text())
            require(stat.S_IMODE(credential_file.stat().st_mode) == 0o600
                    and bool(credentials.get('llm', {}).get('api_key')), 'Migrated private credentials not protected/available')
            require(all(value.encode() in secrets for value in private_values(credentials)), 'Unscanned migrated credential')
            evidence['credentials'] = {'mode': '0o600', 'llm_nonempty': True,
                                       'embedding_auth_present': bool(credentials.get('embedding', {}).get('api_key')),
                                       'packaged': False, 'logged': False}
            index = json.loads(run_check('inspect_index', [str(args.python.resolve()), '-c', INDEX_PROBE],
                                         target, env, secrets, evidence['commands']))
            derived = target / 'data/derived'
            require(derived.is_symlink() and derived.resolve() == cache, 'Unexpected shared derived index target')
            index_manifest = json.loads(Path(index['manifest_path']).read_text())
            require(file_sha(Path(index['vectors_path'])) == index_manifest['vectors_sha256'], 'Derived index hash mismatch')
            evidence['derived_index'] = {k: index_manifest[k] for k in
                ('identity', 'embedding_model', 'corpus_sha256', 'documents', 'dimensions', 'vectors_sha256')}
            evidence['derived_index']['status'] = index['status']
            status_output = json.loads(run_check('wrapper_status', ['bash', str(wrapper), 'status', '--output',
                'outputs/final_install_validation_probe'], temporary_path, env, secrets, evidence['commands']))
            require(status_output['live_writer'] is False and status_output['progress'] is None,
                    'Fresh wrapper status is not idle')
            help_output = run_check('wrapper_help', ['bash', str(wrapper), '--help'], temporary_path,
                                    env, secrets, evidence['commands'])
            require(all(action.encode() in help_output for action in ('prepare-index', 'smoke', 'full', 'status', 'stop', 'accuracy')),
                    'Wrapper help is incomplete')
            require(not guard_file.exists(), 'Installation attempted a network request')
            for relative, data in files.items():
                require((target / relative).read_bytes() == data, 'Installation mutated a packaged artifact')
            evidence.update(network_attempts=0, wrapper_status_and_help_verified=True,
                            packaged_artifacts_unchanged=True)
    except Exception as exc:
        failure = type(exc).__name__
        evidence['failure_type'] = failure
        # Keep only a known-secret-redacted diagnostic, never raw child output.
        message = str(exc)
        for value in secrets:
            message = message.replace(value.decode(), '[REDACTED]')
        evidence['failure'] = message
    finally:
        after = inventory(base)
        shared_after = inventory(cache) if cache.is_dir() else {}
        evidence['base_inventory_after_sha256'] = sha(json.dumps(after, sort_keys=True).encode())
        evidence['base_content_mode_mtime_inode_unchanged'] = before == after
        evidence['shared_index_content_mode_mtime_inode_unchanged'] = shared_before == shared_after
        evidence['temporary_extraction_and_credentials_removed'] = temporary_path is not None and not temporary_path.exists()
        evidence['elapsed_seconds'] = round(time.time() - started, 3)
        evidence['passed'] = (failure is None and before == after and shared_before == shared_after
                              and evidence['temporary_extraction_and_credentials_removed'])
        rendered = (json.dumps(evidence, ensure_ascii=False, indent=2) + '\n').encode()
        no_secrets(rendered, secrets, 'validation receipt')
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with evidence_path.open('xb') as stream:
            stream.write(rendered)
    print(json.dumps({'receipt': str(evidence_path), 'passed': evidence['passed'],
                      'source_commit': evidence.get('source_commit'), 'release_ready': False,
                      'elapsed_seconds': evidence['elapsed_seconds']}, indent=2))
    return 0 if evidence['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New installation-only JSON receipt path')
    parser.add_argument('--base', type=Path, default=DEFAULT_BASE)
    parser.add_argument('--source-repo', type=Path, default=DEFAULT_REPO)
    parser.add_argument('--python', type=Path, default=Path(DEFAULT_PYTHON))
    parser.add_argument('--expected-commit')
    parser.add_argument('--private-credentials', type=Path, action='append', default=[])
    args = parser.parse_args()
    try:
        return verify(args)
    except Exception as exc:
        # Preparatory parse failures can quote private JSON; expose no raw text.
        print(json.dumps({'passed': False, 'failure_type': type(exc).__name__, 'release_ready': False}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
