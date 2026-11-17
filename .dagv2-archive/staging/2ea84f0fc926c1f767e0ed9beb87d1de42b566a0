"""Current protocol guidance is counted on wire; validators still own acceptance."""
from copy import deepcopy

from dagbt.joint_reading import JointReader
from test_personamem_joint_protocol import fixture
from test_v4_obligation_review_feedback_review import (
    OID, PROOF, claim, irrelevant, obligation_fixture, observation, read_issue,
)


def request_data(reader, engine):
    data=reader._payload(engine.steps[0], 'Review source-backed history', ['history'], list(engine.mapper.sources))
    data.update(personal_response_selection=True,phase='history_evidence')
    return data


def test_guidance_uses_current_aliases_and_ids_without_editing_request_or_state():
    reader, engine, state, calls=fixture()
    data=request_data(reader,engine)
    data['evidence_obligations']=[{'id':'issue-current','variable':'history','source_ids':['s1','s2']}]
    data['repair_scope']={'frozen_observation_ids':{'history':['immutable-current']},'failed':[
        {'variable':'history','id':'*','frozen_observation_reviews':{
            'slot_observation_ids':['immutable-current'],'observations':[]}}]}
    data['summary_revision_contracts']={'history':{
        'eligible_route_ids':['route-live'],'previous_version':7}}
    before=deepcopy((data,state.public_dict(),engine.mapper.sources,engine.ledger.public_dict()))
    text=reader._personal_protocol_checklist(data)
    for value in ('issue-current','s1','s2','immutable-current','route-live','previous_version=7'):
        assert value in text
    assert 'Never submit the same ID in both' in text
    assert 'only its own cited sources' in text
    assert 'necessary gaps' in text
    assert before==(data,state.public_dict(),engine.mapper.sources,engine.ledger.public_dict())
    assert not calls.requests


def test_nonpersonal_request_gets_no_new_instruction():
    reader,engine,_,_=fixture()
    data=reader._payload(engine.steps[0], 'Read', ['history'], ['s1'])
    assert reader._personal_protocol_checklist(data)==''


def test_real_wire_candidates_receive_identical_current_checklist():
    reader,engine,state,calls=fixture()
    data=request_data(reader,engine)
    checklist=reader._personal_protocol_checklist(data)
    for wire,system in reader._wire_candidates(data):
        assert system.endswith(checklist)
        assert 'HOST RESPONSE CHECKLIST' in system
        # The checklist is in the actual serialized request and its count path.
        payload=engine.reasoner._payload('joint_read',system,wire,reader._schema(data))
        assert checklist in payload['messages'][0]['content']
        engine.reasoner._count_payload('joint_read',payload)
    assert not calls.requests and not engine.ledger.used


def test_offered_reference_plus_independent_source_review_can_recover():
    reader,engine,state,calls,aliases=obligation_fixture(repairs=1)
    engine.personal_response_selection=True
    def answer(index,data):
        system=calls.requests[-1]['payload']['messages'][0]['content']
        assert 'HOST RESPONSE CHECKLIST' in system and OID in system
        if index==1:
            return claim(observation(PROOF,aliases[:3]))
        assert PROOF in system and aliases[52] in system
        return claim(irrelevant('actually-reviewed-remaining-text',aliases[3:53]),refs=[PROOF])
    calls.respond=answer
    read_issue(reader,engine)
    assert len(calls.requests)==2 and engine.ledger.used['json_repairs']==1
    assert OID not in reader.evidence_obligations and not state.pending


def test_referencing_one_source_still_cannot_close_all_source_obligation():
    reader,engine,state,calls,aliases=obligation_fixture(repairs=1)
    engine.personal_response_selection=True
    calls.respond=lambda index,data:(claim(observation(PROOF,aliases[:3])) if index==1 else claim(refs=[PROOF]))
    read_issue(reader,engine)
    assert OID in reader.evidence_obligations and 'history' in state.pending
    assert not reader.batches[-1]['complete']


def test_diagnostics_includes_nonexception_capacity_and_batch_validation(monkeypatch,tmp_path):
    from test_prefeval_port import script_module
    wrapper=script_module('prefeval_v4')
    rows={arm:{} for arm in wrapper.ARMS}
    arm=wrapper.ARMS[1]
    rows[arm]['x']={'answer':{'status':'unresolved_or_exhausted'},'diagnostics':{
        'events':[{'event':'joint_support_capacity_rejected','next_operation':'semantic_compose',
                   'next_node_id':'response','source_spans':47,'context_tokens':16384}],
        'joint_reading':{'batches':[{'operation':'joint_read','failed_slots':[
            {'variable':'history','id':'*','error':'Coverage missing'}]}]}}}
    monkeypatch.setattr(wrapper,'public_snapshot',lambda output:({}, {}, [], rows,{}))
    report=wrapper.diagnostics(tmp_path)['arms'][arm]
    assert report['top_errors']==[]
    assert report['capacity_deferrals']==1
    assert report['capacity_examples'][0]['next_node_id']=='response'
    assert report['top_validation_failures']==[{'count':1,'operation':'joint_read','error':'Coverage missing'}]
