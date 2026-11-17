"""Publish validation only after the unchanged-16K production smoke succeeds."""
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
from dagbt.token_counting import validate_tokenization_config

BASE = Path('/Users/mao/projects/dagv2_analysis/a48_v3_validation')
OUT = BASE / 'live_smoke_06'
RELEASE = Path('/Users/mao/projects/dagv2_deploy/20261011_a48dc8d_v3')
PROFILE = Path('configs/residual-memory.personamem16k.json')
OLD_PROFILE = Path('configs/residual-memory.example.json')
RESEARCH_DOC = Path('docs/PREFERENCE_RAG_BASELINE_PROTOCOL_20261012.md')
BUDGET = {'context_tokens': 16384, 'llm_calls': 24, 'ann_calls': 36,
          'reasoning_output_tokens': 4096, 'input_margin': 256}


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def audit_chat_records(directory, arm):
    """Inspect stored validation/usage only; never call a model or tokenizer."""
    chats = []
    seeded = set(runner.load(directory / 'seeded_requests.json'))
    for path in sorted((directory / 'requests').glob('*.json')):
        record = runner.load(path)
        payload = record.get('payload', {})
        if 'messages' not in payload:
            continue
        assert path.stem not in seeded, 'Final smoke must generate chats under final source'
        validation = record.get('tokenization_validation', {})
        usage = record.get('response', {}).get('usage', {})
        expected, observed = validation.get('expected_prompt_tokens'), usage.get('prompt_tokens')
        assert validation.get('status') == 'matched', path.name
        assert type(expected) is int and type(observed) is int and expected == observed, path.name
        assert validation.get('observed_prompt_tokens') == observed, path.name
        assert validation.get('tokenization_request_sha256'), path.name
        output = payload.get('max_tokens')
        assert type(output) is int and output > 0, path.name
        margin = 256 if arm == RESIDUAL else 0
        if arm == RESIDUAL:
            assert output == 4096, 'Residual reasoning output reserve changed'
        total = observed + output + margin + 8
        assert total <= 16384, 'Final adapted chat exceeded the common 16K limit'
        chats.append({'prompt_tokens': observed, 'output_token_reserve': output,
                      'input_margin': margin, 'total_with_reserves': total})
    assert chats, 'No generated chat records found'
    return {'chat_records': len(chats), 'all_tokenization_validation_matched': True,
            'context_tokens': 16384, 'max_prompt_tokens': max(row['prompt_tokens'] for row in chats),
            'max_output_token_reserve': max(row['output_token_reserve'] for row in chats),
            'max_total_with_reserves': max(row['total_with_reserves'] for row in chats)}


def historical_tokenization_review():
    reasoning_path = BASE / 'smoke05_server_tokenization_audit.json'
    original_path = BASE / 'smoke05_original_server_tokenization_audit.json'
    reasoning, original = runner.load(reasoning_path), runner.load(original_path)
    references = [row for row in reasoning['results'] if row['kind'] == 'successful_generation_reference']
    terminal = [row for row in reasoning['results'] if row['kind'] == 'previously_rejected_terminal_reconstruction']
    assert len(references) == reasoning['success_references'] == reasoning['exact_prompt_count_matches'] == 10
    assert reasoning['all_http_success'] and reasoning['generation_calls'] == 0
    assert reasoning['generation_requested'] is False
    assert all(row['http_status'] == 200 and row['server_token_count'] == row['provider_prompt_tokens']
               and row['delta_vs_provider_prompt'] == 0 for row in references)
    assert len(original['requests']) == 6 and original['all_matched']
    assert original['generation_requests'] == 0
    assert all(row['matched'] and row['count'] == row['observed_prompt_tokens']
               for row in original['requests'])
    assert len(terminal) == 2
    return {'scope': 'Historical read-only tokenization of existing smoke05 wire messages; no new generation.',
            'reasoning_requests_exactly_matched': 10, 'original_requests_exactly_matched': 6,
            'all_16_historical_prompt_counts_matched': True,
            'source_reports': [{'file': path.name, 'sha256': sha(path)}
                               for path in (reasoning_path, original_path)],
            'historical_first_rejected_window': [
                {key: row[key] for key in ('operation', 'input_tokens_local', 'server_token_count',
                                          'estimated_total_using_server_count',
                                          'fits_unchanged_16384_with_output_margin')} for row in terminal],
            'limit': 'Historical first-window counts do not replace final-code smoke06 validation.'}


