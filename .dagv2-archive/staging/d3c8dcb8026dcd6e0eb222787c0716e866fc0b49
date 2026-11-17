"""Inspect compressed authoritative failures only; never load labels or model APIs."""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, '/Users/mao/projects/dagv2-personamem-a48')
from dagbt.evidence_protocol import parse_evidence_object
from dagbt.personamem import parse_choice
from dagbt.transport import digest


def parsed_response(event):
    try:
        return parse_evidence_object(event.get('raw_output'))
    except (ValueError, TypeError, AttributeError):
        return None


def summarize(entry):
    with gzip.open(ROOT / entry['path'], 'rt') as handle:
        row = json.load(handle)
    d, answer = row.get('diagnostics', {}), row['answer']
    batches = d.get('joint_reading', {}).get('batches', [])
    responses = [e for e in d.get('events', []) if e.get('event') == 'reasoning_response']
    terminal = d.get('terminal_input') or {}
    terminal_event = next((e for e in responses if e.get('logical_call_index') == terminal.get('logical_call_index')), None)
    terminal_value = parsed_response(terminal_event) if terminal_event else None
    failures = Counter(f['error'] for b in batches for f in b.get('failed_slots', []))
    audits = []
    for event in responses:
        if not event.get('operation', '').startswith('audit_joint'):
            continue
        value = parsed_response(event)
        if isinstance(value, dict):
            audits.append({'call_index': event.get('logical_call_index'), 'verdict': value.get('audit_verdict'),
                           'unresolved_count': sum(len(s.get('unresolved', [])) for s in value.get('slots', []) if isinstance(s, dict)),
                           'contradiction_count': sum(o.get('stance') == 'contradiction' for s in value.get('slots', []) if isinstance(s, dict) for o in s.get('observations', []) if isinstance(o, dict))})
    refcounts = Counter(e.get('response_ref') for e in responses if e.get('response_ref'))
    result = {k: entry[k] for k in ['unit_id', 'status', 'path', 'bytes']}
    result.update(cost=d.get('cost'), ledger={k: v for k,v in d.get('ledger', {}).items() if k != 'events'},
                  audit_complete=d.get('audit_complete'), certificate_present=answer.get('certificate') is not None,
                  contract=d.get('fact_state', {}).get('contract'),
                  errors=[{k: e.get(k) for k in ('node_id', 'type', 'error')} for e in d.get('errors', [])],
                  failed_slots=dict(failures), failed_batch_count=sum(bool(b.get('failed_slots')) for b in batches),
                  batch_count=len(batches), empty_source_batch_count=sum(not b.get('visible_source_aliases') for b in batches),
                  empty_source_failed_batch_count=sum(not b.get('visible_source_aliases') and bool(b.get('failed_slots')) for b in batches),
                  audit_batches=[{k:b.get(k) for k in ['complete','audit_complete','failed_slots']} for b in batches if b.get('operation')=='audit_joint'],
                  audit_responses=audits, unique_response_refs=len(refcounts), response_count=len(responses),
                  max_response_ref_repeat=max(refcounts.values(), default=0),
                  terminal_input_validation_complete=terminal.get('validation_complete'),
                  terminal_response_index=terminal.get('logical_call_index'),
                  last_residual_state=next(({k:e.get(k) for k in ['outcome','active_demands','paused_demands']} for e in reversed(d.get('events', [])) if e.get('event')=='residual_state'), None))
    if isinstance(terminal_value, dict):
        result['terminal_check'] = {
            'prediction': terminal_value.get('final_prediction'),
            'choice_legal': parse_choice(terminal_value.get('final_prediction'), ['a','b','c','d']) is not None,
            'semantic_type': type(terminal_value.get('semantic_answer')).__name__,
            'published_semantic_type': type(answer.get('semantic_answer')).__name__,
            'semantic_digest_matches_published': digest(terminal_value.get('semantic_answer')) == digest(answer.get('semantic_answer')),
            'semantic_digest_matches_some_terminal_slot': any(digest(o.get('value')) == digest(terminal_value.get('semantic_answer'))
                for s in terminal_value.get('slots', []) if isinstance(s, dict)
                for o in s.get('observations', []) if isinstance(o, dict) and o.get('stance')=='support'),
        }
    return result


def main():
    entries = [json.loads(s) for s in (ROOT/'row_index.jsonl').read_text().splitlines() if s.strip()]
    entries = [x for x in entries if x['arm']=='dagbt_residual_memory_v1']
    selected = [x for x in entries if x['status'] in {'invalid_output_format','audit_incomplete','budget_exhausted','unresolved_or_exhausted'}]
    selected.sort(key=lambda x: (x['status']=='budget_exhausted', x['bytes']))
    results=[]
    with (ROOT/'failure_features.jsonl').open('w') as out:
        for i, entry in enumerate(selected, 1):
            result=summarize(entry)
            results.append(result)
            out.write(json.dumps(result, ensure_ascii=False)+'\n'); out.flush()
            if i%20==0:
                print(f'Processed {i}/{len(selected)} failure rows', flush=True)
    groups=defaultdict(list)
    for r in results: groups[r['status']].append(r)
    counts={}
    for status, rows in groups.items():
        counts[status] = {
            'n':len(rows),
            'audit_complete':sum(r['audit_complete'] is True for r in rows),
            'failed_slots_present':sum(bool(r['failed_slots']) for r in rows),
            'empty_source_failed_batches_present':sum(r['empty_source_failed_batch_count']>0 for r in rows),
            'response_repeated':sum(r['max_response_ref_repeat']>1 for r in rows),
            'legal_terminal_choice':sum(r.get('terminal_check',{}).get('choice_legal',False) for r in rows),
            'terminal_semantic_mismatch':sum(r.get('terminal_check',{}).get('semantic_digest_matches_published') is False for r in rows),
            'llm_remaining':dict(Counter(str(r['ledger'].get('remaining',{}).get('llm')) for r in rows)),
            'ann_remaining':dict(Counter(str(r['ledger'].get('remaining',{}).get('ann')) for r in rows)),
            'audit_verdicts':dict(Counter(str(a['verdict']) for r in rows for a in r['audit_responses'])),
            'failed_slot_occurrences':dict(sum((Counter(r['failed_slots']) for r in rows),Counter()).most_common(20)),
            'failed_slot_rows':dict(Counter(e for r in rows for e in r['failed_slots']).most_common(20)),
        }
    report={'labels_read':False,'source':'compressed authoritative residual rows',
            'indexed_status_counts':dict(Counter(e['status'] for e in entries)), 'groups':counts}
    (ROOT/'failure_analysis_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__': main()
