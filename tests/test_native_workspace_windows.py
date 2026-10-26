"""Windows native GUI / new readonly IPC. Fixed Python only, new isolated Stores."""
import json
import os
from pathlib import Path
import subprocess
import sys
import hashlib

from abqjobpilot.execution.models import canonical_json,ExecutionError
from abqjobpilot.execution.process_handles import ProcessReference
from supervisor_helpers import ProcessHarness,read_json,wait_until
from test_execution_gui import Gui,db_facts
from test_attachment_gui import action
from test_service_attachment import connection
from test_managed_scope import managed,bind,directory,terminal
from abqjobpilot.execution.recovery import preview_interrupted_recovery
from abqjobpilot.execution.interruption import inspect_interrupted_execution
import pytest

SOURCE=Path(__file__).resolve().parents[1]

class NativeGui(Gui):
    def __init__(self,root,label):
        self.root=root/label;self.root.mkdir()
        self.logs=[(self.root/n).open('wb') for n in ('stdout.txt','stderr.txt')]
        self.process=subprocess.Popen([str(Path(sys.executable).with_name('pythonw.exe')),'-B',str(SOURCE/'tests/run024_gui.py'),'--control',str(self.root)],
            cwd=root,stdin=subprocess.DEVNULL,stdout=self.logs[0],stderr=self.logs[1],shell=False,close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW,env={**os.environ,'TEMP':str(root),'TMP':str(root),'PYTHONDONTWRITEBYTECODE':'1'})
        self.transport=ProcessReference(self.process.pid,cleanup=True);self.actual=None
        wait_until(lambda:(self.root/'identity.json').exists() or self.process.poll() is not None)
        assert (self.root/'identity.json').exists(),(self.root/'stderr.txt').read_text()
        self.identity=read_json(self.root/'identity.json')
        self.actual=ProcessReference(self.identity['process']['pid'],self.identity['process'],cleanup=True)


def choose(gui,h,rid):
    action(gui,'project',project=h.context.root)
    gui.view(lambda v:v['connected'] and rid in json.dumps(v['run_list']))
    action(gui,'select',run_id=rid)
    return gui.view(lambda v:v['connected'] and v['run_id']==rid and rid in v['details']['identity'])


def save(root,name,data):
    (root/(name+'.json')).write_text(canonical_json(data),encoding='utf-8')


def test_native_main_whole_gui_exit_reconnect_same_owner_and_readonly_recovery(tmp_path):
    guis=[];private=None
    with managed(tmp_path,['result_wait']) as h:
        try:
            owner=h.owner();private=connection(h);client=h.client()
            receipt=client.submit(h.requests[0])['receipt'];rid=receipt['run_id']
            worker=bind(h,rid,'worker');wait_until(lambda:len(client.run(rid)['process_exits'])>=2)
            before=db_facts(client,rid);raw_before=hashlib.sha256(Path(h.context.execution_store).read_bytes()).hexdigest()
            g=NativeGui(tmp_path,'native_A');guis.append(g)
            selected=choose(g,h,rid);shown=g.view(lambda v:'WAITING' in v['progress_text'])
            assert 'classification' in shown['details']['evidence'] and 'apply_allowed' in shown['details']['recovery']
            for page in ('overview','classic','runs','results','agent','service','settings'):
                action(g,'navigate',page=page)
            action(g,'navigate',page='overview');action(g,'command');action(g,'size',geometry='1600x900+0+0');action(g,'capture',name='running_1600')
            action(g,'size',geometry='1366x768+0+0');action(g,'capture',name='running_1366')
            action(g,'command',section='runs');action(g,'capture',name='agent_command')
            exits=g.normal_close();cursor=client.progress(rid)['next_sequence']
            wait_until(lambda:client.progress(rid)['next_sequence']>cursor)
            assert worker.exit_evidence() is None and owner.process.poll() is None
            assert client.health()['process']==owner.identity
            g2=NativeGui(tmp_path,'native_B');guis.append(g2)
            reconnected=choose(g2,h,rid)
            assert receipt['request_id'] in reconnected['details']['identity']
            assert db_facts(client,rid)==before
            assert hashlib.sha256(Path(h.context.execution_store).read_bytes()).hexdigest()==raw_before
            for locale in ('en','zh-CN','fr-FR','de-DE'):
                action(g2,'language',locale=locale);action(g2,'capture',name=locale)
            (directory(h,rid)/'release.json').write_text('{}',encoding='utf-8')
            final=terminal(h,rid)
            completed=g2.view(lambda v:'COMMITTED_EMPTY_SCOPE' in v['details']['identity'] and 'VALID' in v['details']['identity'])
            assert len(read_json(owner.control/'physical-launches.json'))==1
            assert client.receipt('key-0')==receipt and final['solver_conclusion']=='NOT_RUN'
            exits2=g2.normal_close()
            save(tmp_path,'NATIVE_EVIDENCE',{'run_id':rid,'receipt':receipt,'owner':owner.identity,'worker_alive_after_gui_exit':worker.identity,
                 'gui_A_exit':exits,'gui_B_exit':exits2,'progress_after_exit':cursor+1,'initial':shown,'reconnected':reconnected,
                 'final':final,'completed':completed,'store_readonly_hash':raw_before,'abaqus_calls':0})
        finally:
            for gui in guis:gui.close()
            if private and private.exists():private.unlink()