def main():
    # Completion and all-success gates precede any report publication.
    assert (OUT / 'smoke_summary.json').is_file(), 'Live smoke06 is still running'
    manifest, summary = runner.load(OUT / 'manifest.json'), runner.load(OUT / 'smoke_summary.json')
    sources = runner.frozen_sources()
    assert manifest['source_hashes'] == summary['source_hashes'] == sources
    assert manifest['datasets'] == ['personamem']
    assert manifest['arms'] == ['original', RESIDUAL]
    questions = manifest['question_ids']['personamem']
    assert len(questions) == len(set(questions)) == 2
    assert manifest['question_attempts'] == summary['question_attempts'] == 1
    assert manifest['labels_read'] is summary['labels_read'] is False
    assert summary['counts'] == {'ok': 4}, summary['counts']

    profile, old_profile = runner.load(ROOT / PROFILE), runner.load(ROOT / OLD_PROFILE)
    assert profile == manifest['config'], 'Live smoke used a different configuration'
    assert 'tokenization' not in old_profile
    assert {key: value for key, value in profile.items() if key != 'tokenization'} == old_profile
    options = validate_tokenization_config(profile)
    assert options is not None and options['mode'] == 'vllm_chat'
    settings = resolve(profile, RESIDUAL)
    assert {key: settings[key] for key in BUDGET} == BUDGET

    rows, counts = [], {}
    for arm in manifest['arms']:
        counts[arm] = {}
        for unit in questions:
            row = runner.load(runner.result_path(OUT, 'personamem', arm, unit))
            status = row['answer']['status']
            counts[arm][status] = counts[arm].get(status, 0) + 1
            diagnostic = row.get('diagnostics', {})
            item = {'unit_id': unit, 'arm': arm, 'status': status, 'seconds': row.get('seconds'),
                    'completion_kind': row['answer'].get('completion_kind')}
            if arm == RESIDUAL:
                reading = diagnostic['joint_reading']
                item.update(ledger_used=diagnostic['ledger']['used'], audit_complete=diagnostic['audit_complete'],
                            reading_batches=len(reading['batches']),
                            failed_reading_batches=sum(bool(batch.get('failed_slots')) for batch in reading['batches']),
                            failed_obligations=len(reading['failed_obligations']))
                assert {key: diagnostic['settings'][key] for key in BUDGET} == BUDGET
                assert diagnostic['audit_complete'] and not reading['failed_obligations'], item
                assert not item['failed_reading_batches'], item
            directories = row['attempt_directories']
            expected = Path('personamem') / arm / 'attempts' / runner.digest(unit) / 'attempt-001'
            assert directories == [str(expected)] and row['runner']['attempt'] == 1
            directory = OUT / expected
            assert sorted(path.name for path in directory.parent.glob('attempt-*')) == ['attempt-001']
            item['request_tokenization'] = audit_chat_records(directory, arm)
            cost = runner.request_cost(directory)
            auxiliary = cost['tokenization']
            assert auxiliary['failed_counts'] == auxiliary['malformed_event_lines'] == 0
            item['tokenization_auxiliary_cost'] = auxiliary
            item['api_cost_excluding_tokenization'] = {key: cost[key] for key in (
                'physical_llm_attempts', 'physical_reader_attempts', 'prompt_tokens',
                'completion_tokens', 'total_tokens', 'token_usage_complete')}
            rows.append(item)
    assert len(rows) == 4 and all(item['status'] == 'ok' for item in rows), counts

    historical = historical_tokenization_review()
    schema_review = runner.load(BASE / 'typed_request_schema_review.json')
    assert schema_review['synthetic_contract_tests']['passed'] == 99
    assert schema_review['synthetic_contract_tests']['skipped'] == 0
    assert schema_review['joint_reading_source_sha256'] == sources['dagbt/joint_reading.py']
    scaffold = runner.load(BASE / 'packaging_fixture_verification.json')
    assert scaffold['passed'] is True
    integrity = runner.verify_originals()
    test_log_path = BASE / 'pytest_final_v3_tokenization.log'
    matches = re.findall(r'(?m)^(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) warnings)? in ([\d.]+)s$',
                         test_log_path.read_text())
    assert matches, 'Missing successful final full-suite result'
    passed, skipped, warnings, seconds = matches[-1]
    auxiliary_totals = {key: sum(row['tokenization_auxiliary_cost'][key] for row in rows)
                        for key in ('logical_calls', 'cache_hits', 'http_attempts',
                                    'successful_http_requests', 'failed_counts', 'observed_seconds')}
    assert (ROOT / RESEARCH_DOC).is_file()
    report = {
        'pytest_passed': int(passed), 'pytest_skipped': int(skipped or 0),
        'pytest_warnings': int(warnings or 0), 'pytest_seconds': float(seconds),
        'pytest_log': {'file': test_log_path.name, 'sha256': sha(test_log_path)},
        'pytest_skip_scope': 'Optional jsonschema tests unavailable in Python 3.11 were run with the standard validator under Python 3.13; see typed_request_schema_review.',
        'warning_scope': 'Numerical RuntimeWarnings from the existing full suite; observed count recorded above.',
        'live_smoke_evaluation_labels_read': False, 'evaluation_only_json_read': False,
        'answer_accuracy_evaluated': False, 'correct_answers_used_for_parameter_selection': False,
        'metadata_research_scope': 'Earlier research parsed metadata fields from an official CSV containing labels; this is not a claim that no label-bearing file was ever read.',
        'original_integrity': integrity, 'source_hashes_match_live_validation': True,
        'deployment_profile': {'path': str(PROFILE), 'sha256': sha(ROOT / PROFILE),
            'previous_profile': str(OLD_PROFILE), 'previous_profile_sha256': sha(ROOT / OLD_PROFILE),
            'only_added_top_level_field': 'tokenization', 'tokenization_mode': options['mode'],
            'tokenization_timeout_seconds': options['timeout_seconds'],
            'tokenization_endpoint_sha256': hashlib.sha256(options['endpoint'].encode()).hexdigest(),
            'unchanged_residual_budgets': BUDGET,
            'original_final_request_context_tokens': 16384,
            'original_frozen_intermediate_regex_checks_unchanged': True},
        'real_service_smoke': {'output': OUT.name,
            'selection': 'Same first two canonical PersonaMem questions as the uploaded failure run.',
            'question_attempts': 1, 'status_counts': counts, 'rows': rows,
            'all_chat_records_prompt_usage_matched': True,
            'chat_records_verified': sum(row['request_tokenization']['chat_records'] for row in rows),
            'tokenization_auxiliary_cost': auxiliary_totals,
            'scope': 'Final frozen source, both arms, production worker/Transport and real services; execution-path validation without answer scoring or parameter training.'},
        'historical_tokenization_review': historical,
        'embedding_probe': runner.load(BASE / 'embedding_bounded_probe.json'),
        'typed_request_schema_review': schema_review,
        'packaging_scaffold_verification': scaffold,
        'baseline_research': {'repository_document': str(RESEARCH_DOC),
            'sha256': sha(ROOT / RESEARCH_DOC),
            'evidence_directory': 'dagv2_analysis/a48_v3_validation/research',
            'external_baselines_run': False},
        'limitations': [
            'Two questions validate execution, not full-dataset reliability or answer accuracy.',
            'No generation/embedding model, service endpoint, credential, output reserve or per-question call/context budget was changed; a new opt-in tokenization endpoint/profile was added.',
            'Server counts match observed prompt usage; deployed weights, tokenizer identity and future server-template stability are not independently pinned.',
            'Server max_model_len is capability metadata; the experiment remains at 16384.',
            'Original frozen internal regex prechecks remain potentially more conservative; only the final adapted chat gate shares deployment counting.',
            'Tokenization requests and latency are reported separately from generation/embedding usage.',
            'Packaged embedding tokenizer is empirically matched, not a verified server-side tokenizer/weights hash.'],
        'development_validation': {
            'earlier_candidate_runs': 'Smoke01–04 exposed parent-slot, source-metadata growth and typed/retraction protocol gaps; smoke05 then exposed a local heuristic context rejection. Earlier failures are retained and are not reported as successful validation.',
            'smoke05_capacity_failure': {'failure_location': 'Local source-window preflight before semantic generation was sent.',
                'provider_context_error_observed': False,
                'evidence': ['smoke05_reasoning_token_audit.json', 'smoke05_server_tokenization_audit.json'],
                'not_reused_as_final_capacity_validation': 'terminal_capacity_final.json predates deployment counting and is not included as new-capacity evidence.'},
            'final_run_uses_new_output_and_single_attempt': True,
            'offline_index_reconstruction_additional_embedding_requests': 0}}
    runner.save(RELEASE / 'validation.json', report)
    print(json.dumps({'status_counts': counts, 'rows': rows, 'original_integrity': integrity},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
