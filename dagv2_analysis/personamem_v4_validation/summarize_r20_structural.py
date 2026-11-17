"""Summarize saved R20 scalar records only; no labels, services, or run writes."""
import json
import hashlib
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPORTS = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
RELEASE = Path('/Users/mao/projects/dagv2-personamem-v4')
RUN = RELEASE / 'outputs/v4_validation_r20'
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
monitor = load(REPORTS / 'r20_structural_monitor.json')
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
receipt = load(REPORTS / 'r20_reader_closed_run_receipt.json')
assert receipt['live_writer'] is False and receipt['validated_canonical_rows'] == 28
assert receipt['state'] == progress['state']
commit = subprocess.check_output(['git', '-C', str(RELEASE), 'rev-parse', 'HEAD'], text=True).strip()
assert commit == '6c046374008ce2e45f817d6bc9876b3ab927ab18', 'Release changed before final report'
assert receipt['source_commit'] == commit
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
closure = load(REPORTS / 'r20_closure_review.json')
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
wire = load(REPORTS / 'r20_history_wire_review.json')
wire_rows = wire['requests']
wire_summary = {
    'shared_history_request_count': len(wire_rows),
    'decode_failures': sum(not row['decode_succeeded'] for row in wire_rows),
    'missing_decode_instruction': sum(not row['decode_instruction_present'] for row in wire_rows),
    'structure_mismatches': sum(row.get('decode_succeeded') and not all(row.get(key) for key in
        ('source_spans_unchanged', 'nonvalue_row_fields_unchanged', 'scope_and_contract_unchanged')) for row in wire_rows),
    'note': 'Actual saved requests containing shared_history_texts, including scoped repairs. Decoding checks preserve original-source spans, nonvalue metadata, scope, and contract; no labels or answer correctness evaluated.'
}
review_wire = load(REPORTS / 'r20_review_wire_review.json')
review_rows = review_wire['requests']
review_wire_summary = {
    'review_wire_request_count': len(review_rows),
    'decode_failures': sum(not row['decode_succeeded'] for row in review_rows),
    'missing_decode_instruction': sum(not row['decode_instruction_present'] for row in review_rows),
    'structure_mismatches': sum(row.get('decode_succeeded') and not all(row.get(key) for key in
        ('registered_row_metadata_unchanged', 'external_scope_contract_source_fields_unchanged',
         'deterministic_repack_applied', 'deterministic_repack_bytes_match')) for row in review_rows),
    'note': 'Actual saved shared_review_texts requests only. Exact decoding/repacking does not prove model comprehension or equivalence to an unavailable pre-encoding runtime object. Zero requests is no online validation.'
}
frontier = load(REPORTS / 'r20_frontier_review.json')
assert frontier['source_commit'] == commit
assert frontier['canonical_residual_rows'] == 14
assert {row['unit_id'] for row in frontier['cases']} == set(ids)
assert frontier['progress_state'] == progress['state']
frontier_summary = {
    'canonical_rows_reviewed': len(frontier['cases']),
    'reader_reached_cases': sum(row.get('reader_reached', False) for row in frontier['cases']),
    'source_identities_rebuilt': sum(row.get('source_content_rebuilt', 0) for row in frontier['cases']),
    'frontier_entries': sum(row.get('frontier_entries', 0) for row in frontier['cases']),
    'exposures_traced_to_wire': sum(row.get('exposures_traced_to_wire', 0) for row in frontier['cases']),
    'confirmed_failures': sum(len(row['confirmed_failures']) for row in frontier['cases']),
    'requires_review': sum(len(row['requires_review']) for row in frontier['cases']),
    'successful_terminal_dependencies_checked': sum(row.get('successful_terminal_dependencies_checked', False) for row in frontier['cases']),
    'note': 'Canonical source identity, actual request exposure, per-query frontier/read/hard-work disjointness, current terminal bindings and supported audit reviewed. Stored history does not prove every unrecorded historical transition or semantic completeness.'
}
frontier['review_state'] = 'closed_run_observation'
frontier['closed_run_receipt'] = 'r20_reader_closed_run_receipt.json'
(REPORTS / 'r20_frontier_review.json').write_text(json.dumps(frontier, ensure_ascii=False, indent=2) + '\n')
tokenization = load(REPORTS / 'r20_tokenization_review.json')
tokenization_summary = {arm: {key: value for key, value in record.items() if key != 'failed_requests'}
    for arm, record in tokenization['arms'].items()}
failure_classification = {}
for arm, record in arms.items():
    service_cases = {event['question_index'] for event in tokenization['arms'][arm]['failed_requests']}
    structural_cases = {row['question_index'] + 1 for row in cases
        if row['failure_categories'] or any(kind != 'TokenizationError' for kind in row['error_type_counts'])}
    if arm == 'original':
        structural_cases = set()
    failed_cases = {row['question_index'] + 1 for row in record['cases'] if row['status'] != 'ok'}
    failure_classification[arm] = {
        'tokenization_failure_evidence_only': sorted((failed_cases & service_cases) - structural_cases),
        'non_tokenization_failure_evidence_only': sorted((failed_cases & structural_cases) - service_cases),
        'mixed_tokenization_and_other_failure_evidence': sorted(failed_cases & service_cases & structural_cases),
        'other_unclassified_failed_cases': sorted(failed_cases - service_cases - structural_cases),
    }
