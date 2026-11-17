"""Offline real-reader checks for the Web correction-review permission."""
from copy import deepcopy
import pytest
from dagbt.reasoning import ProtocolError
from dagbt.webwalker_correction_review import KEY, POLICY
from dagbt.webwalker_reading import WebJointReader
import test_webwalker_reading as t


def prepared(max_repairs=2):
    control={'phase':'bad','mode':'resolve'}
    def respond(i,data):
        if control['phase']=='bad':
            return t.response(t.observation('fix-me',['unbound-source'],value=['painting']))
        result=t.response(t.observation('fix-me',['s2'],value=['painting']))
        if control['phase']=='review':
            if control['mode']=='bad':
                return t.response(t.observation('fix-me',['still-unbound'],value=['painting']))
            if control['mode']=='empty':
                return t.gap_response()
            if control['mode']=='missing-original':
                result=t.response(t.observation('new-unoffered-name',['s2'],value=['painting']))
            if control['mode']!='omit-claim':
                result['slots'][0]['resolved_failed_batch_ids']=[row['id'] for row in data.get('failed_batch_reviews',[]) if row['review_allowed']]
        return result
    reader,e,state,calls=t.web_fixture(respond,max_repairs_per_request=max_repairs)
    t.read(reader,'piano','bad-window')
    assert reader.failed_batch_reviews and not state.valid()[0]
    original=deepcopy(reader.failed_batch_reviews)
    control['phase']='correction'
    t.read(reader,'painting','accepted-correction')
    assert state.valid()[0]['history']==['painting'] and state.pending=={'history'}
    assert reader.failed_batch_reviews
    assert len(reader._web_correction_state['grants'])==1
    control['phase']='review'
    return reader,e,state,calls,control,original


def restore(reader,snapshot=None):
    target=WebJointReader(reader.e,reader.state)
    target.restore_obligations(deepcopy(snapshot or reader.obligation_snapshot()))
    for name in ('read_states','clues','gaps'):
        setattr(target,name,deepcopy(getattr(reader,name)))
    return target


def test_accepted_named_correction_only_authorizes_one_paid_full_review():
    reader,e,state,calls,_,original=prepared()
    before=(len(calls.requests),e.ledger.used['json_repairs'])
    assert not next(iter(reader._web_correction_state['grants'].values()))['consumed']
    t.read(reader,'painting','same-originals')
    assert len(calls.requests)==before[0]+1
    assert e.ledger.used['json_repairs']==before[1]+1
    assert not reader.failed_batch_reviews and not state.pending
    request=calls.requests[-1]['data']
    marker=request['failed_batch_reviews'][0]
    assert marker['review_allowed'] and marker['web_review_permission']['policy']==POLICY
    assert marker['failed'][0]['observation']==original[marker['id']]['failed'][0]['observation']
    assert {source['doc_id'] for source in request['source_spans']}=={'piano','painting'}
    assert all(source['text']==e.docs[source['doc_id']].passage for source in request['source_spans'])
    assert next(iter(reader._web_correction_state['grants'].values()))['consumed']
    assert restore(reader)._web_correction_state==reader._web_correction_state


@pytest.mark.parametrize('mode',['bad','empty','missing-original','omit-claim'])
def test_invalid_or_unclaimed_review_cannot_auto_release_and_cannot_get_local_repair(mode):
    reader,e,state,calls,control,_=prepared()
    control['mode']=mode
    before=(len(calls.requests),e.ledger.used['json_repairs'])
    t.read(reader,'painting','one-shot-only')
    assert len(calls.requests)==before[0]+1
    assert e.ledger.used['json_repairs']==before[1]+1
    assert reader.failed_batch_reviews and state.pending=={'history'}
    assert all(g['consumed'] for g in reader._web_correction_state['grants'].values())
    for identity in ['renamed-query','another-query']:
        assert not reader.failed_review_ready(e.steps[0],['history'],['painting'])
        t.read(reader,'painting',identity)
    assert len(calls.requests)==before[0]+1
    assert restore(reader)._web_correction_state==reader._web_correction_state


def test_last_available_repair_is_charged_and_consumes_permission():
    reader,e,state,calls,_,_=prepared(max_repairs=1)
    e.ledger.limits['json_repairs']=e.ledger.used['json_repairs']+1
    before=len(calls.requests)
    t.read(reader,'painting','last-repair')
    assert len(calls.requests)==before+1 and e.ledger.remaining('json_repairs')==0
    assert all(g['consumed'] for g in reader._web_correction_state['grants'].values())
    assert len(reader._web_correction_state['attempts'])==1
    assert not reader.failed_batch_reviews


