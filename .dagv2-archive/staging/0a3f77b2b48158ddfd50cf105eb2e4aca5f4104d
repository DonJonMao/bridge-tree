"""Generation-only budget/token/paid-plan audit; standard library and local files."""
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


def lines(path):
    try:
        raw = path.read_text().splitlines()
    except FileNotFoundError:
        return []
    result = []
    for line in raw:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def candidate_identity(link):
    return digest({key: value for key, value in link.items() if key != 'id'})


def request(path):
    data = read_json(path)
    if not data:
        return None
    user = None
    for message in data.get('payload', {}).get('messages', []):
        if message.get('role') == 'user':
            try:
                user = json.loads(message['content'])
            except (KeyError, json.JSONDecodeError):
                pass
    output = None
    choices = data.get('response', {}).get('choices', [])
    if choices:
        raw = choices[0].get('message', {}).get('content', '').strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
        try:
            output = json.loads(raw)
        except json.JSONDecodeError:
            output = {'raw_response_not_json': True}
    return {'request_ref': path.stem, 'stage': data.get('stage'),
            'user': user, 'response': output,
            'attempts': data.get('attempts', []),
            'tokenization_validation': data.get('tokenization_validation')}


def task(path):
    events = lines(path / 'fusion_events.jsonl')
    calls = lines(path / 'call_events.jsonl')
    requests = [request(p) for p in (path / 'requests').glob('*.json')]
    requests = [row for row in requests if row]
    requests.sort(key=lambda row: int(row['stage'][1]))
    by_call = {int(row['stage'][1]): row for row in requests}
    budget = {}
    for event in events:
        if event.get('event') == 'budget_reserved':
            budget[event['kind']] = event['used']
    plans = []
    for event in events:
        if event.get('event') != 'web_navigation_plan_decided':
            continue
        paid = by_call.get(event.get('logical_call_index'))
        checks = {'paid_request_record_present': paid is not None}
        inp, response, alternative = {}, {}, None
        if paid:
            inp = paid['user'] if isinstance(paid['user'], dict) else {}
            response = paid['response'] if isinstance(paid['response'], dict) else {}
            checks.update({
                'actual_paid_wire_identity_matches': digest(inp) == event.get('request_identity'),
                'raw_model_plan_preserved': response.get('exploration_plan') == event.get('plan'),
                'raw_model_primary_selection_preserved': response.get('link_id') == event.get('selected_link_id'),
                'paid_plan_identity_matches': digest({
                    'request_identity': event.get('request_identity'),
                    'selection': event.get('selected_link_id'), 'plan': event.get('plan'),
                    'response_ref': paid['request_ref']}) == event.get('paid_plan_ref')})
            alternative = next((link for link in inp.get('links', [])
                                if link['id'] == event.get('plan', {}).get('alternative_link_id')), None)
            primary = next((link for link in inp.get('links', [])
                            if link['id'] == event.get('selected_link_id')), None)
            if event.get('plan', {}).get('alternative_link_id') is not None:
                checks['alternative_from_same_admitted_wire'] = alternative is not None
                checks['alternative_differs_from_primary_url'] = bool(
                    primary and alternative and primary['url'] != alternative['url'])
            checks['navigation_marked_nonfactual'] = event.get('navigation_is_not_fact_support') is True
        consumed = [row for row in events if row.get('event') == 'web_branch_plan_consumed'
                    and row.get('paid_plan_ref') == event.get('paid_plan_ref')]
        invalidated = [row for row in events if row.get('event') == 'web_branch_plan_invalidated'
                       and row.get('paid_plan_ref') == event.get('paid_plan_ref')]
        checks['consumed_at_most_once'] = len(consumed) <= 1
        for consume in consumed:
            checks['consumed_original_occurrence_matches_paid_alternative'] = bool(alternative and
                candidate_identity(consume['link']) == candidate_identity(alternative))
            checks['consumption_adds_no_navigation_model_call'] = consume.get('new_navigation_model_call') is False
            checks['consumption_is_nonfactual'] = consume.get('navigation_is_not_fact_support') is True
            # _consume emits its audit event immediately before the normal
            # _visit reservation. A live snapshot can end between those writes.
            following = [row for row in events if row.get('sequence', -1) > consume['sequence']]
            if following:
                checks['next_event_reserves_normal_web_action'] = (
                    following[0].get('event') == 'budget_reserved' and
                    following[0].get('kind') == 'web_actions' and
                    following[0].get('stage') == 'web_visit')
        plans.append({'decision': event, 'checks': checks, 'consumed': consumed,
                      'invalidated': invalidated, 'all_observed_checks_pass': all(checks.values())})
    validations = [row for row in events if row.get('event') == 'tokenization_usage_validation']
    contexts = [row for row in events if row.get('event') == 'model_context_budget']
    tokenizer = [row for row in events if row.get('event') == 'tokenization_count']
    result = read_json(path / 'result.json')
    terminal = None
    if result:
        diagnostics = result.get('diagnostics', {})
        ledger = diagnostics.get('ledger', {})
        terminal = {'answer_status': result.get('answer', {}).get('status'),
                    'ledger': {key: ledger.get(key) for key in ('limits', 'used', 'remaining')},
                    'errors': diagnostics.get('errors'),
                    'reasoning_call_count': diagnostics.get('reasoning_call_count')}
    return {'question_id': path.parent.name, 'arm': path.name,
            'request_records': len(requests),
            'logical_model_request_starts': sum(row.get('event') == 'reasoning_request_started' for row in events),
            'cache_hits': sum(row.get('event') == 'cache_hit' for row in events),
            'logical_llm_budget_matches_request_starts': budget.get('llm', 0) == sum(
                row.get('event') == 'reasoning_request_started' for row in events),
            'completed_response_records': sum(row['response'] is not None for row in requests),
            'request_stages': [row['stage'] for row in requests],
            'started_call_records': len([row for row in calls if row.get('event') == 'call_started']),
            'llm_physical_attempt_records': sum(len(row['attempts']) for row in requests),
            'llm_failed_attempts': [attempt for row in requests for attempt in row['attempts']
                                    if attempt.get('http_status', 200) != 200],
            'budget_reserved_used': budget,
            'token_usage_validation_counts': dict(Counter(row.get('status') for row in validations)),
            'usage_mismatches': [row for row in validations if row.get('status') != 'matched'],
            'model_context_checks': len(contexts),
            'over_context': [row for row in contexts if row.get('within_estimated_budget') is False],
            'tokenizer_failed_http_attempts': sum(row.get('failed_http_attempts', 0) for row in tokenizer),
            'tokenizer_http_retries': sum(row.get('http_retries', 0) for row in tokenizer),
            'plan_audits': plans,
            'runtime_terminal_result': terminal,
            'last_event_sequence': events[-1].get('sequence') if events else None}


