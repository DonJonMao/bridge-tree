"""Web-only source reading with explicit search gaps and repair headroom.

The common reader still owns facts, sources, counter capture and certification.
A search gap is a completed *empty-evidence* read, never a sourced unresolved
issue. Legacy ``unresolved`` responses retain their original conservative scope.
"""
from copy import deepcopy

from hashlib import sha256

from . import joint_reading as common_reading
from .joint_reading import JointReader
from .reasoning import ProtocolError
from .webwalker_correction_review import CorrectionReviewMixin
from .transport import digest


WEB_ENTAILMENT_INSTRUCTION = '''
WEB SOURCE CHECK: exact entity/event/relation needs originals; audit them.
Publication/revision/effective/event dates differ; people/orgs aren't places.
Menu/topic labels and adjacent text prove no relation.
Another project's dates cannot transfer without source proof.
partial/unknown: real incomplete evidence within the requested scope.
Empty ordinary retrieval uses
no_relevant_evidence. Existing obligations still require legal model review of originals.
'''


WEB_READING_INSTRUCTION = '''
REQUIRED WEB RETRIEVAL PROTOCOL: every requested slot declares reading_status;
BOTH statuses require unresolved=[]. no_relevant_evidence means NO NEW admissible
observation: observations=[], no review/resolution IDs. Optional search_gaps lists
untried directions, only with this status. Old facts/obligations stay unchanged in
controller state; no need to repeat them. This search result is never a negative
fact or proof of absence. Do not cite an answer-free window as unknown; continue
the local bridge. evidence_assessment supplies NEW original-source-cited ordinary
observations. A genuine incomplete statement/ambiguity/conflict requires a named
partial/unknown row with exact source_ids, requested scope and reason; unknown
uses value=null. Never replace it with bare slot.unresolved or a resolution claim.
Old evidence obligations, failed drafts and counters remain mandatory. To settle
an offered issue, use evidence_assessment, explicitly review its original text
with sourced support/corrective/irrelevant observations, cover EVERY required
original source, and claim the offered resolution ID. Genuinely irrelevant text
may settle an earlier absence-only issue; never relabel real partial facts,
supporting text or counters irrelevant just to close them. Empty slots and
partial/unknown observations cannot settle evidence obligations: omit their IDs
from resolved_obligation_ids. Correcting a failed draft need not settle a source
issue. Preserve every required failed draft ID. Frozen rows, including partial/
unknown, must not be restated. Repairs may instead use currently offered
reviewed_observation_ids for immutable sourced rows, under all common source and
resolution checks. Terminal composition/audit use the ordinary protocol without
reading_status/search_gaps.
'''


WEB_REPAIR_INSTRUCTION = '''
An independent grounding review veto or uncertain verdict concerns proposed
entailment, never itself scoped partial/unknown evidence. The originals must
themselves establish the requested scope and genuine incompleteness for
partial/unknown. Re-read originals and choose a sourced disposition under the
same required ID only when those originals warrant it and current edit
permissions allow it.
WEB REPAIR FIELD CHECK: resolved_obligation_ids optionally claims settlement;
never copy obligation IDs as a checklist. unresolved=[] is wire format, not
settlement. With partial/unknown rows, omit resolution claims and leave issues
pending; invent no support/irrelevance. Frozen rows cannot be renamed/repeated;
old issues need no repeated row. Preserve/correct required failed drafts,
replacements and protected counters under offered IDs; empty slots cannot discard
them. Failed-batch format recovery and source-issue settlement remain separate.
'''


WEB_WINDOW_INSTRUCTION = '''
web_reading_context is controller bookkeeping, never evidence or review authority.
new_window_source_ids identifies newly offered window text; retained_mandatory_source_ids
identifies originals retained for existing facts/issues. Re-read required originals,
but do not copy an unchanged old issue into a new observation or settlement claim.
pending_source_issues stay unresolved without repetition. frozen_observations lists
immutable current-batch rows, not permission to cite them as reviewed observations.
Only explicit common review offers grant that permission. If new text adds no
admissible observation, report no_relevant_evidence even while old issues persist.
'''


WEB_REVIEW_CHECKLIST_INSTRUCTION = '''
web_review_checklist is a read-only projection of THIS request's existing offers,
not new review authority or evidence. Conditional coverage counts only currently
offered frozen IDs IF explicitly referenced. Only if claiming settlement of an
obligation in THIS response, review every sources_requiring_new_model_review
original with genuinely sourced new reviews where permitted. Otherwise leave its
ID unclaimed and its controller issue pending, without repeating frozen rows.
A frozen reference cannot cover another source. Only
claimable_failed_batch_ids may be claimed; retained blocked IDs grant no recovery.
Any displayed examples use invented IDs/text, never this response's IDs. Their
irrelevant stance applies only when the actual original warrants that assessment;
otherwise preserve the partial/unknown issue. empty_withdrawal_edit_scope is
read-only field guidance when no new observation exists; it settles no issue.
'''


WEB_SOURCE_REVIEW_INSTRUCTION = '''
web_source_review contains exact already-visible originals and read-only links to
prior judgments/issues/current frozen offers; it adds no evidence or permission.
document_scope_review pairs requested_scopes with each document's earliest visible
original, which may be mid-document. card_original_source_id refers only to this
request's cards[].original_source.id. Establish the requested entity identity and
event/relation from offered originals before transferring any attribute. Shared
site, partner, topic or question context alone establishes no identity bridge.
In an ordinary read, compare new originals with existing requested-slot bindings:
match the requested entity, event/relation and scope before taking an attribute.
An associated workflow, version or process can describe a different event.
known_observations marked model_judgment are prior model assessments, not semantic
certification of their source entailment. Reconsider them against the originals;
do not assume either the old or the new statement is correct. If a real conflict
warrants correction, use the existing legal contradiction/retract_ids mechanism
and separate replacement support only where this request permits it. A review
card itself never retracts or changes a value. During repair, retain the offered
edit scope and immutable current-batch rows. Only offered frozen references may
be used; each covers its own source_ids only. Support from a new original does
not review an old obligated original. Claim an obligation only after warranted
settled review of every required original; otherwise leave it pending. Do not
invent agreement or call genuine partial/counter evidence irrelevant to close it.
'''


WEB_GROUNDING_REVIEW_INSTRUCTION = '''
Independently check each candidate against the exact offered originals and its
requested scope. The candidate is an untrusted proposal, not an established fact.
Judge claim_to_check: it only explains the proposed stance, never evidence or authority.
Return entailed, not_entailed or uncertain, with a short reason, for each candidate_id.
These verdicts judge whether the proposed stance-specific claim is warranted;
entailed can approve irrelevant, not only a supported answer value.
For support, its cited originals must establish both the requested entity/event/
relation and the claimed attribute/value. Another project's attribute, a shared
partner/site/topic, or the question's presupposition supplies no identity bridge.
For partial/unknown, the originals must actually concern that requested scope and
contain genuine incomplete evidence; unrelated text is not scoped uncertainty.
For irrelevant, unrelated means these cited originals are inapplicable as evidence
for the requested scoped claim. It does not claim that the requested subject or
attribute itself is absent or inapplicable in reality.
Originals explicitly describing a different entity/event/relation, without an
observed identity bridge, can warrant this stance; they need not mention or
negate the requested subject. Different labels alone do not establish distinct
subjects; use the offered context to judge identity, and limit the inapplicability
conclusion to the cited originals. Missing an
attribute while still concerning the requested scope does not by itself warrant
irrelevant. Preserve genuine scoped support, partial evidence and counterevidence.
For contradiction, check the originals and the offered target claim:
the evidence must warrant that specific retraction, not merely a different value.
Supported parents are grounding inputs only at their supplied scope and versions.
Prior claims are not certified evidence. No replacement facts, new sources,
retractions, settlement claims or permission decisions may be returned.
'''


WEB_GROUNDING_CLAIMS = {
    'support': 'The cited originals establish the complete proposed value for the requested '
               'entity/event/relation and scope.',
    'partial': 'The cited originals concern the requested entity/event/relation and scope '
               'and contain genuine incomplete evidence, rather than unrelated text or mere answer absence.',
    'unknown': 'The cited originals concern the requested entity/event/relation and scope '
               'and contain genuine uncertainty, rather than unrelated text or mere answer absence.',
    'irrelevant': 'These cited originals are inapplicable as evidence for the requested scoped attribute. '
                  'This claim concerns these cited spans, not whether the requested subject or attribute '
                  'itself exists or is applicable in reality. '
                  'Assess that inapplicability claim, not whether they support an answer. '
                  'Explicitly describing a different subject without an observed identity bridge can '
                  'warrant irrelevant: unrelated text is inapplicable here, even without mentioning or '
                  'negating the requested subject. Mere answer absence does not prove inapplicability '
                  'when the originals still concern the requested scope; reject this stance if it discards '
                  'genuine scoped support, partial evidence or counterevidence.',
    'contradiction': 'The cited originals warrant retracting the specific offered target claim '
                     'at its actual scope and parent versions; a different value alone is insufficient.'}


