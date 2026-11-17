"""Web-only, bounded repairs for the initial typed DAG planner.

The common reasoner owns retries, admission and accounting. This adapter adds
structural output-coverage admission and prepares repairs from actual drafts.
"""
from collections.abc import Mapping
from copy import deepcopy
import json
import re

from .reasoning import ProtocolError, Reasoner
from .residual import references, validate_program


PLANNER_JOINT_RECORD_EXAMPLE = '''{
  "steps": [{
    "question": "Identify the maker, housing material, and catalogue year of the fictional Lumen C3 sensor.",
    "output_slot": "sensor_details", "answer_type": "record",
    "inputs": [], "execution": "retrieval"
  }],
  "final_node_id": "sensor_details",
  "output_contract": {
    "mode": "value", "result_type": "record", "explanation": "none",
    "entity_scope": "fictional Lumen C3 sensor", "time_scope": "catalogue specification",
    "fields": ["maker", "housing_material", "catalogue_year"]
  },
  "program": {
    "variables": {
      "maker": {
        "type": "entity", "demand": "sensor_details", "open": true,
        "scope": {"entity_scope": "fictional Lumen C3 sensor", "time_scope": "catalogue specification"}
      },
      "housing_material": {
        "type": "text", "demand": "sensor_details", "open": true,
        "scope": {"entity_scope": "fictional Lumen C3 sensor", "time_scope": "catalogue specification"}
      },
      "catalogue_year": {
        "type": "number", "demand": "sensor_details",
        "scope": {"entity_scope": "fictional Lumen C3 sensor", "time_scope": "catalogue specification"}
      }
    },
    "expression": {"op": "record", "fields": {
      "maker": {"op": "var", "id": "maker"},
      "housing_material": {"op": "var", "id": "housing_material"},
      "catalogue_year": {"op": "var", "id": "catalogue_year"}
    }},
    "rules_complete": true
  }
}'''


PLANNER_MULTIHOP_BINDING_EXAMPLE = '''{
  "steps": [
    {
      "question": "Identify the unknown item described in the original question.",
      "output_slot": "item",
      "answer_type": "fact",
      "inputs": [],
      "execution": "retrieval"
    },
    {
      "question": "Identify the maker of {item}.",
      "output_slot": "maker",
      "answer_type": "fact",
      "inputs": [
        "item"
      ],
      "execution": "retrieval"
    },
    {
      "question": "Return the identified maker.",
      "output_slot": "answer",
      "answer_type": "fact",
      "inputs": [
        "maker"
      ],
      "execution": "compose"
    }
  ],
  "final_node_id": "answer",
  "output_contract": {
    "mode": "value",
    "result_type": "entity",
    "entity_scope": "maker of the item described in the question",
    "time_scope": "question scope",
    "explanation": "none"
  },
  "program": {
    "variables": {
      "item": {
        "type": "entity",
        "demand": "item",
        "open": true,
        "scope": {
          "entity_scope": "item described in the question",
          "time_scope": "question scope"
        }
      },
      "maker": {
        "type": "entity",
        "demand": "maker",
        "open": true,
        "scope": {
          "entity_scope": "maker of the item described in the question",
          "time_scope": "question scope"
        }
      },
      "answer": {
        "type": "entity",
        "demand": "answer",
        "open": true,
        "scope": {
          "entity_scope": "maker of the item described in the question",
          "time_scope": "question scope"
        }
      }
    },
    "expression": {
      "op": "var",
      "id": "answer"
    },
    "task_expressions": {
      "answer": {
        "op": "var",
        "id": "maker"
      }
    },
    "rules_complete": true
  }
}'''


