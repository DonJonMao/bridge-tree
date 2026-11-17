"""Actual archived F/R metadata and saved exact-token selection evidence only."""
import hashlib
import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path('/Users/mao/projects/dagv2-personamem-v4')
RUN = ROOT / 'outputs/v4_validation_r21'
OUT = Path('/Users/mao/projects/dagv2_analysis/personamem_v4_validation/r21_frozen_selector_review.json')
sys.path.insert(0, str(ROOT))
from dagbt.history_wire import unpack as unpack_history
from dagbt.review_wire import INSTRUCTION as REVIEW_INSTRUCTION, POOL, pack_with_status, unpack as unpack_review
from dagbt.joint_reading import FROZEN_IDS_INSTRUCTION

MARKER = '\n\nReturn one complete JSON object matching this schema:\n'
OPERATIONS = {'joint_read', 'joint_read_repair', 'semantic_compose', 'semantic_compose_repair',
              'audit_joint', 'audit_joint_repair'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def events(path):
    result = []
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        try:
            result.append(json.loads(line))
        except ValueError:
            pass
    return result


records = []
for attempt in (RUN / 'personamem/dagbt_residual_memory_v2/attempts').glob('*/attempt-*'):
    by_wire = {}
    for event in events(attempt / 'tokenization_events.jsonl'):
        if event.get('status') == 'ok' and event.get('token_count_is_estimate') is False:
            by_wire.setdefault(event.get('tokenization_wire_sha256'), []).append(event)
    for path in (attempt / 'requests').glob('*.json'):
        saved = load(path)
        if not saved or not saved.get('stage') or saved['stage'][0] not in OPERATIONS:
            continue
        row = {'request_file': str(path.relative_to(RUN)), 'stage': saved['stage'],
               'has_response': 'response' in saved}
        try:
            payload = saved['payload']
            system = payload['messages'][0]['content']
            prefix, separator, schema_text = system.rpartition(MARKER)
            if not separator:
                raise ValueError('unhandled_schema_transport')
            schema = json.loads(schema_text)
            wire = json.loads(payload['messages'][1]['content'])
            selected_review = POOL in wire
            baseline = unpack_review(wire) if selected_review else deepcopy(wire)
            candidate, candidate_available = pack_with_status(baseline)
            if selected_review:
                assert REVIEW_INSTRUCTION in prefix and candidate_available
                assert candidate == wire
                base_prefix = prefix.replace(REVIEW_INSTRUCTION, '', 1)
            else:
                assert REVIEW_INSTRUCTION not in prefix
                base_prefix = prefix

            def reconstruct(body, text):
                rebuilt = deepcopy(payload)
                rebuilt['messages'][0]['content'] = text + MARKER + schema_text
                rebuilt['messages'][1]['content'] = json.dumps(body, ensure_ascii=False,
                    allow_nan=False, separators=(',', ':'))
                return rebuilt

            baseline_payload = reconstruct(baseline, base_prefix)
            candidate_payload = reconstruct(candidate, base_prefix + REVIEW_INSTRUCTION) if candidate_available else None
            selected_payload = candidate_payload if selected_review else baseline_payload
            assert selected_payload == payload, 'saved_payload_not_exactly_reconstructed'
            base_hash = digest(baseline_payload)
            candidate_hash = digest(candidate_payload) if candidate_available else None
            base_events = by_wire.get(base_hash, [])
            candidate_events = by_wire.get(candidate_hash, []) if candidate_available else []
            base_counts = sorted({event['count'] for event in base_events})
            candidate_counts = sorted({event['count'] for event in candidate_events})
            paired = candidate_available and len(base_counts) == len(candidate_counts) == 1
            comparison = ('candidate_strictly_smaller' if candidate_counts[0] < base_counts[0]
                          else 'candidate_equal_or_larger') if paired else None
            row.update(selector_reconstruction_complete=True, selected_review=selected_review,
                candidate_available=candidate_available, baseline_wire_sha256=base_hash,
                candidate_wire_sha256=candidate_hash, baseline_saved_exact_counts=base_counts,
                candidate_saved_exact_counts=candidate_counts, baseline_count_event_count=len(base_events),
                candidate_count_event_count=len(candidate_events), paired_exact_count_evidence=paired,
                paired_comparison=comparison,
                selection_matches_strictly_smaller_rule=(selected_review == (candidate_counts[0] < base_counts[0]))
                    if paired else (not selected_review if not candidate_available else None),
                selected_wire_saved_count_present=bool(candidate_events if selected_review else base_events))

            data = unpack_history(unpack_review(wire))
            frozen = data.get('repair_scope', {}).get('frozen_observation_ids', {})
            offers = {}
            for entry in data.get('repair_scope', {}).get('failed', []):
                offer = entry.get('frozen_observation_reviews')
                if offer:
                    offers[entry['variable']] = set(offer['slot_observation_ids']) | {
                        item['id'] for item in offer['observations']}
            branches = schema['properties']['slots']['items'].get('oneOf', [])
            constraints = {branch['properties']['variable']['const']: branch['properties'] for branch in branches}
            mismatches = []
            for variable, ids in frozen.items():
                properties = constraints.get(variable, {})
                forbidden = set(properties.get('observations', {}).get('items', {}).get('properties', {}).get(
                    'id', {}).get('not', {}).get('enum', []))
                if forbidden != set(ids) | offers.get(variable, set()):
                    mismatches.append('frozen_id_exclusion')
                references = properties.get('reviewed_observation_ids', {})
                allowed = set(references.get('items', {}).get('enum', []))
                if allowed != offers.get(variable, set()):
                    mismatches.append('review_permission_expansion_or_loss')
            returned_frozen = 0
            response_parseable = None
            if 'response' in saved:
                try:
                    response = json.loads(saved['response']['choices'][0]['message']['content'])
                    response_parseable = isinstance(response, dict)
                    returned_frozen = sum(item.get('id') in frozen.get(slot.get('variable'), [])
                        for slot in response.get('slots', []) for item in slot.get('observations', []))
                except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                    response_parseable = False
            row.update(frozen_id_mapping_present=bool(frozen),
                frozen_id_count=sum(len(ids) for ids in frozen.values()),
                settled_review_offer_id_count=sum(len(ids) for ids in offers.values()),
                frozen_instruction_present=FROZEN_IDS_INSTRUCTION in prefix,
                frozen_schema_mismatch_categories=sorted(set(mismatches)),
                response_json_parseable=response_parseable, returned_ordinary_frozen_id_count=returned_frozen,
                frozen_scope_note='Actual producer-supplied F and schema/R exposure only; this does not independently replay every runtime freeze/thaw transition.')
        except Exception as exc:
            row.update(inspection_incomplete=True, inspection_error_type=type(exc).__name__)
        records.append(row)

records.sort(key=lambda row: row['request_file'])
summary = {
    'saved_reader_requests': len(records),
    'inspection_incomplete': sum(row.get('inspection_incomplete', False) for row in records),
    'actual_frozen_id_requests': sum(row.get('frozen_id_mapping_present', False) for row in records),
    'frozen_instruction_missing': sum(row.get('frozen_id_mapping_present', False)
        and not row.get('frozen_instruction_present') for row in records),
    'frozen_schema_mismatch_requests': sum(bool(row.get('frozen_schema_mismatch_categories')) for row in records),
    'returned_ordinary_frozen_id_count': sum(row.get('returned_ordinary_frozen_id_count', 0) for row in records),
    'multi_candidate_requests': sum(row.get('candidate_available', False) for row in records),
    'paired_exact_count_requests': sum(row.get('paired_exact_count_evidence', False) for row in records),
    'selected_review_requests': sum(row.get('selected_review', False) for row in records),
    'paired_comparison_counts': dict(Counter(row['paired_comparison'] for row in records if row.get('paired_comparison'))),
    'selector_rule_mismatch_requests': sum(row.get('selection_matches_strictly_smaller_rule') is False for row in records),
    'selected_wire_count_missing': sum(row.get('selector_reconstruction_complete', False)
        and not row.get('selected_wire_saved_count_present') for row in records),
}
report = {'run': RUN.name, 'source_commit': 'e6677081cdfb33c01db3aaa274a497168f314f78',
          'scope': 'Read-only actual archived requests and existing exact tokenization events. No new counts, generation, labels, scoring, or source/run mutation. Schema/selection consistency is not model success, semantic sufficiency, or quality evidence.',
          'summary': summary, 'requests': records}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary, ensure_ascii=False))
