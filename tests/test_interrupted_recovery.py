"""New isolated Stores only. Standard creator is replaced by the R13 fixture.

Positive policy unit cases use explicitly injected historical OS observations;
actual retained-handle scope proof is exercised in the Windows integration test.
"""
import copy
import json
import threading
from pathlib import Path

import pytest

from test_standard_backend import case, assert_code
from test_standard_closeout import finished, state
from test_product_standard_control import product
from abqjobpilot.execution import recovery, interruption_probe
from abqjobpilot.execution.models import ExecutionError, canonical_json, now
from abqjobpilot.execution.store import document, update_run, ReadOnlyStore


@pytest.fixture
def session(finished, monkeypatch):
    c=finished
    def observed(ctx,run):
        # Synthetic observation, NOT historical or real process-exit proof.
        return {'source':'CURRENT_WINDOWS_READONLY','started_at':now(),'finished_at':now(),
            'owner':{'state':'PROCESS_UNAVAILABLE'},
            'members':[{'state':'PROCESS_UNAVAILABLE','record_index':i} for i,_ in enumerate(run.get('process_records',[]))],
            'boot':{'state':'ESTIMATE_ONLY','confidence':'ESTIMATE_NOT_SESSION_PROOF'},
            'lock':'NOT_ACQUIRED','scope_handle':'NOT_QUERIED'}
    monkeypatch.setattr(interruption_probe,'observe',observed)
    authority=c.store._session.authority_instance;c.store.close()
    with recovery.RecoveryManagementSession(c.ctx,authority,c.rid) as s:
        c.store=s.store;c.service=s.service;c.session=s
        yield c


def permit(c, **overrides):
    values=dict(subject='isolated-operator',source='TEST_ONLY_INJECTED_EVIDENCE',reason='accept residual domain uncertainty',
                expires_at=now()+300,operation_key='recover-once',residual_risk_accepted=True)
    values.update(overrides)
    return c.session.authorize(c.session.preview(),**values)


def test_preview_only_no_ownership_or_files(finished,monkeypatch):
    c=finished;before=state(c);files={p:p.read_bytes() for p in c.root.rglob('*') if p.is_file()}
    monkeypatch.setattr(interruption_probe,'observe',lambda *a:pytest.fail('Preview probes OS'))
    a=recovery.preview_interrupted_recovery(c.ctx,c.rid);b=recovery.preview_interrupted_recovery(c.ctx,c.rid)
    assert a['preview_digest']==b['preview_digest'] and a['body']['decision']==recovery.ADMIN
    assert not a['body']['apply_allowed'] and state(c)==before
    assert files=={p:p.read_bytes() for p in c.root.rglob('*') if p.is_file()}


def test_admin_reuses_original_policy_and_verifies(session):
    c=session;request=permit(c);before=c.store.query_run(c.ctx,c.rid);calls=len(c.calls)
    result=c.session.apply(request);after=c.store.query_run(c.ctx,c.rid)
    for k,v in before.items():
        if k!='revision':assert after[k]==v
    assert result['verification']['recovery_status']=='RECOVERY_APPLIED'
    assert not result['verification']['execution_verified']
    assert after['overall_exit']=='UNKNOWN' and after['administrative_closeout']
    assert c.store.gate()['state']=='PAUSED' and state(c)['slot'][0][1] is None
    assert len(c.calls)==calls and len(state(c)['reconciliations'])==1
    rec=c.store.reconciliations(c.ctx,c.rid)[0]
    assert rec['policy']=='standard-closeout-v1' and rec['retention']['state']=='RETAINED_NO_REUSE'
    assert (c.engineering/('.'+c.plan['job_name']+'.intent.json')).is_file()


@pytest.mark.parametrize('who', ['owner','member'])
@pytest.mark.parametrize('condition',['EXACT_IDENTITY_ALIVE','QUERY_FAILED','BUDGET_EXHAUSTED','IDENTITY_UNRECORDED'])
def test_activity_refuses_apply_and_preserves_everything(session,monkeypatch,who,condition):
    c=session;request=permit(c);before=state(c);original=interruption_probe.observe
    def observed(*a):
        v=original(*a)
        if who=='owner':v['owner']['state']=condition
        else:v['members'][0]['state']=condition
        return v
    monkeypatch.setattr(interruption_probe,'observe',observed)
    assert_code('RECOVERY_ACTIVITY_UNRESOLVED',lambda:c.session.apply(request));assert state(c)==before