PLANNER_TYPE_GUIDANCE = '''
Type consistency is structural: a var expression has its variable declaration's
type; record produces record; tuple produces set (a JSON array), never string
concatenation; comparisons and and/or/not produce bool. If branches must have
the same result type. Unknown facts stay unbound; the partial evaluator handles
unknowns. Do not test unknownness with eq/ne against const:null, supply an
"Unknown" string fallback, or use an if branch that omits requested fields.
A string const has type entity, NOT text. Comparing a text variable to a string
const such as "Unknown" is invalid, as is combining a text branch with that
entity-valued fallback. Missing factual input is absence of a binding, never
null or a sentinel value to test. Do not move illegal guards into constraints or
task_expressions: the same typing rules apply there. Direct fact records need
only an unconditional record of unbound var references, with no availability
checks; the controller waits for supported bindings before publishing.
The complete expression must match output_contract.result_type. Preserve every
requested output field, dependency and scope when correcting a plan; do not
coerce values or narrow the user's requested output to satisfy a type check.
Every initial task must lead to the designated terminal and participate in F,
including every conditional branch before evidence permits partial evaluation.
Every retrieval task must expose at least one typed UNBOUND program.variables
entry whose demand is that task's exact output_slot. Listing a task only in
steps or inputs does not create its output variable. Declare intermediate
variables as well as the final variable, with each variable's own scope. A
semantic compose consumes its declared parent variables; a deterministic
compose must reference the needed variables in its task_expressions. Repair
missing bindings without guessing values or deleting the planned work.
Independent requested facts must converge: use a record with explicit required
output_contract.fields, or a terminal compose task that consumes all of them and
answers the ENTIRE original question. Do not select one independent leaf as the
complete answer. A set is appropriate for a homogeneous requested list, not for
hiding distinct requested fields. A value-mode record MUST declare its fields.
Independent attributes of the SAME already-known entity at the SAME entity/time
scope MUST share ONE retrieval task with multiple separately typed variables
whose demand is that task. Use a record exposing every requested field only for
a requested multi-field factual answer; boolean/one_reason queries retain their
original output contract and legal if/and expressions even when retrieval is
shared. Split
retrieval tasks when an actual grounding/reasoning dependency or different
requested scopes requires separation; do not invent dependencies to separate
otherwise independent attributes. Keep genuine DAG input dependencies, all
foreseeable downstream tasks with unbound inputs, and genuine conditional
branches intact before evidence allows F_t to eliminate unnecessary work.
For a quantity with a unit, prefer text preserving the complete quantity, or a
sourced record with explicit value and unit fields. If numerical operations are
required, a numeric declaration's unit MUST use the schema's declared unit enum;
never invent another unit code or silently discard a unit to fit a bare number.
If an expression references a separate unit variable, declare that variable's
type, demand and scope in the initial program; never reference an undeclared var.
During structural repair preserve recognized retrieval questions and output
components. Slot renaming is allowed with corresponding dependency updates; do
not delete tasks, expression inputs or record fields to make validation pass.
Complete legal initial-plan example for the fictional question "Identify the
maker, housing material, and catalogue year of the fictional Lumen C3 sensor."
All three factual values below are UNBOUND; no answer is supplied or guessed.
''' + PLANNER_JOINT_RECORD_EXAMPLE + '''
This example demonstrates types and dependencies only. Use the current
question's own entities, requested attributes, scopes and genuine dependencies.
A generic multi-hop binding example follows. It supplies no facts or values:
the item and maker remain unbound until original-source reading. The final
compose only copies the already supported maker through a typed expression.
''' + PLANNER_MULTIHOP_BINDING_EXAMPLE + '''
Use this wiring pattern only when the original question has these dependencies;
do not add an item/maker task or change the requested output to fit the example.
'''


def _has_null_comparison(expression, operation):
    """Diagnose a rejected draft without changing its expression or admission."""
    if isinstance(expression, Mapping):
        args = expression.get('args')
        if expression.get('op') == operation and isinstance(args, list) and any(
                isinstance(arg, Mapping) and arg.get('op') == 'const'
                and 'value' in arg and arg['value'] is None
                for arg in args):
            return True
        return any(_has_null_comparison(value, operation) for value in expression.values())
    if isinstance(expression, list):
        return any(_has_null_comparison(value, operation) for value in expression)
    return False


def _task_structure(value):
    """Read only a well-formed draft DAG; a failed draft is never evidence."""
    if not isinstance(value, Mapping) or not isinstance(value.get('steps'), list):
        return None
    tasks = {}
    for step in value['steps']:
        if (not isinstance(step, Mapping) or not isinstance(step.get('output_slot'), str)
                or not isinstance(step.get('question'), str) or not step['question'].strip()
                or step.get('execution') not in ('retrieval', 'compose')
                or not isinstance(step.get('inputs'), list)
                or any(not isinstance(parent, str) for parent in step['inputs'])
                or step['output_slot'] in tasks):
            return None
        tasks[step['output_slot']] = step
    if not tasks or value.get('final_node_id') not in tasks:
        return None
    keys, visiting = {}, set()

    def key(node):
        if node in visiting or node not in tasks:
            raise ValueError('Cyclic or absent draft task')
        if node not in keys:
            visiting.add(node)
            step = tasks[node]
            for parent in step['inputs']:
                key(parent)
            # A formal slot rename must not change a dependent task's identity.
            question = re.sub(r'\{([^{}]+)\}', lambda match: '{' + key(match[1]) + '}',
                              ' '.join(step['question'].split()))
            keys[node] = json.dumps([step['execution'], question], ensure_ascii=False)
            visiting.remove(node)
        return keys[node]

    try:
        for node in tasks:
            key(node)
    except (KeyError, ValueError):
        return None
    return tasks, keys


