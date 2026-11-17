"""One paid Web failed-draft review after archived, accepted local correction.

This is a permission to ask, never permission to settle. Common validators,
release, source identities, repair charging and publication remain unchanged.
"""
from copy import deepcopy

from .evidence_protocol import parse_evidence_object
from .fact_state import FactState
from .reasoning import ProtocolError
from .transport import digest


KEY = 'web_correction_reviews_v1'
TRACK_KEY = 'web_correction_tracking_origins_v1'
HISTORY_KEY = 'web_read_history_index_v1'
POLICY = 'accepted_local_correction_one_paid_review_v1'


class CorrectionReviewMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._web_correction_state = {'version': 1, 'enabled': True,
                                      'tracked': {}, 'grants': {}, 'attempts': []}
        self._web_correction_signature_view = False
        self._web_correction_active = None
        self._web_correction_ordinary_mode = True

    def obligation_snapshot(self):
        result = super().obligation_snapshot()
        if not self._web_correction_signature_view:
            result[KEY] = deepcopy(self._web_correction_state)
        return result

    def material_signature(self):
        previous = self._web_correction_signature_view
        self._web_correction_signature_view = True
        try:
            return super().material_signature()
        finally:
            self._web_correction_signature_view = previous

    def _correction_context(self, record, state=None):
        state = state or self.state
        variable = record['variable']
        step = next(step for step in self.e.steps if step['output_slot'] == record['task_id'])
        values, _, _ = state.valid()
        return {'task_id': step['output_slot'], 'variable': variable,
                'scope': state.scope(variable),
                'parents': {v: {'version': state.versions[v], 'value': deepcopy(values.get(v))}
                            for v, declaration in state.program['variables'].items()
                            if declaration['demand'] in step['inputs']}}

    @staticmethod
    def _semantic_row(row):
        def original_ids(value):
            return sorted(set(value)) if isinstance(value, list) and all(isinstance(item, str) for item in value) else deepcopy(value)
        return {key: deepcopy(row.get(key)) for key in
                ('variable', 'stance', 'value', 'entity_scope', 'time_scope', 'parent_versions')} | {
                    'retract_ids': original_ids(row.get('retract_ids', [])),
                    'source_ids': original_ids(row.get('source_ids', []))}

    def _marker_parts(self, record):
        bound_sources = {source['source_id'] for source in self.e.mapper.sources.values()}
        def original_draft(row):
            result = self._semantic_row({**row, 'variable': record['variable']})
            # Unbound wire names are not new originals or counter targets.
            # Valid stable source/route identities remain distinct.
            for key, known, absent in (('source_ids', bound_sources, 'unbound_original_source'),
                    ('retract_ids', self.state.routes, 'unbound_counter_target')):
                value = result[key]
                if isinstance(value, list) and all(isinstance(item, str) for item in value):
                    result[key] = sorted({item if item in known else absent for item in value})
            return result
        drafts = []
        for failure in record['failed']:
            for row in [failure.get('observation'), *failure.get('observations', []),
                        *failure.get('replacement_observations', []),
                        *failure.get('required_counter_observations', [])]:
                if isinstance(row, dict):
                    drafts.append(original_draft(row))
            for review in failure.get('obligation_review_sources', []):
                drafts.append({'ordinary_obligation': review['obligation_id'],
                               'required_source_ids': sorted(review['required_source_ids'])})
        for group in record.get('whole_value_reviews', []):
            for row in [*group.get('draft_observations', []), *group.get('known_observations', [])]:
                drafts.append({'whole_value_original': original_draft(row)})
            drafts.append({'whole_value_required_source_ids': sorted(group.get('required_source_ids', []))})
        return {'sources': sorted(set(record['source_ids'])),
                'drafts': sorted({digest(row) for row in drafts})}

    def _marker_family(self, record, context=None):
        # Model/query/alias names, reason prose, feedback changes and retries
        # cannot turn the same original obligation into another permission.
        return digest([context or self._correction_context(record), self._marker_parts(record)])

    def _extends_marker(self, original, current):
        if any(original[key] != current[key] for key in ('task_id', 'variable', 'phase')):
            return False
        old, new = self._marker_parts(original), self._marker_parts(current)
        return set(old['sources']) <= set(new['sources']) and set(old['drafts']) <= set(new['drafts'])

    def _track_existing_corrections(self):
        registry = self._web_correction_state
        if not registry['enabled'] or self.state.revision or self.state.program != self.state.initial_program:
            return
        for rid, record in self.failed_batch_reviews.items():
            if record['phase'] != 'history' or rid in registry['tracked']:
                continue
            step = next(step for step in self.e.steps if step['output_slot'] == record['task_id'])
            if step.get('execution') != 'retrieval' or not self.source_exposures:
                continue
            context = self._correction_context(record)
            # A new common marker ID does not renew the same unresolved defect.
            # Keep explicit Web-only ancestry before accepting later evidence.
            parents = [(old_id, old) for old_id, old in registry['tracked'].items()
                       if old['context'] == context and self._extends_marker(old['record'], record)]
            parent_id, parent = parents[0] if parents else (None, None)
            registry['tracked'][rid] = {'lineage': parent['lineage'] if parent else self._marker_family(record),
                'parent_marker_id': parent_id, 'record': deepcopy(record), 'context': context,
                'after_call': self.e.reasoner.sequence, 'history_start': len(self.state.history),
                'ordinary': deepcopy(self.evidence_obligations)}
            self.source_exposures[-1].setdefault(TRACK_KEY, []).append(
                self._tracking_origin(rid, registry['tracked'][rid]))

    @staticmethod
    def _tracking_origin(marker_id, tracked):
        return {'marker_id': marker_id, 'lineage': tracked['lineage'],
                'parent_marker_id': tracked['parent_marker_id'],
                'history_start': tracked['history_start'], 'after_call': tracked['after_call'],
                'record_identity': digest(tracked['record']), 'context_identity': digest(tracked['context']),
                'ordinary_identity': digest(tracked['ordinary'])}

    def _replayed_state(self, end):
        state = FactState(self.state.initial_program, self.state.contract,
                          self.state.steps, self.state.final_node_id)
        for entry in self.state.history[:end]:
            if entry.get('event') != 'fact_batch_integrated' or entry.get('program_revision') != 0:
                raise ProtocolError('Correction proof cannot replay dynamic or unrecognized state history')
            state.integrate(deepcopy(entry['rows']), entry['pending_variables'])
        return state

    def _paid_rows(self, after_call):
        """Rows actually returned by metered calls, with stable source names."""
        result = []
        records = {row['logical_call_index']: row for row in self.e.reasoner.requests
                   if row.get('logical_call_index', 0) > after_call
                   and row.get('validation_status') == 'valid' and row.get('response_ref')}
        if self.e.ledger.used.get('llm', 0) < len(records):
            return []
        for exposure in self.source_exposures:
            call = exposure.get('logical_call_index')
            record = records.get(call)
            if (record is None or exposure.get('request_status') != 'returned'
                    or record['operation'] not in ('joint_read', 'joint_read_repair')
                    or exposure['phase'] != 'history'
                    or type(exposure.get(HISTORY_KEY)) is not int
                    or not 0 <= exposure[HISTORY_KEY] < len(self.state.history)):
                continue
            aliases = {source['source_alias']: source['source_id'] for source in exposure['sources']}
            aliases.update({source['source_id']: source['source_id'] for source in exposure['sources']})
            try:
                request = parse_evidence_object(record['messages'][1]['content'])
                if (request.get('task', {}).get('output_slot') != exposure['task_id']
                        or self._failed_phase(request) != 'history'):
                    continue
                markers = {}
                for marker in request.get('failed_batch_reviews', []):
                    stable = self._remap_review_sources(marker, aliases)
                    stable['failed'] = [self._remap_failed_entry_sources(item, aliases)
                                        for item in marker['failed']]
                    markers[marker['id']] = stable
                ordinary = {item['id']: self._remap_review_sources(item, aliases)
                            for item in request.get('evidence_obligations', [])}
                response = parse_evidence_object(record['raw_output'])
            except (ValueError, TypeError, KeyError):
                continue
            slots = response.get('slots')
            if not isinstance(slots, list):
                continue
            for slot in slots:
                if not isinstance(slot, dict) or not isinstance(slot.get('observations'), list):
                    continue
                for raw in slot.get('observations', []):
                    if (not isinstance(raw, dict) or not isinstance(raw.get('source_ids'), list)
                            or not raw['source_ids'] or any(not isinstance(source, str) or source not in aliases
                                                          for source in raw['source_ids'])):
                        continue
                    row = {**deepcopy(raw), 'variable': slot.get('variable'),
                           'source_ids': sorted({aliases[source] for source in raw['source_ids']})}
                    result.append({'row': row, 'call': call, 'response_ref': record['response_ref'],
                        'response_digest': digest(record['raw_output']),
                        'request_identity': exposure['request_identity'],
                        'claims': slot.get('resolved_obligation_ids', []),
                        'visible_source_ids': sorted({source['source_id'] for source in exposure['sources']}),
                        'offered_markers': markers, 'ordinary': ordinary,
                        'accepted_history_index': exposure.get(HISTORY_KEY),
                        'unresolved': deepcopy(slot.get('unresolved'))})
        return result

    def _correction_proof(self, tracked, end):
        record, variable = tracked['record'], tracked['record']['variable']
        if (self.state.revision or self.state.program != self.state.initial_program
                or type(tracked['after_call']) is not int or tracked['after_call'] < 0
                or type(tracked['history_start']) is not int
                or not 0 <= tracked['history_start'] < end <= len(self.state.history)):
            return None
        before, after = self._replayed_state(tracked['history_start']), self._replayed_state(end)
        if (self._correction_context(record, before) != tracked['context']
                or self._correction_context(record, after) != tracked['context']):
            return None
        accepted = []
        paid = self._paid_rows(tracked['after_call'])
        for history_index in range(tracked['history_start'], end):
            entry = self.state.history[history_index]
            for row in entry['rows']:
                if row['variable'] != variable:
                    continue
                match = next((item for item in paid if item['accepted_history_index'] == history_index
                              and item['row'].get('id') == row.get('id')
                              and self._semantic_row(item['row']) == self._semantic_row(row)), None)
                if match is not None:
                    offered = match['offered_markers'].get(record['id'])
                    if (offered is not None and self._marker_family(offered, tracked['context'])
                            == self._marker_family(record, tracked['context'])):
                        accepted.append(match)
        required = self._failed_required_rows(record)
        supports = [item for item in accepted if item['row']['stance'] == 'support']
        old_values, _, _ = before.valid()
        new_values, _, _ = after.valid()
        # A named failed support corrected in place, or a named failed counter
        # draft corrected into a counter which actually retires an old route
        # plus a sourced new support. Original invalid stance is not authority.
        if variable in new_values and new_values.get(variable) != old_values.get(variable):
            for support in supports:
                row = support['row']
                if row['value'] != new_values[variable]:
                    continue
                if row.get('id') in required and required[row['id']]['draft'].get('stance') == 'support':
                    return {'kind': 'accepted_named_support_correction', 'history_end': end,
                            'accepted': [support]}
                for counter in accepted:
                    cr = counter['row']
                    if cr['stance'] != 'contradiction' or cr.get('id') not in required:
                        continue
                    targets = cr.get('retract_ids', [])
                    if (targets and all(target in before.routes and not before.routes[target]['revoked']
                        and target in after.routes and after.routes[target]['revoked'] for target in targets)):
                        return {'kind': 'accepted_named_counter_and_support_correction',
                                'history_end': end, 'accepted': [counter, support]}
        # Wildcard coverage failures require their *own* ordinary obligation,
        # an explicit paid claim and accepted reviews covering those originals.
        for failure in record['failed']:
            for review in failure.get('obligation_review_sources', []):
                oid = review['obligation_id']
                ordinary = tracked['ordinary'].get(oid)
                required_sources = set(review['required_source_ids'])
                if (ordinary is None
                        or ordinary['variable'] != variable
                        or set(ordinary['source_ids']) != required_sources):
                    continue
                for call in sorted({item['call'] for item in accepted}):
                    rows = [item for item in accepted if item['call'] == call and oid in item['claims']
                            and item['unresolved'] == [] and item['ordinary'].get(oid) == ordinary
                            and item['row']['stance'] in ('support', 'contradiction', 'irrelevant')]
                    covered = {source for item in rows for source in item['row']['source_ids']}
                    if required_sources and required_sources <= covered:
                        return {'kind': 'accepted_original_ordinary_obligation_review',
                                'history_end': end, 'obligation': deepcopy(ordinary), 'accepted': rows}
        return None

    def _first_correction_proof(self, tracked):
        for end in range(tracked['history_start'] + 1, len(self.state.history) + 1):
            proof = self._correction_proof(tracked, end)
            if proof is not None:
                return proof
        return None

    def _local_semantics(self, state, variable):
        # An unrelated update, repeated prose or identical accepted replay is
        # not a new correction. A later distinct local observation makes an
        # unconsumed opportunity stale rather than enlarging it.
        values, _, _ = state.valid()
        rows = {digest(self._semantic_row(row)): self._semantic_row(row)
                for entry in state.history for row in entry['rows'] if row['variable'] == variable}
        routes = []
        for route in state.routes.values():
            if route['variable'] == variable:
                routes.append({'id': route['id'], 'row': self._semantic_row(route),
                    'revoked': sorted({digest({'source_ids': sorted(item['source_ids'])})
                                       for item in route.get('revoked', [])}),
                    'superseded_by': sorted(route.get('superseded_by', []))})
        return digest({'value_bound': variable in values, 'value': values.get(variable),
                       'rows': sorted(rows.values(), key=digest), 'routes': sorted(routes, key=digest)})

    def _capture_correction_grants(self):
        registry = self._web_correction_state
        if not registry['enabled']:
            return
        for rid, tracked in registry['tracked'].items():
            lineage = tracked['lineage']
            if rid not in self.failed_batch_reviews or lineage in registry['grants']:
                continue
            proof = self._first_correction_proof(tracked)
            if proof is not None:
                ordinary = proof.get('obligation')
                if ordinary is not None and ordinary['id'] in self.evidence_obligations:
                    continue
                registry['grants'][lineage] = {'marker_id': rid, 'proof': proof,
                    'semantic_state': self._local_semantics(
                        self._replayed_state(proof['history_end']), tracked['record']['variable']),
                    'consumed': False}

    def _read(self, *args, **kwargs):
        previous_mode = self._web_correction_ordinary_mode
        self._web_correction_ordinary_mode = (not any(kwargs.get(key) for key in
            ('semantic', 'audit', 'terminal_output'))
            and kwargs.get('source_scope', 'document_windows') == 'document_windows')
        self._web_correction_active = None
        self._track_existing_corrections()
        try:
            return super()._read(*args, **kwargs)
        finally:
            try:
                self._capture_correction_grants()
            finally:
                self._web_correction_active = None
                self._web_correction_ordinary_mode = previous_mode

    def _correction_offer(self, record, *, check_budget=True):
        registry = self._web_correction_state
        tracked = registry['tracked'].get(record['id'])
        grant = registry['grants'].get(tracked['lineage']) if tracked else None
        eligible = bool(registry['enabled'] and self._web_correction_ordinary_mode and not self.state.revision
            and self.state.program == self.state.initial_program and tracked and grant and not grant['consumed']
            and grant['marker_id'] == record['id'] and self._correction_context(record) == tracked['context']
            and grant['semantic_state'] == self._local_semantics(self.state, record['variable'])
            and (grant['proof'].get('obligation', {}).get('id') not in self.evidence_obligations))
        return eligible and (not check_budget or (self.e.s['max_repairs_per_request'] > 0
            and self.e.ledger.remaining('json_repairs') > 0
            and self.e.ledger.remaining('llm') > self.e.s['reserved_audit_calls']))

    def correction_review_lineages(self, step, variables):
        """Pure operation eligibility; registry changes never become facts."""
        return sorted({self._web_correction_state['tracked'][record['id']]['lineage']
            for record in self.failed_batch_reviews.values()
            if record['task_id'] == step['output_slot'] and record['variable'] in variables
            and record['phase'] == 'history' and step.get('execution') == 'retrieval'
            and self._correction_offer(record)})

    def failed_review_ready(self, step, variables, doc_ids=()):
        return super().failed_review_ready(step, variables, doc_ids) or any(
            record['task_id'] == step['output_slot'] and record['variable'] in variables
            and record['phase'] == 'history' and step.get('execution') == 'retrieval'
            and self._correction_offer(record)
            for record in self.failed_batch_reviews.values())

    def _failed_payload(self, records, source_aliases, step, phase):
        result = super()._failed_payload(records, source_aliases, step, phase)
        authorized = {item['variable'] for item in result if item['review_allowed']}
        if phase != 'history' or step.get('execution') != 'retrieval':
            return result
        by_id = {record['id']: record for record in records}
        for item in result:
            record = by_id[item['id']]
            if (item['variable'] not in authorized and record['task_id'] == step['output_slot']
                    and set(record['source_ids']) <= set(source_aliases) and self._correction_offer(record)):
                item['review_allowed'] = True
                tracked = self._web_correction_state['tracked'][record['id']]
                item['web_review_permission'] = {'policy': POLICY, 'lineage': tracked['lineage'],
                    'one_logical_request': True}
                authorized.add(item['variable'])
        return result

    def _request_with_exposure(self, operation, data, identity, wire, system, **options):
        registry, chosen = self._web_correction_state, []
        if operation == 'joint_read_repair' and self._search_gap_scope(data) and not data.get('repair_scope'):
            for item in data.get('failed_batch_reviews', []):
                record = self.failed_batch_reviews.get(item['id'])
                permission = item.get('web_review_permission')
                if permission is not None:
                    tracked = registry['tracked'].get(item['id'])
                    if (not item['review_allowed'] or record is None or not tracked
                            or permission != {'policy': POLICY, 'lineage': tracked['lineage'],
                                              'one_logical_request': True}
                            or not self._correction_offer(record, check_budget=False)):
                        raise ProtocolError('Correction-review permission differs from selected paid request')
                    chosen.append(tracked['lineage'])
        attempt = None
        if chosen:
            attempt = {'policy': POLICY, 'lineages': sorted(chosen),
                       'request_identity': digest(data), 'query_identity': identity,
                       'task_id': data['task']['output_slot'], 'status': 'attempted'}
            for lineage in chosen:
                registry['grants'][lineage]['consumed'] = True
            registry['attempts'].append(attempt)
            self._web_correction_active = attempt
        start = len(self.source_exposures)
        accepted_history_index = len(self.state.history)
        try:
            response = super()._request_with_exposure(operation, data, identity, wire, system, **options)
        except BaseException:
            if attempt is not None:
                attempt['status'] = 'failed_or_not_sent'
            raise
        else:
            if attempt is not None:
                attempt['status'] = 'response_received'
            return response
        finally:
            for exposure in self.source_exposures[start:]:
                exposure[HISTORY_KEY] = accepted_history_index
                if attempt is not None:
                    exposure[KEY] = deepcopy(attempt)

    def _repair_fits(self, operation, data, step, identity, attempt):
        active = self._web_correction_active
        if (active and operation == 'joint_read_repair' and active['query_identity'] == identity
                and active['task_id'] == step['output_slot']):
            return False
        return super()._repair_fits(operation, data, step, identity, attempt)

    def _archived_correction_calls(self):
        result = []
        for request in self.e.reasoner.requests:
            try:
                data = parse_evidence_object(request['messages'][1]['content'])
            except (ValueError, TypeError, KeyError, IndexError):
                continue
            for marker in data.get('failed_batch_reviews', []):
                permission = marker.get('web_review_permission') if isinstance(marker, dict) else None
                if permission is not None:
                    if (not isinstance(permission, dict) or permission.get('policy') != POLICY
                            or not isinstance(permission.get('lineage'), str)
                            or permission.get('one_logical_request') is not True
                            or request['operation'] != 'joint_read_repair'):
                        raise ProtocolError('Archived correction review has invalid operation ownership')
                    result.append((request['logical_call_index'], permission['lineage']))
        return result

    def restore_obligations(self, snapshot):
        disabled = {'version': 1, 'enabled': False, 'tracked': {}, 'grants': {}, 'attempts': []}
        self._web_correction_state = deepcopy(disabled)
        restored = super().restore_obligations(snapshot)
        saved = restored.get(KEY)
        exposed = [(exposure, exposure[KEY]) for exposure in self.source_exposures if KEY in exposure]
        attempts = [attempt for _, attempt in exposed]
        archived_calls = self._archived_correction_calls()
        origins = [origin for exposure in self.source_exposures
                   for origin in exposure.get(TRACK_KEY, [])]
        if saved is None:
            if attempts or archived_calls:
                self._web_correction_state = disabled
                raise ProtocolError('Correction review checkpoint lost consumed permissions')
            self._web_correction_state = disabled
            return restored
        if (not isinstance(saved, dict) or set(saved) != {'version', 'enabled', 'tracked', 'grants', 'attempts'}
                or type(saved['version']) is not int or saved['version'] != 1
                or type(saved['enabled']) is not bool or not isinstance(saved['tracked'], dict)
                or not isinstance(saved['grants'], dict) or not isinstance(saved['attempts'], list)
                or (not saved['enabled'] and (saved['tracked'] or saved['grants'] or saved['attempts']))):
            raise ProtocolError('Malformed correction review checkpoint')
        self._web_correction_state = deepcopy(saved)
        if not saved['enabled']:
            if attempts or archived_calls:
                self._web_correction_state = disabled
                raise ProtocolError('Disabled correction review checkpoint lost consumed ownership')
            return restored
        try:
            for call, lineage in archived_calls:
                matching = [attempt for exposure, attempt in exposed
                            if exposure.get('logical_call_index') == call
                            and lineage in attempt.get('lineages', [])]
                if len(matching) != 1:
                    raise ProtocolError('Correction review checkpoint lost its archived paid attempt')
            expected_origins = [self._tracking_origin(rid, tracked)
                                for rid, tracked in saved['tracked'].items()]
            if sorted(origins, key=digest) != sorted(expected_origins, key=digest):
                raise ProtocolError('Correction review checkpoint lost or changed tracked ownership')
            for rid, tracked in saved['tracked'].items():
                if (set(tracked) != {'lineage', 'parent_marker_id', 'record', 'context', 'after_call', 'history_start', 'ordinary'}
                        or tracked['record']['id'] != rid
                        or type(tracked['after_call']) is not int or tracked['after_call'] < 0
                        or type(tracked['history_start']) is not int
                        or not 0 <= tracked['history_start'] <= len(self.state.history)
                        or self._correction_context(tracked['record'], self._replayed_state(
                            tracked['history_start'])) != tracked['context']):
                    raise ProtocolError('Correction review lineage or scope changed')
                parent_id = tracked['parent_marker_id']
                if parent_id is None:
                    if self._marker_family(tracked['record'], tracked['context']) != tracked['lineage']:
                        raise ProtocolError('Correction review origin lineage changed')
                else:
                    parent = saved['tracked'][parent_id]
                    if (parent_id == rid or parent['context'] != tracked['context']
                            or parent['lineage'] != tracked['lineage']
                            or parent['history_start'] > tracked['history_start']
                            or parent['after_call'] > tracked['after_call']
                            or not self._extends_marker(parent['record'], tracked['record'])):
                        raise ProtocolError('Correction review inherited obligation lost its ancestry')
                ancestors, cursor = {rid}, parent_id
                while cursor is not None:
                    if cursor in ancestors:
                        raise ProtocolError('Correction review lineage ancestry is cyclic')
                    ancestors.add(cursor)
                    cursor = saved['tracked'][cursor]['parent_marker_id']
            seen = set()
            for exposure, attempt in exposed:
                if (set(attempt) != {'policy', 'lineages', 'request_identity', 'query_identity', 'task_id', 'status'}
                        or attempt['policy'] != POLICY or attempt['status'] not in
                            ('failed_or_not_sent', 'response_received')
                        or attempt['lineages'] != sorted(set(attempt['lineages'])) or not attempt['lineages']
                        or set(attempt['lineages']) & seen
                        or any(attempt[key] != exposure[key] for key in
                               ('request_identity', 'query_identity', 'task_id'))
                        or exposure['phase'] != 'history' or exposure['operation'] != 'joint_read_repair'):
                    raise ProtocolError('Correction review attempt has invalid or repeated ownership')
                for lineage in attempt['lineages']:
                    if lineage not in saved['grants']:
                        raise ProtocolError('Correction review consumed grant was deleted')
                seen.update(attempt['lineages'])
            for lineage, grant in saved['grants'].items():
                tracked = saved['tracked'][grant['marker_id']]
                if (set(grant) != {'marker_id', 'proof', 'semantic_state', 'consumed'}
                        or tracked['lineage'] != lineage or type(grant['consumed']) is not bool
                        or self._first_correction_proof(tracked) != grant['proof']
                        or self._local_semantics(self._replayed_state(grant['proof']['history_end']),
                            tracked['record']['variable']) != grant['semantic_state']):
                    raise ProtocolError('Correction review proof is not an archived accepted change')
                if grant['consumed'] != (lineage in seen):
                    raise ProtocolError('Correction review consumption disagrees with attempted exposures')
            # A still-open marker with an archived accepted correction cannot
            # lose its one-shot ownership and subsequently mint a fresh grant.
            for rid, tracked in saved['tracked'].items():
                if (rid in self.failed_batch_reviews and tracked['lineage'] not in saved['grants']
                        and self._first_correction_proof(tracked) is not None):
                    raise ProtocolError('Correction review checkpoint lost an established grant')
            if saved['attempts'] != attempts:
                raise ProtocolError('Correction review attempts were removed or altered')
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self._web_correction_state = disabled
            raise ProtocolError('Invalid correction review checkpoint: ' + str(error)) from error
        return restored