def test_recovery_readonly_ipc_uses_same_core_and_no_apply(tmp_path):
    h=ProcessHarness(tmp_path);private=None;gui=None
    try:
        owner=h.owner(barriers=['dispatch:after_artifact']);client=h.client()
        rid=client.submit(h.requests[0])['receipt']['run_id'];owner.reached('dispatch:after_artifact')
        owner.terminate() # only owned synthetic fixture, identity-bound retained handle
        h.owner();client=h.client();before=db_facts(client,rid)
        core=inspect_interrupted_execution(h.context,rid);rpc=client.inspect_interrupted_execution(rid)
        assert rpc['body']['diagnosis']==core['body']['diagnosis']
        assert rpc['body']['decision_digest']==core['body']['decision_digest']
        p=client.preview_interrupted_recovery(rid);expected=preview_interrupted_recovery(h.context,rid)
        assert p['preview_digest']==expected['preview_digest']
        for _ in range(3):client.preview_interrupted_recovery(rid);client.inspect_interrupted_execution(rid)
        assert db_facts(client,rid)==before
        with pytest.raises(ExecutionError):client.call('apply_interrupted_recovery',{'approved':True})
        with pytest.raises(ExecutionError):client.call('inspect_interrupted_execution',{'run_id':rid,'observe_os':True})
        assert db_facts(client,rid)==before
        private=connection(h);gui=NativeGui(tmp_path,'recovery_gui')
        shown=choose(gui,h,rid)
        assert core['body']['diagnosis']['classification'] in shown['details']['evidence']
        assert p['body']['decision'] in shown['details']['recovery']
        assert db_facts(client,rid)==before
        action(gui,'navigate',page='runs');action(gui,'capture',name='recovery')
        exits=gui.normal_close()
        save(tmp_path,'RECOVERY_IPC',{'core_diagnosis':core['body']['diagnosis'],'rpc':rpc,'preview':p,'unchanged':before})
    finally:
        if gui:gui.close()
        if private and private.exists():private.unlink()
        h.close()


def test_native_project_switch_disconnect_cache_and_missing_service(tmp_path):
    first_root=tmp_path/'first';second_root=tmp_path/'second';first_root.mkdir();second_root.mkdir()
    first=ProcessHarness(first_root);second=ProcessHarness(second_root);gui=None;private=[]
    try:
        owner=first.owner();private.append(connection(first));client=first.client()
        rid=client.submit(first.requests[0])['receipt']['run_id'];first.finished(rid)
        before=db_facts(client,rid)
        gui=NativeGui(tmp_path,'switch_gui');a=choose(gui,first,rid)
        action(gui,'project',project=second.context.root)
        missing=gui.view(lambda v:not v['connected'] and not v['run_list'])
        assert rid not in json.dumps(missing) and not second.children
        second.owner();private.append(connection(second));other=second.client()
        rid2=other.submit(second.requests[0])['receipt']['run_id'];second.finished(rid2)
        b=choose(gui,second,rid2);assert rid not in json.dumps(b)
        choose(gui,first,rid)
        (owner.control/'stop.json').write_text('{}',encoding='utf-8');assert owner.process.wait(timeout=10)==0
        stale=gui.view(lambda v:not v['connected'] and rid in v['details']['identity'])
        assert 'last successful' in stale['status'] and stale['last_update']!='—'
        assert len(first.children)==1 and len(second.children)==1
        gui.normal_close()
        save(tmp_path,'SWITCH_EVIDENCE',{'first':a,'missing':missing,'second':b,'stale':stale,'before':before})
    finally:
        if gui:gui.close()
        for path in private:
            if path.exists():path.unlink()
        first.close();second.close()