def _result_variables(program, tasks, initial):
    """Follow F, not just DAG edges attached to an otherwise unused terminal.

    A semantic task consumes its declared parents. A deterministic task uses
    only its actual expression; unused declared parents cannot fake coverage.
    All if/and/or branches remain present here. Ft may prune them after binding.
    """
    variables = program['variables']
    by_task = {node: {v for v, decl in variables.items() if decl['demand'] == node}
               for node in tasks}
    seen = set()

    def visit(variable):
        if variable in seen:
            return
        seen.add(variable)
        if variable in program.get('task_expressions', {}):
            parents = references(program['task_expressions'][variable])
        else:
            parents = set().union(*(by_task[p] for p in tasks[variables[variable]['demand']]['inputs']))
        for parent in parents:
            visit(parent)

    for variable in initial:
        visit(variable)
    return seen


def _output_variables(program, tasks):
    """Expose requested output components, rather than every grounding input.

    Making an omitted output a parent of another retrieval does not expose it in
    that retrieval's value. An explicit terminal composition can combine its
    inputs; a deterministic composition must actually reference the components.
    """
    variables, seen, outputs = program['variables'], set(), set()
    def visit(variable):
        if variable in seen:
            return
        seen.add(variable)
        task = tasks[variables[variable]['demand']]
        if variable in program.get('task_expressions', {}):
            parents = references(program['task_expressions'][variable])
        elif task['execution'] == 'compose':
            parents = {v for v, declaration in variables.items() if declaration['demand'] in task['inputs']}
        else:
            outputs.add(variable)
            parents = set()
        for parent in parents:
            visit(parent)
    for variable in references(program['expression']):
        visit(variable)
    return outputs


def _guaranteed_output_variables(program, tasks, expression):
    """A product's components cannot be conserved as mutually exclusive outputs."""
    op = expression['op']
    if op == 'if':
        return (_guaranteed_output_variables(program, tasks, expression['args'][1]) &
                _guaranteed_output_variables(program, tasks, expression['args'][2]))
    if op == 'var':
        variable = expression['id']
        if variable in program.get('task_expressions', {}):
            return _guaranteed_output_variables(program, tasks, program['task_expressions'][variable])
        task = tasks[program['variables'][variable]['demand']]
        if task['execution'] != 'compose':
            return {variable}
        return set().union(*(_guaranteed_output_variables(program, tasks, {'op': 'var', 'id': v})
            for v, declaration in program['variables'].items() if declaration['demand'] in task['inputs']))
    children = (expression['fields'].values() if op in ('record', 'failures', 'one_reason')
                else expression.get('args', []))
    return set().union(*(_guaranteed_output_variables(program, tasks, child) for child in children))


