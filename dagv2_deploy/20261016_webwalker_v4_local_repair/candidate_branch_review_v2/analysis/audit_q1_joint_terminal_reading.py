"""Audit terminal q1 JOINT runtime only; scoring/reference files are never read."""
from datetime import datetime, timezone
import json
from pathlib import Path


STAGE = Path(__file__).resolve().parent.parent
ARM = STAGE / 'output/tasks/wwqa-0001/dagbt_joint_memory_v1'
events = [json.loads(line) for line in (ARM / 'fusion_events.jsonl').read_text().splitlines()]
terminal = [event for event in events if event.get('event') == 'terminal_published']
if not terminal or not (ARM / 'fusion_snapshot.json').exists():
    print(json.dumps({'terminal': False, 'event_count': len(events)}))
    raise SystemExit(0)
snapshot = json.loads((ARM / 'fusion_snapshot.json').read_text())['diagnostics']
models, timeline = [], []
for event in events:
    if event.get('event') != 'reasoning_response' or event.get('operation') not in ('joint_read', 'joint_read_repair'):
        continue
    data = json.loads(next(message['content'] for message in event['messages'] if message['role'] == 'user'))
    raw = event['raw_output'].strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0]
    output = json.loads(raw)
    entry = {'call_index': event['logical_call_index'], 'operation': event['operation'],
             'requested_slots': data['requested_slots'],
             'source_review_card_count': len(data.get('web_source_review', {}).get('cards', [])),
             'observations': output.get('slots'),
             'current_failed_batch_ids': [record['id'] for record in data.get('failed_batch_reviews', [])]}
    timeline.append(entry)
    if any(slot.get('observations') for slot in output.get('slots', [])):
        models.append(event)  # Exact actual system/schema, source wire and raw output.
joint = snapshot['joint_reading']
report = {
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Only terminal q1 JOINT generated runtime events/model inputs/outputs and fact/reading snapshots; no references or scoring.',
    'terminal': terminal[-1], 'terminal_fact_state': snapshot['fact_state'],
    'terminal_evidence_obligations': joint['evidence_obligations'],
    'terminal_failed_batch_reviews': joint['failed_batch_reviews'],
    'reading_timeline': timeline,
    'completed_reads': [event for event in events if event.get('event') == 'joint_read_completed'],
    'exact_nonempty_model_records': models,
    'summary': {'reading_requests': len(timeline),
                'card_call_count': sum(entry['source_review_card_count'] > 0 for entry in timeline),
                'routes': len(snapshot['fact_state']['routes']),
                'evidence_obligations': len(joint['evidence_obligations']),
                'failed_batch_review_count': len(joint['failed_batch_reviews']),
                'failed_source_counts': [len(record['source_ids']) for record in joint['failed_batch_reviews']]},
    'findings': [
        'Early reads complete as empty with no fact or evidence issue. The PC Chairs Report read explicitly distinguishes its review-process event from the requested statement-agreement event.',
        'When that read emits named source-free unknown rows alongside no_relevant_evidence, the model creates an invalid mixed disposition. Subsequent repairs preserve the same invalid shape and try failed-batch settlement.',
        'The model does not silently get a validated old time binding from these drafts. Repeated source-free mixed rows are protocol failures rather than semantic evidence obligations.',
        'Source-review card trigger and final fact/issue counts are recorded explicitly above; no causal model-quality conclusion follows from a mechanism not exercised.',
        'The next worktree-only guarded scope reconciliation targets ordinary absence/inapplicable text versus genuine scoped incomplete evidence and legal required-draft correction. It does not rewrite model outputs or waive durable review requirements.']}
out = STAGE / 'analysis/q1_joint_terminal_reading_audit.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'report': str(out), **report['summary']}, indent=2))
