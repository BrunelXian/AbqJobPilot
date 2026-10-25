"""R14 isolated policy tests. No real process creation; evidence injection is labelled."""
from contextlib import closing
import copy
import json
from pathlib import Path
import threading

import pytest

from test_standard_backend import case, assert_code
from abqjobpilot.execution import ExecutionService
from abqjobpilot.execution import closeout, standard_backend
from abqjobpilot.execution.models import canonical_json, now, ExecutionError
from abqjobpilot.execution.store import document, update_run, acquire_supervisor_store, ReadOnlyStore


@pytest.fixture
def finished(case, monkeypatch):
    c=case
    member={'role':'wrapper','pid':12345,'creation_time_100ns':123456789,
            'image_path':r'C:\isolated\fixed-python.exe','observed_at':now(),'identity_status':'VERIFIED'}
    exit_record={**member,'exit_code':0,'exit_observed_at':now(),'exit_source':'direct_Popen_handle'}
    class Observer:
        def __init__(self,child): pass
        def sample(self): return {'process_records':[member], 'process_exits':[exit_record],
            'member_completeness':'UNKNOWN','exit_verification':'UNKNOWN','all_observed_exited':True,
            'observation_unknowns':['INJECTED_UNIT_EVIDENCE_NOT_WINDOWS_ACCEPTANCE']}
        def close(self): pass
    monkeypatch.setattr(standard_backend,'Observer',Observer)
    c.accepted=c.service.submit(c.ctx,c.request(c.approve()))
    c.rid=c.accepted['receipt']['run_id'];c.original=c.service.execute_pending(c.ctx,c.rid)
    c.preview=lambda:c.service.preview_closeout(c.ctx,c.rid)
    c.permission=lambda action=closeout.RELEASE:closeout.issue(c.service,c.preview(),action,
        reason='isolated policy acceptance; unknown full membership retained',
        approval_source='TEST_HARNESS_ONLY_NOT_REAL_INSTANCE',expires_at=now()+600)
    return c


def state(c):
    with c.store.read() as db:
        return {t:list(db.execute('SELECT * FROM '+t)) for t in ('runs','events','validations','observations',
            'reconciliations','consumption','slot','dispatch_gate','management_consumption','management_receipts')}


def test_preview_consistent_read_only_and_no_external_probes(finished,monkeypatch):
    c=finished;before=state(c);files={p:p.read_bytes() for p in c.root.rglob('*') if p.is_file()}
    def forbidden(*a,**k):raise AssertionError('Preview must not execute, validate, probe or write')
    monkeypatch.setattr(standard_backend,'collect',forbidden)
    monkeypatch.setattr(standard_backend,'Observer',forbidden)
    monkeypatch.setattr(c.store,'transaction',forbidden)
    p=c.preview();assert p['actions'][1]['eligible'] and not p['automatic_evidence_closeout']['eligible']
    assert p['historical_facts']['overall_exit']=='UNKNOWN'
    assert state(c)==before and {p:p.read_bytes() for p in c.root.rglob('*') if p.is_file()}==files


def test_explicit_release_preserves_evidence_receipt_gate_and_intent(finished):
    c=finished;req=c.permission();before=state(c)
    result=c.service.apply_closeout(c.ctx,req);run=c.store.query_run(c.ctx,c.rid)
    for key,value in c.original.items():
        if key not in ('revision',): assert run[key]==value
    assert run['administrative_closeout']=='LOGICAL_SLOT_RELEASED_WITH_RESIDUAL_UNCERTAINTY'
    after=state(c)
    for table in ('validations','observations','consumption'):assert before[table]==after[table]
    assert after['slot'][0][1] is None and c.store.gate()['state']=='PAUSED'
    assert (c.engineering/('.'+c.plan['job_name']+'.intent.json')).exists()
    assert c.store.query_receipt(c.ctx,'r13', 'r13-one')==c.accepted['receipt']
    assert len(c.calls)==1 and result['receipt']['projection_at_commit']['evidence_conclusions_unchanged']
    report=c.store.diagnose(c.ctx,c.rid)
    codes=[d['reason_code'] for d in report['body']['diagnostics']]
    assert 'ADMINISTRATIVE_DISPOSITION' in codes and 'EXPLICITLY_RECONCILED' not in codes
    assert 'EXECUTION_UNCERTAIN' in codes and 'DISPATCH_PAUSED' in codes
    from abqjobpilot.execution.diagnostics import report_bytes
    assert b'LOGICAL_SLOT_RELEASED_ONLY' in report_bytes(report)


