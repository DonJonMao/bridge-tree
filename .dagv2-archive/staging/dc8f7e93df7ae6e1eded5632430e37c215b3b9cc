"""Terminal q1 residual runtime audit, deliberately excluding evaluation files."""
from datetime import datetime, timezone
import json
from pathlib import Path

from dagbt.history_wire import unpack as unpack_history
from dagbt.review_wire import unpack as unpack_review


STAGE = Path(__file__).resolve().parent.parent
ARM = STAGE / 'output/tasks/wwqa-0001/dagbt_residual_memory_v2'
events = [json.loads(line) for line in (ARM / 'fusion_events.jsonl').read_text().splitlines()]
snapshot = json.loads((ARM / 'fusion_snapshot.json').read_text())['diagnostics']
assert any(event.get('event') == 'terminal_published' for event in events)
records = []
for event in events:
    if event.get('event') != 'reasoning_response' or event.get('operation') not in ('joint_read', 'joint_read_repair'):
        continue
    data = unpack_history(unpack_review(json.loads(next(message['content'] for message in event['messages']
                                                       if message['role'] == 'user'))))
    sources = data['source_spans']
    if 'source_span_columns' in data:
        sources = [dict(zip(data['source_span_columns'], row)) for row in sources]
    for source in sources:
        if source['doc_id'] in data.get('source_documents', {}):
            source.update(data['source_documents'][source['doc_id']])
    raw = event['raw_output'].strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0]
    records.append({
        'call_index': event['logical_call_index'], 'operation': event['operation'],
        'requested_slots': data['requested_slots'], 'known_observations': data['known_observations'],
        'evidence_obligations': data.get('evidence_obligations', []),
        'current_source_review_cards': data.get('web_source_review'),
        'all_current_originals': sources,
        'failed_batch_reviews': data.get('failed_batch_reviews', []),
        'repair_scope': data.get('repair_scope'), 'web_repair_edit_scope': data.get('web_repair_edit_scope'),
        'response': json.loads(raw)})
joint = snapshot['joint_reading']
report = {
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Only terminal q1 residual generation runtime originals, model requests/outputs and fact/reading snapshots; no references or scoring.',
    'terminal_fact_state': snapshot['fact_state'],
    'terminal_evidence_obligations': joint['evidence_obligations'],
    'terminal_failed_batch_reviews': joint['failed_batch_reviews'],
    'completed_reads': [event for event in events if event.get('event') == 'joint_read_completed'],
    'branch_invalidations': [event for event in events if event.get('event') == 'web_branch_plan_invalidated'],
    'terminal': next(event for event in events if event.get('event') == 'terminal_published'),
    'findings': [
        'Root calls2/3 already combine no_relevant_evidence with named unknown observations and empty source_ids, violating the required empty disposition.',
        'SC-documents calls5/6 repeat those required IDs in the same invalid shape and attempt failed-batch resolution. They do not produce a valid sourced partial/unknown observation.',
        'All completed reads have valid_rows=0 and complete=false. Final facts/routes remain empty, both variable versions remain0, and evidence_obligations is empty.',
        'Two failed_batch_reviews remain, retaining the invalid named drafts. Their required source closure expands from the root window as additional originals are offered, reaching43 sources at terminal.',
        'Source-review cards trigger0 times because this run has no existing known binding, evidence-obligation source or offered frozen source review. The prior time-correction mechanism is therefore not exercised.',
        'Branch invalidation occurs after another failed read; browser-specific material/candidate hash attribution is audited independently by the navigation agent.',
        'The next worktree-only scope reconciliation removes residual common guidance that sends non-applicable entity/event text to unknown. It also explains same-ID irrelevant review for genuinely unrelated originals. It does not auto-normalize the mixed shape or discard required drafts.'],
    'records': records}
out = STAGE / 'analysis/q1_residual_terminal_reading_audit.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'report': str(out), 'records': len(records),
    'cards': sum(record['current_source_review_cards'] is not None for record in records),
    'routes': len(snapshot['fact_state']['routes']), 'evidence_obligations': len(joint['evidence_obligations']),
    'failed_batch_review_count': len(joint['failed_batch_reviews']),
    'failed_source_counts': [len(record['source_ids']) for record in joint['failed_batch_reviews']]}, indent=2))
