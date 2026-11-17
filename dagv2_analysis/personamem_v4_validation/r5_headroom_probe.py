import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from dagbt.budget import Ledger
from dagbt.config import DEFAULTS
from dagbt.joint_reading import JointReader
from dagbt.personal_task import PERSONAL_HISTORY_GUIDANCE
from dagbt.reasoning import Reasoner
from dagbt.token_counting import DeploymentTokenCounter
from dagbt.transport import digest

run = Path('/Users/mao/projects/dagv2-personamem-v4/outputs/v4_validation_r5')
attempt = run/'personamem/dagbt_residual_memory_v2/attempts/7f98d59a44859e0ca7b9b22ca9b60cf2eb5d06090f90ea8cb53d5e2a6f2989b0/attempt-001'
request = json.loads((attempt/'requests/8038d3c2e4fd85f9717b5c59fa3128fe8aca9aaee7cd7be175b75a70b35dd4f2.json').read_text())
config = json.loads((run/'manifest.json').read_text())['config']
settings = {**deepcopy(DEFAULTS), **deepcopy(config['fusion'])}
settings['algorithm_version'] = 'dagbt_residual_memory_v2'
ledger = Ledger({'llm': 24, 'json_repairs': 6})
counter = DeploymentTokenCounter(config, lambda event: None)
reasoner = Reasoner(None, None, config, settings, ledger, lambda event: None)
engine = SimpleNamespace(s=settings, ledger=ledger, reasoner=reasoner)
reader = JointReader(engine, None)

def count(operation, system, data, schema):
    payload = reasoner._payload(operation, system, data, schema)
    wire = {**request['payload'], 'messages': payload['messages']}
    return counter.count(wire)['count']

reasoner.estimate = count
data = json.loads(request['payload']['messages'][1]['content'])
columns = data.pop('source_span_columns', None)
if columns:
    data['source_spans'] = [dict(zip(columns, row)) for row in data['source_spans']]
documents = data.pop('source_documents', None)
if documents:
    for source in data['source_spans']:
        metadata = documents[source['doc_id']]
        source['doc_id'] = metadata['doc_id']
        source['time_metadata'] = metadata['time_metadata']
assert not data.get('known_observations')
saved_instruction = data['personal_task_instruction']
data['personal_task_instruction'] = PERSONAL_HISTORY_GUIDANCE
original = deepcopy(data)
response = json.loads(request['response']['choices'][0]['message']['content'])
event = next(json.loads(line) for line in (attempt/'fusion_events.jsonl').read_text().splitlines()
             if json.loads(line).get('whole_value_reviews'))
groups = event['whole_value_reviews']
feedback = ('whole_value_disagreement: review all scoped drafts and known routes; '
            'compatible fragments need a sourced complete value, genuine conflict stays unresolved')
rows = {(slot['variable'], row['id']): row for slot in response['slots'] for row in slot['observations']}
slots = {slot['variable']: slot for slot in response['slots']}
keys = sorted([*( (v, '*') for v in slots), *rows])

def repair(payload):
    return {**deepcopy(payload), 'repair_scope': {
        'failed': [{'variable': v, 'id': rid, 'feedback': feedback,
                    'observation': deepcopy(rows.get((v, rid))),
                    **({'slot': deepcopy(slots[v])} if rid == '*' else {})} for v, rid in keys],
        'attempt': 1, 'previous_response_identity': digest(response),
        'whole_value_reviews': deepcopy(groups)}}

source_groups = []
spans = data['source_spans']
for index, source in enumerate(spans):
    neighbours = [s['id'] for s in spans[max(0,index-1):index+2] if s['doc_id'] == source['doc_id']]
    source_groups.append(list(dict.fromkeys([source['id'], *neighbours])))

def payload(step, query, variables, aliases, semantic, audit):
    return {**deepcopy(original), 'source_spans': [deepcopy(s) for s in spans if s['id'] in aliases]}

reader._payload = payload
aliases, consumed = reader._fitting_prefix('joint_read', data['task'], data['grounded_subquestion'],
                                          list(data['variables']), source_groups, False, False)
assert consumed
selected = payload(None, None, None, aliases, False, False)
selected_repair = repair(selected)
required = {sid for group in groups for sid in group['required_source_ids']}
selected_ids = {s['id'] for s in selected['source_spans']}
fixed = settings['reasoning_output_tokens'] + settings['input_margin'] + 8
old_repair = repair(original)
old_repair['personal_task_instruction'] = saved_instruction
old_wire = reader._wire_data(old_repair)
old_system = reader._system(old_wire).replace(PERSONAL_HISTORY_GUIDANCE, saved_instruction)
old_repair_count = count('joint_read_repair', old_system, old_wire, reader._schema(old_repair))
assert old_repair_count == 12741
result = {
    'scope': 'Read-only deployment tokenization of saved R5 input and original failed drafts; no generation or evaluation labels.',
    'strict_context_tokens': settings['context_tokens'],
    'output_tokens_unchanged': settings['reasoning_output_tokens'],
    'original_saved_input_tokens': counter.count(request['payload'])['count'],
    'original_repair_input_tokens_reproduced': old_repair_count,
    'original_spans': len(spans),
    'new_guidance_full_input_tokens': reader._estimate('joint_read', original),
    'new_admission_rejects_full_window': not reader._fresh_window_fits('joint_read', original),
    'prefix_groups_consumed': consumed,
    'prefix_spans': len(selected['source_spans']),
    'remaining_unselected_spans': len(spans) - len(selected['source_spans']),
    'prefix_input_tokens': reader._estimate('joint_read', selected),
    'same_failed_draft_repair_input_tokens': reader._estimate('joint_read_repair', selected_repair),
    'same_failed_draft_repair_total_tokens': reader._estimate('joint_read_repair', selected_repair) + fixed,
    'all_original_draft_citations_still_visible': required <= selected_ids,
    'source_text_and_coordinates_unchanged': all(s == next(old for old in spans if old['id']==s['id']) for s in selected['source_spans']),
    'selection_uses_only_initial_input': True,
    'no_post_failure_source_trimming': True,
}
assert result['all_original_draft_citations_still_visible']
assert result['same_failed_draft_repair_total_tokens'] <= settings['context_tokens']
target = Path('/tmp/dagv2_r5_headroom_replay.json')
target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
