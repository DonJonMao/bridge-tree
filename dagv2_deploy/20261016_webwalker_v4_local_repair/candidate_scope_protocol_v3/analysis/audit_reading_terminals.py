"""Summarize generated terminal reading states only, without evaluation input."""
from datetime import datetime, timezone
import json
from pathlib import Path


STAGE = Path(__file__).resolve().parent.parent
summaries = []
for path in sorted((STAGE / 'output/tasks').glob('wwqa-000[01]/*/fusion_snapshot.json')):
    snapshot = json.loads(path.read_text())
    data = snapshot['diagnostics']
    joint = data['joint_reading']
    state = data['fact_state']
    events = [json.loads(line) for line in (path.parent / 'fusion_events.jsonl').read_text().splitlines()]
    terminals = [event for event in events if event.get('event') == 'terminal_published']
    if not terminals:
        continue
    summaries.append({
        'task': path.parent.parent.name, 'arm': path.parent.name,
        'terminal': terminals[-1], 'snapshot_path': str(path),
        'ledger_used': data['ledger']['used'],
        'fact_state': {key: state[key] for key in ('facts', 'versions', 'routes', 'pending_variables')},
        'reading_batch_count': len(joint['batches']),
        'incomplete_batch_count': sum(not record['complete'] for record in joint['batches']),
        'valid_reading_rows': sum(record['valid_rows'] for record in joint['batches']),
        'evidence_obligations': joint['evidence_obligations'],
        'failed_batch_reviews': joint['failed_batch_reviews'],
        'accepted_empty_slot_reads': len(joint['web_navigation_reads']),
        'semantic_warning': 'Empty-window protocol validity and repair reduction do not establish that navigation found the requested facts.'})
report = {'created_utc': datetime.now(timezone.utc).isoformat(),
          'scope': 'Only generated q0/q1 runtime terminal, fact/reading snapshots and metered counts; no references, eval or scoring.',
          'terminals': summaries}
out = STAGE / 'analysis/reading_terminal_summary.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'report': str(out), 'terminals': [
    {key: value for key, value in row.items() if key in (
        'task', 'arm', 'ledger_used', 'reading_batch_count', 'incomplete_batch_count',
        'valid_reading_rows', 'evidence_obligations', 'failed_batch_reviews', 'accepted_empty_slot_reads')}
    for row in summaries]}, ensure_ascii=False, indent=2))
