"""Label-free replay of output loss during bounded Web planner repair."""
from copy import deepcopy
import json

import pytest

from dagbt.engine import legacy_modules
from dagbt.reasoning import ProtocolError
from dagbt.residual import certify_output, expression_type, possible_outputs, references
from dagbt.residual_plan import validate_plan
from dagbt.webwalker_reasoning import (PLANNER_JOINT_RECORD_EXAMPLE,
                                      PLANNER_MULTIHOP_BINDING_EXAMPLE)
from test_webwalker_reasoning import (invoke, plan, reasoner, sent,
                                      tuple_text_trace)


def ordinary_validate(value):
    _, validator, _ = legacy_modules()
    return validate_plan(value, validator.validate_plan)


def diagnostic_value(error, field):
    return json.JSONDecoder().raw_decode(str(error).split(field + '=', 1)[1])[0]


def repaired(first, second, *, match):
    r, calls, ledger, _ = reasoner([json.dumps(first), json.dumps(second)],
                                   max_repairs_per_request=1)
    with pytest.raises(ProtocolError, match=match):
        invoke(r)
    assert len(calls.requests) == ledger.used['llm'] == 2
    assert ledger.used['json_repairs'] == 1
    assert sent(calls, 1)['planner_repair']['previous_draft'] == json.dumps(first)
    assert all(stage[0] == 'planner' for stage, _, _ in calls.requests)


def narrowed_trace():
    first, _, _ = tuple_text_trace()
    second = deepcopy(first)
    second['final_node_id'] = 'agreement_location'
    second['program']['expression'] = {'op': 'var', 'id': 'agreement_location'}
    return first, second


def test_reported_repair_cannot_certify_one_of_two_requested_outputs():
    first, second = narrowed_trace()
    # The previously admitted plan passes the frozen common validator. Web
    # admission must reject it before retrieval or an incomplete certificate.
    assert ordinary_validate(second) == second
    repaired(first, second, match='outside the terminal dependency closure')


def test_initial_plan_cannot_start_with_a_disconnected_answering_branch():
    _, second = narrowed_trace()
    r, calls, ledger, _ = reasoner([json.dumps(second)], max_repairs_per_request=0)
    with pytest.raises(ProtocolError, match='outside the terminal dependency closure'):
        invoke(r)
    assert len(calls.requests) == 1 and ledger.used['json_repairs'] == 0


def test_repair_cannot_hide_output_loss_by_deleting_the_task_and_variable():
    first, second = narrowed_trace()
    second['steps'] = [second['steps'][1]]
    del second['program']['variables']['agreement_date']
    assert ordinary_validate(second) == second
    repaired(first, second, match='removed a recognized output task or expression dependency')


def test_adding_omitted_output_as_retrieval_parent_does_not_expose_its_value():
    first, second = narrowed_trace()
    second['steps'][1]['inputs'] = ['agreement_date']
    assert ordinary_validate(second) == second
    repaired(first, second, match='removed a recognized output task or expression dependency')


def test_parallel_outputs_cannot_be_repaired_into_mutually_exclusive_branches():
    first, second, _ = tuple_text_trace()
    second['program']['expression'] = {'op': 'if', 'args': [
        {'op': 'const', 'value': True}, {'op': 'var', 'id': 'date'}, {'op': 'var', 'id': 'location'}]}
    assert ordinary_validate(second) == second
    repaired(first, second, match='removed a recognized output task or expression dependency')


def test_terminal_graph_parents_do_not_replace_missing_F_dependencies():
    value = plan()
    value['output_contract'] = {k: v for k, v in value['output_contract'].items() if k != 'fields'}
    value['output_contract']['result_type'] = 'entity'
    value['program']['expression'] = {'op': 'var', 'id': 'place'}
    assert ordinary_validate(value) == value
    r, _, _, _ = reasoner([json.dumps(value)], max_repairs_per_request=0)
    with pytest.raises(ProtocolError, match='initial F omits planned task dependencies'):
        invoke(r)


