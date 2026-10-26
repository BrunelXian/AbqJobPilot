"""R16 service policy with explicitly injected process/evidence substitutes.

No positive result here is physical Abaqus evidence. Windows native integration
is tested separately with a fixed Python worker and synthetic text fixtures.
"""
from pathlib import Path
import json
import pytest

from test_standard_backend import case,assert_code,SYNTHETIC_DAT
from abqjobpilot.execution.models import canonical_json,now,CONTRACT,ExecutionError
from abqjobpilot.execution.standard_contract import StandardConfig,management_binding
from abqjobpilot.execution.standard_sequence import prepare_pair,issue_pair
from abqjobpilot.execution.managed_process import ManagedScope
from abqjobpilot.execution import standard_backend as backend
from abqjobpilot.execution.store import document


@pytest.fixture
def pair(case,monkeypatch):
    c=case
    c.service._standard_backend.config=StandardConfig(canonical_json({'interpreter':'unused',
        'process_management':management_binding(),'host_policy':'independent-service-same-windows-session-v1'}))
    second=c.root/'engineering_b';second.mkdir();(second/'scratch').mkdir()
    (second/'axial_bar.inp').write_bytes((c.engineering/'axial_bar.inp').read_bytes())
    c.plans=prepare_pair(c.service,c.engineering,'r016_bar_a_0123abcd',second,'r016_bar_b_0123abcd',expires_at=now()+7200)
    c.grants=issue_pair(c.service,[p['plan_id'] for p in c.plans],approval_source='INJECTED_SCOPE_TEST_NOT_REAL_APPROVAL')
    c.requests=[{'contract_version':CONTRACT,'operation':'submit','project_id':c.ctx.project_id,
        'project_instance_id':c.ctx.project_instance_id,'job_id':p['job_id'],'job_revision':1,'plan_id':p['plan_id'],
        'plan_digest':p['plan_digest'],'grant_id':g['grant_id'],'idempotency_key':'r16-'+str(i),'retry_of':None}
        for i,(p,g) in enumerate(zip(c.plans,c.grants))]
    def no_fallback(*a,**k):raise AssertionError('Managed Standard must never enter unmanaged launch')
    monkeypatch.setattr(backend,'_launch',no_fallback)
    def create(scope,call,out,err):
        scope.started=True;c.calls.append({'call':call,'scope':scope.scope_id})
        plan=next(p for p in c.plans if p['engineering']==call['cwd'])
        root=Path(call['cwd']);(root/(plan['job_name']+'.dat')).write_bytes(SYNTHETIC_DAT.read_bytes())
        (root/(plan['job_name']+'.sta')).write_text('THE ANALYSIS HAS COMPLETED SUCCESSFULLY')
        (root/(plan['job_name']+'.msg')).write_text('THE ANALYSIS HAS BEEN COMPLETED')
        return object()
    monkeypatch.setattr(ManagedScope,'create_standard',create)
    monkeypatch.setattr(ManagedScope,'query',lambda s:{**s.description(),'source':'QueryInformationJobObject.BasicAccounting',
        'creation_confirmed':s.started,'pending_additions':False,'active_processes':0,'total_processes':2,
        'limit_terminated_processes':0,'state':'EMPTY_CONFIRMED'})
    # Substituted OS observations explicitly supply fixed exit evidence; not raw PID disappearance.
    class Observer:
        def __init__(self,child):pass
        def in_scope(self,scope):return True
        def sample(self):return {'process_records':[],'process_exits':[{'role':'wrapper','exit_code':0}],
            'member_completeness':'UNKNOWN','exit_verification':'UNKNOWN','all_observed_exited':True,'observation_unknowns':[]}
        def close(self):pass
    monkeypatch.setattr(backend,'Observer',Observer)
    import time
    monkeypatch.setattr(backend,'time',time)
    return c


def execute(c,i):
    receipt=c.service.submit(c.ctx,c.requests[i])['receipt']
    return c.service.execute_pending(c.ctx,receipt['run_id'])


def test_pair_server_guards_and_success_order(pair):
    c=pair
    assert_code('PREDECESSOR_NOT_QUALIFIED',lambda:c.service.submit(c.ctx,c.requests[1]))
    a=execute(c,0)
    assert a['execution']=='FINISHED' and a['managed_completion']=='COMMITTED_EMPTY_SCOPE'
    assert a['member_completeness']==a['overall_exit']=='UNKNOWN'
    assert a['solver_conclusion']=='COMPLETED_TEXT_EVIDENCE' and a['numerical_validation']=='PRIMARY_THREE_PASS'
    b=execute(c,1);assert b['managed_completion']=='COMMITTED_EMPTY_SCOPE' and len(c.calls)==2
    for i in (0,1):assert c.service.submit(c.ctx,c.requests[i])['replayed']
    with c.store.read() as db:
        events=[{**json.loads(r[1]),'project_sequence':r[0]} for r in db.execute('SELECT sequence,body FROM events ORDER BY sequence')]
        assert db.execute('SELECT run_id FROM slot').fetchone()[0] is None
    end=next(e for e in events if e['run_id']==a['run_id'] and e['type']=='STANDARD_MANAGED_COMPLETED')
    start=next(e for e in events if e['run_id']==b['run_id'] and e['type']=='START_INTENT')
    assert end['project_sequence']<start['project_sequence'] and c.store.gate()['state']=='OPEN'
    report=c.store.diagnose(c.ctx,a['run_id'])
    assert report['body']['facts']['run']['managed_completion']=='COMMITTED_EMPTY_SCOPE'


