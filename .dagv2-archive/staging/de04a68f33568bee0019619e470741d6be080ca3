"""Saved-request closure counts only; no model text output or service calls."""
import hashlib
import json
from collections import Counter
from pathlib import Path

RUN = Path('/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r17')
OUT = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r17_closure_review.json')
COMMIT = 'bcbd16f6b9e2cc5545d32b15cc21ae1d6a74cc94'


def load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def collect(value, required):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'source_ids':
                required.update(item)
            elif key not in ('value', 'output'):
                collect(item, required)
    elif isinstance(value, list):
        for item in value:
            collect(item, required)


cases = []
for attempt in (RUN / 'personamem/dagbt_residual_memory_v2/attempts').glob('*/attempt-*'):
    events = []
    event_path = attempt / 'fusion_events.jsonl'
    if event_path.exists():
        for line in event_path.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    requests = []
    identities = set()
    for path in (attempt / 'requests').glob('*.json'):
        item = load(path)
        if not item:
            continue
        stage = item.get('stage', [])
        if len(stage) != 2 or stage[0] not in ('joint_read', 'semantic_compose', 'audit_joint'):
            continue
        try:
            data = json.loads(item['payload']['messages'][1]['content'])
        except (ValueError, KeyError, IndexError, TypeError):
            continue
        if stage[0] == 'joint_read' and data.get('task', {}).get('execution') != 'compose':
            continue
        if 'known_observation_columns' in data:
            columns = data['known_observation_columns']
            values = data.get('known_observation_values', [])
            data['known_observations'] = [dict(zip(columns, [
                values[cell['shared']] if isinstance(cell, dict) and set(cell) == {'shared'} else cell
                for cell in row])) for row in data['known_observations']]
        required = set()
        for key in ('known_observations', 'supported_parents', 'supported_task_outputs', 'evidence_obligations'):
            collect(data.get(key, []), required)
        for record in data.get('failed_batch_reviews', []):
            required.update(record.get('source_ids', []))
        if 'source_span_columns' in data:
            column = data['source_span_columns'].index('id')
            visible = {row[column] for row in data['source_spans']}
        else:
            visible = {row['id'] for row in data['source_spans']}
        identity = data['request_context']['query_identity']
        identities.add((stage[0], identity))
        requests.append({'stage': stage, 'operation': stage[0],
                         'identity_hash': hashlib.sha256(str(identity).encode()).hexdigest(),
                         'required_source_count': len(required), 'visible_source_count': len(visible),
                         'missing_required_count': len(required - visible),
                         'extra_visible_count': len(visible - required),
                         'complete_visible_source_set_hash': hashlib.sha256(json.dumps(sorted(visible)).encode()).hexdigest()})
    groups = []
    for operation, identity in sorted(identities):
        batches = [event for event in events if event.get('event') == 'joint_read_completed'
                   and event.get('operation') == operation and event.get('identity') == identity]
        groups.append({'operation': operation,
                       'identity_hash': hashlib.sha256(str(identity).encode()).hexdigest(),
                       'completed_event_count': len(batches),
                       'complete_batch_count': sum(bool(batch.get('complete')) for batch in batches),
                       'every_batch_aliases_equal_visible_sources': all(
                           set(batch.get('source_aliases', [])) == set(batch.get('visible_source_aliases', []))
                           for batch in batches),
                       'batch_source_counts': [len(batch.get('source_aliases', [])) for batch in batches]})
    cases.append({'attempt_path': str(attempt.relative_to(RUN)),
                  'result_saved': (attempt / 'result.json').exists(),
                  'requests': sorted(requests, key=lambda item: int(item['stage'][1])),
                  'identity_batch_groups': groups})
report = {'run': 'v4_validation_r17', 'source_commit': COMMIT,
          'scope': 'Saved mandatory-input source-ID set counts only. No labels, model text, services, or run mutations. Extra visible sources may be authorized clues and require separate review; multiple batches for one identity are not automatically a bug.',
          'cases': cases}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
requests = [row for case in cases for row in case['requests']]
groups = [row for case in cases for row in case['identity_batch_groups']]
print(json.dumps({'request_counts_by_operation': dict(Counter(row['operation'] for row in requests)),
                  'requests_missing_required_sources': sum(row['missing_required_count'] > 0 for row in requests),
                  'requests_with_extra_visible_sources': sum(row['extra_visible_count'] > 0 for row in requests),
                  'multiple_batch_identity_count': sum(row['completed_event_count'] > 1 for row in groups),
                  'batch_alias_visibility_mismatch_count': sum(not row['every_batch_aliases_equal_visible_sources'] for row in groups)}, ensure_ascii=False))
