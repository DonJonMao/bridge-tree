#!/usr/bin/env python3
"""Read-only generation audit; never open references, scoring or request payloads.

Only progress.json and task result.json / fusion_events.jsonl /
call_events.jsonl / tokenization_events.jsonl / worker.log are read. Task answers
are not scored or printed. A controlled budget/unresolved result is a terminal
algorithm outcome, not evidence of a program crash.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import re


STAGE = Path('/Users/mao/projects/dagv2_deploy/20261016_dual_benchmark_v4')
DATASETS = ('webwalkerqa', 'browsecomp_plus')
CAPS = {'llm': 24, 'json_repairs': 6, 'web_actions': 36, 'search_actions': 36,
        'set_score': 0, 'reader': 0}
ZERO_COST_KINDS = ('ann', 'embedding_http', 'rerank_http', 'set_score', 'reader')
MODEL_KINDS = ('llm', 'embedding_http', 'rerank_http', 'reader')
BOUNDED = {'BudgetExceeded', 'InputOverflow'}
MODEL_PROTOCOL = {'ProtocolError', 'ProgramError', 'SupportError', 'RefusalError'}
SERVICE = {'ServiceError', 'ResponseError', 'TokenizationError', 'HTTPError',
           'URLError', 'TimeoutError', 'ConnectionError', 'ConnectionResetError',
           'ConnectionRefusedError', 'BrokenPipeError'}
WORKER = {'QuestionTimeout', 'WorkerFailed', 'MissingResult',
          'IncompletePreviousAttempt', 'KeyboardInterrupt', 'SystemExit'}
PROGRAM = {'AttributeError', 'TypeError', 'KeyError', 'IndexError', 'NameError',
           'UnboundLocalError', 'AssertionError', 'ImportError', 'ModuleNotFoundError',
           'SyntaxError', 'IndentationError', 'RecursionError', 'MemoryError'}
EVENT_FIELDS = {
    'event', 'kind', 'stage', 'amount', 'used', 'status', 'type', 'error_type',
    'operation', 'sequence', 'cache_hit', 'replayed_attempts', 'usage',
    'expected_prompt_tokens', 'observed_prompt_tokens', 'error_category',
    'http_attempts', 'http_retries', 'failed_http_attempts',
    'successful_http_requests', 'seconds', 'count', 'input_tokens_local',
    'output_token_reserve', 'context_tokens', 'total_tokens_local',
    'within_estimated_budget', 'token_count_is_estimate', 'max_model_len',
    'tokenization_request_sha256', 'tokenization_wire_sha256', 'response_ref',
    'request_ref', 'logical_call_index',
}


def integer(value):
    return type(value) is int and value >= 0


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def read_journal(path):
    """Snapshot each append-only journal; tolerate only an active trailing write."""
    if not path.exists():
        return [], {'exists': False, 'malformed_lines': [], 'partial_last_line': False}
    raw = path.read_bytes()
    lines = raw.splitlines()
    events, malformed, partial = [], [], False
    for index, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('Journal event is not an object')
        except (ValueError, UnicodeError):
            if index == len(lines) and not raw.endswith(b'\n'):
                partial = True
            else:
                malformed.append(index)
            continue
        events.append({key: value for key, value in row.items() if key in EVENT_FIELDS})
    return events, {'exists': True, 'bytes': len(raw), 'parsed_events': len(events),
                    'malformed_lines': malformed, 'partial_last_line': partial}


def reservations(events):
    total, discrepancies = Counter(), []
    for event in events:
        if event.get('event') != 'budget_reserved':
            continue
        kind, amount = event.get('kind'), event.get('amount')
        if not isinstance(kind, str) or not integer(amount):
            discrepancies.append('invalid_reservation_shape')
            continue
        total[kind] += amount
        if event.get('used') != total[kind]:
            discrepancies.append('noncontiguous_reservation_counter:' + kind)
    return total, sorted(set(discrepancies))


def error_category(name):
    if name in BOUNDED:
        return 'controlled_budget_or_input_guard'
    if name in MODEL_PROTOCOL:
        return 'model_protocol_or_content'
    if name in SERVICE:
        return 'service_or_token_accounting'
    if name in WORKER:
        return 'worker_failure_or_interruption'
    if name in PROGRAM:
        return 'program_exception'
    return 'unclassified_needs_review'


def audit_task(directory, dataset):
    findings = []

    def finding(category, code, severity='error', detail=None):
        row = {'category': category, 'code': code, 'severity': severity}
        if detail is not None:
            row['detail'] = detail
        findings.append(row)

    # Read terminal publication first. An active task that finishes during this
    # snapshot remains active here, avoiding false cross-file reconciliation.
    result = None
    try:
        result = read_json(directory / 'result.json')
    except (ValueError, OSError):
        finding('integrity', 'unreadable_terminal_result')
    terminal = isinstance(result, dict)
    journals, metadata = {}, {}
    for name in ('fusion_events.jsonl', 'call_events.jsonl', 'tokenization_events.jsonl'):
        journals[name], metadata[name] = read_journal(directory / name)
        state = metadata[name]
        if state['malformed_lines'] or (terminal and state['partial_last_line']):
            finding('integrity', 'malformed_journal', detail={
                'file': name, 'lines': state['malformed_lines'],
                'partial_last_line': state['partial_last_line']})
    events, calls, tokenizations = (journals[name] for name in (
        'fusion_events.jsonl', 'call_events.jsonl', 'tokenization_events.jsonl'))
    used, bad_reservations = reservations(events)
    for code in bad_reservations:
        finding('accounting', code)
    answer = (result or {}).get('answer', {})
    diagnostics = (result or {}).get('diagnostics', {})
    ledger = diagnostics.get('ledger')
    cost = diagnostics.get('cost', {})
    published_used = ledger.get('used', {}) if isinstance(ledger, dict) else None
    limits = ledger.get('limits', {}) if isinstance(ledger, dict) else {}
    cost_integrity = 'in_progress' if not terminal else 'reconciled'
    if terminal and published_used is None:
        cost_integrity = 'partial_from_journals_no_published_ledger'
        finding('accounting', 'terminal_has_no_published_ledger', 'warning')
    if terminal and published_used is not None:
        if not all(integer(value) for value in published_used.values()):
            finding('accounting', 'invalid_published_ledger_values')
        if {k:v for k,v in published_used.items() if v} != {k:v for k,v in used.items() if v}:
            finding('accounting', 'published_ledger_differs_from_journal',
                    detail={'published': published_used, 'journal': dict(used)})
        ledger_used, ledger_errors = reservations(ledger.get('events', []))
        if ledger_errors or dict(ledger_used) != dict(used):
            finding('accounting', 'published_ledger_events_differ_from_journal')
    for kind, cap in CAPS.items():
        if used[kind] > cap or (published_used or {}).get(kind, 0) > cap:
            finding('budget', 'protocol_cap_exceeded:' + kind)
        if kind in limits and (not integer(limits[kind]) or limits[kind] > cap):
            finding('budget', 'declared_limit_exceeds_protocol:' + kind)
    for kind, limit in limits.items():
        if integer(limit) and used[kind] > limit:
            finding('budget', 'declared_budget_exceeded:' + kind)
    for kind in ZERO_COST_KINDS:
        if used[kind] or (published_used or {}).get(kind, 0):
            finding('budget', 'zero_score_method_spent:' + kind)

    names = Counter(event.get('event') for event in events)
    operations = Counter(event.get('operation') for event in events
                         if event.get('event') == 'reasoning_request_started')
    expected_cost = {'llm_attempts': used['llm'], 'ann_calls': used['ann'],
                     'set_score_calls': used['set_score'],
                     'rerank_http_attempts': used['rerank_http'],
                     'json_repair_reservations': used['json_repairs'],
                     'generation_calls': names['reasoning_request_started']}
    for key, value in expected_cost.items():
        if key in cost and cost[key] != value:
            finding('accounting', 'published_cost_mismatch:' + key)

    responses = [event for event in events if event.get('event') == 'http_response']
    replay_charges = sum(event.get('replayed_attempts', 0) for event in events
                         if event.get('event') == 'cached_attempt_charge')
    model_reservations = sum(used[kind] for kind in MODEL_KINDS)
    physical_balance = model_reservations - replay_charges - used['http_attempts']
    if terminal and physical_balance != 0:
        finding('accounting', 'model_http_cache_charge_balance_differs',
                detail={'unpaired_model_reservations': physical_balance})
    if len(responses) > used['http_attempts']:
        finding('accounting', 'more_http_responses_than_reserved_attempts')
    usage_totals, missing_usage = Counter(), 0
    llm_responses = [event for event in responses if event.get('kind') == 'llm']
    for event in llm_responses:
        usage = event.get('usage')
        if not isinstance(usage, dict) or not all(integer(usage.get(key)) for key in
                                                ('prompt_tokens', 'completion_tokens')):
            missing_usage += 1
            continue
        usage_totals['prompt_tokens'] += usage['prompt_tokens']
        usage_totals['completion_tokens'] += usage['completion_tokens']
        if integer(usage.get('total_tokens')) and usage['total_tokens'] != (
                usage['prompt_tokens'] + usage['completion_tokens']):
            finding('accounting', 'response_usage_total_mismatch')
    if missing_usage:
        finding('accounting', 'successful_llm_response_missing_usage',
                detail={'responses': missing_usage})

    validations = [event for event in events
                   if event.get('event') == 'tokenization_usage_validation']
    validation_stages = Counter(event.get('stage') for event in validations)
    bad_validation = [event for event in validations
                      if event.get('status') != 'matched'
                      or not integer(event.get('expected_prompt_tokens'))
                      or event.get('expected_prompt_tokens') != event.get('observed_prompt_tokens')]
    if bad_validation:
        finding('token_accounting', 'exact_prompt_usage_validation_failed',
                detail={'events': len(bad_validation)})
    required_validation = Counter(event.get('stage') for event in responses
                                  if event.get('kind') not in ('embedding_http', 'rerank_http'))
    required_validation.update(event.get('stage') for event in events
                               if event.get('event') == 'request_cache_hit'
                               and event.get('kind') not in ('embedding_http', 'rerank_http'))
    missing_validation = required_validation - validation_stages
    if terminal and missing_validation:
        finding('token_accounting', 'successful_responses_missing_exact_usage_validation',
                detail=dict(missing_validation))
    observed_validation = Counter((event.get('stage'), event.get('observed_prompt_tokens'))
                                  for event in validations if event.get('status') == 'matched')
    response_prompts = Counter((event.get('stage'), event['usage']['prompt_tokens'])
                              for event in llm_responses if isinstance(event.get('usage'), dict)
                              and integer(event['usage'].get('prompt_tokens')))
    response_validation_gap = response_prompts - observed_validation
    if terminal and response_validation_gap:
        finding('token_accounting', 'response_usage_and_validation_event_disagree',
                detail=[{'stage': stage, 'prompt_tokens': count, 'responses': amount}
                        for (stage, count), amount in response_validation_gap.items()])
    token_errors = Counter(event.get('error_category') or event.get('status')
                           for event in tokenizations if event.get('status') != 'ok')
    if token_errors:
        finding('service', 'tokenization_http_failures', 'warning', dict(token_errors))
    for event in tokenizations:
        if event.get('status') == 'ok' and event.get('token_count_is_estimate') is not False:
            finding('token_accounting', 'tokenizer_result_is_not_exact')
            break
    fusion_tokens = [event for event in events if event.get('event') == 'tokenization_count']
    if terminal and used['llm']:
        for filename, records in (('call_events.jsonl', calls),
                                  ('tokenization_events.jsonl', tokenizations)):
            if not records:
                finding('accounting', 'charged_llm_has_no_journal:' + filename)
    def token_fingerprint(event):
        return tuple(event.get(key) for key in ('tokenization_request_sha256', 'status',
                                               'cache_hit', 'http_attempts'))
    if terminal and Counter(map(token_fingerprint, fusion_tokens)) != Counter(
            map(token_fingerprint, tokenizations)):
        finding('accounting', 'tokenizer_journal_and_ledger_journal_differ')
    contexts = [event for event in events if event.get('event') == 'model_context_budget']
    current_context = {}
    for event in events:
        if event.get('event') == 'model_context_budget':
            current_context[event.get('stage')] = event
        if event.get('event') == 'budget_reserved' and event.get('kind') == 'http_attempts':
            context = current_context.get(event.get('stage'), {})
            if context.get('within_estimated_budget') is False:
                finding('budget', 'http_started_after_context_guard_rejection')
    for context in contexts:
        if (integer(context.get('context_tokens')) and context['context_tokens'] > 16384
                or integer(context.get('output_token_reserve'))
                and context['output_token_reserve'] > 4096):
            finding('budget', 'context_or_output_limit_exceeds_protocol')

    error_types = Counter(error.get('type', error.get('error_type', 'unknown'))
                          for error in diagnostics.get('errors', []) if isinstance(error, dict))
    failure_type = (result or {}).get('failure', {}).get('error_type')
    if failure_type:
        error_types[failure_type] += 1
    # Active failures also appear as typed events. Do not double-count them
    # when the same error is present in a terminal diagnostic publication.
    if not terminal:
        error_types.update(event.get('type', event.get('error_type')) for event in events
                           if event.get('event') in ('residual_action_incomplete',
                                                    'task_failed', 'audit_incomplete')
                           and (event.get('type') or event.get('error_type')))
    classified = defaultdict(dict)
    for name, count in error_types.items():
        category = error_category(name)
        classified[category][name] = count
        if category in ('program_exception', 'worker_failure_or_interruption'):
            finding(category, name)
        elif category in ('service_or_token_accounting', 'unclassified_needs_review'):
            finding(category, name, 'warning')
    worker = directory / 'worker.log'
    log = worker.read_text(errors='replace') if worker.exists() else ''
    traceback_lines = [index for index, line in enumerate(log.splitlines(), 1)
                       if line.strip() == 'Traceback (most recent call last):']
    fatal_signatures = [signature for signature in ('Fatal Python error:',
                        'Segmentation fault', 'Bus error') if signature in log]
    if traceback_lines or fatal_signatures:
        finding('worker_failure_or_interruption', 'worker_log_traceback_or_fatal',
                detail={'traceback_lines': traceback_lines, 'fatal_signatures': fatal_signatures})
    if any(row['category'] in ('integrity', 'accounting', 'token_accounting')
           and row['severity'] == 'error' for row in findings):
        cost_integrity = 'incomplete_or_inconsistent'
    status = answer.get('status') if terminal else 'active_or_pending'
    category = ('execution_success' if status == 'ok' else
                'environment_exclusion' if status == 'skipped_environment' else
                'controlled_budget_terminal' if status == 'budget_exhausted' else
                'worker_or_service_failure' if failure_type else
                'algorithm_nonanswer_terminal' if terminal else 'in_progress')
    return {
        'dataset': dataset, 'question_id': directory.parent.name, 'arm': directory.name,
        'terminal': terminal, 'answer_status': status, 'outcome_category': category,
        'completion_kind': answer.get('completion_kind'), 'failure_type': failure_type,
        'diagnostic_error_types': dict(error_types), 'classified_errors': dict(classified),
        'worker_log': {'exists': worker.exists(), 'traceback_count': len(traceback_lines),
                       'fatal_signatures': fatal_signatures},
        'budget': {'journal_used': dict(used), 'published_used': published_used,
                   'published_limits': limits, 'protocol_caps': CAPS,
                   'violations': [row for row in findings if row['category'] == 'budget']},
        'calls': {'logical_reasoning_requests': names['reasoning_request_started'],
                  'logical_operations': dict(operations),
                  'published_repair_calls': cost.get('repair_calls'),
                  'repair_reservations': used['json_repairs'],
                  'call_journal_starts': len(calls),
                  'cache_hit_starts': sum(bool(event.get('cache_hit')) for event in calls),
                  'cached_attempt_charges': replay_charges,
                  'physical_model_http_attempts': used['http_attempts'],
                  'successful_model_http_responses': len(responses),
                  'attempts_without_success_response': used['http_attempts'] - len(responses),
                  'physical_charge_balance': physical_balance,
                  'web_http_attempt_events': names['web_http'],
                  'browser_network_request_events': names['web_browser_network']},
        'tokens': {'successful_llm_responses': len(llm_responses),
                   'successful_response_usage_totals': dict(usage_totals),
                   'successful_responses_missing_usage': missing_usage,
                   'usage_totals_exclude_cache_replay': True,
                   'failed_or_inflight_attempt_tokens_are_unknown':
                       used['http_attempts'] > len(responses),
                   'exact_usage_validation_counts': dict(Counter(
                       event.get('status') for event in validations)),
                   'missing_validation_at_snapshot': dict(missing_validation),
                   'tokenizer_http_attempts': sum(event.get('http_attempts', 0)
                                                   for event in tokenizations),
                   'tokenizer_errors': dict(token_errors),
                   'context_guard_rejections': sum(
                       event.get('within_estimated_budget') is False for event in contexts)},
        'cost_log_integrity': cost_integrity, 'journal_snapshots': metadata,
        'findings': findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=STAGE / 'real_smoke_v2')
    parser.add_argument('--output', type=Path, default=STAGE / 'audit_real_smoke_v2_snapshot.json')
    parser.add_argument('--expected-tasks', type=int, default=8)
    parser.add_argument('--require-terminal', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir() or args.expected_tasks < 1:
        parser.error('Existing generation root and positive expected task count required')
    progress = {}
    for relative in ('progress.json', *(name + '/progress.json' for name in DATASETS)):
        row = read_json(root / relative)
        progress[relative] = None if row is None else {
            key: row[key] for key in ('state', 'current', 'completed', 'total', 'failed_tasks')
            if key in row}
    tasks = [audit_task(directory, dataset) for dataset in DATASETS
             for directory in sorted((root / dataset / 'tasks').glob('*/*'))
             if directory.is_dir()]
    terminal = sum(task['terminal'] for task in tasks)
    errors = sum(finding['severity'] == 'error' for task in tasks for finding in task['findings'])
    warnings = sum(finding['severity'] == 'warning' for task in tasks for finding in task['findings'])
    generation_complete = terminal == args.expected_tasks and all(
        (progress[name + '/progress.json'] or {}).get('state') == 'complete' for name in DATASETS)
    report = {
        'audit_utc': datetime.now(timezone.utc).isoformat(), 'root': str(root),
        'scope': 'generation telemetry only; no answers scored',
        'official_references_or_evaluation_read': False,
        'generation_or_scoring_called': False, 'generation_progress': progress,
        'summary': {'expected_tasks': args.expected_tasks, 'discovered_tasks': len(tasks),
                    'terminal_tasks': terminal, 'not_yet_discovered_tasks':
                        max(0, args.expected_tasks - len(tasks)),
                    'generation_complete': generation_complete,
                    'terminal_status_counts': dict(Counter(task['answer_status']
                        for task in tasks if task['terminal'])),
                    'error_findings': errors, 'warning_findings': warnings,
                    'assessment': 'issues_detected' if errors else
                        'complete_no_program_or_accounting_errors' if generation_complete else
                        'no_errors_in_partial_snapshot'},
        'interpretation': [
            'budget_exhausted/unresolved/partial and failed_tasks counts are algorithm outcomes, not program crashes.',
            'Repair invocations and repair reservations differ legitimately; they are reported separately.',
            'HTTP attempt charges include failures; successful token totals omit cache replays and do not invent failed-attempt usage.',
            'Active files are a partial snapshot; strict ledger and cross-journal comparisons apply only to terminal tasks.',
            'Only typed exceptions and explicit accounting/worker invariants are findings; arbitrary error words are not.'],
        'tasks': tasks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'report': str(args.output), **report['summary']}, ensure_ascii=False, indent=2))
    return 1 if errors else 2 if args.require_terminal and not generation_complete else 0


if __name__ == '__main__':
    raise SystemExit(main())
