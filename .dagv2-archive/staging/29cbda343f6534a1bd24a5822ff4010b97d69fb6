#!/usr/bin/env python3
"""Verify and install a recovered WebWalker release without external services."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
import tarfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', required=True)
    parser.add_argument('--work', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--browser-vendor')
    parser.add_argument('--browser-cache')
    args = parser.parse_args()
    archive, work, base = map(Path, (args.archive, args.work, args.base))
    work.mkdir(parents=True, exist_ok=False)
    extracted, target = work / 'extracted', work / 'installed'
    started = datetime.now(timezone.utc).isoformat()
    archive_hash = sha(archive)
    with tarfile.open(archive) as tf:
        members = tf.getmembers()
        names = [m.name for m in members]
        assert len(names) == len(set(names)), 'Duplicate archive entries'
        for m in members:
            p = PurePosixPath(m.name)
            assert not p.is_absolute() and '..' not in p.parts
            assert p.parts[0] == 'dagbt_webwalker_v4_experiment'
            assert m.isfile() or m.isdir(), 'Links and special files are not allowed'
        manifest = json.load(tf.extractfile('dagbt_webwalker_v4_experiment/bundle_manifest.json'))
        expected = {'bundle_manifest.json', 'install_and_smoke.sh', 'install_webwalker.py',
                    'README.md', 'V4_ALIGNMENT.md', manifest['pdf_wheel']}
        expected.update('payload/' + p for p in manifest['payload_sha256'])
        validation = 'dagbt_webwalker_v4_experiment/validation.json' in names
        if validation:
            expected.add('validation.json')
        actual = {'/'.join(PurePosixPath(m.name).parts[1:]) for m in members if m.isfile()}
        assert actual == expected, sorted(actual ^ expected)
        assert not any('credentials.local' in p or '__pycache__' in p or p.endswith('.pyc') for p in actual)
        extracted.mkdir()
        tf.extractall(extracted, filter='data')
    bundle = extracted / 'dagbt_webwalker_v4_experiment'
    assert manifest['web_source_commit'] == '8a491f36aa129d6a869a8df6906f788b03ca0e06'
    assert len(manifest['baseline_source_sha256']) == 107
    assert len(manifest['payload_sha256']) == 147
    for path, expected_hash in manifest['payload_sha256'].items():
        assert sha(bundle / 'payload' / path) == expected_hash
    assert sha(bundle / manifest['pdf_wheel']) == manifest['pdf_wheel_sha256']
    before = {path: sha(base / path) for path in manifest['baseline_source_sha256']}
    assert before == manifest['baseline_source_sha256']
    install_argv = [sys.executable, str(bundle / 'install_webwalker.py'),
                    '--target', str(target), '--base', str(base)]
    with (work / 'install.log').open('xb') as log:
        subprocess.run(install_argv, stdout=log, stderr=subprocess.STDOUT, check=True)
    for path, expected_hash in manifest['payload_sha256'].items():
        assert sha(target / path) == expected_hash
    assert {path: sha(base / path) for path in before} == before
    env = dict(os.environ, DAGBT_PYTHON=sys.executable, PYTHONPATH='.',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    with (work / 'offline.log').open('xb') as log:
        subprocess.run(['bash', 'scripts/run_webwalker.sh', 'offline'], cwd=target,
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    output = (work / 'offline.log').read_text()
    assert output.count('"status": "ok"') == 2
    assert output.count('"completion_kind": "certified_symbolic"') == 2
    assert '"external_network_used": false' in output
    browser_ready = None
    if args.browser_vendor and args.browser_cache:
        env.update(PYTHONPATH=args.browser_vendor, PLAYWRIGHT_BROWSERS_PATH=args.browser_cache)
        code = ('from playwright.sync_api import sync_playwright\n'
                'with sync_playwright() as p:\n'
                ' b=p.chromium.launch(headless=True)\n'
                ' page=b.new_page();page.set_content("<p>Browser ready</p>")\n'
                ' assert page.inner_text("body")=="Browser ready"\n'
                ' b.close()\n'
                'print("Local Chromium launch and HTML rendering passed")\n')
        with (work / 'browser.log').open('xb') as log:
            subprocess.run([sys.executable, '-c', code], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        browser_ready = True
    assert sha(archive) == archive_hash
    receipt = {'status': 'passed', 'started_utc': started,
               'finished_utc': datetime.now(timezone.utc).isoformat(),
               'archive': str(archive), 'archive_sha256': archive_hash,
               'platform': platform.platform(), 'python': sys.version,
               'source_commit': manifest['web_source_commit'],
               'safe_members': len(members), 'payload_files_verified': 147,
               'baseline_files_verified': 107, 'private_credentials_in_archive': False,
               'validation_in_archive': validation, 'fresh_install_exit_code': 0,
               'offline_exit_code': 0, 'offline_certified_arms': 2,
               'external_model_or_website_used': False, 'local_browser_ready': browser_ready,
               'linux_tested': False, 'source_baseline_unchanged': True,
               'logs': {p.name: sha(p) for p in work.glob('*.log')}}
    (work / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
