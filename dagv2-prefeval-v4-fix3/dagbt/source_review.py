"""Paid, per-original review syntax; normal observation guards own acceptance.

No issue is closed here. An explicit model check becomes either a reference to
an unchanged offered observation, or a sourced nonbinding observation. Actual
supports and counters still need the complete ordinary observation protocol.
"""
from copy import deepcopy

from .transport import digest


INSTRUCTION = '''
SOURCE REVIEW FORM (the source_review_contract is authoritative for this form):
Separate a fact's supporting citations from reviewing the other original text.
For each contracted slot return source_checks, exactly one check for EACH listed
source_id. Read its full original text, role, time and scope, not just the quote.
Every check has source_id, assessment, observation_id, quote and reason. quote
must be a nonempty verbatim substring of that original; reason explains how it
bears on the supplied scoped issues. Never invent a quote or classify a source
from its alias, retrieval rank, lack of matching keywords, or a previous summary.

Use assessment="observation" only when that source is cited by a complete new
observation in this slot's observations, or by an unchanged observation explicitly
offered in source_review_contract[variable].reference_observations. Name its exact
observation_id. Referencing an offered immutable row means observations=[] for
that row: DO NOT copy, edit or revise it. Other/new facts and real counterevidence
still require ordinary full observations with their actual scope and parents.
Never reference an arbitrary known route or an observation from an earlier batch.

For original text that truly does not bear on the outstanding scoped issue, use
assessment="irrelevant", observation_id=null, and explain its actual content and
why it does not resolve or challenge the issue. Supporting or contrary text is
NOT irrelevant. If a source supplies only an unresolved clue use "partial"; if
its meaning/applicability cannot be established use "unknown" (observation_id=null).
Those judgments keep the issue open. Never choose irrelevant merely to pass.
The host records these explicit nonbinding checks with value=null; it never turns
them into support or automatically dismisses an issue. Each checked source gets
its own record; do not pad a support's source_ids with unrelated originals.

Only put an offered issue ID in resolved_obligation_ids after actually resolving
its stated descriptions across ALL required originals, with no remaining issue.
If missing optional information is immaterial, explicitly explain that scoped
assessment using the examined originals; do not invent missing user attributes.
Preserve necessary uncertainty, changed preferences and every relevant counter.
The ordinary rules for named failed drafts, required counters and failed-batch
recovery still apply. Return only slots in this history phase; never an answer,
option label, audit verdict, source_review_contract or any other top-level field.
'''


def contract(data):
    """Offer the form only where full original obligations can be reviewed.

    Named draft/whole-value repairs retain their ordinary in-place syntax.
    This does not change sources, authority, state, or budget admission.
    """
    if (not data.get('personal_response_selection')
            or data.get('phase') != 'history_evidence'
            or 'audit_instruction' in data or 'terminal_repair' in data):
        return {}
    scope = data.get('repair_scope', {})
    if (scope.get('whole_value_reviews') or any(
            item.get('id') != '*' or item.get('required_counter_observations')
            or item.get('replacement_observations')
            for item in scope.get('failed', []))):
        return {}
    # A durable failed draft keeps its original recovery permissions and shape.
    if any(record.get('whole_value_reviews') or any(
            item.get('id') != '*' or item.get('required_counter_observations')
            or item.get('replacement_observations')
            for item in record.get('failed', []))
            for record in data.get('failed_batch_reviews', [])):
        return {}
    visible = {source['id']: source for source in data['source_spans']}
    requested = data.get('requested_slots', list(data['variables']))
    result = {}
    for variable in requested:
        issues = [item for item in data.get('evidence_obligations', [])
                  if item['variable'] == variable]
        required = sorted({source for item in issues for source in item['source_ids']})
        if not required or not set(required) <= set(visible):
            continue
        offered = []
        for entry in scope.get('failed', []):
            if entry['variable'] != variable or entry['id'] != '*':
                continue
            offer = entry.get('frozen_observation_reviews', {})
            for identifier in offer.get('slot_observation_ids', []):
                matching = [row for row in entry.get('slot', {}).get('observations', [])
                            if isinstance(row, dict) and row.get('id') == identifier]
                if len(matching) != 1:
                    return {}
                offered.extend(matching)
            offered.extend(offer.get('observations', []))
        if len({row['id'] for row in offered}) != len(offered):
            return {}
        result[variable] = {'source_ids': required,
                            'obligation_ids': [item['id'] for item in issues],
                            'reference_observations': deepcopy(offered)}
    return result


