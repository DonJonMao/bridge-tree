"""Archived R12 admission replay; only optional tokenizer network calls."""
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
events=[json.loads(l) for l in (ATTEMPT/'fusion_events.jsonl').read_text().splitlines()]
requests=[load(p) for p in (ATTEMPT/'requests').glob('*.json')]
request9=next(r for r in requests if r['stage']==['joint_read','9'])
plan=next(e['plan'] for e in events if e['event']=='plan_frozen')
config=load(RUN/'manifest.json')['config']
if config.get('credentials_file') and not Path(config['credentials_file']).is_absolute():
    config['credentials_file']=str(RELEASE/config['credentials_file'])
settings={**deepcopy(DEFAULTS),**deepcopy(config['fusion'])}
settings['algorithm_version']='dagbt_residual_memory_v2'
ledger=Ledger({'llm':24,'json_repairs':6})
ledger.used['llm']=8
reasoner=Reasoner(None,None,config,settings,ledger,lambda e:None)

def unpack(record):
    data=json.loads(record['payload']['messages'][1]['content'])
    columns=data.pop('source_span_columns',None)
    if columns:data['source_spans']=[dict(zip(columns,row)) for row in data['source_spans']]
    documents=data.pop('source_documents',None)
    if documents:
        for source in data['source_spans']:
            metadata=documents[source['doc_id']]
            source['doc_id']=metadata['doc_id'];source['time_metadata']=metadata['time_metadata']
    assert 'known_observation_columns' not in data
    restored={}
    for key,value in data.items():
        restored[key]=value
        if key=='phase':restored['personal_task_instruction']=PERSONAL_HISTORY_GUIDANCE
    return restored

def wire(data,operation='joint_read',cap=None):
    packed=JointReader._wire_data(data)
    payload=reasoner._payload(operation,JointReader._system(packed),packed,JointReader._schema(data),output_token_cap=cap)
    return prepare_request((operation,'replay'),reasoner.url,payload,config)[1]

data9=unpack(request9)
assert _digest(wire(data9,cap=34))==_digest(request9['payload']),'call9 roundtrip mismatch'
bridges=[e['trace'] for e in events if e['event']=='bridge_step_completed' and e['sequence']<=206]
candidate_ids=list(dict.fromkeys(d for bridge in bridges for d in bridge['local_candidate_ids']))
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
for source in data9['source_spans']:
    assert all(sources[source['id']][k]==v for k,v in source.items()),'source reconstruction differs'

def stable(value):
    if isinstance(value,dict):
        return {k:[sources[s]['source_id'] for s in item] if k=='source_ids'
            else deepcopy(item) if k in ('value','output') else stable(item) for k,item in value.items()}
    if isinstance(value,list):return [stable(item) for item in value]
    return deepcopy(value)

state=FactState(plan['program'],plan['output_contract'],plan['steps'],plan['final_node_id'])
state.routes={row['id']:stable(row) for row in data9['known_observations']}
for variable,contract in data9['summary_revision_contracts'].items():
    state.versions[variable]=contract['previous_version']
state.pending={item['variable'] for item in data9.get('evidence_obligations',[])}
engine=SimpleNamespace(s=settings,ledger=ledger,reasoner=reasoner,event=lambda e:None,
    mapper=SimpleNamespace(sources=sources,source_aliases=source_aliases),steps=plan['steps'])
reader=JointReader(engine,state)
reader.evidence_obligations={item['id']:stable(item) for item in data9.get('evidence_obligations',[])}
state_before=deepcopy(state.public_dict())
obligations_before=deepcopy(reader.evidence_obligations)
template=reader._fresh_structure_response(data9)
assert template is not None,'nonempty floor template rejected reconstructed saved state'
assert state.public_dict()==state_before and reader.evidence_obligations==obligations_before

pending=[]
for alias,source in sources.items():
    if int(alias[1:])>=62 and source['doc_id'] in bridges[-1]['local_candidate_ids']:
        neighbours=[source_aliases.get(source.get(k)) for k in ('previous_span_id','next_span_id')]
        pending.append(list(dict.fromkeys([alias,*[a for a in neighbours if a]])))
