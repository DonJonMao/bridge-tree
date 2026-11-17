"""Per-source paid recovery with the real reader, scope and obligation guards."""
from copy import deepcopy

import pytest

from dagbt.source_review import contract, decode, schema_with_checks
from test_v4_obligation_review_feedback_review import (
    OID, PROOF, claim, observation, obligation_fixture, read_issue,
)


def personal_fixture():
    reader, engine, state, calls, aliases = obligation_fixture(repairs=1)
    engine.personal_response_selection = True
    reader.evidence_obligations[OID]['source_ids'] = [
        engine.mapper.sources[a]['source_id'] for a in aliases[:23]]
    return reader, engine, state, calls, aliases


def packet(data, aliases, proof=PROOF):
    sources = {row['id']: row for row in data['source_spans']}
    checks = []
    for alias in aliases[:23]:
        checks.append({'source_id': alias, 'assessment': 'observation' if alias in aliases[:3] else 'irrelevant',
                       'observation_id': proof if alias in aliases[:3] else None,
                       'quote': sources[alias]['text'],
                       'reason': ('The unchanged explicit observation already reviews this original.'
                                  if alias in aliases[:3] else
                                  'This record supplies no activity or constraint relevant to this scoped issue.')})
    result = claim()
    result['slots'][0]['source_checks'] = checks
    return result


def test_paid_per_original_checks_recover_without_rewriting_frozen_facts():
    reader, engine, state, calls, aliases = personal_fixture()
    before = deepcopy(state.routes)
    def reply(index, data):
        if index == 1:
            return claim(observation(PROOF, aliases[:3]))
        assert 'source_review_contract' in data
        offered = data['source_review_contract']['history']
        assert set(offered['source_ids']) == set(aliases[:23])
        assert [row['id'] for row in offered['reference_observations']] == [PROOF]
        return packet(data, aliases)
    calls.respond = reply
    read_issue(reader, engine)
    assert len(calls.requests) == 2
    assert engine.ledger.used['llm'] == 2 and engine.ledger.used['json_repairs'] == 1
    assert OID not in reader.evidence_obligations and not state.pending
    assert all(state.routes[key] == row for key, row in before.items())
    assert state.valid()[0]['history'] == ['piano']
    assert reader.batches[-1]['complete']
    # The recorded model answer remains the actual source-check form.
    assert 'source_checks' in engine.reasoner.last_response['raw_output']


@pytest.mark.parametrize('mistake', ['missing_source', 'duplicate_source', 'wrong_quote',
    'invented_reference', 'known_route_reference', 'frozen_restatement', 'partial', 'unknown',
    'unsourced_support', 'counter_without_target'])
def test_form_cannot_bypass_existing_guards(mistake):
    reader, engine, state, calls, aliases = personal_fixture()
    known = next(iter(state.routes))
    def reply(index, data):
        if index == 1:
            return claim(observation(PROOF, aliases[:3]))
        result = packet(data, aliases)
        slot = result['slots'][0]
        checks = slot['source_checks']
        if mistake == 'missing_source':
            checks.pop()
        elif mistake == 'duplicate_source':
            checks[-1] = deepcopy(checks[-2])
        elif mistake == 'wrong_quote':
            checks[-1]['quote'] = 'Invented words absent from the original.'
        elif mistake in ('invented_reference', 'known_route_reference'):
            checks[0]['observation_id'] = known if mistake == 'known_route_reference' else 'invented'
        elif mistake == 'frozen_restatement':
            slot['observations'] = [observation(PROOF, aliases[:3])]
        elif mistake in ('partial', 'unknown'):
            checks[-1]['assessment'] = mistake
        else:
            row = observation('new-bad-draft', [] if mistake == 'unsourced_support' else [aliases[-1]])
            if mistake == 'counter_without_target':
                row.update(stance='contradiction', value=None, retract_ids=['invented-target'])
            slot['observations'].append(row)
        return result
    calls.respond = reply
    read_issue(reader, engine)
    assert OID in reader.evidence_obligations and 'history' in state.pending
    assert state.valid()[0]['history'] == ['piano']
    assert len(calls.requests) == 2 and engine.ledger.used['json_repairs'] == 1
    assert not reader.batches[-1]['complete']


