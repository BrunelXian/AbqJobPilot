"""One-shot acceptance measurements only. Never submits, authorizes or starts a Backend.

Uses the EXISTING actual GUI telemetry entry and public client. No owner stop,
termination, state repair or DB access. Only identity-checked own GUI WM_CLOSE.
"""
import ctypes
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[3]
sys.path.insert(0, str(SOURCE))
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.models import digest, canonical_json, ExecutionError
from abqjobpilot.execution.process_handles import ProcessReference

PYTHON = r'D:\XianLab\envs\LangChainEnv\Scripts\python.exe'
KEY = 'run013-standard-once'
MANIFEST = SOURCE/'docs/agent_first/run_013/ACCEPTANCE_MANIFEST.json'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def stamp():
    return datetime.datetime.now().astimezone().isoformat()


def save(name, value):
    with (HERE/name).open('x', encoding='utf-8') as f:
        f.write(canonical_json(value)); f.flush(); os.fsync(f.fileno())


def wait(fn, seconds=15):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        result=fn()
        if result: return result
        time.sleep(.05)
    raise RuntimeError('MEASUREMENT_TIMEOUT')


class Gui:
    def __init__(self, label, root):
        self.directory=HERE/label; self.directory.mkdir()
        self.logs=[(self.directory/name).open('xb') for name in ('stdout.txt','stderr.txt')]
        self.child=subprocess.Popen([PYTHON,'-B',str(SOURCE/'tests/run012_gui.py'),
            '--connection',str(root/'private/connection.json'),'--key',KEY,'--control',str(self.directory)],
            cwd=str(root/'non_repository_cwd'),stdin=subprocess.DEVNULL,
            stdout=self.logs[0],stderr=self.logs[1],shell=False,close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            env={'SystemRoot':os.environ['SystemRoot'],'TEMP':str(root),'TMP':str(root),
                 'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'})
        self.transport=ProcessReference(self.child.pid)
        wait(lambda:(self.directory/'identity.json').exists())
        self.identity=read(self.directory/'identity.json')
        info=self.identity['process']
        assert info['parent_pid']==self.child.pid or info['pid']==self.child.pid
        self.actual=ProcessReference(info['pid'],info)

    def view(self):
        try: return read(self.directory/'view.json')
        except (FileNotFoundError, PermissionError, json.JSONDecodeError): return None

    def close_normally(self):
        api=ctypes.WinDLL('user32',use_last_error=True)
        api.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
        api.PostMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
        pid=ctypes.c_uint32();api.GetWindowThreadProcessId(self.identity['hwnd'],ctypes.byref(pid))
        assert pid.value==self.identity['process']['pid'] and self.actual.exit_evidence() is None
        assert api.PostMessageW(self.identity['hwnd'],0x10,0,0)
        wait(lambda:self.actual.exit_evidence(),10)
        wait(lambda:self.transport.exit_evidence(),10)
        return {'method':'identity_checked_WM_CLOSE','time':stamp(),
                'gui':self.actual.exit_evidence(),'venv_launcher':self.transport.exit_evidence(),
                'application':read(self.directory/'exit.json')}

    def release_handles_only(self):
        self.actual.close();self.transport.close()
        self.child._handle.Close();self.child._child_created=False
        for f in self.logs: f.close()


