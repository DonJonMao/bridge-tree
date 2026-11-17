"""Offline exact-response regression for intermediate versus terminal scope.

This is a protocol counterfactual with an explicit predeclared variable scope;
it does not claim to rerun the model or establish semantic answer correctness.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace, ModuleType

BASE = Path(__file__).resolve().parent
ROOT = Path('/Users/mao/projects/dagv2-personamem-a48')
SERVER = BASE.parent / 'a48_v3_server_failure/personamem_a48_v3_smoke'
DIGEST = '2c5c6d1692f65784bc11ccbd23c1fc1e991fc85b13c187b33b9c1398bb6d63f0'
REF = 'fb359b309ba13f01b3e4a0fcc86db44fcb338a8dce7c80581c099f485d07b27c'
OLD_HEAD = 'da64d56250733bc7a87942f6a5389b04a00176bd'
ATTEMPT = SERVER / f'personamem/dagbt_residual_memory_v1/attempts/{DIGEST}/attempt-001'
REQUEST = ATTEMPT / 'requests' / (REF + '.json')
NETWORK_ATTEMPTS = []


def no_network(*args, **kwargs):
    NETWORK_ATTEMPTS.append('blocked network call')
    raise AssertionError('This replay must not use a network')


socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network
sys.path.insert(0, str(ROOT))
from dagbt.evidence_spans import build_source_spans
from dagbt.resources import personamem_document
from dagbt.fact_state import FactState
from dagbt.joint_reading import JointReader
from dagbt.residual import validate_program, ProgramError
from dagbt.residual_plan import validate_plan
from dagbt.residual_control import ResidualControl
from dagbt.engine import legacy_modules
from dagbt.reasoning import ProtocolError


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks = {}
    record = json.loads(REQUEST.read_text())
    raw = record['response']['choices'][0]['message']['content']
    response = json.loads(raw[raw.index('{'):raw.rindex('}') + 1])
    wire = json.loads(record['payload']['messages'][-1]['content'])
    observation = response['slots'][0]['observations'][0]
    original_observation = deepcopy(observation)
    assert response['slots'][0]['variable'] == 'creative_interests'
    assert observation['entity_scope'] == 'user' and observation['time_scope'] == 'past'
    events = [json.loads(line) for line in (ATTEMPT / 'fusion_events.jsonl').open()]
    plan = next(e['plan'] for e in events if e['event'] == 'plan_frozen')
    contract = deepcopy(plan['output_contract'])
    assert contract['entity_scope'] == 'user' and contract['time_scope'] == 'weekend'
    document_ids = {d['doc_id'] for d in wire['source_documents'].values()}
    docs = {}
    corpus = ROOT / 'data/personamem/corpus.jsonl'
    for line in corpus.open():
        item = json.loads(line)
        if item['docid'] in document_ids:
            docs[item['docid']] = personamem_document(item)
    assert set(docs) == document_ids
    original_spans = {docid: build_source_spans(docid, doc, 400) for docid, doc in docs.items()}
    registry = {}
    for source in wire['source_spans']:
        shown = dict(zip(wire['source_span_columns'], source))
        metadata = wire['source_documents'][shown['doc_id']]
        shown['doc_id'] = metadata['doc_id']
        matches = [s for s in original_spans[shown['doc_id']]
                   if all(s[k] == shown[k] for k in ('doc_id', 'start', 'end', 'text', 'source_role', 'source_message_indices'))]
        assert len(matches) == 1
        source = matches[0]
        assert source['time_metadata'] == metadata['time_metadata']
        alias = shown['id']
        registry[alias] = {**deepcopy(source), 'id': alias, 'source_id': source['id']}
    assert len(registry) == 118
    original_registry_digest = digest(registry)
    checks['all_118_visible_sources_match_unchanged_authoritative_corpus'] = True

    def engine():
        return SimpleNamespace(steps=deepcopy(plan['steps']), docs=docs, spans={},
                               s={'max_quote_chars': 400, 'algorithm_version': 'scope_replay_only'},
                               q={'question': wire['original_question']},
                               mapper=SimpleNamespace(sources=deepcopy(registry),
                                   source_aliases={s['source_id']: a for a, s in registry.items()}))

    old_source = subprocess.check_output(['git', 'show', OLD_HEAD + ':dagbt/joint_reading.py'], cwd=ROOT)
    old_module = ModuleType('dagbt._scope_replay_legacy_joint_reading')
    old_module.__package__ = 'dagbt'
    exec(compile(old_source, OLD_HEAD + ':dagbt/joint_reading.py', 'exec'), old_module.__dict__)
    legacy_state = FactState(plan['program'], contract, plan['steps'], plan['final_node_id'])
    legacy = old_module.JointReader(engine(), legacy_state)
    try:
        legacy._observation(deepcopy(observation), 'creative_interests', registry, plan['steps'][0])
    except ProtocolError as exc:
        assert str(exc) == 'Observation scope does not apply to this task'
        legacy_error = str(exc)
    else:
        raise AssertionError('Archived global scope validator must reject the uploaded past observation')
    checks['archived_global_weekend_validator_rejects_exact_past_response'] = True

    corrected = deepcopy(plan['program'])
    corrected['variables']['creative_interests']['scope'] = {'entity_scope': 'user', 'time_scope': 'past'}
    corrected['variables']['suggestion']['scope'] = {'entity_scope': 'user', 'time_scope': 'weekend'}
    validate_program(corrected)
    state = FactState(corrected, contract, plan['steps'], plan['final_node_id'])
    e = engine()
    reader = JointReader(e, state)
    assert state.scope('creative_interests') == {'entity_scope': 'user', 'time_scope': 'past'}
    validated = reader._observation(deepcopy(observation), 'creative_interests', registry, plan['steps'][0])
    state.integrate([validated])
    assert state.valid()[0]['creative_interests'] == observation['value']
    assert validated['time_scope'] == 'past' and validated['entity_scope'] == 'user'
    assert state.contract == contract
    assert original_observation == observation
    assert digest(registry) == original_registry_digest
    checks['predeclared_user_past_accepts_exact_original_response_without_relabeling'] = True
    checks['original_observation_value_reason_and_sources_unchanged'] = True
    checks['terminal_contract_remains_user_weekend'] = True
    payload = reader._payload(plan['steps'][0], wire['grounded_subquestion'], ['creative_interests'], list(registry))
    assert payload['requested_scopes']['creative_interests'] == state.scope('creative_interests')
    assert payload['output_contract'] == contract
    checks['payload_requests_local_scope_and_preserves_terminal_contract'] = True

    failures = {}
    for label, field, value in [('wrong_user', 'entity_scope', 'another_user'), ('wrong_future', 'time_scope', 'future')]:
        changed = {**deepcopy(observation), field: value}
        try:
            reader._observation(changed, 'creative_interests', registry, plan['steps'][0])
        except ProtocolError as exc:
            failures[label] = str(exc)
        else:
            raise AssertionError(label + ' must be rejected')
        checks[label + '_observation_rejected'] = True
    invalid_terminal_program = deepcopy(corrected)
    invalid_terminal_program['variables']['suggestion']['scope']['time_scope'] = 'past'
    try:
        FactState(invalid_terminal_program, contract, plan['steps'], plan['final_node_id'])
    except ProgramError as exc:
        failures['terminal_declaration_mismatch'] = str(exc)
    else:
        raise AssertionError('A terminal declaration may not weaken its frozen output scope')
    checks['terminal_declaration_scope_mismatch_rejected'] = True
    _, repair, _ = legacy_modules()
    corrected_plan = {**deepcopy(plan), 'program': deepcopy(corrected)}
    checked_plan = validate_plan(corrected_plan, repair.validate_plan)
    assert checked_plan == corrected_plan
    checks['corrected_predeclared_scope_plan_passes_real_planner_validator'] = True
    invalid_plan = {**deepcopy(plan), 'program': invalid_terminal_program}
    try:
        validate_plan(invalid_plan, repair.validate_plan)
    except ProtocolError as exc:
        failures['planner_terminal_scope_mismatch'] = str(exc)
    else:
        raise AssertionError('Planner must reject terminal scope mismatch before retrieval')
    checks['planner_terminal_scope_mismatch_rejected'] = True
    terminal_row = {**deepcopy(observation), 'value': 'An example weekend activity', 'time_scope': 'past'}
    try:
        reader._observation(terminal_row, 'suggestion', registry, plan['steps'][-1], require_grounding=False)
    except ProtocolError as exc:
        failures['terminal_observation_mismatch'] = str(exc)
    else:
        raise AssertionError('Terminal observation with past scope must still be rejected')
    checks['terminal_observation_scope_mismatch_rejected'] = True
    before_state = deepcopy(state.public_dict())
    try:
        state.integrate([{**deepcopy(validated), 'time_scope': 'future'}])
    except ProgramError as exc:
        failures['direct_state_integration_mismatch'] = str(exc)
    else:
        raise AssertionError('FactState must independently enforce its variable scope')
    assert state.public_dict() == before_state
    checks['wrong_scope_direct_state_integration_rejected_without_mutation'] = True
    tampered = deepcopy(before_state)
    tampered['routes'][0]['time_scope'] = 'future'
    try:
        state.restore(tampered)
    except ProgramError as exc:
        failures['restored_route_scope_mismatch'] = str(exc)
    else:
        raise AssertionError('Resume must reject a route with altered scope')
    assert state.public_dict() == before_state
    checks['wrong_scope_restored_route_rejected_without_mutation'] = True
    tampered = deepcopy(before_state)
    tampered['program']['variables']['creative_interests']['scope']['time_scope'] = 'future'
    try:
        state.restore(tampered)
    except ProgramError as exc:
        failures['restored_variable_scope_mismatch'] = str(exc)
    else:
        raise AssertionError('Resume must not change a predeclared variable scope')
    assert state.public_dict() == before_state
    checks['restored_predeclared_scope_change_rejected_without_mutation'] = True
    fresh = FactState(corrected, contract, plan['steps'], plan['final_node_id'])
    fresh.restore(before_state)
    assert fresh.public_dict() == before_state
    checks['valid_scoped_state_roundtrip_preserves_original_fact_and_contract'] = True
    current_route = next(iter(fresh.routes.values()))
    fresh.routes['injected_old_scope'] = {**deepcopy(current_route), 'id': 'injected_old_scope', 'time_scope': 'future'}
    fresh.routes['injected_stale_derivation'] = {
        **deepcopy(current_route), 'id': 'injected_stale_derivation',
        'binding_derivation': {'program_revision': fresh.revision - 1}}
    e.fact_state = fresh
    e.final_node_id = plan['final_node_id']
    e.s['max_alternatives'] = 2
    e.nodes = [{'id': s['output_slot']} for s in e.steps]
    e.node_map = lambda: {n['id']: n for n in e.nodes}
    e.compile = lambda: None
    controller = ResidualControl(e)
    controller.sync_nodes()
    node = e.node_map()['creative_interests']
    assert node['variable_scopes'] == {'creative_interests': {'entity_scope': 'user', 'time_scope': 'past'}}
    assert len(node['alternatives']) == 1
    assert node['alternatives'][0]['applicable_scope'] == {'entity_scope': 'user', 'time_scope': 'past'}
    emitted_routes = {rid for a in node['alternatives'] for ids in a['fact_route_ids'].values() for rid in ids}
    assert 'injected_old_scope' not in emitted_routes and 'injected_stale_derivation' not in emitted_routes
    checks['node_scope_metadata_preserves_past_instead_of_terminal_weekend'] = True
    checks['old_scope_and_revision_stale_routes_excluded_from_node_alternatives'] = True
    assert not NETWORK_ATTEMPTS
    report = {
        'passed': all(checks.values()), 'checks': checks, 'no_network_calls': True,
        'blocked_network_attempts': len(NETWORK_ATTEMPTS), 'evaluation_labels_read': False,
        'scores_summary_comparisons_read': False,
        'original_request_path': str(REQUEST), 'original_request_sha256': sha(REQUEST),
        'original_raw_response_sha256': hashlib.sha256(raw.encode()).hexdigest(),
        'original_parsed_observation_sha256': digest(original_observation),
        'original_source_wire_sha256': digest(wire['source_spans']),
        'authoritative_corpus_sha256': sha(corpus), 'visible_source_count': len(registry),
        'original_source_registry_sha256': original_registry_digest,
        'archived_code_head': OLD_HEAD, 'archived_joint_reading_sha256': hashlib.sha256(old_source).hexdigest(),
        'tested_source_hashes': {name: sha(ROOT / 'dagbt' / name) for name in ('joint_reading.py', 'fact_state.py', 'residual.py', 'residual_plan.py', 'residual_control.py')},
        'legacy_validation_error': legacy_error, 'negative_validation_errors': failures,
        'scope_declaration_change': {v: d['scope'] for v, d in corrected['variables'].items() if 'scope' in d},
        'terminal_contract': contract,
        'scope': 'Deterministic offline observation validator replay using exact uploaded first response and authoritative original sources; explicit predeclared scope counterfactual, not model-generated corrected planner or full-run accuracy.',
        'semantic_limit': 'Acceptance proves protocol/source-coordinate compatibility, not that every value is semantically correct or current. No calendar date is inferred from observation indices.',
    }
    destination = BASE / 'scope_response_replay.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'checks': len(checks), 'report': str(destination), 'sha256': sha(destination)}))


if __name__ == '__main__':
    main()