required=set()
def collect(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key=='source_ids':required.update(item)
            elif key not in ('value','output'):collect(item)
    elif isinstance(value,list):
        for item in value:collect(item)
for value in (data9['known_observations'],data9['supported_parents'],data9['supported_task_outputs'],data9['evidence_obligations']):collect(value)
def prefix(size):
    aliases=list(dict.fromkeys(a for group in pending[:size] for a in group))
    all_aliases=list(dict.fromkeys([*(a for a in sources if a in required),*aliases]))
    selected=deepcopy(data9)
    selected['source_spans']=[{k:sources[a][k] for k in
        ('id','doc_id','start','end','text','source_role','source_message_indices','time_metadata')} for a in all_aliases]
    return selected
assert _digest(wire(prefix(46),cap=34))==_digest(request9['payload']),'46-group selected window differs'
def ordinary(data):
    return {**data,'repair_scope':{
        'failed':[{'variable':v,'id':'*','feedback':'x'*240,'observation':None} for v in data['variables']],
        'attempt':1,'previous_response_identity':'0'*64}}
saved={e['tokenization_wire_sha256']:e for e in events if e['event']=='tokenization_count' and e.get('status')=='ok'}
prior=[]
for size in range(1,len(pending)+1):
    selected=prefix(size)
    forms=[selected,ordinary(selected),reader._whole_review_forecast(selected)]
    hashes=[_digest(wire(form,'joint_read' if i==0 else 'joint_read_repair')) for i,form in enumerate(forms)]
    counts=[saved[h]['count'] if h in saved else None for h in hashes]
    ordinary_fit=(counts[0] is not None and counts[1] is not None and max(counts[:2])+4096+264<=16384)
    prior.append({'prefix_groups':size,'wire_sha256s':hashes,
        'all_recorded_hashes_match':counts[0] is not None and counts[1] is not None and (not ordinary_fit or counts[2] is not None),
        'ordinary_fit':ordinary_fit,
        'base_input_tokens':counts[0],'ordinary_repair_input_tokens':counts[1],'forecast_input_tokens':counts[2]})
assert all(row['all_recorded_hashes_match'] for row in prior),'a prefix wire has no exact saved count'

new_events=[];lookups=[];counter=None
class ReadOnlyCounts:
    def count_reasoning_tokens(self,stage,url,payload):
        adapted=prepare_request(stage,url,payload,config)[1]
        identity=_digest(adapted)
        if identity in saved:
            lookups.append(identity);return deepcopy(saved[identity])
        if counter is None:raise RuntimeError('new wire count requires --tokenize')
        return counter.count(adapted)
    def get(self,*args,**kwargs):raise AssertionError('Generation prohibited in this replay')

support=template['slots'][0]['observations'][0]
unknown=[o for slot in template['slots'] for o in slot['observations'] if o['stance']=='unknown']
report={'run':'v4_validation_r12','scope':'Archived saved-state replay; optional tokenizer network only; no labels, generation, answer/source text, credentials or experiment writes.',
    'reader_source_sha256':hashlib.sha256((ROOT/'dagbt/joint_reading.py').read_bytes()).hexdigest(),
    'network_tokenization_enabled':'--tokenize' in sys.argv,'generation_calls':0,
    'actual_call9_wire_roundtrip':True,'pending_prefix_groups':len(pending),'all_original_prefix_hashes_matched':True,
    'recorded_prefix_hash_count':sum(sum(row[key] is not None for key in ('base_input_tokens','ordinary_repair_input_tokens','forecast_input_tokens')) for row in prior),
    'old_selected_prefix_groups':46,'old_actual_cap':34,'old_empty_floor':24,
    'template_support_source_count':len(support['source_ids']),
    'template_summary_exact_selected_route':support['summary_revision']['supersedes_route_ids']==state.valid()[2]['event_history'],
    'template_unknown_obligations':len(unknown),'template_unknown_source_counts':[len(o['source_ids']) for o in unknown],
    'template_unresolved_count':len(template['slots'][0]['unresolved']),
    'template_resolves_no_obligations':template['slots'][0]['resolved_obligation_ids']==[],
    'template_is_counted_only_never_a_prompt_or_answer':True,
    'state_and_obligations_unchanged':state.public_dict()==state_before and reader.evidence_obligations==obligations_before,
    'prefixes':prior}
if '--tokenize' in sys.argv:
    counter=DeploymentTokenCounter(config,new_events.append)
    reasoner.calls=ReadOnlyCounts()
    floor=reader._fresh_structure_floor('joint_read',data9,output_token_cap=34)
    report['new_state_preserving_floor_tokens']=floor
    report['old_cap34_rejected']=34<floor
    candidates=[]
    for row in prior:
        base,ordinary_count,forecast=(row[k] for k in ('base_input_tokens','ordinary_repair_input_tokens','forecast_input_tokens'))
        if forecast is None:
            assert not row['ordinary_fit']
            row['passes_nonempty_floor']=False
            continue
        cap=min(4096,16384-base-264,16384-forecast-4096-264)
        row['candidate_cap']=cap
        row['ordinary_fit']=max(base,ordinary_count)+4096+264<=16384
        row['passes_nonempty_floor']=row['ordinary_fit'] and cap>=floor
        if row['passes_nonempty_floor']:candidates.append(row)
    chosen=max(candidates,key=lambda row:row['prefix_groups'])
    selection=reader._adaptive_fresh_cap('joint_read',prefix(chosen['prefix_groups']))
    assert selection is not None and selection['output_token_cap']==chosen['candidate_cap']
    report['largest_admissible_prefix']={'prefix_groups':chosen['prefix_groups'],
        'source_spans':len(prefix(chosen['prefix_groups'])['source_spans']),**selection,
        'actual_capped_wire_sha256':_digest(wire(prefix(chosen['prefix_groups']),cap=selection['output_token_cap']))}
    report['full4096_path_has_admissible_prefix']=any(row['ordinary_fit'] and row['forecast_input_tokens']+8456<=16384 for row in prior)
report['recorded_count_lookups']=len(lookups)
report['new_tokenization_count_calls']=len(new_events)
report['tokenizer_http_attempts']=sum(e.get('http_attempts',0) for e in new_events)
report['tokenizer_successful_http_requests']=sum(e.get('successful_http_requests',0) for e in new_events)
report['tokenizer_cache_hits']=sum(bool(e.get('cache_hit')) for e in new_events)
out=REPORTS/('r12_state_floor_tokenization.json' if counter else 'r12_state_floor_reconstruction.json')
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='prefixes'},ensure_ascii=False,indent=2))
