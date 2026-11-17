#!/usr/bin/env python3
"""Run offline validation for an immutable, terminal local trial."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('trial', type=Path)
    args = parser.parse_args()
    trial = args.trial.resolve()
    assert json.loads((trial / 'state.json').read_text())['status'] == 'complete'
    declaration = json.loads((trial / 'declaration.json').read_text())
    source = Path(declaration['source_root'])
    for name, expected in declaration['payload_sha256'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == expected, name
    evidence = trial / 'offline_validation'
    evidence.mkdir(exist_ok=False)
    shutil.copytree(trial.parent / 'final_validation/offline_guard', evidence / 'offline_guard')
    wheel = Path('/Users/mao/projects/dagv2_deploy/20261015_webwalker_v4_access_v4_experiment/release/dagbt_webwalker_v4_experiment/deps/pypdf-6.1.3-py3-none-any.whl')
    env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               HF_DATASETS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=os.pathsep.join([str(evidence / 'offline_guard'), str(source), str(wheel)]),
               WEBWALKER_VALIDATION_NETWORK_LOG=str(evidence / 'blocked_network.jsonl'))
    for key in ('DAG_LLM_API_KEY', 'DAG_EMBED_API_KEY', 'DAG_RERANK_API_KEY',
                'OPENAI_API_KEY', 'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN'):
        env.pop(key, None)
    command = [sys.executable, '-m', 'pytest', '-q', 'tests', '-p', 'no:cacheprovider',
               '--junitxml=' + str(evidence / 'pytest-junit.xml')]
    receipt = dict(started_utc=datetime.now(timezone.utc).isoformat(), source_root=str(source),
                   command=command, dependency_wheels={str(wheel): hashlib.sha256(wheel.read_bytes()).hexdigest()},
                   network_policy='Python socket audit hook allows loopback and AF_UNIX only; HF offline flags enabled',
                   log=str(evidence / 'pytest.log'), status='running')
    destination = evidence / 'pytest_receipt.json'
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    started = time.monotonic()
    with (evidence / 'pytest.log').open('xb') as log:
        result = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT)
    receipt.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                   elapsed_seconds=time.monotonic() - started, exit_code=result.returncode,
                   status='passed' if result.returncode == 0 else 'failed',
                   log_sha256=hashlib.sha256((evidence / 'pytest.log').read_bytes()).hexdigest(),
                   blocked_network_attempts=len((evidence / 'blocked_network.jsonl').read_text().splitlines())
                   if (evidence / 'blocked_network.jsonl').exists() else 0)
    if (evidence / 'pytest-junit.xml').exists():
        tree = ET.parse(evidence / 'pytest-junit.xml')
        receipt['test_suites'] = [dict(s.attrib) for s in tree.getroot().iter('testsuite')]
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    print((evidence / 'pytest.log').read_text()[-10000:])
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
