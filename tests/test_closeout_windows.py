"""Actual Windows owner stop/restart/crash, fixed Python only, original records untouched."""
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading

import pytest
from abqjobpilot.execution import create_experiment,ExperimentStore,ExecutionService
from abqjobpilot.execution.models import canonical_json,CONTRACT,now,ExecutionError
from abqjobpilot.execution.standard_contract import StandardConfig,prepare,issue_execution
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.store import ReadOnlyStore
from abqjobpilot.execution import closeout
from supervisor_helpers import wait_until,read_json,bind_child_handle
from test_execution_gui import Gui

SOURCE=Path(__file__).resolve().parents[1]


class Fixture:
    def __init__(self,root,monkeypatch):
        self.root=root;self.children=[];self.refs=[];self.logs=[];self.guis=[];self.killed=set()
        self.evidence={'scope':'WINDOWS_FIXED_PYTHON_SUBSTITUTE_NOT_ABAQUS','abaqus_calls':0,'python':sys.executable,
                       'root':str(root),'os':sys.platform}
        engineering=root/'engineering';engineering.mkdir();(engineering/'scratch').mkdir()
        (engineering/'axial_bar.inp').write_bytes((SOURCE/'docs/agent_first/run_010/axial_bar.inp').read_bytes())
        self.ctx=create_experiment(root,root/'project')
        config=StandardConfig(canonical_json({'interpreter':sys.executable,'host_policy':'independent-service-same-windows-session-v1'}))
        with monkeypatch.context() as patch:
            patch.setattr(StandardConfig,'verify',lambda self:None)
            with closing(ExperimentStore(self.ctx)) as store:
                service=ExecutionService(self.ctx,store,client_namespace='r14-test',standard_config=config)
                self.plan=prepare(service,engineering,'r013_bar_1433abcd',expires_at=now()+3600).to_dict()
                grant=issue_execution(service,self.plan['plan_id'],expires_at=now()+1800,approval_source='CONTROLLED_PYTHON_ONLY')
                self.boot={'context':self.ctx.to_dict(),'authority_instance':store._session.authority_instance,
                    'credential':secrets.token_hex(32),'client_namespace':'r14-test','endpoint_file':str(root/'endpoint.json')}
        self.request={'contract_version':CONTRACT,'operation':'submit','project_id':self.ctx.project_id,
            'project_instance_id':self.ctx.project_instance_id,'plan_id':self.plan['plan_id'],'plan_digest':self.plan['plan_digest'],
            'job_id':self.plan['job_id'],'job_revision':1,'grant_id':grant['grant_id'],'idempotency_key':'r14-fixed','retry_of':None}
        (root/'plan.json').write_text(canonical_json(self.plan))

    def start(self):
        for name in ('stop','connection.json','cleanup.json','approval-error.json'):(self.root/name).unlink(missing_ok=True)
        (self.root/'bootstrap.json').write_text(canonical_json(self.boot))
        out=(self.root/f'owner{len(self.children)}.out').open('wb');err=(self.root/f'owner{len(self.children)}.err').open('wb')
        self.logs.extend([out,err])
        p=subprocess.Popen([sys.executable,'-B',str(SOURCE/'tests/run014_process.py'),'owner',str(self.root)],
            cwd=self.root,stdin=subprocess.DEVNULL,stdout=out,stderr=err,shell=False,close_fds=True,creationflags=0x08000000,
            env={**os.environ,'TEMP':str(self.root),'TMP':str(self.root),'PYTHONDONTWRITEBYTECODE':'1'})
        self.children.append(p);self.refs.append(ProcessReference(p.pid))
        wait_until(lambda:(self.root/'connection.json').exists() or p.poll() is not None)
        assert p.poll() is None,Path(err.name).read_text()
        connection=read_json(self.root/'connection.json');self.client=FakeClient(connection['endpoint'],connection['credential'])
        identity=self.client.health()['process'];self.owner_ref=ProcessReference(identity['pid'],identity);self.refs.append(self.owner_ref)
        self.p=p;self.identity=identity
        return p

    def submit(self):
        accepted=self.client.submit(self.request);self.rid=accepted['receipt']['run_id']
        wait_until(lambda:(self.root/'worker.json').exists())
        identity=read_json(self.root/'worker.json');self.worker=ProcessReference(identity['pid'],identity);self.refs.append(self.worker)
        self.evidence.update(receipt=accepted,worker_identity=identity)
        wait_until(lambda:len(self.client.run(self.rid).get('process_records',[]))>=2)
        # Retain the venv redirector too, not only the worker's actual Python PID.
        members=self.client.run(self.rid)['process_records']
        for member in members:
            if not any(r.identity['pid']==member['pid'] for r in self.refs):
                self.refs.append(ProcessReference(member['pid'],member))
        self.evidence['fixed_substitute_members']=members
        return self.rid

    def finish_observation(self,exit_worker=True):
        if exit_worker:
            (self.root/'release-worker').touch();wait_until(lambda:self.worker.exit_evidence() is not None)
            wait_until(lambda:self.client.run(self.rid).get('all_observed_exited'))
        (self.root/'finish-observation').touch()
        # Run persistence precedes pause_after_error and dispatch-guard exit.
        # Await the existing quiescent-owner precondition; keep all original
        # release eligibility assertions. This is not an execution retry.
        samples=[]
        def quiescent():
            r=self.client.run(self.rid)
            if r['reconciliation']!='RECONCILIATION_REQUIRED':return None
            preview=self.client.preview_closeout(self.rid)
            samples.append({'gate':preview['recorded_gate']['state'],'reasons':preview['reasons']})
            if preview['recorded_gate']['state']=='PAUSED' and 'CURRENT_QUIESCENT_OWNER_REQUIRED' not in preview['reasons']:
                return r
        result=wait_until(quiescent)
        self.evidence['finish_observation_samples']=samples
        return result

    def permission(self):
        (self.root/'approve-test.json').write_text(canonical_json({'run_id':self.rid,'action':closeout.RELEASE}))
        wait_until(lambda:(self.root/'management-request.json').exists() or (self.root/'approval-error.json').exists())
        assert not (self.root/'approval-error.json').exists()
        return read_json(self.root/'management-request.json')

    def stop(self):
        (self.root/'stop').touch();assert self.p.wait(10)==0
        assert self.owner_ref.exit_evidence() is not None

    def cleanup(self):
        (self.root/'release-worker').touch();(self.root/'finish-observation').touch();(self.root/'stop').touch()
        for g in self.guis:g.close()
        for p in self.children:
            code=p.wait(35);assert code==0 or p.pid in self.killed
        exits=wait_until(lambda:([r.exit_evidence() for r in self.refs] if all(r.exit_evidence() is not None for r in self.refs) else None))
        self.evidence['all_retained_handle_exits']=exits
        for r in self.refs:r.close();assert not r.handle
        for log in self.logs:log.close()
        for name in ('bootstrap.json','connection.json','offer.json','management-request.json','approve-test.json'):
            (self.root/name).unlink(missing_ok=True)  # This fixture's exact private files only, after process exits.
        self.evidence['cleanup']={'processes_exited':True,'retained_handles_closed':True,'private_credentials_removed':True}
        if os.environ.get('RUN014_EVIDENCE_DIR'):
            (Path(os.environ['RUN014_EVIDENCE_DIR'])/(self.root.name+'.json')).write_text(canonical_json(self.evidence),encoding='utf-8')


