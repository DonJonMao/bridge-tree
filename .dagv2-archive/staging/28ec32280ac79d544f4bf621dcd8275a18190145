"""Read only canonical case 1 saved structure; no labels/services/run writes."""
import ast, json, hashlib, sys
from pathlib import Path
from collections import Counter
sys.dont_write_bytecode=True
ROOT=Path('/Users/mao/projects/dagv2-personamem-v4')
sys.path.insert(0,str(ROOT))
from dagbt.history_wire import unpack
from jsonschema import Draft202012Validator
RUN=ROOT/'outputs/v4_validation_r19'
OUT=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
COMMIT='0cc2cc78498bcd215252fb8e82d2168868a71b3f'
manifest=json.loads((RUN/'manifest.json').read_text());unit=manifest['question_ids']['personamem'][0]
paths=list((RUN/'personamem/dagbt_residual_memory_v2/rows').glob('*.json'))
path=next(p for p in paths if json.loads(p.read_text())['unit_id']==unit)
result=json.loads(path.read_text());diag=result['diagnostics'];joint=diag['joint_reading'];facts=diag['fact_state']
ATT=RUN/'personamem/dagbt_residual_memory_v2/attempts'/path.stem/f"attempt-{result['runner']['attempt']:03d}"
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def file_hash(p):return hashlib.sha256(p.read_bytes()).hexdigest()
literals={n.value for p in (ROOT/'dagbt').glob('*.py') for n in ast.walk(ast.parse(p.read_text())) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
def category(value):
    if value in literals:return value
    if str(value).startswith('citation_capacity:'):return 'citation_capacity'
    return 'dynamic_error_redacted'
def observation(row):
    if not isinstance(row,dict):return {'type':type(row).__name__}
    return {'id':row.get('id'),'stance':row.get('stance'),'value_hash':digest(row.get('value')),
       'source_ids':row.get('source_ids'),'entity_scope_hash':digest(row.get('entity_scope')),
       'scope_hash':digest({k:row.get(k) for k in ('entity_scope','time_scope')}),'time_scope_hash':digest(row.get('time_scope')),'parent_versions':row.get('parent_versions'),
       'retract_ids':row.get('retract_ids'),'summary_revision_targets':row.get('summary_revision',{}).get('supersedes_route_ids'),
       'row_hash':digest(row)}
def slot(row):
    if not isinstance(row,dict):return {'type':type(row).__name__}
    return {'variable':row.get('variable'),'observations':[observation(x) for x in row.get('observations',[])],
       'unresolved_count':len(row.get('unresolved',[])),'unresolved_hashes':[digest(x) for x in row.get('unresolved',[])],
       'resolved_obligation_ids':row.get('resolved_obligation_ids',[]),
       'resolved_failed_batch_ids':row.get('resolved_failed_batch_ids',[]),
       'reviewed_observation_ids':row.get('reviewed_observation_ids',[])}
records=[]
for p in (ATT/'requests').glob('*.json'):
    item=json.loads(p.read_text());stage=item.get('stage',[])
    if len(stage)!=2:continue
    payload=item['payload'];system=payload['messages'][0]['content']
    data=json.loads(payload['messages'][1]['content'])
    if not isinstance(data,dict):continue
    data=unpack(data)
    if 'source_span_columns' in data:
        data['source_spans']=[dict(zip(data['source_span_columns'],r)) for r in data['source_spans']]
    if stage[0] not in {'joint_read','joint_read_repair','semantic_compose','semantic_compose_repair','audit_joint','audit_joint_repair'}:continue
    raw=item.get('response',{}).get('choices',[{}])[0].get('message',{}).get('content')
    try:response=json.loads(raw)
    except (ValueError,TypeError):response=None
    schema=json.loads(system.rsplit('Return one complete JSON object matching this schema:\n',1)[1])
    errors=list(Draft202012Validator(schema).iter_errors(response)) if response is not None else []
    failed=[]
    for x in data.get('repair_scope',{}).get('failed',[]):
        offer=x.get('frozen_observation_reviews',{})
        failed.append({'variable':x.get('variable'),'id':x.get('id'),'feedback':category(x.get('feedback','')),
            'observation':observation(x['observation']) if x.get('observation') is not None else None,
            'slot':slot(x['slot']) if x.get('slot') is not None else None,
            'offer_slot_ids':offer.get('slot_observation_ids',[]),'offer_complete_rows':[observation(y) for y in offer.get('observations',[])],
            'coverage_feedback':x.get('obligation_review_sources')})
    obligations=[{'id':x['id'],'variable':x['variable'],'source_ids':x['source_ids'],
        'description_hashes':[digest(y) for y in x.get('descriptions',[])]} for x in data.get('evidence_obligations',[])]
    records.append({'stage':stage,'file':str(p.relative_to(RUN)),'file_sha256':file_hash(p),'system_hash':digest(system),'schema_hash':digest(schema),
        'task_id':data.get('task',{}).get('output_slot'),'phase':data.get('phase'),'requested_slots':data.get('requested_slots'),
        'query_hash':digest(data.get('grounded_subquestion')),'public_options_present':'public_options' in data,
        'visible_source_count':len(data.get('source_spans',[])),
        'visible_source_ids':[s['id'] for s in data.get('source_spans',[])],
        'requested_scope_hashes':{v:digest(scope) for v,scope in data.get('requested_scopes',{}).items()},
        'known_observation_ids':[r['id'] for r in data.get('known_observations',[])],
        'prompt_freezing_instruction': 'Already validated observations are frozen and must not be restated or changed.' in system,
        'prompt_explicit_reference_instruction':'Do not restate or edit a frozen observation.' in system,
        'prompt_summary_distinguishes_current_batch':'This does not authorize restating an already validated, frozen row from the current' in system,
        'repair_failed':failed,'evidence_obligations':obligations,
        'failed_batch_reviews':[{'id':x['id'],'variable':x['variable'],'review_allowed':x.get('review_allowed'),'source_count':len(x['source_ids'])} for x in data.get('failed_batch_reviews',[])],
        'response_slots':[slot(x) for x in (response or {}).get('slots',[])],
        'finish_reason':item.get('response',{}).get('choices',[{}])[0].get('finish_reason'),
        'schema_valid':not errors if response is not None else None,
        'schema_error_paths':[{'path':list(e.absolute_path),'schema_path':list(e.absolute_schema_path),'validator':e.validator} for e in errors],
        'schema_branches':schema['properties']['slots']['items'].get('oneOf',[]),
        'input_tokens':item.get('tokenization_validation',{}).get('local_input_tokens'),
        'payload_has_response_format':'response_format' in payload,'output_cap':payload.get('max_tokens')})
records.sort(key=lambda x:int(x['stage'][1]))
for record in records:
    record['all_returned_support_scopes_match_requested']=all(
        row['scope_hash']==record['requested_scope_hashes'].get(slot['variable'])
        for slot in record['response_slots'] for row in slot['observations'] if row['stance']=='support')
    record['obligation_source_coverage']=[]
    for issue in record['evidence_obligations']:
        requested=set(issue['source_ids'])
        cited={source for slot in record['response_slots'] if slot['variable']==issue['variable']
            for row in slot['observations'] for source in row['source_ids']}
        record['obligation_source_coverage'].append({'id':issue['id'],'required_count':len(requested),
            'covered_count':len(requested&cited),'missing_count':len(requested-cited),
            'missing_source_ids':sorted(requested-cited)})

events=[json.loads(s) for s in (ATT/'fusion_events.jsonl').read_text().splitlines()]
filtered=[]
for e in events:
    name=e.get('event')
    if name=='joint_read_completed':
        filtered.append({k:e.get(k) for k in ['sequence','event','operation','identity','source_aliases','visible_source_aliases','valid_rows','complete','input_tokens','initial_output_token_cap']})
        filtered[-1]['failed_slots']=[{'variable':s.get('variable'),'id':s.get('id'),'error':category(s.get('error',''))} for s in e.get('failed_slots',[])]
    elif name=='residual_action_incomplete':
        filtered.append({**{k:e.get(k) for k in ['sequence','event','node_id','type']},'category':category(e.get('error',''))})
    elif name=='residual_state':
        filtered.append({k:e.get(k) for k in ['sequence','event','active_demands','paused_demands','reactivated_demands']})
    elif name in {'model_context_budget','reasoning_request_started'}:
        filtered.append({k:e.get(k) for k in ['sequence','event','operation','logical_call_index','input_tokens_local','output_token_reserve','input_margin','context_tokens'] if k in e})
plan=next(e['plan'] for e in events if e.get('event')=='plan_frozen')
report={'run':RUN.name,'source_commit':COMMIT,'unit_id':unit,'question_index':1,'status':result['answer']['status'],
    'scope':'Canonical case 1 structural review; no labels/scores/services/run mutation. Report contains hashes and structural fields only.',
    'source_files_sha256':{name:file_hash(ROOT/name) for name in ['dagbt/joint_reading.py','dagbt/residual_control.py','dagbt/reasoning.py']},
    'evidence_files_sha256':{str(p.relative_to(RUN)):file_hash(p) for p in [path,ATT/'fusion_events.jsonl',ATT/'fusion_snapshot.json',ATT/'tokenization_events.jsonl']},
    'plan_structure':{'steps':[{'output_slot':s['output_slot'],'inputs':s['inputs'],'execution':s['execution'],'question_hash':digest(s['question'])} for s in plan['steps']],
        'variables':{v:{k:d.get(k) for k in ['type','demand','evidence_semantics']} for v,d in plan['program']['variables'].items()},'mode':plan['output_contract']['mode']},
    'requests':records,'event_timeline':filtered,'ledger':{k:diag['ledger'].get(k) for k in ('limits','used','remaining')},'audit_complete':diag['audit_complete'],
    'pending_variables':facts.get('pending_variables'),'bound_variable_names':list(facts.get('facts',{})),
    'final_obligations':[{'id':x['id'],'variable':x['variable'],'source_count':len(x['source_ids']),'description_hashes':[digest(y) for y in x.get('descriptions',[])]} for x in joint.get('evidence_obligations',[])],
    'final_failed_reviews':[{'id':x['id'],'variable':x['variable'],'source_count':len(x['source_ids']),'validated_observation_ids':[r['id'] for r in x.get('validated_observations',[])],'failed_ids':[f['id'] for f in x.get('failed',[])]} for x in joint.get('failed_batch_reviews',[])],
    'unread_by_query':dict(Counter(x[0] for x in joint.get('unread_obligations',[]))),
    'event_counts':dict(Counter(e.get('event') for e in events)),
    'saved_capacity_counts':[{'sequence':e['sequence'],'count':e['count'],
        'request_sha256':e['tokenization_request_sha256'],'wire_sha256':e.get('tokenization_wire_sha256'),
        'token_count_is_estimate':e['token_count_is_estimate']} for e in events if e.get('sequence') in (369,370)],
    'all_request_accounting_exact':all(not e.get('token_count_is_estimate',True) for e in events if e.get('event')=='tokenization_count')}
(OUT/'r19_case01_reader_failure_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':report['status'],'request_count':len(records),'report':str(OUT/'r19_case01_reader_failure_review.json')},ensure_ascii=False))