def test_generic_multihop_guidance_example_passes_typed_and_web_admission():
    value = json.loads(PLANNER_MULTIHOP_BINDING_EXAMPLE)
    before = deepcopy(value)
    assert ordinary_validate(value) == value
    assert '"value":' not in PLANNER_MULTIHOP_BINDING_EXAMPLE
    r, calls, ledger, _ = reasoner([json.dumps(value)])
    assert invoke(r) == value == before
    assert len(calls.requests) == ledger.used['llm'] == 1
    assert ledger.used['json_repairs'] == 0


def test_missing_retrieval_binding_is_rejected_with_exact_task_diagnostic():
    value = json.loads(PLANNER_MULTIHOP_BINDING_EXAMPLE)
    del value['program']['variables']['item']
    before = deepcopy(value)
    # The ordinary validator permits graph-only parents; Web coverage must
    # still reject the absent factual binding rather than invent a variable.
    assert ordinary_validate(value) == value
    r, calls, ledger, _ = reasoner([json.dumps(value)], max_repairs_per_request=0)
    with pytest.raises(ProtocolError, match='initial F omits planned task dependencies') as caught:
        invoke(r)
    assert diagnostic_value(caught.value, 'unrepresented_task_ids') == ['item']
    assert diagnostic_value(caught.value, 'nonparticipating_task_ids') == ['item']
    assert value == before
    assert len(calls.requests) == ledger.used['llm'] == 1
    assert ledger.used['json_repairs'] == 0


def test_declared_parent_omitted_from_F_is_still_rejected_with_exact_diagnostic():
    value = json.loads(PLANNER_MULTIHOP_BINDING_EXAMPLE)
    value['steps'][-1]['inputs'] = ['item', 'maker']
    value['program']['task_expressions']['answer'] = {'op': 'var', 'id': 'item'}
    before = deepcopy(value)
    assert ordinary_validate(value) == value
    r, calls, ledger, _ = reasoner([json.dumps(value)], max_repairs_per_request=0)
    with pytest.raises(ProtocolError, match='initial F omits planned task dependencies') as caught:
        invoke(r)
    assert diagnostic_value(caught.value, 'unrepresented_task_ids') == []
    assert diagnostic_value(caught.value, 'nonparticipating_task_ids') == ['maker']
    assert value == before
    assert len(calls.requests) == ledger.used['llm'] == 1
    assert ledger.used['json_repairs'] == 0


def test_disconnected_branches_are_rejected_with_sorted_ids_and_exact_terminal():
    value = json.loads(PLANNER_MULTIHOP_BINDING_EXAMPLE)
    for task in ('zeta_component', 'alpha_component'):
        value['steps'].insert(0, {'question': 'Read the independent ' + task + '.',
            'output_slot': task, 'answer_type': 'fact', 'inputs': [], 'execution': 'retrieval'})
        value['program']['variables'][task] = {'type': 'entity', 'demand': task,
            'open': True, 'scope': {'entity_scope': task, 'time_scope': 'question scope'}}
    before = deepcopy(value)
    assert ordinary_validate(value) == value
    r, calls, ledger, _ = reasoner([json.dumps(value)], max_repairs_per_request=0)
    with pytest.raises(ProtocolError, match='outside the terminal dependency closure') as caught:
        invoke(r)
    assert diagnostic_value(caught.value, 'outside_terminal_task_ids') == [
        'alpha_component', 'zeta_component']
    assert diagnostic_value(caught.value, 'terminal_task_id') == 'answer'
    assert value == before
    assert len(calls.requests) == ledger.used['llm'] == 1
    assert ledger.used['json_repairs'] == 0