@pytest.mark.parametrize('condition',['PROCESS_UNAVAILABLE','IDENTITY_MISMATCH'])
def test_missing_exit_not_replaced_by_pid_or_boot_estimate(session,monkeypatch,condition):
    c=session
    with c.store.transaction('negative_fixture') as db:
        r=document(db,'runs','run_id',c.rid);r['process_exits']=[]
        db.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(r),c.rid))
    original=interruption_probe.observe
    def observed(*a):
        result=original(*a);result['owner']['state']=condition
        for member in result['members']:member['state']=condition
        result['boot']['state']='LATER_BOOT_ESTIMATE'
        return result
    monkeypatch.setattr(interruption_probe,'observe',observed)
    before=state(c);p=c.session.preview()
    diagnostic=ReadOnlyStore(c.ctx).inspect_interrupted_execution(c.ctx,c.rid,observe_os=True)
    assert diagnostic['body']['diagnosis']['display_projection']=='UNKNOWN_INTERRUPTED'
    assert p['body']['decision']==recovery.KEEP
    assert_code('RECOVERY_KEEP_BLOCKED',lambda:permit(c));assert state(c)==before


@pytest.mark.parametrize('problem',['missing','expired','subject','test_only','decision','approved','key','risk'])
def test_exact_permission_required(session,problem):
    c=session;req=permit(c)
    if problem=='missing':req['management_grant_id']='missing'
    elif problem=='approved':req['approved']=True
    elif problem=='subject':req['subject']='different'
    elif problem=='decision':req['decision']=recovery.VERIFIED
    elif problem=='key':req['idempotency_key']='changed'
    elif problem=='risk':req['residual_risk_accepted']=False
    else:
        with c.store.transaction('negative_fixture') as db:
            grant=json.loads(db.execute('SELECT body FROM management_grants WHERE grant_id=?',(req['management_grant_id'],)).fetchone()[0])
            if problem=='expired':grant['expires_at']=now()-1
            else:grant['grant_kind']='TEST_ONLY_MANAGEMENT'
            db.execute('UPDATE management_grants SET body=? WHERE grant_id=?',(canonical_json(grant),grant['grant_id']))
    before=state(c)
    with pytest.raises(ExecutionError):c.session.apply(req)
    assert state(c)==before


def test_explicit_residual_acceptance_and_stale_preview(session):
    c=session
    assert_code('RESIDUAL_RISK_REQUIRED',lambda:permit(c,residual_risk_accepted=False))
    req=permit(c)
    with c.store.transaction('new_evidence') as db:update_run(db,document(db,'runs','run_id',c.rid),'NEW_TEST_EVIDENCE')
    before=state(c);assert_code('STALE_PREVIEW',lambda:c.session.apply(req));assert state(c)==before


def test_same_key_concurrency_conflict_replay(session):
    c=session;req=permit(c);answers=[];errors=[];barrier=threading.Barrier(2)
    def apply():
        try:barrier.wait();answers.append(c.session.apply(req))
        except BaseException as e:errors.append(type(e).__name__)
    threads=[threading.Thread(target=apply) for _ in range(2)]
    for t in threads:t.start()
    for t in threads:t.join(5);assert not t.is_alive()
    assert not errors and sorted(v['replayed'] for v in answers)==[False,True]
    assert answers[0]['receipt']==answers[1]['receipt']
    before=state(c);assert_code('IDEMPOTENCY_CONFLICT',lambda:c.session.apply({**req,'reason':'changed'}))
    assert state(c)==before


