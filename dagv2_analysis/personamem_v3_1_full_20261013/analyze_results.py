import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
import statistics
import sys

BASE = Path(__file__).resolve().parent
REPO = Path('/Users/mao/projects/dagv2-personamem-a48')
sys.path.insert(0, str(REPO))
from dagbt.personamem import load_questions, parse_choice
from dagbt.runner import digest, validate_result

manifest = json.loads((BASE / 'manifest.json').read_text())
questions = {q['id']: q for q in load_questions(REPO)}
labels = {r['id']: r for r in json.loads((REPO / 'data/personamem/evaluation_only.json').read_text())}
units = manifest['question_ids']['personamem']
assert digest([questions[u] for u in units]) == manifest['questions_digest']['personamem']
index = json.loads((BASE / 'extraction_report.json').read_text())['rows']
rows = defaultdict(dict)
for i, item in enumerate(index):
    with gzip.open(BASE / item['path'], 'rt') as handle:
        raw = json.load(handle)
    unit = item['unit_id']
    assert unit in units
    validate_result(raw, unit)
    a, q = raw['answer'], questions[unit]
    pred = parse_choice(a.get('prediction'), q['options'])
    gold = parse_choice(labels[unit]['correct_answer'], q['options'])
    assert gold is not None
    valid = a['status'] == 'ok' and pred is not None
    d = raw.get('diagnostics', {})
    runner_cost = raw.get('runner', {}).get('cost', {})
    events = d.get('events', [])
    jr = d.get('joint_reading', {})
    failures = [f for b in jr.get('batches', []) for f in b.get('failed_slots', [])]
    rr = [e for e in events if e.get('event') == 'reasoning_response']
    sp = d.get('spans', [])
    feature = {
        'unit_id': unit, 'arm': item['arm'], 'status': a['status'], 'valid': valid,
        'prediction': pred, 'gold': gold, 'correct': int(valid and pred == gold),
        'persona_id': q['persona_id'], 'question_type': q.get('question_type'), 'topic': q.get('topic'),
        'semantic_answer': a.get('semantic_answer'), 'completion_kind': a.get('completion_kind'),
        'row_path': item['path'], 'row_raw_bytes': item['bytes'], 'attempt_count':len(raw.get('attempt_directories', [])),
        'candidate_doc_count':len(d.get('candidate_doc_ids', [])),
        'terminal_doc_ids': a.get('terminal_input_doc_ids', []),
        'baseline_selected_doc_ids': {k:v.get('selected_doc_ids',[]) for k,v in raw.get('budgets',{}).items()},
        'span_doc_ids':list(dict.fromkeys(s['doc_id'] for s in sp)),
        'cost':d.get('cost',{}), 'http_cost':{k:v for k,v in runner_cost.items() if k != 'requests_by_stage'},
        'seconds': raw.get('runner',{}).get('wall_seconds',raw.get('seconds')),
        'errors': d.get('errors', []), 'failed_slots': failures,
        'operation_counts':dict(Counter(e['operation'] for e in rr)),
        'response_ref_counts':dict(Counter(e.get('response_ref') for e in rr)),
        'batch_count':len(jr.get('batches', [])),
        'empty_visible_batches':sum(not b.get('visible_source_aliases') for b in jr.get('batches', [])),
        'pending_variables':d.get('fact_state',{}).get('pending_variables'),
        'facts':d.get('fact_state',{}).get('facts'),
        'program':d.get('fact_state',{}).get('program'),
        'scope':d.get('memory_scope'), 'audit_complete':d.get('audit_complete'),
        'max_response_ref_repeats':max(Counter(e.get('response_ref') for e in rr).values(),default=0),
    }
    rows[item['arm']][unit] = feature
    if (i+1)%100==0: print('Analyzed',i+1,flush=True)

arms = manifest['arms']
original, fusion = (rows[a] for a in arms)
common = original.keys() & fusion.keys()
valid = {u for u in common if original[u]['valid'] and fusion[u]['valid']}
cases = defaultdict(list)
for u in units:
    if u not in common:continue
    o,f = original[u],fusion[u]
    if u in valid:
        kind = ('both_correct' if o['correct'] and f['correct'] else 'harm' if o['correct'] else 'rescue' if f['correct'] else 'both_wrong')
    else:
        kind = 'not_both_valid'
    cases[kind].append({'unit_id':u,'question':questions[u]['user_question'],'options':questions[u]['options'],
        'question_type':questions[u].get('question_type'),'topic':questions[u].get('topic'),
        'original':{k:o[k] for k in ('status','prediction','correct','row_path')},
        'fusion':{k:f[k] for k in ('status','prediction','correct','row_path')},'gold':o['gold']})
(BASE/'paired_cases.json').write_text(json.dumps(dict(cases),ensure_ascii=False,indent=2))
with (BASE/'features.jsonl').open('w') as handle:
    for arm in arms:
        for unit in units:
            if unit in rows[arm]:handle.write(json.dumps(rows[arm][unit],ensure_ascii=False)+'\n')

summary={'planned':len(units),'common_recorded':len(common),'common_valid':len(valid),'arms':{},'paired_common_valid':{},'case_counts':{k:len(v) for k,v in cases.items()}}
for arm in arms:
    records=list(rows[arm].values())
    costkeys=('total_tokens','http_attempts','reasoning_logical_calls','physical_llm_attempts','cache_hits')
    summary['arms'][arm]={'recorded':len(records),'status_counts':dict(Counter(r['status'] for r in records)),
        'valid':sum(r['valid'] for r in records),'correct':sum(r['correct'] for r in records),
        'accuracy_percent':100*sum(r['correct'] for r in records)/len(records),
        'completion_kinds':dict(Counter(str(r['completion_kind']) for r in records)),
        'mean_seconds':statistics.mean(r['seconds'] for r in records if r['seconds'] is not None),
        'median_seconds':statistics.median(r['seconds'] for r in records if r['seconds'] is not None),
        'cost_totals':{k:sum(r['http_cost'].get(k,0) for r in records) for k in costkeys}}
    selected=[rows[arm][u] for u in valid]
    summary['paired_common_valid'][arm]={'n':len(valid),'correct':sum(r['correct'] for r in selected),
        'accuracy_percent':100*sum(r['correct'] for r in selected)/len(valid)}
summary['per_question_type']={}
for group in sorted({questions[u]['question_type'] for u in common}):
    scope={u for u in common if questions[u]['question_type']==group}
    shared=scope & valid
    summary['per_question_type'][group]={'n':len(scope),'common_valid_n':len(shared),
        'original_correct':sum(original[u]['correct'] for u in scope),'fusion_correct':sum(fusion[u]['correct'] for u in scope),
        'fusion_failures':sum(not fusion[u]['valid'] for u in scope),
        'common_valid_original_correct':sum(original[u]['correct'] for u in shared),
        'common_valid_fusion_correct':sum(fusion[u]['correct'] for u in shared)}
(BASE/'metrics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
