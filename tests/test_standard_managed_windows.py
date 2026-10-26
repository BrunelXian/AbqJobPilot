"""Real Windows native Job/file-handle path, existing IPC/GUI, fixed Python only."""
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

import pytest
from abqjobpilot.execution import create_experiment,ExperimentStore,ExecutionService
from abqjobpilot.execution.models import canonical_json,CONTRACT,now,ExecutionError
from abqjobpilot.execution.standard_contract import StandardConfig,management_binding
from abqjobpilot.execution.standard_sequence import prepare_pair,issue_pair
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.client import FakeClient
from supervisor_helpers import wait_until,read_json
from test_execution_gui import Gui

SOURCE=Path(__file__).resolve().parents[1]


@pytest.fixture
def pair_host(tmp_path,monkeypatch):
    root=tmp_path;ctx=create_experiment(root,root/'project')
    for name in ('a','b'):
        folder=root/name;folder.mkdir();(folder/'scratch').mkdir()
        (folder/'axial_bar.inp').write_bytes((SOURCE/'docs/agent_first/run_010/axial_bar.inp').read_bytes())
    config=StandardConfig(canonical_json({'interpreter':sys.executable,'host_policy':'independent-service-same-windows-session-v1',
        'process_management':management_binding()}))
    with monkeypatch.context() as patch:
        patch.setattr(StandardConfig,'verify',lambda self:None)
        with closing(ExperimentStore(ctx)) as store:
            service=ExecutionService(ctx,store,standard_config=config,client_namespace='r16-test')
            plans=prepare_pair(service,root/'a','r016_bar_a_1111abcd',root/'b','r016_bar_b_2222abcd',expires_at=now()+3600)
            grants=issue_pair(service,[p['plan_id'] for p in plans],approval_source='ACTUAL_PYTHON_SUBSTITUTE_NOT_ABAQUS_APPROVAL')
            bootstrap={'context':ctx.to_dict(),'authority_instance':store._session.authority_instance,'credential':secrets.token_hex(32),
                'client_namespace':'r16-test','endpoint_file':str(root/'endpoint.json')}
    def write(n,v):(root/n).write_text(canonical_json(v),encoding='utf-8')
    write('bootstrap.json',bootstrap);write('plans.json',plans);write('settings.json',{'standard_config':config._json})
    requests=[{'contract_version':CONTRACT,'operation':'submit','project_id':ctx.project_id,'project_instance_id':ctx.project_instance_id,
        'job_id':p['job_id'],'job_revision':1,'plan_id':p['plan_id'],'plan_digest':p['plan_digest'],
        'grant_id':g['grant_id'],'idempotency_key':'r16-test-'+str(i),'retry_of':None} for i,(p,g) in enumerate(zip(plans,grants))]
    children=[];refs=[];logs=[];guis=[];evidence={'scope':'FIXED_PYTHON_SUBSTITUTE_WITH_SYNTHETIC_DAT_NOT_ABAQUS','abaqus_calls':0,
        'python':sys.executable,'root':str(root)}
    def owner():
        out=(root/('owner'+str(len(children))+'.out')).open('wb');err=(root/('owner'+str(len(children))+'.err')).open('wb');logs.extend([out,err])
        child=subprocess.Popen([sys.executable,'-B',str(SOURCE/'tests/run016_process.py'),str(root)],cwd=root,
            stdin=subprocess.DEVNULL,stdout=out,stderr=err,shell=False,close_fds=True,creationflags=0x08000000,
            env={**os.environ,'TEMP':str(root),'TMP':str(root),'PYTHONDONTWRITEBYTECODE':'1'})
        children.append(child);refs.append(ProcessReference(child.pid))
        wait_until(lambda:(root/'connection.json').exists() or child.poll() is not None)
        assert child.poll() is None,(root/('owner'+str(len(children)-1)+'.err')).read_text()
        data=read_json(root/'connection.json');client=FakeClient(data['endpoint'],data['credential'])
        identity=client.health()['process'];ref=ProcessReference(identity['pid'],identity,cleanup=True);refs.append(ref)
        return child,ref,client
    try:yield root,ctx,requests,owner,refs,guis,evidence
    finally:
        for n in (0,1):
            d=root/('case_'+str(n))
            if d.exists():(d/'release-worker').touch()
        (root/'stop').touch()
        for g in guis:g.close()
        for c in children:c.wait(timeout=35)
        exits=[]
        for ref in refs:
            wait_until(lambda:ref.exit_evidence() is not None,timeout=35)
            exits.append(ref.exit_evidence());ref.close()
        for stream in logs:stream.close()
        for name in ('bootstrap.json','connection.json'):(root/name).unlink(missing_ok=True)
        assert not any((root/n).exists() for n in ('bootstrap.json','connection.json'))
        evidence['cleanup']={'retained_handle_exits':exits,'private_removed':True,'native':read_json(root/'cleanup.json')}
        if os.environ.get('RUN016_EVIDENCE_DIR'):
            (Path(os.environ['RUN016_EVIDENCE_DIR'])/(root.name+'.json')).write_text(canonical_json(evidence),encoding='utf-8')


