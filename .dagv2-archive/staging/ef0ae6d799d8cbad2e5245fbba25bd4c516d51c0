"""Safe structural monitoring of already authorized run; no network or mutation of run."""
import ast
import json
from pathlib import Path
from collections import Counter
BASE=Path('/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r20')
OUT=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
SOURCE=Path('/Users/mao/projects/dagv2-personamem-v4/dagbt')
literals={node.value for file in SOURCE.glob('*.py') for node in ast.walk(ast.parse(file.read_text())) if isinstance(node,ast.Constant) and isinstance(node.value,str)}

def load(path):
 try:return json.loads(path.read_text())
 except (OSError,ValueError):return None

def category(error):
 if error=='Evidence obligation resolution requires its offered ID, original sources, a sourced scoped review, and no unresolved issue':return 'obligation_resolution_conditions'
 if error=='A referenced frozen observation must not be restated or changed':return 'frozen_reference_restatement'
 if error.startswith('citation_capacity:'):return 'mandatory_downstream_context_capacity'
 if error in literals:return error
 if error.startswith('llm budget at '):return 'llm_call_reservation'
 if 'exceeds' in error and '(request token accounting)' in error:return 'actual_request_context_capacity'
 return 'dynamic_error_redacted'
manifest=load(BASE/'manifest.json') or {};ids=manifest.get('question_ids',{}).get('personamem',[])
index={unit:i for i,unit in enumerate(ids)}
rows=[]
for file in (BASE/'personamem/dagbt_residual_memory_v2/attempts').glob('*/attempt-*/result.json'):
 result=load(file)
 if not result:continue
 d=result.get('diagnostics',{});joint=d.get('joint_reading',{});cost=d.get('cost',{});used=d.get('ledger',{}).get('used',{})
 diagnostic_source='result_diagnostics'
 protocol_errors=Counter()
 if not d:
  # Early planner failures have no controller snapshot. Recover only explicit
  # scalar usage/error fields from saved events; never synthesize a zero cost.
  diagnostic_source='saved_fusion_events_for_missing_diagnostics'
  early=[]
  event_path=file.parent/'fusion_events.jsonl'
  if event_path.exists():
   for line in event_path.read_text().splitlines():
    try:early.append(json.loads(line))
    except ValueError:pass
  used={}
  for event in early:
   if event.get('event')=='budget_reserved':used[event['kind']]=event['used']
   if event.get('event')=='protocol_error':protocol_errors[category(event.get('error',''))]+=1
  operations=Counter(event.get('operation') for event in early if event.get('event')=='reasoning_request_started')
  cost={'joint_read_calls':operations['joint_read'],'semantic_compose_calls':operations['semantic_compose'],
        'audit_calls':operations['audit_joint'],
        'repair_calls':sum(event.get('event')=='reasoning_repair_prepared' for event in early)
          +sum(n for op,n in operations.items() if isinstance(op,str) and op.endswith('_repair'))}
  raw_error=result.get('answer',{}).get('error','')
  try:inner=json.loads(raw_error[raw_error.index('{'):])
  except (ValueError,TypeError):inner={}
  d={'events':early,'errors':[{'node_id':None,'type':inner.get('error_type'),'error':inner.get('error','')}]
     if inner.get('error_type') else []}
 # Dynamic raw errors never pass through this output; only known fixed messages/categories.
 failures=Counter(category(slot.get('error','')) for batch in joint.get('batches',[]) for slot in batch.get('failed_slots',[]))
 events=d.get('events',[])
 row={'question_index':index.get(result.get('unit_id')),'unit_id':result.get('unit_id'),
     'status':result.get('answer',{}).get('status'),'audit_complete':d.get('audit_complete'),
     'llm_used':used.get('llm'),'json_repairs_used':used.get('json_repairs',0),'ann_used':used.get('ann'),
     'history_calls':cost.get('joint_read_calls'),'terminal_calls':cost.get('semantic_compose_calls'),
     'audit_calls':cost.get('audit_calls'),'repair_calls':cost.get('repair_calls'),
     'diagnostic_source':diagnostic_source,'protocol_error_categories':dict(protocol_errors),
     'pending_variable_count':len(d.get('fact_state',{}).get('pending_variables',[])),
     'failure_categories':dict(failures),'error_type_counts':dict(Counter(item.get('type') for item in d.get('errors',[]))),
     'errors':[{'node_id':item.get('node_id'),'type':item.get('type'),'category':category(item.get('error',''))} for item in d.get('errors',[])],
     'capacity_unavailable_batches':[{'operation':batch.get('operation'),'unread_group_count':len(batch.get('unread_source_aliases',[]))} for batch in joint.get('batches',[]) if batch.get('status')=='capacity_unavailable'],
     'capacity_rejection_count':sum(e.get('event')=='joint_support_capacity_rejected' for e in events),
     'capacity_deferred_count':sum(e.get('event')=='joint_support_handoff_deferred' for e in events),
     'planner_request_count':sum(e.get('event')=='reasoning_request_started' and e.get('operation')=='planner' for e in events),
     'attempt_result_path':str(file.relative_to(BASE))}
 rows.append(row)
