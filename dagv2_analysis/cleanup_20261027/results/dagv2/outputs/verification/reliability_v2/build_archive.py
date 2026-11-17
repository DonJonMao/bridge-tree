from pathlib import Path
import hashlib, json, os, shutil, subprocess, tarfile

root = Path('/Users/mao/projects/dagv2')
report_dir = root / 'outputs/verification/reliability_v2'
archive = root.parent / 'dagv2_bt_deploy_20260927_reliability_v2.tar.gz'
building = archive.with_name(archive.name + '.building')

def hash_file(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

paths = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().rstrip('\0').split('\0'))
paths.update(entry['path'] for entry in json.loads((root / 'original_manifest.json').read_text())['files'])
for relative in paths:
    path = Path(relative)
    assert not path.is_absolute() and '..' not in path.parts
    assert not set(path.parts).intersection({'.git', '.venv', '__pycache__', 'outputs'})
    assert not path.name.endswith('.local.json') and path.name != '.env'
    assert (root / relative).is_file() and not (root / relative).is_symlink(), relative
expected = {relative: hash_file(root / relative) for relative in sorted(paths)}
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
with tarfile.open(building, 'w:gz', compresslevel=6) as target:
    for relative in sorted(paths):
        source = root / relative
        info = target.gettarinfo(str(source), arcname='dagv2/' + relative)
        info.uid = info.gid = 0
        info.uname = info.gname = ''
        with source.open('rb') as handle:
            target.addfile(info, handle)
print('archive_built', flush=True)
extracted = report_dir / 'extracted'
extracted.mkdir(exist_ok=True)
seen = set()
with tarfile.open(building, 'r:gz') as source:
    for member in source:
        assert member.isfile() and member.name.startswith('dagv2/')
        relative = member.name[len('dagv2/'):]
        assert relative in expected and relative not in seen
        seen.add(relative)
        output = extracted / member.name
        output.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256()
        with source.extractfile(member) as handle, output.open('wb') as dest:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                h.update(chunk)
                dest.write(chunk)
        output.chmod(member.mode & 0o777)
        assert h.hexdigest() == expected[relative], relative
assert seen == set(expected)
print('archive_members_verified', len(seen), flush=True)
with (report_dir / 'extracted_offline_preflight.json').open('w') as output:
    subprocess.run([str(root / '.venv/bin/python'), '-m', 'dagbt.runner', 'preflight',
        '--config', str(extracted / 'dagv2/configs/paired.example.json'), '--offline-preflight'],
        cwd=extracted / 'dagv2', stdout=output, check=True)
# Promote only after every member and the actual extracted entrypoint pass.
archive_hash = hash_file(building)
report = {'commit': commit, 'archive': str(archive), 'sha256': archive_hash,
          'bytes': building.stat().st_size, 'member_count': len(seen),
          'verified_member_sha256': expected, 'extracted_offline_preflight': 'passed'}
(report_dir / 'archive_verification.json').write_text(json.dumps(report, indent=2) + '\n')
building.replace(archive)
archive.with_name(archive.name + '.sha256').write_text(archive_hash + '  ' + archive.name + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'verified_member_sha256'}), flush=True)
