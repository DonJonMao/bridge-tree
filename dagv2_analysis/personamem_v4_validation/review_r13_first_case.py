"""Read-only structural report; explicit output allowlists, no network calls."""
import json
from pathlib import Path
from collections import Counter, defaultdict
base=Path('/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r13')
key='7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0'
p=base/'personamem/dagbt_residual_memory_v2/attempts'/key/'attempt-001'
out=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
r=json.loads((p/'result.json').read_text());d=r['diagnostics'];j=d['joint_reading']
events=[json.loads(line) for line in (p/'fusion_events.jsonl').read_text().splitlines()]
requests=[]
for f in (p/'requests').glob('*.json'):
 item=json.loads(f.read_text());stage=item.get('stage',[])
 if stage and stage[0] in ('joint_read','semantic_compose'):
  data=json.loads(item['payload']['messages'][1]['content'])
  item['_data']=data;item['_hash']=f.stem;requests.append(item)
requests.sort(key=lambda x:int(x['stage'][-1]))
by_identity=defaultdict(list)
for item in requests:by_identity[item['_data']['request_context']['query_identity']].append(item)

def closure(value):
 found=set()
 if isinstance(value,dict):
  for k,v in value.items():
   if k=='source_ids':found.update(v)
   elif k not in ('value','output'):found.update(closure(v))
 elif isinstance(value,list):
  for v in value:found.update(closure(v))
 return found

def record_request(item,batch):
 data=item['_data'];columns=data['source_span_columns'];spans=[dict(zip(columns,row)) for row in data['source_spans']]
 by_alias={s['id']:s for s in spans};required=set()
 for field in ('known_observations','supported_parents','supported_task_outputs','evidence_obligations'):
  required.update(closure(data.get(field,{})))
 usage=item['response'].get('usage',{})
 return {'stage':item['stage'],'request_hash':item['_hash'],'max_tokens':item['payload']['max_tokens'],
  'finish_reason':item['response']['choices'][0].get('finish_reason'),
  'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),
  'window_source_count':len(batch['source_aliases']),'visible_source_count':len(spans),
  'visible_document_count':len(data['source_documents']),
  'known_parent_task_obligation_source_closure_count':len(required),
  'required_closure_sources_all_visible':required<=set(by_alias),
  'required_closure_source_text_chars':sum(len(by_alias[a]['text']) for a in required if a in by_alias),
  'visible_source_text_chars':sum(len(s['text']) for s in spans)}

batches=j['batches'];history=defaultdict(list);semantic=[]
for b in batches:
 if b['operation']=='joint_read':history[b['identity']].append(b)
 else:semantic.append(b)
report={'run':'v4_validation_r13','commit':'711848995f681ffb2cfb9684b8f2736f5aa188d6',
 'unit_id':r['unit_id'],'scope':'Read-only saved structural records; no labels, generation, tokenization or experiment mutation. No source/option/prediction/response text included.',
 'termination_kind':'first case naturally published budget_exhausted before root later stopped the whole run',
 'answer_status':r['answer']['status'],'published_row_exists':(base/'personamem/dagbt_residual_memory_v2/rows'/f'{key}.json').is_file(),
 'attempt_result_exists':True,'fusion_snapshot_exists':(p/'fusion_snapshot.json').is_file(),
 'audit_complete':d['audit_complete'],'pending_variables':d['fact_state']['pending_variables'],
 'ledger':{k:d['ledger'][k] for k in ('limits','used','remaining')},
 'cost':{k:d['cost'][k] for k in ('generation_calls','joint_read_calls','repair_calls','json_repair_reservations','semantic_compose_calls','audit_calls','planner_calls','ann_calls','llm_attempts')},
 'history_reads':[], 'semantic_read':{},'final_obligations':{},'interpretation':[]}
for identity,group in history.items():
 items=by_identity[identity]
 report['history_reads'].append({'identity':identity,'node_id':items[0]['_data']['task']['output_slot'],
  'batches':len(group),'complete_batches':sum(b['complete'] for b in group),
  'unique_window_source_aliases':len(set().union(*(set(b['source_aliases']) for b in group))),
  'input_tokens':[b['input_tokens'] for b in group],
  'output_caps':[x['payload']['max_tokens'] for x in items],
  'all_finish_reason_stop':all(x['response']['choices'][0]['finish_reason']=='stop' for x in items)})