class _PlannerCoverage:
    """Conserve structurally recognized work within one bounded planner call.

    These anchors describe the model's own initial interpretation, not inferred
    facts or a proof of natural-language completeness. Repair may fix types and
    wiring, but cannot silently remove recognized output components. A semantic
    rephrasing that cannot be aligned deterministically fails conservatively.
    """
    def __init__(self):
        self.tasks = set()
        self.edges = set()
        self.outputs = set()
        self.product_outputs = set()
        self.fields = set()

    @staticmethod
    def snapshot(value):
        structure = _task_structure(value)
        if structure is None or not isinstance(value.get('output_contract'), Mapping):
            return None
        tasks, keys = structure
        contract_fields = value['output_contract'].get('fields', [])
        fields = set(contract_fields) if (isinstance(contract_fields, list)
            and all(isinstance(field, str) and field for field in contract_fields)) else set()
        snapshot = {
            'tasks': {keys[node] for node, step in tasks.items() if step['execution'] == 'retrieval'},
            'edges': {(keys[parent], keys[node]) for node, step in tasks.items()
                      for parent in step['inputs'] if step['execution'] == 'retrieval'},
            'outputs': set(), 'guaranteed_outputs': set(), 'product_outputs': set(),
            'fields': fields, 'dag': tasks, 'program': None}
        # Type-invalid drafts still express structural work that repairs must
        # conserve. They never become an admitted program or evidence.
        program = value.get('program')
        try:
            program = validate_program(program)
            snapshot['program'] = program
        except (KeyError, TypeError, ValueError, RecursionError):
            pass
        if not isinstance(program, Mapping):
            return snapshot
        expression = program.get('expression')
        if isinstance(expression, Mapping) and expression.get('op') == 'record':
            raw_fields = expression.get('fields')
            if isinstance(raw_fields, Mapping):
                fields |= {name for name in raw_fields if isinstance(name, str) and name}
        if not isinstance(program.get('variables'), Mapping):
            return snapshot
        declarations = program['variables']
        if any(not isinstance(v, str) or not isinstance(decl, Mapping)
               or not isinstance(decl.get('demand'), str) or decl['demand'] not in tasks
               for v, decl in declarations.items()):
            return snapshot
        try:
            output_components = _output_variables(program, tasks)
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, RecursionError):
            output_components = set()
        try:
            guaranteed = _guaranteed_output_variables(program, tasks, expression)
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, RecursionError):
            guaranteed = set()
        counts = {node: sum(decl['demand'] == node for decl in declarations.values()) for node in tasks}
        # Distinct variables sharing a task cannot be conserved by retaining
        # only the task. Their stable variable IDs are part of the output anchor.
        def component_keys(variables):
            return {(keys[declarations[v]['demand']], v if counts[declarations[v]['demand']] > 1 else None)
                    for v in variables}
        outputs, guaranteed_outputs = component_keys(output_components), component_keys(guaranteed)
        snapshot.update(outputs=outputs, guaranteed_outputs=guaranteed_outputs,
            product_outputs=(guaranteed_outputs if isinstance(expression, Mapping)
                             and expression.get('op') in ('record', 'tuple') else set()))
        return snapshot

    def remember(self, snapshot):
        if snapshot is not None:
            self.tasks |= snapshot['tasks']
            self.edges |= snapshot['edges']
            self.outputs |= snapshot['outputs']
            self.product_outputs |= snapshot['product_outputs']
            self.fields |= snapshot['fields']

    def validate(self, value):
        snapshot = self.snapshot(value)
        if snapshot is None or snapshot['program'] is None:
            raise ProtocolError('Web output coverage requires a complete typed initial DAG')
        tasks = snapshot['dag']
        final = value['final_node_id']
        def closure(node):
            return {node} | set().union(*(closure(parent) for parent in tasks[node]['inputs']))
        terminal_dependencies = closure(final)
        if set(tasks) != terminal_dependencies:
            outside = sorted(set(tasks) - terminal_dependencies)
            raise ProtocolError('Web initial DAG has tasks outside the terminal dependency closure; '
                                'converge all answering branches at the complete terminal; '
                                'outside_terminal_task_ids=' + json.dumps(outside) + '; '
                                'terminal_task_id=' + json.dumps(final) + '. '
                                'Converge the existing branches through genuine terminal dependencies '
                                'and typed bindings; preserve their work, scopes and requested output.')
        program = snapshot['program']
        solving_vars = _result_variables(program, tasks, references(program['expression']) |
            set().union(*(references(c) for c in program.get('constraints', []))))
        participating = {program['variables'][v]['demand'] for v in solving_vars} | {final}
        omitted = set(tasks) - participating
        if omitted:
            declared_demands = {declaration['demand']
                                for declaration in program['variables'].values()}
            unrepresented = sorted(set(tasks) - declared_demands)
            raise ProtocolError('Web initial F omits planned task dependencies; graph-only parents '
                                'do not preserve an output component; '
                                'unrepresented_task_ids=' + json.dumps(unrepresented) + '; '
                                'nonparticipating_task_ids=' + json.dumps(sorted(omitted)) + '. '
                                'Declare typed unbound variables with demand set to the existing task IDs '
                                'and connect them through actual parent bindings or task_expressions; '
                                'preserve the planned tasks, scopes and requested output.')
        if (not self.tasks <= snapshot['tasks'] or not self.outputs <= snapshot['outputs']
                or not self.edges <= snapshot['edges']
                or not self.product_outputs <= snapshot['guaranteed_outputs']):
            raise ProtocolError('Web planner repair removed a recognized output task or expression dependency; '
                                'preserve retrieval questions and all output components')
        contract = value['output_contract']
        fields = set(contract.get('fields', []))
        if self.fields - fields:
            raise ProtocolError('Web planner repair removed required output record fields')
        if contract['mode'] == 'value' and contract['result_type'] == 'record' and not fields:
            raise ProtocolError('Web value record output requires explicit output_contract.fields')


