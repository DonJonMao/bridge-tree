#!/usr/bin/env python3
"""Install isolated PrefEval assets and reuse local credentials without model calls."""
import argparse
import errno
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import install_personamem_v4 as assets

CONFIG = 'configs/prefeval-v4.json'
DEFAULT_BASE = Path.home() / 'dagbt_runs/20261014_personamem_v4_experiment/dagv2'


def install(root=ROOT, base=DEFAULT_BASE):
    root, base = Path(root).resolve(), Path(base).expanduser().resolve()
    if root == base or root in base.parents or base in root.parents or not base.is_dir():
        raise assets.InstallError('Use a separate deployment; --base must be an existing PersonaMem deployment')
    assets.CONFIG = CONFIG
    release = assets.release_manifest(root)
    config = assets.read_json(assets.within(root, CONFIG), 'PrefEval config')
    from dagbt.runner import validate_config, validate_experiment_options
    from dagbt.methods import RESIDUAL_V2
    from dagbt.prefeval import validate_dataset
    from types import SimpleNamespace
    validate_config(config)
    validate_experiment_options(config, SimpleNamespace(arms=['original', RESIDUAL_V2], limit=None))
    validate_dataset(root)  # Public data only; does not open gold/raw official rows.
    source_config = next((base / name for name in ('configs/personamem-v4.json',
        'configs/residual-memory.personamem16k.json') if (base / name).is_file()), None)
    base_config = assets.read_json(source_config, 'Base config') if source_config else {}
    rows, missing = assets.frozen_assets(root, base)
    credential_path, credential_data = assets.plan_credentials(root, base, config, base_config)
    assets.ensure_unlisted_sources_absent(root, release['files'], rows, credential_path)
    created = []
    try:
        for source, dest, expected in missing:
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source, dest)
            except OSError as exc:
                if exc.errno != errno.EXDEV:
                    raise
                # Separate filesystems cannot hard-link. Copy only missing frozen vectors.
                with source.open('rb') as inp, dest.open('xb') as out:
                    shutil.copyfileobj(inp, out)
            created.append(dest)
            assets.verify_file(dest, expected, 'Installed frozen vector')
        if credential_data is not None:
            credential_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(credential_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(credential_path)
            with os.fdopen(fd, 'wb') as f:
                f.write(credential_data)
        assets.release_manifest(root)
        assets.frozen_assets(root, base)
        assets.plan_credentials(root, base, config, base_config)
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return {'assets_installed': True, 'release': release['release_name'],
            'base_modified': False, 'network_requests': 0, 'reused_frozen_vectors': len(missing),
            'credentials': 'environment_or_private_local_file',
            'prefeval_index': 'built automatically before generation in this new deployment',
            'next': 'bash scripts/prefeval_v4.sh smoke OR bash scripts/prefeval_v4.sh full'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=DEFAULT_BASE)
    args = parser.parse_args()
    try:
        print(json.dumps(install(base=args.base), ensure_ascii=False, indent=2))
    except Exception as exc:
        message = str(exc) if isinstance(exc, assets.InstallError) else 'Installation failed: ' + type(exc).__name__
        print(json.dumps({'assets_installed': False, 'error': message}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