@pytest.mark.parametrize('dimension',['solver','numerical','exit'])
def test_empty_scope_does_not_qualify_failed_a(pair,monkeypatch,dimension):
    original=backend.collect
    def collect(*a):
        r=original(*a)
        if dimension=='solver':r['solver']='FAILED_TEXT_EVIDENCE'
        if dimension=='numerical':r['numerical']='NUMERICAL_FAIL'
        return r
    monkeypatch.setattr(backend,'collect',collect)
    if dimension=='exit':
        original_sample=backend.Observer.sample
        def sample(self):
            r=original_sample(self);r['process_exits'][0]['exit_code']=23;return r
        monkeypatch.setattr(backend.Observer,'sample',sample)
    a=execute(pair,0);assert a['managed_completion']=='COMMITTED_EMPTY_SCOPE'
    assert pair.store.gate()['state']=='PAUSED'
    assert_code('DISPATCH_PAUSED',lambda:pair.service.submit(pair.ctx,pair.requests[1]))
    # Negative isolated-data fixture: even an explicit later OPEN cannot satisfy A's failed evidence.
    with pair.store.transaction('test_gate') as db:db.execute("UPDATE dispatch_gate SET state='OPEN'")
    assert_code('PREDECESSOR_NOT_QUALIFIED',lambda:pair.service.submit(pair.ctx,pair.requests[1]))
    assert len(pair.calls)==1


@pytest.mark.parametrize('change,code',[('administrative','PREDECESSOR_NOT_QUALIFIED'),('scope_missing','PREDECESSOR_NOT_QUALIFIED'),
    ('window','START_WINDOW_EXPIRED'),('grant','GRANT_EXPIRED'),('output','OUTPUT_CONFLICT'),('input','PLAN_STALE'),('paused','DISPATCH_PAUSED')])
def test_b_rechecks_current_preconditions(pair,monkeypatch,change,code):
    c=pair;a=execute(c,0)
    if change in ('administrative','scope_missing'):
        # Deliberately incomplete/corrupt negative fixture; never used to manufacture a positive case.
        with c.store.transaction('test_negative') as db:
            run=document(db,'runs','run_id',a['run_id'])
            if change=='scope_missing':run['managed_completion']='NOT_CONFIRMED'
            if change=='administrative':run['administrative_closeout']='LOGICAL_SLOT_RELEASED_WITH_RESIDUAL_UNCERTAINTY'
            db.execute('UPDATE runs SET body=? WHERE run_id=?',(canonical_json(run),run['run_id']))
    if change=='window':monkeypatch.setattr('abqjobpilot.execution.standard_sequence.now',lambda:a['created_at']+330)
    if change=='grant':
        with c.store.transaction('test_negative') as db:
            grant=document(db,'grants','grant_id',c.grants[1]['grant_id']);grant['expires_at']=now()-1
            db.execute('UPDATE grants SET body=? WHERE grant_id=?',(canonical_json(grant),grant['grant_id']))
    if change=='output':(Path(c.plans[1]['engineering'])/(c.plans[1]['job_name']+'.odb')).write_bytes(b'conflict-not-odb')
    if change=='input':(Path(c.plans[1]['engineering'])/'axial_bar.inp').write_text('changed')
    if change=='paused':c.store.pause_after_error()
    assert_code(code,lambda:c.service.submit(c.ctx,c.requests[1]));assert len(c.calls)==1


@pytest.mark.parametrize('point',['standard:before_scope_query','standard:before_result_commit','standard_result:before_commit'])
def test_scope_or_transaction_failure_holds_slot(pair,point):
    c=pair
    def fail(name):
        if name==point:raise OSError('injected')
    c.store._checkpoint=fail
    receipt=c.service.submit(c.ctx,c.requests[0])['receipt']
    assert_code('RECONCILIATION_REQUIRED',lambda:c.service.execute_pending(c.ctx,receipt['run_id']))
    c.store._checkpoint=lambda name:None
    with c.store.read() as db:
        assert db.execute('SELECT run_id FROM slot').fetchone()[0]==receipt['run_id']
        assert document(db,'runs','run_id',receipt['run_id']).get('managed_completion')!='COMMITTED_EMPTY_SCOPE'
    assert c.store.gate()['state']=='PAUSED' and len(c.calls)==1
    assert c.service.submit(c.ctx,c.requests[0])['replayed']


