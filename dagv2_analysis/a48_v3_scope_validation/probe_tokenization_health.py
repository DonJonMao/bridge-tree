"""Exactly two readonly tokenizer calls; no retries and no generation."""
import hashlib
import json
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = Path('/Users/mao/projects/dagv2-personamem-a48')
UPLOAD = BASE.parent / 'a48_v3_server_failure/personamem_a48_v3_smoke'
UNIT = '2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0'
sys.path.insert(0, str(ROOT))
from dagbt.token_counting import DeploymentTokenCounter, TokenizationError


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    destination = BASE / 'tokenization_health_probe.json'
    if destination.exists():
        raise SystemExit('Health probe already recorded; refusing an implicit retry')
    config_path = ROOT / 'configs/residual-memory.personamem16k.json'
    config = json.loads(config_path.read_text())
    inputs = [
        ('uploaded_original_source_chat', 'original', 'aa69b664ae711a19ae497fafa8ffaa1127186fdb703d5acbcadc204e8d222ea3'),
        ('uploaded_residual_first_read', 'dagbt_residual_memory_v1', 'fb359b309ba13f01b3e4a0fcc86db44fcb338a8dce7c80581c099f485d07b27c'),
    ]
    report = {'generation_calls': 0, 'network_purpose': 'readonly deployment tokenization only',
              'maximum_authorized_calls': 3, 'planned_calls': 2, 'sequential': True,
              'fresh_counter_per_call': True, 'retries': 0, 'evaluation_labels_read': False,
              'config_path': str(config_path), 'config_sha256': sha(config_path),
              'counter_source_sha256': sha(ROOT / 'dagbt/token_counting.py'),
              'timeout_seconds': config['tokenization']['timeout_seconds'], 'results': []}
    for name, arm, ref in inputs:
        path = UPLOAD / f'personamem/{arm}/attempts/{UNIT}/attempt-001/requests/{ref}.json'
        record = json.loads(path.read_text())
        expected = record['response']['usage']['prompt_tokens']
        assert record['tokenization_validation']['status'] == 'matched'
        events = []
        counter = DeploymentTokenCounter(config, events.append)
        result = {'input': name, 'request_path': str(path), 'request_sha256': sha(path),
                  'prior_provider_prompt_tokens': expected, 'started_unix': time.time()}
        started = time.monotonic()
        try:
            counted = counter.count(record['payload'])
            result.update(status='ok', count=counted['count'], count_matches_prior_usage=counted['count'] == expected,
                          tokenization_request_sha256=counted['tokenization_request_sha256'])
        except TokenizationError as exc:
            result.update(status='error', error_category=exc.category, http_status=exc.http_status,
                          count_matches_prior_usage=None)
        result['elapsed_seconds'] = time.monotonic() - started
        assert len(events) == 1 and not events[0]['cache_hit']
        result['safe_event'] = events[0]
        report['results'].append(result)
        destination.write_text(json.dumps(report, indent=2) + '\n')
    report['http_attempts'] = sum(r['safe_event']['http_attempts'] for r in report['results'])
    report['successful_counts'] = sum(r['status'] == 'ok' for r in report['results'])
    report['failed_counts'] = sum(r['status'] == 'error' for r in report['results'])
    report['all_counts_match_prior_provider_usage'] = all(r['count_matches_prior_usage'] is True for r in report['results'])
    report['observed_seconds'] = sum(r['elapsed_seconds'] for r in report['results'])
    report['caveat'] = 'Two isolated health samples cannot establish sustained tokenizer availability or complete live-smoke validation.'
    assert report['http_attempts'] <= 3
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'report': str(destination), 'sha256': sha(destination),
                      'http_attempts': report['http_attempts'], 'successful_counts': report['successful_counts'],
                      'failed_counts': report['failed_counts'],
                      'all_counts_match_prior_provider_usage': report['all_counts_match_prior_provider_usage'],
                      'observed_seconds': report['observed_seconds'],
                      'results': [{k: r.get(k) for k in ('input', 'status', 'count', 'error_category', 'elapsed_seconds')}
                                  for r in report['results']]}))


if __name__ == '__main__':
    main()
