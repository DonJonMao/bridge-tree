"""Summarize saved R16 scalar records only; no labels, services, or run writes."""
import json
import hashlib
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPORTS = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
RELEASE = Path('/Users/mao/projects/dagv2-personamem-v4')
RUN = RELEASE / 'outputs/v4_validation_r16'
sys.dont_write_bytecode = True
sys.path.insert(0, str(RELEASE))
from dagbt.runner import result_path, validate_result


def load(path):
    return json.loads(path.read_text())


manifest = load(RUN / 'manifest.json')
assert all(hashlib.sha256((RELEASE / name).read_bytes()).hexdigest() == expected
           for name, expected in manifest['source_hashes'].items()), 'Frozen source hash mismatch'
ids = manifest['question_ids']['personamem']
assert len(ids) == len(set(ids)) == 14
monitor = load(REPORTS / 'r16_structural_monitor.json')
cases = monitor['cases']
assert len(cases) == 14 and {row['unit_id'] for row in cases} == set(ids)
arms = {}
for arm in manifest['arms']:
    rows = {}
    for path in (RUN / 'personamem' / arm / 'rows').glob('*.json'):
        result = load(path)
        unit = result.get('unit_id')
        if unit not in ids:
            continue
        assert unit not in rows, 'Duplicate authoritative unit row'
        assert path == result_path(RUN, 'personamem', arm, unit), 'Noncanonical row path'
        validate_result(result, unit)
        assert result.get('runner', {}).get('dataset') == 'personamem'
        assert result.get('runner', {}).get('arm') == arm
        rows[unit] = {'question_index': ids.index(unit), 'unit_id': unit,
                      'status': result.get('answer', {}).get('status')}
    assert set(rows) == set(ids), f'{arm}: authoritative rows not complete'
    arms[arm] = {'authoritative_rows': len(rows),
                 'status_counts': dict(Counter(row['status'] for row in rows.values())),
                 'cases': sorted(rows.values(), key=lambda row: row['question_index'])}

progress = load(RUN / 'progress.json')
assert progress.get('state') in {'complete', 'complete_with_failures'}, 'Run not naturally complete'
commit = subprocess.check_output(['git', '-C', str(RELEASE), 'rev-parse', 'HEAD'], text=True).strip()
assert commit == 'b9e28a7faa8d419f9f1283574fa095399919c243', 'Release changed before final report'
dirty = subprocess.check_output(['git', '-C', str(RELEASE), 'status', '--porcelain', '--untracked-files=no'], text=True)
assert not dirty, 'Tracked release source differs from recorded commit'

slot_case_counts = Counter()
slot_occurrences = Counter()
error_case_counts = Counter()
protocol_case_counts = Counter()
capacity_cases = []
for row in cases:
    slot_case_counts.update(row['failure_categories'].keys())
    slot_occurrences.update(row['failure_categories'])
    error_case_counts.update(row['error_type_counts'].keys())
    protocol_case_counts.update(row.get('protocol_error_categories', {}).keys())
    if (row['capacity_unavailable_batches'] or row['capacity_rejection_count']
            or 'InputOverflow' in row['error_type_counts']):
        capacity_cases.append(row['question_index'] + 1)

totals = {key: sum(row.get(key) or 0 for row in cases)
          for key in ('llm_used', 'json_repairs_used', 'history_calls',
                      'terminal_calls', 'audit_calls', 'ann_used')}
