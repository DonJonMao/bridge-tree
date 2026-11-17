"""Collect fixed-scope regression and production execution evidence, without scoring."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path('/Users/mao/projects/dagv2-personamem-a48')
sys.path.insert(0, str(ROOT))
from dagbt import runner
from dagbt.config import resolve
from dagbt.methods import RESIDUAL

BASE = Path(__file__).parent
OUT = BASE / 'live_smoke_03'
RELEASE = Path('/Users/mao/projects/dagv2_deploy/20261012_a48dc8d_v3_1')
PROFILE = 'configs/residual-memory.personamem16k.json'
BASE_METADATA = Path('/Users/mao/projects/dagv2_deploy/20261011_a48dc8d_v3/patch/payload/DEPLOYMENT.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = runner.load(OUT / 'manifest.json')
    summary = runner.load(OUT / 'smoke_summary.json')
    assert manifest['source_hashes'] == summary['source_hashes'] == runner.frozen_sources()
    assert summary['counts'] == {'ok': 4}
    assert summary['labels_read'] is manifest['labels_read'] is False
    assert manifest['question_attempts'] == summary['question_attempts'] == 1
    assert manifest['arms'] == ['original', RESIDUAL]
    questions = manifest['question_ids']['personamem']
    uploaded = runner.load(Path('/Users/mao/projects/dagv2_analysis/a48_v3_server_failure/personamem_a48_v3_smoke/manifest.json'))
    assert questions == uploaded['question_ids']['personamem'] and len(questions) == 2
    config = runner.load(ROOT / PROFILE)
    assert config == manifest['config'] == uploaded['config']
    budgets = {k: resolve(config, RESIDUAL)[k] for k in (
        'context_tokens', 'llm_calls', 'ann_calls', 'reasoning_output_tokens',
        'input_margin', 'json_repairs', 'max_repairs_per_request')}
    assert budgets == dict(context_tokens=16384, llm_calls=24, ann_calls=36,
        reasoning_output_tokens=4096, input_margin=256, json_repairs=6, max_repairs_per_request=2)
    rows = []
    for arm in manifest['arms']:
        for question in questions:
            row = runner.load(runner.result_path(OUT, 'personamem', arm, question))
            assert row['answer']['status'] == 'ok'
            path = Path('personamem') / arm / 'attempts' / runner.digest(question) / 'attempt-001'
            assert row['attempt_directories'] == [str(path)] and row['runner']['attempt'] == 1
            directory = OUT / path
            assert [p.name for p in directory.parent.glob('attempt-*')] == ['attempt-001']
            seeded = set(runner.load(directory / 'seeded_requests.json'))
            chats = []
            for request_path in (directory / 'requests').glob('*.json'):
                request = runner.load(request_path)
                payload = request.get('payload', {})
                if 'messages' not in payload:
                    continue
                assert request_path.stem not in seeded
                validation = request['tokenization_validation']
                prompt = request['response']['usage']['prompt_tokens']
                assert validation['status'] == 'matched'
                assert prompt == validation['expected_prompt_tokens'] == validation['observed_prompt_tokens']
                total = prompt + payload['max_tokens'] + 8 + (256 if arm == RESIDUAL else 0)
                assert total <= 16384
                chats.append({'prompt_tokens': prompt, 'total_with_reserves': total})
            assert chats
            item = dict(arm=arm, unit_id=question, status='ok', seconds=row['seconds'],
                chat_records=len(chats), max_prompt_tokens=max(c['prompt_tokens'] for c in chats),
                max_total_with_reserves=max(c['total_with_reserves'] for c in chats))
            if arm == RESIDUAL:
                diagnostic = row['diagnostics']
                assert diagnostic['audit_complete']
                assert not diagnostic['joint_reading']['failed_obligations']
                assert not diagnostic['joint_reading']['unread_obligations']
                state = diagnostic['fact_state']
                contract = state['contract']
                terminal = row['answer']['final_node_id']
                scopes = {}
                for variable, declaration in state['program']['variables'].items():
                    scope = declaration.get('scope', {k: contract[k] for k in ('entity_scope', 'time_scope')})
                    if declaration['demand'] == terminal:
                        assert scope == {k: contract[k] for k in ('entity_scope', 'time_scope')}
                    scopes[variable] = scope
                for route in state['routes']:
                    # Obsolete dynamic declarations remain valid provenance,
                    # even though the fact store excludes them from current bindings.
                    programs = [state['program'], *(r['program'] for r in state['instantiations'])]
                    declared = [p['variables'][route['variable']] for p in programs
                        if route['variable'] in p['variables']]
                    route_scope = {k: route[k] for k in ('entity_scope', 'time_scope')}
                    assert any(route_scope == d.get('scope', {
                        k: contract[k] for k in ('entity_scope', 'time_scope')}) for d in declared)
                item.update(audit_complete=True, failed_obligations=0, variable_scopes=scopes,
                    terminal_scope={k: contract[k] for k in ('entity_scope', 'time_scope')},
                    ledger_used=diagnostic['ledger']['used'])
            cost = runner.request_cost(directory)
            auxiliary = cost['tokenization']
            assert auxiliary['failed_counts'] == auxiliary['malformed_event_lines'] == 0
            item['tokenization_auxiliary_cost'] = auxiliary
            item['api_cost_excluding_tokenization'] = {k: cost[k] for k in (
                'physical_llm_attempts', 'physical_reader_attempts', 'prompt_tokens',
                'completion_tokens', 'total_tokens', 'token_usage_complete')}
            rows.append(item)
    replay = runner.load(BASE / 'scope_response_replay.json')
    assert replay['passed'] is True
    assert replay['no_network_calls'] is True and replay['evaluation_labels_read'] is False
    assert all(replay['checks'].values())
    for name, expected in replay['tested_source_hashes'].items():
        assert sha(ROOT / 'dagbt' / name) == expected
    fixture = runner.load(BASE / 'packaging_fixture_verification.json')
    assert fixture['passed'] is True
    log = BASE / 'pytest_full.log'
    matches = re.findall(r'^(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) warnings)? in ([\d.]+)s(?: \([\d:]+\))?$',
        log.read_text(), re.MULTILINE)
    assert matches
    passed, skipped, warnings, seconds = matches[-1]
    schema_log = BASE / 'pytest_schema.log'
    schema_matches = re.findall(r'^(\d+) passed in ([\d.]+)s$', schema_log.read_text(), re.MULTILINE)
    assert schema_matches and schema_matches[-1][0] == '130'
    prior_runs = []
    for prior_name in ('live_smoke_01', 'live_smoke_02'):
        prior = runner.load(BASE / prior_name / 'smoke_summary.json')
        assert runner.load(BASE / prior_name / 'manifest.json')['config'] == manifest['config']
        for name, expected in replay['tested_source_hashes'].items():
            assert prior['source_hashes']['dagbt/' + name] == expected
        prior_rows = []
        for arm in manifest['arms']:
            for question in questions:
                row = runner.load(runner.result_path(BASE / prior_name, 'personamem', arm, question))
                prior_rows.append(dict(arm=arm, unit_id=question, answer=row['answer'],
                    errors=row.get('diagnostics', {}).get('errors', []),
                    tokenization_auxiliary_cost=row['runner']['cost'].get('tokenization')))
        prior_runs.append(dict(output=prior_name, counts=prior['counts'], rows=prior_rows,
            same_scope_fix_source_and_config=True,
            tokenizer_transport_before_bounded_retries=True))
    report = dict(
        base_commit='da64d56250733bc7a87942f6a5389b04a00176bd',
        base_deployment_sha256=sha(BASE_METADATA),
        uploaded_archive_sha256='2df03ca7dee8cde6f49eef2c450e2a9fa3459f30e3468e8d18e839fd504f5760',
        diagnosis=runner.load(BASE / 'diagnosis_report.json'),
        diagnosis_report_sha256=sha(BASE / 'diagnosis_report.json'),
        exact_response_replay=replay,
        pytest=dict(passed=int(passed), skipped=int(skipped or 0), warnings=int(warnings or 0),
            seconds=float(seconds), log_sha256=sha(log)),
        preceding_pytest_failure=dict(
            test='tests/test_paired_runner.py::test_stop_foreground_relative_output_path',
            log_sha256=sha(BASE / 'pytest_full_initial_failure.log'),
            focused_rerun_log_sha256=sha(BASE / 'pytest_stop_focused.log'),
            note='Initial full run: 1 failed, 1092 passed, 92 skipped. Existing offline worker start/stop race timed out; fixture log showed joining a not-yet-started process. Single focused rerun passed without source changes. Final full-suite result is recorded separately.'),
        schema_supplement=dict(passed=130, skipped=0, log_sha256=sha(schema_log),
            scope='All 92 optional JSON Schema skips plus 38 overlapping checks run with the validator installed.'),
        original_integrity=runner.verify_originals(),
        source_hashes_match_live_validation=True,
        config_unchanged_from_uploaded_v3=True,
        unchanged_budgets=budgets,
        real_service_smoke=dict(question_attempts=1, status_counts={'original': {'ok': 2}, RESIDUAL: {'ok': 2}},
            rows=rows, labels_read=False, answer_accuracy_evaluated=False),
        packaging_scaffold_verification=fixture,
        preceding_live_validation=dict(runs=prior_runs,
            note='Both kept as unsuccessful validation: tokenizer connection/read timeouts prevented residual evidence reading; one original task also failed in the first run.',
            bounded_readonly_probe=runner.load(BASE / 'tokenization_health_probe.json'),
            final_run_reason='Second failure confirmed a repeated tokenizer transport issue. Final code adds bounded identical read-only connection/read retries using the existing request-attempt limit; failed physical attempts remain logged.'),
        limitations=[
            'Two fixed questions validate execution and scope flow, not full-dataset accuracy or reliability.',
            'Scope applicability is still a model semantic judgment; exact scope validation does not independently prove factual correctness.',
            'No budget, backend, source evidence, failure obligation lifetime or retrieval scheduling change. Read-only tokenizer transport now uses the existing max_identical_attempts for bounded transient retries.',
            'Auxiliary deployment-tokenizer traffic/latency remain separate from generation and embedding costs.',
            'Legacy variables without explicit scope inherit the output contract; new planner prompts require explicit applicable variable scopes.'
        ])
    runner.save(RELEASE / 'validation.json', report)
    print(json.dumps({'pytest':report['pytest'], 'rows':rows}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
