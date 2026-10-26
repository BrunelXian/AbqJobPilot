"""Actual Windows fixed Python identities and original Job evidence, no Abaqus."""
from pathlib import Path

from abqjobpilot.execution.models import now
from abqjobpilot.execution.recovery import RecoveryManagementSession, VERIFIED, ADMIN, verify_interrupted_recovery
from abqjobpilot.execution.store import ReadOnlyStore
from test_standard_backend import assert_code
from test_managed_scope import managed, bind, directory
from test_process_fixture import factory
from test_recorded_exit_reconciliation import exited
from test_closeout_windows import Fixture
from supervisor_helpers import read_json,wait_until
from abqjobpilot.execution.models import canonical_json
from abqjobpilot.execution.interruption_probe import observe


def approve(session):
    return session.authorize(session.preview(),subject='isolated-test-operator',source='FIXED_PYTHON_ONLY',
        reason='explicit recovery of this isolated attempt',expires_at=now()+300,
        operation_key='windows-recovery-once',residual_risk_accepted=True)


def release_observer_handles(h):
    """Archive our exit observations then release OUR handles, never feed them to Apply.

    A dead process held by a debugger/observer can refuse a fresh image query.
    Recovery correctly blocks that case; this positive fixture represents the
    later condition where those independent observer handles have been closed.
    """
    rows=[]
    refs=getattr(h,'refs',None)
    if refs is None:refs=list(h.references.values())
    for ref in refs:
        fact=ref.exit_evidence();assert fact is not None;rows.append(fact);ref.close()
    if hasattr(h,'refs'):h.refs.clear()
    if hasattr(h,'references'):h.references.clear()
    for child in h.children:
        assert child.process.poll() is not None
        if child.native:
            api,handle=child.native;assert api.WaitForSingleObject(handle,0)==0
            rows.append({'owner':child.identity,'retained_handle_signaled':True})
            api.CloseHandle(handle);child.native=None
        child.process._handle.Close()  # This test's already-waited Popen handle only.
    (h.root/'recovery-observer-handles.json').write_text(canonical_json(rows),encoding='utf-8')


def await_readonly_observation(context,run,path):
    samples=[]
    def ready():
        value=observe(context,run);samples.append(value)
        return value if all(m['state'] in {'EXACT_IDENTITY_EXITED','PROCESS_UNAVAILABLE','IDENTITY_MISMATCH'}
                            for m in [value['owner'],*value['members']]) else None
    try:return wait_until(ready)
    finally:path.write_text(canonical_json(samples),encoding='utf-8')


def test_original_managed_proof_crash_reconcile_preserves_pending(tmp_path):
    with managed(tmp_path,['normal','normal']) as h:
        owner=h.owner(barriers=['process:after_identity','managed:after_empty']);c=h.client()
        a,b=[c.submit(q)['receipt']['run_id'] for q in h.requests]
        owner.reached('process:after_identity');worker=bind(h,a,'worker');owner.release('process:after_identity')
        owner.reached('managed:after_empty');original=c.run(a);pending=c.run(b)
        assert original['managed_scope']['state']=='EMPTY_CONFIRMED'
        owner.terminate()  # This newly created fixture's identity-retained handle.
        wait_until(worker.exit_evidence)
        authority=read_json(h.bootstrap)['authority_instance']
        release_observer_handles(h)
        await_readonly_observation(h.context,original,h.root/'recovery-pre-admission-observations.json')
        with RecoveryManagementSession(h.context,authority,a) as s:
            p=s.preview();assert p['body']['decision']==VERIFIED,p['body']['reasons']
            request=approve(s);result=s.apply(request);after=s.store.query_run(h.context,a)
            assert after['execution']=='FINISHED' and after['reconciliation']=='NONE'
            assert after['managed_completion']=='NOT_CONFIRMED'  # No counterfeit automatic completion.
            assert after['recovery_scope_completion']=='RECONCILED_RECORDED_EMPTY_SCOPE'
            for key in ('process_records','process_exits','managed_scope','solver_conclusion','artifact_validation'):
                assert after.get(key)==original.get(key)
            assert s.store.query_run(h.context,b)==pending and s.store.gate()['state']=='PAUSED'
            assert s.apply(request)['replayed']
            h.evidence.update(before=original,preview=p,result=result,after=after,pending=pending)
        with RecoveryManagementSession(h.context,authority,a) as s:
            assert s.apply(request)['receipt']==result['receipt']  # Replay is before stale owner checks.
        assert verify_interrupted_recovery(h.context,request)['receipt']==result['receipt']
        assert len(read_json(owner.control/'physical-launches.json'))==1


def test_owner_live_or_dead_with_worker_live_never_releases(tmp_path):
    with managed(tmp_path,['result_wait','normal']) as h:
        owner=h.owner(barriers=['process:after_identity']);c=h.client();a,b=[c.submit(q)['receipt']['run_id'] for q in h.requests]
        owner.reached('process:after_identity');worker=bind(h,a,'worker')
        authority=read_json(h.bootstrap)['authority_instance']
        assert_code('OWNER_BUSY',lambda:RecoveryManagementSession(h.context,authority,a))
        owner.terminate();assert worker.exit_evidence() is None
        before=Path(h.context.execution_store).read_bytes()
        assert_code('RECOVERY_ACTIVITY_UNRESOLVED',lambda:RecoveryManagementSession(h.context,authority,a))
        assert Path(h.context.execution_store).read_bytes()==before
        assert ReadOnlyStore(h.context).query_run(h.context,b)['queue_state']=='PENDING'
        (directory(h,a)/'owner-bound.json').write_text('{}')
        (directory(h,a)/'release.json').write_text('{}');wait_until(worker.exit_evidence)
        h.evidence.update(worker_alive_after_owner_exit=worker.identity,release_refused=True)


def test_recorded_four_roles_uses_existing_r7_policy(factory):
    h=factory('normal',None);rid,receipt,original=exited(h)
    release_observer_handles(h)
    await_readonly_observation(h.context,original,h.root/'recovery-pre-admission-observations.json')
    with RecoveryManagementSession(h.context,read_json(h.bootstrap)['authority_instance'],rid) as s:
        assert s.preview()['body']['policy']['policy']=='recorded-process-reconciliation-v1'
        result=s.apply(approve(s));after=s.store.query_run(h.context,rid)
        assert after['execution']=='FINISHED' and after['exit_verification']=='VERIFIED'
        assert after['solver_conclusion']=='NOT_RUN' and after['artifact_validation']==original['artifact_validation']
        assert s.store.gate()['state']=='PAUSED'
        assert result['verification']['recovery_status']=='RECOVERY_APPLIED'


def test_original_standard_policy_real_python_exits(tmp_path,monkeypatch):
    h=Fixture(tmp_path,monkeypatch);cleaned=False
    try:
        h.start();rid=h.submit();before=h.finish_observation();h.stop()
        h.cleanup();cleaned=True
        await_readonly_observation(h.ctx,before,h.root/'recovery-pre-admission-observations.json')
        with RecoveryManagementSession(h.ctx,h.boot['authority_instance'],rid) as s:
            p=s.preview();assert p['body']['decision']==ADMIN
            request=approve(s);result=s.apply(request);after=s.store.query_run(h.ctx,rid)
            assert after['overall_exit']==before['overall_exit']=='UNKNOWN'
            assert s.store.gate()['state']=='PAUSED' and after['administrative_closeout']
            h.evidence.update(recovery_preview=p,recovery_result=result,recovery_after=after)
    finally:
        if not cleaned:h.cleanup()
