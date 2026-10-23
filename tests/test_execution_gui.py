"""Windows GUI lifecycle and readonly progress integration (no Solver)."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from abqjobpilot.execution.models import canonical_json, ExecutionError
from abqjobpilot.execution.process_handles import ProcessReference
from supervisor_helpers import ProcessHarness, read_json, wait_until

SOURCE=Path(__file__).resolve().parents[1]


def save_evidence(name, data):
    if os.environ.get('RUN012_EVIDENCE_DIR'):
        target=Path(os.environ['RUN012_EVIDENCE_DIR'])/(name+'.json')
        with target.open('x',encoding='utf-8') as f: f.write(canonical_json(data))


def public_run(run):
    keys=('run_id','project_id','project_instance_id','phase_attempt_id','plan_id','plan_digest','backend_id',
          'execution','queue_state','backend_outcome','process_observation','exit_verification','artifact_validation',
          'solver_conclusion','reconciliation','revision','process_records','process_exits','process_membership')
    return {k:run[k] for k in keys if k in run}


class Gui:
    def __init__(self, root, connection, key, label):
        self.root=root/label; self.root.mkdir()
        self.logs=[(self.root/n).open('wb') for n in ('stdout.txt','stderr.txt')]
        self.process=subprocess.Popen([sys.executable,'-B',str(SOURCE/'tests/run012_gui.py'),
            '--connection',str(connection),'--key',key,'--control',str(self.root)],
            cwd=str(root),stdin=subprocess.DEVNULL,stdout=self.logs[0],stderr=self.logs[1],
            shell=False,close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','TEMP':str(root),'TMP':str(root)})
        self.transport=ProcessReference(self.process.pid,cleanup=True)
        self.actual=None
        try:
            wait_until(lambda:(self.root/'identity.json').exists() or self.process.poll() is not None)
            assert (self.root/'identity.json').exists(),(self.root/'stderr.txt').read_text()
            self.identity=read_json(self.root/'identity.json')
            identity=self.identity['process']
            assert identity['parent_pid']==self.process.pid or identity['pid']==self.process.pid
            self.actual=ProcessReference(identity['pid'],identity,cleanup=True)
        except BaseException:
            self.close();raise

    def view(self,predicate):
        def check():
            if not (self.root/'view.json').exists():return None
            try: view=read_json(self.root/'view.json')
            except PermissionError: return None # Windows rename/read race; bounded wait, not a business query fallback.
            return view if predicate(view) else None
        return wait_until(check)

    def normal_close(self):
        api=ctypes.WinDLL('user32',use_last_error=True)
        api.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
        api.PostMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
        pid=ctypes.c_uint32()
        api.GetWindowThreadProcessId(self.identity['hwnd'],ctypes.byref(pid))
        assert pid.value==self.identity['process']['pid']
        assert api.PostMessageW(self.identity['hwnd'],0x10,0,0) # Normal WM_CLOSE
        assert self.process.wait(timeout=10)==0,(self.root/'stderr.txt').read_text()
        self.exits={'gui':self.actual.exit_evidence(),'venv_launcher':self.transport.exit_evidence(),
                    'application':read_json(self.root/'exit.json')}
        assert all(self.exits[k]['exit_code']==0 for k in ('gui','venv_launcher'))
        return self.exits

    def close(self):
        for ref in (self.actual,self.transport):
            if ref:
                if ref.exit_evidence() is None:
                    ref.api.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
                    assert ref.api.TerminateProcess(ref.handle,79)
                    ref.api.WaitForSingleObject(ref.handle,8000)
                ref.close()
        self.process.wait(timeout=8)
        for f in self.logs:f.close()


def connection(h):
    p=h.root/'gui-private-connection.json'
    p.write_text(canonical_json({'endpoint':read_json(h.endpoint_file),'credential':h.credential}),encoding='utf-8')
    return p


def db_facts(client,rid):
    # All assertions use public immutable records; no private SQL during GUI use.
    return {'run':client.run(rid),'receipt':client.receipt('key-0'),'gate':client.dispatch_gate(),
            'events':client.events(),'validations':client.validations(rid)}


def test_actual_gui_close_reopen_public_client_worker_survives(tmp_path):
    h=ProcessHarness(tmp_path,process_scenarios=['result_wait'])
    guis=[];refs=[];conn=None
    evidence={'os':sys.platform,'python':sys.executable,'version':sys.version,'temporary_root':str(tmp_path)}
    try:
        owner=h.owner()
        client=h.client()
        # Independent ordinary public example process submits before any GUI exists.
        offer=tmp_path/'offer.json';offer.write_text(canonical_json({'request':h.requests[0]}),encoding='utf-8')
        conn=connection(h);session=tmp_path/'session';session.mkdir()
        with (tmp_path/'client.stderr').open('wb') as err:
            a=subprocess.Popen([sys.executable,'-B',str(SOURCE/'examples/agent_first/client_workflow.py'),
                '--source',str(SOURCE),'--connection',str(conn),'--offer',str(offer),'--session',str(session),'--phase','submit'],
                cwd=tmp_path,stdout=subprocess.DEVNULL,stderr=err,shell=False,close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW)
            ar=ProcessReference(a.pid,cleanup=True);refs.append(ar)
            assert a.wait(timeout=15)==0,(tmp_path/'client.stderr').read_text()
        receipt=read_json(session/'session.json')['receipt'];rid=receipt['run_id']
        run=wait_until(lambda:(r if len((r:=client.run(rid))['process_records'])==4 else None))
        worker=next(m for m in run['process_records'] if m['role']=='worker')
        wr=ProcessReference(worker['pid'],worker,cleanup=True);refs.append(wr)
        wait_until(lambda:len(client.run(rid)['process_exits'])>=2)
        before=db_facts(client,rid)
        gui=Gui(tmp_path,conn,'key-0','gui_A');guis.append(gui)
        first=gui.view(lambda v:v['connected'] and rid in json.dumps(v['rows']) and 'WAITING' in v['progress_text'])
        assert dict(first['rows'])['原始接收回执']==receipt['request_id']
        page=client.progress(rid);seq=page['next_sequence']
        gui.view(lambda v:'"sequence": '+str(seq+1) in v['progress_text'])
        exits=gui.normal_close()
        after_seq=client.progress(rid)['next_sequence']
        wait_until(lambda:client.progress(rid)['next_sequence']>after_seq)
        growth=client.progress(rid)
        assert wr.exit_evidence() is None
        assert owner.process.poll() is None
        assert client.health()['process']==owner.identity
        assert client.dispatch_gate()==before['gate']
        assert client.receipt('key-0')==receipt
        gui2=Gui(tmp_path,conn,'key-0','gui_B');guis.append(gui2)
        reopened=gui2.view(lambda v:v['connected'] and rid in json.dumps(v['rows']) and 'WAITING' in v['progress_text'])
        assert client.submit(h.requests[0])['replayed'] # Same public request, no second execution.
        assert db_facts(client,rid)==before
        (Path(h.context.runtime_root)/'process_runs'/rid/'release.json').write_text('{}',encoding='utf-8')
        finished=h.finished(rid)
        shown=gui2.view(lambda v:v['connected'] and dict(v['rows']).get('Artifact 独立验证')=='VALID')
        assert finished['solver_conclusion']=='NOT_RUN' and finished['artifact_validation']=='VALID'
        assert len(finished['process_exits'])==4 and all(e['exit_code']==0 for e in finished['process_exits'])
        assert finished['process_records']==run['process_records']
        assert len([e for e in client.events() if e['type']=='START_INTENT'])==1
        physical=read_json(owner.control/'physical-launches.json')
        assert len(physical)==1 and physical[0]['run_id']==rid
        assert dict(shown['rows'])['执行阶段']==finished['execution']
        assert dict(shown['rows'])['OS 退出验证']==finished['exit_verification']
        # Stop owner normally after completion; connected GUI must show stale state.
        (owner.control/'stop.json').write_text('{}',encoding='utf-8');assert owner.process.wait(timeout=10)==0
        lost=gui2.view(lambda v:not v['connected'])
        assert '缓存不是实时' in lost['status'] and lost['last_update'] >= shown['last_update']
        # Explicit owner restart is paused; merely updating its connection/reopening cannot resume it.
        owner2=h.owner();conn=connection(h);client=h.client()
        paused=gui2.view(lambda v:v['connected'] and 'PAUSED' in v['status'])
        assert client.dispatch_gate()['state']=='PAUSED' and client.receipt('key-0')==receipt
        assert client.run(rid)['process_records']==run['process_records']
        exits2=gui2.normal_close()
        evidence.update(run_id=rid,receipt=receipt,owner_before=owner.identity,client_A_exit=ar.exit_evidence(),
            gui_A=first,gui_A_exits=exits,worker_alive_after_gui_chain_exit=wr.identity,
            progress_after_chain_exit=growth,sequence_at_gui_chain_exit=after_seq,gui_B=reopened,gui_completed=shown,gui_B_exits=exits2,
            disconnected=lost,restarted_paused=paused,service_final=public_run(finished),
            physical_member_set_unchanged=True,physical_launches=physical,start_intent_count=1,abaqus_calls=0)
        if os.environ.get('RUN012_EVIDENCE_DIR'):
            import shutil
            shutil.copyfile(gui2.root/'window.png',Path(os.environ['RUN012_EVIDENCE_DIR'])/'actual_dev_gui.png')
    finally:
        for g in guis:g.close()
        for ref in refs:
            if ref.exit_evidence() is None:
                ref.api.WaitForSingleObject(ref.handle,50000)
            assert ref.exit_evidence() is not None
            ref.close()
        for p in (conn,tmp_path/'offer.json'):
            if p and p.exists():p.unlink()
        h.close()
        evidence['cleanup']={'owner_lifecycle':read_json(tmp_path/'lifecycle.json'),'gui_handles_closed':True,'additional_private_handoff_removed':True}
        save_evidence('windows_gui_lifecycle',evidence)


def test_progress_auth_bounds_readonly_and_corruption(tmp_path):
    h=ProcessHarness(tmp_path,process_scenarios=['normal'])
    try:
        h.owner();client=h.client();rid=client.submit(h.requests[0])['receipt']['run_id'];h.finished(rid)
        before=db_facts(client,rid)
        first=client.progress(rid,0,1);assert len(first['records'])==1 and first['has_more']
        rest=client.progress(rid,first['next_sequence']);assert rest['records'][-1]['event']=='WORKER_RETURNING'
        assert db_facts(client,rid)==before
        for args in ({'run_id':rid,'after_sequence':0,'limit':65}, {'run_id':rid,'after_sequence':999,'limit':1},
                     {'run_id':rid,'after_sequence':0,'limit':1,'path':'C:/unexpected'}):
            with pytest.raises(ExecutionError):client.call('progress',args)
        from abqjobpilot.execution.client import FakeClient
        with pytest.raises(ExecutionError):FakeClient(client.endpoint,'wrong').progress(rid)
        with pytest.raises(ExecutionError):FakeClient({**client.endpoint,'project_instance_id':'wrong'},h.credential).progress(rid)
        log=Path(h.context.runtime_root)/'process_runs'/rid/'progress.jsonl'
        raw=log.read_bytes()
        for bad,code in ((b'x'*65537,'LIMIT_EXCEEDED'),(b'{}\n','INVALID_REQUEST')):
            log.write_bytes(bad)
            with pytest.raises(ExecutionError) as exc:client.progress(rid)
            assert exc.value.code==code
        log.write_bytes(raw+b'{')
        assert client.progress(rid)['records']==first['records']+rest['records']
        assert db_facts(client,rid)==before
    finally:h.close()


def test_product_entries_starter_exits_and_owner_is_independent(tmp_path):
    root=tmp_path/'demo'
    script=SOURCE/'examples/agent_first/dev_gui_demo.py'
    children=[];refs=[];logs=[];guis=[];data={}
    def command(action):
        out=(tmp_path/(action+'.stdout')).open('wb');err=(tmp_path/(action+'.stderr')).open('wb');logs.extend((out,err))
        p=subprocess.Popen([sys.executable,'-B',str(script),action,'--root',str(root)],
            cwd=tmp_path,stdin=subprocess.DEVNULL,stdout=out,stderr=err,shell=False,close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW,env={**os.environ,'TEMP':str(tmp_path),'TMP':str(tmp_path),'PYTHONDONTWRITEBYTECODE':'1'})
        children.append(p)
        ref=ProcessReference(p.pid,cleanup=True);refs.append(ref)
        assert p.wait(timeout=20)==0,(tmp_path/(action+'.stderr')).read_text()
        assert ref.exit_evidence()['exit_code']==0
        return ref.exit_evidence()
    try:
        data['starter_exit']=command('start')
        conn=root/'private/connection.json'
        wait_until(conn.exists)
        from abqjobpilot.execution.client import FakeClient
        value=read_json(conn);client=FakeClient(value['endpoint'],value['credential'])
        for identity in (read_json(root/'control/owner-identity.json'),read_json(root/'control/owner-transport.json')):
            refs.append(ProcessReference(identity['pid'],identity,cleanup=True))
        assert all(ref.exit_evidence() is None for ref in refs[-2:])
        # Opening before submit does not authorize/submit anything.
        gui=Gui(tmp_path,conn,'dev-gui-demo-request-1','waiting_gui');guis.append(gui)
        waiting=gui.view(lambda v:v['connected'] and dict(v['rows']).get('Run ID')=='未提交')
        assert client.events()==[]
        gui.normal_close()
        data['submit_client_exit']=command('submit')
        receipt=client.receipt('dev-gui-demo-request-1');rid=receipt['run_id']
        wait_until(lambda:len(client.run(rid)['process_records'])==4)
        gui2=Gui(tmp_path,conn,'dev-gui-demo-request-1','product_gui');guis.append(gui2)
        gui2.view(lambda v:v['connected'] and 'WAITING' in v['progress_text'])
        data['gui_exit']=gui2.normal_close()
        before=client.progress(rid)['next_sequence']
        wait_until(lambda:client.progress(rid)['next_sequence']>before)
        # The product's fixed trusted timer, not the GUI, releases after 45 seconds.
        final=wait_until(lambda:(r if (r:=client.run(rid))['execution']=='FINISHED' else None),timeout=60)
        assert final['artifact_validation']=='VALID' and len(final['process_exits'])==4
        assert all(e['exit_code']==0 for e in final['process_exits'])
        data.update(root=str(root),waiting_gui=waiting,run=public_run(final),receipt=receipt,gate=client.dispatch_gate(),
                    owner_identity=client.health()['process'],progress=client.progress(rid))
    finally:
        for g in guis:g.close()
        if (root/'control').exists() and not (root/'control/stop.json').exists():
            (root/'control/stop.json').write_text('{}',encoding='utf-8')
        for ref in refs:
            if ref.exit_evidence() is None:ref.api.WaitForSingleObject(ref.handle,50000)
            assert ref.exit_evidence() is not None
            ref.close()
        for p in children:p.wait(timeout=8)
        for f in logs:f.close()
        if (root/'control/cleanup.json').exists():
            data['cleanup']=read_json(root/'control/cleanup.json')
            assert data['cleanup']['private_remaining']==0
        save_evidence('product_entries',data)


def test_gui_observes_crashed_owner_uncertainty_without_recovery(tmp_path):
    h=ProcessHarness(tmp_path,process_scenarios=['result_wait']);gui=None;conn=None
    try:
        owner=h.owner(barriers=['process:before_create'])
        rid=h.client().submit(h.requests[0])['receipt']['run_id']
        owner.reached('process:before_create');owner.terminate()
        owner2=h.owner();client=h.client();conn=connection(h)
        before=db_facts(client,rid)
        assert before['gate']['state']=='PAUSED'
        assert before['run']['reconciliation_requirement']=='RECONCILIATION_REQUIRED'
        gui=Gui(tmp_path,conn,'key-0','uncertain_gui')
        view=gui.view(lambda v:v['connected'] and dict(v['rows']).get('对账需求')=='RECONCILIATION_REQUIRED')
        gui.view(lambda v:v['connected'] and v['last_update']>view['last_update'])
        assert db_facts(client,rid)==before
        assert not (owner2.control/'physical-launches.json').exists()
        wrong=read_json(conn);wrong['endpoint']['project_instance_id']='wrong-project'
        conn.write_text(canonical_json(wrong),encoding='utf-8')
        rejected=gui.view(lambda v:not v['connected'] and 'PROJECT_IDENTITY_MISMATCH' in v['status'])
        assert db_facts(client,rid)==before
        exits=gui.normal_close()
        save_evidence('gui_owner_crash_block',{'view':view,'gui_exits':exits,'state_unchanged':True,
                      'gate':before['gate'],'run':public_run(before['run']),'no_second_launch':True,
                      'wrong_project_rejected':rejected})
    finally:
        if gui:gui.close()
        if conn and conn.exists():conn.unlink()
        h.close()


def test_stalled_ipc_keeps_tk_responsive_and_close_is_bounded(tmp_path):
    import socket
    import threading
    from abqjobpilot.execution.protocol import PROTOCOL, receive, MAX_REQUEST
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1)
    listener.settimeout(10)
    accepted=threading.Event();release=threading.Event();errors=[]
    def stalled():
        try:
            with listener.accept()[0] as stream:
                receive(stream,MAX_REQUEST);accepted.set();release.wait(10)
        except Exception as exc:errors.append(type(exc).__name__)
    peer=threading.Thread(target=stalled);peer.start()
    conn=tmp_path/'connection.json'
    conn.write_text(canonical_json({'endpoint':{'protocol':PROTOCOL,'host':'127.0.0.1','port':listener.getsockname()[1],
        'project_id':'test','project_instance_id':'instance','context_digest':'test','owner_id':'stalled',
        'process':{},'execution_store':str(tmp_path/'unused.db')},'credential':'test-transport-only-not-a-real-secret'}),encoding='utf-8')
    gui=None
    try:
        gui=Gui(tmp_path,conn,'key','slow_gui')
        assert accepted.wait(5)
        view=gui.view(lambda v:not v['connected'])
        closed=gui.normal_close()
        assert closed['application']['heartbeat_ticks']>=15
        save_evidence('gui_stalled_transport',{'view':view,'normal_close':closed,'no_business_store_created':not (tmp_path/'unused.db').exists()})
    finally:
        release.set();peer.join(10);listener.close()
        if gui:gui.close()
        conn.unlink()
    assert not peer.is_alive() and not errors
