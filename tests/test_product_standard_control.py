"""Run021B: fresh product stores; all real process creation trapped.

Native Job query is substituted here. Windows end-to-end tests separately use
real fixed Python children and the native Job path. No positive fixture edits
Grant/Run/dispatch records directly.
"""
from pathlib import Path
from types import SimpleNamespace
import concurrent.futures
import subprocess
import sys
import threading

import pytest
from abqjobpilot.product_project import create_project
from abqjobpilot.product_standard import prepare_product
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.local_credentials import read_private
from abqjobpilot.execution.models import CONTRACT, ExecutionError, canonical_json, digest, now
from abqjobpilot.execution.standard_contract import StandardConfig, management_binding
from abqjobpilot.execution.product_standard import ProductStandardControl
from abqjobpilot.execution.service import ExecutionService
from abqjobpilot.execution.store import acquire_initial_preparation_store, document
from abqjobpilot.execution.lifecycle import LifecycleControl, require_idle
from abqjobpilot.execution.managed_process import ManagedScope
from abqjobpilot.execution import standard_backend as backend

SOURCE=Path(__file__).resolve().parents[1]
SYNTHETIC_DAT=SOURCE/'tests/fixtures/synthetic/standard_axial_cp936.txt'


@pytest.fixture
def product(tmp_path,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('No real process creation in isolated control tests')
    for name in ('Popen','run','call','check_output','check_call'):monkeypatch.setattr(subprocess,name,forbidden)
    monkeypatch.setattr(backend,'_launch',forbidden)
    monkeypatch.setattr(StandardConfig,'verify',lambda s:None)
    monkeypatch.setattr(backend,'check_host',lambda c:{'eligible':True,'source':'INJECTED_NOT_HOST_ACCEPTANCE'})
    root=tmp_path/'product';create_project(root,'Control substitute')
    engineering=root/'engineering';engineering.mkdir();(engineering/'scratch').mkdir()
    (engineering/'axial_bar.inp').write_bytes((SOURCE/'docs/agent_first/run_010/axial_bar.inp').read_bytes())
    config=StandardConfig(canonical_json({'interpreter':sys.executable,'process_management':management_binding(),
        'host_policy':'independent-service-same-windows-session-v1','fixture_only':True}))
    plan=prepare_product(root,engineering,'r021_bar_1234abcd',config,expires_at=now()+3600)
    manager=ServiceLifecycleManager(root);profile=manager._profile();ctx=manager.context
    store=acquire_initial_preparation_store(ctx,profile['authority_instance'])
    service=ExecutionService(ctx,store,standard_config=config,client_namespace=profile['client_namespace'])
    binding=profile['standard_extension']['binding'];control=ProductStandardControl(binding);service.product_control=control
    token=read_private(ctx,manager._path('standard-operator.json'))['operator_token']
    lifecycle=LifecycleControl(profile['operator_digest'],'start_test',standard_binding=binding)
    calls=[]
    def create(scope,call,out,err):
        scope.started=True;calls.append(call)
        (engineering/(plan['job_name']+'.dat')).write_bytes(SYNTHETIC_DAT.read_bytes())
        (engineering/(plan['job_name']+'.sta')).write_text('THE ANALYSIS HAS COMPLETED SUCCESSFULLY')
        (engineering/(plan['job_name']+'.msg')).write_text('THE ANALYSIS HAS BEEN COMPLETED')
        return object()
    monkeypatch.setattr(ManagedScope,'create_standard',create)
    monkeypatch.setattr(ManagedScope,'query',lambda s:{**s.description(),'source':'QueryInformationJobObject.BasicAccounting',
        'creation_confirmed':s.started,'pending_additions':False,'active_processes':0,'total_processes':2,
        'limit_terminated_processes':0,'state':'EMPTY_CONFIRMED'})
    class Observer:
        def __init__(self,child):pass
        def in_scope(self,s):return True
        def sample(self):return {'process_records':[],'process_exits':[{'role':'wrapper','exit_code':0}],
            'member_completeness':'UNKNOWN','exit_verification':'UNKNOWN','all_observed_exited':True,'observation_unknowns':[]}
        def close(self):pass
    monkeypatch.setattr(backend,'Observer',Observer)
    monkeypatch.setattr(backend,'close_reference',lambda child:None)
    c=SimpleNamespace(root=root,ctx=ctx,store=store,service=service,control=control,plan=plan,token=token,
                      manager=manager,lifecycle=lifecycle,calls=calls,engineering=engineering)
    c.operation=lambda action,args,key='op':{'action':action,'arguments':args,'operation_key':key,
        'operator_token':token,'owner_id':store._session.owner_id}
    c.approval=c.operation('authorize',{'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],
        'expires_at':now()+500,'subject':'isolated-substitute-controller','source':'NO_ABAQUS_FIXED_TEST'},'authorize')
    c.approve=lambda:control.invoke(service,c.approval)['receipt']['grant_id']
    c.request=lambda gid,key='submit':{'contract_version':CONTRACT,'operation':'submit','project_id':ctx.project_id,
        'project_instance_id':ctx.project_instance_id,'job_id':plan['job_id'],'job_revision':1,'plan_id':plan['plan_id'],
        'plan_digest':plan['plan_digest'],'grant_id':gid,'idempotency_key':key,'retry_of':None}
    c.submit=lambda gid:service.submit(ctx,c.request(gid))['receipt']['run_id']
    def dispatch(rid,key='dispatch'):
        r=store.query_run(ctx,rid)
        return c.operation('dispatch_once',{'run_id':rid,'revision':r['revision'],'gate_version':store.gate()['version'],
                                           'start_not_after':now()+25},key)
    c.dispatch=dispatch
    c.stop=lambda:lifecycle.stop(service,{'owner_id':store._session.owner_id,'operation_key':'stop',
                                         'operator_token':manager._operator()})
    try:yield c
    finally:store.close()


def rejected(code,call):
    with pytest.raises(ExecutionError) as exc:call()
    assert exc.value.code==code


def test_exact_approval_paused_accept_single_dispatch_and_idle_stop(product):
    c=product;gid=c.approve();rid=c.submit(gid)
    assert c.store.gate()['state']=='PAUSED' and c.calls==[]
    rejected('DISPATCH_PAUSED',lambda:c.service.execute_pending(c.ctx,rid))
    c.control.blocked=False # this direct negative call was not the owner poller
    req=c.dispatch(rid);first=c.control.invoke(c.service,req)
    assert c.store.gate()['state']=='PAUSED'
    result=c.service.execute_pending(c.ctx,rid)
    assert result['managed_completion']=='COMMITTED_EMPTY_SCOPE' and result['execution']=='FINISHED'
    assert result['solver_conclusion']=='COMPLETED_TEXT_EVIDENCE' and result['numerical_validation']=='PRIMARY_THREE_PASS'
    assert result['overall_exit']==result['member_completeness']=='UNKNOWN' and result['odb_content_validation']=='NOT_RUN'
    assert c.control.invoke(c.service,req)['receipt']==first['receipt']
    assert c.control.invoke(c.service,c.approval)['replayed']
    assert c.service.submit(c.ctx,c.request(gid))['replayed'] and len(c.calls)==1
    with c.store.read() as db:
        assert db.execute('SELECT run_id FROM slot').fetchone()[0] is None
        grant=document(db,'grants','grant_id',gid)
        assert grant['approval_subject']=='isolated-substitute-controller' and grant['product_scope']['input_manifest']==c.plan['input_manifest']
        assert db.execute('SELECT COUNT(*) FROM consumption').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM management_receipts').fetchone()[0]==2
    assert c.stop()['receipt']['state']=='STOP_COMMITTED' and c.store.gate()['state']=='PAUSED'


@pytest.mark.parametrize('token_kind',['connection','lifecycle','self_admin'])
def test_connection_and_stop_permissions_cannot_approve(product,token_kind):
    c=product;req=dict(c.approval)
    req['operator_token']=c.manager._profile()['credential'] if token_kind=='connection' else (c.manager._operator() if token_kind=='lifecycle' else 'admin')
    rejected('REAL_OPERATOR_REQUIRED',lambda:c.control.invoke(c.service,req))
    with c.store.read() as db:assert db.execute('SELECT COUNT(*) FROM grants').fetchone()[0]==0


@pytest.mark.parametrize('change',['input','plan_digest','project','approved','output','expiry','test_grant'])
def test_admission_denies_changed_or_test_authority(product,change):
    c=product;gid=c.approve();req=c.request(gid)
    if change=='input':(c.engineering/'axial_bar.inp').write_text('changed')
    if change=='plan_digest':req['plan_digest']='wrong'
    if change=='project':req['project_id']='wrong'
    if change=='approved':req['approved']=True
    if change=='output':(c.engineering/(c.plan['job_name']+'.odb')).write_bytes(b'not an ODB')
    if change=='expiry':
        with c.store.transaction('negative_fixture') as db:
            g=document(db,'grants','grant_id',gid);g['expires_at']=now()-1
            db.execute('UPDATE grants SET body=? WHERE grant_id=?',(canonical_json(g),gid))
    if change=='test_grant':
        from execution_helpers import FakeGrantFixture
        from abqjobpilot.execution.models import ExecutionPlan
        req['grant_id']=FakeGrantFixture(c.store).issue_exact(ExecutionPlan.from_dict(c.plan))
    with pytest.raises(ExecutionError):c.service.submit(c.ctx,req)
    assert c.calls==[]
    with c.store.read() as db:assert db.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==0


def test_consumption_keys_and_concurrent_dispatch(product):
    c=product;gid=c.approve()
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        rows=list(pool.map(lambda _:c.service.submit(c.ctx,c.request(gid)),range(4)))
    rid=rows[0]['receipt']['run_id'];assert all(r['receipt']==rows[0]['receipt'] for r in rows)
    rejected('GRANT_CONSUMED',lambda:c.service.submit(c.ctx,c.request(gid,'second')))
    req=c.dispatch(rid)
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        replies=list(pool.map(lambda _:c.control.invoke(c.service,req),range(4)))
    assert sum(not r['replayed'] for r in replies)==1
    changed={**req,'arguments':{**req['arguments'],'start_not_after':req['arguments']['start_not_after']-1}}
    rejected('IDEMPOTENCY_CONFLICT',lambda:c.control.invoke(c.service,changed))
    rejected('STALE_DISPATCH',lambda:c.control.invoke(c.service,c.dispatch(rid,'new-key')))
    c.service.execute_pending(c.ctx,rid);assert len(c.calls)==1


@pytest.mark.parametrize('change',['revision','gate','owner','wrong_run','expired_window','output'])
def test_precise_dispatch_preconditions(product,change):
    c=product;rid=c.submit(c.approve());req=c.dispatch(rid)
    if change=='revision':req['arguments']['revision']+=1
    if change=='gate':req['arguments']['gate_version']+=1
    if change=='owner':req['owner_id']='wrong-owner'
    if change=='wrong_run':req['arguments']['run_id']='r_wrong'
    if change=='expired_window':req['arguments']['start_not_after']=now()-1
    if change=='output':(c.engineering/(c.plan['job_name']+'.dat')).write_bytes(b'old')
    with pytest.raises(ExecutionError):c.control.invoke(c.service,req)
    assert c.calls==[] and c.store.gate()['state']=='PAUSED'


@pytest.mark.parametrize('point',['management:before_commit','product_control:after_commit','claim:before_commit',
    'standard:after_intent','standard:after_create','standard:before_scope_query','standard_result:before_commit'])
def test_faults_never_unrecorded_open_or_retry(product,point):
    c=product;rid=c.submit(c.approve());req=c.dispatch(rid)
    def fail(name):
        if name==point:raise OSError('controlled storage failure')
    if point.startswith(('management','product_control')):
        c.store._checkpoint=fail
        with pytest.raises((OSError,ExecutionError)):c.control.invoke(c.service,req)
        c.store._checkpoint=lambda n:None
        if point.startswith('product_control'):assert c.control.invoke(c.service,req)['replayed']
        else:assert 'single_dispatch' not in c.store.query_run(c.ctx,rid)
        assert not c.calls
    else:
        c.control.invoke(c.service,req);c.store._checkpoint=fail
        with pytest.raises(ExecutionError):c.service.execute_pending(c.ctx,rid)
        count=len(c.calls);c.store._checkpoint=lambda n:None
        rejected('DISPATCH_PAUSED',lambda:c.service.execute_pending(c.ctx,rid))
        assert len(c.calls)==count and c.control.blocked
    assert c.store.gate()['state']=='PAUSED'


def test_window_checked_again_after_launch_intent_barrier(product,monkeypatch):
    c=product;rid=c.submit(c.approve());req=c.dispatch(rid);c.control.invoke(c.service,req)
    def barrier(name):
        if name=='standard:before_create':monkeypatch.setattr('abqjobpilot.execution.product_standard.now',lambda:req['arguments']['start_not_after'])
    c.store._checkpoint=barrier
    rejected('RECONCILIATION_REQUIRED',lambda:c.service.execute_pending(c.ctx,rid))
    assert c.calls==[] and c.store.query_run(c.ctx,rid)['launch_state']=='CALL_ENTERED_OUTCOME_UNKNOWN'


def test_stop_pending_unknown_and_racing_submit(product):
    c=product;gid=c.approve();rid=c.submit(gid)
    rejected('SERVICE_NOT_IDLE',c.stop)
    c.control.invoke(c.service,c.dispatch(rid))
    entered=threading.Event();release=threading.Event()
    def barrier(name):
        if name=='standard:after_intent':entered.set();assert release.wait(5)
    c.store._checkpoint=barrier
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        future=pool.submit(c.service.execute_pending,c.ctx,rid);assert entered.wait(5)
        rejected('SERVICE_NOT_IDLE',c.stop);release.set();future.result()
    c.stop()
    rejected('SERVICE_STOPPING',lambda:c.service.submit(c.ctx,c.request(gid,'new')))


def test_general_resume_and_direct_issuer_cannot_bypass(product):
    c=product
    rejected('DISPATCH_POLICY_MISMATCH',lambda:c.service.resume_dispatch(c.ctx,{}))
    from abqjobpilot.execution.standard_contract import issue_execution
    rejected('REAL_OPERATOR_REQUIRED',lambda:issue_execution(c.service,c.plan['plan_id'],expires_at=now()+30,approval_source='unscoped'))
    with c.store.read() as db:require_idle(db,standard_binding=c.control.binding)


def test_stop_races_acceptance_under_same_owner_mutex(product):
    c=product;gid=c.approve();barrier=threading.Barrier(2)
    def stop():
        barrier.wait()
        try:return ('stop',c.stop())
        except ExecutionError as ex:return ('stop_error',ex.code)
    def submit():
        barrier.wait()
        try:return ('submit',c.submit(gid))
        except ExecutionError as ex:return ('submit_error',ex.code)
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        a=pool.submit(stop);b=pool.submit(submit);results=dict([a.result(),b.result()])
    if 'stop' in results:assert results['submit_error']=='SERVICE_STOPPING'
    else:assert results['stop_error']=='SERVICE_NOT_IDLE' and 'submit' in results
    assert c.store.gate()['state']=='PAUSED' and c.calls==[]


def test_claimed_unknown_scope_prevents_stop(product):
    c=product;rid=c.submit(c.approve());c.control.invoke(c.service,c.dispatch(rid))
    def fail(name):
        if name=='standard:after_create':raise OSError('identity persistence fault')
    c.store._checkpoint=fail
    rejected('RECONCILIATION_REQUIRED',lambda:c.service.execute_pending(c.ctx,rid))
    c.store._checkpoint=lambda n:None
    rejected('SERVICE_NOT_IDLE',c.stop)
    assert c.store.query_run(c.ctx,rid)['reconciliation']=='RECONCILIATION_REQUIRED'


def test_readonly_preparation_and_management_receipt(product):
    c=product
    from abqjobpilot.product_standard import inspect_preparation
    before=Path(c.ctx.execution_store).read_bytes()
    inspected=inspect_preparation(c.root)
    assert inspected['plan']==c.plan and inspected['counts']==dict(plans=1,grants=0,runs=0,receipts=0,consumption=0)
    assert Path(c.ctx.execution_store).read_bytes()==before and c.calls==[]
    result=c.control.invoke(c.service,c.approval)
    assert c.store.management_receipt(c.service.client_namespace,'product_standard_authorize','authorize')==result['receipt']


def test_fixed_example_check_is_readonly_and_hashes_actual_materials(product,monkeypatch,tmp_path):
    import importlib.util
    script=SOURCE/'examples/agent_first/product_standard_acceptance.py'
    spec=importlib.util.spec_from_file_location('acceptance_example',script);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    c=product
    from abqjobpilot.execution.standard_contract import identity
    body={'format':'product-standard-single-acceptance-v1','root':str(c.root),'plan':c.plan,'operation_keys':{},
          'materials':[identity(c.engineering/'axial_bar.inp')]}
    manifest=tmp_path/'manifest.json';body_hash=digest(body).split(':')[1]
    manifest.write_text(canonical_json({'body':body,'body_sha256':body_hash}))
    monkeypatch.setattr(sys,'argv',[str(script),'--manifest',str(manifest),'--body-sha256',body_hash])
    before=Path(c.ctx.execution_store).read_bytes()
    assert module.main()['abaqus_calls_this_check']==0 and Path(c.ctx.execution_store).read_bytes()==before
    (c.engineering/'axial_bar.inp').write_text('changed')
    rejected('PLAN_STALE',module.main)
