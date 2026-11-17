"""Audit q0 generation navigation plans only; never read evaluation or inputs."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from nav_monitor_generation import (STAGE, OUTPUT, digest, read_json, read_lines,
                                input_payload, decode_response, pages_for)


def candidate_identity(link):
    return digest({key: value for key, value in link.items() if key != 'id'})


def audit_arm(path):
    events = read_lines(path / 'fusion_events.jsonl')
    pages = pages_for('wwqa-0000')
    requests = {}
    raw_decisions = []
    source_errors = []
    read_rows, reading_span_errors, reading_span_exposures = [], [], 0
    for request_path in (path / 'requests').glob('*.json'):
        request = read_json(request_path)
        if not request or not request.get('stage'):
            continue
        sequence = int(request['stage'][1])
        inp, out = input_payload(request), decode_response(request)
        requests[sequence] = (request, inp, out)
        if request['stage'][0] != 'web_navigate':
            if request['stage'][0] in ('joint_read', 'joint_read_repair', 'audit_joint'):
                read_rows.append({'call': sequence, 'operation': request['stage'][0],
                    'request_ref': request_path.stem, 'has_response': 'response' in request,
                    'response': out,
                    'source_review_cards': inp.get('web_source_review', {}).get('cards', []),
                    'repair_scope': inp.get('repair_scope'),
                    'protocol_diagnostics': inp.get('web_reading_protocol_diagnostics')})
                columns = inp.get('source_span_columns')
                for raw_source in inp.get('source_spans', []):
                    source = dict(zip(columns, raw_source)) if columns else dict(raw_source)
                    source.update(inp.get('source_documents', {}).get(source.get('doc_id'), {}))
                    page = pages.get(source.get('doc_id'))
                    if page:
                        reading_span_exposures += 1
                        document = page['document']
                        passage = (document['title'] or page['url']) + '\n' + document['text']
                        if passage[source['start']:source['end']] != source['text']:
                            reading_span_errors.append({'call': sequence, 'source': source})
            continue
        for link in inp.get('links', []):
            page = pages.get(link['source_doc_id'])
            if not page:
                source_errors.append({'call': sequence, 'error': 'missing_original_page', 'link': link})
                continue
            context = link.get('source_context')
            if context:
                document = page['document']
                passage = (document['title'] or page['url']) + '\n' + document['text']
                if passage[context['start']:context['end']] != context['text']:
                    source_errors.append({'call': sequence, 'error': 'original_context_mismatch', 'link': link})
        if not isinstance(out, dict):
            continue
        plan = out.get('exploration_plan')
        primary = next((link for link in inp.get('links', []) if link['id'] == out.get('link_id')), None)
        alternative = next((link for link in inp.get('links', [])
                            if isinstance(plan, dict) and link['id'] == plan.get('alternative_link_id')), None)
        raw_decisions.append({'call': sequence, 'request_ref': request_path.stem,
            'has_response': 'response' in request, 'request_identity': digest(inp),
            'repair': 'validation_feedback' in inp, 'selected_link_id': out.get('link_id'),
            'primary': primary, 'alternative': alternative, 'plan': plan,
            'reason_characters': len(plan.get('reason', '')) if isinstance(plan, dict) else None,
            'alternative_reason_characters': len(plan.get('alternative_reason') or '') if isinstance(plan, dict) else None})
    raw_decisions.sort(key=lambda row: row['call'])
    read_rows.sort(key=lambda row: row['call'])
    plan_events = [event for event in events if event.get('event') == 'web_navigation_plan_decided']
    chains = []
    for event in plan_events:
        call = event['logical_call_index']
        request, inp, out = requests[call]
        alternative = next((link for link in inp.get('links', [])
                            if link['id'] == event['plan'].get('alternative_link_id')), None)
        selected = next((link for link in inp.get('links', []) if link['id'] == event['selected_link_id']), None)
        terminal_events = [row for row in events if row.get('paid_plan_ref') == event['paid_plan_ref']
                           and row.get('event') in ('web_branch_plan_consumed', 'web_branch_plan_invalidated')]
        consumed = [row for row in terminal_events if row['event'] == 'web_branch_plan_consumed']
        endpoint = terminal_events[0]['sequence'] if terminal_events else None
        between = [row for row in events if row['sequence'] > event['sequence']
                   and (endpoint is None or row['sequence'] < endpoint)]
        primary_follow = next((row for row in between if row.get('event') == 'web_link_followed'
                               and selected and row.get('link', {}).get('url') == selected['url']), None)
        chains.append({'paid_plan_ref': event['paid_plan_ref'], 'decision': event,
            'primary': selected, 'alternative': alternative,
            'request_identity_matches_actual_paid_wire': event['request_identity'] == digest(inp),
            'accepted_plan_matches_raw_response': event['plan'] == out.get('exploration_plan'),
            'primary_follow_event': primary_follow,
            'terminal_events': terminal_events,
            'pending_in_latest_generation_log': alternative is not None and not terminal_events,
            'one_use': len(consumed) <= 1,
            'consumed_original_candidate_matches_paid_choice': all(alternative is not None
                and candidate_identity(row['link']) == candidate_identity(alternative) for row in consumed),
            'reads_between_decision_and_endpoint': [row for row in between
                if row.get('event') == 'joint_read_completed'],
            'navigation_calls_between_decision_and_endpoint': [row['logical_call_index'] for row in between
                if row.get('event') == 'reasoning_request_started' and row.get('operation') == 'web_navigate'],
            'semantic_events_between': [row for row in between
                if any(part in row.get('event', '') for part in ('fact', 'obligation', 'integrat', 'binding', 'counter'))]})
    budget = {}
    for event in events:
        if event.get('event') == 'budget_reserved':
            budget[event['kind']] = event['used']
    result = read_json(path / 'result.json')
    generation_result = None
    if result:
        diagnostics = result.get('diagnostics', {})
        generation_result = {'answer': result.get('answer'),
            'ledger': {key: diagnostics.get('ledger', {}).get(key) for key in ('limits', 'used', 'remaining')},
            'errors': diagnostics.get('errors'), 'reasoning_call_count': diagnostics.get('reasoning_call_count'),
            'audit_complete': diagnostics.get('audit_complete')}
    return {'arm': path.name, 'budget_used': budget, 'raw_navigation_decisions': raw_decisions,
            'plan_chains': chains, 'original_link_coordinate_errors': source_errors,
            'reader_responses': read_rows, 'reading_span_exposures_checked': reading_span_exposures,
            'reading_span_coordinate_errors': reading_span_errors,
            'protocol_errors': [event for event in events if event.get('event') == 'protocol_error'],
            'event_counts': dict(Counter(event.get('event') for event in events)),
            'generation_result': generation_result}


def main():
    report = {'updated_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'q0 generation artifacts only; no evaluation/reference/input/manifest reads',
              'driver_state': read_json(STAGE / 'state.json'),
              'arms': [audit_arm(path) for path in sorted((OUTPUT / 'tasks' / 'wwqa-0000').glob('*'))
                       if path.is_dir()]}
    target = STAGE / 'analysis' / 'q0_branch_plan_audit.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'updated_utc': report['updated_utc'], 'arms': [{
        'arm': arm['arm'], 'budget_used': arm['budget_used'],
        'navigation_calls': len(arm['raw_navigation_decisions']),
        'accepted_plans': len(arm['plan_chains']),
        'plan_outcomes': [{'call': chain['decision']['logical_call_index'],
            'primary_url': (chain['primary'] or {}).get('url'),
            'alternative_url': (chain['alternative'] or {}).get('url'),
            'terminal_events': [event['event'] for event in chain['terminal_events']],
            'pending': chain['pending_in_latest_generation_log']} for chain in arm['plan_chains']],
        'coordinate_errors': len(arm['original_link_coordinate_errors']),
        'generation_result': arm['generation_result']} for arm in report['arms']]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
