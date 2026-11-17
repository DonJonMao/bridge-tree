"""Read only generated runtime artifacts; never open evaluation/reference inputs."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

STAGE = Path(__file__).resolve().parent.parent
OUTPUT = STAGE / 'output'


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def read_lines(path):
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return []
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def decode_response(data):
    choices = data.get('response', {}).get('choices', [])
    raw = choices[0].get('message', {}).get('content') if choices else None
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {'unparsed_raw_output': raw}


def input_payload(data):
    for message in data.get('payload', {}).get('messages', []):
        if message.get('role') == 'user':
            try:
                value = json.loads(message.get('content', ''))
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    return {}


def pages_for(qid):
    pages = {}
    for path in (OUTPUT / 'pages' / qid).glob('*.json'):
        data = read_json(path)
        if not data or 'document_hash' not in data:
            continue
        doc_id = 'web-' + digest([data['url'], data['document_hash']])[:24]
        pages[doc_id] = data
    return pages


def occurrence_upgrades(inp, pages):
    """Identify the actual older-body/newer-menu occurrence in a sent wire."""
    order = list(reversed(inp.get('local_exploration', {}).get('visited_doc_ids', [])))
    upgraded = []
    for link in inp.get('links', []):
        source = link.get('source_doc_id')
        if source not in order or link.get('source_region') not in ('main', 'content'):
            continue
        newer = order[:order.index(source)]
        shadowed = []
        for doc_id in newer:
            page = pages.get(doc_id, {})
            context = page.get('document', {}).get('link_contexts', {}).get(link['url'])
            if context and context.get('region') not in ('main', 'content'):
                shadowed.append({'doc_id': doc_id, 'url': page.get('url'),
                                 'source_region': context.get('region')})
        if shadowed:
            page = pages.get(source, {})
            document = page.get('document', {})
            passage = document.get('title', '') + '\n' + document.get('text', '')
            context = link.get('source_context', {})
            upgraded.append({
                'link_id': link.get('id'), 'url': link.get('url'), 'text': link.get('text'),
                'source_doc_id': source, 'source_region': link.get('source_region'),
                'source_page_url': page.get('url'), 'source_context': context,
                'source_context_matches_cached_original':
                    passage[context.get('start', 0):context.get('end', 0)] == context.get('text'),
                'newer_noncontent_occurrences': shadowed})
    return upgraded


def request_summary(path, pages):
    data = read_json(path)
    if not data:
        return None
    stage = data.get('stage', [])
    inp = input_payload(data)
    out = decode_response(data)
    row = {'request_ref': path.stem, 'stage': stage,
           'has_response': 'response' in data, 'response': out,
           'physical_attempt_count': len(data.get('attempts', [])),
           'tokenization_validation': data.get('tokenization_validation')}
    if stage and stage[0] == 'web_navigate':
        feedback = inp.get('reading_feedback', {})
        row.update(link_count=len(inp.get('links', [])),
                   selected_link=next((link for link in inp.get('links', [])
                                       if isinstance(out, dict) and link['id'] == out.get('link_id')), None),
                   older_content_occurrence_upgrades=occurrence_upgrades(inp, pages),
                   local_exploration=inp.get('local_exploration'),
                   reading_feedback=feedback)
    if 'repair_scope' in inp:
        row['repair_scope'] = inp['repair_scope']
    if 'web_reading_protocol_diagnostics' in inp:
        row['web_reading_protocol_diagnostics'] = inp['web_reading_protocol_diagnostics']
    return row


def task_summary(path):
    qid, arm = path.parent.name, path.name
    events = read_lines(path / 'fusion_events.jsonl')
    requests = [request_summary(p, pages_for(qid)) for p in (path / 'requests').glob('*.json')]
    requests = [r for r in requests if r]
    requests.sort(key=lambda r: int(r['stage'][1]) if len(r['stage']) > 1 else -1)
    budget = {}
    for event in events:
        if event.get('event') == 'budget_reserved':
            budget[event['kind']] = event['used']
    notable = []
    for event in events:
        name = event.get('event', '')
        if (any(word in name for word in ('error', 'failed', 'failure', 'exhaust', 'pause', 'stall'))
                or name in ('web_link_followed', 'joint_read_completed', 'web_browser_fallback')
                or (event.get('status') in ('failed', 'mismatch', 'rejected'))):
            notable.append(event)
    # These names contain runtime generation results only. Deliberately do not
    # glob/open eval, reference, input, manifest, or declaration artifacts.
    generation_results = {}
    for name in ('result.json', 'output.json', 'error.json', 'completed.json'):
        value = read_json(path / name)
        if value is not None:
            if name == 'result.json':
                diagnostics = value.get('diagnostics', {})
                generation_results[name] = {
                    'answer': value.get('answer'), 'seconds': value.get('seconds'),
                    'ledger': {key: diagnostics.get('ledger', {}).get(key)
                               for key in ('limits', 'used', 'remaining')},
                    'errors': diagnostics.get('errors'),
                    'reasoning_call_count': diagnostics.get('reasoning_call_count'),
                    'audit_complete': diagnostics.get('audit_complete')}
            else:
                generation_results[name] = value
    log = path / 'worker.log'
    log_tail = log.read_text().splitlines()[-10:] if log.exists() else []
    return {'question_id': qid, 'arm': arm,
            'request_count': len(requests), 'requests': requests,
            'budget_reserved_used': budget,
            'event_counts': dict(Counter(e.get('event') for e in events)),
            'last_event_sequence': events[-1].get('sequence') if events else None,
            'last_event_elapsed_seconds': events[-1].get('elapsed_seconds') if events else None,
            'notable_generation_events': notable,
            'generation_results': generation_results, 'worker_log_tail': log_tail}


def main():
    report = {'updated_utc': datetime.now(timezone.utc).isoformat(),
              'monitor_scope': 'generation-only; no evaluation/reference files read',
              'stage': str(STAGE), 'driver_state': read_json(STAGE / 'state.json'),
              'generation_progress': read_json(OUTPUT / 'progress.json'),
              'tasks': [task_summary(path) for path in sorted((OUTPUT / 'tasks').glob('*/*'))
                        if path.is_dir()]}
    path = STAGE / 'analysis' / 'candidate_generation_monitor.json'
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)
    print(json.dumps({
        'updated_utc': report['updated_utc'],
        'driver_state': report['driver_state'], 'progress': report['generation_progress'],
        'tasks': [{'question_id': task['question_id'], 'arm': task['arm'],
                   'requests': task['request_count'], 'budget': task['budget_reserved_used'],
                   'navigation': [{'stage': r['stage'],
                                   'selected_url': (r.get('selected_link') or {}).get('url'),
                                   'upgraded_occurrence_count': len(r.get('older_content_occurrence_upgrades', []))}
                                  for r in task['requests'] if r['stage'][0] == 'web_navigate'],
                   'protocol_diagnostic_calls': [r['stage'] for r in task['requests']
                                                 if r.get('web_reading_protocol_diagnostics')],
                   'notable_event_names': dict(Counter(e['event'] for e in task['notable_generation_events'])),
                   'generation_result': task['generation_results']}
                  for task in report['tasks']]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
