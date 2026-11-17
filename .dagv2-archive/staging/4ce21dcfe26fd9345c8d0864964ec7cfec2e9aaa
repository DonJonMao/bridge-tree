"""Independent input/output audit of generated candidate q1; no labels or network."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

STAGE = Path(__file__).resolve().parent.parent
TASKS = STAGE / 'output' / 'tasks' / 'wwqa-0001'


def decode(raw):
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0]
    return json.loads(raw)


records = []
for arm in sorted(TASKS.iterdir()):
    for path in (arm / 'requests').glob('*.json'):
        request = json.loads(path.read_text())
        stage = request['stage']
        if stage[0] not in ('joint_read', 'joint_read_repair'):
            continue
        inp = json.loads(next(message['content'] for message in request['payload']['messages']
                              if message['role'] == 'user'))
        system = request['payload']['messages'][0]['content']
        marker = 'Return one complete JSON object matching this schema:'
        instructions, schema = system.split(marker, 1)
        schema = json.loads(schema)
        spans = inp['source_spans']
        if 'source_span_columns' in inp:
            spans = [dict(zip(inp['source_span_columns'], row)) for row in spans]
        response = decode(request['response']['choices'][0]['message']['content'].strip())
        selected_input_fields = (
            'original_question', 'task', 'grounded_subquestion', 'variables', 'requested_slots',
            'requested_scopes', 'required_scope', 'output_contract', 'known_observations',
            'evidence_obligations', 'failed_batch_reviews', 'web_reading_context',
            'web_review_checklist', 'repair_scope', 'web_repair_edit_scope',
            'web_reading_protocol_diagnostics', 'source_documents', 'shared_review_texts')
        records.append({
            'arm': arm.name, 'stage': stage, 'request_path': str(path),
            'request_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'input': {key: inp[key] for key in selected_input_fields if key in inp},
            'all_offered_source_ids': [source['id'] for source in spans],
            'event_comparison_original_sources': [source for source in spans
                                                  if source['id'] in ('s91', 's102')],
            'full_actual_system_instructions_before_schema': instructions,
            'actual_slot_schema': schema['properties']['slots']['items'],
            'response': response})
records.sort(key=lambda row: (row['arm'], int(row['stage'][1])))

report = {
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Read-only independent candidate generation input/system/response audit; no raw references, evaluation or extra requests.',
    'pipeline_terminal_evidence': json.loads((STAGE / 'state.json').read_text()),
    'findings': [
        {'id': 'time_not_hidden', 'classification': 'verified_no_input_or_schema_omission',
         'evidence': 'RES ordinary calls 17,20,23 request both time/location; time=ICSE 2018 route fact_92b23e546ea07a1296a127ea is visible, source s91 and explicit November 2002 source s102 are both visible, time contradiction schema permits retracting that route.'},
        {'id': 'incorrect_event_relation_origin', 'classification': 'model_semantic_error',
         'evidence': 'Both arms call12 infer duplicate-statement agreement from s91 Latest ICSE Review Process establishment for ICSE 2018, a different event/relation. No request states that this is the statement agreement.'},
        {'id': 'new_event_date_ignored', 'classification': 'model_semantic_error',
         'evidence': 'RES17 copies known time=ICSE2018 while writing Charleston/FSE-10/November2002 from s102 into location. RES20 emits audit_verdict=conflict but still no contradiction or corrected time; RES23 repeats again.'},
        {'id': 'current_diagnostic_works', 'classification': 'verified_mechanism_trigger',
         'evidence': 'JOINT13 paid repair contains source-reference diagnostic for location/o2 and original source-free draft. The next response preserves o2, cites s91, and is protocol-valid. RES has no source-free current drafts, so absence of this diagnostic is expected.'},
        {'id': 'obligation_originals_not_hidden', 'classification': 'model_protocol_error',
         'evidence': 'RES18/19/21/22 display original s91 and s102, failed-slot missing_source_ids=[s91], and checklist sources_requiring_new_model_review=[s91]. Responses review/reference only s102 while claiming settlement of the s91 obligation; frozen support is also restated.'},
        {'id': 'frozen_wording_ambiguity', 'classification': 'potential_instruction_clarity_improvement_not_authority_bug',
         'evidence': 'Common sentence Already validated observations are frozen and must not be restated or changed occurs inside the repair paragraph but is also sent during ordinary reads. It should be explicitly limited to current-batch frozen observations during repair; known fact routes remain source-groundedly retractable under existing contradiction rules.'},
        {'id': 'synthetic_issue_anchoring', 'classification': 'potential_instruction_clarity_improvement',
         'evidence': 'Obligation descriptions repeat the earlier model claim that ICSE2018 was the agreement. They are explicitly not facts, but a generic field reminder that prior model descriptions are claims to re-evaluate could reduce anchoring without changing evidence/authority.'}
    ],
    'general_repair_options': [
        'Web-only precise prompt qualification: current-batch validated observations are frozen during repair; known_observations are prior model judgments whose same-variable fact route may still be challenged with a sourced contradiction and separate corrected support.',
        'Read-only per-request consistency reminder: assess newly offered original text against every requested variable, including currently bound variables; do not blindly copy known rows. Display only already-authorized same-variable retraction targets and actual new source IDs.',
        'Explain that audit_verdict=conflict is not a substitute for a sourced contradiction/retraction or corrected support in a typed retrieval response.',
        'For obligation settlement, project the existing exact missing-source review requirement and legal offered frozen IDs, without accepting citation padding, frozen re-emission or automatic irrelevant classification.'
    ],
    'records': records}
path = STAGE / 'analysis' / 'candidate_q1_consistency_input_audit.json'
path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'report': str(path), 'records': len(records),
                  'findings': report['findings']}, ensure_ascii=False, indent=2))