def main():
    manifest=read(MANIFEST)
    assert digest(manifest['body'])=='sha256:3c59461d53e658eb9894d6936bd405f85a7f27b6ebc3deb5343c81d8411ceebe'
    root=Path(manifest['body']['context']['test_root'])
    conn=read(root/'private/connection.json');client=FakeClient(conn['endpoint'],conn['credential'])
    owner_identity=conn['endpoint']['process']
    refs=[];guis=[];before_close=None;after_close=None;solver_ref=None;receipt=None
    result={'started_at':stamp(),'role':'measurement_only','submits_from_this_script':0,
            'abaqus_calls_from_this_script':0,'owner':owner_identity,'gui_close_running_solver':'NOT_OBSERVED'}
    try:
        owner=ProcessReference(owner_identity['pid'],owner_identity);refs.append(owner)
        assert owner.exit_evidence() is None
        gui=Gui('gui_A',root);guis.append(gui)
        first=wait(lambda:(v if (v:=gui.view()) and v['connected'] else None))
        assert dict(first['rows'])['Run ID']=='未提交'
        save('READY.json',{'time':stamp(),'gui':gui.identity,'owner':owner_identity,
                           'health':client.health(),'gate':client.dispatch_gate(),'rendered':first})
        print('GUI_READY_NO_SUBMISSION',flush=True)
        end=time.monotonic()+180
        while time.monotonic()<end:
            try: receipt=client.receipt(KEY);break
            except ExecutionError as e:
                if e.code!='NOT_FOUND': raise
            time.sleep(.1)
        if receipt is None: raise RuntimeError('NO_SUBMISSION_WITHIN_MEASUREMENT_BUDGET')
        save('ORIGINAL_RECEIPT.json',receipt);rid=receipt['run_id']
        result['receipt']=receipt
        end=time.monotonic()+330
        last=None;closed=False;reopened=False;log_before=None;last_write=0
        with (HERE/'PUBLIC_OBSERVATIONS.jsonl').open('x',encoding='utf-8') as log:
            while time.monotonic()<end:
                run=client.run(rid);view=guis[-1].view()
                if time.monotonic()-last_write>=.5 or run.get('execution_phase')!=last:
                    log.write(canonical_json({'read_at':stamp(),'run':run,'progress':client.progress(rid)})+'\n');log.flush()
                    last_write=time.monotonic();last=run.get('execution_phase')
                if not closed and view and view['connected'] and dict(view['rows']).get('Run ID')==rid:
                    for member in run.get('process_records',[]):
                        if Path(member['image_path']).name.casefold()!='standard.exe': continue
                        candidate=ProcessReference(member['pid'],member)
                        if candidate.exit_evidence() is not None: candidate.close();continue
                        solver_ref=candidate;refs.append(candidate)
                        before_close={'time':stamp(),'solver':member,'solver_exit':candidate.exit_evidence(),
                            'owner':client.health(),'owner_exit':owner.exit_evidence(),'progress':client.progress(rid),
                            'view':view,'receipt':client.receipt(KEY),'gate':client.dispatch_gate()}
                        save('BEFORE_GUI_CLOSE.json',before_close)
                        exits=gui.close_normally();closed=True
                        after_close={'time':stamp(),'gui_exits':exits,'solver':candidate.identity,
                            'solver_exit':candidate.exit_evidence(),'owner_exit':owner.exit_evidence(),
                            'health':client.health(),'progress':client.progress(rid),'receipt':client.receipt(KEY),
                            'gate':client.dispatch_gate()}
                        save('AFTER_GUI_CLOSE.json',after_close)
                        result['gui_close_running_solver']='OBSERVED' if (after_close['solver_exit'] is None and after_close['owner_exit'] is None) else 'NOT_OBSERVED_AFTER_CLOSE'
                        print('GUI_CLOSED '+result['gui_close_running_solver'],flush=True)
                        # No need to wait for log growth; small model may finish quickly.
                        log_before=after_close['progress']
                        second=Gui('gui_B',root);guis.append(second)
                        shown=wait(lambda:(v if (v:=second.view()) and v['connected'] and dict(v['rows']).get('Run ID')==rid else None))
                        reopened=True
                        save('GUI_RECONNECTED.json',{'time':stamp(),'gui':second.identity,'rendered':shown,
                            'receipt':client.receipt(KEY),'health':client.health(),'gate':client.dispatch_gate(),
                            'solver_exit_at_reconnect':candidate.exit_evidence(),'progress':client.progress(rid)})
                        print('GUI_RECONNECTED_SAME_RUN',flush=True)
                        break
                if closed and 'log_change_after_close' not in result:
                    progress=client.progress(rid)
                    if progress!=log_before:
                        result['log_change_after_close']={'time':stamp(),'progress':progress,
                            'solver_exit':solver_ref.exit_evidence() if solver_ref else None}
                if run.get('execution_phase')=='EVIDENCE_RECORDED' or run.get('execution')=='BLOCKED':
                    save('FINAL_PUBLIC_RUN.json',run)
                    save('FINAL_VALIDATIONS.json',client.validations(rid))
                    save('FINAL_GATE.json',client.dispatch_gate())
                    events=[];cursor=0
                    while True:
                        page=client.events(cursor,64)
                        if not page:break
                        events.extend(page);cursor=max(e['project_sequence'] for e in page)
                        if len(events)>1024:raise RuntimeError('EVENT_BOUND')
                    save('FINAL_EVENTS.json',events)
                    report=client.diagnose(rid)
                    client.export_diagnostic(report,export_root=HERE,target=HERE/'DIAGNOSTIC.json')
                    shown=wait(lambda:(v if (v:=guis[-1].view()) and v['connected'] and dict(v['rows']).get('执行阶段')==run['execution'] else None))
                    save('FINAL_GUI_VIEW.json',shown)
                    result['final_run']=run;result['final_gate']=client.dispatch_gate()
                    result['final_receipt_matches']=client.receipt(KEY)==receipt
                    result['reconnected']=reopened
                    break
                time.sleep(.08)
            else: result['measurement_end']='WAIT_ENDED_NO_OWNER_OR_SOLVER_STOP'
        result['ended_at']=stamp();result['remaining_gui']=[g.identity for g in guis if g.actual.exit_evidence() is None]
        result['owner_left_running']=owner.exit_evidence() is None
        save('MEASUREMENT_RESULT.json',result)
        print('MEASUREMENT_FINISHED_OWNER_AND_GUI_PRESERVED',flush=True)
    except BaseException as exc:
        save('MEASUREMENT_ERROR.json',{'time':stamp(),'code':getattr(exc,'code',type(exc).__name__),
                                      'next':'Readonly query only; no resubmit or automatic process termination'})
        raise
    finally:
        for ref in refs:ref.close()
        for gui in guis:gui.release_handles_only()


if __name__=='__main__':main()
