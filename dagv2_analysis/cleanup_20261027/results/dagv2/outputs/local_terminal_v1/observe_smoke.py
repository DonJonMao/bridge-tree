"""Private sanitized live observation; never changes the smoke or reads labels."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).parent / 'smoke_3plus3_v2'
def read(path):
    return json.loads(path.read_text())

pid = read(root / 'pid.json')['pid']
process = subprocess.run(['ps', '-p', str(pid), '-o', 'pid,pgid,etime,state,command'], text=True, capture_output=True)
print(process.stdout.strip() or 'writer_pid_missing')
progress = read(root / 'progress.json')
print('run', {k: progress.get(k) for k in ('state', 'dataset', 'question_index', 'terminal_counts') if k in progress})
index = read(root / 'index_build/hotpotqa/progress.json')
print('index', {k: index.get(k) for k in ('status', 'completed_documents', 'documents', 'elapsed_seconds')})
for dataset in ('hotpotqa', 'personamem'):
    arm = root / dataset / 'dagbt_local_terminal_v1'
    print(dataset, 'terminal_statuses', [read(p)['answer']['status'] for p in sorted((arm / 'rows').glob('*.json'))])
    active = sorted((arm / 'attempts').glob('*/attempt-*/fusion_events.jsonl'), key=lambda p: p.stat().st_mtime)
    if active:
        counts, last, used, operation = {}, {}, {}, None
        for line in active[-1].read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get('event')
            counts[kind] = counts.get(kind, 0) + 1
            if kind == 'budget_reserved':
                used[event['kind']] = event['used']
            if kind == 'reasoning_request_started':
                operation = event['operation']
            last = {k: event[k] for k in ('event', 'operation', 'sequence', 'elapsed_seconds') if k in event}
        print(dataset, 'latest_attempt', {k: counts.get(k, 0) for k in ('reasoning_request_started', 'bridge_rerank_request', 'node_resolved')}, 'last', last)
        print(dataset, 'latest_budget_used', used)
        print(dataset, 'latest_generation_operation', operation)
