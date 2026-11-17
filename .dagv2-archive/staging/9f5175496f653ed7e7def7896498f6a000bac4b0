import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_large_payload_install_streams_and_preserves_existing_files(tmp_path, monkeypatch):
    install = load_script('install_webwalker')
    bundle, base, target = (tmp_path / name for name in ('bundle', 'base', 'target'))
    (base / 'dagbt').mkdir(parents=True)
    (base / 'dagbt/engine.py').write_text('fixture base')
    (base / 'configs').mkdir()
    (base / 'configs/personamem-v4.json').write_text(json.dumps({'credentials_file': 'configs/credentials.local.json'}))
    (base / 'configs/credentials.local.json').write_text(json.dumps({'fixture_key': 'local-secret'}))
    (bundle / 'payload/configs').mkdir(parents=True)
    config = bundle / 'payload/configs/webwalker-v4.json'
    config.write_text(json.dumps({'credentials_file': 'configs/credentials.local.json'}))
    corpus = bundle / 'payload/data/browsecomp_plus/corpus.sqlite3'
    corpus.parent.mkdir(parents=True)
    with corpus.open('wb') as stream:
        for _ in range(8):
            stream.write(b'x' * 1024 * 1024)
    (bundle / 'deps').mkdir()
    wheel = bundle / 'deps/pypdf-fixture.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('pypdf/__init__.py', '# fixture dependency\n')
    hashes = {str(p.relative_to(bundle / 'payload')): install.sha(p) for p in (config, corpus)}
    (bundle / 'bundle_manifest.json').write_text(json.dumps({
        'baseline_source_sha256': {}, 'payload_sha256': hashes,
        'pdf_wheel': 'deps/' + wheel.name, 'pdf_wheel_sha256': install.sha(wheel),
        'baseline_commit': 'fixture'}))
    original = Path.read_bytes
    def bounded_read(path):
        if path.name == 'corpus.sqlite3':
            raise AssertionError('Large corpus was loaded wholesale')
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', bounded_read)
    install.install(bundle, target, base)
    assert install.sha(target / 'data/browsecomp_plus/corpus.sqlite3') == hashes['data/browsecomp_plus/corpus.sqlite3']
    assert (target / 'configs/credentials.local.json').stat().st_mode & 0o777 == 0o600
    install.install(bundle, target, base)  # exact install is idempotent
    (target / 'data/browsecomp_plus/corpus.sqlite3').write_text('preserved changed local corpus')
    with pytest.raises(ValueError, match='Preserving an existing different'):
        install.install(bundle, target, base)


def test_tiny_archive_contains_both_fixed_datasets_and_one_command_launchers(tmp_path, monkeypatch):
    package = load_script('package_benchmarks')
    source = tmp_path / 'source'
    paths = ['data/webwalkerqa/manifest.json', 'data/browsecomp_plus/manifest.json',
             'data/browsecomp_plus/corpus.sqlite3', 'configs/webwalker-v4.json']
    for relative in paths:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}' if path.suffix == '.json' else 'tiny corpus fixture')
    for relative in ('scripts/install_webwalker.py', 'docs/BENCHMARKS_UPLOAD.md'):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture artifact\n')
    (source / 'configs/credentials.local.json').write_text('PRIVATE_SENTINEL')
    wheel = tmp_path / 'pypdf-fixture.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('pypdf/__init__.py', '# fixture\n')
    monkeypatch.setattr(package, 'ROOT', source)
    monkeypatch.setattr(package, 'baseline_sources', lambda: {})
    monkeypatch.setattr(package, 'payload_paths', lambda baseline: paths)
    monkeypatch.setattr(package.subprocess, 'check_output', lambda *a, **k: 'fixture-head\n')
    result = package.build(tmp_path / 'release', wheel)
    archive_path = Path(result['archive'])
    assert result['sha256'] == hashlib.sha256(archive_path.read_bytes()).hexdigest()
    with tarfile.open(archive_path, 'r:gz') as archive:
        names = archive.getnames()
        assert any(name.endswith('/payload/data/browsecomp_plus/corpus.sqlite3') for name in names)
        assert any(name.endswith('/payload/data/webwalkerqa/manifest.json') for name in names)
        assert not any('credentials.local' in name or '/outputs/' in name for name in names)
        launcher = archive.extractfile(package.NAME + '/install_and_run.sh').read().decode()
        assert 'bash scripts/run_benchmarks.sh offline' in launcher
        assert 'bash scripts/run_benchmarks.sh full' in launcher
        assert 'nohup' not in launcher  # the Python coordinator owns detachment and its writer lock


def test_payload_list_includes_new_algorithm_tests_and_only_complete_corpus_files(tmp_path, monkeypatch):
    package = load_script('package_benchmarks')
    for name in ('webwalkerqa', 'browsecomp_plus'):
        directory = tmp_path / 'data' / name
        directory.mkdir(parents=True)
        (directory / 'manifest.json').write_text('{}')
    for name in ('questions.jsonl', 'evaluation_only.json', 'corpus.sqlite3', 'corpus.sqlite3.partial'):
        (tmp_path / 'data/browsecomp_plus' / name).write_text('fixture')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_webwalker_grounding.py').write_text('# regression')
    (tmp_path / 'tests/test_browsecomp_engine.py').write_text('# regression')
    monkeypatch.setattr(package, 'ROOT', tmp_path)
    paths = package.payload_paths({})
    assert 'tests/test_webwalker_grounding.py' in paths and 'tests/test_browsecomp_engine.py' in paths
    assert 'data/browsecomp_plus/corpus.sqlite3' in paths
    assert 'data/browsecomp_plus/corpus.sqlite3.partial' not in paths
    (tmp_path / 'data/browsecomp_plus/corpus.sqlite3').unlink()
    with pytest.raises(ValueError, match='runtime artifact is missing'):
        package.payload_paths({})


@pytest.mark.parametrize('entry', ['webwalker_offline_smoke.py', 'browsecomp_offline_smoke.py'])
def test_shipped_offline_http_entry_runs_both_arms_with_independent_source_review(entry):
    completed = subprocess.run([sys.executable, str(ROOT / 'scripts' / entry)],
                               cwd=ROOT, capture_output=True, text=True, timeout=60, check=True)
    result = json.loads(completed.stdout)
    assert result['external_network_used'] is False
    assert {row['arm'] for row in result['offline_http_smoke']} == {
        'dagbt_joint_memory_v1', 'dagbt_residual_memory_v2'}
    assert all(row['status'] == 'ok' and row['grounding_reviews'] >= 2
               and row['completion_kind'] == 'certified_symbolic'
               for row in result['offline_http_smoke'])