@pytest.mark.parametrize('kind',['repair-zero','audit-reserve','disabled-request-repair'])
def test_original_budget_limits_deny_permission(kind):
    reader,e,state,calls,_,_=prepared()
    if kind=='repair-zero': e.ledger.limits['json_repairs']=e.ledger.used['json_repairs']
    if kind=='audit-reserve': e.ledger.limits['llm']=e.ledger.used['llm']+e.s['reserved_audit_calls']
    if kind=='disabled-request-repair': e.s['max_repairs_per_request']=0
    before=len(calls.requests)
    assert not reader.failed_review_ready(e.steps[0],['history'],['painting'])
    t.read(reader,'painting','denied')
    assert len(calls.requests)==before and reader.failed_batch_reviews and state.pending
    assert not next(iter(reader._web_correction_state['grants'].values()))['consumed']


@pytest.mark.parametrize('failure',['tokenizer','transport'])
def test_failed_or_not_sent_request_consumes_opportunity_conservatively(failure):
    reader,e,state,calls,_,_=prepared()
    before=(len(calls.requests),e.ledger.used['json_repairs'])
    def fail(*args,**kwargs): raise RuntimeError('scripted '+failure+' failure')
    if failure=='tokenizer':
        register=reader._record_source_exposure
        def register_then_fail_count(*args,**kwargs):
            result=register(*args,**kwargs)
            e.reasoner._count_payload=fail
            return result
        reader._record_source_exposure=register_then_fail_count
    else: calls.respond=fail
    try: t.read(reader,'painting','failure-window')
    except RuntimeError: pass
    assert e.ledger.used['json_repairs']==before[1]+1
    assert len(calls.requests)==before[0]+(failure=='transport')
    assert reader.failed_batch_reviews and state.pending
    assert all(g['consumed'] for g in reader._web_correction_state['grants'].values())
    assert reader._web_correction_state['attempts'][0]['status']=='failed_or_not_sent'
    assert restore(reader)._web_correction_state==reader._web_correction_state


def test_bookkeeping_is_not_material_progress():
    reader,e,state,calls,_,_=prepared()
    before=reader.material_signature()
    registry=deepcopy(reader._web_correction_state)
    reader._web_correction_state['attempts'].append({'diagnostic':'not evidence'})
    next(iter(reader._web_correction_state['grants'].values()))['consumed']=True
    assert reader.material_signature()==before
    reader._web_correction_state=registry
    assert restore(reader).material_signature()==before


def test_later_new_local_evidence_makes_old_permission_stale():
    reader,e,state,calls,_,_=prepared()
    row=t.observation('later-counter',['s1'],stance='contradiction',retract_ids=list(state.routes))
    row['value']=None
    normalized=reader._observation(row,'history',{'s1':e.mapper.sources['s1']},e.steps[0])
    state.integrate([normalized],state.pending)
    assert not reader.failed_review_ready(e.steps[0],['history'],['painting'])
    assert restore(reader)._web_correction_state==reader._web_correction_state


def test_identical_semantic_replay_and_changed_reason_do_not_stale_or_regrant():
    reader,e,state,calls,_,_=prepared()
    row=deepcopy(state.history[-1]['rows'][0]);row['reason']='Different wording of same sourced correction.';row['id']='renamed-accepted-row'
    state.integrate([row],state.pending)
    assert reader.failed_review_ready(e.steps[0],['history'],['painting'])
    before=deepcopy(reader._web_correction_state['grants'])
    reader._capture_correction_grants()
    assert reader._web_correction_state['grants']==before


def test_query_and_failed_draft_renaming_do_not_create_new_lineage():
    reader,e,state,calls,_,_=prepared()
    record=deepcopy(next(iter(reader.failed_batch_reviews.values())))
    old=reader._marker_family(record)
    record['id']='new-marker';record['query_identity']='new-query';record['batch_identity']='new-batch'
    record['failed'][0]['id']='new-draft';record['failed'][0]['feedback']='Different prose'
    record['failed'][0]['observation']['id']='new-draft';record['failed'][0]['observation']['reason']='New wording'
    assert reader._marker_family(record)==old


@pytest.mark.parametrize('change',['delete-registry','reset-consumed','delete-attempt','delete-grant','invent-grant','duplicate-grant','alter-proof'])
def test_restore_rejects_removed_or_forged_consumption_and_grants(change):
    reader,e,state,calls,control,_=prepared()
    control['mode']='omit-claim'
    t.read(reader,'painting','consumed-marker')
    snapshot=deepcopy(reader.obligation_snapshot());saved=snapshot[KEY]
    lineage=next(iter(saved['grants']))
    if change=='delete-registry': del snapshot[KEY]
    elif change=='reset-consumed': saved['grants'][lineage]['consumed']=False
    elif change=='delete-attempt': saved['attempts']=[]
    elif change=='delete-grant': del saved['grants'][lineage]
    elif change in ('invent-grant','duplicate-grant'):
        saved['grants']['unearned-lineage']=deepcopy(saved['grants'][lineage])
    elif change=='alter-proof': saved['grants'][lineage]['proof']['accepted'][0]['response_ref']='forged'
    with pytest.raises(ProtocolError): restore(reader,snapshot)


