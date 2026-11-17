"""Add explicit obligation condition counts; no raw content emitted."""
import json
from pathlib import Path
from collections import Counter
out=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
p=Path('/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r15/personamem/dagbt_residual_memory_v2/attempts/2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0/attempt-001')
report=json.loads((out/'r15_second_case_review.json').read_text());chain=[]
for f in (p/'requests').glob('*.json'):
 item=json.loads(f.read_text());stage=item.get('stage',[])
 if stage not in (['joint_read','11'],['joint_read_repair','12'],['joint_read_repair','13']):continue
 data=json.loads(item['payload']['messages'][1]['content']);answer=json.loads(item['response']['choices'][0]['message']['content'])
 columns=data['source_span_columns'];visible={source[columns.index('id')] for source in data['source_spans']}
 frozen={};feedback=[];prior_rows={}
 for entry in data.get('repair_scope',{}).get('failed',[]):
  offer=entry.get('frozen_observation_reviews',{})
  for row in entry.get('slot',{}).get('observations',[]):
   prior_rows[(entry['variable'],row['id'])]=row
   if row['id'] in offer.get('slot_observation_ids',[]):frozen[(entry['variable'],row['id'])]=row
  for row in offer.get('observations',[]):frozen[(entry['variable'],row['id'])]=row
  for review in entry.get('obligation_review_sources',[]):
   feedback.append({'required_source_count':len(review['required_source_ids']),
      'covered_source_count':len(review['covered_source_ids']),'missing_source_count':len(review['missing_source_ids'])})
 record={'stage':stage,'input_feedback':feedback,'offered_frozen_observation_count':len(frozen),
     'input_feedback_is_frozen_restatement_error':any(entry.get('feedback')=='A referenced frozen observation must not be restated or changed' for entry in data.get('repair_scope',{}).get('failed',[])),
     'slot_conditions':[]}
 for slot in answer['slots']:
  variable=slot['variable'];rows=slot['observations'];refs=slot.get('reviewed_observation_ids',[])
  referenced=[frozen[(variable,identifier)] for identifier in refs if (variable,identifier) in frozen]
  settled=[row for row in rows+referenced if row['stance'] in ('support','contradiction','irrelevant') and row['source_ids']]
  covered={source for row in settled for source in row['source_ids']}
  partial=[row for row in rows if row['stance'] in ('partial','unknown') and row['source_ids']]
  conditions={'variable':variable,'observation_stance_counts':dict(Counter(row['stance'] for row in rows)),
      'requested_reference_count':len(refs),'requested_references_offered_count':len(referenced),
      'reference_and_reported_id_overlap_count':len(set(refs)&{row['id'] for row in rows}),
      'partial_count':len(partial),'unresolved_count':len(slot['unresolved']),
      'settled_scopes_match':all(all(row.get(key)==value for key,value in data['requested_scopes'][variable].items()) for row in settled),
      'resolutions':[],'repeated_frozen_rows':[]}
  for row in rows:
   if row['id'] not in refs or (variable,row['id']) not in frozen:continue
   original=frozen[(variable,row['id'])];old=set(original['source_ids']);new=set(row['source_ids'])
   conditions['repeated_frozen_rows'].append({'exactly_unchanged':row==original,
       'only_source_order_changed':old==new and all(row.get(key)==original.get(key) for key in (set(row)|set(original))-{'source_ids'}),
       'added_source_count':len(new-old),'removed_source_count':len(old-new)})
  for oid in slot.get('resolved_obligation_ids',[]):
   obligation=next((review for review in data.get('evidence_obligations',[]) if review['id']==oid),None)
   required=set(obligation['source_ids']) if obligation else set()
   conditions['resolutions'].append({'offered_id_exists':obligation is not None,
       'variable_matches':obligation is not None and obligation['variable']==variable,
       'required_source_count':len(required),'all_required_sources_visible':required<=visible,
       'required_sources_covered_if_counting_raw_rows_and_offered_refs':len(required&covered),
       'missing_required_source_count':len(required-covered)})
  record['slot_conditions'].append(conditions)
 chain.append(record)
chain.sort(key=lambda item:int(item['stage'][-1]));report['obligation_review_chain']=chain
report['interpretation']='Natural second-case failure, with LLM and JSON repair budget remaining. The exact 52/17/35 source difference and one valid frozen offer reached repair12; its response redundantly referenced and restated the frozen support, changing only citation order and still adding zero coverage. Repair13 correctly received no stale offer after that noncoverage validation error, then again claimed full resolution with only17 of52 sources. Even accepting the redundant restatement would still leave35 required originals unreviewed. Later constraints and response reads failed capacity before terminal generation. This is evidence of instruction noncompliance in this case, not an accuracy or universal algorithm verdict.'
(out/'r15_second_case_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(out/'r15_second_case_review.md').write_text('''# R15 second-case structural review

Natural outcome: `unresolved_or_exhausted`; LLM13/24, JSON repairs5/6, ANN3. No terminal generation or audit occurred.

- Call11: correct offered obligation and scope, all52 sources visible, zero unresolved or partial output; support covered17 and omitted35.
- Repair12: exact52/17/35 feedback and one frozen observation offer reached the request. The response both referenced and restated the same support, changing only citation order. Coverage stayed17/52. The explicit reference/restatement rule correctly rejected this use.
- Repair13: the preceding noncoverage error correctly cleared stale difference feedback and offers. The response removed the reference but again claimed resolution with the same17 sources;35 remained uncovered.
- Subsequent constraints and response windows hit input capacity. The first case in this run had naturally succeeded, but the two cases do not establish an accuracy result.

No source text, answer text, labels, credentials, model generation, network tokenization or experiment mutations were involved in this report. The redundant reference was not the sole cause: accepting it would still leave the same35-source coverage gap.
''')
print(json.dumps({'report':str(out/'r15_second_case_review.json'),'markdown':str(out/'r15_second_case_review.md'),'chain_stages':[item['stage'] for item in chain]}))