def test_managed_standard_pair_public_gui_and_real_scope(pair_host):
    root,ctx,requests,start,refs,guis,e=pair_host
    _,owner,c=start();first=c.submit(requests[0]);a=first['receipt']['run_id']
    wait_until(lambda:(root/'case_0/worker.json').exists())
    identity=read_json(root/'case_0/worker.json');worker=ProcessReference(identity['pid'],identity);refs.append(worker)
    before=wait_until(lambda:r if (r:=c.run(a)).get('managed_scope',{}).get('active_processes',0)>0 else None)
    with pytest.raises(ExecutionError) as ex:c.submit(requests[1])
    assert ex.value.code=='PREDECESSOR_NOT_QUALIFIED' and len(read_json(root/'physical-launches.json'))==1
    gui=Gui(root,root/'connection.json','r16-test-0','gui_a');guis.append(gui)
    seen=gui.view(lambda v:v['connected'] and a in json.dumps(v['rows']) and 'STA_BYTES' in v['progress_text'])
    closed=gui.normal_close();assert worker.exit_evidence() is None and owner.exit_evidence() is None
    gui2=Gui(root,root/'connection.json','r16-test-0','gui_b');guis.append(gui2)
    reconnected=gui2.view(lambda v:v['connected'] and a in json.dumps(v['rows']))
    assert c.submit(requests[0])['receipt']==first['receipt']
    (root/'case_0/release-worker').touch()
    final_a=wait_until(lambda:r if (r:=c.run(a))['execution']=='FINISHED' else None,timeout=15)
    assert final_a['managed_completion']=='COMMITTED_EMPTY_SCOPE' and final_a['numerical_validation']=='PRIMARY_THREE_PASS'
    assert final_a['member_completeness']==final_a['overall_exit']=='UNKNOWN'
    second=c.submit(requests[1]);b=second['receipt']['run_id']
    wait_until(lambda:(root/'case_1/worker.json').exists());id_b=read_json(root/'case_1/worker.json');refs.append(ProcessReference(id_b['pid'],id_b))
    (root/'case_1/release-worker').touch()
    final_b=wait_until(lambda:r if (r:=c.run(b))['execution']=='FINISHED' else None,timeout=15)
    assert final_b['managed_completion']=='COMMITTED_EMPTY_SCOPE' and final_b['solver_conclusion']=='COMPLETED_TEXT_EVIDENCE'
    assert c.submit(requests[1])['replayed'] and len(read_json(root/'physical-launches.json'))==2
    shown=gui2.view(lambda v:dict(v['rows']).get('范围收尾')=='COMMITTED_EMPTY_SCOPE');gui2.normal_close()
    e.update(first=first,second=second,before=before,gui=seen,gui_exits=closed,reconnected=reconnected,final_gui=shown,
        final_a=final_a,final_b=final_b,events=c.events(),physical=read_json(root/'physical-launches.json'),diagnostic=c.diagnose(a),gate=c.dispatch_gate())


