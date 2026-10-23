"""R13: Standard creation seam is replaced, with a global no-Abaqus trap."""
from contextlib import closing
from pathlib import Path
import json
import subprocess
import threading
import time

import pytest

from abqjobpilot.execution import create_experiment,ExperimentStore,ExecutionService
from abqjobpilot.execution.models import ExecutionError,CONTRACT,canonical_json,digest,now
from abqjobpilot.execution.standard_contract import StandardConfig,prepare,issue_execution,BACKEND,RESOURCES
from abqjobpilot.execution import standard_backend as backend
from abqjobpilot.execution.store import document

ROOT=Path(__file__).resolve().parents[1]
HISTORICAL=ROOT/'docs/agent_first/run_011/result_review_001/ORIGINAL_DAT.bin'


@pytest.fixture
def case(tmp_path,monkeypatch):
    def forbidden(*a,**k): raise AssertionError('Any real process creation is forbidden in offline Standard cases')
    for method in ('Popen','run','call','check_output','check_call'): monkeypatch.setattr(subprocess,method,forbidden)
    monkeypatch.setattr(StandardConfig,'verify',lambda self: None)
    monkeypatch.setattr(backend,'check_host',lambda config:{'eligible':True,'scope':'INJECTED_TEST_NOT_HOST_ACCEPTANCE'})
    ctx=create_experiment(tmp_path,tmp_path/'project')
    engineering=tmp_path/'engineering'; engineering.mkdir(); (engineering/'scratch').mkdir()
    (engineering/'axial_bar.inp').write_bytes((ROOT/'docs/agent_first/run_010/axial_bar.inp').read_bytes())
    config=StandardConfig(canonical_json({'test_config':'no_real_capability','interpreter':'unused'}))
    store=ExperimentStore(ctx); service=ExecutionService(ctx,store,standard_config=config,client_namespace='r13')
    plan=prepare(service,engineering,'r013_bar_0123abcd',expires_at=now()+7200).to_dict()
    calls=[]
    def launch(call,out,err): calls.append(call); return object()
    monkeypatch.setattr(backend,'_launch',launch); monkeypatch.setattr(backend,'close_reference',lambda child: None)
    class Observer:
        def __init__(self,child): pass
        def sample(self): return {'process_records':[],'process_exits':[], 'member_completeness':'UNKNOWN',
            'exit_verification':'UNKNOWN','all_observed_exited':True,'observation_unknowns':['CONTROLLED_SUBSTITUTE']}
        def close(self): pass
    monkeypatch.setattr(backend,'Observer',Observer)
    # Accelerate the worker's monotonic budget without changing the fixed Plan resource policy.
    tick=[0]
    def clock(): tick[0]+=151; return tick[0]
    monkeypatch.setattr(backend,'time',type('Clock',(),{'monotonic':staticmethod(clock),'sleep':staticmethod(lambda n:None),'time_ns':staticmethod(time.time_ns)}))
    def request(grant='missing',key='r13-one'):
        return {'contract_version':CONTRACT,'operation':'submit','project_id':ctx.project_id,
            'project_instance_id':ctx.project_instance_id,'job_id':plan['job_id'],'job_revision':1,
            'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],'grant_id':grant,'idempotency_key':key,'retry_of':None}
    def approve(): return issue_execution(service,plan['plan_id'],expires_at=now()+3600,approval_source='controlled_substitute_test_only')['grant_id']
    yield type('Case',(),dict(ctx=ctx,store=store,service=service,plan=plan,engineering=engineering,calls=calls,
        request=staticmethod(request),approve=staticmethod(approve),config=config,root=tmp_path))()
    store.close()


def assert_code(code,func):
    with pytest.raises(ExecutionError) as error: func()
    assert error.value.code==code


def test_real_requires_separate_grant_and_opt_in(case):
    c=case
    assert_code('GRANT_REQUIRED',lambda:c.service.submit(c.ctx,c.request()))
    from execution_helpers import FakeGrantFixture
    from abqjobpilot.execution.models import ExecutionPlan
    grant=FakeGrantFixture(c.store).issue_exact(ExecutionPlan.from_dict(c.plan))
    assert_code('REAL_GRANT_REQUIRED',lambda:c.service.submit(c.ctx,c.request(grant)))
    from abqjobpilot.execution.test_authority import issue_process_execution
    assert_code('TEST_GRANT_ONLY',lambda:issue_process_execution(c.service,c.plan['plan_id'],expires_at=now()+10))
    disabled=ExecutionService(c.ctx,c.store)
    assert_code('BACKEND_DISABLED',lambda:disabled.submit(c.ctx,c.request(grant)))
    with c.store.read() as db:
        assert db.execute('select count(*) from runs').fetchone()[0]==0
        assert db.execute('select count(*) from consumption').fetchone()[0]==0
    assert c.calls==[]


@pytest.mark.parametrize('change',['input','project','output','approved','digest','expired'])
def test_changed_or_unapproved_request_never_launches(case,change):
    c=case; req=c.request(c.approve())
    if change=='input': (c.engineering/'axial_bar.inp').write_text('different')
    if change=='project': req['project_instance_id']='wrong'
    if change=='output': (c.engineering/(c.plan['job_name']+'.odb')).write_bytes(b'old')
    if change=='approved': req['approved']=True
    if change=='digest': req['plan_digest']='sha256:'+64*'a'
    if change=='expired':
        with c.store.transaction('fixture') as db:
            grant=document(db,'grants','grant_id',req['grant_id']); grant['expires_at']=now()-1
            db.execute('update grants set body=? where grant_id=?',(canonical_json(grant),req['grant_id']))
    with pytest.raises(ExecutionError): c.service.submit(c.ctx,req)
    assert c.calls==[]
    with c.store.read() as db: assert db.execute('select count(*) from runs').fetchone()[0]==0


def test_durable_receipt_single_launch_separate_partial_dimensions(case,monkeypatch):
    c=case; req=c.request(c.approve()); accepted=c.service.submit(c.ctx,req); rid=accepted['receipt']['run_id']
    assert c.store.query_run(c.ctx,rid)['execution']=='PLANNED'
    def launch(call,out,err):
        assert c.store.query_run(c.ctx,rid)['launch_state']=='CALL_ENTERED_OUTCOME_UNKNOWN'
        assert (c.engineering/('.'+c.plan['job_name']+'.intent.json')).exists()
        c.calls.append(call)
        (c.engineering/(c.plan['job_name']+'.dat')).write_bytes(HISTORICAL.read_bytes())
        (c.engineering/(c.plan['job_name']+'.sta')).write_text('THE ANALYSIS HAS COMPLETED SUCCESSFULLY')
        (c.engineering/(c.plan['job_name']+'.msg')).write_text('THE ANALYSIS HAS BEEN COMPLETED')
        return object()
    monkeypatch.setattr(backend,'_launch',launch)
    run=c.service.execute_pending(c.ctx,rid)
    assert run['solver_conclusion']=='COMPLETED_TEXT_EVIDENCE'
    assert run['numerical_validation']=='PRIMARY_THREE_PASS'
    assert run['artifact_validation']=='VALID' and run['odb_content_validation']=='NOT_RUN'
    assert run['member_completeness']==run['overall_exit']==run['exit_verification']=='UNKNOWN'
    assert run['execution']=='BLOCKED' and run['reconciliation']=='RECONCILIATION_REQUIRED'
    assert c.store.gate()['state']=='PAUSED'
    replay=c.service.submit(c.ctx,req)
    assert replay['receipt']==accepted['receipt'] and replay['replayed']
    with pytest.raises(ExecutionError): c.service.execute_pending(c.ctx,rid)
    assert len(c.calls)==1
    with c.store.read() as db: assert db.execute('select run_id from slot').fetchone()[0]==rid
    report=c.store.diagnose(c.ctx,rid)
    assert report['body']['report_version']=='af-run-diagnostic-v3'
    assert report['body']['facts']['run']['member_completeness']=='UNKNOWN'
    assert not any(d['reason_code']=='FAKE_COMPLETED' for d in report['body']['diagnostics'])
    from abqjobpilot.execution.audit_export import export_report
    # Export signature covered by existing R5 group; report parser must accept v3.
    from abqjobpilot.execution.diagnostics import report_bytes
    assert b'COMPLETED_TEXT_EVIDENCE' in report_bytes(report)


@pytest.mark.parametrize('point',['standard:after_intent','standard:before_create','standard:after_create','standard:before_result_commit'])
def test_creation_commit_crash_windows_remain_blocked(case,point):
    c=case; receipt=c.service.submit(c.ctx,c.request(c.approve()))['receipt']; rid=receipt['run_id']
    def fail(name):
        if name==point: raise OSError('injected store/creation window')
    c.store._checkpoint=fail
    assert_code('RECONCILIATION_REQUIRED',lambda:c.service.execute_pending(c.ctx,rid))
    assert (c.engineering/('.'+c.plan['job_name']+'.intent.json')).exists()
    count=len(c.calls); assert count==(0 if point in ('standard:after_intent','standard:before_create') else 1)
    c.store._checkpoint=lambda name:None
    with pytest.raises(ExecutionError): c.service.execute_pending(c.ctx,rid)
    assert len(c.calls)==count
    assert c.store.query_run(c.ctx,rid)['reconciliation']=='RECONCILIATION_REQUIRED'


def test_host_failure_before_external_attempt(case,monkeypatch):
    c=case; rid=c.service.submit(c.ctx,c.request(c.approve()))['receipt']['run_id']
    monkeypatch.setattr(backend,'check_host',lambda config:{'eligible':False})
    assert_code('RECONCILIATION_REQUIRED',lambda:c.service.execute_pending(c.ctx,rid))
    assert c.calls==[] and not (c.engineering/('.'+c.plan['job_name']+'.intent.json')).exists()


def test_historical_cp936_sample_and_malformed_data():
    from abqjobpilot.execution.standard_dat import parse
    raw=HISTORICAL.read_bytes(); result=parse(raw)
    assert result['numerical']=='PRIMARY_THREE_PASS'
    primary=[v for v in result['comparisons'] if v['group']=='primary']
    from decimal import Decimal
    assert [Decimal(v['actual']) for v in primary]==[Decimal('0.01'),Decimal('1'),Decimal('-1')]
    assert [v['effective_tolerance'] for v in primary]==['0.000001','0.0001','0.0001']
    for content in (b'',raw[:500],raw+raw,raw.replace(b'ANALYSIS COMPLETE',b'NOT COMPLETE')):
        assert parse(content)['numerical']=='EVIDENCE_INSUFFICIENT'


def test_parser_failure_does_not_erase_os_evidence(case,monkeypatch):
    c=case; rid=c.service.submit(c.ctx,c.request(c.approve()))['receipt']['run_id']
    monkeypatch.setattr(backend,'collect',lambda *a: (_ for _ in ()).throw(ExecutionError('EVIDENCE_CHANGED','injected')))
    run=c.service.execute_pending(c.ctx,rid)
    assert run['launch_state']=='PROCESS_OBJECT_RETURNED'
    assert run['result_reason']=='EVIDENCE_CHANGED' and run['solver_conclusion']=='EVIDENCE_INSUFFICIENT'
    assert run['reconciliation']=='RECONCILIATION_REQUIRED'


def test_concurrent_service_claim_single_effect(case,monkeypatch):
    c=case; rid=c.service.submit(c.ctx,c.request(c.approve()))['receipt']['run_id']
    entered=threading.Event(); release=threading.Event()
    original=backend._launch
    def blocked(*args): entered.set(); assert release.wait(5); return original(*args)
    monkeypatch.setattr(backend,'_launch',blocked)
    errors=[]
    def work():
        try: c.service.execute_pending(c.ctx,rid)
        except Exception as e: errors.append(e)
    t=threading.Thread(target=work); t.start(); assert entered.wait(5)
    other=ExecutionService(c.ctx,c.store,standard_config=c.config)
    current=other.execute_pending(c.ctx,rid)
    assert current['execution']=='START_INTENT'
    assert c.store.query_run(c.ctx,rid)['run_id']==rid
    release.set(); t.join(5); assert not t.is_alive() and not errors and len(c.calls)==1


def test_intent_fsync_failure_and_uncertain_creation_preserve_claim(case,monkeypatch):
    c=case;rid=c.service.submit(c.ctx,c.request(c.approve()))['receipt']['run_id']
    monkeypatch.setattr(backend.os,'fsync',lambda f:(_ for _ in ()).throw(OSError('fsync')))
    assert_code('RECONCILIATION_REQUIRED',lambda:c.service.execute_pending(c.ctx,rid))
    assert c.calls==[] and (c.engineering/('.'+c.plan['job_name']+'.intent.json')).exists()
    assert c.store.query_run(c.ctx,rid)['launch_state']=='NOT_CALLED'


def test_creation_error_never_means_safe_to_repeat(case,monkeypatch):
    c=case;rid=c.service.submit(c.ctx,c.request(c.approve()))['receipt']['run_id']
    def uncertain(*a):c.calls.append('attempt');raise OSError('lost creation result')
    monkeypatch.setattr(backend,'_launch',uncertain)
    assert_code('RECONCILIATION_REQUIRED',lambda:c.service.execute_pending(c.ctx,rid))
    assert len(c.calls)==1 and c.store.query_run(c.ctx,rid)['launch_state']=='CALL_ENTERED_OUTCOME_UNKNOWN'
    with pytest.raises(ExecutionError): c.service.execute_pending(c.ctx,rid)
    assert len(c.calls)==1


def test_one_grant_budget_and_dispatch_rechecks(case):
    c=case;grant=c.approve()
    assert_code('GRANT_CONSUMED',c.approve)
    rid=c.service.submit(c.ctx,c.request(grant))['receipt']['run_id']
    (c.engineering/'axial_bar.inp').write_text('changed after acceptance')
    assert_code('PLAN_STALE',lambda:c.service.execute_pending(c.ctx,rid))
    assert c.calls==[] and c.store.query_run(c.ctx,rid)['execution']=='BLOCKED'


def test_cross_project_same_output_identity_cannot_restart(case):
    c=case;other_ctx=create_experiment(c.root,c.root/'other_project')
    with closing(ExperimentStore(other_ctx)) as other_store:
        other=ExecutionService(other_ctx,other_store,standard_config=c.config)
        second=prepare(other,c.engineering,c.plan['job_name'],expires_at=now()+7200).to_dict()
        assert second['output_key']==c.plan['output_key']
        c.service.execute_pending(c.ctx,c.service.submit(c.ctx,c.request(c.approve()))['receipt']['run_id'])
        from abqjobpilot.execution.standard_contract import check_plan
        assert_code('OUTPUT_CONFLICT',lambda:check_plan(other,second))
        assert len(c.calls)==1


def test_live_and_old_text_cannot_be_promoted(case):
    c=case;rid=c.service.submit(c.ctx,c.request(c.approve()))['receipt']['run_id']
    run=c.store.query_run(c.ctx,rid)
    dat=c.engineering/(c.plan['job_name']+'.dat');dat.write_bytes(HISTORICAL.read_bytes())
    # Future intent demonstrates attribution refusal, not a fixture-created success.
    assert_code('EVIDENCE_IDENTITY_MISMATCH',lambda:backend.collect(c.ctx,c.plan,run,{'intent_at_ns':time.time_ns()+10**9},{'all_observed_exited':True}))
    result=backend.collect(c.ctx,c.plan,run,{'intent_at_ns':0},{'all_observed_exited':False})
    assert result['reason']=='OBSERVED_EXIT_INCOMPLETE' and result['numerical']=='EVIDENCE_INSUFFICIENT'


def test_initial_preparation_lease_cannot_bypass_started_owner(case):
    from abqjobpilot.execution.store import acquire_initial_preparation_store,acquire_supervisor_store
    c=case;authority=c.store._session.authority_instance
    assert_code('OWNER_BUSY',lambda:acquire_initial_preparation_store(c.ctx,authority))
    c.store.close()
    with closing(acquire_initial_preparation_store(c.ctx,authority)) as provision:
        with provision.read() as db:assert dict(db.execute('select key,value from meta'))['supervisor_started']=='0'
    with closing(acquire_supervisor_store(c.ctx,authority)):pass
    assert_code('OWNER_UNCONFIRMED',lambda:acquire_initial_preparation_store(c.ctx,authority))