def test_restore_rejects_deletion_of_unconsumed_grant():
    reader,e,state,calls,_,_=prepared()
    snapshot=deepcopy(reader.obligation_snapshot());snapshot[KEY]['grants']={}
    with pytest.raises(ProtocolError): restore(reader,snapshot)


def test_legacy_restore_disables_only_new_permission():
    reader,e,state,calls,_,_=prepared()
    snapshot=deepcopy(reader.obligation_snapshot());del snapshot[KEY]
    restored=restore(reader,snapshot)
    assert restored.failed_batch_reviews==reader.failed_batch_reviews
    assert restored._web_correction_state['enabled'] is False
    assert not restored.failed_review_ready(e.steps[0],['history'],['painting'])
    restored._capture_correction_grants()
    assert restored._web_correction_state['grants']=={}


def test_alias_permutation_restore_keeps_proof_and_sources():
    reader,e,state,calls,_,_=prepared()
    snapshot=deepcopy(reader.obligation_snapshot())
    aliases={'s1':'s2','s2':'s3','s3':'s1'}
    e.mapper.sources={aliases[key]:{**value,'id':aliases[key]} for key,value in e.mapper.sources.items()}
    e.mapper.source_aliases={value['source_id']:key for key,value in e.mapper.sources.items()}
    restored=restore(reader,snapshot)
    assert restored._web_correction_state==reader._web_correction_state
    assert restored.failed_review_ready(e.steps[0],['history'],['painting'])
    assert {s['source_alias'] for s in restored.source_exposures[0]['sources']}=={'s1'}
    assert restored.source_exposures[0]['sources'][0]['current_source_alias']=='s2'


@pytest.mark.parametrize('mode',['unrelated-id','invalid-source','same-value','prospective-only'])
def test_no_permission_without_accepted_named_obligation_correction(mode):
    control={'phase':'bad'}
    def respond(i,data):
        if control['phase']=='bad':return t.response(t.observation('fix-me',['unbound'],value=['painting']))
        if mode=='prospective-only':return t.gap_response()
        return t.response(t.observation('unrelated' if mode=='unrelated-id' else 'fix-me',
            ['unbound'] if mode=='invalid-source' else ['s2'],value=['painting']))
    reader,e,state,calls=t.web_fixture(respond,max_repairs_per_request=1)
    if mode=='same-value':
        good=reader._observation(t.observation('already-known',['s2'],value=['painting']),
            'history',{'s2':e.mapper.sources['s2']},e.steps[0]);state.integrate([good])
    t.read(reader,'piano','bad-window')
    control['phase']='correction'
    t.read(reader,'painting','new-window')
    assert not reader._web_correction_state['grants']


def ordinary_prepared():
    control={'phase':'unknown'}
    def respond(i,data):
        if control['phase']=='unknown':
            row=t.observation('old-uncertainty',['s1'],stance='unknown');row['value']=None
            return t.response(row)
        if control['phase']=='incomplete-closure' and data.get('repair_scope'):
            result=t.response()
            result['slots'][0].update(reading_status='evidence_assessment',reviewed_observation_ids=['sourced-answer'],
                resolved_obligation_ids=[r['id'] for r in data.get('evidence_obligations',[])])
            return result
        rows=[t.observation('sourced-answer',['s2'],value=['painting'])]
        if control['phase'] in ('close','review'):
            row=t.observation('original-reviewed',['s1'],stance='irrelevant');row['value']=None
            rows.append(row)
        result=t.response(*rows)
        result['slots'][0]['resolved_obligation_ids']=[r['id'] for r in data.get('evidence_obligations',[])]
        if control['phase']=='review':
            result['slots'][0]['resolved_failed_batch_ids']=[r['id'] for r in data.get('failed_batch_reviews',[]) if r['review_allowed']]
        return result
    reader,e,state,calls=t.web_fixture(respond,max_repairs_per_request=1)
    t.read(reader,'piano','old-uncertainty')
    old=deepcopy(reader.evidence_obligations)
    control['phase']='incomplete-closure'
    t.read(reader,'painting','missing-original')
    assert reader.evidence_obligations and reader.failed_batch_reviews
    assert any('obligation_review_sources' in item for record in reader.failed_batch_reviews.values() for item in record['failed'])
    assert not reader._web_correction_state['grants']
    control['phase']='close'
    t.read(reader,'advice','paid-original-review')
    assert not reader.evidence_obligations and reader.failed_batch_reviews and state.pending
    assert len(reader._web_correction_state['grants'])==1
    control['phase']='review'
    return reader,e,state,calls,control,old


