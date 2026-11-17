"""Bounded actual deployment counts of two saved R19 review-wire candidates."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path('/Users/mao/projects/dagv2-personamem-v4')
ANALYSIS = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
REPORT = ANALYSIS / 'r20_review_wire_actual_token_comparison.json'
SUMMARY = ANALYSIS / 'r20_review_wire_actual_token_comparison.md'
REPLAY = ANALYSIS / 'r19_saved_review_wire_replay.json'
CONFIG = ROOT / 'configs/personamem-v4.json'


def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = Path(args[0].decode() if isinstance(args[0], bytes) else args[0])
        if path.name in {'evaluation_only.json', 'summary.json'} or 'scores' in path.parts:
            raise RuntimeError('Labels and scores are outside this comparison')
        mode = args[1]
        if isinstance(mode, str) and any(flag in mode for flag in 'wax+'):
            if path.resolve() not in {REPORT, SUMMARY}:
                raise RuntimeError('Comparison may only write its two external receipts')


sys.addaudithook(guard)
sys.path.insert(0, str(ROOT))
from dagbt import review_wire
from dagbt.config import resolve
from dagbt.model_runtime import prepare_request
from dagbt.reasoning import Reasoner
from dagbt.token_counting import DeploymentTokenCounter, TokenizationError


def serialized(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def main():
    if REPORT.exists() or SUMMARY.exists():
        raise SystemExit('Receipts already exist; no repeated counting is permitted')
    start = datetime.now(timezone.utc).isoformat()
    replay_bytes = REPLAY.read_bytes()
    replay = json.loads(replay_bytes)
    selected = [row for row in replay['requests'] if row['applied'] is True]
    assert len(selected) == 2, 'Only the two previously applied saved requests are authorized'
    config_bytes = CONFIG.read_bytes()
    config = json.loads(config_bytes)
    config_identity = serialized(config)
    settings = resolve(config, 'dagbt_residual_memory_v2')
    reasoner = Reasoner(None, None, config, settings, None, lambda event: None)
    source_paths = [ROOT / 'dagbt' / name for name in
                    ['review_wire.py', 'reasoning.py', 'model_runtime.py', 'token_counting.py', 'config.py']]
    source_before = {str(path.relative_to(ROOT)): path.read_bytes() for path in source_paths}
    assert sha(source_before['dagbt/review_wire.py']) == replay['codec_sha256']
    saved_records, prepared, rows = [], [], []
    delimiter = '\n\nReturn one complete JSON object matching this schema:\n'
    for selected_row in selected:
        path = Path(replay['attempt']) / 'requests' / selected_row['request_file']
        raw = path.read_bytes()
        assert sha(raw) == selected_row['request_file_sha256']
        saved = json.loads(raw)
        old = saved['payload']
        old_identity = serialized(old)
        assert len(old['messages']) == 2
        assert [message['role'] for message in old['messages']] == ['system', 'user']
        system, found, schema_text = old['messages'][0]['content'].rpartition(delimiter)
        assert found and review_wire.INSTRUCTION not in system
        schema = json.loads(schema_text)
        data = json.loads(old['messages'][1]['content'])
        original_data = serialized(data)
        assert sha(original_data) == selected_row['old_user_json_sha256']
        stage = saved['stage']
        assert stage[0] == 'joint_read_repair' and stage[1] in {'7', '8'}
        old_reasoning = reasoner._payload(stage[0], system, data, schema,
                                         output_token_cap=old['max_tokens'])
        _, reconstructed_old, _ = prepare_request(stage, reasoner.url, old_reasoning, config)
        assert serialized(reconstructed_old) == old_identity, 'Saved payload not reproduced exactly'
        packed, applied = review_wire.pack_with_status(data)
        assert applied and serialized(review_wire.unpack(packed)) == original_data
        assert serialized(data) == original_data
        assert sha(serialized(packed)) == selected_row['new_user_json_sha256']
        new_reasoning = reasoner._payload(stage[0], system + review_wire.INSTRUCTION, packed, schema,
                                         output_token_cap=old['max_tokens'])
        _, new, _ = prepare_request(stage, reasoner.url, new_reasoning, config)
        assert serialized({key: value for key, value in old.items() if key != 'messages'}) == serialized(
            {key: value for key, value in new.items() if key != 'messages'})
        assert new['messages'][0]['content'] == system + review_wire.INSTRUCTION + delimiter + schema_text
        assert old['messages'][1]['content'] == original_data.decode('utf-8')
        assert new['messages'][1]['content'] == serialized(packed).decode('utf-8')
        assert serialized(old) == old_identity
        saved_records.append((path, raw))
        prepared.append((reconstructed_old, new))
        rows.append({'request_file': path.name, 'request_file_sha256': sha(raw), 'stage': stage,
                     'applied': True, 'old_payload_exactly_reconstructed': True,
                     'ordered_type_sensitive_inverse': True, 'schema_and_other_payload_fields_unchanged': True,
                     'old_payload_sha256': sha(old_identity), 'new_payload_sha256': sha(serialized(new)),
                     'old_user_json_sha256': sha(original_data), 'new_user_json_sha256': sha(serialized(packed)),
                     'output_token_reserve': old['max_tokens'], 'input_margin': settings['input_margin'],
                     'safety_reserve': 8, 'context_limit': settings['context_tokens']})

    # All structural assertions above precede any network call.
    events = []
    counter = DeploymentTokenCounter(config, events.append)
    configured_attempts = counter.options['max_identical_attempts']
    # This independent diagnostic counter is not a shared run object. Keep the
    # actual config and wire unchanged but do not retry a failed measurement.
    counter.options['max_identical_attempts'] = 1
    opener = counter._opener
    http_opens = []

    class TokenizeOnlyOpener:
        def open(self, request, **kwargs):
            if request.full_url != counter.options['endpoint'] or request.get_method() != 'POST':
                raise TokenizationError('comparison_forbidden_endpoint')
            body = json.loads(request.data)
            if set(body) != {'model', 'messages', 'add_generation_prompt'} or body['add_generation_prompt'] is not True:
                raise TokenizationError('comparison_forbidden_payload')
            if len(http_opens) >= 4:
                raise TokenizationError('comparison_count_limit')
            http_opens.append(sha(request.data))
            return opener.open(request, **kwargs)

    counter._opener = TokenizeOnlyOpener()
    count_invocations = 0
    failure = None
    for index, pair in enumerate(prepared):
        for side, payload in zip(['old', 'new'], pair):
            count_invocations += 1
            try:
                result = counter.count(payload)
            except TokenizationError as error:
                failure = {'request_index': index, 'side': side, 'error_category': error.category,
                           'http_status': error.http_status}
                break
            rows[index][side] = result
            rows[index][side + '_total_with_existing_reserves'] = (
                result['count'] + rows[index]['output_token_reserve'] + settings['input_margin'] + 8)
        if failure:
            break
        rows[index]['input_token_reduction_old_minus_new'] = rows[index]['old']['count'] - rows[index]['new']['count']

    assert len(events) == count_invocations <= 4
    assert all(event['http_retries'] == 0 for event in events)
    assert serialized(config) == config_identity and serialized(counter.config) == config_identity
    assert CONFIG.read_bytes() == config_bytes and REPLAY.read_bytes() == replay_bytes
    assert all(path.read_bytes() == raw for path, raw in saved_records)
    assert all((ROOT / relative).read_bytes() == content for relative, content in source_before.items())
    report = {'scope': 'Actual deployment counts of two already-sent saved R19 repair requests only',
              'started_utc': start, 'ended_utc': datetime.now(timezone.utc).isoformat(),
              'source_commit': '6c046374008ce2e45f817d6bc9876b3ab927ab18',
              'source_root': str(ROOT), 'attempt': replay['attempt'],
              'replay_sha256': sha(replay_bytes), 'config_sha256': sha(config_bytes),
              'source_sha256': {name: sha(content) for name, content in source_before.items()},
              'configuration_modified': False, 'saved_requests_modified': False, 'source_modified': False,
              'labels_or_scores_read': False, 'generation_calls': 0, 'embedding_calls': 0,
              'count_invocations': count_invocations, 'http_attempts': len(http_opens),
              'diagnostic_counter_max_identical_attempts': 1, 'configured_max_identical_attempts': configured_attempts,
              'retry_policy_scope': 'Only this private diagnostic counter options; current run/config/requests unchanged',
              'success': failure is None, 'failure': failure, 'events': events, 'requests': rows,
              'unissued_77_source_request_reconstructed': False, 'case_success_established': False,
              'limit': 'These are saved repairs 7/8, not the later unavailable 77-source candidate; no claim about the 367-token gap, R20 success or answer quality.'}
    with REPORT.open('x') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    if failure:
        conclusion = f"计数未完成：{failure['side']} 请求计数失败（{failure['error_category']}），已停止后续计数且未重试。"
    else:
        conclusion = '\n'.join(f"- 保存的 repair {row['stage'][1]}：输入 {row['old']['count']} → {row['new']['count']} tokens；旧减新为 {row['input_token_reduction_old_minus_new']:+d}。" for row in rows)
    with SUMMARY.open('x') as handle:
        handle.write('# R20 review-wire 实际 token 对比\n\n' + conclusion + '\n\n')
        handle.write('仅测 R19 已发送的两个 repair 请求；先确认旧 payload 精确重建及新层无损 inverse，再按当前部署 tokenizer 计数。只在独立诊断 counter 禁用重试，实验配置及其重试策略未改。未生成、未 embedding、未读取标签或评分、未改源码或运行记录。\n\n')
        handle.write('不重建尚未发送的 77-source 请求，不由本结果推断已填补 367-token 缺口、案例成功或准确率改善。\n')
    print(json.dumps({'success': report['success'], 'count_invocations': count_invocations,
                      'http_attempts': len(http_opens), 'failure': failure,
                      'requests': [{key: row.get(key) for key in ['stage', 'input_token_reduction_old_minus_new',
                                   'old_total_with_existing_reserves', 'new_total_with_existing_reserves']}
                                   for row in rows], 'report_sha256': sha(REPORT.read_bytes())}, ensure_ascii=False))


if __name__ == '__main__':
    main()
