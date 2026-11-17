"""Apply the verified PersonaMem deployment patch to its exact packaged base."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def safe_path(root, relative):
    part = Path(relative)
    if part.is_absolute() or '..' in part.parts or not part.parts:
        raise ValueError('Unsafe patch path: ' + relative)
    result = root / part
    if any(p.is_symlink() for p in (result, *result.parents) if p != root.parent):
        raise ValueError('Symlink in patch path: ' + str(result))
    return result


def verify_files(root, files):
    for name, item in files.items():
        path = safe_path(root, name)
        if not path.is_file() or sha(path) != item['sha256']:
            raise ValueError('Missing or changed file: ' + str(path))


def replace_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.patch-', delete=False) as handle:
        temp = Path(handle.name)
    try:
        shutil.copy2(source, temp)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path)
    args = parser.parse_args()
    target = args.target.expanduser().resolve(strict=True)
    package = Path(__file__).resolve().parent
    patch = json.loads((package / 'patch.json').read_text())
    verify_files(package / 'payload', patch['files'])
    metadata_path = target / 'DEPLOYMENT.json'
    metadata = json.loads(metadata_path.read_text())
    if metadata.get('source_commit') == patch['target_commit']:
        verify_files(target, patch['files'])
        verify_files(target, metadata['files'])
        print('Patch already installed: ' + patch['target_commit'])
        return
    if (metadata.get('source_commit') != patch['base_commit'] or
            sha(metadata_path) != patch['base_deployment_sha256']):
        raise ValueError('This patch requires the unmodified da64d56 (PersonaMem a48 v3) deployment package.')
    with ExitStack() as stack:
        # Existing experiment writers must be stopped before source replacement.
        for path in sorted((target / 'outputs').rglob('writer.lock')):
            handle = stack.enter_context(path.open('r+'))
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Stop the running experiment first: ' + str(path.parent)) from None
        verify_files(target, metadata['files'])
        for name in patch['files']:
            path = safe_path(target, name)
            if path.exists() and name not in metadata['files'] and name != 'DEPLOYMENT.json':
                raise ValueError('Patch would overwrite an untracked file: ' + str(path))
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = target / 'deployment_backups' / ('runtime-v3-1-' + stamp)
        backup.mkdir(parents=True)
        for name in patch['files']:
            path = target / name
            if path.exists():
                saved = backup / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, saved)
        applied = []
        try:
            # Publish the new deployment identity only after replacing its files.
            names = sorted(name for name in patch['files'] if name != 'DEPLOYMENT.json') + ['DEPLOYMENT.json']
            for name in names:
                replace_file(package / 'payload' / name, target / name)
                applied.append(name)
            updated = json.loads(metadata_path.read_text())
            verify_files(target, updated['files'])
        except BaseException:
            for name in reversed(applied):
                if (backup / name).exists():
                    replace_file(backup / name, target / name)
                else:
                    (target / name).unlink(missing_ok=True)
            raise
        print('Installed: ' + patch['target_commit'])
        print('Backup: ' + str(backup))
        print('Use a NEW experiment output directory: outputs/personamem_a48_v3_1_smoke or personamem_a48_v3_1_full')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        raise SystemExit('Patch not installed: ' + str(error))
