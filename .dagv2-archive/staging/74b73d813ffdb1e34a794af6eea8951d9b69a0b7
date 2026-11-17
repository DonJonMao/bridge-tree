"""Audit only generated q1 runtime requests/responses, never labels or scoring."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from dagbt.history_wire import unpack as unpack_history
from dagbt.review_wire import unpack as unpack_review


STAGE = Path(__file__).resolve().parent.parent
TASK = STAGE / 'output' / 'tasks' / 'wwqa-0001'


def expand(wire):
    data = unpack_history(unpack_review(wire))
    if data.get('source_span_columns'):
        data['source_spans'] = [dict(zip(data['source_span_columns'], row))
                                for row in data['source_spans']]
    for source in data.get('source_spans', []):
        document = data.get('source_documents', {}).get(source['doc_id'])
        if document:
            source.update(deepcopy(document))
    return data


def parse_response(raw):
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0]
    try:
        return json.loads(raw)
    except ValueError:
        return {'unparsed_output': raw}


def audit_record(event, arm):
    data = expand(json.loads(next(message['content'] for message in event['messages']
                                  if message['role'] == 'user')))
    output = parse_response(event.get('raw_output'))
    originals = {source['id']: source for source in data.get('source_spans', [])}
    cards = data.get('web_source_review', {}).get('cards', [])
    card_checks = [{'source_id': card['original_source']['id'],
                    'matches_current_original_exactly':
                        card['original_source'] == originals.get(card['original_source']['id']),
                    'card': card} for card in cards]
    offered = {(entry['variable'], entry['id']): entry
               for entry in data.get('web_review_checklist', {}).get('offered_frozen_observations', [])}
    slots = output.get('slots', []) if isinstance(output, dict) else []
    slots = [slot for slot in slots if isinstance(slot, dict)] if isinstance(slots, list) else []
    obligations = []
    referenced_sources = {card['original_source']['id'] for card in cards}
    for issue in data.get('evidence_obligations', []):
        matches = [slot for slot in slots if slot.get('variable') == issue['variable']]
        slot = matches[0] if len(matches) == 1 else {}
        rows = [row for row in slot.get('observations', []) if isinstance(row, dict)]
        settled = [row for row in rows if row.get('stance') in ('support', 'contradiction', 'irrelevant')]
        new_coverage = {source for row in settled for source in row.get('source_ids', [])}
        refs = slot.get('reviewed_observation_ids', [])
        frozen = [offered[issue['variable'], identifier] for identifier in refs
                  if (issue['variable'], identifier) in offered]
        frozen_coverage = {source for row in frozen
                           if row['can_contribute_to_settled_source_coverage']
                           for source in row['source_ids']}
        required = set(issue.get('source_ids', []))
        referenced_sources.update(required)
        claimed = issue['id'] in slot.get('resolved_obligation_ids', [])
        obligations.append({
            'id': issue['id'], 'variable': issue['variable'], 'required_source_ids': sorted(required),
            'explicitly_claimed': claimed, 'new_settled_review_source_ids': sorted(new_coverage),
            'explicit_frozen_reference_source_ids': sorted(frozen_coverage),
            'missing_required_source_ids': sorted(required - new_coverage - frozen_coverage),
            'new_reviews': rows, 'offered_frozen_references_used': frozen,
            'unoffered_review_ids': [identifier for identifier in refs
                                     if (issue['variable'], identifier) not in offered],
            'coverage_is_arithmetic_only_not_semantic_certification': True})
    counters, supports, frozen_restatements = [], [], []
    for slot in slots:
        variable = slot.get('variable')
        for row in slot.get('observations', []):
            if not isinstance(row, dict):
                continue
            referenced_sources.update(row.get('source_ids', []))
            record = {'variable': variable, **row}
            if row.get('stance') == 'contradiction':
                counters.append(record)
            if row.get('stance') == 'support':
                supports.append(record)
            if (variable, row.get('id')) in offered:
                frozen_restatements.append(record)
    known = data.get('known_observations', [])
    for row in known:
        referenced_sources.update(row.get('source_ids', []))
    return {
        'arm': arm, 'call_index': event['logical_call_index'], 'operation': event['operation'],
        'requested_slots': data.get('requested_slots'),
        'known_observations': known, 'visible_original_source_ids': list(originals),
        'relevant_originals': [source for identifier, source in originals.items()
                               if identifier in referenced_sources],
        'source_review_cards': card_checks,
        'source_review_instruction_in_actual_system': 'web_source_review contains exact already-visible originals'
            in event['messages'][0]['content'],
        'contradictions': counters, 'supports': supports,
        'obligation_reviews': obligations, 'offered_frozen_restatements': frozen_restatements,
        'repair_scope': data.get('repair_scope'),
        'web_review_checklist': data.get('web_review_checklist'),
        'web_repair_edit_scope': data.get('web_repair_edit_scope'), 'response': output}


records, progress = [], []
for path in sorted(TASK.glob('*/fusion_events.jsonl')):
    arm = path.parent.name
    events = []
    for line in path.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass  # A concurrent final line may be unfinished.
    progress.append({'arm': arm, 'event_count': len(events),
                     'last_event': events[-1].get('event') if events else None,
                     'last_sequence': events[-1].get('sequence') if events else None,
                     'terminal_published': any(event.get('event') == 'terminal_published' for event in events)})
    records.extend(audit_record(event, arm) for event in events
                   if event.get('event') == 'reasoning_response'
                   and event.get('operation') in ('joint_read', 'joint_read_repair'))
records.sort(key=lambda row: (row['arm'], row['call_index']))
summary = {'created_utc': datetime.now(timezone.utc).isoformat(),
           'scope': 'Only q1 generated runtime read/repair records, originals, offers and output; no scoring or labels.',
           'progress': progress, 'record_count': len(records),
           'card_call_count': sum(bool(row['source_review_cards']) for row in records),
           'all_cards_match_current_originals': all(check['matches_current_original_exactly']
                for row in records for check in row['source_review_cards']),
           'contradiction_calls': [{'arm': row['arm'], 'call_index': row['call_index'],
                                  'contradictions': row['contradictions']} for row in records
                                  if row['contradictions']],
           'claims_missing_original_review': [{'arm': row['arm'], 'call_index': row['call_index'], **issue}
                for row in records for issue in row['obligation_reviews']
                if issue['explicitly_claimed'] and issue['missing_required_source_ids']],
           'records': records}
out = STAGE / 'analysis' / 'q1_reading_runtime_audit.json'
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({key: value for key, value in summary.items() if key != 'records'},
                 ensure_ascii=False, indent=2))