def test_normal_owner_stop_leaves_worker_alive_and_restart_blocked(tmp_path,monkeypatch):
    h=Fixture(tmp_path,monkeypatch)
    try:
        h.start();h.submit();run=h.finish_observation(False)
        assert not run['all_observed_exited'] and not h.client.preview_closeout(h.rid)['actions'][1]['eligible']
        owner=h.identity;h.stop()
        assert h.worker.exit_evidence() is None
        sta=Path(h.plan['engineering'])/(h.plan['job_name']+'.sta');before=sta.stat().st_size
        wait_until(lambda:sta.stat().st_size>before)
        h.evidence.update(owner_before_stop=owner,worker_alive_after_owner_and_launcher_exit=True,log_grew_after_owner_exit=True)
        h.start();assert h.identity!=owner
        assert h.client.run(h.rid)==run and h.client.dispatch_gate()['state']=='PAUSED'
        assert h.client.preview_closeout(h.rid)['resources']['slot_run_id']==h.rid
        assert len(read_json(tmp_path/'physical-launches.json'))==1
        h.evidence['restart_preview']=h.client.preview_closeout(h.rid)
    finally:h.cleanup()


def test_public_disposition_lost_response_gui_and_restart(tmp_path,monkeypatch):
    h=Fixture(tmp_path,monkeypatch)
    try:
        h.start();h.submit();original=h.finish_observation();preview=h.client.preview_closeout(h.rid)
        assert preview['actions'][1]['eligible'];req=h.permission()
        gui=Gui(tmp_path,tmp_path/'connection.json','r14-fixed','closeout-gui');h.guis.append(gui)
        shown=gui.view(lambda v:v['connected'] and dict(v['rows']).get('逻辑槽占用')==h.rid)
        (tmp_path/'drop-response').touch()
        with pytest.raises(ExecutionError) as exc:h.client.apply_closeout(req)
        assert exc.value.code=='ACCEPTANCE_UNKNOWN'
        result=h.client.apply_closeout(req);assert result['replayed']
        after=h.client.run(h.rid);assert after['overall_exit']==original['overall_exit']=='UNKNOWN'
        rendered=gui.view(lambda v:dict(v['rows']).get('行政处置（不改退出证据）')=='LOGICAL_SLOT_RELEASED_WITH_RESIDUAL_UNCERTAINTY')
        exits=gui.normal_close();assert h.client.dispatch_gate()['state']=='PAUSED'
        h.evidence.update(preview=preview,result=result,gui_before=shown,gui_after=rendered,gui_exits=exits,
            diagnostic=h.client.diagnose(h.rid),original_run=original,administrative_run=after)
        h.stop();h.start()
        assert h.client.apply_closeout(req)['receipt']==result['receipt']
        assert h.client.dispatch_gate()['state']=='PAUSED'
        assert h.client.preview_closeout(h.rid)['resources']['slot_run_id'] is None
        assert len(read_json(tmp_path/'physical-launches.json'))==1
        h.evidence['physical_launches']=read_json(tmp_path/'physical-launches.json')
    finally:h.cleanup()


