"""Reconstruct saved R10 prefixes and measure lossless whole-review sharing.

No generation, labels, experiment writes or source/answer text output. Optional
--tokenize makes network calls only to the approved deployment tokenizer.
"""
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
from dagbt.personal_task import PERSONAL_HISTORY_GUIDANCE
from dagbt.reasoning import Reasoner
from dagbt.resources import personamem_document
from dagbt.token_counting import DeploymentTokenCounter, _digest

ROOT = Path('/Users/mao/projects/dagv2-personamem-v4-reconcile')
RELEASE = Path('/Users/mao/projects/dagv2-personamem-v4')
REPORTS = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
RUN = RELEASE/'outputs/v4_validation_r10'
ATTEMPT = RUN/'personamem/dagbt_residual_memory_v2/attempts/7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0/attempt-001'
BASELINE = 'b160f3ad449796a714c3d45df232b29032262dce'

old_module = types.ModuleType('dagbt._r10_baseline_joint_reading')
old_source = subprocess.check_output(['git','show',BASELINE+':dagbt/joint_reading.py'],cwd=ROOT,text=True)
exec(compile(old_source,'<saved-baseline-joint-reading>','exec'),old_module.__dict__)
OldReader = old_module.JointReader

def load(path):
    return json.loads(path.read_text())

requests = [load(p) for p in (ATTEMPT/'requests').glob('*.json')]
request17 = next(r for r in requests if r['stage']==['joint_read','17'])
request19 = next(r for r in requests if r['stage']==['semantic_compose','19'])
diagnostics = load(ATTEMPT/'fusion_snapshot.json')['diagnostics']
config = load(RUN/'manifest.json')['config']
if config.get('credentials_file') and not Path(config['credentials_file']).is_absolute():
    config['credentials_file'] = str(RELEASE/config['credentials_file'])
settings = {**deepcopy(DEFAULTS),**deepcopy(config['fusion'])}
settings['algorithm_version'] = 'dagbt_residual_memory_v2'
reasoner = Reasoner(None,None,config,settings,Ledger({'llm':24,'json_repairs':6}),lambda e:None)

def unpack(record):
    data = json.loads(record['payload']['messages'][1]['content'])
    columns = data.pop('source_span_columns',None)
    if columns:
        data['source_spans'] = [dict(zip(columns,row)) for row in data['source_spans']]
    documents = data.pop('source_documents',None)
    if documents:
        for source in data['source_spans']:
            metadata = documents[source['doc_id']]
            source['doc_id'] = metadata['doc_id']
            source['time_metadata'] = metadata['time_metadata']
    columns = data.pop('known_observation_columns',None)
    if columns:
        values = data.pop('known_observation_values')
        data['known_observations'] = [dict(zip(columns,[deepcopy(values[v['shared']])
            if isinstance(v,dict) and set(v)=={'shared'} else v for v in row]))
            for row in data['known_observations']]
    if data.get('phase')=='history_evidence':
        restored = {}
        for key,value in data.items():
            restored[key] = value
            if key=='phase':
                restored['personal_task_instruction'] = PERSONAL_HISTORY_GUIDANCE
        data = restored
    return data

def wire(reader,data,operation='joint_read'):
    packed = reader._wire_data(data)
    payload = reasoner._payload(operation,reader._system(packed),packed,reader._schema(data))
    return {**request17['payload'],'messages':payload['messages']}

data17 = unpack(request17)
assert _digest(wire(OldReader,data17)) == _digest(request17['payload']), 'saved call 17 did not roundtrip'
data = deepcopy(data17)
data['known_observations'] = [r for r in unpack(request19)['known_observations'] if r['variable']=='recent_changes']
latest = data['known_observations'][-1]
data['summary_revision_contracts'] = {'recent_changes':{
    'previous_version':3,'eligible_route_ids':[latest['id']],
    'required_source_ids':deepcopy(latest['source_ids'])}}

candidate_ids = diagnostics['candidate_doc_ids']
records = {}
with (RELEASE/'data/personamem/corpus.jsonl').open() as handle:
    for line in handle:
        record = json.loads(line)
        if record['docid'] in candidate_ids:
            records[record['docid']] = record
sources = {}
for doc_id in candidate_ids:
    for source in build_source_spans(doc_id,personamem_document(records[doc_id]),min(400,settings['max_quote_chars'])):
        alias = 's'+str(len(sources)+1)
        sources[alias] = {**deepcopy(source),'source_id':source['id'],'id':alias}
for source in data17['source_spans']:
    assert all(sources[source['id']][k]==v for k,v in source.items()), 'source reconstruction differs'

pending = next(b['unread_source_aliases'] for b in diagnostics['joint_reading']['batches']
               if b.get('status')=='capacity_unavailable' and b['operation']=='joint_read')
