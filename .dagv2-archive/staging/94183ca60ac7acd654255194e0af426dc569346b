"""Minimal q0 runtime-only wrong-entity reading evidence; no labels or scoring."""
from datetime import datetime, timezone
import json
from pathlib import Path


STAGE = Path(__file__).resolve().parent.parent
PATH = STAGE / 'output/tasks/wwqa-0000/dagbt_joint_memory_v1/fusion_events.jsonl'
CONFLICT = ('Use its\nentity_scope and time_scope strings exactly only when that scope actually applies;\n'
            'otherwise return unknown/irrelevant.')


def parse(raw):
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
    return json.loads(raw)


events = [json.loads(line) for line in PATH.read_text().splitlines()]
records = []
for event in events:
    if event.get('event') != 'reasoning_response' or event.get('logical_call_index') not in (6, 7, 8):
        continue
    data = json.loads(next(message['content'] for message in event['messages'] if message['role'] == 'user'))
    sources = data['source_spans']
    if 'source_span_columns' in data:
        sources = [dict(zip(data['source_span_columns'], row)) for row in sources]
    for source in sources:
        if source['doc_id'] in data.get('source_documents', {}):
            source.update(data['source_documents'][source['doc_id']])
    records.append({
        'logical_call_index': event['logical_call_index'], 'operation': event['operation'],
        'original_question': data['original_question'], 'requested_scopes': data['requested_scopes'],
        'original_source': next(source for source in sources if source['id'] == 's48'),
        'common_wrong_scope_unknown_or_irrelevant_sentence_in_actual_system':
            CONFLICT in event['messages'][0]['content'],
        'web_source_review_present': 'web_source_review' in data,
        'web_reading_protocol_diagnostics': data.get('web_reading_protocol_diagnostics'),
        'web_repair_edit_scope': data.get('web_repair_edit_scope'),
        'required_failed_ids': [{'variable': row['variable'], 'id': row['id'], 'feedback': row['feedback']}
                                 for row in data.get('repair_scope', {}).get('failed', [])],
        'response': parse(event['raw_output'])})
report = {
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Only q0 joint generated read/repair calls6/7/8 and their exact originals; no labels or scoring.',
    'common_presentation_conflict': CONFLICT,
    'records': records,
    'findings': [
        'Call6 emits support from a different project while its reason explicitly denies target applicability; other fields emit source-free unknown from the same mismatch.',
        'Call7 retains required IDs and changes all three to source-free unknown. Call8 satisfies source-reference format with s48 but still explicitly says the source describes another project.',
        'Current source-reference diagnostics explain a necessary format constraint, not relevance. The model repairs citation syntax without fixing evidence disposition.',
        'New source-review cards do not trigger here: no prior known binding, old evidence obligation or offered frozen reference yet exists.',
        'The unchanged common sentence directs a scope mismatch to unknown/irrelevant, conflicting with the Web new-window no_relevant_evidence disposition.'],
    'generic_next_iteration_options_not_applied': [
        'Guarded reconciliation of the exact common scope-mismatch sentence for ordinary Web retrieval; preserve the true in-scope incomplete and existing-source review cases.',
        'Show mutually exclusive empty-new-window versus genuine scoped incomplete dispositions adjacent to the authoritative requested scope, using invented contrasting examples rather than entity keyword heuristics.',
        'For a required failed draft about an unrelated source, explain the legal same-ID irrelevant review when warranted; never force source padding into an unknown row merely to satisfy source_ids.',
        'Do not automatically classify other entities from names, delete required IDs, override source semantics, or settle real partial/counter evidence.']}
out = STAGE / 'analysis/q0_wrong_entity_reading_audit.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'report': str(out), 'record_count': len(records),
                  'common_conflict_confirmed_in_calls': [row['logical_call_index'] for row in records
                    if row['common_wrong_scope_unknown_or_irrelevant_sentence_in_actual_system']]}, indent=2))
