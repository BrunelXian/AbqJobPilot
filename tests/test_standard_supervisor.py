"""Windows IPC + actual existing GUI, with a fixed Python substitute only."""
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

from abqjobpilot.execution import create_experiment,ExperimentStore,ExecutionService
from abqjobpilot.execution.models import canonical_json,CONTRACT,now
from abqjobpilot.execution.standard_contract import StandardConfig,prepare,issue_execution
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.client import FakeClient
from supervisor_helpers import wait_until,read_json
from test_execution_gui import Gui

SOURCE=Path(__file__).resolve().parents[1]


def test_windows_public_standard_path_gui_reconnect_substitute(tmp_path,monkeypatch):
    root=tmp_path
    engineering=root/'engineering';engineering.mkdir();(engineering/'scratch').mkdir()
    (engineering/'axial_bar.inp').write_bytes((SOURCE/'docs/agent_first/run_010/axial_bar.inp').read_bytes())
    ctx=create_experiment(root,root/'project')
    config=StandardConfig(canonical_json({'interpreter':sys.executable,'host_policy':'independent-service-same-windows-session-v1'}))
    with monkeypatch.context() as patch:
        patch.setattr(StandardConfig,'verify',lambda self:None)
        with closing(ExperimentStore(ctx)) as store:
            service=ExecutionService(ctx,store,client_namespace='r13-ipc',standard_config=config)
            plan=prepare(service,engineering,'r013_bar_1023abcd',expires_at=now()+3600).to_dict()
            grant=issue_execution(service,plan['plan_id'],expires_at=now()+1800,approval_source='TEST_SUBSTITUTE_NOT_REAL_APPROVAL')
            bootstrap={'context':ctx.to_dict(),'authority_instance':store._session.authority_instance,'credential':secrets.token_hex(32),
                'client_namespace':'r13-ipc','endpoint_file':str(root/'endpoint.json')}
    (root/'bootstrap.json').write_text(canonical_json(bootstrap));(root/'plan.json').write_text(canonical_json(plan))
    request={'contract_version':CONTRACT,'operation':'submit','project_id':ctx.project_id,'project_instance_id':ctx.project_instance_id,
        'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],'job_id':plan['job_id'],'job_revision':1,
        'grant_id':grant['grant_id'],'idempotency_key':'r13-public','retry_of':None}
    (root/'offer.json').write_text(canonical_json(request));(root/'session').mkdir()
    logs=[];refs=[];guis=[];processes=[];evidence={'scope':'CONTROLLED_PYTHON_SUBSTITUTE_NOT_ABAQUS','abaqus_calls':0,'os':sys.platform,'python':sys.executable}
    def spawn(script,args,label):
        out=(root/(label+'.out')).open('wb');err=(root/(label+'.err')).open('wb');logs.extend([out,err])
        child=subprocess.Popen([sys.executable,'-B',str(script),*args],cwd=root,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
            shell=False,close_fds=True,creationflags=0x08000000,
            env={**os.environ,'TEMP':str(root),'TMP':str(root),'PYTHONDONTWRITEBYTECODE':'1'})
        processes.append(child);ref=ProcessReference(child.pid);refs.append(ref);return child
    owner=None
    try:
        owner=spawn(SOURCE/'tests/run013_process.py',['owner',str(root)],'owner')
        wait_until(lambda:(root/'connection.json').exists() or owner.poll() is not None)
        assert (root/'connection.json').exists(),(root/'owner.err').read_text()
        connection=read_json(root/'connection.json');client=FakeClient(connection['endpoint'],connection['credential'])
        actual_owner=ProcessReference(client.health()['process']['pid'],client.health()['process']);refs.append(actual_owner)
        ordinary=spawn(SOURCE/'examples/agent_first/standard_client.py',
            ['--connection',str(root/'connection.json'),'--offer',str(root/'offer.json'),'--session',str(root/'session')],'client')
        assert ordinary.wait(15)==0,(root/'client.out').read_text()+(root/'client.err').read_text()
        accepted=read_json(root/'session/receipt.json');rid=accepted['receipt']['run_id']
        wait_until(lambda:(root/'worker.json').exists())
        worker=read_json(root/'worker.json');wr=ProcessReference(worker['pid'],worker);refs.append(wr)
        wait_until(lambda:len(client.run(rid)['process_records'])>=2)
        before=time.monotonic();state=client.run(rid);assert time.monotonic()-before<2
        assert wr.exit_evidence() is None and state['member_completeness']=='UNKNOWN'
        gui=Gui(root,root/'connection.json','r13-public','gui1');guis.append(gui)
        shown=gui.view(lambda v:v['connected'] and rid in json.dumps(v['rows']) and 'STA_BYTES' in v['progress_text'])
        exits1=gui.normal_close()
        length=(engineering/(plan['job_name']+'.sta')).stat().st_size
        wait_until(lambda:(engineering/(plan['job_name']+'.sta')).stat().st_size>length)
        assert wr.exit_evidence() is None and actual_owner.exit_evidence() is None
        gui2=Gui(root,root/'connection.json','r13-public','gui2');guis.append(gui2)
        reconnect=gui2.view(lambda v:v['connected'] and rid in json.dumps(v['rows']))
        assert client.submit(request)['receipt']==accepted['receipt']
        assert len(read_json(root/'physical-launches.json'))==1
        (root/'release-worker').touch()
        wait_until(lambda:wr.exit_evidence() is not None,timeout=10)
        wait_until(lambda:client.run(rid).get('all_observed_exited'),timeout=10)
        (root/'finish-observation').touch()
        final=wait_until(lambda:(r if (r:=client.run(rid))['reconciliation']=='RECONCILIATION_REQUIRED' else None))
        end=gui2.view(lambda v:v['connected'] and dict(v['rows']).get('DAT 数值验证')=='PRIMARY_THREE_PASS')
        assert final['solver_conclusion']=='COMPLETED_TEXT_EVIDENCE' and final['exit_verification']=='UNKNOWN'
        assert final['member_completeness']==final['overall_exit']=='UNKNOWN'
        assert final['odb_content_validation']=='NOT_RUN' and client.dispatch_gate()['state']=='PAUSED'
        assert len(read_json(root/'physical-launches.json'))==1
        report=client.diagnose(rid);client.export_diagnostic(report,export_root=root/'session',target=root/'session/diagnostic.json')
        exits2=gui2.normal_close()
        evidence.update(receipt=accepted,owner=client.health()['process'],worker=worker,worker_exit=wr.exit_evidence(),
            gui1=shown,gui1_exits=exits1,gui2=reconnect,gui2_final=end,gui2_exits=exits2,
            public_final=final,physical_launches=read_json(root/'physical-launches.json'),diagnostic=report)
    finally:
        (root/'release-worker').touch();(root/'finish-observation').touch();(root/'stop').touch()
        for gui in guis:gui.close()
        for child in processes: assert child.wait(timeout=30)==0,(root/'owner.err').read_text()
        evidence['handle_exit_evidence']=[ref.exit_evidence() for ref in refs]
        assert all(e is not None for e in evidence['handle_exit_evidence'])
        for ref in refs:ref.close()
        for log in logs:log.close()
        assert not any((root/n).exists() for n in ('connection.json','bootstrap.json','offer.json'))
        evidence['cleanup']=read_json(root/'cleanup.json')
        if os.environ.get('RUN013_EVIDENCE_DIR'):
            (Path(os.environ['RUN013_EVIDENCE_DIR'])/'windows_substitute_gui.json').write_text(canonical_json(evidence),encoding='utf-8')