WEB_REVIEW_EXAMPLES = {
    'illustration_only_never_current_ids': True,
    'assume': {
        'sample_catalogue': 'Sample catalogue: a link to a specification, with no attribute claim or ambiguity.',
        'sample_specification': 'The sample item has the requested attribute: blue.',
        'offered_frozen_support': {'id': 'sample_fact', 'source_ids': ['sample_specification']},
        'offered_issue': {'id': 'sample_issue', 'source_ids': ['sample_catalogue']}},
    'valid_only_if_original_really_irrelevant': {
        'variable': 'sample_attribute', 'reading_status': 'evidence_assessment',
        'observations': [{'id': 'sample_catalogue_review', 'stance': 'irrelevant', 'value': None,
                          'source_ids': ['sample_catalogue'], 'entity_scope': 'sample item',
                          'time_scope': 'sample scope', 'parent_versions': {}, 'retract_ids': [],
                          'reason': 'This original is only a navigation link, with no attribute claim or ambiguity.'}],
        'unresolved': [], 'reviewed_observation_ids': ['sample_fact'],
        'resolved_obligation_ids': ['sample_issue']},
    'invalid_missing_original_review': {
        'variable': 'sample_attribute', 'reading_status': 'evidence_assessment',
        'observations': [], 'unresolved': [], 'reviewed_observation_ids': ['sample_fact'],
        'resolved_obligation_ids': ['sample_issue']}}


WEB_REPAIR_EDIT_SCOPE_INSTRUCTION = '''
web_repair_edit_scope only describes this request's existing runtime permissions.
For named_only slots use only writable_observation_ids; retain every required ID
and protected counter, and omit frozen rows. Protected rows describe relations,
never extra writable IDs. Do not add a replacement support ID.
If original evidence warrants a counter, correct its existing ID with value=null
and real retract_ids. A separate new support needs a later ordinarily authorized
read; this promises neither a later call nor release of old failed-batch markers.
Whole-slot permission applies only to that variable; no source or review authority
is added. All original semantic, coverage and resolution checks still apply.
'''


WEB_EMPTY_REPAIR_INSTRUCTION = '''
This repair has only wildcard slot failures; no mandatory draft/counter/whole-value
or durable review. With NO NEW observation, correct using
reading_status=no_relevant_evidence, observations=[], unresolved=[], no review/
resolution IDs. Withdraw only this call's invalid claim;
the frozen rows and the controller's evidence obligations remain unchanged.
'''


# This adapter reconciles only the known ordinary-Web wire-format conflicts.
# Pin complete common segments and their selected composition: common changes
# require an explicit review, never silently discard a new or modified instruction.
_WEB_COMMON_SEGMENT_SHA256 = {
    'SYSTEM': '679b21862b858724263ef3d587d3e9f8528a73becd347a08df2029baf553bb46',
    'COLUMNAR_INSTRUCTION': '9ca4109a13005a8621bec0ae91bdb9a07198beca2f751e1e97a0dd683bbba4d2',
    'FROZEN_IDS_INSTRUCTION': '64c50e319587aed9f4d3a9c21fa9b2d8f46812674b89ffd270a0618a909f0572',
    'OBLIGATION_REVIEW_INSTRUCTION': '48182174acf308e0c5feee64c813d1536a983b49d239618623d7c4c1bb06bc0d',
    'WHOLE_VALUE_REVIEW_INSTRUCTION': '6fe25dcedb8a5ad71f84926f60adf52fa7defa550d5d4a1195e9732bfb734db6',
    'WHOLE_VALUE_REFERENCE_INSTRUCTION': '076b05845255829602175aa5d437c0f676b47ef9e34f8b07a2bda925fb796a06',
    'FAILED_BATCH_REVIEW_INSTRUCTION': '4a13f9c58d18d5cf2981bb64487bf9ef29635058b45cf15dcff6ea1f5caa9ba7',
    'OBSERVATION_TABLE_INSTRUCTION': 'd755d1eeb582e07281ef77b00fbc29ca826b3059b052ce5b5454b36e57361468',
}

_WEB_COMMON_REPLACEMENTS = {
    'SYSTEM': (
        ('Return one slot per requested variable, with observations\nand unresolved descriptions.',
         'Return one slot per requested variable, with observations and unresolved=[].'),
        ('proof, or partial/unresolved if no such proof exists.',
         'proof, or a named sourced review with value=null and unresolved=[] if no such\nproof exists. Use partial/unknown only for genuine requested-scope incomplete\nevidence; use irrelevant only when the original warrants it and current repair\npermissions allow. Preserve required IDs, originals and protected counters.'),
        ('Use its\nentity_scope and time_scope strings exactly only when that scope actually applies;\notherwise return unknown/irrelevant.',
         'Use its\nentity_scope and time_scope strings exactly only when the original applies; never\ntransfer another entity/event into the requested scope. A new window containing\nonly another entity/event and no applicable observation uses no_relevant_evidence\nwith observations=[] and unresolved=[]. partial/unknown requires genuine incomplete\nevidence about the requested entity/event within that scope. Required failed draft\nIDs, protected counters and old source obligations retain their existing review\nrequirements; an empty slot cannot discard or settle them.'),
        ('an independently supported value, a partial/unknown observation, or slot.unresolved\ndescriptions.',
         'an independently supported value or a named sourced partial/unknown observation\nwith value=null and unresolved=[].'),
        ('Already validated observations are frozen and must not be restated or changed.',
         'Already validated observations within this current batch are frozen during its\nrepairs and must not be restated or changed. Prior known_observations remain\nsubject to the legal source-grounded contradiction/retract_ids mechanism.'),
        ('Correct that draft under the same ID or preserve sourced partial/unknown evidence;\ndo not delete it or add other IDs unless a wildcard or replacement list permits it.',
         'Correct that draft under the same ID. Preserve genuine scoped partial/unknown\nevidence. When its original is genuinely inapplicable, a sourced irrelevant review\nwith value=null may correct that same ID only within the current edit permissions.\nNever relabel protected counters or genuine supporting/partial evidence irrelevant.\nDo not delete required IDs or add other IDs unless a wildcard or replacement list permits it.'),
    ),
    'WHOLE_VALUE_REVIEW_INSTRUCTION': (
        ('If the issue cannot be settled,\npreserve it in slot.unresolved with its original evidence. Agreement is not required.',
         'If the issue cannot be settled,\nretain each required draft ID and original source as a named partial/unknown\nobservation with value=null and unresolved=[]. The controller issue stays pending.\nAgreement is not required.'),
    ),
    'OBLIGATION_REVIEW_INSTRUCTION': (
        ('Keep partial/unknown evidence and unresolved issues when appropriate.',
         'Keep genuine partial/unknown evidence as named sourced observations with\nvalue=null and unresolved=[]; the controller issue stays pending.'),
        ('review all required sources, and retain every counter, partial or unresolved\nissue.',
         'review all required sources, and retain every counter and genuine partial/unknown\nobservation. Unsettled controller issues stay pending; unresolved=[].'),
    ),
    'FAILED_BATCH_REVIEW_INSTRUCTION': (
        ('If its meaning still cannot be established, return the\nsourced partial/unknown review and its unresolved issue; do not invent agreement.',
         'If its meaning still cannot be established, return the\nnamed sourced partial/unknown review with value=null and unresolved=[]; the\ncontroller source issue stays pending. Failed-format recovery need not settle\nthat source issue; do not invent agreement.'),
    ),
}


def _web_retrieval_common_system(data, system):
    """Reconcile known common wording without changing source or review authority."""
    if data.get('personal_response_selection') or data.get('public_options') is not None:
        raise ProtocolError('Unexpected common branch in ordinary Web retrieval')
    names = ['SYSTEM']
    if 'source_span_columns' in data:
        names.append('COLUMNAR_INSTRUCTION')
    scope = data.get('repair_scope', {})
    if scope.get('frozen_observation_ids'):
        names.append('FROZEN_IDS_INSTRUCTION')
    if any('obligation_review_sources' in entry or 'frozen_observation_reviews' in entry
           for entry in scope.get('failed', [])):
        names.append('OBLIGATION_REVIEW_INSTRUCTION')
    if scope.get('whole_value_reviews'):
        names.append('WHOLE_VALUE_REVIEW_INSTRUCTION')
        if any('known_observation_ids' in group for group in scope['whole_value_reviews']):
            names.append('WHOLE_VALUE_REFERENCE_INSTRUCTION')
    if data.get('failed_batch_reviews'):
        names.append('FAILED_BATCH_REVIEW_INSTRUCTION')
        if any(record.get('whole_value_reviews') for record in data['failed_batch_reviews']):
            names.append('WHOLE_VALUE_REVIEW_INSTRUCTION')
    if 'known_observation_columns' in data:
        names.append('OBSERVATION_TABLE_INSTRUCTION')
    segments = [getattr(common_reading, name) for name in names]
    if system != ''.join(segments):
        raise ProtocolError('Ordinary Web common instruction composition changed')
    result = []
    for name, segment in zip(names, segments):
        if sha256(segment.encode()).hexdigest() != _WEB_COMMON_SEGMENT_SHA256[name]:
            raise ProtocolError('Ordinary Web common instruction source changed: ' + name)
        for old, new in _WEB_COMMON_REPLACEMENTS.get(name, ()):
            if segment.count(old) != 1:
                raise ProtocolError('Ordinary Web instruction replacement count changed: ' + name)
            segment = segment.replace(old, new, 1)
        result.append(segment)
    return ''.join(result)