def test_exact_original_ordinary_obligation_closure_authorizes_paid_historical_review():
    reader,e,state,calls,control,old=ordinary_prepared()
    grant=next(iter(reader._web_correction_state['grants'].values()))
    assert grant['proof']['kind']=='accepted_original_ordinary_obligation_review'
    assert grant['proof']['obligation']==next(iter(old.values()))
    before=(len(calls.requests),e.ledger.used['json_repairs'])
    t.read(reader,'advice','ordinary-one-shot')
    assert len(calls.requests)==before[0]+1 and e.ledger.used['json_repairs']==before[1]+1
    assert not reader.failed_batch_reviews and not state.pending
    assert restore(reader)._web_correction_state==reader._web_correction_state


def test_ordinary_proof_tampering_or_reopening_cannot_grant_permission():
    reader,e,state,calls,control,old=ordinary_prepared()
    snapshot=deepcopy(reader.obligation_snapshot())
    grant=next(iter(snapshot[KEY]['grants'].values()))
    grant['proof']['obligation']['source_ids']=[]
    with pytest.raises(ProtocolError):restore(reader,snapshot)
    reader.evidence_obligations.update(old)
    assert not reader.failed_review_ready(e.steps[0],['history'],['advice'])


def test_one_variables_grant_cannot_authorize_sibling_or_multiple_markers():
    reader,e,state,calls,_,_=prepared()
    record=deepcopy(next(iter(reader.failed_batch_reviews.values())))
    record['id']='second-marker'
    reader.failed_batch_reviews[record['id']]=record
    payload=reader._payload(e.steps[0],'same-query',['history'],['s1','s2'])
    assert sum(r['review_allowed'] for r in payload['failed_batch_reviews'])==1
    peer_step={**e.steps[0],'output_slot':'peer'}
    assert not reader.correction_review_lineages(peer_step,['history'])
    assert not reader.correction_review_lineages(e.steps[0],['peer'])
    # A common fresh-source permission for the same variable already owns the
    # only slot; Web must not append another selected marker.
    payload=reader._payload(e.steps[0],'new-source',['history'],['s1','s2','s3'])
    assert sum(r['review_allowed'] for r in payload['failed_batch_reviews'])==1
    assert not any(r.get('web_review_permission') for r in payload['failed_batch_reviews'])


@pytest.mark.parametrize('tamper_counter',[False,True])
def test_accepted_named_counter_plus_replacement_has_sourced_proof_and_preserves_protected_counter(tamper_counter):
    control={'phase':'old','route':None}
    def respond(i,data):
        if control['phase']=='old':return t.response(t.observation('old-route',['s1']))
        counter=t.observation('fix-counter',['s2'] if control['phase']=='review' and tamper_counter else ['s1'],
            stance='contradiction',retract_ids=[control['route']]);counter['value']=None
        if control['phase']=='bad':
            result=t.response(counter);result['undeclared_envelope']=True;return result
        result=t.response(counter,t.observation('replacement',['s2'],value=['painting']))
        if control['phase']=='review':
            result['slots'][0]['resolved_failed_batch_ids']=[r['id'] for r in data.get('failed_batch_reviews',[]) if r['review_allowed']]
        return result
    reader,e,state,calls=t.web_fixture(respond,max_repairs_per_request=1)
    t.read(reader,'piano','old-valid')
    control.update(phase='bad',route=next(iter(state.routes)))
    t.read(reader,'piano','invalid-containing-envelope')
    protected=[deepcopy(c) for r in reader.failed_batch_reviews.values() for f in r['failed'] for c in f.get('required_counter_observations',[])]
    assert protected and not state.routes[control['route']]['revoked']
    control['phase']='correction'
    t.read(reader,'painting','actual-sourced-counter-correction')
    assert state.routes[control['route']]['revoked'] and state.valid()[0]['history']==['painting']
    grant=next(iter(reader._web_correction_state['grants'].values()))
    assert grant['proof']['kind']=='accepted_named_counter_and_support_correction'
    assert {item['row']['stance'] for item in grant['proof']['accepted']}=={'support','contradiction'}
    control['phase']='review'
    before=len(calls.requests)
    t.read(reader,'painting','one-historical-counter-review')
    assert len(calls.requests)==before+1
    archived=[c for r in calls.requests[-1]['data']['failed_batch_reviews'] for f in r['failed'] for c in f.get('required_counter_observations',[])]
    assert archived and archived[0]['retract_ids']==protected[0]['retract_ids']
    assert state.routes[control['route']]['revoked']
    assert bool(reader.failed_batch_reviews)==tamper_counter
    assert bool(state.pending)==tamper_counter
    assert restore(reader)._web_correction_state==reader._web_correction_state


