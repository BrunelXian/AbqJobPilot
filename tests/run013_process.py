"""Fixed non-Solver test harness. Not a product entry or executable Backend option."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

SOURCE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SOURCE))
root=Path(sys.argv[2]);mode=sys.argv[1]
from abqjobpilot.execution.models import canonical_json
from abqjobpilot.execution.ownership import current_process_identity
def write(path,value):path.write_text(canonical_json(value),encoding='utf-8')

if mode=='worker':
    write(root/'worker.json',current_process_identity())
    plan=json.loads((root/'plan.json').read_text());dat=Path(plan['engineering'])/(plan['job_name']+'.dat')
    sta=dat.with_suffix('.sta');msg=dat.with_suffix('.msg')
    deadline=time.monotonic()+25
    with sta.open('xb',buffering=0) as stream:
        stream.write(b'FIXED PYTHON SUBSTITUTE, NOT ABAQUS\n')
        while not (root/'release-worker').exists() and time.monotonic()<deadline:
            stream.write(b'  1  1  1\n');time.sleep(.1)
        stream.write(b'THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n')
    # Explicit offline sample replay, never represented as physical Abaqus evidence.
    dat.write_bytes((SOURCE/'docs/agent_first/run_011/result_review_001/ORIGINAL_DAT.bin').read_bytes())
    msg.write_text('THE ANALYSIS HAS BEEN COMPLETED')
    raise SystemExit(0)

from abqjobpilot.execution.standard_contract import StandardConfig
from abqjobpilot.execution.supervisor import FakeSupervisor,load_bootstrap
from abqjobpilot.execution import standard_backend as backend
ctx,boot=load_bootstrap(root,root/'bootstrap.json')
StandardConfig.verify=lambda self:None  # Test-only private configuration; real entry has no such flag.
config=StandardConfig(canonical_json({'interpreter':sys.executable,'host_policy':'independent-service-same-windows-session-v1'}))
real_popen=subprocess.Popen
launches=[]
def substitute(call,out,err):
    p=real_popen([sys.executable,'-B',str(Path(__file__).resolve()),'worker',str(root)],
        cwd=root,stdin=subprocess.DEVNULL,stdout=out,stderr=err,shell=False,close_fds=True,creationflags=0x08000000,
        env={'SystemRoot':os.environ['SystemRoot'],'TEMP':str(root),'TMP':str(root),'PYTHONDONTWRITEBYTECODE':'1'})
    launches.append({'pid':p.pid,'scope':'CONTROLLED_PYTHON_SUBSTITUTE','call_count':len(launches)+1})
    write(root/'physical-launches.json',launches);return p
backend._launch=substitute
def prohibited(*a,**k): raise AssertionError('REAL ABAQUS/UNEXPECTED PROCESS FORBIDDEN')
for n in ('Popen','run','call','check_output','check_call'):setattr(subprocess,n,prohibited)
real_clock=time.monotonic
class Clock:
    @staticmethod
    def monotonic():return real_clock()+(400 if (root/'finish-observation').exists() else 0)
    sleep=staticmethod(time.sleep);time_ns=staticmethod(time.time_ns)
backend.time=Clock
owner=FakeSupervisor(ctx,boot,standard_config=config)
write(root/'connection.json',{'endpoint':owner.endpoint,'credential':boot['credential']})
write(root/'owner.json',owner.endpoint['process'])
stopped=threading.Event()
def stop():
    while not stopped.wait(.05):
        if (root/'stop').exists() and owner.store._session.active_dispatches==0:stopped.set()
t=threading.Thread(target=stop);t.start()
try:owner.serve(stopped)
finally:
    stopped.set();t.join()
    for name in ('bootstrap.json','connection.json','offer.json'):
        (root/name).unlink(missing_ok=True)
    write(root/'cleanup.json',{'owner_returned':True,'private_files_removed':True,'abaqus_calls':0})
