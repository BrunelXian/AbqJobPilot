"""Instrument the normal no-argument run_gui.main, using only UI action hooks."""
import argparse
import ctypes
import json
from pathlib import Path
import sys

p=argparse.ArgumentParser();p.add_argument('--control',required=True,type=Path);args=p.parse_args()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def guard(event,values):
    if event=='import' and values[0] in {'abqjobpilot.config','abqjobpilot.runner_core','abqjobpilot.gui_legacy',
            'abqjobpilot.execution.store','abqjobpilot.execution.service','abqjobpilot.execution.supervisor',
            'abqjobpilot.execution.test_authority','abqjobpilot.project','abqjobpilot.settings_store'}:
        raise AssertionError('Normal attachment GUI imported forbidden capability')
    if event in {'subprocess.Popen','os.system','sqlite3.connect'}:raise AssertionError('GUI launch/database trap')
sys.addaudithook(guard)
from abqjobpilot.execution.ownership import current_process_identity
from abqjobpilot.execution.client import FakeClient
from abqjobpilot import gui_app
import run_gui

original_call=FakeClient.call
def readonly_call(client,operation,arguments):
    assert operation in {'health','project_view','run','receipt','events','progress','validations','preview_closeout','inspect_interrupted_execution','preview_interrupted_recovery'}
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
    if value['connected'] and 'WAITING' in value['progress_text'] and not (args.control/'window.png').exists():
        from run012_capture import capture
        app.update_idletasks();capture(hwnd,args.control/'window.png')

original=gui_app.AbqJobPilotApp
ticks=[0]
def construct(**kw):
    global app,hwnd
    assert kw['attachment_mode'] is True and kw['execution_connection'] is None
    app=original(**kw,on_execution_view=observe)
    app.update_idletasks()
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.GetAncestor.argtypes=[ctypes.c_void_p,ctypes.c_uint];api.GetAncestor.restype=ctypes.c_void_p
    hwnd=api.GetAncestor(app.winfo_id(),2)
    write('identity.json',{'process':current_process_identity(),'hwnd':hwnd,'normal_main':True})
    def tick():
        ticks[0]+=1
        for source in sorted(args.control.glob('action_*.json')):
            action=json.loads(source.read_text(encoding='utf-8'));source.unlink()
            view=app.execution_view
            if action['operation']=='project':
                gui_app.filedialog.askdirectory=lambda **kw:action['project']
                view.choose_button.invoke()
            elif action['operation']=='select':
                view.navigate('runs');view.run_tree.selection_set(action['run_id']);view.run_tree.event_generate('<<TreeviewSelect>>')
            elif action['operation']=='reconnect':view.reconnect()
            elif action['operation']=='older':view.older_button.invoke()
            write('ack_'+action['action_id']+'.json',{'operation':action['operation'],
                  'selection_generation':view.lifecycle_generation})
        app.after(50,tick)
    app.after(50,tick)
    return app
gui_app.AbqJobPilotApp=construct
sys.argv=[str(Path(run_gui.__file__))]
run_gui.main()
for reader in app.execution_view.readers:reader.thread.join(5);assert not reader.thread.is_alive()
write('exit.json',{'mainloop_returned':True,'reader_joined':True,'heartbeat_ticks':ticks[0],
      'no_legacy_import':'abqjobpilot.config' not in sys.modules,'normal_main':True})
