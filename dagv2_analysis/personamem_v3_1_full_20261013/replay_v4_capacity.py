"""Count only, never generation: replay the eight recorded capacity dead ends."""
from copy import deepcopy
import gzip, importlib.util, json, sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path('/Users/mao/projects/dagv2-personamem-v4')
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from dagbt.budget import Ledger
from dagbt.fact_state import FactState
from dagbt.resources import personamem_document
from dagbt.evidence_mapping import EvidenceMapper
from dagbt.joint_reading import JointReader
from dagbt.residual_control import ResidualControl
from dagbt.reasoning import Reasoner
from dagbt.transport import Transport, digest
spec=importlib.util.spec_from_file_location('dagbt._capacity_old_reader','/Users/mao/projects/dagv2-personamem-a48/dagbt/joint_reading.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
selected=[x for x in json.loads((BASE/'contract_deadend_repro.json').read_text())['rows'] if x['primary_observed_cause']=='local_input_overflow']
questions={x['id']:x for x in map(json.loads,(ROOT/'data/personamem/questions.jsonl').read_text().splitlines())}
needed=set()
for feature in selected:
 with gzip.open(BASE/feature['path'],'rt') as f: row=json.load(f)
 needed.update(row['diagnostics']['candidate_doc_ids'])
docs={}
with (ROOT/'data/personamem/corpus.jsonl').open() as f:
 for line in f:
  doc=json.loads(line)
  if doc['docid'] in needed: docs[doc['docid']]=personamem_document(doc)
config=json.loads((ROOT/'configs/personamem-v4.json').read_text())
if config.get('credentials_file'):
 config['credentials_file']=str(Path('/Users/mao/projects/dagv2')/config['credentials_file'])
results=[]
for feature in selected:
 with gzip.open(BASE/feature['path'],'rt') as f: row=json.load(f)
 d=row['diagnostics']; initial=next(e for e in d['events'] if e['event']=='typed_dag_initialized')
 state=FactState(d['fact_state']['initial_program'],d['fact_state']['contract'],initial['dag'],initial['final_node_id'])
 state.restore(d['fact_state']); q=questions[row['unit_id']]; settings=d['settings']
 engine=SimpleNamespace(q={**q,'question':q['user_question']},reader_question=q['question'],output_options=q['options'],
   personal_response_selection=False,steps=initial['dag'],final_node_id=initial['final_node_id'],fact_state=state,
   docs=docs,s=settings,spans={s['id']:s for s in d['spans']},candidates=[],chunks=[],event=lambda e:None)
 engine.mapper=EvidenceMapper(engine);engine.mapper.add_candidates(d['candidate_doc_ids'])
 assert all(s in engine.mapper.source_aliases for route in state.routes.values() for s in route['source_ids'])
 controller=ResidualControl(engine);engine.residual_control=controller
 new=controller.reader; previous=old.JointReader(engine,state)
 failed=next(b for b in reversed(d['joint_reading']['batches']) if b.get('status')=='capacity_unavailable')
 step=next(s for s in engine.steps if s['output_slot']==feature['errors'][-1]['node_id'])
 variables=controller.demand_variables(step['output_slot'])
 values,_,route_ids=state.valid()
 related={v for v,declaration in state.program['variables'].items() if v in values and declaration['demand'] in step['inputs']}
 frontier=list(related)
 while frontier:
  for rid in route_ids.get(frontier.pop(),[]):
   for parent in state.routes[rid]['parent_versions']:
    if parent not in related:related.add(parent);frontier.append(parent)
 variables=list(dict.fromkeys([*variables,*sorted(related)]))
 query=controller.grounded(step)
 trial=failed['unread_source_aliases'][0]
 operation=failed['operation']; ledger=Ledger({'llm':0})
 cfg={**config,'fusion':settings}
 transport=Transport('capacity-'+row['unit_id'],BASE/'v4_capacity_tokenization',cfg,ledger,None)
 reasoner=Reasoner(transport,None,cfg,settings,ledger,lambda e:None)
 if '--admission' in sys.argv:
  broad=max(state.routes.values(),key=lambda r:len(r['source_ids']))
  history=d['fact_state']['history']
  position=next(i for i,batch in enumerate(history) if any(r['stance']=='support' and r['variable']==broad['variable'] and r['source_ids']==broad['source_ids'] and r['value']==broad['value'] for r in batch['rows']))
  before=FactState(d['fact_state']['initial_program'],d['fact_state']['contract'],initial['dag'],initial['final_node_id'])
  for batch in history[:position]: before.integrate(batch['rows'],batch['pending_variables'])
  candidate=history[position]['rows']
  engine.fact_state=before;engine.reasoner=reasoner
  admission_events=[];engine.event=admission_events.append
  controller=ResidualControl(engine);engine.residual_control=controller
  reader=controller.reader
  before_identity=digest(before.public_dict())
  rejected=reader._handoff_failures(candidate,{(r['variable'],r['id']) for r in candidate if r['stance']=='support'})
  record={'unit_id':row['unit_id'],'history_batch_index':position,'broad_variable':broad['variable'],
    'broad_source_count':len(broad['source_ids']),'rejected_broad_support':any(v==broad['variable'] for v,rid in rejected),
    'rejected': [{'variable':v,'id':rid,'feedback':message} for (v,rid),message in rejected.items()],
    'events':admission_events,'facts_unchanged':before_identity==digest(before.public_dict()),
    'generation_requests':len(reasoner.requests)}
  results.append(record);print(json.dumps(record),flush=True)
  (BASE/'v4_capacity_admission.json').write_text(json.dumps({'scope':'Exact deployment-tokenizer check immediately BEFORE original broad support integration, using original logged candidate rows and prior history. No generation or labels. Citation refinement success is not inferred.', 'rows':results},indent=2)+'\n')
  continue
 record={'unit_id':row['unit_id'],'old_status':row['answer']['status'],'operation':operation,
    'context_tokens':settings['context_tokens'],'output_reserve':settings['reasoning_output_tokens'],'input_margin':settings['input_margin'],
    'known_routes':len(state.routes),'route_source_counts':[{'variable':r['variable'],'count':len(r['source_ids'])} for r in state.routes.values()]}
 for name,reader in [('deployed',previous),('v4_same_plan',new),('v4_personal_guidance',new)]:
  engine.personal_response_selection=name=='v4_personal_guidance'
  reader.current_identity=failed['identity'];reader.current_terminal_output=step['output_slot']==engine.final_node_id
  data=reader._payload(step,query,variables,trial,operation=='semantic_compose',audit=operation=='audit_joint')
  wire=reader._wire_data(data);schema=reader._schema(data)
  count=reasoner.estimate(operation,reader._system(wire),wire,schema)
  repair_data={**data,'repair_scope':{'failed':[{'variable':v,'id':'*','feedback':'x'*240,'observation':None} for v in data['variables']], 'attempt':1,'previous_response_identity':'0'*64}}
  repair_wire=reader._wire_data(repair_data)
  repair_count=reasoner.estimate(operation+'_repair',reader._system(repair_wire),repair_wire,reader._schema(repair_data))
  total=max(count,repair_count)+settings['reasoning_output_tokens']+settings['input_margin']+8
  record[name]={'input_tokens':count,'repair_input_tokens':repair_count,'required_total':total,'fits':total<=settings['context_tokens'],
     'wire_bytes':len(json.dumps(wire,ensure_ascii=False,separators=(',',':')).encode()),'source_spans':len(data['source_spans']),
     'source_characters':sum(len(s['text']) for s in data['source_spans']),'packed_observations':'known_observation_columns' in wire}
  if name=='v4_personal_guidance':
   (BASE/'v4_capacity_payloads').mkdir(exist_ok=True)
   with gzip.open(BASE/'v4_capacity_payloads'/f'{row["unit_id"]}.json.gz','wt') as f:json.dump(data,f)
 results.append(record)
 print(json.dumps(record),flush=True)
 (BASE/'v4_capacity_replay.json').write_text(json.dumps({'scope':'Reconstruct recorded dead-end plan/state + first original unfit source window; exact deployment token counts, no generation or labels. V4 personal-guidance variant keeps old plan solely to isolate wire size; it is not an admissible new plan.', 'rows':results},indent=2)+'\n')
