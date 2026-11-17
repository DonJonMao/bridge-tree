"""Regressions for the failure modes observed in the stopped PrefEval run.

All services are scripted; these tests verify execution and evidence retention,
not real-model accuracy or the production tokenizer's capacity.
"""
from copy import deepcopy
import json

import numpy as np
import pytest

from dagbt.engine import Engine
from dagbt.methods import RESIDUAL_V2
from dagbt.personal_task import bind_personal_terminal, validate_personal_plan
from dagbt.reasoning import InputOverflow, ProtocolError
from test_v4_personal_task import plan, QUESTION, OPTIONS, PersonalServices, demo
from test_v4_joint_reading import prepare_terminal, terminal_response
from test_v4_headroom_review import large_personal_history
from test_personamem_joint_protocol import observation, response


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Recovery regressions must stay offline')
    monkeypatch.setattr('urllib.request.urlopen', forbidden)
    monkeypatch.setattr('urllib.request.build_opener', forbidden)


def test_public_goal_is_host_bound_without_changing_inferred_history_or_raw_plan():
    proposed = plan()
    proposed['steps'][-1]['question'] = 'Select an appropriate response to the user.'
    before = deepcopy(proposed)
    with pytest.raises(ProtocolError, match='exact original user utterance'):
        validate_personal_plan(proposed, QUESTION)
    bound = bind_personal_terminal(proposed, QUESTION)
    assert proposed == before
    assert bound['steps'][:-1] == before['steps'][:-1]
    assert bound['program'] == before['program']
    assert bound['steps'][-1] == {**before['steps'][-1], 'question': QUESTION}
    proposed['output_contract']['mode'] = 'value'
    with pytest.raises(ProtocolError, match='semantic/text'):
        bind_personal_terminal(proposed, QUESTION)


def test_real_engine_binds_goal_then_requires_sourced_selection_and_audit():
    class ParaphrasedPlanner(PersonalServices):
        def get(self, stage, url, payload):
            reply = super().get(stage, url, payload)
            if stage[0] == 'planner':
                content = reply['response']['choices'][0]['message']
                value = json.loads(content['content'])
                value['steps'][-1]['question'] = 'Select a reply personalized to the user.'
                content['content'] = json.dumps(value)
            return reply
    from types import SimpleNamespace
    text = 'I enjoy hands-on DIY projects, including making furniture from reclaimed wood.'
    doc = SimpleNamespace(doc_id='diy', passage=text, metadata={'source_segments': [
        {'role': 'user', 'start': 0, 'end': len(text), 'source_message_indices': [0]}]})
    calls = ParaphrasedPlanner()
    e = Engine({'id':'bound-public-goal', 'question':QUESTION},
        ({'diy':doc}, ['diy'], np.array([[1,0,0]], np.float32), None, demo.Tokenizer()), calls,
        {'_test_transport':True, 'llm_base_url':'http://synthetic/v1', 'llm_model':'script',
         'embedding_base_url':'http://synthetic/v1', 'embedding_model':'script',
         'fusion':{'initial_width':1, 'proposal_width':1, 'joint_read_window_spans':12}},
        RESIDUAL_V2, reader_question=QUESTION, output_options=OPTIONS,
        task_kind='personal_response_selection')
    row = e.run()
    assert row['answer']['status'] == 'ok' and row['answer']['prediction'] == 'a'
    assert row['answer']['sources'] and row['diagnostics']['audit_complete']
    assert e.ledger.used['json_repairs'] == 0
    assert sum(r['operation']=='planner' for r in e.reasoner.requests) == 1
    assert any(event['event']=='personal_terminal_question_bound' for event in e.events)
    assert e.steps[-1]['question'] == QUESTION


