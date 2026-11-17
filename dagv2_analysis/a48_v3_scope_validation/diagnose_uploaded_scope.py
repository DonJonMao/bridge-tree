"""Compact, label-free diagnosis of the uploaded v3 inference trace."""
import hashlib
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
SERVER = BASE.parent / 'a48_v3_server_failure/personamem_a48_v3_smoke'
LOCAL = BASE.parent / 'a48_v3_validation/live_smoke_06'
DIGEST = '2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0'
ARM = 'dagbt_residual_memory_v1'


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempt(root):
    return root / f'personamem/{ARM}/attempts/{DIGEST}/attempt-001'


def inspect(root):
    directory = attempt(root)
    events = [json.loads(line) for line in (directory / 'fusion_events.jsonl').open()]
    plan = next(e['plan'] for e in events if e['event'] == 'plan_frozen')
    calls = []
    for event in events:
        if event['event'] != 'http_response' or event['kind'] != 'llm':
            continue
        path = directory / 'requests' / (event['response_ref'] + '.json')
        record = load(path)
        raw = record['response']['choices'][0]['message']['content']
        parsed = json.loads(raw[raw.index('{'):raw.rindex('}') + 1])
        calls.append({'stage': record['stage'], 'request_file': str(path),
                      'request_file_sha256': sha(path),
                      'raw_response_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                      'scopes': [{'variable': slot['variable'], 'observations': [
                          {k: row[k] for k in ('id', 'stance', 'entity_scope', 'time_scope')}
                          for row in slot['observations']]} for slot in parsed.get('slots', [])]})
    row = load(directory / 'result.json')
    diag = row['diagnostics']
    return {
        'attempt': str(directory), 'result_sha256': sha(directory / 'result.json'),
        'event_file_sha256': sha(directory / 'fusion_events.jsonl'),
        'plan': plan, 'calls': calls,
        'status': row['answer']['status'], 'completion_kind': row['answer']['completion_kind'],
        'ledger': {k: diag['ledger'][k] for k in ('limits', 'used', 'remaining')},
        'pending_variables': diag['fact_state']['pending_variables'],
        'failed_obligations': diag['joint_reading']['failed_obligations'],
        'failed_read_states': sum(s['state'] == 'invalid' for s in diag['joint_reading']['read_states']),
        'event_counts': dict(Counter(e['event'] for e in events)),
        'bridge_node_counts': dict(Counter(e['trace']['node_id'] for e in events if e['event'] == 'bridge_step_completed')),
        'timeline': [({'sequence': e['sequence'], 'elapsed_seconds': e['elapsed_seconds'], 'event': e['event'],
                      'node_id': e['trace']['node_id'], 'ann_completed': e['trace']['ann_calls_completed'],
                      'local_candidates': len(e['trace']['local_candidate_ids']),
                      'search_status': e['trace']['search_status']}
                     if e['event'] == 'bridge_step_completed' else
                     {'sequence': e['sequence'], 'elapsed_seconds': e['elapsed_seconds'], 'event': e['event'],
                      'source_count': len(e['source_aliases']), 'valid_rows': e['valid_rows'],
                      'complete': e['complete'], 'failed_slots': e['failed_slots']})
                     for e in events if e['event'] in ('bridge_step_completed', 'joint_read_completed')],
        'all_chat_tokenization_matched': all(e['status'] == 'matched' for e in events if e['event'] == 'tokenization_usage_validation'),
        'max_total_with_output_and_margins': max(e['total_tokens_local'] for e in events if e['event'] == 'model_context_budget'),
    }


def main():
    server, local = inspect(SERVER), inspect(LOCAL)
    sm, lm = load(SERVER / 'manifest.json'), load(LOCAL / 'manifest.json')
    si, li = (load(r / 'index_artifacts.json')['personamem']['manifest'] for r in (SERVER, LOCAL))
    index_fields = ('identity', 'corpus_sha256', 'document_ids_sha256', 'passages_sha256', 'dimensions', 'vectors_sha256')
    compared = {k: {'same': si[k] == li[k], 'value': si[k]} for k in index_fields}
    report = {
        'no_network_calls': True, 'evaluation_labels_read': False,
        'scores_summary_comparisons_read': False,
        'source_hashes_exactly_equal': sm['source_hashes'] == lm['source_hashes'],
        'source_hash_count': len(sm['source_hashes']),
        'config_exactly_equal': sm['config'] == lm['config'],
        'question_ids_exactly_equal': sm['question_ids'] == lm['question_ids'],
        'server_manifest_sha256': sha(SERVER / 'manifest.json'),
        'local_manifest_sha256': sha(LOCAL / 'manifest.json'),
        'index_content_comparison': compared,
        'index_manifest_caveat': 'Whole manifests differ in machine paths, build time and ledger metadata; index identity and actual vectors hash match.',
        'server': server, 'local_smoke06': local,
        'root_cause': 'Global terminal user/weekend scope was applied to the intermediate task asking for past creative interests. Uploaded calls 2/3/4 preserved user/past and failed validation. Local smoke06 call 2 returned user/weekend and passed the same validator.',
        'failure_amplification': 'The first failed source-window obligation remains pending; its 118 aliases become invalid read_states and ordinary reads do not reopen them. Later 15 independently valid windows cannot erase a failed counter obligation. Controller restarts at first active DAG step, so creative_interests consumes all 36 ANN calls; other nodes never run.',
        'bounded_fix': 'Declare intermediate variable scope before retrieval and validate each observation against its own scope, while retaining terminal output scope. Do not clear failed counter obligations, relabel historical evidence as weekend, increase budgets or silently accept an incomplete answer.',
        'limits': ['This diagnosis does not evaluate answer correctness.',
                   'Scope declaration replay is an explicit counterfactual protocol check, not a claim the corrected planner produced that declaration live.',
                   'Scheduler behavior is documented separately; no scheduler change is part of this scope fix.'],
    }
    assert report['source_hashes_exactly_equal'] and report['config_exactly_equal']
    assert all(v['same'] for v in compared.values())
    output = BASE / 'diagnosis_report.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'report': str(output), 'sha256': sha(output), 'server_status': server['status'],
                      'source_hash_count': report['source_hash_count'], 'index_content_equal': True}))


if __name__ == '__main__':
    main()
