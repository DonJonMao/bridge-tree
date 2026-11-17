"""Offline reconstruction of one saved R16 capacity-rejected handoff.

Reads archived model inputs, safe protocol events and structured fact state;
does not read labels or model response text, issue requests, or alter a run.
Only publishes payloads after both original wire hashes match saved events.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import urllib.request


ATTEMPT_KEY = '2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def forbid_network(*args, **kwargs):
    raise AssertionError('Archived handoff reconstruction forbids network')


def extract_options(original_attempt, question, format_question, instruction):
    pattern = re.compile(
        r"Use the user's recorded conversation history to select the best answer to the current request\.\n\n"
        + re.escape('Current request:\n' + question + '\n\nCandidate answers:\n')
        + r'(.*?)' + re.escape('\n\n' + instruction), re.DOTALL)
    found = {}
    paths = []
    for path in sorted((original_attempt / 'requests').glob('*.json')):
        record = json.loads(path.read_text())
        for message in record['payload'].get('messages', []):
            for match in pattern.finditer(message['content']):
                choices = match.group(1)
                sections = re.split(r'(?m)^\(([a-d])\) ', choices)
                if sections[0] != '' or sections[1::2] != list('abcd'):
                    raise ValueError('Public option input cannot be unambiguously decoded')
                options = [value[:-1] if value.endswith('\n') else value for value in sections[2::2]]
                if format_question(question, options) != match.group(0):
                    raise ValueError('Public option reconstruction is not exact')
                found[canonical(options)] = options
                paths.append(path)
    if len(found) != 1:
        raise ValueError('Need one unique set of options from archived input messages')
    return next(iter(found.values())), list(dict.fromkeys(paths))


def reconstruct(root):
    sys.path.insert(0, str(root))
    from dagbt.fact_state import FactState
    from dagbt.model_runtime import prepare_request
    from dagbt.personamem import format_question, ANSWER_INSTRUCTION
    from dagbt.reasoning import Reasoner
    from dagbt.residual_control import ResidualControl

    run = root / 'outputs/v4_validation_r16'
    attempt = run / 'personamem/dagbt_residual_memory_v2/attempts' / ATTEMPT_KEY / 'attempt-001'
    original_attempt = run / 'personamem/original/attempts' / ATTEMPT_KEY / 'attempt-001'
    snapshot_path = attempt / 'fusion_snapshot.json'
    events_path = attempt / 'fusion_events.jsonl'
    diag = json.loads(snapshot_path.read_text())['diagnostics']
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    steps = next(event['dag'] for event in events if event['event'] == 'typed_dag_initialized')
    state = FactState(diag['fact_state']['initial_program'], diag['fact_state']['contract'], steps, 'response')
    state.restore(diag['fact_state'])
    record = diag['joint_reading']['failed_batch_reviews'][0]
    if len(record['failed']) != 1 or record['variable'] != 'current_attitude':
        raise ValueError('Unexpected archived failed scope')
    draft = deepcopy(record['failed'][0]['observation'])
    state.integrate([{**draft, 'variable': 'current_attitude'}], {'current_attitude'})

    by_coordinates = {}
    original_question = None
    request_paths = []
    example = None
    for path in sorted((attempt / 'requests').glob('*.json')):
        saved = json.loads(path.read_text())
        if saved['stage'][0] not in ['joint_read', 'joint_read_repair']:
            continue
        data = json.loads(saved['payload']['messages'][1]['content'])
        if original_question is not None and data['original_question'] != original_question:
            raise ValueError('Archived questions differ')
        original_question = data['original_question']
        request_paths.append(path)
        example = saved
        for item in data['source_spans']:
            source = dict(zip(data['source_span_columns'], item)) if data.get('source_span_columns') else deepcopy(item)
            if data.get('source_documents'):
                source.update(data['source_documents'][source['doc_id']])
            coordinates = source['doc_id'], source['start'], source['end']
            if coordinates in by_coordinates and by_coordinates[coordinates] != source:
                raise ValueError('Source metadata differs across archived inputs')
            by_coordinates[coordinates] = source
    sources = {}
    for span in diag['spans']:
        source = deepcopy(by_coordinates[span['doc_id'], span['start'], span['end']])
        if source['text'] != span['exact_quote']:
            raise ValueError('Structured source quote differs from archived input')
        source['source_id'] = span['id']
        sources[source['id']] = source
    sources = dict(sorted(sources.items(), key=lambda item: int(item[0][1:])))
    options, option_paths = extract_options(original_attempt, original_question, format_question, ANSWER_INSTRUCTION)

    manifest_path = run / 'manifest.json'
    config = deepcopy(json.loads(manifest_path.read_text())['config'])
    config['fusion'] = deepcopy(diag['settings'])
    engine = SimpleNamespace(fact_state=state, steps=steps, s=diag['settings'], q={'question': original_question},
        mapper=SimpleNamespace(sources=sources, source_aliases={value['source_id']:key for key,value in sources.items()}),
        personal_response_selection=True, reader_question=original_question, output_options=options,
        final_node_id='response')
    controller = ResidualControl(engine)
    engine.residual_control = controller
    reader = controller.reader
    reader.current_identity = digest(['mandatory_handoff', 'response', state.revision, state.versions])
    reader.current_terminal_output = True
    data = reader._payload(steps[-1], controller.grounded(steps[-1]), list(state.program['variables']), [], True)
    if len(data['source_spans']) != 39:
        raise ValueError('Reconstructed mandatory closure is not the saved 39 sources')
    repair = {**data, 'repair_scope': {
        'failed': [{'variable': variable, 'id': '*', 'feedback': 'x' * 240, 'observation': None}
                   for variable in data['variables']],
        'attempt': 1, 'previous_response_identity': '0' * 64}}
    reasoner = Reasoner(None, None, config, engine.s, None, forbid_network)
    wires = []
    for operation, content in [('semantic_compose', data), ('semantic_compose_repair', repair)]:
        packed = reader._wire_data(content)
        request = reasoner._payload(operation, reader._system(packed), packed, reader._schema(content))
        _, wire, _ = prepare_request((operation, '13'), example['url'], request, config)
        wires.append(wire)
    rejected_index = next(i for i,event in enumerate(events) if event['event'] == 'joint_support_capacity_rejected')
    expected = [event for event in events[:rejected_index] if event['event'] == 'tokenization_count'][-2:]
    comparisons = [{'operation': operation, 'saved_hash': event['tokenization_wire_sha256'],
                    'reconstructed_hash': digest(wire), 'matches': event['tokenization_wire_sha256'] == digest(wire),
                    'saved_input_tokens': event['count']}
                   for operation,wire,event in zip(['semantic_compose','semantic_compose_repair'],wires,expected)]
    print(json.dumps(comparisons, indent=2))
    if not all(item['matches'] for item in comparisons):
        raise ValueError('Reconstructed wires do not match saved handoff tokenization identity')
    watched = [snapshot_path,events_path,manifest_path,*request_paths,*option_paths,
               root/'dagbt/fact_state.py',root/'dagbt/joint_reading.py',root/'dagbt/residual_control.py',
               root/'dagbt/reasoning.py',root/'dagbt/model_runtime.py',Path(__file__)]
    return {'scope':'Exact saved R16 second-case prospective mandatory handoff, not a generation or current-state retry',
            'network_calls':0,'generation_calls':0,'labels_read':False,'raw_model_response_read':False,
            'source_spans':len(data['source_spans']),'known_routes':len(data['known_observations']),
            'comparisons':comparisons,'artifact_sha256':{str(path):file_hash(path) for path in watched},
            'wires':{'semantic_compose':wires[0],'semantic_compose_repair':wires[1]}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite reconstruction artifact')
    urllib.request.urlopen = forbid_network
    urllib.request.build_opener = forbid_network
    receipt = reconstruct(args.root)
    args.output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print('Saved exact reconstructed handoff:',args.output)


if __name__ == '__main__':
    main()
