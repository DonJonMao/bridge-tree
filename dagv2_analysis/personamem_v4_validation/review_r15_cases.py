"""Read-only structural case reports; no model text, labels, or external calls."""
import json
from pathlib import Path
from collections import Counter
BASE=Path('/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r15')
OUT=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
CASES=[('first','7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0'),
       ('second','2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0')]
for ordinal,key in CASES:
 p=BASE/'personamem/dagbt_residual_memory_v2/attempts'/key/'attempt-001'
 if not (p/'result.json').exists():continue
 r=json.loads((p/'result.json').read_text());d=r['diagnostics']
 events=[json.loads(line) for line in (p/'fusion_events.jsonl').read_text().splitlines()]
 requests=[]
 for f in (p/'requests').glob('*.json'):
  item=json.loads(f.read_text());stage=item.get('stage',[])
  if not stage or stage[0] not in ('planner','joint_read','joint_read_repair','semantic_compose','semantic_compose_repair','audit_joint','audit_joint_repair'):continue
  data=json.loads(item['payload']['messages'][1]['content']);response=item.get('response',{});usage=response.get('usage',{});choices=response.get('choices',[])
  if not isinstance(data,dict):data={}
  fields=data.get('repair_scope',{}).get('failed',[])
  feedback=sum(len(entry.get('obligation_review_sources',[])) for entry in fields)
  offers=sum(len(entry.get('frozen_observation_reviews',{}).get('slot_observation_ids',[]))+
      len(entry.get('frozen_observation_reviews',{}).get('observations',[])) for entry in fields)
  parsed=None
  if choices:
   try:parsed=json.loads(choices[0]['message']['content'])
   except (ValueError,KeyError,TypeError):pass
  slots=parsed.get('slots',[]) if isinstance(parsed,dict) else []
  requests.append({'stage':stage,'max_tokens':item['payload']['max_tokens'],
      'finish_reason':choices[0].get('finish_reason') if choices else None,
      'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),
      'input_obligation_feedback_count':feedback,'offered_frozen_observation_count':offers,
      'output_explicit_frozen_reference_count':sum(len(slot.get('reviewed_observation_ids',[])) for slot in slots if isinstance(slot,dict))})
 requests.sort(key=lambda item:int(item['stage'][-1]))
 report={'run':'v4_validation_r15','case':ordinal,'commit':'50d1ba0b2edb623384e51ac42ea12b36e5b69229',
     'unit_id':r['unit_id'],'termination_kind':'natural published terminal outcome',
     'scope':'Structural saved records only; no labels, prediction/source text, generation, tokenization or experiment mutation.',
     'answer_status':r['answer']['status'],'audit_complete':d['audit_complete'],
     'pending_variables':d['fact_state']['pending_variables'],
     'ledger':{key:d['ledger'][key] for key in ('limits','used','remaining')},
     'cost':{key:d['cost'][key] for key in ('planner_calls','joint_read_calls','repair_calls','semantic_compose_calls','audit_calls','json_repair_reservations','generation_calls')},
     'cap_selections':[{key:event[key] for key in ('sequence','node_id','prefix_groups','output_token_cap','structure_floor_tokens','base_input_tokens','whole_review_forecast_input_tokens','initial_total_tokens','forecast_total_tokens','repair_output_reserve','context_tokens') if key in event} for event in events if event['event']=='joint_fresh_output_cap_selected'],
     'batches':[{'operation':event['operation'],'complete':event['complete'],
         'window_source_count':len(event['source_aliases']),'visible_source_count':len(event['visible_source_aliases']),
         'failed_slot_count':len(event['failed_slots']),
         **({'audit_complete':event['audit_complete'],'audit_verdict':event['audit_verdict']} if event['operation']=='audit_joint' else {})}
         for event in events if event['event']=='joint_read_completed'],
     'requests':requests,'event_counts':dict(Counter(event['event'] for event in events)),
     'interpretation':'Execution and certificate/audit outcome only. No labels or answer contents inspected; success does not establish accuracy or a causal improvement over different plans.'}
 (OUT/f'r15_{ordinal}_case_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'case':ordinal,'status':report['answer_status'],'audit_complete':report['audit_complete'],
     'llm_used':report['ledger']['used'].get('llm',0),'feedback_items':sum(item['input_obligation_feedback_count'] for item in requests),
     'explicit_refs':sum(item['output_explicit_frozen_reference_count'] for item in requests),
     'report':str(OUT/f'r15_{ordinal}_case_review.json')}))
