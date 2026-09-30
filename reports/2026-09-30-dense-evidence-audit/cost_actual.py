"""Read authoritative task artifacts and reconstruct ContextPlans; no model calls."""
import csv
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

from bridgetree.clients import build_context_plan
from bridgetree.types import Memory

ROOT = Path('outputs/diagnostics/evidence_v2_20260930_logs/run')
DEST = Path('reports/2026-09-30-dense-evidence-audit')
manifest = json.loads((ROOT / 'run_manifest.json').read_text())
qpath = Path('data/raw/personamem-v1/questions_32k.csv')
assert hashlib.sha256(qpath.read_bytes()).hexdigest() == manifest['dataset']['source_sha256'][qpath.name]
questions = {(str(x['persona_id']), str(x['question_id'])): x for x in csv.DictReader(qpath.open())}
outcomes = [json.loads(p.read_text()) for p in (ROOT / 'outcomes').glob('*.json')]
key = lambda x: (x['task']['persona_id'], x['task']['question_id'])
dense = {key(x): x for x in outcomes if x['task']['method_id'] == 'dense'}
evidence = {key(x): x for x in outcomes if x['task']['method_id'] == 'evidence_bridge'}
visible = {}
for p in (ROOT / 'visible_memories').glob('*.json'):
    value = json.loads(p.read_text())
    visible[(str(value['persona_id']), str(value['question_id']))] = value

def nested(value, path, default=None):
    for name in path.split('.'):
        if not isinstance(value, dict) or name not in value:
            return default
        value = value[name]
    return value

def stats(values):
    values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return {'n': len(values), 'sum': sum(values), 'mean': statistics.mean(values) if values else None,
            'median': statistics.median(values) if values else None, 'min': min(values) if values else None,
            'max': max(values) if values else None}

METRICS = [
    'ann_calls', 'scored_sets', 'reranker_adapter_requests', 'generator_calls', 'evidence_calls',
    'generator_input_tokens_estimate', 'elapsed_ms', 'memory_embedding_samples',
    'memory_embedding_adapter_invocations', 'adapter_invocations.embedding_adapter_invocations',
    'evidence_reasoning.evidence_llm_calls', 'evidence_reasoning.evidence_input_tokens_estimate',
    'evidence_reasoning.evidence_output_tokens_estimate', 'evidence_reasoning.evidence_llm_elapsed_ms',
    'evidence_reasoning.evidence_json_repairs', 'set_scorer.logical_input_tokens_estimate',
    'set_scorer.reranker_elapsed_ms', 'set_scorer.reranker_samples',
    'set_scorer.persistent_cache_hits', 'set_scorer.memory_cache_hits',
    'set_scorer.reranker_transport.batch_requests', 'set_scorer.reranker_transport.transport_attempts',
    'set_scorer.reranker_transport.transport_document_attempts',
    'set_scorer.reranker_transport.failed_batch_requests', 'set_scorer.reranker_transport.split_events',
]

rows = []
for k, e in evidence.items():
    d = dense.get(k)
    if not d or d['status'] != 'success' or e['status'] != 'success':
        continue
    ds, es = set(d['selected_ids']), set(e['selected_ids'])
    q = questions[k]
    memories = {x['memory_id']: Memory(**x) for x in visible[k]['visible_memories']}
    def plan(ids):
        return build_context_plan(q['user_question_or_message'], [memories[i] for i in sorted(ids)],
                                  q['all_options'], token_budget=8192, strict=False)
    dp, ep, up = plan(ds), plan(es), plan(ds | es)
    assert dp.token_count == d['costs']['generator_input_tokens_estimate'], (k, 'dense token mismatch')
    assert ep.token_count == e['costs']['generator_input_tokens_estimate'], (k, 'evidence token mismatch')
    artifact = json.loads((ROOT / 'candidate_pool' / (e['task']['task_id'] + '.json')).read_text())
    sel = artifact['evidence_selection']
    usage = Counter()
    usage_requests = 0
    for request in sel['requests']:
        source = request.get('response_metadata', {}).get('usage')
        if isinstance(source, dict):
            usage_requests += 1
            for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                if isinstance(source.get(name), (int, float)):
                    usage[name] += source[name]
    row = {
        'persona_id': k[0], 'question_id': k[1], 'dense_task_id': d['task']['task_id'],
        'evidence_task_id': e['task']['task_id'],
        'cohort': nested(e, 'diagnostics.evidence_bridge_summary.reliability.reliability_status'),
        'dense_correct': d['correct'], 'evidence_correct': e['correct'],
        'dense_memory_count': len(ds), 'evidence_memory_count': len(es),
        'shared_memory_count': len(ds & es), 'dense_dropped_count': len(ds - es),
        'evidence_added_count': len(es - ds),
        'dense_retained_fraction': len(ds & es) / len(ds) if ds else None,
        'evidence_new_fraction': len(es - ds) / len(es) if es else None,
        'dense_input_tokens': dp.token_count, 'evidence_input_tokens': ep.token_count,
        'union_input_tokens': up.token_count, 'union_within_budget': up.within_budget,
        'union_added_over_evidence_tokens': up.token_count - ep.token_count,
        'reader_budget': up.budget, 'dense_ids': sorted(ds), 'evidence_ids': sorted(es),
        'evidence_request_count': len(sel['requests']), 'provider_usage_request_count': usage_requests,
        'evidence_provider_usage': dict(usage), 'dense_costs': d['costs'], 'evidence_costs': e['costs'],
        'mapped_fact_count': len(sel['mappings']), 'exposed_candidate_count': len(sel['candidate_ids']),
        'eligible_memory_count': len(sel['eligible_memory_ids']),
        'dense_in_evidence_candidates': len(ds & set(sel['candidate_ids'])),
        'dense_fully_mapped_count': len(ds & set(sel['fully_mapped_ids'])),
        'dense_eligible_count': len(ds & set(sel['eligible_memory_ids'])),
        'dense_not_eligible_count': len(ds - set(sel['eligible_memory_ids'])),
        'dense_eligible_but_unselected_count': len((ds & set(sel['eligible_memory_ids'])) - es),
    }
    rows.append(row)

