"""Private read-only audit of the fixed smoke; never loads evaluation labels."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dagbt import runner
from dagbt import local_terminal
from dagbt.transport import digest

VERSION = 'dagbt_local_terminal_v1'


def json_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def upstream_cost(path):
    """Observed reranker upstream requests, excluding seeded responses/cache replay."""
    seed = path / 'seeded_requests.json'
    seeded = set(runner.load(seed)) if seed.exists() else set()
    count, observed, missing, failed, mismatches = 0, 0, 0, 0, 0
    for record_path in (path / 'requests').glob('*.json'):
        record = runner.load(record_path)
        if record_path.stem in seeded:
            continue
        attempts = record.get('attempts', [])
        if not any(a.get('kind') == 'rerank_http' for a in attempts):
            continue
        successful = sum(a.get('http_status') == 200 for a in attempts)
        failed += sum(a.get('http_status') != 200 for a in attempts)
        if not successful:
            continue
        response = record.get('response', {})
        value = response.get('usage', {}).get('upstream_requests')
        metadata_value = response.get('scoring_metadata', {}).get('upstream_requests')
        if value is not None and metadata_value is not None and value != metadata_value:
            mismatches += 1
        value = value if value is not None else metadata_value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            count += value
            observed += 1
            missing += max(0, successful - 1)
        else:
            missing += successful
    return {'upstream_request_count': count if observed else None,
        'upstream_responses_observed': observed, 'upstream_successful_responses_missing_count': missing,
        'upstream_failed_or_lost_http_attempts': failed, 'upstream_metadata_mismatches': mismatches,
        'upstream_forward_count': None,
        'upstream_observability': 'reranker successful nonseeded response usage.upstream_requests; counted once per stored response, not per set or replay; failed/lost work unreported; forwards not exposed'}


def audit_attempt(path):
    events = json_rows(path / 'fusion_events.jsonl')
    transport = runner.request_cost(path)
    counts = Counter(e.get('operation') for e in events if e.get('event') == 'reasoning_request_started')
    contexts, measured, requests, issues = {}, {}, {}, []
    final = None
    public_question = runner.load(path / 'task.json').get('question', {})
    for event in events:
        kind = event.get('event')
        if kind == 'plan_frozen':
            final = event['plan']['final_node_id']
        if kind == 'bridge_discovery_completed':
            trace = event['trace']
            context = trace.get('scoring_context_id')
            if context:
                contexts[context] = trace.get('scorer_cost_cumulative', {})
                for score in trace.get('measured_sets_cumulative', []):
                    measured[(context, tuple(score['ids']))] = score['score']
                query = trace.get('scoring_query')
                if trace.get('query') != query:
                    issues.append('discovery_scoring_query_mismatch')
                for activation in trace.get('search_archive', {}).get('activations', []):
                    if activation.get('scoring_context_id') != context or activation.get('scoring_query') != query:
                        issues.append('activation_context_mismatch')
                    r0, r1, r2, r3 = [activation[k] for k in ('P', 'Pe', 'PG', 'PGe')]
                    if activation['activation'] != (r3-r2)-(r1-r0):
                        issues.append('activation_arithmetic_mismatch')
                    if activation['target_marginal_after'] != r3-r2:
                        issues.append('marginal_arithmetic_mismatch')
        if kind == 'bridge_rerank_request':
            key = tuple(event['stage'])
            if key in requests:
                issues.append('duplicate_rerank_stage')
            requests[key] = event
            if event.get('algorithm_version') != VERSION or not event.get('scoring_context_id'):
                issues.append('missing_local_scoring_identity')
            if event.get('query') != event.get('scoring_query'):
                issues.append('actual_backend_query_mismatch')
        if kind in ('baseline_prepared', 'final_selection', 'reader_input'):
            issues.append('legacy_stage_executed')
    successful_samples, failed_unknown_samples = 0, 0
    seed = path / 'seeded_requests.json'
    seeded = set(runner.load(seed)) if seed.exists() else set()
    for record_path in (path / 'requests').glob('*.json'):
        record = runner.load(record_path)
        identity = {k: record[k] for k in ('unit_id', 'url', 'payload', 'algorithm_version', 'scoring_context_id') if k in record}
        if digest(identity) != record_path.stem:
            issues.append('request_identity_mismatch')
        stage = record.get('stage', [])
        messages = record.get('payload', {}).get('messages', [])
        if len(messages) > 1:
            try:
                data = json.loads(messages[1]['content'])
            except (json.JSONDecodeError, TypeError):
                data = None
            if isinstance(data, dict):
                terminal = bool(stage and stage[0] == 'resolve' and data.get('node_id') == final)
                if ('public_options' in data or 'public_output_question' in data) and not terminal:
                    issues.append('public_output_outside_terminal_request')
                if terminal and public_question.get('options') is not None:
                    if data.get('public_options') != public_question['options'] or data.get('public_output_question') != public_question['question']:
                        issues.append('terminal_public_output_contract_mismatch')
        if tuple(stage) not in requests:
            continue
        expected = requests[tuple(stage)]
        payload = record['payload']
        if payload['query'] != expected['scoring_query'] or payload['documents'] != expected['documents']:
            issues.append('wire_query_or_documents_mismatch')
        if record.get('scoring_context_id') != expected['scoring_context_id']:
            issues.append('wire_scoring_context_mismatch')
        for attempt in ([] if record_path.stem in seeded else record.get('attempts', [])):
            if attempt.get('http_status') == 200:
                successful_samples += len(payload['documents'])
            else:
                failed_unknown_samples += len(payload['documents'])
    total_context = {key: sum(c.get(key, 0) for c in contexts.values()) for key in (
        'scored_sets', 'reranker_adapter_requests', 'reranker_samples', 'memory_cache_hits', 'persistent_cache_hits')}
    ledger = None
    for filename in ('fusion_snapshot.json', 'fusion_partial.json'):
        if (path / filename).exists():
            snapshot = runner.load(path / filename)
            ledger = snapshot.get('ledger') or snapshot.get('diagnostics', {}).get('ledger')
            if ledger:
                break
    used = (ledger or {}).get('used', {})
    if used.get('set_score', 0) != total_context['scored_sets']:
        issues.append('context_cost_ledger_mismatch')
    if any(used.get(kind, 0) > cap for kind, cap in [('ann', 36), ('set_score', 512), ('llm', 24), ('reader', 0)]):
        issues.append('question_budget_exceeded')
    upstream = upstream_cost(path)
    if upstream['upstream_metadata_mismatches']:
        issues.append('upstream_usage_metadata_mismatch')
    result = {
        'logical_generation_calls': sum(counts.values()), 'logical_node_resolve_calls': counts['resolve'],
        'logical_generation_by_operation': dict(counts), 'ann_calls': used.get('ann', 0),
        'logical_set_score_units': used.get('set_score', 0), 'completed_scored_sets': len(measured),
        'scoring_contexts': len(contexts), 'scorer_cost_once_per_context': total_context,
        'physical_llm_attempts': transport.get('physical_llm_attempts', 0),
        'physical_embedding_http_attempts': transport.get('by_kind', {}).get('embedding_http', {}).get('http_attempts', 0),
        'physical_rerank_http_attempts': transport.get('by_kind', {}).get('rerank_http', {}).get('http_attempts', 0),
        'successful_rerank_http_set_samples': successful_samples,
        'failed_or_unknown_rerank_http_set_samples': failed_unknown_samples,
        'transport_cache_hits': transport.get('cache_hits', 0),
        'independent_reader_calls': transport.get('reader_logical_calls', 0),
        'global_final_selector_calls': counts['select'] + counts['select_repair'],
        **upstream,
        'issues': sorted(set(issues)),
    }
    return result


def audit_run(root):
    manifest = runner.load(root / 'manifest.json')
    if runner.lock_is_held(root):
        raise ValueError('Live writer: audit only the terminal capture')
    if manifest.get('algorithm_version') != VERSION or manifest.get('question_attempts') != 1:
        raise ValueError('Not the fixed single-attempt local-terminal smoke')
    if manifest['source_hashes'] != runner.frozen_sources():
        raise ValueError('Current sources differ from captured algorithm')
    tasks = []
    for dataset, ids in manifest['question_ids'].items():
        for unit in ids:
            row_path = runner.result_path(root, dataset, VERSION, unit)
            row = runner.validate_result(runner.load(row_path), unit)
            paths = row.get('attempt_directories', [])
            if len(paths) != 1:
                raise ValueError('Expected one recorded attempt')
            cost = audit_attempt(root / paths[0])
            if row.get('reader_response') or row.get('budgets') != {}:
                cost['issues'].append('fabricated_legacy_output')
            if row['answer']['status'] == 'ok':
                graph = row['diagnostics']['support_graph']
                current = local_terminal.provenance(graph, row['answer']['final_node_id'])
                if current != row['answer']['sources'] or current['node_versions'] != row['answer']['dependency_versions']:
                    cost['issues'].append('published_provenance_mismatch')
            scope = row.get('diagnostics', {}).get('memory_scope')
            if scope:
                visible = set(scope['visible_doc_ids'])
                if not set(row['diagnostics'].get('candidate_doc_ids', [])) <= visible:
                    cost['issues'].append('candidate_outside_memory_scope')
                if not set(row['answer'].get('terminal_input_doc_ids', [])) <= visible:
                    cost['issues'].append('terminal_input_outside_memory_scope')
                if not set((row['answer'].get('sources') or {}).get('doc_ids', [])) <= visible:
                    cost['issues'].append('published_sources_outside_memory_scope')
                bridge = row['diagnostics'].get('bridge_cost') or {}
                for trace in bridge.get('traces', []):
                    if any(not set(score['ids']) <= visible for score in trace.get('measured_sets_cumulative', [])):
                        cost['issues'].append('scored_set_outside_memory_scope')
            tasks.append({'dataset': dataset, 'question_id_sha256': digest(unit),
                'answer_status': row['answer']['status'], 'final_node_id': row['answer'].get('final_node_id'),
                'wall_seconds': row.get('runner', {}).get('wall_seconds'),
                'audit_complete': row.get('diagnostics', {}).get('audit_complete'),
                'reliability_cohort': row.get('diagnostics', {}).get('reliability', {}).get('cohort'),
                'prediction_is_null': row['answer'].get('prediction') is None,
                'cost': cost})
    if len(tasks) != 6:
        raise ValueError('Expected all six terminal questions')
    totals = {key: sum(t['cost'][key] for t in tasks) for key in (
        'logical_generation_calls', 'logical_node_resolve_calls', 'ann_calls', 'logical_set_score_units',
        'completed_scored_sets', 'physical_llm_attempts', 'physical_embedding_http_attempts', 'physical_rerank_http_attempts',
        'successful_rerank_http_set_samples', 'failed_or_unknown_rerank_http_set_samples',
        'transport_cache_hits', 'independent_reader_calls', 'global_final_selector_calls',
        'upstream_request_count', 'upstream_responses_observed', 'upstream_successful_responses_missing_count',
        'upstream_failed_or_lost_http_attempts', 'upstream_metadata_mismatches')}
    return {'algorithm_version': VERSION, 'labels_read': False,
        'status_counts': dict(Counter(t['answer_status'] for t in tasks)),
        'tasks': tasks, 'totals': totals, 'issues': sorted({i for t in tasks for i in t['cost']['issues']}),
        'upstream_request_count': totals['upstream_request_count'], 'upstream_forward_count': None,
        'index_build_cost': runner.request_cost(root / 'index_build' / 'hotpotqa')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    report = audit_run(args.root)
    destination = args.root / 'completion_audit.json'
    runner.save(destination, report)
    destination.chmod(0o600)
    print(json.dumps({k: report[k] for k in ('status_counts', 'totals', 'issues')}, indent=2))
