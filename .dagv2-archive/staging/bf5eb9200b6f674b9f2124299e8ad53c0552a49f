"""Read-only R14 first-case report using explicit structural output allowlists."""
import ast
import json
from pathlib import Path
from collections import Counter
ROOT=Path('/Users/mao/projects/dagv2-personamem-v4-reconcile')
BASE=Path('/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r14')
OUT=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
KEY='7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0'
p=BASE/'personamem/dagbt_residual_memory_v2/attempts'/KEY/'attempt-001'
result=json.loads((p/'result.json').read_text());d=result['diagnostics'];joint=d['joint_reading']
events=[json.loads(line) for line in (p/'fusion_events.jsonl').read_text().splitlines()]
literals={node.value for f in (ROOT/'dagbt').glob('*.py') for node in ast.walk(ast.parse(f.read_text()))
    if isinstance(node,ast.Constant) and isinstance(node.value,str)}
requests={tuple(r['stage']):r for f in (p/'requests').glob('*.json') if (r:=json.loads(f.read_text())).get('stage')}

def error_kind(error):
    if error in literals:return error
    if error.startswith('citation_capacity: mandatory '):return 'citation_capacity: mandatory downstream request exceeds context including repair reserve'
    return 'dynamic_error_not_emitted'

def numeric_request(stage):
    r=requests[stage];response=r.get('response',{});usage=response.get('usage',{});choices=response.get('choices',[])
    return {'stage':list(stage),'max_tokens':r['payload'].get('max_tokens'),
        'finish_reason':choices[0].get('finish_reason') if choices else None,
        'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens')}

def obligation_conditions(stage):
    r=requests[stage];data=json.loads(r['payload']['messages'][1]['content'])
    answer=json.loads(r['response']['choices'][0]['message']['content'])
    columns=data['source_span_columns'];visible={row[columns.index('id')] for row in data['source_spans']}
    records=[]
    for slot in answer.get('slots',[]):
        rows=slot.get('observations',[])
        settled=[row for row in rows if row.get('stance') in ('support','contradiction','irrelevant') and row.get('source_ids')]
        partial=[row for row in rows if row.get('stance') in ('partial','unknown') and row.get('source_ids')]
        covered={alias for row in settled for alias in row['source_ids']}
        for oid in slot.get('resolved_obligation_ids',[]):
            offered=next((item for item in data.get('evidence_obligations',[]) if item['id']==oid),None)
            required=set(offered['source_ids']) if offered else set()
            records.append({'variable':slot['variable'],'offered_id_exists':offered is not None,
                'offered_variable_matches':offered is not None and offered['variable']==slot['variable'],
                'required_source_count':len(required),'all_required_sources_visible':required<=visible,
                'settled_observation_count':len(settled),'settled_stance_counts':dict(Counter(row['stance'] for row in settled)),
                'settled_scopes_match':all(all(row.get(k)==v for k,v in data['requested_scopes'][slot['variable']].items()) for row in settled),
                'partial_or_unknown_observation_count':len(partial),'unresolved_count':len(slot.get('unresolved',[])),
                'covered_source_count':len(covered),'required_source_covered_count':len(required&covered),
                'missing_required_source_count':len(required-covered),'all_required_sources_covered':required<=covered})
    failed=data.get('repair_scope',{}).get('failed',[])
    return {'stage':list(stage),'conditions':records,
        'repair_feedback_is_generic_obligation_error':bool(failed) and all(item.get('feedback')==
            'Evidence obligation resolution requires its offered ID, original sources, a sourced scoped review, and no unresolved issue' for item in failed),
        'repair_has_explicit_missing_source_feedback':any('summary_revision_sources' in item or 'missing_source_ids' in item for item in failed)}

report={'run':'v4_validation_r14','commit':'25fc3849ab8d4b7ab85cf5efdeafddf2d685c58b','unit_id':result['unit_id'],
    'scope':'Read-only saved structural evidence. No generation, tokenization, labels, source/option/prediction text, full snapshots or credentials emitted; no experiment mutations.',
    'termination_kind':'natural first-case terminal outcome before any later operator stop',
    'published_row_exists':(BASE/'personamem/dagbt_residual_memory_v2/rows'/f'{KEY}.json').exists(),
    'answer_status':result['answer']['status'],'audit_complete':d['audit_complete'],
    'pending_variables':d['fact_state']['pending_variables'],
    'ledger':{k:d['ledger'][k] for k in ('limits','used','remaining')},
    'cost':{k:d['cost'][k] for k in ('generation_calls','joint_read_calls','repair_calls','json_repair_reservations','semantic_compose_calls','audit_calls','planner_calls','ann_calls','llm_attempts')},
    'cap_selections':[],
    'requests':[numeric_request(stage) for stage in sorted((stage for stage in requests if stage[0] in ('planner','joint_read','joint_read_repair','semantic_compose','semantic_compose_repair','audit_joint','audit_joint_repair')),key=lambda stage:int(stage[-1]))],
    'obligation_failure':[obligation_conditions(('joint_read','6')),obligation_conditions(('joint_read_repair','7'))],
    'batch_results':[],'mandatory_handoff_rejections':[],'repair_capacity_failures':[],
    'unread_obligation_count':len(joint['unread_obligations']),
    'failed_obligation_count':len(joint['failed_obligations']),
    'evidence_obligations':[{'variable':item['variable'],'source_count':len(item['source_ids']),'description_count':len(item['descriptions'])} for item in joint['evidence_obligations']],
    'failed_batch_reviews':[{'variable':item['variable'],'source_count':len(item['source_ids']),
        'failed_draft_count':len(item['failed']),'validated_observation_count':len(item['validated_observations'])} for item in joint['failed_batch_reviews']],
    'error_types':dict(Counter(item['type'] for item in d['errors']))}
