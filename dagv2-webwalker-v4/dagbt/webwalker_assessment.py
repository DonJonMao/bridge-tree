"""Operational navigation assessments, never evidence or absence certificates."""
from copy import deepcopy

from .transport import digest


PAUSED = 'navigation_assessment_paused'


def candidate_identity(link):
    # lN is a request-local selection alias, not an original-link identity.
    return digest({name: value for name, value in link.items() if name != 'id'})


def _semantic(value, field=None):
    """Project operationally meaningful content; retain the full originals.

    Model observation names, explanations and accumulated descriptions are not
    new evidence. Actual source sets, scopes, values, counter targets, parent
    versions, revision ancestry and explicit review references remain material.
    This projection never changes a reading/review permission or a fact.
    """
    if field in ('value', 'binding_derivation'):
        return deepcopy(value)
    if isinstance(value, dict):
        result = {key: _semantic(item, key) for key, item in value.items()
                  if key not in ('id', 'reason', 'descriptions', 'origins', 'invalid_response',
                                 'error', 'feedback', 'query_identity', 'batch_identity',
                                 'seen_source_ids', 'seen_parent_signatures')}
        # Whole-slot and row-specific repair are different authority scopes.
        if 'id' in value and ('observation' in value or 'slot' in value):
            result['whole_slot'] = value['id'] == '*'
        return result
    if isinstance(value, (list, tuple)):
        items = [_semantic(item) for item in value]
        if field in ('source_ids', 'required_source_ids', 'retract_ids', 'supersedes_route_ids',
                     'superseded_by', 'known_observation_ids', 'slot_observation_ids', 'revoked',
                     'observations', 'validated_observations', 'draft_observations',
                     'known_observations', 'required_counter_observations',
                     'replacement_observations', 'failed', 'whole_value_reviews'):
            return sorted({digest(item) for item in items})
        return items
    return value


def _unique(rows):
    return sorted({digest(_semantic(row)) for row in rows})


def accepted_evidence_identity(state):
    # A real counter can revoke an unselected OR proof while the chosen value,
    # source set and binding version survive. That accepted correction still
    # deserves task-local priority. Repeated source-identical counter wording
    # does not; full unchanged route/counter records remain in FactState.
    return digest([state.valid(), state.versions, _unique(state.routes.values())])


def _material(engine, node, identity):
    control = getattr(engine, 'residual_control', None)
    reader = getattr(control, 'reader', None)
    state = getattr(control, 'state', getattr(engine, 'fact_state', None))
    if state is None:
        # Offline adapters may explicitly supply their material version.
        return getattr(control, 'navigation_material', None)
    tasks = {node}
    pending = [node]
    steps = {step['output_slot']: step for step in engine.steps}
    while pending:
        for parent in steps.get(pending.pop(), {}).get('inputs', []):
            if parent not in tasks:
                tasks.add(parent); pending.append(parent)
    variables = {v for v, declaration in state.program['variables'].items()
                 if declaration['demand'] in tasks}
    def original(alias):
        source = engine.mapper.sources[alias]
        return digest({name: value for name, value in source.items() if name != 'id'})
    def issue_rows(name):
        return _unique(row for row in getattr(reader, name, {}).values()
                       if row.get('variable') in variables)
    failed_permissions = []
    # A consumed review's ever-growing histories are not progress. Only an
    # actual change of currently available original/parent review authority is.
    available = {source['source_id'] for source in engine.mapper.sources.values()
                 if source['doc_id'] in getattr(control, 'local_pools', {}).get(node, [])}
    for row in getattr(reader, 'failed_batch_reviews', {}).values():
        if row.get('variable') in variables:
            parent_signature = getattr(reader, '_failed_parent_signature', lambda variable: None)(row['variable'])
            failed_permissions.append({'variable': row['variable'], 'task_id': row.get('task_id'),
                'phase': row.get('phase'),
                'new_originals': sorted(available - set(row.get('seen_source_ids', []))),
                'new_parent': parent_signature is not None
                    and parent_signature not in row.get('seen_parent_signatures', [])})
    return {
        'program': state.program, 'contract': state.contract, 'dag': engine.steps,
        'variables': sorted(variables),
        'versions': {v: state.versions[v] for v in sorted(variables)},
        'pending': sorted(variables & state.pending),
        'routes': _unique(row for row in state.routes.values() if row['variable'] in variables),
        'read_states': sorted([original(alias), status]
            for (key, alias), status in getattr(reader, 'read_states', {}).items() if key == identity),
        'discovery': sorted([original(alias), digest(entry)]
            for (key, alias), entry in getattr(reader, 'discovery_frontier', {}).items() if key == identity),
        'unread': sorted([original(alias), sorted(owners & variables)]
            for (key, alias), owners in getattr(reader, 'unread_obligations', {}).items()
            if key == identity and owners & variables),
        # Failed-obligation keys identify batches, not original source aliases.
        # Their semantic records below retain the actual mandatory drafts.
        'failed_owners': sorted({v for (key, _), owners in getattr(reader, 'failed_obligations', {}).items()
                                if key == identity for v in owners & variables}),
        'evidence_obligations': issue_rows('evidence_obligations'),
        'failed_batch_reviews': issue_rows('failed_batch_reviews'),
        'failed_review_authority': _unique(failed_permissions)}


def context_identity(bridge, state):
    # Original frontier universe includes visited/failed entries. Merely removing
    # a failed URL, rotating presentation, or consuming a budget cannot renew it.
    originals = sorted(digest({'doc_id': doc_id, 'document_hash': page['document_hash'],
                              'links': page['document']['links'],
                              'contexts': page['document'].get('link_contexts', {})})
                       for doc_id, page in bridge.pages.items())
    capacity = {name: getattr(bridge.e, 's', {}).get(name) for name in
                ('context_tokens', 'reasoning_output_tokens', 'input_margin', 'response_format')}
    return digest({'query': state['query'], 'node': state['node'],
                   'identity': state['identity_context'], 'originals': originals,
                   'material': _material(bridge.e, state['node'], state['key']),
                   'capacity': capacity, 'link_window': bridge.settings.get('link_window', 128)})


def current_assessment(bridge, state, *, create=False):
    context = context_identity(bridge, state)
    records = state.get('navigation_assessments', {})
    if context not in records:
        if not create:
            return context, None
        records = state.setdefault('navigation_assessments', {})
        records[context] = {'null_candidates': [], 'null_windows': [],
                            'reconsideration_used': False, 'pause_reason': None}
    return context, records[context]


def unseen_candidates(links, record):
    assessed = set(record['null_candidates']) if record else set()
    return [link for link in links if candidate_identity(link) not in assessed]


def actionable(bridge, state, links):
    if not links:
        return False
    if 'query' not in state:
        return True
    _, record = current_assessment(bridge, state)
    return (record is None or (record['pause_reason'] is None
            and (bool(unseen_candidates(links, record)) or not record['reconsideration_used'])))


def mark_null(record, links, data):
    assessed = set(record['null_candidates'])
    assessed.update(candidate_identity(link) for link in links)
    record['null_candidates'] = sorted(assessed)
    window = {'candidate_ids': [candidate_identity(link) for link in links],
              'source_pages': [{key: deepcopy(value) for key, value in source.items() if key != 'text'}
                  | {'excerpt_sha256': digest(source['text']), 'source_record_sha256': digest(source)}
                  for source in data['source_pages']]}
    if window not in record['null_windows']:
        record['null_windows'].append(window)
