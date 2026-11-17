#!/usr/bin/env python3
"""Package the fixed two-dataset v4 experiments without private credentials."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'e6677081cdfb33c01db3aaa274a497168f314f78'
NAME = 'dagbt_benchmarks_v4_experiment'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def baseline_sources():
    paths = subprocess.check_output(
        ['git', 'ls-tree', '-r', '--name-only', BASELINE], cwd=ROOT, text=True).splitlines()
    baseline = {}
    for path in paths:
        if not (path.endswith('.py') and path.split('/')[0] in
                ('dagbt', 'dagv2', 'dagresolve', 'package', 'vendor')):
            continue
        original = subprocess.check_output(['git', 'show', BASELINE + ':' + path], cwd=ROOT)
        expected = hashlib.sha256(original).hexdigest()
        if sha(ROOT / path) != expected:
            raise ValueError('Do not package changed baseline core: ' + path)
        baseline[path] = expected
    return baseline


def payload_paths(baseline):
    paths = set(baseline)
    for pattern in ('dagbt/webwalker_*.py', 'dagbt/browsecomp_*.py',
                    'tests/test_webwalker*.py', 'tests/test_browsecomp*.py',
                    'tests/test_benchmark*.py'):
        paths.update(str(p.relative_to(ROOT)) for p in ROOT.glob(pattern))
    paths.update(('dagbt/benchmark_suite.py', 'configs/webwalker-v4.json',
                  'configs/browsecomp-plus-v4.json', 'scripts/run_webwalker.sh',
                  'scripts/run_browsecomp_plus.sh', 'scripts/run_benchmarks.sh',
                  'scripts/webwalker_offline_smoke.py', 'scripts/browsecomp_offline_smoke.py',
                  'scripts/install_webwalker_browser.py',
                  'scripts/webwalker_diagnose.py', 'scripts/demo_residual_memory.py',
                  'scripts/demo_local_terminal.py', 'scripts/package_benchmarks.py',
                  'scripts/install_webwalker.py', 'scripts/prepare_browsecomp_plus.py',
                  'docs/BENCHMARKS_UPLOAD.md'))
    for name in ('webwalkerqa', 'browsecomp_plus'):
        directory = ROOT / 'data' / name
        if not (directory / 'manifest.json').is_file():
            raise ValueError('Prepared dataset manifest is missing: ' + str(directory))
        if name == 'browsecomp_plus':
            for filename in ('questions.jsonl', 'evaluation_only.json', 'corpus.sqlite3', 'manifest.json'):
                path = directory / filename
                if not path.is_file() or path.is_symlink():
                    raise ValueError('Fixed BrowseComp-Plus runtime artifact is missing: ' + str(path))
                paths.add(str(path.relative_to(ROOT)))
            continue
        for path in directory.rglob('*'):
            if (path.is_file() and not path.is_symlink()
                    and not any(p.startswith('.') or p == '__pycache__'
                                for p in path.relative_to(directory).parts)
                    and not path.name.endswith(('.tmp', '.part', '.download', '-wal', '-shm'))):
                paths.add(str(path.relative_to(ROOT)))
    return sorted(paths)


def installer_script(mode):
    return '''#!/usr/bin/env bash
set -euo pipefail
TASK_BUNDLE="$(cd "$(dirname "$0")" && pwd)"
TASK_TARGET="${1:-${DAGBT_TARGET:-$HOME/dagbt_runs/20261016_dual_benchmark_v4_v3/dagv2}}"
TASK_PYTHON="${DAGBT_PYTHON:-}"
if [[ -z "$TASK_PYTHON" ]]; then
  if [[ -x "$TASK_TARGET/.venv/bin/python" ]]; then
    TASK_PYTHON="$TASK_TARGET/.venv/bin/python"
  elif [[ -x "$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python" ]]; then
    TASK_PYTHON="$HOME/dagbt_runs/20260930_v3/dagv2/.venv/bin/python"
  else
    TASK_PYTHON="python3"
  fi
fi
"$TASK_PYTHON" "$TASK_BUNDLE/install_webwalker.py" --target "$TASK_TARGET" --base "${DAGBT_PERSONAMEM_BASE:-$HOME/dagbt_runs/20261014_personamem_v4_experiment/dagv2}"
cd "$TASK_TARGET"
if [[ "${2:-with-browser}" != "--no-browser" ]]; then
  "$TASK_PYTHON" scripts/install_webwalker_browser.py --target "$TASK_TARGET"
fi
DAGBT_PYTHON="$TASK_PYTHON" bash scripts/run_benchmarks.sh offline
DAGBT_PYTHON="$TASK_PYTHON" bash scripts/run_benchmarks.sh MODE
'''.replace('MODE', mode)


def build(destination, wheel, validation=None, *, hardlink_data=False):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    bundle = destination / NAME
    bundle.mkdir(exist_ok=False)
    baseline = baseline_sources()
    hashes = {}
    for relative in payload_paths(baseline):
        source, target = ROOT / relative, bundle / 'payload' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if hardlink_data and relative.startswith('data/'):
            os.link(source, target)
        else:
            shutil.copy2(source, target)
        hashes[relative] = sha(target)
    shutil.copy2(ROOT / 'scripts/install_webwalker.py', bundle / 'install_webwalker.py')
    shutil.copy2(ROOT / 'docs/BENCHMARKS_UPLOAD.md', bundle / 'README.md')
    (bundle / 'deps').mkdir()
    wheel = Path(wheel).resolve()
    shutil.copy2(wheel, bundle / 'deps' / wheel.name)
    manifest = {'baseline_commit': BASELINE,
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'baseline_source_sha256': baseline, 'payload_sha256': hashes,
                'pdf_wheel': 'deps/' + wheel.name, 'pdf_wheel_sha256': sha(wheel),
                'datasets': {
                    name: json.loads((ROOT / 'data' / name / 'manifest.json').read_text())
                    for name in ('webwalkerqa', 'browsecomp_plus')},
                'protocol': 'dual_benchmark_v4_sequential_v1',
                'bundle_revision': 3,
                'generation_before_scoring': True, 'credentials_in_bundle': False,
                'default_target': '~/dagbt_runs/20261016_dual_benchmark_v4_v3/dagv2'}
    (bundle / 'bundle_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    if validation:
        shutil.copy2(validation, bundle / 'validation.json')
    for name, mode in (('install_and_run.sh', 'full'), ('install_and_smoke.sh', 'smoke')):
        path = bundle / name
        path.write_text(installer_script(mode))
        path.chmod(0o755)
    archive = destination / (NAME + '.tar.gz')
    with tarfile.open(archive, 'w:gz', compresslevel=3) as tar:
        tar.add(bundle, arcname=NAME)
    # The corpus may have been linked for staging. Verify it stayed frozen
    # during packaging before publishing the archive checksum.
    for relative, expected in hashes.items():
        if sha(bundle / 'payload' / relative) != expected:
            archive.unlink(missing_ok=True)
            raise ValueError('Payload changed while packaging: ' + relative)
    archive_hash = sha(archive)
    archive.with_suffix(archive.suffix + '.sha256').write_text(archive_hash + '  ' + archive.name + '\n')
    result = {'archive': str(archive), 'sha256': archive_hash, 'bytes': archive.stat().st_size,
              'payload_files': len(hashes), 'verified_baseline_files': len(baseline),
              'datasets': ['webwalkerqa', 'browsecomp_plus'], 'credentials_in_bundle': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--pdf-wheel', required=True)
    parser.add_argument('--validation')
    parser.add_argument('--hardlink-data', action='store_true',
                        help='Stage frozen local data with hard links, then verify hashes after archiving')
    args = parser.parse_args()
    build(args.destination, args.pdf_wheel, args.validation, hardlink_data=args.hardlink_data)