def test_retain_is_independent_and_does_not_release(finished):
    c=finished;retained=c.service.apply_closeout(c.ctx,c.permission(closeout.RETAIN))
    assert state(c)['slot'][0][1]==c.rid and c.preview()['actions'][1]['eligible']
    released=c.service.apply_closeout(c.ctx,c.permission())
    assert retained['receipt']['operation_id']!=released['receipt']['operation_id']
    assert len(state(c)['reconciliations'])==2 and len(c.calls)==1


@pytest.mark.parametrize('changed',['revision','event','gate','owner'])
def test_stale_assessment_rejected(finished,changed):
    c=finished;req=c.permission()
    if changed=='owner':
        authority=c.store._session.authority_instance;c.store.close()
        c.store=acquire_supervisor_store(c.ctx,authority);c.service=ExecutionService(c.ctx,c.store,client_namespace='r13')
    else:
        with c.store.transaction('isolated_change') as db:
            if changed=='gate':db.execute('UPDATE dispatch_gate SET version=version+1')
            else:update_run(db,document(db,'runs','run_id',c.rid),'TEST_NEW_EVIDENCE')
    before=state(c)
    assert_code('STALE_OWNER' if changed=='owner' else 'STALE_PREVIEW',lambda:c.service.apply_closeout(c.ctx,req))
    assert state(c)==before
    c.store.close()


@pytest.mark.parametrize('problem',['missing','expired','wrong_scope','test_only','approved'])
def test_disposition_requires_independent_exact_operator_permission(finished,problem):
    c=finished;req=c.permission()
    if problem=='missing':req['management_grant_id']='not_registered'
    elif problem=='approved':req['approved']=True
    else:
        with c.store.transaction('isolated_permission_fault') as db:
            grant=json.loads(db.execute('SELECT body FROM management_grants WHERE grant_id=?',(req['management_grant_id'],)).fetchone()[0])
            if problem=='expired':grant['expires_at']=now()-1
            if problem=='wrong_scope':grant['scope']['reason']='different'
            if problem=='test_only':grant['grant_kind']='TEST_ONLY'
            db.execute('UPDATE management_grants SET body=? WHERE grant_id=?',(canonical_json(grant),grant['grant_id']))
    before=state(c)
    with pytest.raises(ExecutionError):c.service.apply_closeout(c.ctx,req)
    assert state(c)==before and len(c.calls)==1


def test_replay_conflict_concurrent_effect_once_and_new_owner_replay(finished):
    c=finished;req=c.permission();barrier=threading.Barrier(2);answers=[]
    other=ExecutionService(c.ctx,c.store,client_namespace='r13')
    def apply(s):barrier.wait();answers.append(s.apply_closeout(c.ctx,req))
    threads=[threading.Thread(target=apply,args=(s,)) for s in (c.service,other)]
    for t in threads:t.start()
    for t in threads:t.join(5);assert not t.is_alive()
    assert len(answers)==2 and sorted(a['replayed'] for a in answers)==[False,True]
    assert answers[0]['receipt']==answers[1]['receipt'] and len(state(c)['reconciliations'])==1
    assert_code('IDEMPOTENCY_CONFLICT',lambda:c.service.apply_closeout(c.ctx,{**req,'reason':'different'}))
    authority=c.store._session.authority_instance;c.store.close()
    with closing(acquire_supervisor_store(c.ctx,authority)) as store:
        service=ExecutionService(c.ctx,store,client_namespace='r13')
        gate=store.gate();assert gate['state']=='PAUSED'
        assert service.apply_closeout(c.ctx,req)['receipt']==answers[0]['receipt']
        assert store.gate()==gate
        assert_code('STALE_OWNER',lambda:service.apply_closeout(c.ctx,{**req,'idempotency_key':'new-key'}))
        assert store.query_run(c.ctx,c.rid)['overall_exit']=='UNKNOWN'


def test_competing_dispositions_cannot_both_change_same_revision(finished):
    c=finished;retain=c.permission(closeout.RETAIN);release=c.permission()
    c.service.apply_closeout(c.ctx,retain)
    assert_code('STALE_PREVIEW',lambda:c.service.apply_closeout(c.ctx,release))
    assert state(c)['slot'][0][1]==c.rid and len(state(c)['reconciliations'])==1