def test_ack_loss_replay_and_expiry_between_b_accept_and_create(pair,monkeypatch):
    c=pair;a=execute(c,0)
    def fail(name):
        if name=='accept:after_commit':raise OSError('lost ack')
    c.store._checkpoint=fail
    assert_code('ACCEPTANCE_UNKNOWN',lambda:c.service.submit(c.ctx,c.requests[1]))
    c.store._checkpoint=lambda name:None
    replay=c.service.submit(c.ctx,c.requests[1]);assert replay['replayed']
    rid=replay['receipt']['run_id']
    def expire(name):
        if name=='standard:before_create':monkeypatch.setattr('abqjobpilot.execution.standard_sequence.now',lambda:a['created_at']+330)
    c.store._checkpoint=expire
    assert_code('RECONCILIATION_REQUIRED',lambda:c.service.execute_pending(c.ctx,rid))
    assert len(c.calls)==1 and c.store.query_run(c.ctx,rid)['reconciliation']=='RECONCILIATION_REQUIRED'


def test_no_unmanaged_fallback_and_test_grant_stays_separate(pair,monkeypatch):
    from abqjobpilot.execution.test_authority import issue_process_execution
    assert_code('TEST_GRANT_ONLY',lambda:issue_process_execution(pair.service,pair.plans[0]['plan_id'],expires_at=now()+60))
    monkeypatch.setattr(ManagedScope,'create_standard',lambda *a:(_ for _ in ()).throw(ExecutionError('MANAGED_CREATE_FAILED','test refusal')))
    assert_code('RECONCILIATION_REQUIRED',lambda:execute(pair,0))
    assert pair.calls==[]


def test_known_off_scope_execution_is_not_automatically_closed(pair,monkeypatch):
    monkeypatch.setattr(backend.Observer,'in_scope',lambda self,scope:False)
    assert_code('RECONCILIATION_REQUIRED',lambda:execute(pair,0))
    assert pair.store.gate()['state']=='PAUSED' and len(pair.calls)==1
    with pair.store.read() as db:
        rid=db.execute('SELECT run_id FROM slot').fetchone()[0]
        assert rid and document(db,'runs','run_id',rid)['standard_error']=='MANAGED_SCOPE_UNCOVERED'


@pytest.mark.parametrize('late_empty',[False,True])
def test_deadline_never_releases_slot_or_enables_late_b(pair,monkeypatch,late_empty):
    import time
    tick=[0]
    def clock():tick[0]+=301;return tick[0]
    monkeypatch.setattr(backend,'time',type('Clock',(),{'monotonic':staticmethod(clock),
        'sleep':staticmethod(lambda n:None),'time_ns':staticmethod(time.time_ns)}))
    query=ManagedScope.query
    def bounded(s):
        v=query(s)
        if not late_empty:v.update(active_processes=1,state='ACTIVE')
        return v
    monkeypatch.setattr(ManagedScope,'query',bounded)
    a=execute(pair,0)
    assert a['execution']=='BLOCKED' and a['observation_deadline_reached']
    assert a['managed_completion']!='COMMITTED_EMPTY_SCOPE'
    assert pair.store.gate()['state']=='PAUSED'
    assert_code('DISPATCH_PAUSED',lambda:pair.service.submit(pair.ctx,pair.requests[1]))
    with pair.store.read() as db:assert db.execute('SELECT run_id FROM slot').fetchone()[0]==a['run_id']
    assert len(pair.calls)==1


def test_paused_during_a_completion_does_not_open_gate(pair):
    def pause(name):
        if name=='standard:before_validation':pair.store.pause_after_error()
    pair.store._checkpoint=pause
    a=execute(pair,0)
    assert a['managed_completion']=='COMMITTED_EMPTY_SCOPE'
    assert pair.store.gate()['state']=='PAUSED'
    assert_code('DISPATCH_PAUSED',lambda:pair.service.submit(pair.ctx,pair.requests[1]))


def test_changed_management_is_not_a_new_runtime_choice(pair):
    from abqjobpilot.execution.models import digest
    with pair.store.transaction('negative_fixture') as db:
        p=document(db,'plans','plan_id',pair.plans[0]['plan_id'])
        p['process_management']['policy']='unmanaged'
        p['plan_digest']=digest({k:v for k,v in p.items() if k!='plan_digest'})
        db.execute('UPDATE plans SET body=? WHERE plan_id=?',(canonical_json(p),p['plan_id']))
    pair.requests[0]['plan_digest']=p['plan_digest']
    with pytest.raises(ExecutionError):pair.service.submit(pair.ctx,pair.requests[0])
    assert pair.calls==[]
