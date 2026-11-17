#!/usr/bin/env python3
"""Summarize terminal local trials from their saved production artifacts."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def decode(raw):
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        return json.loads(raw)
    except ValueError:
        return None


def summarize(trial):
    state = load(trial / 'state.json')
    assert state['status'] == 'complete', state['status']
    output = trial / 'output'
    evaluation = load(output / 'evaluation.json')
    verdicts = {(row['question_id'], row['arm']): row for row in evaluation['rows']}
    tasks = []
    for path in sorted(output.glob('tasks/*/*/result.json')):
        result = load(path)
        detail = result['diagnostics']
        calls = [json.loads(line) for line in (path.parent / 'call_events.jsonl').read_text().splitlines()]
        navigations, protocol_hints, source_reviews = [], [], []
        for call in calls:
            if call.get('event') != 'call_started':
                continue
            request = load(path.parent / 'requests' / (call['request_ref'] + '.json'))
            messages = request['payload']['messages']
            data = json.loads(messages[1]['content'])
            if not isinstance(data, dict):
                continue
            if data.get('web_reading_protocol_diagnostics'):
                protocol_hints.append({'stage': call['stage'],
                    'diagnostics': data['web_reading_protocol_diagnostics']})
            if data.get('web_source_review'):
                source_reviews.append({'stage': call['stage'],
                    'source_ids': [card['original_source']['id']
                                   for card in data['web_source_review']['cards']],
                    'cards': len(data['web_source_review']['cards'])})
            if call['stage'].startswith('web_navigate/'):
                raw = request.get('response', {}).get('choices', [{}])[0].get('message', {}).get('content')
                response = decode(raw)
                selected = next((link for link in data['links'] if response
                                 and link['id'] == response.get('link_id')), None)
                navigations.append({'stage': call['stage'], 'offered': len(data['links']),
                    'selected': selected, 'response': response,
                    'assessment': data.get('navigation_assessment')})
        key = (result['unit_id'], result['method'])
        tasks.append({'question_id': key[0], 'arm': key[1], 'answer': result['answer'],
            'evaluation': verdicts[key], 'generation_cost': detail['cost'],
            'ledger_used': detail['ledger']['used'], 'ledger_limits': detail['ledger']['limits'],
            'errors': detail['errors'], 'visits': detail['web']['visits'],
            'navigation': navigations, 'repair_protocol_diagnostics': protocol_hints,
            'source_review_calls': source_reviews,
            'branch_plan_events': [event for event in detail['events'] if event.get('event') in (
                'web_navigation_plan_decided', 'web_branch_plan_consumed', 'web_branch_plan_invalidated')],
            'incomplete_read_batches': [batch for batch in detail['joint_reading']['batches']
                                        if not batch.get('complete')],
            'call_kinds': dict(Counter(call['stage'].split('/')[0] for call in calls
                                      if call.get('event') == 'call_started')),
            'result_path': str(path),
            'result_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    declaration = load(trial / 'declaration.json')
    source = Path(declaration['source_root'])
    changed = [name for name, expected in declaration['payload_sha256'].items()
               if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected]
    assert not changed, changed
    report = {'trial': str(trial), 'pipeline': state,
        'source_hashes_still_match_declaration': True,
        'runtime_config_still_matches_declaration': hashlib.sha256(
            (trial / 'runtime_config.json').read_bytes()).hexdigest() == declaration['runtime_config_sha256'],
        'correct_tasks': sum(row['correct'] is True for row in evaluation['rows']),
        'planned_tasks': len(evaluation['rows']), 'judge_model': evaluation['judge_model'],
        'judge_failures': sum(row['correct'] is None for row in evaluation['rows']),
        'environment_exclusions': evaluation['environment_exclusions'], 'tasks': tasks}
    destination = trial / 'analysis_summary.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'summary': str(destination), 'correct_tasks': report['correct_tasks'],
                      'planned_tasks': report['planned_tasks'], 'immutable_source_verified': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('trial', type=Path)
    summarize(parser.parse_args().trial.resolve())