def test_deterministic_compose_must_use_all_preserved_output_components():
    first = plan()
    first['output_contract']['result_type'] = 'text'
    first['output_contract'].pop('fields')
    first['program']['expression'] = {'op': 'tuple', 'args': [
        {'op': 'var', 'id': 'time'}, {'op': 'var', 'id': 'place'}]}
    second = deepcopy(first)
    second['program']['variables']['details'] = {'type': 'entity', 'demand': 'details'}
    second['output_contract']['result_type'] = 'entity'
    second['program']['expression'] = {'op': 'var', 'id': 'details'}
    second['program']['task_expressions'] = {'details': {'op': 'var', 'id': 'place'}}
    assert ordinary_validate(second) == second
    repaired(first, second, match='initial F omits planned task dependencies')


def joint_record():
    return {
        'steps': [{'question': 'Find the project sponsor, launch date and duration.',
                   'output_slot': 'project_details', 'answer_type': 'record',
                   'inputs': [], 'execution': 'retrieval'}],
        'final_node_id': 'project_details',
        'output_contract': {'mode': 'value', 'result_type': 'record', 'explanation': 'none',
                            'entity_scope': 'fictional project', 'time_scope': 'documented project',
                            'fields': ['sponsor', 'launch_date', 'duration']},
        'program': {'variables': {
            name: {'type': 'text', 'demand': 'project_details'}
            for name in ('sponsor', 'launch_date', 'duration')},
            'expression': {'op': 'record', 'fields': {
                name: {'op': 'var', 'id': name} for name in ('sponsor', 'launch_date', 'duration')}}},
    }


@pytest.mark.parametrize('delete_variable', [False, True])
def test_same_reading_task_cannot_lose_one_of_its_output_variables(delete_variable):
    first = joint_record()
    first['output_contract']['result_type'] = 'text'
    first['output_contract'].pop('fields')
    second = joint_record()
    second['output_contract']['fields'].remove('launch_date')
    del second['program']['expression']['fields']['launch_date']
    if delete_variable:
        del second['program']['variables']['launch_date']
    assert ordinary_validate(second) == second
    repaired(first, second, match='removed a recognized output task or expression dependency')


def test_record_field_contract_cannot_be_removed_even_with_dependencies_preserved():
    first = joint_record()
    first['program']['expression'] = {'op': 'tuple', 'args': [
        {'op': 'var', 'id': name} for name in ('sponsor', 'launch_date', 'duration')]}
    second = joint_record()
    second['output_contract'].pop('fields')
    assert ordinary_validate(second) == second
    repaired(first, second, match='removed required output record fields')


def test_new_value_record_requires_explicit_fields_without_automatic_rewriting():
    value = joint_record()
    value['output_contract'].pop('fields')
    before = deepcopy(value)
    r, _, _, _ = reasoner([json.dumps(value)], max_repairs_per_request=0)
    with pytest.raises(ProtocolError, match='removed required output record fields|requires explicit'):
        invoke(r)
    assert value == before


def test_generic_compound_record_can_repair_without_inventing_any_answers():
    valid = joint_record()
    first = deepcopy(valid)
    first['program']['expression'] = {'op': 'tuple', 'args': [
        {'op': 'var', 'id': name} for name in ('sponsor', 'launch_date', 'duration')]}
    r, calls, ledger, _ = reasoner([json.dumps(first), json.dumps(valid)])
    result = invoke(r, 'Who sponsored the project, when did it start, and how long did it run?')
    assert result == valid
    assert set(result['output_contract']['fields']) == {'sponsor', 'launch_date', 'duration'}
    assert ledger.used['llm'] == 2 and ledger.used['json_repairs'] == 1
    assert len(calls.requests) == 2
    assert all('value' not in expression for expression in result['program']['expression']['fields'].values())


def test_unit_and_joint_attribute_guidance_adds_no_planner_stage_or_repair():
    valid = joint_record()
    r, calls, ledger, _ = reasoner([json.dumps(valid)])
    assert invoke(r) == valid
    system = calls.requests[0][2]['messages'][0]['content']
    assert 'multiple separately typed variables' in system
    assert 'MUST share ONE retrieval task' in system
    assert 'optional grouping' not in system
    assert 'explicit value and unit fields' in system
    assert "schema's declared unit enum" in system
    assert 'never reference an undeclared var' in system
    assert 'Unknown facts stay unbound' in system
    assert 'eq/ne against const:null' in system
    assert 'never string\nconcatenation' in system
    assert 'A string const has type entity, NOT text' in system
    assert 'Do not move illegal guards into constraints or\ntask_expressions' in system
    assert len(calls.requests) == ledger.used['llm'] == 1
    assert ledger.used['json_repairs'] == 0


