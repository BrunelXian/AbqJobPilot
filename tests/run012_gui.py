"""Actual Dev GUI process. Tests close it with OS WM_CLOSE, never hide/quit only."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys

parser=argparse.ArgumentParser()
parser.add_argument('--connection',required=True,type=Path)
parser.add_argument('--key',required=True)
parser.add_argument('--control',required=True,type=Path)
args=parser.parse_args()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def guard(event, values):
    if event=='import' and values[0] in {'abqjobpilot.config','abqjobpilot.runner_core','abqjobpilot.gui_legacy',
        'abqjobpilot.execution.store','abqjobpilot.execution.service','abqjobpilot.execution.supervisor',
        'abqjobpilot.execution.test_authority','abqjobpilot.project','abqjobpilot.settings_store'}:
        raise AssertionError('Forbidden GUI capability import: '+values[0])
    if event in {'subprocess.Popen','os.system','sqlite3.connect'}: raise AssertionError('GUI execution/storage trap')
sys.addaudithook(guard)
from abqjobpilot.execution.ownership import current_process_identity
from abqjobpilot.gui_app import AbqJobPilotApp
def write(name,data):
    target=args.control/name; partial=target.with_suffix('.partial')
    partial.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    try: partial.replace(target)
    except PermissionError:
        # Best-effort test telemetry only; next rendered frame retries. Never
        # used as service evidence or to change UI/business behavior.
        partial.unlink()
def observe(value):
    write('view.json',value)
    if value['connected'] and 'WAITING' in value['progress_text'] and not (args.control/'window.png').exists():
        from run012_capture import capture
        app.update_idletasks()
        capture(hwnd,args.control/'window.png')
app=AbqJobPilotApp(execution_connection=args.connection,request_key=args.key,on_execution_view=observe)
app.update_idletasks()
api=ctypes.WinDLL('user32',use_last_error=True)
api.GetAncestor.argtypes=[ctypes.c_void_p,ctypes.c_uint];api.GetAncestor.restype=ctypes.c_void_p
hwnd=api.GetAncestor(app.winfo_id(),2)
write('identity.json',{'process':current_process_identity(),'hwnd':hwnd})
ticks=[0]
def tick():
    ticks[0]+=1
    app.after(50,tick)
app.after(50,tick)
app.mainloop()
app.execution_view.reader.thread.join(5)
assert not app.execution_view.reader.thread.is_alive()
write('exit.json',{'mainloop_returned':True,'reader_joined':True,'heartbeat_ticks':ticks[0],
                   'no_legacy_import': 'abqjobpilot.config' not in sys.modules})