def test_true_owner_crash_during_disposition_no_unrecorded_unlock(tmp_path,monkeypatch):
    h=Fixture(tmp_path,monkeypatch)
    try:
        h.start();h.submit();h.finish_observation();req=h.permission()
        (tmp_path/'crash-before-commit').touch();errors=[]
        def apply():
            try:h.client.apply_closeout(req)
            except ExecutionError as exc:errors.append(exc.code)
        thread=threading.Thread(target=apply);thread.start()
        ready=wait_until(lambda:read_json(tmp_path/'crash-ready.json') if (tmp_path/'crash-ready.json').exists() else None)
        api,handle=bind_child_handle(h.p,ready['owner'])
        try:
            assert api.TerminateProcess(handle,77) and api.WaitForSingleObject(handle,8000)==0
        finally:api.CloseHandle(handle)
        h.killed.add(h.p.pid);h.p.wait(8);thread.join(5);assert not thread.is_alive() and errors==['ACCEPTANCE_UNKNOWN']
        # No journal recovery or automatic restart: supported reads must refuse.
        with pytest.raises(ExecutionError) as exc:ReadOnlyStore(h.ctx).query_run(h.ctx,h.rid)
        assert exc.value.code=='STORE_REQUIRES_MAINTENANCE'
        assert len(read_json(tmp_path/'physical-launches.json'))==1
        h.evidence.update(crash_window=ready,read_result=exc.value.code,maintenance_required=True)
    finally:h.cleanup()
