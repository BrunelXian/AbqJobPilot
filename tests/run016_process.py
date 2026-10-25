"""Trusted fixed Python substitution for the managed Standard service tests only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

SOURCE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SOURCE))
root=Path(sys.argv[1])
from abqjobpilot.execution.models import canonical_json
from abqjobpilot.execution.standard_contract import StandardConfig,CMD,ENTRY
from abqjobpilot.execution.supervisor import FakeSupervisor,load_bootstrap
from abqjobpilot.execution.managed_process import ManagedScope
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution import standard_backend

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(canonical_json(v),encoding='utf-8')

ctx,boot=load_bootstrap(root,root/'bootstrap.json')
config=StandardConfig(read(root/'settings.json')['standard_config'])
StandardConfig.verify=lambda self:None # explicitly injected test configuration, not exposed to product CLI
plans=read(root/'plans.json');original=ManagedScope.create_standard;resources=[];launches=[]
def substitute(scope,call,out,err):
    assert call['application']==CMD and ENTRY in call['command_line']
    index=next(i for i,p in enumerate(plans) if p['engineering']==call['cwd'])
    control=root/('case_'+str(index));control.mkdir(exist_ok=True)
    write(control/'plan.json',plans[index])
    fixed=[sys.executable,'-B',str(SOURCE/'tests/run013_process.py'),'worker',str(control)]
    test_call={'application':sys.executable,'command_line':subprocess.list2cmdline(fixed),
        'cwd':str(control),'start_not_after':call['start_not_after'],
        'environment':{'SystemRoot':os.environ['SystemRoot'],'TEMP':str(root),'TMP':str(root),'PYTHONDONTWRITEBYTECODE':'1'}}
    child=original(scope,test_call,out,err);resources.append((scope,child))
    ref=ProcessReference(child.pid)
    try:launches.append({'plan_id':plans[index]['plan_id'],'identity':ref.identity,'scope_id':scope.scope_id,
        'source':'ACTUAL_NATIVE_JOB_LIST_PYTHON_SUBSTITUTE','at_ns':time.time_ns()})
    finally:ref.close()
    write(root/'physical-launches.json',launches)
    return child
ManagedScope.create_standard=substitute
def prohibit(*a,**k):raise AssertionError('No real Abaqus or unmanaged fallback allowed')
standard_backend._launch=prohibit
for name in ('Popen','run','call','check_call','check_output'):setattr(subprocess,name,prohibit)
def guard(event,args):
    if event=='abqjobpilot.managed_standard_create':
        application,command,cwd=args
        assert application==sys.executable and str(SOURCE/'tests/run013_process.py') in command
        assert Path(cwd).is_relative_to(root) and ENTRY not in command
sys.addaudithook(guard)
owner=FakeSupervisor(ctx,boot,standard_config=config)
write(root/'connection.json',{'endpoint':owner.endpoint,'credential':boot['credential']})
stopped=threading.Event()
def stop():
    while not stopped.wait(.05):
        if (root/'stop').exists() and owner.store._session.active_dispatches==0:stopped.set()
thread=threading.Thread(target=stop);thread.start()
try:owner.serve(stopped)
finally:
    stopped.set();thread.join()
    write(root/'cleanup.json',{'abaqus_calls':0,'owner_returned':True,
        'native_handles':[{'scope_id':s.scope_id,'job_closed':s.handle is None,'root_closed':p.handle is None} for s,p in resources]})