def test_managed_standard_owner_crash_does_not_adopt_or_start_b(pair_host):
    import ctypes
    root,ctx,requests,start,refs,guis,e=pair_host
    child,owner,c=start();rid=c.submit(requests[0])['receipt']['run_id']
    wait_until(lambda:(root/'case_0/worker.json').exists())
    identity=read_json(root/'case_0/worker.json');worker=ProcessReference(identity['pid'],identity);refs.append(worker)
    before=wait_until(lambda:r if (r:=c.run(rid)).get('execution_phase')=='OBSERVING' else None)
    owner.api.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
    assert owner.api.TerminateProcess(owner.handle,97);wait_until(lambda:owner.exit_evidence() is not None)
    child.wait(10);assert worker.exit_evidence() is None
    # Only replace the dead test owner's connection handoff, never any business data or lock.
    (root/'connection.json').unlink();_,new_owner,new=start()
    assert new.dispatch_gate()['state']=='PAUSED' and new.run(rid)['reconciliation_requirement']=='RECONCILIATION_REQUIRED'
    with pytest.raises(ExecutionError):new.submit(requests[1])
    assert worker.exit_evidence() is None and len(read_json(root/'physical-launches.json'))==1
    e.update(before=before,after=new.run(rid),worker_alive_after_owner_exit=identity,gate=new.dispatch_gate(),owner_crash_exit=owner.exit_evidence())


def test_public_pair_orchestrator_uses_existing_server(pair_host):
    import concurrent.futures
    sys.path.insert(0,str(SOURCE/'examples/agent_first'))
    from standard_client import run_pair
    root,ctx,requests,start,refs,guis,e=pair_host
    _,owner,c=start()
    (root/'offer.json').write_text(canonical_json({'requests':requests}))
    session=root/'session';session.mkdir()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(run_pair,root/'connection.json',root/'offer.json',session)
        for n in (0,1):
            wait_until(lambda:(root/('case_'+str(n))/'worker.json').exists())
            identity=read_json(root/('case_'+str(n))/'worker.json');refs.append(ProcessReference(identity['pid'],identity))
            assert len(read_json(root/'physical-launches.json'))==n+1
            (root/('case_'+str(n))/'release-worker').touch()
        result=future.result(timeout=20)
    assert result['status']=='PAIR_OBSERVED' and result['b_numerical']=='PRIMARY_THREE_PASS'
    assert run_pair(root/'connection.json',root/'offer.json',session)==result
    assert len(read_json(root/'physical-launches.json'))==2
    e.update(result=result,physical=read_json(root/'physical-launches.json'),events=c.events())
    (root/'offer.json').unlink()


def test_native_creation_deadline_checked_after_attribute_preparation(tmp_path,monkeypatch):
    from abqjobpilot.execution.managed_process import ManagedScope
    binding={k:k for k in ('project_instance_id','run_id','plan_digest','phase_attempt_id','owner_id','owner_epoch')}
    scope=ManagedScope(binding)
    def forbid(*args):raise AssertionError('Expired window must never enter CreateProcessW')
    monkeypatch.setattr(scope.api,'CreateProcessW',forbid)
    try:
        with (tmp_path/'out').open('xb') as out,(tmp_path/'err').open('xb') as err:
            with pytest.raises(ExecutionError) as exc:
                scope.create_standard({'application':sys.executable,'command_line':'unused-fixed-test',
                    'cwd':str(tmp_path),'environment':{},'start_not_after':now()-1},out,err)
            assert exc.value.code=='START_WINDOW_EXPIRED'
        assert not scope.started and scope.query()['total_processes']==0
    finally:scope.close()