@pytest.mark.parametrize('point',['management:before_commit','management:after_commit'])
def test_transaction_and_lost_response_no_unrecorded_release(finished,point):
    c=finished;req=c.permission();before=state(c)
    def fail(name):
        if name==point:raise OSError('injected commit boundary')
    c.store._checkpoint=fail
    assert_code('STORE_UNAVAILABLE' if point.endswith('before_commit') else 'ACCEPTANCE_UNKNOWN',lambda:c.service.apply_closeout(c.ctx,req))
    c.store._checkpoint=lambda name:None
    if point.endswith('before_commit'):assert state(c)==before
    else:
        after=state(c);assert after['slot'][0][1] is None and len(after['management_receipts'])==1
        assert len(after['management_consumption'])==1 and len(after['reconciliations'])==1
        assert c.service.apply_closeout(c.ctx,req)['replayed'] and state(c)==after
    assert len(c.calls)==1


@pytest.mark.parametrize('missing',['member','exit','identity','observation_end','consumption'])
def test_insufficient_evidence_cannot_release(finished,missing):
    c=finished
    with c.store.transaction('isolated_negative_evidence') as db:
        r=document(db,'runs','run_id',c.rid)
        if missing=='member':r['process_records']=[]
        elif missing=='exit':r['process_exits']=[]
        elif missing=='identity':r['process_exits'][0]['creation_time_100ns']+=1
        elif missing=='observation_end':r['observation_deadline_reached']=False
        else:db.execute('DELETE FROM consumption')
        db.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(r),c.rid))
    if missing=='consumption':assert_code('EVIDENCE_INSUFFICIENT',c.preview)
    else:
        p=c.preview();assert not p['actions'][1]['eligible']
        assert_code('CLOSEOUT_PRECONDITION_FAILED',c.permission)
    assert state(c)['slot'][0][1]==c.rid


def test_separate_resume_quarantine_and_pending_prerequisites(finished):
    c=finished
    assert_code('RECONCILIATION_REQUIRED',lambda:closeout.issue_resume(c.service,
        expected_gate_version=c.store.gate()['version'],approval_source='test',expires_at=now()+10))
    c.service.apply_closeout(c.ctx,c.permission())
    resume=closeout.issue_resume(c.service,expected_gate_version=c.store.gate()['version'],approval_source='separate-test',expires_at=now()+100)
    assert c.store.gate()['state']=='PAUSED'
    c.service.resume_dispatch(c.ctx,resume);assert c.store.gate()['state']=='OPEN'
    assert c.store.pending_for_owner() is None
    # A new job name/plan cannot reclaim either the old engineering tree or scratch.
    from abqjobpilot.execution.standard_contract import prepare,check_plan
    assert_code('RESOURCE_RETAINED',lambda:prepare(c.service,c.engineering,'r013_bar_a123abcd',expires_at=now()+600))
    authority=c.store._session.authority_instance;c.store.close()
    with closing(acquire_supervisor_store(c.ctx,authority)) as store:
        service=ExecutionService(c.ctx,store,client_namespace='r13')
        gate=store.gate();assert gate['state']=='PAUSED'
        assert service.resume_dispatch(c.ctx,resume)['replayed'] and store.gate()==gate
        with store.read() as db:assert closeout.administratively_released(db,document(db,'runs','run_id',c.rid))


def test_test_only_resume_cannot_approve_real_residual_risk(finished):
    from reconciliation_helpers import FakeManagementFixture,management_request
    c=finished;c.service.apply_closeout(c.ctx,c.permission())
    scope={'expected_gate_version':c.store.gate()['version']}
    grant=FakeManagementFixture(c.store).issue('resume_dispatch',scope)
    req=management_request(c.ctx,c.store._session.owner_id,'resume_dispatch',scope,grant,'test-cannot-open')
    before=state(c)
    with pytest.raises(ExecutionError):c.service.resume_dispatch(c.ctx,req)
    assert state(c)==before and c.store.gate()['state']=='PAUSED'


def test_remaining_uncertainty_blocks_independent_resumption(finished):
    c=finished;c.service.apply_closeout(c.ctx,c.permission())
    # Negative fixture only: another unresolved Run is not silently ignored.
    with c.store.transaction('isolated_second_uncertain') as db:
        r=copy.deepcopy(c.original);r['run_id']='r_'+'9'*32;r['attempt_no']=2
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)',(r['run_id'],r['job_id'],r['job_revision'],
            r['plan_id'],r['grant_id'],2,None,canonical_json(r)))
    assert_code('RECONCILIATION_REQUIRED',lambda:closeout.issue_resume(c.service,
        expected_gate_version=c.store.gate()['version'],approval_source='test',expires_at=now()+100))
    assert c.store.gate()['state']=='PAUSED'


