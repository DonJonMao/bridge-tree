"""Read-only saved-state reconstruction; optional tokenization, never generation."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import types

from dagbt.budget import Ledger
from dagbt.config import DEFAULTS
from dagbt.evidence_spans import build_source_spans
from dagbt.joint_reading import JointReader
from dagbt.model_runtime import prepare_request
from dagbt.personal_task import PERSONAL_HISTORY_GUIDANCE
from dagbt.reasoning import Reasoner
from dagbt.resources import personamem_document
from dagbt.token_counting import DeploymentTokenCounter, _digest

ROOT=Path('/Users/mao/projects/dagv2-personamem-v4-reconcile')
RELEASE=Path('/Users/mao/projects/dagv2-personamem-v4')
REPORTS=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
RUN=RELEASE/'outputs/v4_validation_r11'
ATTEMPT=RUN/'personamem/dagbt_residual_memory_v2/attempts/7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0/attempt-001'
BASELINE='5afd8ab09f7305ea1551ca77d1eb6358f00dddcc'
load=lambda path:json.loads(path.read_text())
old_module=types.ModuleType('dagbt._r11_baseline_joint_reading')
exec(compile(subprocess.check_output(['git','show',BASELINE+':dagbt/joint_reading.py'],cwd=ROOT,text=True),
    '<saved-r11-joint-reading>','exec'),old_module.__dict__)
OldReader=old_module.JointReader
requests=[load(p) for p in (ATTEMPT/'requests').glob('*.json')]
request14=next(r for r in requests if r['stage']==['joint_read','14'])
request22=next(r for r in requests if r['stage']==['semantic_compose','22'])
events=[json.loads(line) for line in (ATTEMPT/'fusion_events.jsonl').read_text().splitlines()]
prior=load(REPORTS/'r11_first_case_review.json')
config=load(RUN/'manifest.json')['config']
if config.get('credentials_file') and not Path(config['credentials_file']).is_absolute():
    config['credentials_file']=str(RELEASE/config['credentials_file'])
settings={**deepcopy(DEFAULTS),**deepcopy(config['fusion'])}
settings['algorithm_version']='dagbt_residual_memory_v2'
ledger=Ledger({'llm':24,'json_repairs':6})
ledger.used['llm']=14
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
    if data.get('phase')=='history_evidence':
        restored={}
        for key,value in data.items():
            restored[key]=value
            if key=='phase':restored['personal_task_instruction']=PERSONAL_HISTORY_GUIDANCE
        data=restored
    return data

def wire(reader,data,operation='joint_read',cap=None):
    packed=reader._wire_data(data)
    payload=reasoner._payload(operation,reader._system(packed),packed,reader._schema(data),output_token_cap=cap)
    return prepare_request((operation,'replay'),reasoner.url,payload,config)[1]

data14=unpack(request14)
assert _digest(wire(OldReader,data14))==_digest(request14['payload']),'call14 wire roundtrip differs'
data=deepcopy(data14)
data['known_observations']=[r for r in unpack(request22)['known_observations'] if r['variable']=='past_events']
latest=data['known_observations'][-1]
data['summary_revision_contracts']={'past_events':{
    'previous_version':3,'eligible_route_ids':[latest['id']],
    'required_source_ids':deepcopy(latest['source_ids'])}}
bridges=[e['trace'] for e in events if e['event']=='bridge_step_completed' and e['sequence']<=233]
candidate_ids=list(dict.fromkeys(d for b in bridges for d in b['local_candidate_ids']))
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
for source in data14['source_spans']:
    assert all(sources[source['id']][k]==v for k,v in source.items()),'source mapper reconstruction differs'
pending=[]
for alias,source in sources.items():
    if int(alias[1:])>=128 and source['doc_id'] in bridges[-1]['local_candidate_ids']:
        neighbours=[source_aliases.get(source.get(k)) for k in ('previous_span_id','next_span_id')]
        pending.append(list(dict.fromkeys([alias,*[a for a in neighbours if a]])))
assert len(pending)==15,'unexpected pending prefix count'
required=set()
def collect(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key=='source_ids':required.update(item)
            elif key not in ('value','output'):collect(item)
    elif isinstance(value,list):
        for item in value:collect(item)
for value in (data['known_observations'],data['supported_parents'],data['supported_task_outputs']):collect(value)
def prefix(size):
    aliases=list(dict.fromkeys(a for group in pending[:size] for a in group))
    all_aliases=list(dict.fromkeys([*(a for a in sources if a in required),*aliases]))
    selected=deepcopy(data)
    selected['source_spans']=[{k:sources[a][k] for k in
        ('id','doc_id','start','end','text','source_role','source_message_indices','time_metadata')} for a in all_aliases]
    return selected
def ordinary(data):
    return {**data,'repair_scope':{
        'failed':[{'variable':v,'id':'*','feedback':'x'*240,'observation':None} for v in data['variables']],
        'attempt':1,'previous_response_identity':'0'*64}}

saved_counts={e['tokenization_wire_sha256']:e for e in events
              if e['event']=='tokenization_count' and e.get('status')=='ok'}
new_events=[];reused=[];counter=None
class ReadOnlyCounts:
    def count_reasoning_tokens(self,stage,url,payload):
        adapted=prepare_request(stage,url,payload,config)[1]
        identity=_digest(adapted)
        if identity in saved_counts:
            reused.append(identity)
            return deepcopy(saved_counts[identity])
        if counter is None:raise RuntimeError('New exact wire requires --tokenize')
        return counter.count(adapted)
    def get(self,*args,**kwargs):
        raise AssertionError('Generation is prohibited in this replay')

report={'run':'v4_validation_r11','baseline_commit':BASELINE,
    'scope':'Read-only archived input reconstruction and optional deployment tokenization; zero labels, generation or experiment writes.',
    'saved_call14_wire_roundtrip':True,'network_tokenization_enabled':'--tokenize' in sys.argv,
    'generation_calls':0,'context_tokens':16384,'repair_output_reserve_tokens':4096,
    'input_margin_tokens':256,'fixed_margin_tokens':8,'prefixes':[]}
selected_payloads=[]
for name,size,index in [('minimum',1,3),('maximum',15,0)]:
    selected=prefix(size);selected_payloads.append(selected)
    payloads=[selected,ordinary(selected),JointReader._whole_review_forecast(selected)]
    hashes=[_digest(wire(OldReader,p,'joint_read' if i==0 else 'joint_read_repair')) for i,p in enumerate(payloads)]
    expected=prior['prefix_trials'][index]
    report['prefixes'].append({'name':name,'prefix_groups':size,'source_spans':len(selected['source_spans']),
        'old_wire_sha256s':hashes,'recorded_wire_sha256s':expected['wire_sha256s'],
        'exact_all_old_hashes_match':hashes==expected['wire_sha256s'],
        'saved_full_output_forecast_total_tokens':expected['forecast_total']})
assert all(r['exact_all_old_hashes_match'] for r in report['prefixes']),json.dumps(report)
if '--tokenize' in sys.argv:
    counter=DeploymentTokenCounter(config,new_events.append)
    reasoner.calls=ReadOnlyCounts()
    engine=types.SimpleNamespace(s=settings,ledger=ledger,reasoner=reasoner,event=lambda e:None)
    reader=JointReader(engine,None)
    for row,selected in zip(report['prefixes'],selected_payloads):
        assert not reader._fresh_window_fits('joint_read',selected)
        selection=reader._adaptive_fresh_cap('joint_read',selected)
        assert selection is not None
        row.update(selection)
        row['actual_capped_initial_wire_sha256']=_digest(wire(JointReader,selected,cap=selection['output_token_cap']))
        row['passes_with_actual_initial_cap']=selection['initial_total_tokens']<=16384 and selection['forecast_total_tokens']<=16384
    report['floor_policy']='Exact count of complete assistant-chat wrapper containing minimum slots JSON; retained wrapper overhead is a policy allowance, not raw completion lower bound or semantic sufficiency guarantee.'
report['recorded_count_lookups']=len(reused)
report['new_tokenization_count_calls']=len(new_events)
report['tokenizer_http_attempts']=sum(e.get('http_attempts',0) for e in new_events)
report['tokenizer_successful_http_requests']=sum(e.get('successful_http_requests',0) for e in new_events)
report['tokenizer_cache_hits']=sum(bool(e.get('cache_hit')) for e in new_events)
out=REPORTS/('r11_adaptive_cap_tokenization.json' if counter else 'r11_adaptive_cap_reconstruction.json')
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
