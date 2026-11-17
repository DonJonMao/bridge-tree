"""Exercise the shipped installer against exact-base files, including rollback."""
import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from unittest.mock import patch

from build_patch import ROOT, BASE, RELEASE, OLD_META, describe, save


def verify_archive_members(archive, files):
    expected = {'apply_patch.py', 'install_and_smoke.sh', 'README.md',
                'validation.json', 'patch.json', *('payload/' + name for name in files)}
    members = archive.getmembers()
    names = [member.name for member in members]
    assert len(names) == len(set(names)), 'Duplicate archive members'
    assert set(names) == expected, 'Archive members do not exactly match the manifest'
    assert all(member.isfile() and not Path(member.name).is_absolute()
               and '..' not in Path(member.name).parts for member in members), 'Unsafe archive member'


def main():
    base = json.loads(OLD_META.read_text())
    spec = importlib.util.spec_from_file_location('installer', RELEASE / 'patch/apply_patch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checks = []
    with tempfile.TemporaryDirectory(prefix='a48-v3-1-install-', dir=RELEASE) as directory:
        directory = Path(directory)
        target = directory / 'dagv2'
        target.mkdir()
        for name, expected in base['files'].items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            source = ROOT / name
            if describe(source) == expected:
                os.link(source, path)  # Installer always replaces, never edits these shared files.
            else:
                path.write_bytes(subprocess.check_output(['git', 'show', BASE + ':' + name], cwd=ROOT))
        shutil.copy2(OLD_META, target / 'DEPLOYMENT.json')
        module.verify_files(target, base['files'])
        checks.append('exact_base_reconstruction')

        def install():
            with patch.object(sys, 'argv', ['apply_patch.py', '--target', str(target)]), contextlib.redirect_stdout(io.StringIO()) as output:
                module.main()
            return output.getvalue()

        lock = target / 'outputs/active/writer.lock'
        lock.parent.mkdir(parents=True)
        with lock.open('a+') as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                install()
            except RuntimeError as error:
                assert 'Stop the running experiment' in str(error)
            else:
                raise AssertionError('Active writer accepted')
        checks.append('active_writer_rejected')

        installed_patch = json.loads((RELEASE / 'patch/patch.json').read_text())
        payload_file = next(name for name in installed_patch['files'] if name != 'DEPLOYMENT.json')
        payload = RELEASE / 'patch/payload' / payload_file
        original = payload.read_bytes()
        try:
            payload.write_bytes(original + b'\ncorrupted\n')
            try:
                install()
            except ValueError as error:
                assert 'Missing or changed file' in str(error)
            else:
                raise AssertionError('Corrupted payload accepted')
        finally:
            payload.write_bytes(original)
        checks.append('corrupted_payload_rejected')

        base_name = next(name for name in base['files'] if name.startswith('dagbt/'))
        base_file = target / base_name
        original = base_file.read_bytes()
        base_file.unlink()
        try:
            base_file.write_bytes(original + b'\ncorrupted\n')
            try:
                install()
            except ValueError as error:
                assert 'Missing or changed file' in str(error)
            else:
                raise AssertionError('Changed base accepted')
        finally:
            base_file.write_bytes(original)
        checks.append('changed_base_rejected')

        replace = module.replace_file
        calls = 0
        def failed_replace(source, destination):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise OSError('Injected partial-install failure')
            replace(source, destination)
        with patch.object(module, 'replace_file', failed_replace):
            try:
                install()
            except OSError as error:
                assert str(error) == 'Injected partial-install failure'
            else:
                raise AssertionError('Failure injection missed')
        module.verify_files(target, base['files'])
        assert (target / 'DEPLOYMENT.json').read_bytes() == OLD_META.read_bytes()
        assert not any((target / name).exists() for name in installed_patch['files']
                       if name not in base['files'] and name != 'DEPLOYMENT.json')
        checks.append('partial_install_rollback')

        assert 'Installed: ' in install()
        new_metadata = json.loads((target / 'DEPLOYMENT.json').read_text())
        module.verify_files(target, new_metadata['files'])
        assert 'Patch already installed' in install()
        checks.extend(['install_hashes_verified', 'idempotent_install'])

        with tarfile.open(RELEASE / 'dagv2_personamem_a48_v3_1_patch.tar.gz') as archive:
            verify_archive_members(archive, installed_patch['files'])
            extracted = directory / 'archive'
            archive.extractall(extracted, filter='data')
        module.verify_files(extracted / 'payload', installed_patch['files'])
        checks.append('exact_archive_members_verified')

        # Hash verification of the manifest's subset is insufficient: reject
        # extra files as well, including an unlisted credentials-like sentinel.
        extra_archive = directory / 'unexpected-member.tar.gz'
        with tarfile.open(RELEASE / 'dagv2_personamem_a48_v3_1_patch.tar.gz') as source:
            with tarfile.open(extra_archive, 'w:gz') as destination:
                for member in source.getmembers():
                    destination.addfile(member, source.extractfile(member))
                sentinel = b'non-secret test sentinel'
                member = tarfile.TarInfo('payload/configs/credentials.local.json')
                member.size = len(sentinel)
                destination.addfile(member, io.BytesIO(sentinel))
        with tarfile.open(extra_archive) as archive:
            try:
                verify_archive_members(archive, installed_patch['files'])
            except AssertionError as error:
                assert 'exactly match' in str(error)
            else:
                raise AssertionError('Unlisted archive file accepted')
        checks.append('unlisted_archive_file_rejected')
    result = {'checks': checks, 'passed': True,
        'base_commit': BASE, 'target_commit': installed_patch['target_commit'],
        'deployment_file_count': len(new_metadata['files'])}
    save(RELEASE / 'installer_verification.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
