"""Real Windows product creation + GUI/client/owner lifecycle, fixed Python only."""
from contextlib import contextmanager
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from abqjobpilot.product_project import create_project,open_project
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution.models import ExecutionError,canonical_json,now
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.local_credentials import private_value
from supervisor_helpers import wait_until,read_json
from test_execution_gui import Gui
from test_attachment_gui import action
from test_service_lifecycle import telemetry

SOURCE=Path(__file__).resolve().parents[1]


def retain_owner_chain(manager, health, refs):
    """Bind actual owner and its venv transport while both are alive."""
    identity=health['process'];ref=ProcessReference(identity['pid'],identity);refs.append(ref)
    created=read_json(manager._path(manager._current()['start_id']+'/created.json'))
    if created['transport_pid']!=identity['pid']:
        assert created['transport_pid']==identity['parent_pid']
        transport=ProcessReference(created['transport_pid'])
        assert transport.identity['creation_time_100ns']<=identity['creation_time_100ns']
        assert Path(transport.identity['image_path']).name.lower()=='python.exe'
        refs.append(transport)
    return ref


def save(root,name,value):
    (root/(name+'.json')).write_text(canonical_json(value),encoding='utf-8')
    target=os.environ.get('RUN020_EVIDENCE_DIR')
    if target:(Path(target)/(name+'.json')).write_text(canonical_json(value),encoding='utf-8')


@contextmanager
def own_project(root):
    """Exact new test path only; no PID kill, release our fixture barrier then idle stop."""
    refs=[]
    try:yield refs
    finally:
        m=ServiceLifecycleManager(root)
        for release in Path(m.context.runtime_root).glob('process_runs/*/fixture.json'):
            (release.parent/'release.json').write_text('{}')
        if m.inspect()['state']=='CONNECTED':
            client,ctx,health=m.connect();ref=retain_owner_chain(m,health,refs)
            deadline=time.monotonic()+65
            while True:
                try:m.stop(owner_id=client.endpoint['owner_id'],operation_key='test-cleanup');break
                except ExecutionError:
                    if time.monotonic()>=deadline:raise
                    time.sleep(.05)
        for ref in refs:wait_until(lambda:ref.exit_evidence(),timeout=12)
        cleanup={'process_exits':[r.exit_evidence() for r in refs],'handles_closed':len(refs),'private_files_removed':[],'abaqus_calls':0}
        for ref in refs:ref.close()
        for name in ('lifecycle.json','operator.json','connection.json','offer.json'):
            p=m.private/name
            if p.exists():p.unlink();cleanup['private_files_removed'].append(name)
        (root/'test_cleanup.json').write_text(canonical_json(cleanup))


def independent(root,project,*,start=False,offer=None,label='client'):
    out=root/(label+'.json');err=root/(label+'.stderr')
    command=[sys.executable,'-B',str(SOURCE/'tests/run020_client.py'),'--project',str(project),'--out',str(out)]
    if start:command+=['--start']
    if offer:command+=['--offer',str(offer)]
    with err.open('wb') as log:
        child=subprocess.Popen(command,cwd=root,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=log,
            shell=False,close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW,
            env={**os.environ,'TEMP':str(root),'TMP':str(root),'PYTHONDONTWRITEBYTECODE':'1'})
        ref=ProcessReference(child.pid)
        try:
            assert child.wait(timeout=15)==0,err.read_text()
            result=read_json(out);result['client_exit']=ref.exit_evidence();assert 'error' not in result
            return result
        finally:ref.close()


def attach(gui,project,rid=None):
    ack=action(gui,'project',project=str(project))
    gui.view(lambda v:v['connected'] and v['selection_generation']==ack['selection_generation']
             and (not rid or rid in json.dumps(v['run_list'])))
    if rid:action(gui,'select',run_id=rid)
    return gui.view(lambda v:v['connected'] and (not rid or dict(v['rows']).get('Run ID')==rid))