def test_complete_fictional_joint_record_example_is_legal_and_keeps_every_fact_unbound():
    value = json.loads(PLANNER_JOINT_RECORD_EXAMPLE)
    assert ordinary_validate(value) == value
    assert len(value['steps']) == 1
    task = value['steps'][0]
    variables = value['program']['variables']
    assert task['execution'] == 'retrieval' and task['inputs'] == []
    assert {decl['type'] for decl in variables.values()} == {'entity', 'text', 'number'}
    assert {decl['demand'] for decl in variables.values()} == {task['output_slot']}
    assert set(value['output_contract']['fields']) == set(variables)
    assert references(value['program']['expression']) == set(variables)
    assert all(expr['op'] == 'var' for expr in value['program']['expression']['fields'].values())
    assert not any('domain' in decl for decl in variables.values())
    assert possible_outputs(value['program'], {})['status'] == 'indeterminate'
    assert possible_outputs(value['program'], {'maker': 'Fictional manufacturer',
                                              'housing_material': 'Fictional material'})['status'] == 'indeterminate'
    r, calls, ledger, _ = reasoner([PLANNER_JOINT_RECORD_EXAMPLE])
    assert invoke(r, task['question']) == value
    assert PLANNER_JOINT_RECORD_EXAMPLE in calls.requests[0][2]['messages'][0]['content']
    assert len(calls.requests) == ledger.used['llm'] == 1
    assert ledger.used['json_repairs'] == 0


def test_shared_retrieval_preserves_boolean_contract_and_legal_conditional_Ft():
    value = {
        'steps': [{'question': 'Check the documented route and condition for the fictional permit.',
                   'output_slot': 'checks', 'answer_type': 'bool', 'inputs': [], 'execution': 'retrieval'}],
        'final_node_id': 'checks',
        'output_contract': {'mode': 'value', 'result_type': 'bool', 'explanation': 'none',
                            'entity_scope': 'fictional permit', 'time_scope': 'documented decision'},
        'program': {'variables': {name: {'type': 'bool', 'demand': 'checks'}
                                  for name in ('route_applies', 'condition_met')},
                    'expression': {'op': 'if', 'args': [
                        {'op': 'var', 'id': 'route_applies'}, {'op': 'var', 'id': 'condition_met'},
                        {'op': 'const', 'value': False}]}}}
    r, calls, ledger, _ = reasoner([json.dumps(value)])
    assert invoke(r) == value
    system = calls.requests[0][2]['messages'][0]['content']
    assert 'only for\na requested multi-field factual answer' in system
    assert 'boolean/one_reason queries retain their\noriginal output contract and legal if/and expressions' in system
    certificate = certify_output(value['program'], {'route_applies': False}, value['output_contract'])
    assert certificate['output'] is False
    assert certificate['eliminated_variables'] == ['condition_met']
    assert len(calls.requests) == ledger.used['llm'] == 1
    assert ledger.used['json_repairs'] == 0