identity=semantic[0]['identity'];completed=[b for b in semantic if b['complete']];failed=semantic[-1]
items=by_identity[identity]
paid_aliases=set().union(*(set(b['source_aliases']) for b in completed))
failed_aliases=set(failed['source_aliases'])
expected='llm budget at semantic_compose: requested=1, remaining=0'
assert all(e['error']==expected for e in d['errors'])
assert all(x['error']==expected for x in failed['failed_slots'])
assert len(d['errors'])==1 and d['errors'][0]['type']=='BudgetExceeded'
report['semantic_read']={'identity':identity,'same_identity_all_batches':all(b['identity']==identity for b in semantic),
 'controller_read_invocations_evidence':'One residual checkpoint before all five windows; all share identity; JointReader.read while-pending loop emits each batch before returning.',
 'complete_batches':len(completed),'failed_before_generation_batches':1,
 'complete_window_source_counts':[len(b['source_aliases']) for b in completed],
 'visible_source_counts':[len(b['visible_source_aliases']) for b in semantic],
 'paid_window_unique_sources':len(paid_aliases),'all_five_window_unique_sources':len(paid_aliases|failed_aliases),
 'failed_window_sources':len(failed_aliases),'failed_window_sources_not_previously_in_paid_window':len(failed_aliases-paid_aliases),
 'failed_slot_variables':sorted(x['variable'] for x in failed['failed_slots']),
 'fixed_error':expected,
 'failed_batch_logged_input_tokens_is_previous_request':True,
 'paid_requests':[record_request(item,b) for item,b in zip(items,completed)],
 'remaining_llm':d['ledger']['remaining']['llm'],'reserved_audit_calls':d['settings']['reserved_audit_calls'],
 'minimum_remaining_calls_if_final_window_and_single_audit_succeed':2,
 'minimum_budget_deficit_calls':1,
 'audit_not_started_reason':'Ordinary semantic window blocked by reservation before semantic read finished; one remaining LLM call is reserved for audit, which is not yet admissible.'}
report['final_obligations']={'unread_obligation_count':len(j['unread_obligations']),
 'failed_obligation_count':len(j['failed_obligations']),'evidence_obligation_count':len(j['evidence_obligations']),
 'failed_batch_review_count':len(j['failed_batch_reviews']),
 'failed_batch_reviews':[{'variable':x['variable'],'phase':x['phase'],'source_count':len(x['source_ids']),
  'validated_observation_count':len(x['validated_observations'])} for x in j['failed_batch_reviews']],
 'note':'Selected final five-source window is removed from unread markers after the preflight failure and retained as failed reviews covering its complete forty-source visible context. Zero unread does not mean terminal completion.'}
report['interpretation']=[
 'This is a natural first-case budget outcome, unlike R11/R12 operator-stopped first cases.',
 'History windows all passed without repairs, output truncation or capacity errors; they consumed eighteen generation calls across three reads.',
 'Four terminal calls are advancing source windows within one semantic read, not four controller retries or a proven controller loop.',
 'The fifth terminal window needs a normal call, but remaining one is reserved for audit. Minimum full-task call total is twenty-five if that window and a single audit succeed without repairs; this is a lower bound, not a completion guarantee.',
 'Current full-output-first prefix admission can prefer many small windows to a larger eligible capped history window; R12 exact network-tokenization comparison supplies evidence for testing a different admission policy. R13 exhaustion alone does not prove a defect.',
 'No prediction or accuracy conclusion is drawn. Effective-answer quality requires completed matched examples and independent evaluation.'
]
(out/'r13_first_case_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
lines=['# R13 first-case structural review','',
 'The first case naturally published `budget_exhausted`; the later operator stop of the overall run does not change that terminal outcome.','',
 'Calls: planner 1 + history 18 + semantic composition 4 = 23/24. There were no JSON repairs and no audit calls. All 18 history windows completed; their three reads used 7, 5, and 6 windows.','',
 'The four successful semantic calls and the next failed batch share one identity and form one `JointReader.read()` window loop. Completed window source counts were 38, 22, 25, 27; the final selected window had 5 sources and a total visible context of 40 sources. Its preflight failed before generation.','',
 'One LLM call remained, reserved for audit. At least two more calls were required: the last ordinary semantic window and one audit. Thus the current path needed at least 25 total calls; more might be needed if evidence, output, or audit still failed.','',
 'The final five-source window moved from unread markers into four failed-review markers, each retaining the complete 40-source context. Zero unread markers does not mean all work passed. The failed batch input_tokens field repeats the previous successful request count and must not be interpreted as a newly paid request.','',
 'No evidence here establishes repeated controller composition. The concrete pressure is history window count plus a multiwindow terminal context. The proposed prefix-admission change should be evaluated as an efficiency hypothesis, not an already-proven accuracy improvement.','',
 'JSON report contains only explicit structural/count/hash allowlists. No labels, model generation, network tokenization, or experiment mutations were performed by this report script.']
(out/'r13_first_case_review.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'report_json':str(out/'r13_first_case_review.json'),'report_md':str(out/'r13_first_case_review.md'),
 'history_batches':[x['batches'] for x in report['history_reads']],
 'semantic_required_closure_counts':[x['known_parent_task_obligation_source_closure_count'] for x in report['semantic_read']['paid_requests']],
 'semantic_required_text_chars':[x['required_closure_source_text_chars'] for x in report['semantic_read']['paid_requests']],
 'semantic_unique_sources':report['semantic_read']['all_five_window_unique_sources'],
 'failed_window_new_sources':report['semantic_read']['failed_window_sources_not_previously_in_paid_window'],
 'published_row_exists':report['published_row_exists']}))
