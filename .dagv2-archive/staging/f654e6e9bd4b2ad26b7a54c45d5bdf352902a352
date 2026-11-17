"""Compare existing generation usage with read-only /tokenize, never generate."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics
import sys
from types import SimpleNamespace
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path('/Users/mao/projects/dagv2-personamem-a48')
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from dagbt.joint_reading import JointReader
from dagbt.model_runtime import prepare_request, resolve_api_key
from dagbt.reasoning import Reasoner
from dagbt.transport import digest


def main():
    smoke = BASE / 'live_smoke_05'
    manifest = json.loads((smoke / 'manifest.json').read_text())
    assert all(hashlib.file_digest((ROOT / name).open('rb'), 'sha256').hexdigest() == expected
               for name, expected in manifest['source_hashes'].items())
    attempts = smoke / 'personamem/dagbt_residual_memory_v1/attempts'
    jobs = []
    for directory in sorted(attempts.glob('*/attempt-001')):
        cache = {}
        for path in (directory / 'requests').glob('*.json'):
            row = json.loads(path.read_text())
            if 'messages' in row.get('payload', {}):
                cache[tuple(row['stage'])] = row
        for event in map(json.loads, (directory / 'fusion_events.jsonl').read_text().splitlines()):
            if event['event'] != 'reasoning_response':
                continue
            cached = cache[event['operation'], str(event['logical_call_index'])]
            jobs.append({'unit_id': directory.parent.name, 'operation': event['operation'],
                         'call_index': event['logical_call_index'],
                         'input_tokens_local': event['input_tokens_local'],
                         'provider_prompt_tokens': cached['response']['usage']['prompt_tokens'],
                         'wire': cached['payload'], 'url': cached['url'], 'kind': 'successful_generation_reference'})
    assert len(jobs) == 10
    failed_key = '2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0'
    diagnostics = json.loads((attempts / failed_key / 'attempt-001/result.json').read_text())['diagnostics']
    settings = diagnostics['settings']
    canonical = json.loads(Path('/tmp/personamem_smoke05_terminal_payload.json').read_text())
    known_wire_data = json.loads(Path('/tmp/personamem_smoke05_terminal_wire.json').read_text())
    prior = json.loads((BASE / 'smoke05_reasoning_token_audit.json').read_text())
    assert digest(canonical) == prior['failed_terminal']['canonical_payload_sha256']
    assert JointReader._wire_data(canonical) == known_wire_data
    sample = jobs[0]
    config = {'model_profile': 'bridgetree', 'llm_model': sample['wire']['model'],
              'llm_base_url': sample['url'].rsplit('/chat/completions', 1)[0]}
    reasoner = Reasoner(None, None, config, settings, None, lambda event: None)
    reasoner.sequence = 5
    reader = JointReader(SimpleNamespace(reasoner=reasoner, s=settings), None)
    repair = {**canonical, 'repair_scope': {'failed': [
        {'variable': variable, 'id': '*', 'feedback': 'x' * 240, 'observation': None}
        for variable in canonical['variables']], 'attempt': 1, 'previous_response_identity': '0' * 64}}
    for operation, data in [('semantic_compose', canonical), ('semantic_compose_repair', repair)]:
        wire_data = reader._wire_data(data)
        payload = reasoner._payload(operation, reader._system(wire_data), wire_data, reader._schema(data))
        url, wire, _ = prepare_request((operation, '6'), reasoner.url, payload, config)
        jobs.append({'unit_id': failed_key, 'operation': operation,
                     'input_tokens_local': reader._estimate(operation, data),
                     'provider_prompt_tokens': None, 'wire': wire, 'url': url,
                     'kind': 'previously_rejected_terminal_reconstruction'})

    def tokenize(job):
        # Existing cached generation URL is only used to locate the same host.
        parsed = urllib.parse.urlsplit(job['url'])
        url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, '/tokenize', '', ''))
        assert urllib.parse.urlsplit(url).path == '/tokenize'
        auth_config = {'model_profile': 'bridgetree', 'llm_model': job['wire']['model'],
                       'llm_base_url': job['url'].rsplit('/chat/completions', 1)[0]}
        key = resolve_api_key(auth_config, 'llm')
        body = {'model': job['wire']['model'], 'messages': deepcopy(job['wire']['messages']),
                'add_generation_prompt': True}
        headers = {'Content-Type': 'application/json'}
        if key:
            headers['Authorization'] = 'Bearer ' + key
        request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode(),
                                         headers=headers, method='POST')
        result = {key: value for key, value in job.items() if key not in ('wire', 'url')}
        result['messages_sha256'] = digest(body['messages'])
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=15) as response:
                value = json.load(response)
                result.update(http_status=response.status, server_token_count=value.get('count'),
                              server_max_model_len=value.get('max_model_len'))
            assert isinstance(result['server_token_count'], int)
            result['delta_vs_provider_prompt'] = (None if job['provider_prompt_tokens'] is None else
                result['server_token_count'] - job['provider_prompt_tokens'])
        except Exception as error:
            # Do not render provider response bodies, request text, URLs or keys.
            result.update(error_type=type(error).__name__, http_status=getattr(error, 'code', None))
        return result

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(tokenize, jobs))
    successful = results[:10]
    terminal = results[10:]
    complete = all(row.get('http_status') == 200 and 'server_token_count' in row for row in results)
    matches = sum(row.get('delta_vs_provider_prompt') == 0 for row in successful)
    reserve = settings['reasoning_output_tokens'] + settings['input_margin'] + 8
    for row in terminal:
        if 'server_token_count' in row:
            row.update(estimated_total_using_server_count=row['server_token_count'] + reserve,
                       fits_unchanged_16384_with_output_margin=row['server_token_count'] + reserve <= settings['context_tokens'])
    report = {'kind': 'read_only_server_tokenization_audit', 'generation_requested': False,
              'generation_calls': 0, 'tokenization_requests': len(jobs), 'proxies_disabled': True,
              'timeout_seconds': 15, 'source_hashes_match_smoke05': True,
              'canonical_failed_payload_sha256': digest(canonical), 'all_http_success': complete,
              'success_references': 10, 'exact_prompt_count_matches': matches,
              'add_generation_prompt': True, 'preserved_context_limit': settings['context_tokens'],
              'preserved_output_token_reserve': settings['reasoning_output_tokens'],
              'preserved_input_margin': settings['input_margin'], 'preserved_extra_margin': 8,
              'results': results,
              'limits': ['Exact equality on these ten requests verifies this observed wire/template path only, not immutable server weights/tokenizer identity.',
                         'Server max_model_len is capability metadata, not permission to raise the 16384 experimental limit.',
                         'Terminal counts cover the reconstructed first rejected source window and its provisional repair envelope, not all later growing windows or actual future repair drafts.',
                         'No generation was sent; tokenization does not prove answer correctness or completion of the failed experiment.']}
    path = BASE / 'smoke05_server_tokenization_audit.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'report': str(path), 'all_http_success': complete,
                      'exact_prompt_count_matches': matches, 'reference_count': 10,
                      'terminal_counts': [{key: row.get(key) for key in (
                          'operation', 'input_tokens_local', 'server_token_count',
                          'estimated_total_using_server_count', 'fits_unchanged_16384_with_output_margin')}
                                          for row in terminal]}, indent=2))


if __name__ == '__main__':
    main()
