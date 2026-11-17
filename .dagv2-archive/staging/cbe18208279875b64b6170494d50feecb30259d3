#!/usr/bin/env python3
"""Verify, preserve metadata, then remove only the reviewed obsolete artifacts.

Dry run by default. --execute additionally requires a passing final archive
installation receipt. Scientific logs and source worktrees are never candidates.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

PROJECTS = Path('/Users/mao/projects')
VALIDATION = PROJECTS / 'dagv2_analysis/personamem_v4_validation'
REVIEW_HASH = 'f7304d28c2aa5e5d91f5baeb15292e3a4842b2daa5d4311e55586438dc70eb84'
PRESERVE = VALIDATION / 'historical_deployments'
ARCHIVES = {
    PROJECTS / relative
    for relative in (
        'dagv2_deploy/20261011/dagv2_bt_deploy_20261011_personamem_v4.tar.gz',
        'dagv2_deploy/20261011_a48dc8d/dagv2_bt_deploy_20261011_personamem_a48.tar.gz',
        'dagv2_deploy/20261011_a48dc8d_v2/dagv2_personamem_a48_v2_patch.tar.gz',
        'dagv2_deploy/20261011_a48dc8d_v3/dagv2_personamem_a48_v3_patch.tar.gz',
        'dagv2_deploy/20261012_a48dc8d_v3_1/dagv2_personamem_a48_v3_1_patch.tar.gz',
        'dagv2/scripts/dagv2_personamem_a48_v3_patch.tar.gz',
        'dagv2/scripts/dagv2_personamem_a48_v3_1_patch.tar.gz')
}
ALLOWED_FILES = ARCHIVES | {p.with_name(p.name + '.sha256') for p in ARCHIVES}
ALLOWED_STAGING = {PROJECTS / 'dagv2_deploy' / name / 'patch' for name in
                   ('20261011_a48dc8d_v2', '20261011_a48dc8d_v3', '20261012_a48dc8d_v3_1')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def direct_path(path):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve(), 'Symlink or noncanonical cleanup path')
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor /= part
        require(not cursor.is_symlink(), 'Symlink in cleanup path')
    return path


def verify_file(record):
    path = direct_path(record['path'])
    require(path.is_file() and path.stat().st_size == record['bytes']
            and digest(path) == record['sha256'], 'Reviewed file is missing or changed: ' + str(path))
    return path


def stage_files(stage):
    rows = {}
    for row in (stage['preserve_before_delete'] + stage['reconstructible_payload']
                + stage['disposable_generated_cache']
                + [item['staging_file'] for item in stage['duplicate_validation_receipts']]):
        old = rows.setdefault(row['path'], row)
        require(old['bytes'] == row['bytes'] and old['sha256'] == row['sha256'], 'Conflicting staging file records')
    return rows


def verify_stage(stage):
    root = direct_path(stage['path'])
    require(root in ALLOWED_STAGING and root.is_dir(), 'Unapproved staging directory')
    rows = stage_files(stage)
    actual = set()
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            path = direct_path(Path(directory) / name)
            require(path.is_file() or path.is_dir(), 'Unsupported object in staging')
            if path.is_file():
                actual.add(str(path))
    require(actual == set(rows), 'Staging contains unreviewed or missing files')
    for row in rows.values():
        path = verify_file(row)
        require(root in path.parents, 'Staging file escapes approved directory')
    for item in stage['duplicate_validation_receipts']:
        verify_file(item['retained_external_file'])
        require(item['staging_file']['sha256'] == item['retained_external_file']['sha256'],
                'Duplicate validation receipt differs from retained outside copy')
    for row in stage['reconstructible_payload']:
        require(row['commit'] == stage['target_commit'] and row['exact_git_blob_match'], 'Inconsistent historical commit')
        result = subprocess.run(['git', 'cat-file', 'blob', row['commit'] + ':' + row['relative_path']],
                                cwd=stage['git_repository'], capture_output=True)
        require(result.returncode == 0 and len(result.stdout) == row['bytes']
                and hashlib.sha256(result.stdout).hexdigest() == row['sha256'],
                'Historical payload Git object is unavailable or changed')
    return rows


def installation_gate(path):
    path = direct_path(path)
    record = json.loads(path.read_text())
    checks = ('passed', 'tar_manifest_verified', 'committed_source_bytes_verified', 'idempotent',
              'packaged_artifacts_unchanged', 'wrapper_status_and_help_verified',
              'temporary_extraction_and_credentials_removed',
              'base_content_mode_mtime_inode_unchanged', 'shared_index_content_mode_mtime_inode_unchanged')
    require(record.get('schema') == 'dagv2_final_archive_installation_review_v1'
            and all(record.get(name) is True for name in checks) and record.get('network_attempts') == 0,
            'A complete passing final archive installation receipt is mandatory')
    archive = direct_path(record['archive'])
    require(archive not in ALLOWED_FILES and not any(root == archive or root in archive.parents for root in ALLOWED_STAGING),
            'The verified new release must never be a cleanup candidate')
    verify_file({'path': str(archive), 'bytes': record['archive_bytes'], 'sha256': record['archive_sha256']})
    checksum = archive.with_name(archive.name + '.sha256')
    require(checksum.read_text().strip().split() == [record['archive_sha256'], archive.name], 'New release checksum changed')
    with tarfile.open(archive, 'r:gz') as tar:
        member = tar.getmember('dagv2/DEPLOYMENT.json')
        require(member.isfile(), 'New release manifest is not a regular file')
        manifest = json.loads(tar.extractfile(member).read())
    require(manifest['source_commit'] == record['source_commit']
            and manifest['validation']['source_commit'] == record['source_commit']
            and manifest['validation'].get('release_ready') is True, 'New release approval identity changed')
    return {'receipt': str(path), 'receipt_sha256': digest(path), 'archive': str(archive),
            'archive_sha256': record['archive_sha256'], 'source_commit': record['source_commit']}


def save_receipt(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.cleanup-receipt-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def perform(args):
    review_path = direct_path(args.review)
    require(digest(review_path) == REVIEW_HASH, 'Cleanup review differs from the independently checked version')
    review = json.loads(review_path.read_text())
    archive_rows = review['archive_delete_candidates']
    stages = review['staging_reviews']
    require({Path(row['path']) for row in archive_rows} == ALLOWED_FILES and len(archive_rows) == 14,
            'Cleanup archive set differs from the explicit allowlist')
    require({Path(stage['path']) for stage in stages} == ALLOWED_STAGING and len(stages) == 3,
            'Cleanup staging set differs from the explicit allowlist')
    output = direct_path(args.output)
    require(VALIDATION in output.parents and not output.exists() and PRESERVE not in output.parents,
            'Use a new execution receipt path directly under the validation area')
    gate = installation_gate(args.install_receipt)
    receipt = {'schema': 'dagv2_reviewed_cleanup_execution_v1', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
               'review': str(review_path), 'review_sha256': REVIEW_HASH, 'installation_gate': gate,
               'execute_requested': args.execute, 'completed': False, 'deleted_files': [],
               'removed_directories': [], 'preserved_metadata': [], 'scientific_logs_deleted': False,
               'source_worktrees_deleted': False}
    for row in archive_rows:
        verify_file(row)
    validated_stages = [(stage, verify_stage(stage)) for stage in stages]
    require(sum(len(stage['preserve_before_delete']) for stage in stages) == 14, 'Preservation file set changed')
    receipt['preflight'] = {'archive_files_verified': 14, 'staging_directories_verified': 3,
                            'staging_files_verified': sum(len(rows) for _, rows in validated_stages),
                            'historical_git_payloads_verified': sum(len(s['reconstructible_payload']) for s in stages)}
    if not args.execute:
        receipt['status'] = 'verified_dry_run_no_copies_or_deletions'
        save_receipt(output, receipt)
        print(json.dumps({'receipt': str(output), 'status': receipt['status'], 'completed': False}, indent=2))
        return 0
    save_receipt(output, receipt)
    try:
        # Finish and verify every preservation copy before the first deletion.
        for stage in stages:
            root = Path(stage['path'])
            for row in stage['preserve_before_delete']:
                source = verify_file(row)
                relative = source.relative_to(root)
                destination = direct_path(PRESERVE / root.parent.name / relative)
                require(PRESERVE in destination.parents, 'Metadata destination escapes the preservation area')
                destination.parent.mkdir(parents=True, exist_ok=True)
                expected = {**row, 'path': str(destination)}
                if not destination.exists():
                    with source.open('rb') as reader, destination.open('xb') as writer:
                        shutil.copyfileobj(reader, writer)
                    shutil.copystat(source, destination, follow_symlinks=False)
                verify_file(expected)
                receipt['preserved_metadata'].append({'source': str(source), 'destination': str(destination),
                    'bytes': row['bytes'], 'sha256': row['sha256'], 'verified': True})
                save_receipt(output, receipt)
        require(len(receipt['preserved_metadata']) == 14, 'Not all metadata was preserved')
        # Recheck all inputs after copying, before committing any destructive step.
        require(installation_gate(args.install_receipt) == gate, 'Final release changed during preservation')
        require(digest(review_path) == REVIEW_HASH, 'Cleanup review changed during preservation')
        for row in archive_rows:
            verify_file(row)
        for stage, _ in validated_stages:
            verify_stage(stage)
        for row in archive_rows:
            path = verify_file(row)
            path.unlink()
            receipt['deleted_files'].append({**row, 'kind': 'obsolete_archive_or_checksum'})
            save_receipt(output, receipt)
        for stage, rows in validated_stages:
            root = Path(stage['path'])
            # Individual allowlisted unlinks cannot sweep up a newly added log.
            for row in rows.values():
                path = verify_file(row)
                path.unlink()
                receipt['deleted_files'].append({'path': str(path), 'bytes': row['bytes'],
                    'sha256': row['sha256'], 'kind': 'reviewed_staging_file'})
                save_receipt(output, receipt)
            for directory, dirs, names in os.walk(root, topdown=False, followlinks=False):
                require(not names, 'Unexpected new file appeared; directory removal stopped')
                path = direct_path(directory)
                path.rmdir()  # Fails closed if an unreviewed file/directory appeared.
                receipt['removed_directories'].append(str(path))
                save_receipt(output, receipt)
        receipt.update(completed=True, status='completed', completed_at_utc=datetime.now(timezone.utc).isoformat(),
                       obsolete_archives_deleted=14, staging_roots_removed=3)
    except Exception as exc:
        receipt.update(status='stopped_after_error', failure_type=type(exc).__name__, failure=str(exc))
        raise
    finally:
        save_receipt(output, receipt)
    print(json.dumps({'receipt': str(output), 'completed': True, 'preserved_files': 14,
                      'obsolete_archive_files_removed': 14, 'staging_directories_removed': 3}, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, default=VALIDATION / 'cleanup_review.json')
    parser.add_argument('--install-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='Perform the already authorized, verified cleanup')
    args = parser.parse_args()
    try:
        return perform(args)
    except Exception as exc:
        print(json.dumps({'completed': False, 'failure_type': type(exc).__name__, 'error': str(exc)}, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