def test_no_form_can_silently_drop_counter_drafts_when_quote_is_invalid():
    reader, engine, state, calls, aliases = personal_fixture()
    saved = {}
    def reply(index, data):
        if index == 1:
            return claim(observation(PROOF, aliases[:3]))
        result = packet(data, aliases)
        result['slots'][0]['source_checks'][-1]['quote'] = 'not in any original'
        counter = observation('retained-counter', aliases[:1], stance='contradiction', value=['piano'])
        counter.update(value=None, retract_ids=[next(iter(state.routes))])
        result['slots'][0]['observations'].append(counter)
        saved['raw'] = deepcopy(result)
        canonical = decode(result, data)
        assert canonical['slots'][0]['observations'] == [counter]
        assert 'source_review_error' in canonical
        return result
    calls.respond = reply
    read_issue(reader, engine)
    assert any(item.get('id') == 'retained-counter'
               for record in reader.failed_batch_reviews.values() for item in record['failed'])
    assert OID in reader.evidence_obligations


def test_canonical_sources_state_and_wire_counts_stay_separate():
    reader, engine, state, calls, aliases = personal_fixture()
    data = reader._payload(engine.steps[0], 'Review history', ['history'], aliases[:23])
    before = deepcopy((data, state.public_dict(), reader.obligation_snapshot(), engine.ledger.public_dict()))
    schema = reader._schema(data)
    branch = schema['properties']['slots']['items']['oneOf'][0]
    assert 'source_checks' in branch['required']
    assert branch['properties']['source_checks']['minItems'] == 23
    for wire, system in reader._wire_candidates(data):
        assert 'source_review_contract' in wire and 'SOURCE REVIEW FORM' in system
        payload = engine.reasoner._payload('joint_read', system, wire, schema)
        engine.reasoner._count_payload('joint_read', payload)
    assert before == (data, state.public_dict(), reader.obligation_snapshot(), engine.ledger.public_dict())
    assert not calls.requests


@pytest.mark.parametrize('phase', ['response_selection', 'response_audit'])
def test_terminal_and_audit_do_not_get_a_new_response_protocol(phase):
    reader, engine, state, calls, aliases = personal_fixture()
    data = reader._payload(engine.steps[0], 'Review history', ['history'], aliases[:23])
    data['phase'] = phase
    baseline = reader._schema(data)
    assert not contract(data)
    assert schema_with_checks(baseline, data) is baseline
    raw = packet({**data, 'source_spans': data['source_spans']}, aliases)
    assert decode(raw, data) is raw


def test_named_counter_or_whole_value_repair_never_uses_the_short_form():
    reader, engine, state, calls, aliases = personal_fixture()
    data = reader._payload(engine.steps[0], 'Review history', ['history'], aliases[:23])
    data['repair_scope'] = {'failed': [{'variable': 'history', 'id': 'counter-draft', 'feedback': 'keep counter'}]}
    assert not contract(data)
    data['repair_scope'] = {'failed': [], 'whole_value_reviews': [{'variable': 'history'}]}
    assert not contract(data)


def test_per_source_unknown_can_preserve_issue_without_claiming_resolution():
    reader, engine, state, calls, aliases = personal_fixture()
    def reply(index, data):
        if index == 1:
            return claim(observation(PROOF, aliases[:3]))
        result = packet(data, aliases)
        result['slots'][0]['resolved_obligation_ids'] = []
        result['slots'][0]['source_checks'][-1]['assessment'] = 'unknown'
        result['slots'][0]['source_checks'][-1]['reason'] = 'The source applicability remains uncertain.'
        return result
    calls.respond = reply
    read_issue(reader, engine)
    assert OID in reader.evidence_obligations and 'history' in state.pending
    assert engine.ledger.used['llm'] == 2
