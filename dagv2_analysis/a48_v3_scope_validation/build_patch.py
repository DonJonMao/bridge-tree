"""Assemble and verify a small, exact-base standalone deployment patch."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path('/Users/mao/projects/dagv2-personamem-a48')
BASE = 'da64d56250733bc7a87942f6a5389b04a00176bd'
RELEASE = Path('/Users/mao/projects/dagv2_deploy/20261012_a48dc8d_v3_1')
OLD_META = Path('/Users/mao/projects/dagv2_deploy/20261011_a48dc8d_v3/patch/payload/DEPLOYMENT.json')


def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def describe(path):
    return {'sha256': sha(path), 'bytes': path.stat().st_size}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit == BASE or subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise RuntimeError('Commit all reviewed release files before packaging')
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASE, commit], cwd=ROOT, text=True).splitlines()
    if any(not name.startswith(('dagbt/', 'tests/', 'docs/'))
           and name not in {'scripts/demo_residual_memory.py',
                            'configs/residual-memory.personamem16k.json'} for name in changed):
        raise RuntimeError('Unexpected production patch scope')
    patch_dir = RELEASE / 'patch'
    payload = patch_dir / 'payload'
    metadata = json.loads(OLD_META.read_text())
    validation = json.loads((RELEASE / 'validation.json').read_text())
    metadata.update(source_commit=commit, patch_base_commit=BASE,
        release_name='personamem_a48_v3_1', validation=validation)
    # Payload is generated output. Never reuse files from an earlier build or
    # remove the hand-maintained installer templates beside it.
    if payload.is_symlink():
        payload.unlink()
    elif payload.exists():
        shutil.rmtree(payload)
    payload.mkdir(parents=True, exist_ok=True)
    for name in changed:
        source = ROOT / name
        if not source.is_file():
            raise RuntimeError('Patch installer does not support deletions: ' + name)
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        metadata['files'][name] = describe(source)
    for name, expected in metadata['files'].items():
        if describe(ROOT / name) != expected:
            raise RuntimeError('Unexpected unmodified deployment mismatch: ' + name)
    save(payload / 'DEPLOYMENT.json', metadata)
    changed.append('DEPLOYMENT.json')
    save(patch_dir / 'patch.json', {'base_commit': BASE, 'target_commit': commit,
        'base_deployment_sha256': sha(OLD_META),
        'files': {name: describe(payload / name) for name in changed}})
    shutil.copy2(ROOT / 'docs/PERSONAMEM_A48_SCOPE_FIX_20261012.md', patch_dir / 'README.md')
    shutil.copy2(RELEASE / 'validation.json', patch_dir / 'validation.json')
    tar = RELEASE / 'dagv2_personamem_a48_v3_1_patch.tar.gz'
    # Publish only the declared payload and fixed installer artifacts. A stray
    # credential, stale source file or local report must never enter the tar.
    members = ['apply_patch.py', 'install_and_smoke.sh', 'README.md',
               'validation.json', 'patch.json', *('payload/' + name for name in changed)]
    with tarfile.open(tar, 'w:gz') as archive:
        for name in sorted(members):
            path = patch_dir / name
            if path.is_symlink() or not path.is_file():
                raise RuntimeError('Missing or unsafe release member: ' + name)
            archive.add(path, arcname=name, recursive=False)
    tar.with_name(tar.name + '.sha256').write_text(sha(tar) + '  ' + tar.name + '\n')
    print(json.dumps({'target_commit': commit, 'patch_bytes': tar.stat().st_size,
        'sha256': sha(tar), 'changed_files': changed}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