class WebJointReader(CorrectionReviewMixin, JointReader):
    def __init__(self, engine, state):
        super().__init__(engine, state)
        self.web_search_gaps = []
        self.web_capacity_admissions = []
        self._web_headroom_candidates = {}
        self._selected_web_headroom = None
        self.web_paid_recoveries = []
        self._selected_web_paid_recovery = None
        self._active_web_paid_recovery = None
        self.web_navigation_reads = []
        self._web_navigation_nonempty_slots = {}
        self._web_navigation_exposure_batches = {}
        self.web_single_shot_reads = []
        self.web_source_attempts = []
        self._selected_web_single_shot = None
        self._active_web_single_shot = None
        self._web_grounding_decisions = None
        self._web_grounding_context = None

    def _read(self, *args, **kwargs):
        # This mode authorizes one selected batch, never a later read/audit.
        self._selected_web_paid_recovery = None
        self._active_web_paid_recovery = None
        self._selected_web_single_shot = None
        self._active_web_single_shot = None
        self._web_navigation_nonempty_slots = {}
        self._web_navigation_exposure_batches = {}
        # Request-local semantic vetoes, never persisted review authority.
        self._web_grounding_decisions = {}
        first_gap, first_batch = len(self.web_search_gaps), len(self.batches)
        first_exposure = len(self.source_exposures)
        try:
            return super()._read(*args, **kwargs)
        finally:
            self._accept_navigation_reads(first_gap, first_batch, first_exposure)
            requests = {record['logical_call_index']: record for record in self.e.reasoner.requests}
            for batch_index in range(first_batch, len(self.batches)):
                calls = [exposure['logical_call_index'] for index, exposure in enumerate(self.source_exposures)
                         if self._web_navigation_exposure_batches.get(index) == batch_index
                         and exposure.get('logical_call_index') in requests]
                if calls:
                    call = calls[-1]
                    self.batches[batch_index].update(
                        input_tokens=requests[call]['input_tokens_local'], read_logical_call_index=call)
                    self.e.event({'event': 'web_reading_input_accounted', 'batch_index': batch_index,
                                  'read_logical_call_index': call,
                                  'input_tokens': requests[call]['input_tokens_local']})
            self._selected_web_paid_recovery = None
            self._active_web_paid_recovery = None
            self._selected_web_single_shot = None
            self._active_web_single_shot = None
            self._web_grounding_decisions = None
            self._web_grounding_context = None

    def _grounding_key(self, row):
        return digest({'observation': row, 'review_context': self._web_grounding_context})

    def _observation(self, *args, **kwargs):
        # Common source, type, scope and offered-target checks always run first.
        row = super()._observation(*args, **kwargs)
        if self._web_grounding_decisions is not None:
            decision = self._web_grounding_decisions.get(self._grounding_key(row))
            if decision is not None and decision['verdict'] != 'entailed':
                raise ProtocolError('Independent original-source grounding review '
                                    + decision['verdict'] + ': ' + decision['reason'][:160])
        return row

    def _review_grounding_candidates(self, response, data, read_call_index):
        """One paid independent veto before common validation can freeze a row.

        The raw response is retained. A veto is a named failure in the existing
        repair loop, never a replacement stance, empty read or permission grant.
        """
        if self._web_grounding_decisions is None or not self._search_gap_scope(data):
            return
        # A changed definition, neighbour, parent or target changes the review.
        # No semantic verdict is reused across reading/repair requests.
        self._web_grounding_decisions.clear()
        self._web_grounding_context = digest({key: data.get(key) for key in (
            'source_spans', 'supported_parents', 'requested_scopes',
            'known_observations', 'program_revision')})
        visible = {source['id']: source for source in data['source_spans']}
        candidates = {}
        slots = response.get('slots', []) if isinstance(response, dict) else []
        for slot in slots if isinstance(slots, list) else []:
            if not isinstance(slot, dict) or slot.get('variable') not in data['variables']:
                continue
            rows = slot.get('observations', [])
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict) or not row.get('source_ids'):
                    continue
                try:
                    normalized = super()._observation(row, slot['variable'], visible, data['task'],
                        offered_route_ids={route['id'] for route in data['known_observations']})
                except (ValueError, KeyError, TypeError):
                    continue  # The common validator retains the structural failure.
                key = self._grounding_key(normalized)
                if key not in self._web_grounding_decisions:
                    candidate = {field: deepcopy(value) for field, value in normalized.items()
                                 if field != 'reason'}
                    candidate['source_ids'] = [self.e.mapper.source_aliases[source]
                                               for source in normalized['source_ids']]
                    candidates[key] = candidate
        if not candidates:
            return
        for key in candidates:
            self._web_grounding_decisions[key] = {
                'verdict': 'uncertain', 'reason': 'Independent source review unavailable.'}
        payload = {key: deepcopy(data[key]) for key in
                   ('original_question', 'requested_scopes', 'supported_parents', 'source_spans')}
        targets = {target for row in candidates.values() for target in row['retract_ids']}
        payload['retraction_targets'] = [
            {key: deepcopy(value) for key, value in row.items() if key != 'reason'}
            for row in data['known_observations'] if row['id'] in targets]
        payload['candidates'] = [{'candidate_id': key, 'observation': row,
                                  'claim_to_check': WEB_GROUNDING_CLAIMS[row['stance']]}
                                 for key, row in candidates.items()]
        schema = {'type': 'object', 'properties': {'reviews': {'type': 'array',
            'minItems': len(candidates), 'maxItems': len(candidates), 'items': {
                'type': 'object', 'properties': {
                    'candidate_id': {'type': 'string', 'enum': list(candidates)},
                    'verdict': {'type': 'string', 'enum': ['entailed', 'not_entailed', 'uncertain']},
                    'reason': {'type': 'string', 'minLength': 1}},
                'required': ['candidate_id', 'verdict', 'reason'], 'additionalProperties': False}}},
            'required': ['reviews'], 'additionalProperties': False}

        def validate(value):
            if not isinstance(value, dict) or set(value) != {'reviews'} or not isinstance(value['reviews'], list):
                raise ProtocolError('Grounding review requires one result per exact candidate')
            decisions = {}
            for result in value['reviews']:
                if (not isinstance(result, dict) or set(result) != {'candidate_id', 'verdict', 'reason'}
                        or result['candidate_id'] not in candidates or result['candidate_id'] in decisions
                        or result['verdict'] not in ('entailed', 'not_entailed', 'uncertain')
                        or not isinstance(result['reason'], str) or not result['reason'].strip()):
                    raise ProtocolError('Grounding review contains an invalid or duplicate result')
                decisions[result['candidate_id']] = {key: result[key] for key in ('verdict', 'reason')}
            if set(decisions) != set(candidates):
                raise ProtocolError('Grounding review omitted a candidate')
            return decisions

        before = self.e.reasoner.sequence
        read_response = self.e.reasoner.last_response
        error = None
        try:
            decisions = self.e.reasoner.request('web_grounding_review',
                WEB_GROUNDING_REVIEW_INSTRUCTION, payload, validate, schema,
                output_token_cap=min(1024, self.e.s['reasoning_output_tokens']))
            self._web_grounding_decisions.update(decisions)
        except Exception as exc:
            # The original read still reaches common draft capture on failure.
            error = type(exc).__name__
        finally:
            # Common failed-draft capture still processes the original read.
            # Sequence and the separate archived review remain monotonic/intact.
            self.e.reasoner.last_response = read_response
        self.e.event({'event': 'web_grounding_review_completed',
            'read_logical_call_index': read_call_index,
            'review_logical_call_index': self.e.reasoner.sequence if self.e.reasoner.sequence > before else None,
            'error_type': error,
            'decisions': {key: deepcopy(self._web_grounding_decisions[key]) for key in candidates}})

    def _accept_navigation_reads(self, first_gap, first_batch, first_exposure):
        """Archive completed empty slots as navigation hints, never facts."""
        for batch_index, batch in enumerate(self.batches[first_batch:], first_batch):
            if not batch.get('complete'):
                continue
            matching = [exposure for index, exposure in enumerate(
                            self.source_exposures[first_exposure:], first_exposure)
                        if exposure['query_identity'] == batch['identity']
                        and self._web_navigation_exposure_batches.get(index) == batch_index]
            for gap in self.web_search_gaps[first_gap:]:
                if gap['query_identity'] != batch['identity']:
                    continue
                # Repairs request only failed variables. Another slot's later
                # repair does not replace this slot's already completed read.
                slot_exposures = [exposure for exposure in matching
                                  if gap['variable'] in exposure['variables']]
                if (not slot_exposures
                        or slot_exposures[-1].get('request_status') != 'returned'
                        or gap['logical_call_index'] != slot_exposures[-1]['logical_call_index']
                        or gap['request_identity'] != slot_exposures[-1]['request_identity']):
                    continue
                source_ids = {source['source']['source_id'] if 'source' in source else source['source_id']
                              for source in slot_exposures[-1]['sources']}
                if set(gap['source_ids']) != source_ids:
                    continue
                # Valid/frozen rows and unresolved drafts accumulate within a
                # slot across repairs. Its final empty response cannot relabel
                # that work as an empty read; successful other slots may still
                # supply their own independent navigation hints.
                if any(gap['variable'] in self._web_navigation_nonempty_slots.get(
                        exposure['logical_call_index'], set()) for exposure in slot_exposures):
                    continue
                record = {**deepcopy(gap), 'doc_ids': list(dict.fromkeys(
                    source['doc_id'] for source in self.e.mapper.sources.values()
                    if source['source_id'] in source_ids))}
                if record not in self.web_navigation_reads:
                    self.web_navigation_reads.append(record)

    def navigation_feedback(self, node_id, identity=None):
        """Read-only, same-query feedback for choosing observed hyperlinks."""
        query_identity = (identity if isinstance(identity, str) else digest(identity)
                          if identity is not None else None)
        reads = [deepcopy(row) for row in self.web_navigation_reads
                 if row['task_id'] == node_id
                 and (query_identity is None or row['query_identity'] == query_identity)]
        return {'protocol': 'web_reading_feedback_v1',
                'evidence_semantics': 'navigation_hints_not_facts',
                'query_identity': query_identity,
                'accepted_empty_reads': reads,
                'assessed_doc_ids': list(dict.fromkeys(doc for row in reads for doc in row['doc_ids']))}

    def navigation_feedback_projection(self, node_id, identity=None):
        """Group accepted empty-read metadata for navigation; never change evidence.

        The raw per-variable archive is retained by navigation_feedback(). A
        shared paid source exposure is presented once, with its original page
        coordinates and actual URL/title rather than repeated opaque span IDs.
        This is a read-only hint, not a fact, absence proof or review permission.
        """
        raw = self.navigation_feedback(node_id, identity=identity)
        sources = {source['source_id']: source for source in self.e.mapper.sources.values()}
        groups, projected = {}, []
        raw_fields = {'variable', 'reading_status', 'search_gaps', 'query_identity',
                      'task_id', 'request_identity', 'logical_call_index', 'source_ids', 'doc_ids'}
        passthrough = 0
        for row in raw['accepted_empty_reads']:
            # Only the closed, pure-navigation archive format is lossy-projectable.
            # Future/required row fields remain verbatim and non-optional.
            if (not isinstance(row, dict) or set(row) != raw_fields
                    or row['reading_status'] != 'no_relevant_evidence'
                    or any(not isinstance(row[field], str) for field in
                           ('variable', 'query_identity', 'task_id', 'request_identity'))
                    or type(row['logical_call_index']) is not int or row['logical_call_index'] < 0
                    or any(not isinstance(row[field], list)
                           or any(not isinstance(value, str) for value in row[field])
                           for field in ('source_ids', 'doc_ids', 'search_gaps'))):
                projected.append(deepcopy(row))
                passthrough += 1
                continue
            source_ids = sorted(set(row['source_ids']))
            key = digest([row['query_identity'], row['task_id'], row['request_identity'],
                          row['logical_call_index'], source_ids])
            if key not in groups:
                documents = {}
                unmapped = 0
                for source_id in source_ids:
                    source = sources.get(source_id)
                    if source is None:
                        unmapped += 1
                        continue
                    doc_id = source['doc_id']
                    if doc_id not in documents:
                        doc = self.e.docs.get(doc_id)
                        metadata = getattr(doc, 'metadata', {}) if doc is not None else {}
                        documents[doc_id] = {'doc_id': doc_id,
                            'url': metadata.get('url'), 'title': getattr(doc, 'title', None),
                            'source_ranges': [], 'source_count': 0}
                    document = documents[doc_id]
                    document['source_count'] += 1
                    document['source_ranges'].append([source['start'], source['end']])
                for document in documents.values():
                    document['source_ranges'].sort()
                groups[key] = {'query_identity': row['query_identity'], 'task_id': row['task_id'],
                    'request_identity': row['request_identity'],
                    'logical_call_index': row['logical_call_index'],
                    'raw_empty_read_record_count': 0, 'variable_hints': [],
                    'unique_source_count': len(source_ids), 'unmapped_source_count': unmapped,
                    'documents': list(documents.values()), 'grants_review_authority': False}
                projected.append(groups[key])
            group = groups[key]
            group['raw_empty_read_record_count'] += 1
            group['variable_hints'].append({'variable': row['variable'],
                'reading_status': row['reading_status'], 'search_gaps': deepcopy(row['search_gaps'])})
        return {**raw, 'protocol': 'web_reading_feedback_projection_v2',
            'source_protocol': raw['protocol'],
            'presentation': 'grouped_original_exposures_full_archive_retained',
            'grants_review_authority': False,
            'accepted_empty_read_count': len(raw['accepted_empty_reads']),
            'projected_empty_exposure_count': len(groups),
            'passthrough_empty_read_count': passthrough,
            'omitted_accepted_empty_read_count': 0, 'omitted_empty_exposure_count': 0,
            'assessed_doc_count': len(raw['assessed_doc_ids']),
            'accepted_empty_reads': projected}

    def _payload(self, step, query, variables, aliases, semantic=False, *, audit=False,
                 proof_projection=False):
        data = super()._payload(step, query, variables, aliases, semantic,
                                audit=audit, proof_projection=proof_projection)
        if self._search_gap_scope(data) and data.get('evidence_obligations'):
            mandatory = super()._payload(step, query, variables, [], semantic,
                                         audit=audit, proof_projection=proof_projection)
            window = list(dict.fromkeys(aliases))
            data['web_reading_context'] = {
                'evidence_semantics': 'bookkeeping_not_facts', 'grants_review_authority': False,
                'window_source_ids': window,
                'new_window_source_ids': [alias for alias in window
                                          if (self.current_identity, alias) not in self.read_states],
                'retained_mandatory_source_ids': [source['id'] for source in mandatory['source_spans']],
                'pending_source_issues': [
                    {'obligation_id': issue['id'], 'source_ids': list(issue['source_ids']),
                     'state': 'unresolved_controller_owned', 'ordinary_restatement_needed': False}
                    for issue in data.get('evidence_obligations', [])]}
        self._add_review_checklist(data)
        return data

    @staticmethod
    def _add_review_checklist(data):
        """Expose source-set arithmetic from current offers, never infer a review."""
        if not WebJointReader._search_gap_scope(data):
            return
        scope = data.get('repair_scope', {})
        if not (data.get('evidence_obligations') or data.get('failed_batch_reviews')
                or scope.get('frozen_observation_ids')):
            return
        offers = {}
        for entry in scope.get('failed', []):
            offer = entry.get('frozen_observation_reviews', {})
            rows = list(offer.get('observations', []))
            for identifier in offer.get('slot_observation_ids', []):
                matching = [row for row in entry.get('slot', {}).get('observations', [])
                            if isinstance(row, dict) and row.get('id') == identifier]
                if len(matching) == 1:
                    rows.append(matching[0])
            for row in rows:
                key = (entry['variable'], row['id'])
                description = {'variable': key[0], 'id': key[1], 'stance': row['stance'],
                               'source_ids': list(row['source_ids']),
                               'can_contribute_to_settled_source_coverage':
                                   row['stance'] in ('support', 'contradiction', 'irrelevant')}
                offers.setdefault(key, []).append(description)
        # Conflicting/duplicate descriptions cannot create reference authority.
        offered = [rows[0] for rows in offers.values()
                   if all(row == rows[0] for row in rows)]
        obligations = []
        for issue in data.get('evidence_obligations', []):
            required = list(dict.fromkeys(issue['source_ids']))
            reference_sources = {source for row in offered if row['variable'] == issue['variable']
                                 and row['can_contribute_to_settled_source_coverage']
                                 for source in row['source_ids']}
            obligations.append({
                'obligation_id': issue['id'], 'variable': issue['variable'],
                'required_original_source_ids': required,
                'source_ids_covered_only_if_frozen_rows_explicitly_referenced': [
                    source for source in required if source in reference_sources],
                'sources_requiring_new_model_review': [
                    source for source in required if source not in reference_sources],
                'new_review_required_only_if_settlement_claimed': True,
                'settlement_still_requires_valid_sourced_review_and_explicit_claim': True})
        frozen = [{'variable': variable, 'id': identifier}
                  for variable, identifiers in scope.get('frozen_observation_ids', {}).items()
                  for identifier in identifiers]
        checklist = {
            'evidence_semantics': 'bookkeeping_not_facts', 'grants_review_authority': False,
            'offered_frozen_observations': offered,
            'frozen_ids_without_reference_permission': [row for row in frozen
                if (row['variable'], row['id']) not in {(offer['variable'], offer['id']) for offer in offered}],
            'obligations': obligations,
            'claimable_failed_batch_ids': [record['id'] for record in data.get('failed_batch_reviews', [])
                                          if record.get('review_allowed') is True],
            'blocked_failed_batch_ids': [record['id'] for record in data.get('failed_batch_reviews', [])
                                        if record.get('review_allowed') is not True]}
        example_variables = [variable for variable in data.get('requested_slots', data.get('variables', {}))
                             if any(issue['variable'] == variable for issue in obligations)
                             and any(row['variable'] == variable and row['stance'] == 'support'
                                     for row in offered)]
        if example_variables:
            checklist['invented_response_examples'] = deepcopy(WEB_REVIEW_EXAMPLES)
            checklist['invented_response_examples']['applicable_variables'] = example_variables
        if WebJointReader._empty_repair_allowed(data):
            failed_variables = {entry['variable'] for entry in scope['failed']}
            checklist['empty_withdrawal_edit_scope'] = {
                'read_only': True, 'condition': 'no_new_admissible_observation',
                'variables': [variable for variable in data.get('requested_slots', data.get('variables', {}))
                              if variable in failed_variables],
                'reading_status': 'no_relevant_evidence',
                'empty_fields': ['observations', 'unresolved'],
                'omit_fields': ['reviewed_observation_ids', 'resolved_obligation_ids',
                                'resolved_failed_batch_ids'],
                'controller_evidence_and_issues_unchanged': True}
        data['web_review_checklist'] = checklist

    def _wire_candidates(self, data):
        # Frozen rows are established after the canonical payload is built.
        # Add a lossless wire-only description; this grants no review offers.
        wire_data = deepcopy(data)
        wire_data.pop('web_reading_protocol_diagnostics', None)
        diagnostics = self._source_reference_repair_diagnostics(wire_data)
        if diagnostics:
            wire_data['web_reading_protocol_diagnostics'] = {
                'read_only': True, 'grants_review_authority': False,
                'repair_edit_scope_unchanged': True, 'errors': diagnostics}
        if (self._search_gap_scope(wire_data)
                and wire_data.get('repair_scope', {}).get('frozen_observation_ids')):
            scope = wire_data['repair_scope']
            wire_data.setdefault('web_reading_context', {})['frozen_observations'] = [
                {'variable': variable, 'id': identifier,
                 'immutable': True, 'grants_review_authority': False}
                for variable, identifiers in scope.get('frozen_observation_ids', {}).items()
                for identifier in identifiers]
        # The common reader creates each repair after _payload. Recompute from
        # its actual current offers rather than retaining the initial checklist.
        self._add_review_checklist(wire_data)
        self._add_source_review_cards(wire_data)
        edits = self._repair_edit_scope(wire_data)
        if edits:
            wire_data['web_repair_edit_scope'] = {
                'read_only': True, 'grants_review_authority': False,
                'historical_marker_authorization_unchanged': True, 'slots': edits}
        candidates = super()._wire_candidates(wire_data)
        # Presentation order only: canonical payloads/request identities retain
        # their original structure, and all added bytes are counted normally.
        return tuple(({ 'web_source_review': wire['web_source_review'],
                        **{key: value for key, value in wire.items()
                           if key != 'web_source_review'}}, system)
                     if 'web_source_review' in wire else (wire, system)
                     for wire, system in candidates)

    @staticmethod
    def _add_source_review_cards(data):
        """Repeat visible originals beside existing references, without judging them.

        Keep this in the wire candidate so all duplicated original text participates
        in the production capacity checks. Canonical payloads and offers are intact.
        """
        data.pop('web_source_review', None)
        if not WebJointReader._search_gap_scope(data):
            return
        requested = set(data.get('requested_slots', data.get('variables', {})))
        references = {}

        def attach(source_ids, kind, reference):
            for source_id in dict.fromkeys(source_ids):
                groups = references.setdefault(source_id, {
                    'known_observation_refs': [], 'obligation_refs': [],
                    'offered_frozen_refs': []})
                if reference not in groups[kind]:
                    groups[kind].append(deepcopy(reference))

        for row in data.get('known_observations', []):
            if row.get('variable') in requested:
                attach(row.get('source_ids', []), 'known_observation_refs',
                       {key: deepcopy(row[key]) for key in
                        ('variable', 'id', 'stance', 'semantic_status', 'revoked') if key in row})
        for issue in data.get('evidence_obligations', []):
            if issue.get('variable') in requested:
                attach(issue.get('source_ids', []), 'obligation_refs',
                       {'variable': issue['variable'], 'id': issue['id']})
        # Derive references from current offers even if a caller reuses an old
        # wire projection whose checklist no longer describes this request.
        current = {key: value for key, value in data.items() if key != 'web_review_checklist'}
        WebJointReader._add_review_checklist(current)
        for row in current.get('web_review_checklist', {}).get('offered_frozen_observations', []):
            if row.get('variable') in requested:
                attach(row.get('source_ids', []), 'offered_frozen_refs', row)
        cards = []
        seen = set()
        for source in data.get('source_spans', []):
            source_id = source['id']
            if source_id in references and source_id not in seen:
                cards.append({'original_source': deepcopy(source), **references[source_id]})
                seen.add(source_id)
        earliest = {}
        for source in data.get('source_spans', []):
            previous = earliest.get(source['doc_id'])
            if previous is None or source['start'] < previous['start']:
                earliest[source['doc_id']] = source
        documents = []
        for doc_id, source in earliest.items():
            original = ({'card_original_source_id': source['id']} if source['id'] in seen
                        else deepcopy(source))
            documents.append({'doc_id': doc_id, 'earliest_visible_original': original})
        if cards or documents:
            data['web_source_review'] = {
                'read_only': True, 'grants_review_authority': False,
                'existing_permissions_unchanged': True,
                'document_scope_review': {
                    'requested_scopes': deepcopy(data.get('requested_scopes', {})),
                    'documents': documents},
                'cards': cards}

    @staticmethod
    def _source_reference_repair_diagnostics(data):
        """Explain a current Web rejection without changing its captured draft.

        Invalid typed Web slots intentionally reach the common reader intact,
        which captures named/counter drafts before reporting a malformed slot.
        Recover only the missing source-reference detail for the repair wire;
        this is neither a second validator nor a review or edit permission.
        """
        if not WebJointReader._search_gap_scope(data):
            return []
        errors = []
        for failure_index, failed in enumerate(data.get('repair_scope', {}).get('failed', [])):
            slot = failed.get('slot')
            if (not isinstance(slot, dict) or slot.get('reading_status') != 'evidence_assessment'
                    or not isinstance(slot.get('observations'), list)):
                continue
            for observation_index, row in enumerate(slot['observations']):
                if not isinstance(row, dict):
                    continue
                sources = row.get('source_ids')
                if (not isinstance(sources, list) or not sources
                        or any(not isinstance(source, str) or not source for source in sources)):
                    errors.append({
                        'variable': slot.get('variable'), 'observation_id': row.get('id'),
                        'path': (f'repair_scope.failed[{failure_index}].slot.'
                                 f'observations[{observation_index}].source_ids'),
                        'error': ('evidence_assessment requires a non-empty list of '
                                  'non-empty original-source alias strings.')})
        return errors

    @staticmethod
    def _search_gap_scope(data):
        return (data.get('task', {}).get('execution') == 'retrieval'
                and not any(key in data for key in
                            ('audit_instruction', 'public_output_question', 'terminal_repair')))

    @staticmethod
    def _system(data):
        system = JointReader._system(data)
        if WebJointReader._search_gap_scope(data):
            system = _web_retrieval_common_system(data, system)
        system += WEB_ENTAILMENT_INSTRUCTION
        if WebJointReader._search_gap_scope(data):
            system += WEB_READING_INSTRUCTION
            if data.get('web_reading_context'):
                system += WEB_WINDOW_INSTRUCTION
            if data.get('web_review_checklist'):
                system += WEB_REVIEW_CHECKLIST_INSTRUCTION
            if data.get('web_repair_edit_scope'):
                system += WEB_REPAIR_EDIT_SCOPE_INSTRUCTION
            if data.get('repair_scope') or data.get('evidence_obligations'):
                system += WEB_REPAIR_INSTRUCTION
            if data.get('repair_scope'):
                if WebJointReader._empty_repair_allowed(data):
                    system += WEB_EMPTY_REPAIR_INSTRUCTION
            if data.get('web_source_review'):
                system += WEB_SOURCE_REVIEW_INSTRUCTION
        if 'audit_instruction' in data:
            system += ('\nAudit must cover EVERY attribute requested by original_question and each '
                       'output_contract.fields entry. Correct individual facts do not establish a '
                       'complete terminal answer; withhold supported if an attribute is missing.\n')
        return system

    @staticmethod
    def _empty_repair_allowed(data):
        scope = data.get('repair_scope', {})
        failures = scope.get('failed', [])
        return bool(failures and all(entry.get('id') == '*' for entry in failures)
                    and not any(entry.get('observation') is not None or entry.get('observations')
                                for entry in failures)
                    and not scope.get('invalid_response')
                    and not scope.get('whole_value_reviews')
                    and not any(entry.get(key) for entry in failures for key in
                                ('replacement_observations', 'required_counter_observations'))
                    and not any(review.get('review_allowed')
                                for review in data.get('failed_batch_reviews', [])))

    @staticmethod
    def _repair_edit_scope(data):
        """Project current same-variable edit permissions, never create offers."""
        if not WebJointReader._search_gap_scope(data):
            return []
        scope = data.get('repair_scope', {})
        failed = scope.get('failed', [])
        if not failed:
            return []
        result = []
        for variable in data.get('requested_slots', data.get('variables', {})):
            entries = [entry for entry in failed if entry['variable'] == variable]
            if not entries:
                continue
            wildcard = any(entry['id'] == '*' for entry in entries)
            frozen = set(scope.get('frozen_observation_ids', {}).get(variable, []))
            for entry in entries:
                offer = entry.get('frozen_observation_reviews', {})
                frozen.update(offer.get('slot_observation_ids', []))
                frozen.update(row['id'] for row in offer.get('observations', []))
            required, originals, counters = set(), set(), []
            for entry in entries:
                replacements = entry.get('replacement_observations', [])
                if replacements:
                    originals.add(entry['id'])
                    required.update(row['id'] for row in replacements)
                elif entry['id'] != '*':
                    required.add(entry['id'])
                for row in entry.get('required_counter_observations', []):
                    if row not in counters:
                        counters.append(deepcopy(row))
            # A pure wildcard has no extra ID edit restrictions. The common
            # whole-slot schema/validator already expresses its permission;
            # projecting an empty scope would only inflate real repair wire
            # and synthetic capacity forecasts. Keep every concrete named,
            # frozen, replacement or protected-counter restriction intact.
            if wildcard and not (required or originals or frozen or counters):
                continue
            result.append({
                'variable': variable, 'mode': 'whole_slot' if wildcard else 'named_only',
                'additional_unique_observation_ids_allowed': wildcard,
                'writable_observation_ids': sorted(required - frozen),
                'required_observation_ids': sorted(required - frozen),
                'replaced_duplicate_ids': sorted(originals),
                'frozen_observation_ids': sorted(frozen),
                'protected_counter_observations': counters,
                'new_support_requires_later_ordinary_read': not wildcard})
        return result

    @staticmethod
    def _schema(data):
        schema = JointReader._schema(data)
        if not WebJointReader._search_gap_scope(data):
            return schema
        slot = schema['properties']['slots']['items']
        slot['properties']['reading_status'] = {
            'type': 'string', 'enum': ['no_relevant_evidence', 'evidence_assessment']}
        slot['required'].append('reading_status')
        slot['properties']['unresolved']['maxItems'] = 0
        slot['properties']['observations']['items']['properties']['source_ids']['minItems'] = 1
        slot['properties']['search_gaps'] = {
            'type': 'array', 'minItems': 1,
            'items': {'type': 'string', 'minLength': 1},
            'description': 'Untried search directions only; permitted with empty observations and unresolved.'}
        empty = {key: {'maxItems': 0} for key in
                 ('observations', 'unresolved', 'resolved_obligation_ids',
                  'resolved_failed_batch_ids', 'reviewed_observation_ids')
                 if key in slot['properties']}
        evidence = [{'properties': {'observations': {'minItems': 1}}}]
        if 'reviewed_observation_ids' in slot['properties']:
            evidence.append({'required': ['reviewed_observation_ids'],
                             'properties': {'reviewed_observation_ids': {'minItems': 1}}})
        slot.setdefault('allOf', []).append({
            'if': {'properties': {'reading_status': {'const': 'no_relevant_evidence'}}},
            'then': {'properties': empty},
            'else': {'anyOf': evidence, 'not': {'required': ['search_gaps']}}})
        if 'resolved_obligation_ids' in slot['properties']:
            # Mirror the existing core guard. Unknown/partial observations can
            # remain genuine issues, but cannot justify an obligation release.
            # A corrected failed draft is a separate kind of resolution.
            slot['allOf'].append({
                'if': {'required': ['resolved_obligation_ids'],
                       'properties': {'resolved_obligation_ids': {'minItems': 1}}},
                'then': {'properties': {
                    'reading_status': {'const': 'evidence_assessment'},
                    'observations': {'items': {'properties': {
                        'stance': {'enum': ['support', 'contradiction', 'irrelevant']}}}}}}})
        # The common runtime rejects new IDs in a named-only repair, even
        # though the shared general-purpose observation schema permits them.
        # Mirror the current same-variable offers without changing the parser.
        edits = {entry['variable']: entry for entry in WebJointReader._repair_edit_scope(data)}
        for branch in slot.get('oneOf', []):
            properties = branch['properties']
            edit = edits.get(properties['variable']['const'])
            if edit is None:
                continue
            observations = properties['observations']
            if edit['mode'] == 'named_only':
                allowed = edit['writable_observation_ids']
                rule = {'enum': allowed} if allowed else {'not': {}}
                observations['items'].setdefault('allOf', []).append({'properties': {'id': rule}})
            if edit['replaced_duplicate_ids']:
                observations['items'].setdefault('allOf', []).append({
                    'properties': {'id': {'not': {'enum': edit['replaced_duplicate_ids']}}}})
            for identifier in edit['required_observation_ids']:
                observations.setdefault('allOf', []).append({
                    'contains': {'properties': {'id': {'const': identifier}}, 'required': ['id']}})
        return schema

    @staticmethod
    def _gap_response(response, data):
        """Decode the required typed retrieval disposition without new facts.

        Invalid extensions remain on the original response. The core therefore
        captures its observation/counter drafts before rejecting the envelope,
        instead of an adapter exception bypassing that mandatory capture.
        """
        if not WebJointReader._search_gap_scope(data):
            return response, []
        rejected = deepcopy(response)
        if isinstance(rejected, dict) and isinstance(rejected.get('slots'), list):
            for slot in rejected['slots']:
                if isinstance(slot, dict) and 'reading_status' not in slot:
                    # The unmodified legacy shape would otherwise pass core
                    # validation. An undeclared adapter marker rejects it only
                    # AFTER the core has captured every named/counter draft.
                    slot['web_reading_protocol_error'] = 'Required reading_status is missing'
        if (not isinstance(response, dict)
                or set(response) - {'slots', 'final_prediction', 'semantic_answer', 'audit_verdict'}
                or not isinstance(response.get('slots'), list)):
            return rejected, []
        if ('final_prediction' in response
                and response['final_prediction'] is not None
                and not isinstance(response['final_prediction'], str)):
            return rejected, []
        if ('audit_verdict' in response
                and response['audit_verdict'] not in ('supported', 'unknown', 'conflict')):
            return rejected, []
        requested = set(data['variables'])
        seen, records = set(), []
        required = {'variable', 'observations', 'unresolved'}
        reviews = {'resolved_obligation_ids', 'resolved_failed_batch_ids', 'reviewed_observation_ids'}
        allowed = required | reviews | {'search_gaps', 'reading_status'}
        for slot in response['slots']:
            if (not isinstance(slot, dict) or not required <= set(slot) or set(slot) - allowed
                    or not isinstance(slot.get('variable'), str)
                    or slot['variable'] not in requested or slot['variable'] in seen
                    or not isinstance(slot['observations'], list)
                    or not isinstance(slot['unresolved'], list)
                    or slot['unresolved']):
                return rejected, []
            seen.add(slot['variable'])
            for key in reviews & set(slot):
                values = slot[key]
                if (not isinstance(values, list) or any(not isinstance(value, str) for value in values)
                        or len(set(values)) != len(values)):
                    return rejected, []
            status = slot.get('reading_status')
            if status == 'no_relevant_evidence':
                gaps = slot.get('search_gaps', [])
                if (not isinstance(gaps, list)
                        or ('search_gaps' in slot and not gaps)
                        or any(not isinstance(gap, str) or not gap.strip() for gap in gaps)
                        or slot['observations'] or any(slot.get(key) for key in reviews)):
                    return rejected, []
                records.append({'variable': slot['variable'], 'reading_status': status,
                                'search_gaps': deepcopy(gaps)})
            elif status == 'evidence_assessment':
                rows = slot['observations']
                references = slot.get('reviewed_observation_ids', [])
                if ('search_gaps' in slot or (not rows and not references)
                        or any(not isinstance(row, dict)
                               or not isinstance(row.get('source_ids'), list) or not row['source_ids']
                               or any(not isinstance(source, str) or not source for source in row['source_ids'])
                               for row in rows)):
                    return rejected, []
            else:
                return rejected, []
        if seen != requested:
            return rejected, []
        decoded = deepcopy(response)
        for slot in decoded['slots']:
            slot.pop('search_gaps', None)
            slot.pop('reading_status')
        return decoded, records

    def _web_headroom(self, operation, data, *, fresh_sources=True):
        # An initial request can also be a paid recovery of a durable draft.
        # Its existing originals/drafts are already in data, but any newly
        # exposed text can still produce another failed response. Recovery is
        # therefore not an exemption from fresh-window repair forecasting.
        recovery = any(item.get('review_allowed')
                       for item in data.get('failed_batch_reviews', []))
        if (operation != 'joint_read' or not fresh_sources or not self._search_gap_scope(data)
                or data.get('repair_scope')
                or self.e.s['max_repairs_per_request'] <= bool(recovery)
                or self.e.ledger.remaining('json_repairs') <= bool(recovery)
                or self.e.ledger.remaining('llm') < self.e.s['reserved_audit_calls'] + 2):
            return None
        failed = []
        for variable in data['variables']:
            entry = {'variable': variable, 'id': '*', 'feedback': 'x' * 240,
                     'observation': None,
                     'slot': {'variable': variable, 'observations': [], 'unresolved': []}}
            obligations = [item for item in data.get('evidence_obligations', [])
                           if item['variable'] == variable]
            if obligations:
                # Coverage feedback repeats required/missing source aliases;
                # unlike the future draft, this growth is known before reading.
                entry['obligation_review_sources'] = [
                    {'obligation_id': item['id'],
                     'required_source_ids': list(item['source_ids']),
                     # A failed review may cite every other visible source
                     # while missing all required originals. Count that known
                     # coverage footprint as well as the missing originals.
                     'covered_source_ids': [source['id'] for source in data['source_spans']
                                            if source['id'] not in item['source_ids']],
                     'missing_source_ids': list(item['source_ids'])}
                    for item in obligations]
            # These are measurement-only empty shells. They grant no frozen
            # review authority; the common reader offers actual IDs later.
            entry['frozen_observation_reviews'] = {
                'slot_observation_ids': [], 'observations': []}
            failed.append(entry)
        forecast = {**data, 'repair_scope': {
            'failed': failed,
            'attempt': 1, 'previous_response_identity': '0' * 64,
            'invalid_response': ''}}
        count = self._estimate(operation + '_repair', forecast)
        output = self.e.s['reasoning_output_tokens']
        total = count + 2 * output + self.e.s['input_margin'] + 8
        return {'repair_forecast_input_tokens': count, 'unknown_draft_reserve': output,
                'repair_output_reserve': output, 'forecast_total_tokens': total,
                'context_tokens': self.e.s['context_tokens'],
                'within_budget': total <= self.e.s['context_tokens'],
                'durable_recovery': bool(recovery),
                'policy': 'scoped_repair_envelope_plus_one_unknown_draft_allowance_v2'}

    def _fresh_window_fits(self, operation, data, *, fresh_sources=True):
        if not super()._fresh_window_fits(operation, data, fresh_sources=fresh_sources):
            return False
        headroom = self._web_headroom(operation, data, fresh_sources=fresh_sources)
        if headroom is not None:
            self._web_headroom_candidates[digest(data)] = headroom
        return headroom is None or headroom['within_budget']

    def _fitting_prefix(self, operation, step, query, variables, pending, semantic, audit):
        self._web_headroom_candidates = {}
        self._selected_web_headroom = None
        self._selected_web_paid_recovery = None
        self._active_web_paid_recovery = None
        self._selected_web_single_shot = None
        self._active_web_single_shot = None
        if operation == 'joint_read' and step.get('execution') == 'retrieval' and not semantic and not audit:
            self._prioritize_discovery_regions(pending)
        try:
            aliases, consumed = super()._fitting_prefix(
                operation, step, query, variables, pending, semantic, audit)
            if consumed:
                data = self._payload(step, query, variables, aliases, semantic, audit=audit)
                identity = digest(data)
                if identity in self._web_headroom_candidates:
                    self._selected_web_headroom = (identity, self._web_headroom_candidates[identity])
            else:
                aliases, consumed = self._paid_recovery_prefix(
                    operation, step, query, variables, pending, semantic, audit)
                if not consumed:
                    aliases, consumed = self._single_shot_prefix(
                        operation, step, query, variables, pending, semantic, audit)
            return aliases, consumed
        finally:
            self._web_headroom_candidates = {}

    def _prioritize_discovery_regions(self, pending):
        """Schedule unoffered body text first without removing other work."""
        ranks = {'main': 0, 'content': 0, 'navigation': 2, 'utility_ui': 3, 'hidden_ui': 4}
        def priority(group):
            source = self.e.mapper.sources[group[0]]
            document = self.e.docs[source['doc_id']]
            regions = document.metadata.get('web_regions', [])
            overlap = [(max(0, min(source['end'], region['end']) - max(source['start'], region['start'])),
                        ranks.get(region.get('role'), 1)) for region in regions]
            return max(overlap, key=lambda item: item[0])[1] if overlap and max(x[0] for x in overlap) else 1
        positions = [index for index, group in enumerate(pending)
                     if group and (self.current_identity, group[0]) in self.discovery_frontier]
        ordered = sorted((pending[index] for index in positions), key=priority)
        for index, group in zip(positions, ordered):
            pending[index] = group

    def _paid_recovery_prefix(self, operation, step, query, variables, pending, semantic, audit):
        """Try one paid old-draft review only after every full forecast fails.

        The full original request must fit. No unknown-response workspace is
        promised: if this single response fails, the common reader retains it
        and all originals, and this batch buys no further local repair.
        """
        if (operation != 'joint_read' or semantic or audit or self.current_terminal_output
                or step.get('execution') != 'retrieval'):
            return [], 0
        common = {'query_identity': self.current_identity, 'task_id': step['output_slot'],
                  'policy': 'single_paid_durable_recovery_v1'}
        reason = 'no_new_source_authorized_failed_review'
        if (self.e.s['max_repairs_per_request'] <= 0
                or self.e.ledger.remaining('json_repairs') <= 0
                or self.e.ledger.remaining('llm') <= self.e.s['reserved_audit_calls']):
            reason = 'durable_recovery_budget_unavailable'
        else:
            # Ascending prefixes deliberately select the smallest new group.
            for size in range(1, len(pending) + 1):
                aliases = list(dict.fromkeys(a for group in pending[:size] for a in group))
                data = self._payload(step, query, variables, aliases, semantic, audit=audit)
                if not self._search_gap_scope(data) or self._failed_phase(data) != 'history':
                    continue
                forecast = self._web_headroom_candidates.get(digest(data))
                if forecast is None or forecast['within_budget']:
                    continue
                offered = []
                new_sources = set()
                candidate_sources = {self.e.mapper.sources[a]['source_id'] for a in aliases}
                for review in data.get('failed_batch_reviews', []):
                    record = self.failed_batch_reviews.get(review['id'])
                    if not review.get('review_allowed') or record is None:
                        continue
                    fresh = candidate_sources - set(record['seen_source_ids'])
                    if fresh:
                        offered.append(review['id'])
                        new_sources.update(fresh)
                # Parent changes or a renamed query alone cannot unlock this.
                if not offered:
                    continue
                if not super()._fits(operation, data):
                    reason = 'complete_recovery_request_exceeds_context'
                    continue
                selection = {**common, 'request_identity': digest(data),
                             'prefix_groups': size, 'source_count': len(data['source_spans']),
                             'failed_batch_ids': offered, 'new_source_ids': sorted(new_sources),
                             'base_input_tokens': self._estimate(operation, data),
                             'output_token_reserve': self.e.s['reasoning_output_tokens'],
                             'context_tokens': self.e.s['context_tokens'],
                             'additional_local_repairs_allowed': 0,
                             'rejected_full_forecast': deepcopy(forecast), 'status': 'selected'}
                self.web_paid_recoveries.append(selection)
                self._selected_web_paid_recovery = selection
                self.e.event({'event': 'web_paid_recovery_selected', **deepcopy(selection)})
                return aliases, size
        self.e.event({'event': 'web_paid_recovery_blocked', **common, 'reason': reason})
        return [], 0

    def _single_shot_context(self, data):
        """Scope/actual-parent identity without query names or source aliases."""
        values, _, _ = self.state.valid()
        parents = {variable: {'version': self.state.versions[variable],
                              'value': deepcopy(values.get(variable))}
                   for variable, declaration in self.state.program['variables'].items()
                   if declaration['demand'] in data['task']['inputs']}
        # Use the complete stable task-variable scope, not a chosen subset that
        # could turn the same material into a supposedly new paid window.
        variables = {variable: {'type': declaration['type'], 'scope': self.state.scope(variable)}
                     for variable, declaration in self.state.program['variables'].items()
                     if declaration['demand'] == data['task']['output_slot']}
        return {'task_id': data['task']['output_slot'], 'parent_bindings': parents,
                'variables': variables}

    def _single_shot_new_source_ids(self, data, aliases):
        context = self._single_shot_context(data)
        seen = {source for attempt in self.web_source_attempts
                if attempt['context'] == context for source in attempt['source_ids']}
        # Older source-exposure records also block reuse conservatively, even
        # if a caller imported them without the new parent-binding archive.
        for exposure in self.source_exposures:
            if (exposure['task_id'] == context['task_id']
                    and all(exposure['parent_versions'].get(variable) == binding['version']
                            for variable, binding in context['parent_bindings'].items())
                    and {digest(scope) for scope in exposure['scopes'].values()} & {
                        digest(scope) for scope in data['requested_scopes'].values()}):
                seen.update(source['source_id'] for source in exposure['sources'])
        return sorted({self.e.mapper.sources[alias]['source_id'] for alias in aliases} - seen)

    def _single_shot_prefix(self, operation, step, query, variables, pending, semantic, audit):
        """One paid fresh-window attempt when only future repair room is absent.

        No failed-batch permission is created here. All actual mandatory text
        and issues stay in the normal payload and validators; no later local
        repair is promised or charged for this selected batch.
        """
        if (operation != 'joint_read' or semantic or audit or self.current_terminal_output
                or step.get('execution') != 'retrieval'
                or self.e.ledger.remaining('llm') <= self.e.s['reserved_audit_calls']):
            return [], 0
        for size in range(1, len(pending) + 1):
            aliases = list(dict.fromkeys(alias for group in pending[:size] for alias in group))
            data = self._payload(step, query, variables, aliases, semantic, audit=audit)
            if (not self._search_gap_scope(data) or self._failed_phase(data) != 'history'
                    or data.get('repair_scope') or data.get('failed_batch_reviews')):
                continue
            forecast = self._web_headroom_candidates.get(digest(data))
            if forecast is None or forecast.get('within_budget') is not False:
                continue
            new_sources = self._single_shot_new_source_ids(data, aliases)
            if not new_sources:
                continue
            _, _, count = self._select_wire(operation, self._wire_candidates(data), self._schema(data))
            total = (count['count'] + self.e.s['reasoning_output_tokens']
                     + self.e.s['input_margin'] + 8)
            if count.get('token_count_is_estimate') is not False or total > self.e.s['context_tokens']:
                continue
            selection = {'policy': 'single_paid_fresh_window_v1', 'status': 'selected',
                         'query_identity': self.current_identity, 'task_id': step['output_slot'],
                         'request_identity': digest(data), 'context': self._single_shot_context(data),
                         'new_source_ids': new_sources, 'prefix_groups': size,
                         'base_input_tokens': count['count'], 'actual_total_tokens': total,
                         'output_token_reserve': self.e.s['reasoning_output_tokens'],
                         'context_tokens': self.e.s['context_tokens'],
                         'additional_local_repairs_allowed': 0,
                         'rejected_full_forecast': deepcopy(forecast)}
            self.web_single_shot_reads.append(selection)
            self._selected_web_single_shot = selection
            self.e.event({'event': 'web_single_shot_selected', **deepcopy(selection)})
            return aliases, size
        return [], 0

    def _repair_fits(self, operation, data, step, identity, attempt):
        active = self._active_web_single_shot
        if (active is not None and operation == 'joint_read_repair'
                and identity == active['query_identity']
                and step['output_slot'] == active['task_id'] and self._search_gap_scope(data)):
            active['local_repair_blocked'] = True
            self.e.event({'event': 'web_single_shot_local_repair_blocked',
                          'query_identity': identity, 'task_id': step['output_slot'],
                          'repair_attempt': attempt, 'policy': active['policy']})
            return False
        active = self._active_web_paid_recovery
        if (active is not None and operation == 'joint_read_repair'
                and identity == active['query_identity']
                and step['output_slot'] == active['task_id']
                and self._search_gap_scope(data)):
            active['local_repair_blocked'] = True
            self.e.event({'event': 'web_paid_recovery_local_repair_blocked',
                          'query_identity': identity, 'task_id': step['output_slot'],
                          'repair_attempt': attempt, 'policy': active['policy'],
                          'reason': 'single_paid_response_already_attempted'})
            # The common reader calls this before reserving another repair.
            return False
        return super()._repair_fits(operation, data, step, identity, attempt)

    def _preserve_unresolved_issues(self, response, data, identity):
        """A malformed Web envelope cannot erase an ordinary factual issue.

        Named observation drafts are captured by the common reader even when
        an envelope is invalid. Bare slot.unresolved strings have no draft ID,
        so preserve their conservative original-source scope before that
        rejection. No content-based interpretation, fact or resolution occurs.
        """
        slots = response.get('slots') if isinstance(response, dict) else None
        if not isinstance(slots, list):
            return
        reviews = {}
        for slot in slots:
            if (not isinstance(slot, dict) or not isinstance(slot.get('variable'), str)
                    or slot['variable'] not in data['variables']
                    or not isinstance(slot.get('unresolved'), list)):
                continue
            # Invalid non-string fields remain in the raw draft. Identifiable
            # string issues are retained even in a malformed containing list.
            issues = [issue for issue in slot['unresolved'] if isinstance(issue, str) and issue]
            if issues:
                review = reviews.setdefault(slot['variable'], {'observations': [], 'unresolved': []})
                review['unresolved'].extend(issues)
        if reviews:
            self._update_evidence_obligations(
                reviews, [], data,
                {(variable, '*'): 'Web response retains ordinary unresolved evidence before envelope validation'
                 for variable in reviews}, identity)

    def _request_with_exposure(self, operation, data, identity, wire, system, **options):
        # Reuse admission's measurement, never contact the tokenizer before
        # the common reader has registered attempted exposure or after a
        # successful response. Logging is not another fallible admission step.
        single_shot = self._selected_web_single_shot
        if single_shot is not None:
            if (single_shot['request_identity'] != digest(data)
                    or single_shot['query_identity'] != identity or operation != 'joint_read'
                    or single_shot['context'] != self._single_shot_context(data)
                    or data.get('failed_batch_reviews')):
                from .reasoning import InputOverflow
                raise InputOverflow('Selected single-shot window differs from the actual request')
            self._active_web_single_shot = single_shot
            self._selected_web_single_shot = None
            single_shot['status'] = 'started'
            self.e.event({'event': 'web_single_shot_started', **deepcopy(single_shot)})
        source_attempt = None
        if self._search_gap_scope(data):
            # Register before transport/counting. Failed or not-sent attempts
            # retain ownership too; no rollback creates fresh-read permission.
            source_attempt = {
                'context': self._single_shot_context(data),
                'source_ids': sorted({self.e.mapper.sources[source['id']]['source_id']
                                      for source in data['source_spans']}),
                'operation': operation, 'request_identity': digest(data),
                'status': 'attempted'}
            self.web_source_attempts.append(source_attempt)
        selection = self._selected_web_paid_recovery
        if (selection is not None and selection['request_identity'] == digest(data)
                and selection['query_identity'] == identity and operation == 'joint_read_repair'):
            self._active_web_paid_recovery = selection
            self._selected_web_paid_recovery = None
            selection['status'] = 'started'
            self.e.event({'event': 'web_paid_recovery_started', **deepcopy(selection)})
        # Batch completion appends its diagnostic only after every local repair.
        # This private index therefore groups all of one batch's exposures even
        # when a failed-slot repair narrows its original-source closure.
        self._web_navigation_exposure_batches[len(self.source_exposures)] = len(self.batches)
        try:
            raw = super()._request_with_exposure(operation, data, identity, wire, system, **options)
        except BaseException:
            if source_attempt is not None:
                source_attempt['status'] = 'failed_or_not_sent'
            if self._active_web_single_shot is not None:
                self._active_web_single_shot['status'] = 'request_failed'
            if self._active_web_paid_recovery is not None:
                self._active_web_paid_recovery['status'] = 'request_failed'
            raise
        if source_attempt is not None:
            source_attempt['status'] = 'response_received'
        if self._active_web_paid_recovery is not None:
            self._active_web_paid_recovery['status'] = 'response_received'
        if self._active_web_single_shot is not None:
            self._active_web_single_shot['status'] = 'response_received'
        slots = raw.get('slots', []) if isinstance(raw, dict) else []
        self._web_navigation_nonempty_slots[self.e.reasoner.sequence] = {
            slot['variable'] for slot in slots if isinstance(slot, dict)
            and isinstance(slot.get('variable'), str) and slot['variable'] in data['variables']
            and any(slot.get(field) for field in ('observations', 'unresolved',
                'resolved_obligation_ids', 'resolved_failed_batch_ids', 'reviewed_observation_ids'))
        } if isinstance(slots, list) else set(data['variables'])
        # Ordinary unresolved issues have no observation draft IDs. Retain
        # their source scope even if an outer/duplicate-slot error is repaired
        # by an empty response. Valid envelopes produce the same obligation ID
        # in the common update below; this early capture cannot resolve it.
        self._preserve_unresolved_issues(raw, data, identity)
        selection = self._selected_web_headroom
        if selection is not None and selection[0] == digest(data):
            headroom = selection[1]
            admission = {'query_identity': identity, 'task_id': data['task']['output_slot'],
                         'source_count': len(data['source_spans']), **headroom}
            self.web_capacity_admissions.append(admission)
            self.e.event({'event': 'web_reading_capacity_admitted', **deepcopy(admission)})
        decoded, records = self._gap_response(raw, data)
        for record in records:
            diagnostic = {**record, 'query_identity': identity,
                          'task_id': data['task']['output_slot'],
                          'request_identity': digest(data),
                          'logical_call_index': self.e.reasoner.sequence,
                          'source_ids': [self.e.mapper.sources[source['id']]['source_id']
                                         for source in data['source_spans']]}
            self.web_search_gaps.append(diagnostic)
            self.e.event({'event': 'web_search_gap_observed', **deepcopy(diagnostic)})
        # Source exposure and all reading diagnostics already own the read's
        # actual call index. The independent request has its own ledger/index.
        read_call_index = self.source_exposures[-1]['logical_call_index']
        self._review_grounding_candidates(decoded, data, read_call_index)
        # Reasoner.last_response and archived raw_output are never rewritten.
        return decoded

    def public_dict(self):
        # These archives are diagnostic only. In particular, do not include
        # them in obligation_snapshot(): the core hashes that behavioral state
        # when deciding whether a read made progress.
        return {**super().public_dict(),
                'web_reading_protocol': 'required_typed_web_reading_v3',
                'web_search_gaps': deepcopy(self.web_search_gaps),
                'web_capacity_admissions': deepcopy(self.web_capacity_admissions),
                'web_paid_recoveries': deepcopy(self.web_paid_recoveries),
                'web_single_shot_reads': deepcopy(self.web_single_shot_reads),
                'web_source_attempts': deepcopy(self.web_source_attempts),
                'web_navigation_reads': deepcopy(self.web_navigation_reads)}
