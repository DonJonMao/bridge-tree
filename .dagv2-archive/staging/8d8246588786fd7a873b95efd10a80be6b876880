from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time

root = Path('/Users/mao/projects/dagv2-webwalker-v4')
evidence = Path(__file__).parent
assert json.loads((evidence.parent / 'candidate_occurrence_feedback/state.json').read_text())['status'] == 'complete', 'Wait for generation and scoring to finish before the full test suite loads dataset fixtures'
wheel = Path('/Users/mao/projects/dagv2_deploy/20261015_webwalker_v4_access_v4_experiment/release/dagbt_webwalker_v4_experiment/deps/pypdf-6.1.3-py3-none-any.whl')
env = os.environ.copy()
env.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1',
    'PYTHONDONTWRITEBYTECODE': '1',
    'PYTHONPATH': os.pathsep.join([str(evidence / 'offline_guard'), str(root), str(wheel)]),
    'WEBWALKER_VALIDATION_NETWORK_LOG': str(evidence / 'blocked_network.jsonl')})
for key in ('DAG_LLM_API_KEY', 'DAG_EMBED_API_KEY', 'DAG_RERANK_API_KEY', 'OPENAI_API_KEY', 'HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN'):
    env.pop(key, None)
command = [sys.executable, '-m', 'pytest', '-q', 'tests', '-p', 'no:cacheprovider', '--junitxml=' + str(evidence / 'pytest-junit.xml')]
started = datetime.now(timezone.utc).isoformat()
t0 = time.monotonic()
receipt = {'started_utc': started, 'source_root': str(root),
    'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'python': sys.executable, 'command': command,
    'dependency_wheels': {str(wheel): hashlib.sha256(wheel.read_bytes()).hexdigest()},
    'network_policy': 'Python socket audit hook permits loopback and AF_UNIX only; HF/Transformers offline flags enabled; no real-model smoke requested',
    'log': str(evidence / 'pytest.log'), 'status': 'running'}
(evidence / 'pytest_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
with (evidence / 'pytest.log').open('wb') as log:
    proc = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
receipt.update({'finished_utc': datetime.now(timezone.utc).isoformat(),
    'elapsed_seconds': time.monotonic() - t0, 'exit_code': proc.returncode,
    'status': 'passed' if proc.returncode == 0 else 'failed',
    'log_sha256': hashlib.sha256((evidence / 'pytest.log').read_bytes()).hexdigest(),
    'blocked_network_attempts': len((evidence / 'blocked_network.jsonl').read_text().splitlines()) if (evidence / 'blocked_network.jsonl').exists() else 0})
if (evidence / 'pytest-junit.xml').exists():
    import xml.etree.ElementTree as ET
    tree = ET.parse(evidence / 'pytest-junit.xml')
    receipt['test_suites'] = [dict(s.attrib) for s in tree.getroot().iter('testsuite')]
    receipt['junit_sha256'] = hashlib.sha256((evidence / 'pytest-junit.xml').read_bytes()).hexdigest()
(evidence / 'pytest_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2), flush=True)
print((evidence / 'pytest.log').read_text()[-20000:], flush=True)
sys.exit(proc.returncode)