rows.sort(key=lambda row:(row['question_index'] if row['question_index'] is not None else 999,row['attempt_result_path']))
progress=load(BASE/'progress.json') or {}
summary={'run':'v4_validation_r20','source_commit':'6c046374008ce2e45f817d6bc9876b3ab927ab18','scope':'Read-only structural analysis: this analysis reads no labels/scores and exports no source/answer text; the runner may separately auto-score at terminal completion.',
    'planned_questions':len(ids),'completed_attempt_rows':len(rows),
    'status_counts':dict(Counter(row['status'] for row in rows)),
    'progress':{k:progress.get(k) for k in ('state','arm','question_index','questions_in_dataset','updated_unix','failed_arm_tasks')},
    'cases':rows}
prior=load(OUT/'r20_structural_monitor.json') or {}
active=[];new_active_failures=[]
previous_active={item['attempt_path']:item for item in prior.get('active_attempts',[])}
for event_file in (BASE/'personamem/dagbt_residual_memory_v2/attempts').glob('*/attempt-*/fusion_events.jsonl'):
 if (event_file.parent/'result.json').exists():continue
 events=[]
 for line in event_file.read_text().splitlines():
  try:events.append(json.loads(line))
  except ValueError:pass
 if not events:continue
 attempt_path=str(event_file.parent.relative_to(BASE));last=previous_active.get(attempt_path,{}).get('last_sequence',0)
 used={}
 for event in events:
  if event.get('event')=='budget_reserved':used[event['kind']]=event['used']
  if event.get('sequence',0)<=last:continue
  if event.get('event')=='joint_read_completed' and not event.get('complete',True):
   new_active_failures.append({'attempt_path':attempt_path,'sequence':event['sequence'],'operation':event['operation'],
       'failures':[category(slot.get('error','')) for slot in event.get('failed_slots',[])]})
  elif event.get('event')=='residual_action_incomplete':
   new_active_failures.append({'attempt_path':attempt_path,'sequence':event['sequence'],'error_type':event.get('type'),
       'category':category(event.get('error',''))})
 active.append({'attempt_path':attempt_path,'last_sequence':events[-1].get('sequence'),
     'llm_used':used.get('llm',0),'json_repairs_used':used.get('json_repairs',0),
     'completed_batches':sum(event.get('event')=='joint_read_completed' and event.get('complete',False) for event in events)})
summary['arm_status_counts']={}
for arm in manifest.get('arms',[]):
 canonical=[load(p) for p in (BASE/'personamem'/arm/'rows').glob('*.json')]
 summary['arm_status_counts'][arm]=dict(Counter(r.get('answer',{}).get('status') for r in canonical if r))
summary['active_attempts']=active
summary['active_failure_events']=prior.get('active_failure_events',[])+new_active_failures
import contextlib, io, runpy
with contextlib.redirect_stdout(io.StringIO()):
 runpy.run_path(str(OUT/'review_r20_tokenization.py'),run_name='__main__')
 runpy.run_path(str(OUT/'review_r20_review_wire.py'),run_name='__main__')
token_review=load(OUT/'r20_tokenization_review.json') or {}
summary['tokenization_failures']={arm:{key:value for key,value in item.items() if key!='failed_requests'}
 for arm,item in token_review.get('arms',{}).items()}
previous={row['attempt_result_path']:row for row in prior.get('cases',[])}
new=[row for row in rows if previous.get(row['attempt_result_path'])!=row]
(OUT/'r20_structural_monitor.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'completed':len(rows),'planned':len(ids),'status_counts':summary['status_counts'],
    'progress':summary['progress'],'arm_status_counts':summary['arm_status_counts'],'tokenization_failures':summary['tokenization_failures'],'new_cases':new,'active':active,'new_active_failures':new_active_failures},ensure_ascii=False))
