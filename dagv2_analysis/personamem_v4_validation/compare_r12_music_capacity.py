"""Optional earlier-window capacity comparison; no change to prefix policy."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

from dagbt.fact_state import FactState
from dagbt.joint_reading import JointReader
from dagbt.model_runtime import prepare_request
from dagbt.token_counting import DeploymentTokenCounter, _digest

root=Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation')
arguments=sys.argv
sys.argv=[str(root/'measure_r12_state_floor.py')]
with contextlib.redirect_stdout(io.StringIO()):
    prior=runpy.run_path(sys.argv[0])
sys.argv=arguments
request=next(r for r in prior['requests'] if r['stage']==['joint_read','3'])
data=prior['unpack'](request)
wire=prior['wire'];sources=prior['sources'];source_aliases=prior['source_aliases']
reasoner=prior['reasoner'];settings=prior['settings'];config=prior['config'];plan=prior['plan'];saved=prior['saved']
assert _digest(wire(data))==_digest(request['payload'])
state=FactState(plan['program'],plan['output_contract'],plan['steps'],plan['final_node_id'])
state.routes={row['id']:prior['stable'](row) for row in data['known_observations']}
for variable,contract in data.get('summary_revision_contracts',{}).items():
    state.versions[variable]=contract['previous_version']
engine=SimpleNamespace(s=settings,ledger=prior['ledger'],reasoner=reasoner,event=lambda e:None,
    mapper=SimpleNamespace(sources=sources,source_aliases=source_aliases),steps=plan['steps'])
reader=JointReader(engine,state)
reader.evidence_obligations={item['id']:prior['stable'](item) for item in data.get('evidence_obligations',[])}
assert reader._fresh_structure_response(data) is not None
pending=[]
for alias,source in sources.items():
    if int(alias[1:])>=54 and source['doc_id'] in prior['bridges'][0]['local_candidate_ids']:
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
for value in (data['known_observations'],data['supported_parents'],data['supported_task_outputs'],data.get('evidence_obligations',[])):
    collect(value)
def prefix(size):
    aliases=list(dict.fromkeys(a for group in pending[:size] for a in group))
    all_aliases=list(dict.fromkeys([*(a for a in sources if a in required),*aliases]))
    selected=deepcopy(data)
    selected['source_spans']=[{k:sources[a][k] for k in
        ('id','doc_id','start','end','text','source_role','source_message_indices','time_metadata')} for a in all_aliases]
    return selected
assert _digest(wire(prefix(16)))==_digest(request['payload']),'original full-output selection differs'
recorded=[]
for size in range(1,len(pending)+1):
    selected=prefix(size)
    forms=[selected,prior['ordinary'](selected),reader._whole_review_forecast(selected)]
    hashes=[_digest(wire(form,'joint_read' if i==0 else 'joint_read_repair')) for i,form in enumerate(forms)]
    if not all(h in saved for h in hashes):continue
    base,ordinary,forecast=[saved[h]['count'] for h in hashes]
    recorded.append({'prefix_groups':size,'wire_sha256s':hashes,'base_input_tokens':base,
        'ordinary_repair_input_tokens':ordinary,'forecast_input_tokens':forecast,
        'ordinary_fit':max(base,ordinary)+4360<=16384,
        'full_output_forecast_fit':forecast+8456<=16384,
        'candidate_cap':min(4096,16384-base-264,16384-forecast-4360)})
events=[];lookups=[]
counter=DeploymentTokenCounter(config,events.append)
class ReadOnlyCounts:
    def count_reasoning_tokens(self,stage,url,payload):
        adapted=prepare_request(stage,url,payload,config)[1]
        identity=_digest(adapted)
        if identity in saved:lookups.append(identity);return deepcopy(saved[identity])
        return counter.count(adapted)
    def get(self,*args,**kwargs):raise AssertionError('Generation prohibited')
reasoner.calls=ReadOnlyCounts()
floor=reader._fresh_structure_floor('joint_read',data,output_token_cap=4096)
candidates=[row for row in recorded if row['prefix_groups']>16 and row['ordinary_fit'] and row['candidate_cap']>=floor]
chosen=max(candidates,key=lambda row:row['prefix_groups'])
selection=reader._adaptive_fresh_cap('joint_read',prefix(chosen['prefix_groups']))
assert selection is not None
report={'run':'v4_validation_r12','scope':'Read-only earlier music_prefs window comparison using saved matching wire hashes and new deployment tokenization only; zero generation or labels.',
    'original_call3_wire_roundtrip':True,'policy_unchanged':'Full 4096 output prefix still wins; larger adaptive example is a capacity comparison only.',
    'remaining_prefix_groups':len(pending),'recorded_prefixes_with_all_three_hashes':len(recorded),
    'nonempty_state_preserving_floor_tokens':floor,
    'actual_full_output_selection':{'prefix_groups':16,'source_spans':len(data['source_spans']),
        'output_token_cap':4096,**{k:v for k,v in next(row for row in recorded if row['prefix_groups']==16).items() if k!='prefix_groups'}},
    'larger_recorded_adaptive_example':{'prefix_groups':chosen['prefix_groups'],
        'source_spans':len(prefix(chosen['prefix_groups'])['source_spans']),**selection,
        'all_three_original_wire_sha256s':chosen['wire_sha256s']},
    'largest_prefix_claimed':False,
    'interpretation':'A larger recorded window has sufficient measured output capacity to preserve the selected current fact. This is not a semantic quality or completion-within-24-calls guarantee; full-output-first selection was not changed.',
    'generation_calls':0,'new_tokenization_count_calls':len(events),
    'tokenizer_http_attempts':sum(e.get('http_attempts',0) for e in events),
    'tokenizer_cache_hits':sum(bool(e.get('cache_hit')) for e in events),'recorded_count_lookups':len(lookups)}
(root/'r12_music_capacity_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