def group(xs):
    n = len(xs)
    def outcome_summary(ys):
        return {'n': len(ys), 'dense_correct': sum(x['dense_correct'] for x in ys),
                'evidence_correct': sum(x['evidence_correct'] for x in ys),
                'dense_accuracy': sum(x['dense_correct'] for x in ys) / len(ys) if ys else None,
                'evidence_accuracy': sum(x['evidence_correct'] for x in ys) / len(ys) if ys else None}
    return {
        **outcome_summary(xs),
        'context_stats': {field: stats([x[field] for x in xs]) for field in (
            'dense_memory_count', 'evidence_memory_count', 'shared_memory_count',
            'dense_dropped_count', 'evidence_added_count', 'dense_retained_fraction',
            'evidence_new_fraction', 'dense_input_tokens', 'evidence_input_tokens',
            'union_input_tokens', 'union_added_over_evidence_tokens',
            'mapped_fact_count', 'exposed_candidate_count', 'eligible_memory_count',
            'dense_in_evidence_candidates', 'dense_fully_mapped_count', 'dense_eligible_count',
            'dense_not_eligible_count', 'dense_eligible_but_unselected_count')},
        'pooled_dense_retention': sum(x['shared_memory_count'] for x in xs) / sum(x['dense_memory_count'] for x in xs) if xs else None,
        'pooled_evidence_new_fraction': sum(x['evidence_added_count'] for x in xs) / sum(x['evidence_memory_count'] for x in xs) if sum(x['evidence_memory_count'] for x in xs) else None,
        'union_within_budget_count': sum(x['union_within_budget'] for x in xs),
        'drops_dense_despite_union_fitting': sum(x['union_within_budget'] and x['dense_dropped_count'] > 0 for x in xs),
        'evidence_reader_shorter': sum(x['evidence_input_tokens'] < x['dense_input_tokens'] for x in xs),
        'evidence_reader_longer': sum(x['evidence_input_tokens'] > x['dense_input_tokens'] for x in xs),
        'evidence_reader_equal': sum(x['evidence_input_tokens'] == x['dense_input_tokens'] for x in xs),
        'selection_size_groups': {
            'zero': outcome_summary([x for x in xs if x['evidence_memory_count'] == 0]),
            'one_to_three': outcome_summary([x for x in xs if 1 <= x['evidence_memory_count'] <= 3]),
            'four_or_more': outcome_summary([x for x in xs if x['evidence_memory_count'] >= 4]),
        },
        'cost_metrics': {method: {metric: stats([nested(x[method + '_costs'], metric) for x in xs])
                                 for metric in METRICS} for method in ('dense', 'evidence')},
        'memory_vector_cache_hits': {method: sum(x[method + '_costs'].get('memory_vector_cache_hit') is True for x in xs)
                                     for method in ('dense', 'evidence')},
        'evidence_provider_usage': {field: stats([x['evidence_provider_usage'].get(field) for x in xs])
                                    for field in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
        'provider_usage_requests': sum(x['provider_usage_request_count'] for x in xs),
        'logical_evidence_calls': sum(x['evidence_costs']['evidence_reasoning']['evidence_llm_calls'] for x in xs),
    }

result = {
    'scope': 'authoritative outcomes, current attempt only; pair both successful; no module stream summation',
    'run_root': str(ROOT), 'question_csv_hash_verified': True,
    'union_budget_method': 'rebuild full chronological original-memory ContextPlan from matched raw CSV query/options and exported visible memories; dense/evidence token estimates both reproduced exactly',
    'outcome_counts': {str(k): v for k, v in Counter((x['task']['method_id'], x['status']) for x in outcomes).items()},
    'cohort_counts': dict(Counter(x['cohort'] for x in rows)),
    'groups': {'all_common_success': group(rows), 'normal_common_success': group([x for x in rows if x['cohort'] == 'normal'])},
    'top_level_evidence_calls_zero_with_positive_nested_calls': sum(x['costs'].get('evidence_calls') == 0 and nested(x, 'costs.evidence_reasoning.evidence_llm_calls', 0) > 0 for x in evidence.values()),
    'evidence_authoritative_outcome_count': len(evidence),
    'rows': sorted(rows, key=lambda x: (x['persona_id'], x['question_id'])),
}
(DEST / 'cost_actual.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({k:v for k,v in result.items() if k != 'rows'}, indent=2, ensure_ascii=False))