@pytest.mark.parametrize('point',['management:before_commit','management:after_commit'])
def test_transaction_response_loss(session,point):
    c=session;req=permit(c);before=state(c)
    def fail(name):
        if name==point:raise OSError('test boundary')
    c.store._checkpoint=fail
    assert_code('STORE_UNAVAILABLE' if point.endswith('before_commit') else 'ACCEPTANCE_UNKNOWN',lambda:c.session.apply(req))
    c.store._checkpoint=lambda name:None
    if point.endswith('before_commit'):assert state(c)==before
    else:
        assert recovery.verify_interrupted_recovery(c.ctx,req)['receipt']==c.session.apply(req)['receipt']
        assert c.session.apply(req)['replayed'] and len(state(c)['reconciliations'])==1


def test_same_lock_rejects_active_owner(finished):
    c=finished;before=state(c)
    assert_code('OWNER_BUSY',lambda:recovery.RecoveryManagementSession(c.ctx,c.store._session.authority_instance,c.rid))
    assert state(c)==before


def test_no_preview_authority_or_solver_grant_change(session):
    c=session;p=c.session.preview();before=state(c)
    with pytest.raises(ExecutionError):c.session.apply(p)
    assert state(c)==before
    assert not hasattr(__import__('abqjobpilot.execution.client',fromlist=['FakeClient']).FakeClient,'authorize_recovery')


def test_closed_run_and_queued_remain_untouched(session):
    c=session;req=permit(c);c.session.apply(req);before=state(c)
    assert c.session.preview()['body']['decision']==recovery.KEEP
    assert_code('RECOVERY_KEEP_BLOCKED',lambda:permit(c,operation_key='not-a-retry'))
    assert state(c)==before


def test_new_empty_product_recovery_is_rejected(tmp_path):
    from abqjobpilot.product_project import create_project
    from abqjobpilot.service_lifecycle import ServiceLifecycleManager
    root=tmp_path/'product';create_project(root,'Recovery isolation')
    manager=ServiceLifecycleManager(root);db=Path(manager.context.execution_store);before=db.read_bytes()
    from abqjobpilot.recovery_management import open_product_recovery
    assert_code('NOT_FOUND',lambda:open_product_recovery(root,'r_'+'1'*32))
    assert db.read_bytes()==before


def test_product_bridge_recorded_managed_scope_and_tamper_guards(product,monkeypatch):
    import time
    from abqjobpilot.execution.managed_process import ManagedScope
    from abqjobpilot.recovery_management import open_product_recovery
    c=product;query=ManagedScope.query
    monkeypatch.setattr(ManagedScope,'query',lambda s:{**query(s),'query_monotonic_ns':time.monotonic_ns()})
    class SimulatedCrash(BaseException):pass
    def crash(point):
        if point=='standard:before_validation':raise SimulatedCrash()
    rid=c.submit(c.approve());c.control.invoke(c.service,c.dispatch(rid));c.store._checkpoint=crash
    with pytest.raises(SimulatedCrash):c.service.execute_pending(c.ctx,rid)
    c.store._checkpoint=lambda n:None
    original=c.store.query_run(c.ctx,rid);assert len(c.calls)==1
    c.store.close()
    monkeypatch.setattr(interruption_probe,'observe',lambda *a:{'source':'INJECTED_NOT_OS_EVIDENCE',
        'owner':{'state':'PROCESS_UNAVAILABLE'},'members':[]})
    with open_product_recovery(c.root,rid) as s:
        p=s.preview();assert p['body']['decision']==recovery.VERIFIED,p['body']['reasons']
        with s.store.read() as db:
            event=db.execute("SELECT event_id,body FROM events WHERE run_id=? AND json_extract(body,'$.type')='STANDARD_CREATED'",(rid,)).fetchone()
        with s.store.transaction('negative_creation_fixture') as db:
            broken=json.loads(event[1]);broken['payload']['launch_state']='CALL_ENTERED_OUTCOME_UNKNOWN'
            db.execute('UPDATE events SET body=? WHERE event_id=?',(canonical_json(broken),event[0]))
        assert s.preview()['body']['decision']!=recovery.VERIFIED
        with s.store.transaction('restore_isolated_creation_fixture') as db:
            db.execute('UPDATE events SET body=? WHERE event_id=?',(event[1],event[0]))
        # Negative evidence fixtures: no authoritative proof from flags alone.
        for field,value in [('scope_id','scope_different'),('active_processes',1),('pending_additions',True),
                            ('query_monotonic_ns',None),('creation_confirmed',False)]:
            with s.store.transaction('negative_fixture') as db:
                r=document(db,'runs','run_id',rid);r['managed_scope'][field]=value
                db.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(r),rid))
            assert s.preview()['body']['decision']!=recovery.VERIFIED
            with s.store.transaction('restore_isolated_fixture') as db:
                db.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(original),rid))
        req=s.authorize(s.preview(),subject='isolated-product-operator',source='INJECTED_FIXED_PYTHON_NOT_REAL_APPROVAL',
            reason='recorded managed evidence reconciliation',expires_at=now()+300,operation_key='product-once')
        result=s.apply(req);after=s.store.query_run(c.ctx,rid)
        assert after['solver_conclusion']==original['solver_conclusion']
        assert after['artifact_validation']==original['artifact_validation']
        assert result['verification']['recovery_status']=='RECOVERY_APPLIED'
        assert s.store.gate()['state']=='PAUSED' and len(c.calls)==1