@pytest.mark.parametrize('guard_location', ['expression', 'task_expressions'])
@pytest.mark.parametrize('comparison', ['eq', 'ne'])
def test_null_unknown_guard_remains_rejected_even_when_moved_to_task_expressions(guard_location, comparison):
    value = joint_record()
    guard = {'op': comparison, 'args': [
        {'op': 'var', 'id': 'sponsor'}, {'op': 'const', 'value': None}]}
    if guard_location == 'expression':
        value['program']['expression']['fields']['sponsor'] = guard
    else:
        value = plan()
        value['program']['variables']['checked_time'] = {'type': 'text', 'demand': 'details'}
        value['program']['task_expressions'] = {'checked_time': {'op': 'if', 'args': [
            {'op': comparison, 'args': [
                {'op': 'var', 'id': 'time'}, {'op': 'const', 'value': None}]},
            {'op': 'var', 'id': 'time'}, {'op': 'const', 'value': 'Unknown'}]}}
        value['program']['expression']['fields']['time'] = {'op': 'var', 'id': 'checked_time'}
    raw = json.dumps(value)
    r, calls, ledger, _ = reasoner([raw], max_repairs_per_request=0)
    with pytest.raises(ProtocolError, match='null is not an unknown-test'):
        invoke(r)
    assert json.dumps(value) == raw
    assert r.last_response['raw_output'] == raw
    assert len(calls.requests) == ledger.used['llm'] == 1
    assert ledger.used['json_repairs'] == 0


@pytest.mark.parametrize('expression', [
    {'op': 'eq', 'args': [{'op': 'var', 'id': 'time'}, {'op': 'const', 'value': 'Unknown'}]},
    {'op': 'if', 'args': [{'op': 'const', 'value': True},
                          {'op': 'var', 'id': 'time'}, {'op': 'const', 'value': 'Unknown'}]},
])
def test_entity_string_sentinel_cannot_bypass_public_text_typing(expression):
    value = plan()
    assert expression_type({'op': 'const', 'value': 'Unknown'}, value['program']['variables']) == 'entity'
    value['program']['expression']['fields']['time'] = expression
    raw = json.dumps(value)
    r, calls, ledger, _ = reasoner([raw], max_repairs_per_request=0)
    with pytest.raises(ProtocolError, match='Invalid expression arity or operand types'):
        invoke(r)
    assert r.last_response['raw_output'] == raw
    assert len(calls.requests) == ledger.used['llm'] == 1
    assert ledger.used['json_repairs'] == 0


@pytest.mark.parametrize('operation', ['eq', 'ne'])
@pytest.mark.parametrize('null_operand', [True, False])
def test_null_unknown_test_gets_precise_diagnostic_in_existing_metered_repair(operation, null_operand):
    valid = joint_record()
    invalid = deepcopy(valid)
    invalid['program']['expression'] = {'op': 'if', 'args': [
        {'op': operation, 'args': [
            {'op': 'var', 'id': 'sponsor'},
            {'op': 'const', 'value': None if null_operand else True}]},
        deepcopy(valid['program']['expression']),
        deepcopy(valid['program']['expression'])]}
    r, calls, ledger, _ = reasoner([json.dumps(invalid), json.dumps(valid)])
    assert invoke(r) == valid
    repair = sent(calls, 1)['planner_repair']
    diagnostic = repair['validation_errors'][0]['error']
    assert diagnostic.startswith('Invalid expression arity or operand types: ' + operation)
    assert ('null is not an unknown-test' in diagnostic) is null_operand
    assert repair['previous_draft'] == json.dumps(invalid)
    assert len(calls.requests) == ledger.used['llm'] == 2
    assert ledger.used['json_repairs'] == 1


@pytest.mark.parametrize('operation', ['eq', 'ne'])
def test_type_invalid_null_draft_still_preserves_recognized_retrieval_tasks(operation):
    first = plan()
    original_expression = deepcopy(first['program']['expression'])
    first['program']['expression'] = {'op': 'if', 'args': [
        {'op': operation, 'args': [{'op': 'var', 'id': 'time'}, {'op': 'const', 'value': None}]},
        original_expression, deepcopy(original_expression)]}
    second = plan()
    second['steps'].pop(0)
    second['steps'][-1]['inputs'] = ['place']
    second['steps'][-1]['question'] = 'Combine {place}.'
    second['output_contract']['fields'] = ['place']
    del second['program']['variables']['time']
    del second['program']['expression']['fields']['time']
    assert ordinary_validate(second) == second
    repaired(first, second, match='removed a recognized output task or expression dependency')


