"""Instrument the actual normal native entry; no business API replacement."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys

p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);args=p.parse_args()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['ABQJOBPILOT_UI_PREFS']=str(args.control.parent/'display.json')
def guard(event,values):
    if event=='import' and values[0] in {'abqjobpilot.config','abqjobpilot.runner_core','abqjobpilot.gui_legacy',
            'abqjobpilot.execution.supervisor','abqjobpilot.execution.test_authority','abqjobpilot.recovery_management'}:
        raise AssertionError('Product-only monitoring imported a forbidden capability')
    if event in {'subprocess.Popen','os.system','sqlite3.connect'}:raise AssertionError('Read-only GUI launch/database trap')
sys.addaudithook(guard)
from abqjobpilot.execution.ownership import current_process_identity
from abqjobpilot.execution.client import FakeClient
from abqjobpilot import gui_app
import run_gui

original_call=FakeClient.call
def readonly_call(client,operation,arguments):
    assert operation in {'health','project_view','run','receipt','events','progress','validations','preview_closeout',
                          'inspect_interrupted_execution','preview_interrupted_recovery'}
    return original_call(client,operation,arguments)
FakeClient.call=readonly_call

def write(name,data):
    path=args.control/name;temp=path.with_suffix('.partial')
    temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    try:temp.replace(path)
    except PermissionError:temp.unlink()

def observe(value):
    value['selection_generation']=app.execution_view.lifecycle_generation
    write('view.json',value)

original=gui_app.AbqJobPilotApp;ticks=[0];errors=[]
def construct(**kw):
    global app,hwnd
    assert kw['native_workspace'] and kw['attachment_mode']
    app=original(**kw,on_execution_view=observe)
    app.report_callback_exception=lambda *args:errors.append(str(args))
    app.update_idletasks()
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.GetAncestor.argtypes=[ctypes.c_void_p,ctypes.c_uint];api.GetAncestor.restype=ctypes.c_void_p
    hwnd=api.GetAncestor(app.winfo_id(),2)
    write('identity.json',{'process':current_process_identity(),'hwnd':hwnd,'normal_main':True,'native':True})
    def tick():
        ticks[0]+=1
        for source in sorted(args.control.glob('action_*.json')):
            action=json.loads(source.read_text(encoding='utf-8'));source.unlink();view=app.execution_view
            op=action['operation']
            if op=='project':view.attach_project(action['project'])
            elif op=='select':view.select_run_id(action['run_id'])
            elif op=='reconnect':view.reconnect()
            elif op=='older':view.older_button.invoke()
            elif op=='navigate':view.navigate(action['page'])
            elif op=='language':view.change_language(action['locale'])
            elif op=='size':app.geometry(action['geometry']);app.update_idletasks();view.restore_layout(default=True)
            elif op=='command':view.show_command(action.get('section'))
            elif op=='select_results':view.results_tree.selection_set(action['run_id']);view.results_tree.event_generate('<<TreeviewSelect>>')
            elif op=='filter':view.filters[view.queue_tree].set(action['text'])
            elif op=='capture':
                from cockpit_capture import capture
                app.update();capture(hwnd,args.control/(action['name']+'.png'))
            write('ack_'+action['action_id']+'.json',{'operation':op,'selection_generation':view.lifecycle_generation,'page':view.current_page,'ticks':ticks[0]})
        app.after(50,tick)
    app.after(50,tick);return app
gui_app.AbqJobPilotApp=construct
sys.argv=[str(Path(run_gui.__file__))];run_gui.main()
for reader in app.execution_view.readers:reader.thread.join(8);assert not reader.thread.is_alive()
assert not errors,errors
write('exit.json',{'mainloop_returned':True,'reader_joined':True,'heartbeat_ticks':ticks[0],
                  'no_legacy_import':'abqjobpilot.config' not in sys.modules,'normal_main':True,'native':True})