@pytest.mark.parametrize('absent',[False,True])
def test_process_query_denial_cannot_be_mistaken_for_absence(monkeypatch,absent):
    from abqjobpilot.execution import process_handles
    def fail(*a,**k):
        e=ExecutionError('PROCESS_IDENTITY_UNKNOWN','injected query failure');e.pid_absent=absent;raise e
    monkeypatch.setattr(process_handles,'ProcessReference',fail)
    result=interruption_probe._observe_identity({'pid':123,'creation_time_100ns':123,'image_path':r'C:\fixed-python.exe'})
    assert result['state']==('PROCESS_UNAVAILABLE' if absent else 'QUERY_FAILED')


@pytest.mark.parametrize('change',['project','instance','owner','type','deadline'])
def test_scope_identity_and_expiry_are_exact(session,change):
    c=session;req=permit(c)
    if change=='project':req['project_id']='p_wrong'
    elif change=='instance':req['project_instance_id']='i_wrong'
    elif change=='owner':req['owner_id']='owner_wrong'
    else:
        with c.store.transaction('negative_fixture') as db:
            g=json.loads(db.execute('SELECT body FROM management_grants WHERE grant_id=?',(req['management_grant_id'],)).fetchone()[0])
            if change=='type':g['action']='resume_dispatch'
            else:g['expires_at']=now()-1
            db.execute('UPDATE management_grants SET body=? WHERE grant_id=?',(canonical_json(g),g['grant_id']))
    before=state(c)
    with pytest.raises(ExecutionError):c.session.apply(req)
    assert state(c)==before


def test_competing_requests_cannot_release_twice(session):
    c=session;a=permit(c);b=permit(c,operation_key='competing')
    # Distinct exact permissions do not expand the effects of one revision.
    c.session.apply(a);before=state(c)
    assert_code('STALE_PREVIEW',lambda:c.session.apply(b))
    assert state(c)==before


def test_committed_receipt_survives_later_verification_failure(session,monkeypatch):
    c=session;request=permit(c);first=c.session.apply(request);before=state(c)
    def fail(*a):raise ExecutionError('STORE_UNAVAILABLE','isolated read failure')
    monkeypatch.setattr(recovery,'verify_interrupted_recovery',fail)
    again=c.session.apply(request)
    assert again['replayed'] and again['receipt']==first['receipt']
    assert again['verification']['current_verification']=='NOT_CONFIRMED' and state(c)==before


def test_permission_expiring_during_os_observation_is_rechecked(session,monkeypatch):
    c=session;request=permit(c);before=state(c);original=interruption_probe.observe;expired=now()+1000
    def observed(*a):
        result=original(*a)
        monkeypatch.setattr(recovery.closeout,'now',lambda:expired)
        return result
    monkeypatch.setattr(interruption_probe,'observe',observed)
    assert_code('MANAGEMENT_GRANT_EXPIRED',lambda:c.session.apply(request))
    assert state(c)==before
