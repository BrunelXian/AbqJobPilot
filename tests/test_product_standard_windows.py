"""Actual Windows product owner / GUI / managed Python substitute, never Abaqus."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from abqjobpilot.product_project import create_project
from abqjobpilot.product_standard import prepare_product, StandardOperator
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution.models import canonical_json, now, CONTRACT, ExecutionError
from abqjobpilot.execution.standard_contract import StandardConfig, management_binding
from abqjobpilot.execution.process_handles import ProcessReference
from supervisor_helpers import wait_until, read_json
from test_execution_gui import Gui
from test_attachment_gui import action
from test_product_windows import attach, independent, retain_owner_chain
from test_service_lifecycle import telemetry

SOURCE=Path(__file__).resolve().parents[1]


@pytest.fixture
def product_host(tmp_path,monkeypatch):
    monkeypatch.setattr(StandardConfig,'verify',lambda s:None)
    original=subprocess.Popen
    def fixed(args,*a,**kw):
        args=list(args)
        for before,after in [('abqjobpilot/service_owner.py','tests/run021b_service_owner.py'),
                             ('tests/run020_gui.py','tests/run021b_gui.py')]:
            expected=str(SOURCE/before)
            if expected in args:args[args.index(expected)]=str(SOURCE/after)
        assert all('abq2024' not in str(x).lower() for x in args)
        return original(args,*a,**kw)
    monkeypatch.setattr(subprocess,'Popen',fixed)
    root=tmp_path/'product';create_project(root,'Run021B product native substitute')
    engineering=root/'engineering';engineering.mkdir();(engineering/'scratch').mkdir()
    (engineering/'axial_bar.inp').write_bytes((SOURCE/'docs/agent_first/run_010/axial_bar.inp').read_bytes())
    config=StandardConfig(canonical_json({'interpreter':sys.executable,'process_management':management_binding(),
        'host_policy':'independent-service-same-windows-session-v1','fixture_only':True}))
    plan=prepare_product(root,engineering,'r021_bar_1122abcd',config,expires_at=now()+3600)
    (root/'test-plan.json').write_text(canonical_json(plan))
    manager=ServiceLifecycleManager(root);operator=StandardOperator(root);refs=[];guis=[]
    evidence={'scope':'PRODUCT_STANDARD_NATIVE_PYTHON_SUBSTITUTE_SYNTHETIC_DAT_ONLY','abaqus_calls':0,
              'root':str(root),'python':sys.executable}
    try:yield root,plan,manager,operator,refs,guis,evidence
    finally:
        fixture=root/'fixture'
        if fixture.exists():(fixture/'release-worker').touch()
        for gui in guis:
            if gui.actual and gui.actual.handle and gui.actual.exit_evidence() is None:gui.normal_close()
            gui.close()
        status=manager.inspect()['state']
        if status=='CONNECTED':
            c,_,h=manager.connect()
            def stop():
                try:return manager.stop(owner_id=c.endpoint['owner_id'],operation_key='cleanup')
                except ExecutionError:return None
            wait_until(stop,timeout=35)
        elif status=='BLOCKED':
            # Keep credentials for diagnosis if the host prevents IPC. Never
            # report cleanup just because no handles were retained yet.
            owner_file=Path(manager.context.root)/'owner.json'
            if owner_file.exists():
                identity=read_json(owner_file)['process']
                try:check=ProcessReference(identity['pid'],identity)
                except ExecutionError:check=None
                if check:
                    try:assert check.exit_evidence() is not None,'Unreachable owned test process; preserve credentials'
                    finally:check.close()
        for ref in refs:wait_until(lambda:ref.exit_evidence(),timeout=35)
        evidence['cleanup']={'process_exits':[r.exit_evidence() for r in refs]}
        for ref in refs:ref.close()
        evidence['cleanup']['handles_closed']=len(refs)
        evidence['cleanup']['native']=[read_json(p) for p in fixture.glob('cleanup_start_*.json')]
        assert all(h['scope_closed'] and h['root_closed'] for row in evidence['cleanup']['native'] for h in row['handles'])
        for name in ('lifecycle.json','operator.json','standard-profile.json','standard-operator.json','connection.json','offer.json'):
            (root/'private'/name).unlink(missing_ok=True)
        evidence['cleanup']['private_removed']=True
        target=os.environ.get('RUN021B_EVIDENCE_DIR')
        if target:(Path(target)/(tmp_path.name+'.json')).write_text(canonical_json(evidence),encoding='utf-8')


def approve_submit(root,plan,m,op):
    c,ctx,_=m.connect()
    approval=op.request('authorize',{'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],
        'expires_at':now()+500,'subject':'Windows controlled harness','source':'FIXED_PYTHON_SUBSTITUTION_ONLY'},operation_key='approval')
    req={'contract_version':CONTRACT,'operation':'submit','project_id':ctx.project_id,'project_instance_id':ctx.project_instance_id,
        'job_id':plan['job_id'],'job_revision':1,'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],
        'grant_id':approval['receipt']['grant_id'],'idempotency_key':'product-single','retry_of':None}
    offer=root/'private/offer.json';offer.write_text(canonical_json(req))
    result=independent(root.parent,root,offer=offer)
    return c,result['submission']['receipt']['run_id'],result,req,approval


def arm(c,rid,op,key='dispatch'):
    args={'run_id':rid,'revision':c.run(rid)['revision'],'gate_version':c.dispatch_gate()['version'],'start_not_after':now()+25}
    return args,op.request('dispatch_once',args,operation_key=key)


def test_product_standard_gui_full_chain_and_safe_restart(product_host):
    root,p,m,op,refs,guis,e=product_host
    gui=Gui(root.parent,None,None,'gui_a',attachment=True,product=True);guis.append(gui)
    action(gui,'project',project=str(root))
    wait_until(lambda:'NOT_RUNNING' in telemetry(gui.root/'lifecycle.json').get('status',''))
    action(gui,'start');wait_until(lambda:m.inspect()['state']=='CONNECTED')
    c,ctx,h=m.connect();owner=retain_owner_chain(m,h,refs)
    assert m.start()['created'] is False and c.dispatch_gate()['state']=='PAUSED'
    c,rid,submitted,request,approval=approve_submit(root,p,m,op)
    assert c.run(rid)['execution']=='PLANNED' and not (root/'fixture/physical.jsonl').exists()
    args,dispatch=arm(c,rid,op)
    wait_until(lambda:(root/'fixture/worker.json').exists())
    identity=read_json(root/'fixture/worker.json');worker=ProcessReference(identity['pid'],identity);refs.append(worker)
    seen=attach(gui,root,rid);gui.view(lambda v:'STA_BYTES' in v['progress_text'])
    with pytest.raises(ExecutionError) as error:m.stop(owner_id=c.endpoint['owner_id'],operation_key='active')
    assert error.value.code=='SERVICE_NOT_IDLE'
    exited=gui.normal_close();assert owner.exit_evidence() is None and worker.exit_evidence() is None
    sta=Path(p['engineering'])/(p['job_name']+'.sta');size=sta.stat().st_size
    wait_until(lambda:sta.stat().st_size>size)
    alive={'owner':owner.identity,'worker':worker.identity,'sta_before':size,'sta_after':sta.stat().st_size}
    again=Gui(root.parent,None,None,'gui_b',attachment=True,product=True);guis.append(again)
    reconnected=attach(again,root,rid)
    assert c.submit(request)['receipt']==submitted['submission']['receipt']
    assert op.request('dispatch_once',args,operation_key='dispatch')['receipt']==dispatch['receipt']
    (root/'fixture/release-worker').touch()
    final=wait_until(lambda:r if (r:=c.run(rid))['execution']=='FINISHED' else None,timeout=20)
    assert final['managed_completion']=='COMMITTED_EMPTY_SCOPE' and final['numerical_validation']=='PRIMARY_THREE_PASS'
    assert final['solver_conclusion']=='COMPLETED_TEXT_EVIDENCE' and final['overall_exit']=='UNKNOWN'
    shown=again.view(lambda v:dict(v['rows']).get('Managed process scope')=='COMMITTED_EMPTY_SCOPE')
    assert c.dispatch_gate()['state']=='PAUSED'
    physical=(root/'fixture/physical.jsonl').read_text().splitlines();assert len(physical)==1
    again.normal_close();stop=m.stop(owner_id=c.endpoint['owner_id'],operation_key='normal-stop')
    wait_until(lambda:owner.exit_evidence());wait_until(lambda:m.inspect()['state']=='NOT_RUNNING')
    old_owner=c.endpoint['owner_id'];m.start();c2,_,h2=m.connect();retain_owner_chain(m,h2,refs)
    assert c2.endpoint['owner_id']!=old_owner and c2.dispatch_gate()['state']=='PAUSED'
    assert c2.submit(request)['receipt']==submitted['submission']['receipt']
    assert op.request('dispatch_once',args,operation_key='dispatch',owner_id=old_owner)['receipt']==dispatch['receipt']
    assert c2.run(rid)['revision']==final['revision'] and len((root/'fixture/physical.jsonl').read_text().splitlines())==1
    with pytest.raises(ExecutionError):op.request('dispatch_once',args,operation_key='another',owner_id=old_owner)
    e.update(owner=h['process'],approval=approval,submission=submitted,dispatch=dispatch,gui=seen,gui_exit=exited,
        after_gui_exit=alive,reconnected=reconnected,final=final,shown=shown,physical=[json.loads(x) for x in physical],
        stop=stop,restart=h2['process'],gate=c2.dispatch_gate(),events=c2.events(),diagnostic=c2.diagnose(rid))
    secrets=[m._profile()['credential'],m._operator()]
    from abqjobpilot.local_credentials import read_private
    secrets.append(read_private(m.context,m._path('standard-operator.json'))['operator_token'])
    assert all(s not in canonical_json(e) for s in secrets)


def test_dispatch_response_loss_replay_no_second_start(product_host):
    root,p,m,op,refs,guis,e=product_host;m.start();c,_,h=m.connect();retain_owner_chain(m,h,refs)
    c,rid,submitted,request,approval=approve_submit(root,p,m,op)
    args={'run_id':rid,'revision':c.run(rid)['revision'],'gate_version':c.dispatch_gate()['version'],'start_not_after':now()+25}
    (root/'fixture/drop-response').touch()
    with pytest.raises(ExecutionError) as error:op.request('dispatch_once',args,operation_key='lost')
    assert error.value.code=='ACCEPTANCE_UNKNOWN'
    replay=op.request('dispatch_once',args,operation_key='lost');assert replay['replayed']
    assert c.management_receipt('product_standard_dispatch_once','lost')==replay['receipt']
    wait_until(lambda:(root/'fixture/worker.json').exists());identity=read_json(root/'fixture/worker.json')
    refs.append(ProcessReference(identity['pid'],identity));(root/'fixture/release-worker').touch()
    final=wait_until(lambda:r if (r:=c.run(rid))['execution']=='FINISHED' else None,timeout=20)
    assert len((root/'fixture/physical.jsonl').read_text().splitlines())==1
    e.update(replay=replay,final=final,gate=c.dispatch_gate())


@pytest.mark.parametrize('point',['dispatch:after_claim','standard:after_create'])
def test_owner_hard_exit_does_not_rearm_or_auto_restart(product_host,point):
    root,p,m,op,refs,guis,e=product_host;m.start();c,ctx,h=m.connect();owner=retain_owner_chain(m,h,refs)
    c,rid,submitted,request,approval=approve_submit(root,p,m,op)
    (root/'fixture/crash-at').write_text(point)
    arm(c,rid,op)
    wait_until(lambda:owner.exit_evidence())
    assert owner.exit_evidence()['exit_code']==97 and (root/'fixture/crash-reached').read_text()==point
    physical=root/'fixture/physical.jsonl'
    if point=='standard:after_create':
        wait_until(lambda:(root/'fixture/worker.json').exists())
        identity=read_json(root/'fixture/worker.json');worker=ProcessReference(identity['pid'],identity);refs.append(worker)
        assert worker.exit_evidence() is None
        e['worker_survived_owner']=identity
        assert len(physical.read_text().splitlines())==1
    else:assert not physical.exists()
    assert m.inspect()['state']=='BLOCKED'
    with pytest.raises(ExecutionError) as error:m.start()
    assert error.value.code=='START_BLOCKED'
    from abqjobpilot.execution.store import open_existing_read_only
    r=open_existing_read_only(ctx).query_run(ctx,rid)
    assert r['single_dispatch']['state']=='CLAIMED' and r['execution']!='FINISHED'
    assert open_existing_read_only(ctx).gate()['state']=='PAUSED'
    assert len(list(m.private.glob('start_*/created.json')))==1
    e.update(crash_point=point,owner_exit=owner.exit_evidence(),stored_run=r,
             status=m.inspect(),physical_launch_count=1 if physical.exists() else 0)