cap_fields=('sequence','node_id','prefix_groups','output_token_cap','structure_floor_tokens','base_input_tokens','whole_review_forecast_input_tokens','initial_total_tokens','forecast_total_tokens','repair_output_reserve','input_margin','safety_margin','context_tokens')
for index,event in enumerate(events):
    if event['event']=='joint_fresh_output_cap_selected':
        report['cap_selections'].append({key:event[key] for key in cap_fields if key in event})
    elif event['event']=='joint_read_completed':
        report['batch_results'].append({'sequence':event['sequence'],'operation':event['operation'],'identity':event['identity'],
            'complete':event['complete'],'source_count':len(event['source_aliases']),
            'visible_source_count':len(event['visible_source_aliases']),'valid_rows':event['valid_rows'],
            'failed_slots':[{'variable':item['variable'],'category':error_kind(item['error'])} for item in event['failed_slots']]})
    elif event['event']=='joint_support_capacity_rejected':
        preceding=[item['count'] for item in events[max(0,index-5):index] if item['event']=='tokenization_count']
        report['mandatory_handoff_rejections'].append({'sequence':event['sequence'],
            'next_operation':event['next_operation'],'next_node_id':event['next_node_id'],
            'source_spans':event['source_spans'],'support_draft_count':len(event['support_draft_ids']),
            'source_ids_preserved':event['source_ids_preserved'],'context_tokens':event['context_tokens'],
            'preceding_saved_token_counts':preceding})
    elif event['event']=='joint_repair_input_unavailable':
        report['repair_capacity_failures'].append({key:event[key] for key in
            ('sequence','operation','node_id','repair_attempt','input_tokens','output_token_reserve','input_margin','context_tokens','estimated_total_tokens') if key in event})
report['interpretation']=[
    'R14 is a natural unresolved_or_exhausted result with LLM budget remaining, but all six JSON repair reservations consumed. No terminal generation or audit occurred.',
    'The music large-window cap425 exceeded its measured floor410 but truncated; a full4096 repair completed. A state-preserving floor is not a guarantee of enough output for semantic work.',
    'The event_history cap569 and full repair both stopped normally. The offered obligation ID, scope and all53 original sources were present, with no unresolved/partial output. A three-source support declared that whole53-source obligation resolved; required<=covered failed because50 sources were not covered.',
    'Repair feedback retained the offered obligation and original slot but gave a generic condition error, not an explicit missing-source difference. The unchanged scoped repair was subsequently stopped without another generation.',
    'Failed review kept93 event_history sources. Subsequent support admission was rejected because mandatory semantic composition carried95 original source spans and exceeded16k with full output/repair reserve. A later actual repair total16627 exceeded the limit by243.',
    'R14 planner has four historical nodes versus three in R13; whole-task call counts are not a controlled policy-only comparison. The fixed archived R12 replay remains the clean admission comparison.',
    'No source dropping, automatic obligation clearing, accuracy claim or code-defect conclusion is justified by these counts alone.'
]
(OUT/'r14_first_case_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
markdown=['# R14 first-case review','',
 'Natural terminal status: `unresolved_or_exhausted`. LLM13/24, ANN4, JSON repairs6/6; terminal calls0, audit calls0.','',
 'Music history used an initial full window and a second large capped window. Cap425/floor410 truncated; a full4096 repair passed. The nonempty structural floor did not guarantee enough generation length.','',
 'Event-history cap569/floor505 returned normally, as did its repair. Both requested resolution of the correct offered obligation, with all53 original sources visible, a scoped support, zero partial observations and zero unresolved entries. The support covered3 required sources and omitted50. The exact failed subcondition was full required-source coverage. Repair feedback supplied the generic condition and original slot, without a source difference list.','',
 'That failed review retained93 sources. Six subsequent support-admission failures targeted mandatory semantic composition with95 visible original sources; its saved preceding input counts were14161–14524. One actual repair required16627 total tokens, exceeding16384 by243. Pending variables remained event_history, cultural_interests and taste_changes.','',
 'These are distinct from total LLM-budget exhaustion. R14 also used a different four-history-node plan than R13, so aggregate call counts do not isolate the prefix policy.','',
 'This report contains structural counts and fixed-error classifications only; it makes no answer-accuracy or automatic code-defect claim.']
(OUT/'r14_first_case_review.md').write_text('\n'.join(markdown)+'\n')
print(json.dumps({'report_json':str(OUT/'r14_first_case_review.json'),'report_md':str(OUT/'r14_first_case_review.md'),
    'status':report['answer_status'],'llm_used':report['ledger']['used']['llm'],
    'json_repairs_used':report['ledger']['used']['json_repairs'],'mandatory_handoff_rejections':len(report['mandatory_handoff_rejections'])}))