def schema_with_checks(schema, data):
    """Constrain the new syntax without changing existing observation shapes."""
    offered = contract(data)
    if not offered:
        return schema
    result = deepcopy(schema)
    item = result['properties']['slots']['items']
    check = {'type': 'object', 'properties': {
        'source_id': {'type': 'string'},
        'assessment': {'enum': ['observation', 'irrelevant', 'partial', 'unknown']},
        'observation_id': {'type': ['string', 'null']},
        'quote': {'type': 'string', 'minLength': 1},
        'reason': {'type': 'string', 'minLength': 1}},
        'required': ['source_id', 'assessment', 'observation_id', 'quote', 'reason'],
        'additionalProperties': False,
        'allOf': [{'if': {'properties': {'assessment': {'const': 'observation'}}},
                   'then': {'properties': {'observation_id': {'type': 'string', 'minLength': 1}}},
                   'else': {'properties': {'observation_id': {'type': 'null'}}}}]}
    item['properties']['source_checks'] = {'type': 'array', 'items': check}
    for branch in item['oneOf']:
        properties = branch['properties']
        variable = properties['variable']['const']
        if variable in offered:
            sources = offered[variable]['source_ids']
            properties['source_checks'] = {
                'minItems': len(sources), 'maxItems': len(sources),
                'items': {'properties': {'source_id': {'enum': sources}}}}
            branch.setdefault('required', []).append('source_checks')
        else:
            properties['source_checks'] = {'maxItems': 0}
    return result


def decode(response, data):
    """Translate explicit judgments only; preserve drafts on malformed forms.

    Legacy ordinary replies still go through the unchanged strict guards.
    Malformed new replies retain all full counter drafts for the reader's normal
    envelope repair instead of throwing before its evidence-capture step.
    """
    offered = contract(data)
    if (not offered or not isinstance(response, dict)
            or not isinstance(response.get('slots'), list)
            or not any(isinstance(slot, dict) and 'source_checks' in slot
                       for slot in response['slots'])):
        return response
    result = deepcopy(response)
    originals = {source['id']: source for source in data['source_spans']}
    try:
        seen_variables = set()
        for slot in result['slots']:
            variable = slot['variable']
            if variable in seen_variables:
                raise ValueError('duplicate review slot')
            seen_variables.add(variable)
            if variable not in offered:
                if slot.get('source_checks'):
                    raise ValueError('unoffered review variable')
                slot.pop('source_checks', None)
                continue
            checks = slot.pop('source_checks')
            if not isinstance(checks, list) or not isinstance(slot['observations'], list):
                raise ValueError('review checks and observations must be lists')
            ids = [check['source_id'] for check in checks]
            if (len(set(ids)) != len(ids)
                    or set(ids) != set(offered[variable]['source_ids'])):
                raise ValueError('each required original needs exactly one check')
            refs = slot.get('reviewed_observation_ids', [])
            if (not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs)
                    or len(set(refs)) != len(refs)):
                raise ValueError('observation references must remain unique explicit IDs')
            refs = list(refs)
            rows = slot['observations']
            available = [*rows, *offered[variable]['reference_observations']]
            for check in checks:
                if (set(check) != {'source_id', 'assessment', 'observation_id', 'quote', 'reason'}
                        or not isinstance(check['quote'], str) or not check['quote'].strip()
                        or check['quote'] not in originals[check['source_id']]['text']
                        or not isinstance(check['reason'], str) or not check['reason'].strip()):
                    raise ValueError('source review needs an exact original quote and a reason')
                assessment = check['assessment']
                if assessment == 'observation':
                    identifier = check['observation_id']
                    matching = [row for row in available if isinstance(row, dict)
                                and row.get('id') == identifier]
                    if len(matching) != 1 or check['source_id'] not in matching[0]['source_ids']:
                        raise ValueError('review must cite a unique offered or new observation using this original')
                    if matching[0] not in rows and identifier not in refs:
                        refs.append(identifier)
                else:
                    if assessment not in ('irrelevant', 'partial', 'unknown') or check['observation_id'] is not None:
                        raise ValueError('nonbinding review cannot invent a support or an observation reference')
                    scope = data['requested_scopes'][variable]
                    rows.append({'id': 'source_check_' + digest([variable, check])[:24],
                        'stance': assessment, 'value': None, 'source_ids': [check['source_id']],
                        **scope, 'parent_versions': {}, 'retract_ids': [],
                        'reason': check['reason'] + '\nOriginal quote: ' + check['quote']})
            if refs:
                slot['reviewed_observation_ids'] = refs
        if not set(offered) <= seen_variables:
            raise ValueError('missing contracted review slot')
    except (KeyError, TypeError, ValueError) as exc:
        # Keep exact raw drafts, including any full sourced counter. The extra
        # envelope field deliberately enters ordinary repair, never success.
        result = deepcopy(response)
        result['source_review_error'] = str(exc)
    return result