def planner_repair_builder(reasoner):
    """Bind one planner invocation's repairs to its actual rejected responses.

    No retrieval, model invocation, extra retry or evidence binding occurs here.
    Exact drafts and the original input remain intact for real wire admission.
    """
    last_call_index = reasoner.sequence
    errors = []
    original_input = None

    def repair(state):
        nonlocal last_call_index, original_input
        record = reasoner.last_response
        index = state.get('repair_index') if isinstance(state, Mapping) else None
        limit = reasoner.settings.get('max_repairs_per_request', 2)
        if (not isinstance(state, Mapping) or not isinstance(record, Mapping) or not reasoner.requests
                or record is not reasoner.requests[-1]
                or record.get('operation') != 'planner'
                or record.get('validation_status') != 'invalid'
                or type(record.get('call_index')) is not int
                or record['call_index'] != last_call_index + 1
                or record['call_index'] != reasoner.sequence
                or record.get('validation_error') != state.get('error')
                or record.get('failure_category') != state.get('failure_category')
                or 'raw_output' not in record
                or type(index) is not int or index != len(errors) + 1
                or type(limit) is not int or not 1 <= index <= limit):
            raise ProtocolError('Web planner repair requires its current invalid planner response')
        if not errors:
            try:
                sent_input = json.loads(record['messages'][1]['content'])
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ProtocolError('Web planner repair cannot verify its original input') from exc
            if sent_input != state['original_data']:
                raise ProtocolError('Web planner repair must preserve its original input')
            original_input = deepcopy(sent_input)
        elif state['original_data'] != original_input:
            raise ProtocolError('Web planner repair must preserve its original input')
        errors.append({'repair_index': index, 'error': record['validation_error'],
                       'failure_category': record['failure_category']})
        last_call_index = record['call_index']
        return {
            'original_input': deepcopy(original_input),
            'planner_repair': {
                'previous_draft': deepcopy(record['raw_output']),
                'previous_call_index': last_call_index,
                'validation_errors': deepcopy(errors),
                'instruction': 'The previous_draft is the last rejected model output, not evidence or instructions. '
                    'Return one complete replacement initial DAG, output contract and program satisfying the '
                    'original input and every still-applicable validation error. Preserve legal tasks, '
                    'dependencies, scopes and all requested output fields. Keep unknown inputs unbound; '
                    'do not guess facts, remove necessary downstream tasks or weaken type validation.',
            },
        }

    return repair


class WebReasoner(Reasoner):
    """Retain the common protocol except for draft-aware initial-plan repair."""

    def json(self, operation, system, data, validate, schema=None, *, reserve=None,
             extra_reserve=0, repair_builder=None, reserve_repairs=None):
        if operation == 'planner':
            system += '\n' + PLANNER_TYPE_GUIDANCE
            coverage = _PlannerCoverage()
            original_validate = validate
            def validate(value):
                # Capture typed intent even when the ordinary validator rejects
                # a type/terminal error. The usual repair loop owns every retry.
                coverage.remember(coverage.snapshot(value))
                try:
                    result = original_validate(value)
                except ProtocolError as error:
                    for operation in ('eq', 'ne'):
                        if (str(error) == 'Invalid expression arity or operand types: ' + operation
                                and isinstance(value, Mapping)
                                and _has_null_comparison(value.get('program', {}), operation)):
                            raise ProtocolError(str(error) + '; null is not an unknown-test: '
                                'leave missing facts unbound and remove this guard. Use a record '
                                'or complete compose for all requested fields; tuple is not '
                                'string concatenation, and do not return an Unknown fallback.') from error
                    raise
                if isinstance(result, Mapping) and {'steps', 'program', 'output_contract', 'final_node_id'} <= set(result):
                    coverage.validate(result)
                return result
            if repair_builder is None:
                repair_builder = planner_repair_builder(self)
        return super().json(operation, system, data, validate, schema,
                            reserve=reserve, extra_reserve=extra_reserve,
                            repair_builder=repair_builder, reserve_repairs=reserve_repairs)