@pytest.mark.parametrize('resolve',[True,False])
def test_real_web_controller_schedules_one_new_permission_through_old_exhaustion_and_keeps_audit(resolve,monkeypatch,tmp_path):
    import json
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from threading import Thread
    import numpy as np
    from dagbt.methods import RESIDUAL_V2
    from dagbt.transport import digest
    from dagbt.webwalker_control import WebResidualControl
    from dagbt.webwalker_engine import WebEngine
    from test_webwalker import demo
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            raw=('<p>Signal catalogue.</p><a href="/spec">Specification</a>' if self.path=='/' else
                 '<p>The fixture signal is enabled: true.</p>').encode()
            self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(raw)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    planned={'steps':[demo.step('signal','Find whether the fixture signal is enabled.'),
                      demo.step('decision','Report the supported signal flag.',['signal'],'compose')],
        'final_node_id':'decision','output_contract':demo.contract('value','bool','signal'),
        'program':{'variables':{'a':{'type':'bool','demand':'signal'}},'expression':demo.var('a')}}
    class Model:
        def __init__(self):self.requests=[]
        def get(self,stage,url,payload):
            data=json.loads(payload['messages'][1]['content'])
            if isinstance(data,dict):data=t.expand_wire_data(data)
            self.requests.append((stage[0],deepcopy(data)))
            if stage[0]=='planner':value=deepcopy(planned)
            elif stage[0]=='web_navigate':value={'link_id':next(l['id'] for l in data['links'] if l['url'].endswith('/spec'))}
            elif stage[0]=='web_grounding_review':
                sources={source['id']:source for source in data['source_spans']}
                reviews=[]
                for candidate in data['candidates']:
                    row=candidate['observation']
                    grounded=(row['variable']=='a' and row['stance']=='support' and row['value'] is True
                        and row['source_ids'] and all(identifier in sources and
                            'fixture signal is enabled: true' in sources[identifier]['text']
                            for identifier in row['source_ids'])
                        and all(row[key]==value for key,value in data['requested_scopes']['a'].items()))
                    reviews.append({'candidate_id':candidate['candidate_id'],
                        'verdict':'entailed' if grounded else 'not_entailed',
                        'reason':'Check the enabled signal against the cited specification and requested scope.'})
                value={'reviews':reviews}
            else:
                sourced=[s['id'] for s in data['source_spans'] if 'fixture signal is enabled: true' in s['text']]
                audit=stage[0].startswith('audit_joint')
                row={'id':'fix-signal','stance':'support','value':True,'source_ids':sourced or ['invisible-original'],
                     **data['requested_scopes']['a'],'parent_versions':{},'retract_ids':[],'reason':'Explicit invented specification.'}
                slot={'variable':'a','observations':[] if audit else [row],'unresolved':[]}
                if not audit:
                    slot['reading_status']='evidence_assessment'
                    if resolve and any(r.get('web_review_permission') for r in data.get('failed_batch_reviews',[])):
                        slot['resolved_failed_batch_ids']=[r['id'] for r in data['failed_batch_reviews'] if r['review_allowed']]
                value={'slots':[slot]}
                if audit:value['audit_verdict']='supported'
            return {'response_ref':'offline-'+str(len(self.requests)),
                    'response':{'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}}
    model=Model()
    engine=WebEngine({'id':'permission-controller','question':'Is the fixture signal enabled?'},
        ({},[],np.empty((0,0),dtype=np.float32),None,demo.Tokenizer()),model,
        {'_test_transport':True,'llm_base_url':'http://fixture/v1','llm_model':'fixture',
         'webwalker':{'max_actions':36,'http_attempts':1}},RESIDUAL_V2,
        root_url='http://127.0.0.1:'+str(server.server_port),page_cache=tmp_path,allow_local=True)
    seeded={}
    capture=WebJointReader._capture_correction_grants
    def capture_then_seed(self):
        capture(self)
        if self._web_correction_state['grants'] and not seeded:
            control=engine.residual_control;step=engine.steps[0];identity=self.current_identity
            options={'semantic':False,'terminal_output':False,'review_existing_obligations':True,
                     'source_scope':'document_windows','discovery_doc_ids':list(control.local_pools['signal'])}
            material=self.material_signature()
            old_attempt=digest([identity,material,list(control.local_pools['signal']),options])
            old_effect=digest([identity,material])
            control.read_attempts.update([old_attempt,'preserved-other-attempt'])
            control.read_effects.update([old_effect,'preserved-other-effect'])
            control.exhausted.update([identity,'preserved-other-exhaustion'])
            seeded.update(identity=identity,attempt=old_attempt,effect=old_effect,material=material,
                          state=deepcopy(self.state.public_dict()),candidate=control.candidate())
    monkeypatch.setattr(WebJointReader,'_capture_correction_grants',capture_then_seed)
    try:
        result=engine.run();control=engine.residual_control;reader=control.reader
        assert seeded and seeded['candidate'] is None and seeded['state']['pending_variables']==['a']
        assert any(op=='web_grounding_review' for op,data in model.requests)
        assert engine.steps==planned['steps'] and engine.fact_state.valid()[0]['a'] is True
        assert seeded['identity'] in control.exhausted and 'preserved-other-exhaustion' in control.exhausted
        assert seeded['attempt'] in control.read_attempts and 'preserved-other-attempt' in control.read_attempts
        assert seeded['effect'] in control.read_effects and 'preserved-other-effect' in control.read_effects
        assert len(reader._web_correction_state['attempts'])==1
        scheduled=[event for event in engine.events if event['event']=='web_correction_review_scheduled']
        assert len(scheduled)==1 and scheduled[0]['operation_identity'] in control.read_attempts
        assert all(g['consumed'] for g in reader._web_correction_state['grants'].values())
        permission_requests=[data for op,data in model.requests if isinstance(data,dict) and any(r.get('web_review_permission') for r in data.get('failed_batch_reviews',[]))]
        assert len(permission_requests)==1
        assert len(permission_requests[0]['source_spans'])>=2
        if resolve:
            assert result['answer']['status']=='ok' and result['answer']['prediction']=='true'
            assert result['answer']['completion_kind']=='certified_symbolic'
            assert control.certificate is not None and engine.audit_complete
            assert any(op.startswith('audit_joint') for op,data in model.requests)
            assert not reader.failed_batch_reviews and not engine.fact_state.pending
        else:
            assert result['answer']['status']=='unresolved_or_exhausted' and result['answer']['prediction'] is None
            assert not engine.audit_complete and control.certificate is None
            assert reader.failed_batch_reviews and engine.fact_state.pending=={'a'}
            assert reader.material_signature()==seeded['material']
            assert not any(event['event']=='web_task_turn_completed' and event['sequence']>scheduled[0]['sequence'] for event in engine.events)
        assert engine.ledger.limits['llm']==24 and engine.ledger.limits['json_repairs']==6
        assert engine.s['reserved_audit_calls']==1 and engine.s['context_tokens']==16384
        assert engine.s['reasoning_output_tokens']==4096 and engine.s['max_repairs_per_request']==2
        checkpoint=control.snapshot();before=len(model.requests)
        # Baseline WebBridge has no restore method. Validate the saved reader
        # permission and serialized operation caches without claiming complete
        # controller/network restoration.
        restored_reader=restore(reader,checkpoint['reader'])
        assert restored_reader._web_correction_state==reader._web_correction_state
        assert scheduled[0]['operation_identity'] in checkpoint['read_attempts']
        assert not control._web_correction_ticket(engine.steps[0],['a'])
        again=control.run()
        assert len(model.requests)==before and again['answer']['status']==result['answer']['status']
    finally:
        server.shutdown();server.server_close();thread.join()


@pytest.mark.parametrize('options',[{'semantic':True},{'audit':True},{'terminal_output':True},{'source_scope':'mandatory_closure'}])
def test_nonordinary_options_cannot_spend_ticket_to_bypass_common_input_dedup(options):
    from dagbt.webwalker_control import WebResidualControl
    from dagbt.transport import digest
    reader,e,state,calls,_,_=prepared()
    e.fact_state=state
    control=WebResidualControl(e);control.reader=reader
    identity='already-tried-nonordinary'
    old=digest([identity,reader.material_signature(),['painting'],options])
    control.read_attempts.add(old)
    before=len(calls.requests)
    assert control._web_correction_ticket(e.steps[0],['history'],**options) is None
    assert not control.read_progress(e.steps[0],'query',['history'],['painting'],identity,**options)
    assert len(calls.requests)==before and control.read_attempts=={old}
    assert not next(iter(reader._web_correction_state['grants'].values()))['consumed']
    assert not reader.correction_review_lineages({**e.steps[0],'execution':'compose'},['history'])


@pytest.mark.parametrize('malformed',['null-slots','null-observations','malformed-source-list','malformed-retract-list'])
def test_malformed_archived_drafts_never_crash_permission_tracking_or_mint_grants(malformed):
    if malformed=='null-slots': value={'slots':None}
    elif malformed=='null-observations':value={'slots':[{'variable':'history','observations':None,'unresolved':[],'reading_status':'evidence_assessment'}]}
    elif malformed=='malformed-source-list':value=t.response(t.observation('bad',[{'unexpected':'source'}]))
    else:value=t.response(t.observation('bad',['s1'],retract_ids=[{'unexpected':'route'}]))
    reader,e,state,calls=t.web_fixture(lambda i,data:deepcopy(value),max_repairs_per_request=1)
    t.read(reader,'piano','malformed-old')
    assert reader.failed_batch_reviews
    t.read(reader,'painting','malformed-new')
    assert not reader._web_correction_state['grants'] and state.pending


@pytest.mark.parametrize('expansion',['new-draft','expanded-source','both'])
def test_consumed_lineage_cannot_renew_when_new_marker_inherits_original_and_expands(expansion):
    reader,e,state,calls,control,_=prepared(max_repairs=1)
    control['mode']='omit-claim'
    t.read(reader,'painting','consume-existing-permission')
    registry=reader._web_correction_state
    old_id,old_record=next(iter(reader.failed_batch_reviews.items()))
    old_lineage=registry['tracked'][old_id]['lineage']
    assert registry['grants'][old_lineage]['consumed']
    inherited=deepcopy(old_record);inherited['id']='new-inherited-marker';inherited['query_identity']='renamed-inherited-query'
    if expansion in ('new-draft','both'):
        inherited['failed'].append({'id':'extra-defect','variable':'history','feedback':'Additional named failure',
            'observation':{**t.observation('extra-defect',['unbound-source'],value=['guitar']),'variable':'history'}})
    if expansion in ('expanded-source','both'):
        inherited['source_ids']=sorted(set(inherited['source_ids'])|{e.mapper.sources['s3']['source_id']})
    inherited['seen_source_ids']=sorted(s['source_id'] for s in e.mapper.sources.values())
    reader.failed_batch_reviews[inherited['id']]=inherited
    assert reader._marker_family(inherited)!=reader._marker_family(registry['tracked'][old_id]['record'])
    old_route=next(rid for rid,row in state.routes.items() if row['variable']=='history' and not row['revoked'])
    def corrected(i,data):
        counter=t.observation('actual-replacement-counter',['s3'],stance='contradiction',retract_ids=[old_route]);counter['value']=None
        return t.response(counter,t.observation('fix-me',['s3'],value=['guitar']))
    calls.respond=corrected
    t.read(reader,'advice','actual-second-accepted-correction')
    tracked=registry['tracked'][inherited['id']]
    assert tracked['parent_marker_id']==old_id and tracked['lineage']==old_lineage
    assert state.valid()[0]['history']==['guitar'] and state.routes[old_route]['revoked']
    # This is a real second accepted, sourced named correction. Without
    # ancestry, the expanded content hash would mint a second permission.
    assert reader._first_correction_proof(tracked) is not None
    assert len(registry['grants'])==len(registry['attempts'])==1
    assert not reader.correction_review_lineages(e.steps[0],['history'])
    assert restore(reader)._web_correction_state==registry
    snapshot=deepcopy(reader.obligation_snapshot())
    del snapshot[KEY]['tracked'][old_id]
    with pytest.raises(ProtocolError):restore(reader,snapshot)
    snapshot=deepcopy(reader.obligation_snapshot())
    snapshot[KEY]['tracked'][inherited['id']]['parent_marker_id']=None
    snapshot[KEY]['tracked'][inherited['id']]['lineage']=reader._marker_family(inherited)
    # Forging a new root with copied accepted proof cannot inherit the old
    # grant: actual consumed exposure still owns the old ancestor.
    del snapshot[KEY]['grants'][old_lineage]
    with pytest.raises(ProtocolError):restore(reader,snapshot)


@pytest.mark.parametrize('options',[{'semantic':True},{'audit':True},{'terminal_output':True},{'source_scope':'mandatory_closure'}])
def test_direct_reader_nonordinary_mode_never_offers_or_consumes_new_review_permission(options):
    from dagbt.reasoning import InputOverflow
    reader,e,state,calls,_,_=prepared()
    before=(len(calls.requests),e.ledger.used['json_repairs'])
    try:
        reader.read(e.steps[0],'same originals',['history'],['painting'],'nonordinary-direct',**options)
    except (InputOverflow,ProtocolError):
        # mandatory_closure is already compose/audit-only in the common reader.
        assert options.get('source_scope')=='mandatory_closure'
    assert not reader._web_correction_state['attempts']
    assert not next(iter(reader._web_correction_state['grants'].values()))['consumed']
    assert all(not any(row.get('web_review_permission') for row in call['data'].get('failed_batch_reviews',[]))
               for call in calls.requests[before[0]:])
    assert reader.failed_batch_reviews and state.pending
    assert reader._web_correction_ordinary_mode is True


def test_unbound_source_and_counter_target_names_do_not_reset_marker_lineage():
    reader,e,state,calls,_,_=prepared()
    record=deepcopy(next(iter(reader.failed_batch_reviews.values())))
    original=deepcopy(record)
    record['failed'][0]['observation']['source_ids']=['different-unbound-wire-name']
    assert reader._marker_family(record)==reader._marker_family(original)
    original['failed'][0]['observation'].update(stance='contradiction',value=None,retract_ids=['unknown-old-target'])
    record=deepcopy(original)
    record['failed'][0]['observation']['retract_ids']=['unknown-renamed-target']
    assert reader._marker_family(record)==reader._marker_family(original)


def test_restore_rejects_combined_deletion_of_unconsumed_tracking_and_grant():
    reader,e,state,calls,_,_=prepared()
    snapshot=deepcopy(reader.obligation_snapshot())
    snapshot[KEY]['tracked']={};snapshot[KEY]['grants']={}
    with pytest.raises(ProtocolError):restore(reader,snapshot)
    before=reader.material_signature()
    reader._web_correction_state['tracked']={};reader._web_correction_state['grants']={}
    assert reader.material_signature()==before


def test_future_paid_replay_cannot_attribute_correction_to_earlier_accepted_history():
    reader,e,state,calls,_,_=prepared()
    grant=next(iter(reader._web_correction_state['grants'].values()))
    tracked=reader._web_correction_state['tracked'][grant['marker_id']]
    from dagbt.webwalker_correction_review import HISTORY_KEY
    witness=grant['proof']['accepted'][0]['call']
    exposure=next(item for item in reader.source_exposures if item['logical_call_index']==witness)
    original=exposure[HISTORY_KEY]
    # Even with matching ID/value/sources and a genuinely paid raw response,
    # its request must precede the exact integration batch it is proving.
    exposure[HISTORY_KEY]=original+1
    assert reader._first_correction_proof(tracked) is None
    with pytest.raises(ProtocolError):restore(reader)


@pytest.mark.parametrize('mode',['effective','counter-only','same-value','no-target','already-revoked'])
def test_named_invalid_support_corrected_into_counter_requires_actual_revocation_and_changed_supported_value(mode):
    control={'phase':'old','route':None}
    def respond(i,data):
        if control['phase']=='old':return t.response(t.observation('old-valid',['s1']))
        if control['phase']=='bad':return t.response(t.observation('fix-me',['invisible-source'],value=['painting']))
        targets=[] if mode=='no-target' else [control['route']]
        counter=t.observation('fix-me',['s2'],stance='contradiction',retract_ids=targets);counter['value']=None
        if control['phase']=='revoke-old':return t.response(counter)
        rows=[counter]
        if mode!='counter-only':rows.append(t.observation('new-replacement',['s2'],value=['piano'] if mode=='same-value' else ['painting']))
        return t.response(*rows)
    reader,e,state,calls=t.web_fixture(respond,max_repairs_per_request=1)
    t.read(reader,'piano','initial-valid')
    control['route']=next(iter(state.routes))
    if mode=='already-revoked':
        control['phase']='revoke-old';t.read(reader,'painting','old-route-already-revoked')
        assert state.routes[control['route']]['revoked']
    control['phase']='bad';t.read(reader,'piano','named-invalid-support')
    control['phase']='correction';t.read(reader,'advice' if mode=='already-revoked' else 'painting','counter-in-place-and-replacement')
    assert bool(reader._web_correction_state['grants'])==(mode=='effective')
    if mode=='effective':
        grant=next(iter(reader._web_correction_state['grants'].values()))
        assert grant['proof']['kind']=='accepted_named_counter_and_support_correction'
        assert state.routes[control['route']]['revoked'] and state.valid()[0]['history']==['painting']
        assert {r['row']['stance'] for r in grant['proof']['accepted']}=={'support','contradiction'}


def test_legacy_disabled_snapshot_can_be_saved_and_restored_again_without_rearming():
    reader,e,state,calls,_,_=prepared()
    snapshot=deepcopy(reader.obligation_snapshot());del snapshot[KEY]
    disabled=restore(reader,snapshot)
    again=restore(disabled)
    assert again._web_correction_state['enabled'] is False
    assert not again.correction_review_lineages(e.steps[0],['history'])


def test_restore_exception_disables_tampered_object_before_returning_to_caller():
    reader,e,state,calls,control,_=prepared()
    control['mode']='omit-claim';t.read(reader,'painting','consumed')
    snapshot=deepcopy(reader.obligation_snapshot())
    next(iter(snapshot[KEY]['grants'].values()))['consumed']=False
    target=WebJointReader(e,state)
    with pytest.raises(ProtocolError):target.restore_obligations(snapshot)
    assert target._web_correction_state['enabled'] is False
    assert not target.correction_review_lineages(e.steps[0],['history'])


def test_restore_cannot_erase_all_web_metadata_while_true_paid_request_archive_remains():
    from dagbt.webwalker_correction_review import TRACK_KEY
    reader,e,state,calls,control,_=prepared()
    control['mode']='omit-claim';t.read(reader,'painting','actual-paid-review')
    snapshot=deepcopy(reader.obligation_snapshot())
    snapshot[KEY].update(tracked={},grants={},attempts=[])
    for exposure in snapshot['source_exposures']:
        exposure.pop(KEY,None);exposure.pop(TRACK_KEY,None)
    with pytest.raises(ProtocolError):restore(reader,snapshot)