def test_type_invalid_null_draft_still_preserves_retrieval_dependency_edges():
    first = plan()
    first['steps'][1]['inputs'] = ['time']
    first['program']['expression']['fields']['time'] = {'op': 'eq', 'args': [
        {'op': 'var', 'id': 'time'}, {'op': 'const', 'value': None}]}
    second = plan()
    # Keep the retrieval question and output components; only its edge changes.
    assert ordinary_validate(second) == second
    repaired(first, second, match='removed a recognized output task or expression dependency')


def test_type_invalid_null_draft_preserves_explicit_record_fields_without_contract_fields():
    first = joint_record()
    first['output_contract'].pop('fields')
    first['program']['expression']['fields']['sponsor'] = {'op': 'eq', 'args': [
        {'op': 'var', 'id': 'sponsor'}, {'op': 'const', 'value': None}]}
    second = joint_record()
    second['program']['expression']['fields']['funder'] = second['program']['expression']['fields'].pop('sponsor')
    second['output_contract']['fields'] = ['funder', 'launch_date', 'duration']
    assert ordinary_validate(second) == second
    repaired(first, second, match='removed required output record fields')


def test_type_invalid_null_draft_preserves_shared_task_output_variables():
    first = joint_record()
    first['program']['expression']['fields']['sponsor'] = {'op': 'eq', 'args': [
        {'op': 'var', 'id': 'sponsor'}, {'op': 'const', 'value': None}]}
    second = joint_record()
    del second['program']['variables']['sponsor']
    del second['program']['expression']['fields']['sponsor']
    second['output_contract']['fields'].remove('sponsor')
    assert ordinary_validate(second) == second
    repaired(first, second, match='removed a recognized output task or expression dependency')


def test_complete_text_terminal_composition_preserves_independent_outputs():
    first, second, valid = tuple_text_trace()
    valid['program']['expression'] = {'op': 'var', 'id': 'answer'}
    r, calls, ledger, _ = reasoner([json.dumps(value) for value in (first, second, valid)])
    assert invoke(r) == valid
    assert len(calls.requests) == 3
    assert ledger.used['json_repairs'] == 2


def test_legal_conditional_branches_can_still_be_eliminated_by_Ft():
    value = {
        'steps': [
            {'question': 'Determine which documented route applies.', 'output_slot': 'choice',
             'answer_type': 'bool', 'inputs': [], 'execution': 'retrieval'},
            {'question': 'Find the value for the first route.', 'output_slot': 'first',
             'answer_type': 'number', 'inputs': [], 'execution': 'retrieval'},
            {'question': 'Find the value for the second route.', 'output_slot': 'second',
             'answer_type': 'number', 'inputs': [], 'execution': 'retrieval'},
            {'question': 'Return the applicable route value.', 'output_slot': 'result',
             'answer_type': 'number', 'inputs': ['choice', 'first', 'second'], 'execution': 'compose'}],
        'final_node_id': 'result',
        'output_contract': {'mode': 'value', 'result_type': 'number', 'explanation': 'none',
                            'entity_scope': 'fictional routes', 'time_scope': 'specified event'},
        'program': {'variables': {name: {'type': kind, 'demand': name}
                                  for name, kind in [('choice', 'bool'), ('first', 'number'), ('second', 'number')]},
                    'expression': {'op': 'if', 'args': [
                        {'op': 'var', 'id': name} for name in ('choice', 'first', 'second')]}}}
    r, calls, ledger, _ = reasoner([json.dumps(value)])
    assert invoke(r) == value
    facts = {'choice': True, 'first': 7}
    outcome = possible_outputs(value['program'], facts)
    certificate = certify_output(value['program'], facts, value['output_contract'])
    assert outcome['status'] == 'determined'
    assert certificate['output'] == 7
    assert certificate['eliminated_variables'] == ['second']
    assert len(calls.requests) == 1 and ledger.used['json_repairs'] == 0