summary = {
    'run': 'v4_validation_r20', 'source_commit': commit,
    'source_tracked_files_clean': True,
    'canonical_rows_validated': sum(data['authoritative_rows'] for data in arms.values()),
    'frozen_source_hashes_verified': len(manifest['source_hashes']),
    'scope': 'Natural fixed-14 structural outcomes only. This analysis reads no labels/scores, exports no predictions, performs no accuracy scoring/services/run mutation; runner may auto-score independently.',
    'progress': {key: progress.get(key) for key in ('state', 'failed_arm_tasks', 'updated_unix')},
    'arms': arms, 'dagbt_cases': cases, 'dagbt_cost_totals': totals,
    'dagbt_failed_slot_case_counts_overlapping': dict(slot_case_counts),
    'dagbt_failed_slot_occurrence_counts': dict(slot_occurrences),
    'dagbt_error_type_case_counts_overlapping': dict(error_case_counts),
    'dagbt_protocol_error_case_counts_overlapping': dict(protocol_case_counts),
    'dagbt_cases_with_capacity_events_1_based': capacity_cases,
    'mandatory_scope_check': closure_summary,
    'tokenization_external_failures': tokenization_summary,
    'recorded_failure_classification_1_based': failure_classification,
    'handoff_deferred_events': sum(row.get('capacity_deferred_count', 0) for row in cases),
    'cost_totals_scope': 'Observed ledger usage only; missing ledger fields are not proof of zero cost. Failed tokenizer request cost is reported separately from algorithm budgets.',
    'shared_history_wire_check': wire_summary,
    'shared_review_wire_check': review_wire_summary,
    'frontier_source_exposure_check': frontier_summary,
    'strict_check': receipt['strict_check'],
    'interpretation': 'ok denotes protocol/process success, not answer correctness. Failure categories overlap and are observations, not exclusive causal attribution. A legal audit correction can require a new identity and one new compose/audit batch.',
}
(REPORTS / 'r20_final_structural_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')

lines = [
    '# R20 固定 14 题结构验证汇总', '',
    f'冻结源码：`{commit}`。自然结束：`{progress["state"]}`。报告生成时 release tracked files clean。', '',
    '本报告未读取标签或评分文件、未评分；报告不包含题目/选项/答案文本。runner 自身在全部任务终态后可能自动评分。`ok` 仅表示执行和协议流程完成，不表示回答正确。', '',
    '| 方法 | 已发布题数 | 状态 |', '| --- | ---: | --- |',
]
for arm, data in arms.items():
    lines.append(f'| {arm} | {data["authoritative_rows"]} | {json.dumps(data["status_counts"], ensure_ascii=False)} |')
lines += ['', '按已保存 tokenizer 与非 tokenizer 失败证据分类（题号从 1 开始；类别是观测证据，不是反事实归因）：' + json.dumps(failure_classification, ensure_ascii=False), '',
          'DAGBT 逐题记录（编号从 1 开始）：', '',
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
lines += ['', ('本轮没有实际 compose/audit 请求；相关零异常计数来自空集合，不能据此宣称终端或审计验证通过。' if not closure_requests else '实际终端与审计请求按保存材料检查；计数不替代语义正确性。'), '', '类别可以重叠，不能将不同类别的题数相加。合法审计纠正可以产生新的 identity 和新的 compose/audit batch。', '',
          f'出现容量相关事件的题号：{capacity_cases}。', '',
          f'真实 mandatory 请求结构计数：{json.dumps(closure_summary, ensure_ascii=False)}', '',
          f'两臂独立 tokenization 故障汇总：{json.dumps(tokenization_summary, ensure_ascii=False)}', '',
          'Tokenization connection_or_timeout 是外部连接/等待失败，与真实 InputOverflow 及模型协议错误分别统计；保存请求已经执行既有有界同请求重试。没有停止、重启或放宽服务及预算。含这类失败的本轮不能据此证明算法质量下降或修改有效。', '',
          '费用字段只汇总已记录的账本；缺少字段不等于零成本，失败 tokenizer 请求耗时另列。', '',
          f'真实 shared_history_texts 请求结构计数：{json.dumps(wire_summary, ensure_ascii=False)}', '',
          f'真实 shared_review_texts 请求结构计数：{json.dumps(review_wire_summary, ensure_ascii=False)}', '',
          f'探索前沿、原文身份与实际曝光检查：{json.dumps(frontier_summary, ensure_ascii=False)}', '',
          f'独立闭合回执 smoke gate：{json.dumps(receipt["strict_check"], ensure_ascii=False)}', '',
          '仅记录当前固定运行的结构结果，不沿用前次运行的逐题归因。', '']
(REPORTS / 'r20_final_structural_summary.md').write_text('\n'.join(lines))
print(json.dumps({'report': str(REPORTS / 'r20_final_structural_summary.json'),
                  'markdown': str(REPORTS / 'r20_final_structural_summary.md'),
                  'source_commit': commit, 'progress': summary['progress'],
                  'arm_status_counts': {arm: data['status_counts'] for arm, data in arms.items()},
                  'dagbt_cost_totals': totals,
                  'mandatory_scope_check': closure_summary,
    'tokenization_external_failures': tokenization_summary,
    'recorded_failure_classification_1_based': failure_classification,
    'handoff_deferred_events': sum(row.get('capacity_deferred_count', 0) for row in cases),
    'cost_totals_scope': 'Observed ledger usage only; missing ledger fields are not proof of zero cost. Failed tokenizer request cost is reported separately from algorithm budgets.',
                  'shared_history_wire_check': wire_summary,
                  'shared_review_wire_check': review_wire_summary,
                  'frontier_source_exposure_check': frontier_summary,
                  'strict_check': receipt['strict_check'],
                  'dagbt_capacity_cases_1_based': capacity_cases}, ensure_ascii=False))