def test_preview_limit_busy_and_legacy_diagnostic_compatibility(finished):
    c=finished
    entered=threading.Event();release=threading.Event()
    def hold():
        with c.store._session.lock:entered.set();release.wait(3)
    t=threading.Thread(target=hold);t.start();assert entered.wait(2)
    try:assert_code('STORE_UNAVAILABLE',c.preview)
    finally:release.set();t.join()
    from abqjobpilot.execution.diagnostics import report_bytes
    from abqjobpilot.execution.models import digest
    report=c.store.diagnose(c.ctx,c.rid)
    report['body']['rules_version']='standard-diagnostic-rules-v1'
    for k in ('administrative_closeout','disposition_record_id','disposition_action'):report['body']['facts']['run'].pop(k)
    report['content_digest']=digest(report['body'])
    assert report_bytes(report)
    with c.store.transaction('isolated_limit') as db:
        r=document(db,'runs','run_id',c.rid);r['oversized']='x'*262145
        db.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(r),c.rid))
    assert_code('LIMIT_EXCEEDED',c.preview)


def test_trusted_operator_entry_refuses_active_owner_and_has_no_backend(finished,monkeypatch,capsys):
    import importlib.util
    import sys
    c=finished;path=Path(__file__).resolve().parents[1]/'examples/agent_first/standard_closeout_operator.py'
    spec=importlib.util.spec_from_file_location('r14_operator',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    bootstrap={'context':c.ctx.to_dict(),'authority_instance':c.store._session.authority_instance,
        'credential':'isolated-test-private-secret-000000000000000','client_namespace':'r13','endpoint_file':str(c.root/'endpoint.json')}
    private=c.root/'bootstrap.json';private.write_text(canonical_json(bootstrap))
    args=[str(path),'preview','--test-root',str(c.root),'--bootstrap',str(private),'--run-id',c.rid]
    monkeypatch.setattr(sys,'argv',args);before=state(c)
    assert module.main()==0 and state(c)==before
    assert bootstrap['credential'] not in capsys.readouterr().out
    args[1]='review-and-decide';monkeypatch.setattr(sys.stdin,'isatty',lambda:True)
    assert module.main()==2 and state(c)==before
    assert 'OWNER_BUSY' in capsys.readouterr().out
    c.store.close()
    answers=iter([closeout.RELEASE,'TEST ONLY residual risk accepted','test human reference'])
    monkeypatch.setattr('builtins.input',lambda prompt='':next(answers))
    assert module.main()==0
    from abqjobpilot.execution.store import ReadOnlyStore
    ro=ReadOnlyStore(c.ctx)
    assert ro.query_run(c.ctx,c.rid)['administrative_closeout']=='LOGICAL_SLOT_RELEASED_WITH_RESIDUAL_UNCERTAINTY'
    assert ro.gate()['state']=='PAUSED' and len(c.calls)==1
    private.unlink() # Only this test's own credential material, after lease closed.


def test_preview_cannot_mix_concurrent_sqlite_views(finished,monkeypatch):
    import sqlite3
    c=finished;writer_updated=threading.Event();start_writer=threading.Event();errors=[]
    before=c.preview()
    def writer():
        start_writer.wait(2)
        db=sqlite3.connect(c.ctx.execution_store,timeout=3)
        try:
            db.execute('BEGIN IMMEDIATE')
            update_run(db,document(db,'runs','run_id',c.rid),'TEST_NEW_EVIDENCE')
            db.execute('UPDATE dispatch_gate SET version=version+1')
            writer_updated.set();db.commit()
        except Exception as exc:errors.append(exc)
        finally:db.close()
    original=closeout._rows;called=[]
    def interleave(*a,**kw):
        if not called:
            called.append(True);start_writer.set();assert writer_updated.wait(.5)
        return original(*a,**kw)
    thread=threading.Thread(target=writer);thread.start()
    monkeypatch.setattr(closeout,'_rows',interleave)
    observed=c.preview();thread.join(4)
    assert not thread.is_alive() and not errors
    assert observed['preview_digest']==before['preview_digest']
    after=c.preview()
    assert after['run_revision']==before['run_revision']+1
    assert after['recorded_gate']['version']==before['recorded_gate']['version']+1