closure = load(REPORTS / 'r16_closure_review.json')
closure_requests = [row for case in closure['cases'] for row in case['requests']]
closure_groups = [row for case in closure['cases'] for row in case['identity_batch_groups']]
closure_summary = {
    'initial_requests_by_operation': dict(Counter(row['operation'] for row in closure_requests)),
    'requests_missing_required_sources': sum(row['missing_required_count'] > 0 for row in closure_requests),
    'requests_with_extra_visible_sources': sum(row['extra_visible_count'] > 0 for row in closure_requests),
    'identity_groups_with_multiple_batches': sum(row['completed_event_count'] > 1 for row in closure_groups),
    'identity_groups_with_alias_visibility_mismatch': sum(not row['every_batch_aliases_equal_visible_sources'] for row in closure_groups),
    'note': 'Actual archived initial compose/audit requests only; per-request required IDs derive from known rows/counters, supported parents/task outputs, obligations, and failed-review originals. Repairs are counted in the case cost table, not as initial requests here.'
}
summary = {
    'run': 'v4_validation_r16', 'source_commit': commit,
    'source_tracked_files_clean': True,
    'canonical_rows_validated': sum(data['authoritative_rows'] for data in arms.values()),
    'frozen_source_hashes_verified': len(manifest['source_hashes']),
    'scope': 'Natural fixed-14 structural outcomes only. No labels read, no predictions exported, no accuracy scoring, no services or run mutations.',
    'progress': {key: progress.get(key) for key in ('state', 'failed_arm_tasks', 'updated_unix')},
    'arms': arms, 'dagbt_cases': cases, 'dagbt_cost_totals': totals,
    'dagbt_failed_slot_case_counts_overlapping': dict(slot_case_counts),
    'dagbt_failed_slot_occurrence_counts': dict(slot_occurrences),
    'dagbt_error_type_case_counts_overlapping': dict(error_case_counts),
    'dagbt_protocol_error_case_counts_overlapping': dict(protocol_case_counts),
    'dagbt_cases_with_capacity_events_1_based': capacity_cases,
    'mandatory_scope_check': closure_summary,
    'interpretation': 'ok denotes protocol/process success, not answer correctness. Failure categories overlap and are observations, not exclusive causal attribution. A legal audit correction can require a new identity and one new compose/audit batch.',
}
(REPORTS / 'r16_final_structural_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')

lines = [
    '# R16 固定 14 题结构验证汇总', '',
    f'冻结源码：`{commit}`。自然结束：`{progress["state"]}`。报告生成时 release tracked files clean。', '',
    '本报告未读取标签、未导出题目/选项/答案文本、未评分。`ok` 仅表示执行和协议流程完成，不表示回答正确。', '',
    '| 方法 | 已发布题数 | 状态 |', '| --- | ---: | --- |',
]
for arm, data in arms.items():
    lines.append(f'| {arm} | {data["authoritative_rows"]} | {json.dumps(data["status_counts"], ensure_ascii=False)} |')
lines += ['', 'DAGBT 逐题记录（编号从 1 开始）：', '',
          '| 题号 | 状态 | LLM | JSON 修复 | history | terminal | audit | 失败类别 |',
          '| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |']
for row in cases:
    categories = list(row['failure_categories'])
    categories += list(row.get('protocol_error_categories', {}))
    categories += [name for name in row['error_type_counts'] if name not in categories]
    if row['capacity_unavailable_batches'] and 'InputOverflow' not in categories:
        categories.append('capacity_unavailable')
    lines.append('| ' + ' | '.join(str(value) for value in (
        row['question_index'] + 1, row['status'], row['llm_used'], row['json_repairs_used'],
        row['history_calls'], row['terminal_calls'], row['audit_calls'], '; '.join(categories) or '无')) + ' |')
lines += ['', '类别可以重叠，不能将不同类别的题数相加。合法审计纠正可以产生新的 identity 和新的 compose/audit batch。', '',
          f'出现容量相关事件的题号：{capacity_cases}。', '',
          f'真实 mandatory 请求结构计数：{json.dumps(closure_summary, ensure_ascii=False)}', '',
          '仅记录当前固定运行的结构结果，不沿用前次运行的逐题归因。', '']
(REPORTS / 'r16_final_structural_summary.md').write_text('\n'.join(lines))
print(json.dumps({'report': str(REPORTS / 'r16_final_structural_summary.json'),
                  'markdown': str(REPORTS / 'r16_final_structural_summary.md'),
                  'source_commit': commit, 'progress': summary['progress'],
                  'arm_status_counts': {arm: data['status_counts'] for arm, data in arms.items()},
                  'dagbt_cost_totals': totals,
                  'mandatory_scope_check': closure_summary,
                  'dagbt_capacity_cases_1_based': capacity_cases}, ensure_ascii=False))
