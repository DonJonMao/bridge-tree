"""R12 archived music window through current real prefix admission.

Saved exact wire counts are reused; --tokenize permits at most four fresh
network tokenization counts. Generation and labels are never accessed.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from dagbt.budget import Ledger
from dagbt.config import DEFAULTS
from dagbt.evidence_spans import build_source_spans
from dagbt.fact_state import FactState
from dagbt.joint_reading import JointReader
from dagbt.model_runtime import prepare_request
from dagbt.personal_task import PERSONAL_HISTORY_GUIDANCE
from dagbt.reasoning import Reasoner
from dagbt.resources import personamem_document
from dagbt.token_counting import DeploymentTokenCounter, _digest

ROOT=Path('/Users/mao/projects/dagv2-personamem-v4-reconcile')
RELEASE=Path('/Users/mao/projects/dagv2-personamem-v4')
REPORTS=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
RUN=RELEASE/'outputs/v4_validation_r12'
ATTEMPT=RUN/'personamem/dagbt_residual_memory_v2/attempts/7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0/attempt-001'
load=lambda path:json.loads(path.read_text())
events=[json.loads(line) for line in (ATTEMPT/'fusion_events.jsonl').read_text().splitlines()]
requests=[load(path) for path in (ATTEMPT/'requests').glob('*.json')]
request=next(item for item in requests if item['stage']==['joint_read','3'])
plan=next(event['plan'] for event in events if event['event']=='plan_frozen')
config=load(RUN/'manifest.json')['config']
if config.get('credentials_file') and not Path(config['credentials_file']).is_absolute():
    config['credentials_file']=str(RELEASE/config['credentials_file'])
settings={**deepcopy(DEFAULTS),**deepcopy(config['fusion'])}
settings['algorithm_version']='dagbt_residual_memory_v2'
ledger=Ledger({'llm':24,'json_repairs':6});ledger.used['llm']=2
reasoner=Reasoner(None,None,config,settings,ledger,lambda event:None)
data=json.loads(request['payload']['messages'][1]['content'])
columns=data.pop('source_span_columns');data['source_spans']=[dict(zip(columns,row)) for row in data['source_spans']]
documents=data.pop('source_documents')
for source in data['source_spans']:
    metadata=documents[source['doc_id']]
    source['doc_id']=metadata['doc_id'];source['time_metadata']=metadata['time_metadata']
restored={}
for key,value in data.items():
    restored[key]=value
    if key=='phase':restored['personal_task_instruction']=PERSONAL_HISTORY_GUIDANCE
data=restored

def wire(selected,operation='joint_read',cap=None):
    packed=JointReader._wire_data(selected)
    payload=reasoner._payload(operation,JointReader._system(packed),packed,JointReader._schema(selected),output_token_cap=cap)
    return prepare_request((operation,'replay'),reasoner.url,payload,config)[1]
assert _digest(wire(data))==_digest(request['payload']),'archived payload roundtrip differs'
bridge=next(event['trace'] for event in events if event['event']=='bridge_step_completed')
candidate_ids=bridge['local_candidate_ids']
records={}
with (RELEASE/'data/personamem/corpus.jsonl').open() as handle:
    for line in handle:
        record=json.loads(line)
        if record['docid'] in candidate_ids:records[record['docid']]=record
sources={};source_aliases={}
for doc_id in candidate_ids:
    for source in build_source_spans(doc_id,personamem_document(records[doc_id]),min(400,settings['max_quote_chars'])):
        alias='s'+str(len(sources)+1)
        sources[alias]={**deepcopy(source),'source_id':source['id'],'id':alias}
        source_aliases[source['id']]=alias
for source in data['source_spans']:
    assert all(sources[source['id']][key]==value for key,value in source.items()),'source reconstruction differs'

def stable(value):
    if isinstance(value,dict):
        return {key:[sources[alias]['source_id'] for alias in item] if key=='source_ids'
            else deepcopy(item) if key in ('value','output') else stable(item) for key,item in value.items()}
    if isinstance(value,list):return [stable(item) for item in value]
    return deepcopy(value)
state=FactState(plan['program'],plan['output_contract'],plan['steps'],plan['final_node_id'])
state.routes={row['id']:stable(row) for row in data['known_observations']}
for variable,contract in data.get('summary_revision_contracts',{}).items():state.versions[variable]=contract['previous_version']
state.pending={item['variable'] for item in data.get('evidence_obligations',[])}
reader_events=[]
engine=SimpleNamespace(s=settings,ledger=ledger,reasoner=reasoner,event=reader_events.append,
    mapper=SimpleNamespace(sources=sources,source_aliases=source_aliases),steps=plan['steps'],
    q={'question':data['original_question']},personal_response_selection=True,
    residual_control=SimpleNamespace(task_projection=lambda parent:deepcopy(data['supported_task_outputs'].get(parent)),
        rules_completion_needed=lambda:data['rules_completion_required']))
reader=JointReader(engine,state)
reader.current_identity=data['request_context']['query_identity']
reader.evidence_obligations={item['id']:stable(item) for item in data.get('evidence_obligations',[])}
pending=[]
for alias,source in sources.items():
    if int(alias[1:])>=54:
        neighbours=[source_aliases.get(source.get(key)) for key in ('previous_span_id','next_span_id')]
        pending.append(list(dict.fromkeys([alias,*[a for a in neighbours if a]])))
step=data['task'];query=data['grounded_subquestion'];variables=list(data['variables'])
old_aliases=list(dict.fromkeys(alias for group in pending[:16] for alias in group))
old_data=reader._payload(step,query,variables,old_aliases)
assert _digest(wire(old_data))==_digest(request['payload']),'real payload does not match archived 16-group window'
assert len(pending)==70
state_before=deepcopy(state.public_dict());obligations_before=deepcopy(reader.evidence_obligations)
saved={event['tokenization_wire_sha256']:event for event in events
    if event['event']=='tokenization_count' and event.get('status')=='ok'}
new_events=[];lookups=[];fresh_count=0
counter=DeploymentTokenCounter(config,new_events.append) if '--tokenize' in sys.argv else None
class ReadOnlyCounts:
    def count_reasoning_tokens(self,stage,url,payload):
        global fresh_count
        adapted=prepare_request(stage,url,payload,config)[1];identity=_digest(adapted)
        if identity in saved:
            lookups.append(identity);return deepcopy(saved[identity])
        if counter is None:raise RuntimeError('new wire requires explicitly enabled network tokenization')
        fresh_count+=1
        if fresh_count>4:raise RuntimeError('fresh network tokenization limit reached')
        return counter.count(adapted)
    def get(self,*args,**kwargs):raise AssertionError('Generation prohibited')
reasoner.calls=ReadOnlyCounts()
if counter is None:
    print(json.dumps({'original_real_payload_exact_match':True,'pending_prefix_groups':len(pending),
        'generation_calls':0,'new_network_tokenization_calls':0}))
    sys.exit(0)
aliases,consumed=reader._fitting_prefix('joint_read',step,query,variables,pending,False,False)
selection=reader._fresh_initial_selection
actual_data=reader._payload(step,query,variables,aliases)
assert selection is not None
assert selection['data_identity']==reader._selection_data_identity(actual_data)
assert state.public_dict()==state_before and reader.evidence_obligations==obligations_before
assert len(reader_events)==1 and reader_events[0]['event']=='joint_fresh_output_cap_selected'
assert not reasoner.requests and ledger.used['llm']==2
report={'run':'archived_v4_validation_r12','scope':'Current production _fitting_prefix and _payload replay; saved exact wire counts plus explicitly authorized network tokenization; zero generation/labels/experiment mutation.',
    'reader_source_sha256':hashlib.sha256((ROOT/'dagbt/joint_reading.py').read_bytes()).hexdigest(),
    'original_real_payload_exact_match':True,
    'previous_full_output_selection':{'prefix_groups':16,'visible_source_count':len(old_data['source_spans']),
        'output_token_cap':4096,'actual_wire_sha256':_digest(request['payload'])},
    'remaining_prefix_groups':len(pending),
    'current_actual_prefix_selection':{'prefix_groups':consumed,'window_source_count':len(aliases),
        'visible_source_count':len(actual_data['source_spans']),**selection,
        'actual_capped_wire_sha256':_digest(wire(actual_data,cap=selection['output_token_cap'])),
        'selection_identity_matches_actual_payload':True},
    'selected_all_remaining_groups':consumed==len(pending),
    'selection_event_count':len(reader_events),'state_and_obligations_unchanged':True,
    'generation_calls':0,'recorded_count_lookups':len(lookups),
    'new_tokenization_count_calls':len(new_events),
    'tokenizer_http_attempts':sum(event.get('http_attempts',0) for event in new_events),
    'tokenizer_successful_http_requests':sum(event.get('successful_http_requests',0) for event in new_events),
    'tokenizer_cache_hits':sum(bool(event.get('cache_hit')) for event in new_events),
    'interpretation':'Current policy actually selects the checked larger capped window; this establishes admission/capacity only, not semantic correctness, generation success, or full-task completion.'}
(REPORTS/'r14_prefix_admission_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