def test_deferred_compose_does_not_poison_parents_or_block_next_owner(monkeypatch):
    reader, e, state, calls = prepare_terminal(personal=True)
    before = deepcopy(state.public_dict())
    fits = reader._fits
    monkeypatch.setattr(reader, '_fits', lambda *args:False)
    with pytest.raises(InputOverflow):
        reader.read(e.steps[1], 'Select from current sourced history', ['suggestion'], [],
            'unattempted-capacity-probe', semantic=True, terminal_output=True,
            source_scope='mandatory_closure')
    assert state.public_dict() == before
    assert not reader.unread_obligations and not reader.source_exposures
    assert not calls.requests and reader.semantic_inputs is None
    monkeypatch.setattr(reader, '_fits', fits)
    calls.respond = lambda index,data:terminal_response(data,e.output_options[0])
    reader.read(e.steps[1], 'Select from current sourced history', ['suggestion'], [],
        'new-compose-owner', semantic=True, terminal_output=True,
        source_scope='mandatory_closure')
    assert reader.semantic_inputs['validation_complete'] and not state.pending
    assert len(calls.requests) == 1


def test_real_foreign_unread_work_is_still_rejected_without_silent_transfer():
    reader, e, state, calls = prepare_terminal(personal=True)
    reader.unread_obligations['genuine-old-query','s1'] = {'history'}
    before = deepcopy(reader.obligation_snapshot())
    with pytest.raises(ProtocolError, match='owned by another query'):
        reader.read(e.steps[1], 'Select from current sourced history', ['suggestion'], [],
            'new-owner', semantic=True, terminal_output=True,source_scope='mandatory_closure')
    assert reader.obligation_snapshot() == before and not calls.requests


def test_small_fresh_window_retains_unoffered_candidates_and_full_required_sources():
    reader, e, state, calls = large_personal_history()
    e.s['joint_read_window_spans'] = 12
    aliases = list(e.mapper.sources)
    originals = deepcopy(e.mapper.sources)
    calls.respond = lambda index,data:response(observation('sufficient-history',
        [data['source_spans'][0]['id']], value=['piano']))
    reader.read(e.steps[0], 'Review relevant activities', ['history'], list(e.docs),
        'bounded-fresh', discovery_doc_ids=list(e.docs))
    assert len(calls.requests) == 1
    offered = {source['id'] for source in calls.requests[0]['data']['source_spans']}
    assert 1 <= len(offered) <= 12
    assert set(a for identity,a in reader.discovery_frontier if identity=='bounded-fresh') == set(aliases)-offered
    assert e.mapper.sources == originals and not state.pending
    assert not reader.unread_obligations
    # Existing required evidence is not silently reduced to the window cap.
    retained = aliases[:20]
    visible = {a:e.mapper.sources[a] for a in retained}
    state.integrate([reader._observation(observation('existing-long-proof',retained,value=['piano']),
        'history',visible,e.steps[0])])
    proof = reader._payload(e.steps[0], 'Review relevant activities', ['history'], [])
    assert set(retained) <= {source['id'] for source in proof['source_spans']}


def test_diagnostics_counts_current_rows_without_gold_or_model_calls(monkeypatch,tmp_path):
    from test_prefeval_port import script_module
    wrapper=script_module('prefeval_v4')
    rows={arm:{} for arm in wrapper.ARMS}
    rows[RESIDUAL_V2]['example']={
        'answer':{'status':'unresolved_or_exhausted'},
        'diagnostics':{'errors':[{'type':'InputOverflow','error':'Synthetic capacity failure'}],
            'events':[{'event':'joint_capacity_deferred','operation':'semantic_compose',
                'node_id':'response','context_tokens':16384,'input_tokens':13000}]}}
    monkeypatch.setattr(wrapper,'public_snapshot',lambda output:({}, {}, [], rows,
        {arm:0 for arm in wrapper.ARMS}))
    def forbidden(*args,**kwargs):
        raise AssertionError('Diagnostics may not read labels or write a report')
    monkeypatch.setattr(wrapper.prefeval,'validate_dataset',forbidden)
    monkeypatch.setattr(wrapper.runner,'save',forbidden)
    report=wrapper.diagnostics(tmp_path)
    assert report['labels_read'] is False
    residual=report['arms'][RESIDUAL_V2]
    assert residual['completed']==1 and residual['capacity_deferrals']==1
    assert residual['top_errors']==[{'type':'InputOverflow','error':'Synthetic capacity failure','count':1}]


@pytest.mark.parametrize('bad',[True,-1,1.5])
def test_fresh_window_setting_rejects_invalid_values(bad):
    from dagbt.config import resolve
    with pytest.raises(ValueError,match='joint_read_window_spans'):
        resolve({'fusion':{'joint_read_window_spans':bad}},RESIDUAL_V2)

