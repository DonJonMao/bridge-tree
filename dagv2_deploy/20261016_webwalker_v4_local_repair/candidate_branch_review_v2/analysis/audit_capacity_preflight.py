"""Read-only generation trace audit: candidate token counting versus paid requests."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json

STAGE = Path(__file__).resolve().parent.parent
TASK = STAGE / 'output/tasks/wwqa-0001/dagbt_joint_memory_v1'
rows = []
for line in (TASK / 'fusion_events.jsonl').read_text().splitlines():
    try:
        rows.append(json.loads(line))
    except json.JSONDecodeError:
        pass
counts = [row for row in rows if row.get('event') == 'tokenization_count']
checks = [row for row in rows if row.get('event') == 'model_context_budget']
starts = [row for row in rows if row.get('event') == 'reasoning_request_started']
completed14 = next((row for row in rows if row.get('event') == 'joint_read_completed'
                    and row.get('sequence', 0) > 352), None)
start15 = next((row for row in starts if row.get('logical_call_index') == 15), None)
preflight = [row for row in counts if completed14 and row['sequence'] > completed14['sequence']
             and (start15 is None or row['sequence'] < start15['sequence'])]
report = {
    'updated_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'generation-only local event audit plus read-only frozen source loop review; no extra tokenization, model, site, eval or reference requests',
    'task': str(TASK),
    'last_event': {key: rows[-1].get(key) for key in ('event', 'sequence', 'elapsed_seconds', 'unix')},
    'paid_logical_request_starts': len(starts),
    'tokenization_count_events': len(counts),
    'recorded_tokenizer_http_attempts': sum(row.get('http_attempts', 0) for row in counts),
    'tokenizer_cache_hit_events': sum(bool(row.get('cache_hit')) for row in counts),
    'tokenizer_failed_attempts': sum(row.get('failed_http_attempts', 0) for row in counts),
    'tokenizer_http_retries': sum(row.get('http_retries', 0) for row in counts),
    'tokenizer_retry_records': [row for row in counts if row.get('failed_http_attempts') or row.get('http_retries')],
    'actual_generation_context_checks': len(checks),
    'actual_generation_over_context': [row for row in checks if row.get('within_estimated_budget') is not True],
    'actual_generation_max_input_tokens': max((row['input_tokens_local'] for row in checks), default=0),
    'actual_generation_max_total_tokens': max((row['total_tokens_local'] for row in checks), default=0),
    'call14_completed_event': completed14,
    'next_paid_start15': start15,
    'between_call14_completion_and_call15': {
        'tokenization_events': len(preflight),
        'http_attempts': sum(row.get('http_attempts', 0) for row in preflight),
        'cache_hit_events': sum(bool(row.get('cache_hit')) for row in preflight),
        'min_candidate_input_tokens': min((row['count'] for row in preflight), default=0),
        'max_candidate_input_tokens': max((row['count'] for row in preflight), default=0),
        'candidate_counts_exceeding_local_context_16384': sum(row['count'] > 16384 for row in preflight),
        'candidate_counts_are_not_paid_generation': True,
    },
    'finite_loop_review': [
        {'file': 'source/dagbt/joint_reading.py', 'function': '_fitting_prefix',
         'evidence': 'A local tested dict counts each prefix size once. It tries N, a shrinking binary interval, then range(1,N) only when needed; therefore at most N distinct prefix trials for fixed pending groups.'},
        {'file': 'source/dagbt/joint_reading.py', 'function': '_adaptive_fresh_cap',
         'evidence': 'while cap>0 either returns or replaces cap with a strictly smaller integer; cap begins at most reasoning_output_tokens (4096 here).'},
        {'file': 'source/dagbt/joint_reading.py', 'function': '_select_wire / _fits',
         'evidence': '_select_wire counts at most baseline and one reversible packed candidate. _fits checks the complete initial and repair envelopes; overflow candidates are measured without generation.'},
        {'file': 'source/dagbt/webwalker_reading.py', 'function': '_paid_recovery_prefix / _single_shot_prefix',
         'evidence': 'Each is a finite range(1,len(pending)+1) scan. They may add O(N) exact counting after the common fit search; no loop adds source groups.'},
        {'file': 'source/dagbt/joint_reading.py', 'function': '_read',
         'evidence': 'Outer while pending either raises when consumed=0 or deletes pending[:consumed] before a request; pending strictly decreases inside a read.'},
    ],
    'interpretation': [
        'Large candidate token counts are preflight measurement results; they are distinct from model_context_budget events attached to actual paid requests.',
        'The observed long pause after call14 ended in a selected one-response paid durable recovery and call15, without process restart or source mutation.',
        'Finite exact prefix scans can still be expensive when a large source frontier has no admissible full repair forecast; no claim of low latency or a global monotone maximum is made.',
    ],
}
path = STAGE / 'analysis/generation_capacity_preflight_audit.json'
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({key: report[key] for key in ('updated_utc', 'last_event', 'paid_logical_request_starts',
    'tokenization_count_events', 'recorded_tokenizer_http_attempts', 'tokenizer_cache_hit_events',
    'tokenizer_failed_attempts', 'tokenizer_http_retries', 'actual_generation_context_checks',
    'actual_generation_over_context', 'actual_generation_max_input_tokens', 'actual_generation_max_total_tokens',
    'between_call14_completion_and_call15')}, ensure_ascii=False, indent=2))