report = {'updated_utc': datetime.now(timezone.utc).isoformat(),
          'scope': 'generation-only budget/token/paid-plan audit; no evaluation, references, input, manifest, declaration or raw pages read',
          'driver_state': read_json(STAGE / 'state.json'),
          'generation_progress': read_json(OUTPUT / 'progress.json'),
          'tasks': [task(path) for path in sorted((OUTPUT / 'tasks').glob('*/*')) if path.is_dir()]}
target = STAGE / 'analysis' / 'candidate_budget_plan_monitor.json'
temporary = target.with_suffix('.json.tmp')
temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
temporary.replace(target)
print(json.dumps({'updated_utc': report['updated_utc'],
                  'driver_status': (report['driver_state'] or {}).get('status'),
                  'progress': report['generation_progress'],
                  'tasks': [{key: row[key] for key in (
                      'question_id', 'arm', 'request_records', 'budget_reserved_used',
                      'logical_model_request_starts', 'logical_llm_budget_matches_request_starts',
                      'token_usage_validation_counts', 'over_context',
                      'tokenizer_failed_http_attempts', 'tokenizer_http_retries')} |
                      {'plans': len(row['plan_audits']),
                       'plan_consumptions': sum(len(plan['consumed']) for plan in row['plan_audits']),
                       'failed_plan_audits': [plan for plan in row['plan_audits'] if not plan['all_observed_checks_pass']]}
                      for row in report['tasks']]}, ensure_ascii=False, indent=2))
