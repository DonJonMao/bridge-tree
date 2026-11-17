"""Offline packaging/installer scaffold regression, without building a release."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

import build_patch
import verify_installer


def main():
    templates = build_patch.RELEASE / 'patch'
    template_hashes = {name: build_patch.sha(templates / name)
                       for name in ('apply_patch.py', 'install_and_smoke.sh')}
    with tempfile.TemporaryDirectory(prefix='a48-packaging-fixture-') as tmp:
        tmp = Path(tmp).resolve()
        root = tmp / 'repo'
        root.mkdir()
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
        git('init', '-q')
        git('config', 'user.name', 'Offline fixture')
        git('config', 'user.email', 'offline@example.invalid')
        original = {
            'dagbt/existing.py': 'value = 1\n',
            'dagbt/unchanged.py': 'value = 2\n',
            'docs/PERSONAMEM_A48_SCOPE_FIX_20261012.md': 'Fixture docs\n',
        }
        for name, content in original.items():
            file = root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content)
        git('add', '.')
        git('commit', '-qm', 'baseline')
        base = git('rev-parse', 'HEAD')
        old_meta = tmp / 'old-deployment.json'
        build_patch.save(old_meta, {'source_commit': base,
                                   'files': {name: build_patch.describe(root / name)
                                             for name in original}})
        (root / 'dagbt/existing.py').write_text('value = 3\n')
        (root / 'dagbt/new_a.py').write_text('new_a = 1\n')
        (root / 'dagbt/new_b.py').write_text('new_b = 2\n')
        (root / 'docs/PERSONAMEM_A48_SCOPE_FIX_20261012.md').write_text('Updated docs\n')
        git('add', '.')
        git('commit', '-qm', 'patched')
        release = tmp / 'release'
        patch_dir = release / 'patch'
        (patch_dir / 'payload/configs').mkdir(parents=True)
        (patch_dir / 'payload/configs/credentials.local.json').write_text('non-secret stale sentinel\n')
        (patch_dir / 'stray-private-sentinel.txt').write_text('non-secret root sentinel\n')
        for name in template_hashes:
            shutil.copy2(templates / name, patch_dir / name)
        build_patch.save(release / 'validation.json', {'offline_fixture': True})
        for module in (build_patch, verify_installer):
            module.ROOT, module.BASE, module.RELEASE, module.OLD_META = root, base, release, old_meta
        with contextlib.redirect_stdout(io.StringIO()):
            build_patch.main()
        assert not (patch_dir / 'payload/configs/credentials.local.json').exists()
        assert (patch_dir / 'stray-private-sentinel.txt').exists()
        assert all(build_patch.sha(patch_dir / name) == expected
                   for name, expected in template_hashes.items())
        with contextlib.redirect_stdout(io.StringIO()):
            verify_installer.main()
        result = json.loads((release / 'installer_verification.json').read_text())
        checks = result['checks'] + ['stale_payload_removed', 'installer_templates_preserved',
                                    'root_stray_file_excluded']
        manifest = json.loads((patch_dir / 'patch.json').read_text())
        archive_path = release / 'dagv2_personamem_a48_v3_1_patch.tar.gz'
        for variant in ('duplicate', 'symlink'):
            hostile = tmp / (variant + '.tar.gz')
            with tarfile.open(archive_path) as source, tarfile.open(hostile, 'w:gz') as destination:
                for member in source.getmembers():
                    if variant == 'symlink' and member.name == 'README.md':
                        member.type = tarfile.SYMTYPE
                        member.linkname = '/tmp/outside'
                        member.size = 0
                        destination.addfile(member)
                    else:
                        destination.addfile(member, source.extractfile(member))
                if variant == 'duplicate':
                    member = source.getmember('README.md')
                    destination.addfile(member, source.extractfile(member))
            with tarfile.open(hostile) as archive:
                try:
                    verify_installer.verify_archive_members(archive, manifest['files'])
                except AssertionError:
                    checks.append(variant + '_archive_member_rejected')
                else:
                    raise AssertionError(variant + ' accepted')
        spec = importlib.util.spec_from_file_location('fixture_installer', patch_dir / 'apply_patch.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        for name in ('../outside', '/tmp/outside', ''):
            try:
                installer.safe_path(root, name)
            except ValueError:
                pass
            else:
                raise AssertionError('Unsafe path accepted: ' + name)
        (root / 'symlink').symlink_to(tmp / 'outside', target_is_directory=True)
        try:
            installer.safe_path(root, 'symlink/new.py')
        except ValueError:
            checks.append('unsafe_and_symlink_paths_rejected')
        else:
            raise AssertionError('Symlink parent accepted')
        result = {'passed': True, 'scope': 'isolated offline fixture only', 'checks': checks,
                  'production_release_built': False, 'network_calls': 0}
    # Keep only counts/check names; the fixture never contains credentials.
    build_patch.save(Path(__file__).with_name('packaging_fixture_verification.json'), result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