required = set()
def collect(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key=='source_ids':
                required.update(item)
            elif key not in ('value','output'):
                collect(item)
    elif isinstance(value,list):
        for item in value:
            collect(item)
collect(data['known_observations'])
collect(data['supported_parents'])
collect(data['supported_task_outputs'])

def prefix(size):
    aliases = list(dict.fromkeys(a for group in pending[:size] for a in group))
    all_aliases = list(dict.fromkeys([*(a for a in sources if a in required),*aliases]))
    selected = deepcopy(data)
    selected['source_spans'] = [{k:sources[a][k] for k in
        ('id','doc_id','start','end','text','source_role','source_message_indices','time_metadata')}
        for a in all_aliases]
    return selected

def ordinary(data):
    return {**data,'repair_scope':{
        'failed':[{'variable':v,'id':'*','feedback':'x'*240,'observation':None} for v in data['variables']],
        'attempt':1,'previous_response_identity':'0'*64}}

def forecast(data):
    feedback = ('whole_value_disagreement: review all scoped drafts and known routes; '
        'compatible fragments need a sourced complete value, genuine conflict stays unresolved')
    return {**data,'repair_scope':{
        'failed':[{'variable':v,'id':'*','feedback':feedback,'observation':None,
            'slot':{'variable':v,'observations':[],'unresolved':[]}} for v in data['variables']],
        'whole_value_reviews':[{'variable':v,'scope':data['requested_scopes'][v],
            'draft_observations':[],'known_observations':[r for r in data['known_observations'] if r['variable']==v],
            'required_source_ids':[s['id'] for s in data['source_spans']]} for v in data['variables']],
        'attempt':1,'previous_response_identity':'0'*64}}

prior = load(REPORTS/'r10_first_case_review.json')
events=[]
counter=DeploymentTokenCounter(config,events.append) if '--tokenize' in sys.argv else None
report={'run':'v4_validation_r10','baseline_commit':BASELINE,
    'scope':'Saved-wire reconstruction; no labels, generation, predictions, option/source text or credentials emitted.',
    'network_tokenization_enabled':bool(counter),'generation_calls':0,
    'saved_call17_wire_roundtrip':True,'context_tokens':settings['context_tokens'],
    'output_reserve_tokens':settings['reasoning_output_tokens'],
    'unknown_draft_reserve_tokens':settings['reasoning_output_tokens'],
    'input_margin_tokens':settings['input_margin'],'fixed_margin_tokens':8,'prefixes':[]}
for name,size,index in [('minimum',1,5),('maximum',len(pending),0)]:
    selected=prefix(size)
    payloads=[selected,ordinary(selected),forecast(selected)]
    old_wires=[wire(OldReader,p,'joint_read' if i==0 else 'joint_read_repair') for i,p in enumerate(payloads)]
    expected=prior['prefix_trials'][index]
    hashes=[_digest(w) for w in old_wires]
    row={'name':name,'prefix_groups':size,'source_spans':len(selected['source_spans']),
        'old_wire_sha256s':hashes,'recorded_wire_sha256s':expected['wire_sha256s'],
        'exact_all_old_hashes_match':hashes==expected['wire_sha256s'],
        'old_forecast_input_tokens':expected['whole_review_forecast_input_tokens'],
        'old_forecast_total_tokens':expected['forecast_total']}
    report['prefixes'].append(row)
    if not row['exact_all_old_hashes_match']:
        continue
    new_wire=wire(JointReader,payloads[2],'joint_read_repair')
    row['new_wire_sha256']=_digest(new_wire)
    packed=JointReader._wire_data(payloads[2])
    row['known_routes_referenced']=sum(len(g.get('known_observation_ids',[])) for g in packed['repair_scope']['whole_value_reviews'])
    if counter:
        result=counter.count(new_wire)
        row['new_forecast_input_tokens']=result['count']
        row['new_forecast_total_tokens']=result['count']+2*settings['reasoning_output_tokens']+settings['input_margin']+8
        row['input_tokens_saved']=row['old_forecast_input_tokens']-result['count']
        row['passes_unchanged_forecast_guard']=row['new_forecast_total_tokens']<=settings['context_tokens']
report['tokenizer_count_calls']=len(events)
report['tokenizer_http_attempts']=sum(e.get('http_attempts',0) for e in events)
report['tokenizer_event_keys']=sorted({k for event in events for k in event})
output=REPORTS/('r10_whole_review_tokenization.json' if counter else 'r10_whole_review_reconstruction.json')
output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
assert all(r['exact_all_old_hashes_match'] for r in report['prefixes']), 'prefix wire hash mismatch; no unsupported token claim'