def trusted_fixture_during_initial_lease(root,monkeypatch):
    """Separate trusted harness runs in creating owner's lease, before publication.

    Normal creation is asserted PAUSED/empty first. Uses existing test issuer +
    resume transaction; no SQL fabrication or management bypass after startup.
    This hook is NOT a product option, GUI operation or ordinary client ability.
    """
    import abqjobpilot.service_lifecycle as lifecycle
    from abqjobpilot.execution import ExecutionService,JobSpec,ConfigSnapshot
    from abqjobpilot.execution.models import RESOURCES,CONTRACT
    from abqjobpilot.execution.process_backend import ProcessFixtureConfig
    from abqjobpilot.execution.test_authority import issue_process_execution
    from reconciliation_helpers import FakeManagementFixture,management_request
    from abqjobpilot.execution.reconciliation import RESUME
    original=lifecycle.configure_lifecycle
    def provision(service,**kw):
        store=service.store;ctx=service.context
        assert store.gate()['state']=='PAUSED'
        with store.read() as c:
            assert c.execute('SELECT COUNT(*) FROM grants').fetchone()[0]==0
            assert c.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==0
        config=ProcessFixtureConfig.current(managed_scope=True)
        config=type(config)(**{**asdict(config),'max_seconds':60})
        service=ExecutionService(ctx,store,client_namespace='product-client',process_config=config)
        result=original(service,process_config=config)
        source=root/'fixture-input.txt';source.write_text('Explicit trusted fixed test input')
        spec=JobSpec.from_dict({'job_id':'product_fixture','revision':1,'project_id':ctx.project_id,
            'project_instance_id':ctx.project_instance_id,'input_refs':[str(source)],'resources':dict(RESOURCES),
            'metadata':{'label':'TEST_ONLY trusted harness'}})
        plan=service.prepare(ctx,spec,ConfigSnapshot.from_dict({'config_revision':1,'values':{'label':'test'}}),
                             expires_at=now()+600,process_scenario='result_wait').to_dict()
        grant=issue_process_execution(service,plan['plan_id'],expires_at=now()+600)
        scope={'expected_gate_version':store.gate()['version']}
        permission=FakeManagementFixture(store).issue(RESUME,scope)
        resumed=service.resume_dispatch(ctx,management_request(ctx,store._session.owner_id,RESUME,scope,permission,'explicit-test-resume'))
        request={'contract_version':CONTRACT,'operation':'submit','project_id':ctx.project_id,
            'project_instance_id':ctx.project_instance_id,'job_id':plan['job_id'],'job_revision':plan['job_revision'],
            'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],'grant_id':grant,'idempotency_key':'product-one','retry_of':None}
        (root/'private/offer.json').write_text(canonical_json(request))
        (root/'trusted_setup.json').write_text(canonical_json({'initial_empty_paused':True,'resume_receipt':resumed['receipt'],
            'scope':'fixed Python TEST_ONLY','service_started':False,'run_submitted':False}))
        return result
    with monkeypatch.context() as patch:
        patch.setattr(lifecycle,'configure_lifecycle',provision)
        create_project(root,'Trusted test Project')
    return root/'private/offer.json'


def test_gui_new_empty_product_start_reopen_independent_client_stop(tmp_path):
    project=tmp_path/'created_by_gui';guis=[]
    first=Gui(tmp_path,None,None,'gui_A',attachment=True,product=True);guis.append(first)
    try:
        action(first,'new',project=str(project),name='Run020 GUI Project')
        wait_until(lambda:(project/'agent_project.json').exists())
        with own_project(project) as refs:
            from test_product_project import facts,inventory
            manifest=open_project(project);empty=facts(project)
            assert all(v==0 for v in empty['counts'].values()) and empty['gate']['state']=='PAUSED'
            m=ServiceLifecycleManager(project);assert m.inspect()['state']=='NOT_RUNNING'
            wait_until(lambda:'NOT_RUNNING' in telemetry(first.root/'lifecycle.json').get('status',''))
            displayed=telemetry(first.root/'lifecycle.json')['project_identity']
            assert manifest['project_id'] in displayed and manifest['project_instance_id'] in displayed
            action(first,'start');wait_until(lambda:m.inspect()['state']=='CONNECTED')
            shown=first.view(lambda v:v['connected']);client,ctx,health=m.connect()
            owner=health['process'];ref=retain_owner_chain(m,health,refs)
            assert client.project_view()['runs']==[] and client.dispatch_gate()['state']=='PAUSED'
            public=independent(tmp_path,project,start=True)
            assert public['owner']==owner and public['start']['created'] is False
            closed=first.normal_close();assert ref.exit_evidence() is None
            second=Gui(tmp_path,None,None,'gui_B',attachment=True,product=True);guis.append(second)
            reopened=attach(second,project);assert m.connect()[2]['process']==owner
            assert open_project(project)==manifest and facts(project)['counts']==empty['counts']
            before=inventory(project)
            action(second,'new',project=str(project),name='Cannot overwrite')
            wait_until(lambda:'PROJECT_EXISTS' in telemetry(second.root/'lifecycle.json').get('status',''))
            assert inventory(project)==before
            action(second,'stop');wait_until(lambda:ref.exit_evidence())
            wait_until(lambda:m.inspect()['state']=='NOT_RUNNING')
            action(second,'start');wait_until(lambda:m.inspect()['state']=='CONNECTED')
            c,_,h=m.connect();refs.append(ProcessReference(h['process']['pid'],h['process']))
            assert h['process']!=owner and c.dispatch_gate()['state']=='PAUSED' and c.project_view()['runs']==[]
            save(tmp_path,'empty_gui_product',{'project':manifest,'initial':empty,'identity_before_start':displayed,'shown':shown,'reopened':reopened,
                'owner':owner,'gui':first.identity,'gui_exit':closed,'public_client':public,'owner_exit':ref.exit_evidence(),
                'restart_owner':h['process'],'gate':c.dispatch_gate(),'abaqus_calls':0})
            second.normal_close()
    finally:
        for gui in guis:gui.close()


def test_fixed_worker_product_gui_chain_and_secret_free_reports(tmp_path,monkeypatch):
    project=tmp_path/'test_product';offer=trusted_fixture_during_initial_lease(project,monkeypatch);guis=[]
    with own_project(project) as refs:
        try:
            first=Gui(tmp_path,None,None,'gui_A',attachment=True,product=True);guis.append(first)
            action(first,'project',project=str(project))
            wait_until(lambda:'NOT_RUNNING' in telemetry(first.root/'lifecycle.json').get('status',''))
            action(first,'start');m=ServiceLifecycleManager(project);wait_until(lambda:m.inspect()['state']=='CONNECTED')
            client,ctx,health=m.connect();owner=health['process'];owner_ref=retain_owner_chain(m,health,refs)
            submitted=independent(tmp_path,project,offer=offer);rid=submitted['submission']['receipt']['run_id']
            run=wait_until(lambda:r if len((r:=client.run(rid))['process_records'])==4 else None)
            worker=next(p for p in run['process_records'] if p['role']=='worker')
            worker_ref=ProcessReference(worker['pid'],worker);refs.append(worker_ref)
            attach(first,project,rid);first.view(lambda v:'WAITING' in v['progress_text'])
            with pytest.raises(ExecutionError) as e:m.stop(owner_id=client.endpoint['owner_id'],operation_key='active-refused')
            assert e.value.code=='SERVICE_NOT_IDLE'
            gate=client.dispatch_gate();before=client.run(rid);closed=first.normal_close()
            assert owner_ref.exit_evidence() is None and worker_ref.exit_evidence() is None
            cursor=client.progress(rid)['next_sequence'];wait_until(lambda:client.progress(rid)['next_sequence']>cursor)
            after_close={'owner_alive':owner_ref.exit_evidence() is None,'worker_alive':worker_ref.exit_evidence() is None,
                'cursor_before':cursor,'cursor_after':client.progress(rid)['next_sequence'],'observed_at':now()}
            second=Gui(tmp_path,None,None,'gui_B',attachment=True,product=True);guis.append(second)
            reopened=attach(second,project,rid)
            assert client.run(rid)==before and client.dispatch_gate()==gate
            replay=independent(tmp_path,project,offer=offer,label='replay')
            assert replay['submission']['replayed'] and replay['submission']['receipt']==submitted['submission']['receipt']
            (Path(ctx.runtime_root)/'process_runs'/rid/'release.json').write_text('{}')
            finished=wait_until(lambda:r if (r:=client.run(rid))['execution']=='FINISHED' else None,timeout=30)
            assert finished['managed_completion']=='COMMITTED_EMPTY_SCOPE' and finished['artifact_validation']=='VALID'
            assert finished['solver_conclusion']=='NOT_RUN'
            second.view(lambda v:dict(v['rows']).get('Artifact 独立验证')=='VALID')
            assert len([x for x in client.events() if x['type']=='START_INTENT'])==1
            report=client.diagnose(rid)
            # This is an audit projection of the same previously read report.
            export_root=tmp_path/'exports';export_root.mkdir()
            client.export_diagnostic(report,export_root=export_root,target=export_root/'run.json')
            secret=m._profile()['credential'];operator=m._operator()
            for p in list(first.root.glob('*.json'))+list(second.root.glob('*.json'))+list(export_root.glob('*')):
                text=p.read_text(encoding='utf-8');assert secret not in text and operator not in text
            save(tmp_path,'fixed_worker_product',{'owner':owner,'worker':worker,'submission':submitted,
                'gui':first.identity,'gui_exit':closed,'after_gui_exit':after_close,'reopened':reopened,
                'finished':finished,'replay':replay,'gate':gate,'abaqus_calls':0})
            target=os.environ.get('RUN020_EVIDENCE_DIR')
            if target and (first.root/'window.png').exists():shutil.copyfile(first.root/'window.png',Path(target)/'product_gui.png')
            second.normal_close()
        finally:
            for gui in guis:gui.close()


def test_product_credentials_wrong_context_copies_and_connection_permission(tmp_path):
    project=tmp_path/'one';create_project(project,'One')
    other=tmp_path/'two';create_project(other,'Two')
    with own_project(project),own_project(other):
        m=ServiceLifecycleManager(project);m.start();client,ctx,health=m.connect()
        assert ServiceLifecycleManager(other).inspect()['state']=='NOT_RUNNING'
        shutil.copytree(project,tmp_path/'copied')
        with pytest.raises(ExecutionError):ServiceLifecycleManager(tmp_path/'copied').connect()
        path=m.private/'connection.json';original=path.read_bytes()
        value={'endpoint':client.endpoint,'credential':'invalid-credential'}
        path.write_text(canonical_json(private_value(ctx,value)))
        try:
            with pytest.raises(ExecutionError) as e:m.connect()
            assert e.value.code=='AUTHENTICATION_FAILED'
            with pytest.raises(ExecutionError):m.start()
        finally:path.write_bytes(original)
        with pytest.raises(ExecutionError) as e:client.stop_service(client.endpoint['owner_id'],'denied',client._credential)
        assert e.value.code=='LIFECYCLE_PERMISSION_REQUIRED'
        shutil.copyfile(path,other/'private/connection.json')
        with pytest.raises(ExecutionError) as e:ServiceLifecycleManager(other).connect()
        assert e.value.code=='LOCAL_CREDENTIAL_UNAVAILABLE'
        (other/'private/connection.json').unlink()  # Only the injected wrong file in our new test Project.
        assert len(list(m.private.glob('start_*/created.json')))==1


@pytest.mark.parametrize('damage',['old_endpoint','wrong_project','protocol','plaintext'])
def test_encrypted_handoff_fail_closed_no_second_owner(tmp_path,damage):
    project=tmp_path/'product';create_project(project,'Project')
    with own_project(project):
        m=ServiceLifecycleManager(project);m.start();client,ctx,health=m.connect()
        path=m.private/'connection.json';original=path.read_bytes()
        value={'endpoint':dict(client.endpoint),'credential':client._credential}
        if damage=='old_endpoint':value['endpoint']['owner_id']='obsolete'
        if damage=='wrong_project':value['endpoint']['project_id']='wrong'
        if damage=='protocol':value['endpoint']['protocol']='future'
        path.write_text(canonical_json(value if damage=='plaintext' else private_value(ctx,value)))
        try:
            assert m.inspect()['state']=='BLOCKED'
            with pytest.raises(ExecutionError):m.start()
            assert len(list(m.private.glob('start_*/created.json')))==1
        finally:path.write_bytes(original)


def test_two_product_gui_switch_and_pause_remain_isolated(tmp_path):
    one=tmp_path/'one';two=tmp_path/'two'
    create_project(one,'One');create_project(two,'Two');gui=None
    with own_project(one),own_project(two):
        m1=ServiceLifecycleManager(one);m2=ServiceLifecycleManager(two);m1.start();m2.start()
        from test_product_project import facts
        before=[facts(one),facts(two)]
        try:
            gui=Gui(tmp_path,None,None,'gui',attachment=True,product=True)
            a=attach(gui,one);b=attach(gui,two)
            assert dict(a['rows'])['Owner']!=dict(b['rows'])['Owner']
            assert dict(a['rows'])['Owner'] not in json.dumps(b)
            assert a['run_list']==b['run_list']==[]
            assert 'PAUSED' in a['status'] and 'PAUSED' in b['status']
            assert before==[facts(one),facts(two)]
            gui.normal_close()
        finally:
            if gui:gui.close()


def test_public_readonly_example_in_non_repository_cwd(tmp_path):
    project=tmp_path/'product';create_project(project,'Public API')
    with own_project(project):
        m=ServiceLifecycleManager(project);m.start()
        from test_product_project import facts
        before=facts(project)
        script=SOURCE/'examples/agent_first/product_inspect.py'
        command=[sys.executable,'-B',str(script),'--project',str(project)]
        with (tmp_path/'example.stdout').open('wb') as out,(tmp_path/'example.stderr').open('wb') as err:
            child=subprocess.Popen(command,cwd=tmp_path,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                shell=False,close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW,
                env={**os.environ,'TEMP':str(tmp_path),'TMP':str(tmp_path),'PYTHONDONTWRITEBYTECODE':'1'})
            ref=ProcessReference(child.pid)
            try:
                assert child.wait(timeout=12)==0
                exit=ref.exit_evidence()
            finally:ref.close()
        result=read_json(tmp_path/'example.stdout')
        assert result['service']['state']=='CONNECTED' and result['runs']['runs']==[]
        assert facts(project)==before and m._profile()['credential'] not in (tmp_path/'example.stdout').read_text()
        save(tmp_path,'public_example',{'command':command,'cwd':str(tmp_path),'result':result,'exit':exit,'abaqus_calls':0})
