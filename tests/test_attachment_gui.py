"""Normal Dev entry: actual Windows UI selection, whole-process close/reconnect."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from abqjobpilot.execution.models import canonical_json
from abqjobpilot.execution.process_handles import ProcessReference
from supervisor_helpers import ProcessHarness, read_json, wait_until
from test_execution_gui import Gui, db_facts
from test_service_attachment import connection
from test_managed_scope import managed, bind, directory, terminal

SOURCE=Path(__file__).resolve().parents[1]

def action(gui,operation,**values):
    # UI automation channel belongs only to the test process, not application IPC.
    action_id=str(time.monotonic_ns())
    path=gui.root/('action_'+action_id+'.json')
    temporary=path.with_suffix('.partial')
    temporary.write_text(canonical_json({'operation':operation,'action_id':action_id,**values}),encoding='utf-8');temporary.replace(path)
    ack=gui.root/('ack_'+action_id+'.json')
    def acknowledged():
        try:return read_json(ack)
        except (FileNotFoundError,PermissionError):return None
    return wait_until(acknowledged)

def choose(gui,h,rid):
    previous=read_json(gui.root/'view.json')['last_update'] if (gui.root/'view.json').exists() else None
    ack=action(gui,'project',project=h.context.root)
    gui.view(lambda v:v['connected'] and v['selection_generation']==ack['selection_generation']
             and v['last_update']!=previous and rid in json.dumps(v['run_list']))
    action(gui,'select',run_id=rid)
    return gui.view(lambda v:v['connected'] and dict(v['rows']).get('Run ID')==rid)

def evidence(name,data,gui=None):
    target=os.environ.get('RUN018_EVIDENCE_DIR')
    if target:
        with (Path(target)/(name+'.json')).open('x',encoding='utf-8') as stream:stream.write(canonical_json(data))
        if gui and (gui.root/'window.png').exists():shutil.copyfile(gui.root/'window.png',Path(target)/(name+'.png'))


def test_normal_dev_entry_managed_worker_survives_gui_chain_and_reconnect(tmp_path):
    data={'os':sys.platform,'interpreter':sys.executable,'abaqus_calls':0}
    guis=[];private=None;ar=None
    with managed(tmp_path,['result_wait']) as h:
        try:
            owner=h.owner();private=connection(h);client=h.client()
            offer=tmp_path/'offer.json';offer.write_text(canonical_json({'request':h.requests[0]}),encoding='utf-8')
            session=tmp_path/'session';session.mkdir()
            with (tmp_path/'client.stderr').open('wb') as err:
                child=subprocess.Popen([sys.executable,'-B',str(SOURCE/'examples/agent_first/client_workflow.py'),
                    '--source',str(SOURCE),'--connection',str(private),'--offer',str(offer),'--session',str(session),'--phase','submit'],
                    cwd=tmp_path,stdout=subprocess.DEVNULL,stderr=err,close_fds=True,shell=False,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                ar=ProcessReference(child.pid)
                assert child.wait(timeout=15)==0,(tmp_path/'client.stderr').read_text()
            receipt=read_json(session/'session.json')['receipt'];rid=receipt['run_id']
            worker=bind(h,rid,'worker');wait_until(lambda:len(client.run(rid)['process_exits'])>=2)
            baseline=db_facts(client,rid)
            database_before=hashlib.sha256(Path(h.context.execution_store).read_bytes()).hexdigest()
            gui=Gui(tmp_path,None,None,'normal_A',attachment=True);guis.append(gui)
            selected=choose(gui,h,rid)
            shown=gui.view(lambda v:'WAITING' in v['progress_text'])
            cursor=client.progress(rid)['next_sequence']
            gui.view(lambda v:'"sequence": '+str(cursor+1) in v['progress_text'])
            exits=gui.normal_close()
            cursor=client.progress(rid)['next_sequence']
            wait_until(lambda:client.progress(rid)['next_sequence']>cursor)
            assert worker.exit_evidence() is None
            assert client.health()['process']==owner.identity
            assert owner.process.poll() is None
            gui2=Gui(tmp_path,None,None,'normal_B',attachment=True);guis.append(gui2)
            reconnected=choose(gui2,h,rid)
            assert dict(reconnected['rows'])['原始接收回执']==receipt['request_id']
            assert db_facts(client,rid)==baseline
            action(gui2,'reconnect')
            gui2.view(lambda v:v['connected'] and dict(v['rows']).get('Run ID')==rid)
            assert db_facts(client,rid)==baseline
            assert hashlib.sha256(Path(h.context.execution_store).read_bytes()).hexdigest()==database_before
            (directory(h,rid)/'release.json').write_text('{}',encoding='utf-8')
            final=terminal(h,rid)
            complete=gui2.view(lambda v:v['connected'] and dict(v['rows']).get('Artifact 独立验证')=='VALID')
            assert final['managed_completion']=='COMMITTED_EMPTY_SCOPE'
            assert final['solver_conclusion']=='NOT_RUN'
            assert len(read_json(owner.control/'physical-launches.json'))==1
            assert client.receipt('key-0')==receipt
            # Own completed service is stopped by its test harness, not GUI.
            (owner.control/'stop.json').write_text('{}',encoding='utf-8');assert owner.process.wait(timeout=10)==0
            disconnected=gui2.view(lambda v:not v['connected'])
            assert '缓存不是实时' in disconnected['status'] and dict(disconnected['rows'])['Run ID']==rid
            next_owner=h.owner();connection(h);client=h.client()
            paused=gui2.view(lambda v:v['connected'] and 'PAUSED' in v['status'])
            assert client.dispatch_gate()['state']=='PAUSED'
            assert client.run(rid)==final and client.receipt('key-0')==receipt
            exits2=gui2.normal_close()
            data.update(run_id=rid,receipt=receipt,owner=owner.identity,worker_alive_after_entire_gui_exit=worker.identity,
                client_A_exit=ar.exit_evidence(),gui_A=shown,gui_A_exit=exits,progress_sequence_after_gui_exit=cursor+1,
                gui_B=reconnected,gui_complete=complete,disconnected=disconnected,restarted_paused=paused,
                gui_B_exit=exits2,final=final,physical_launches=read_json(owner.control/'physical-launches.json'))
            data['readonly_database_hash_while_worker_waited']=database_before
            evidence('normal_gui_lifecycle',data,gui2)
        finally:
            for gui in guis:gui.close()
            if ar:ar.close()
            for path in (private,tmp_path/'offer.json'):
                if path and path.exists():path.unlink()
    evidence('normal_gui_cleanup',h.evidence)


def test_explicit_project_switch_missing_service_and_unknown_stay_readonly(tmp_path):
    roots=[tmp_path/n for n in ('first','second')]
    for root in roots:root.mkdir()
    first,second=[ProcessHarness(root) for root in roots]
    private=[];guis=[]
    try:
        owner=first.owner(barriers=['dispatch:after_artifact'])
        private.append(connection(first));client=first.client()
        rid=client.submit(first.requests[0])['receipt']['run_id'];owner.reached('dispatch:after_artifact')
        owner.terminate() # only identity-bound test owner; never a user process
        first.owner();connection(first)
        before=db_facts(client:=first.client(),rid)
        assert before['gate']['state']=='PAUSED'
        gui=Gui(tmp_path,None,None,'switch',attachment=True);guis.append(gui)
        unknown=choose(gui,first,rid)
        assert 'PAUSED' in unknown['status']
        action(gui,'project',project=second.context.root)
        missing=gui.view(lambda v:not v['connected'] and not v['rows'] and not v['run_list'])
        assert not second.children and rid not in json.dumps(missing)
        other=second.owner();private.append(connection(second));c2=second.client()
        rid2=c2.submit(second.requests[0])['receipt']['run_id'];second.finished(rid2)
        shown=choose(gui,second,rid2)
        assert rid not in json.dumps(shown) and first.context.project_id not in json.dumps(shown)
        choose(gui,first,rid)
        assert db_facts(client,rid)==before
        exits=gui.normal_close()
        evidence('project_switch_and_paused_unknown',{'unknown':unknown,'missing':missing,'second':shown,'exits':exits,
                 'first_unchanged':before,'abaqus_calls':0})
    finally:
        for gui in guis:gui.close()
        for path in private:
            if path.exists():path.unlink()
        first.close();second.close()


def test_normal_gui_large_run_list_pages_without_blocking_ui(tmp_path):
    h=ProcessHarness(tmp_path,fake_jobs=70);gui=private=None
    try:
        owner=h.owner(barriers=['dispatch:after_claim']);c=h.client();private=connection(h)
        ids=[c.submit(q)['receipt']['run_id'] for q in h.requests]
        owner.reached('dispatch:after_claim')
        gui=Gui(tmp_path,None,None,'pages',attachment=True)
        action(gui,'project',project=h.context.root)
        first=gui.view(lambda v:v['connected'] and len(v['run_list'])==32)
        assert [r[0] for r in first['run_list']]==list(reversed(ids))[:32]
        action(gui,'older')
        second=gui.view(lambda v:v['connected'] and v['run_list'] and v['run_list'][0][0]==ids[-33])
        action(gui,'older')
        third=gui.view(lambda v:v['connected'] and len(v['run_list'])==6)
        action(gui,'select',run_id=ids[0])
        selected=gui.view(lambda v:v['connected'] and dict(v['rows']).get('Run ID')==ids[0])
        exits=gui.normal_close()
        assert exits['application']['heartbeat_ticks']>=8
        assert c.run(ids[-1])['queue_state']=='PENDING'
        evidence('large_list',{'first':first,'second':second,'third':third,'selected':selected,'exits':exits})
    finally:
        if gui:gui.close()
        if private:private.unlink()
        h.close()
