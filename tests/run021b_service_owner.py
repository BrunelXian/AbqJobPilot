"""TEST ONLY: run the real product owner main with native creation restricted
to one fixed Python fixture. This file is not an installed/registered profile.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SOURCE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SOURCE))
from abqjobpilot.execution.standard_contract import StandardConfig, CMD, ENTRY
from abqjobpilot.execution.managed_process import ManagedScope
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.models import canonical_json
from abqjobpilot.execution import standard_backend
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution.supervisor import FakeSupervisor

project=Path(sys.argv[sys.argv.index('--project')+1]).parent
control=project/'fixture';control.mkdir(exist_ok=True)
StandardConfig.verify=lambda s:None
native=ManagedScope.create_standard;handles=[]

def substitute(scope,call,out,err):
    assert call['application']==CMD and ENTRY in call['command_line']
    plan=json.loads((project/'test-plan.json').read_text())
    assert call['cwd']==plan['engineering']
    (control/'plan.json').write_text(canonical_json(plan))
    fixed=[sys.executable,'-B',str(SOURCE/'tests/run013_process.py'),'worker',str(control)]
    child=native(scope,{'application':sys.executable,'command_line':subprocess.list2cmdline(fixed),
        'cwd':str(control),'start_not_after':call['start_not_after'],
        'environment':{'SystemRoot':os.environ['SystemRoot'],'TEMP':str(project),'TMP':str(project),'PYTHONDONTWRITEBYTECODE':'1'}},out,err)
    ref=ProcessReference(child.pid)
    try:
        with (control/'physical.jsonl').open('a') as f:
            f.write(canonical_json({'identity':ref.identity,'scope_id':scope.scope_id,'at_ns':time.time_ns(),
                                   'source':'NATIVE_JOB_LIST_FIXED_PYTHON_NOT_ABAQUS'})+'\n')
    finally:ref.close()
    handles.append((scope,child))
    return child

ManagedScope.create_standard=substitute
def deny(*a,**kw):raise AssertionError('Real Abaqus/unmanaged process creation forbidden')
standard_backend._launch=deny
for name in ('Popen','run','call','check_call','check_output'):setattr(subprocess,name,deny)
def audit(event,args):
    if event=='abqjobpilot.managed_standard_create':
        application,command,cwd=args
        assert application==sys.executable and str(SOURCE/'tests/run013_process.py') in command
        assert Path(cwd)==control and ENTRY not in command
sys.addaudithook(audit)
def checkpoint(self,name):
    if name=='product_control:before_response' and (control/'drop-response').exists():
        (control/'drop-response').unlink();raise OSError('test response lost')
FakeSupervisor._checkpoint=checkpoint
from abqjobpilot.execution.store import ExperimentStore
def fault(self,name):
    marker=control/'crash-at'
    if marker.exists() and marker.read_text()==name:
        (control/'crash-reached').write_text(name);os._exit(97)
ExperimentStore._checkpoint=fault
from abqjobpilot.service_owner import main
main()
start_id=sys.argv[sys.argv.index('--start-id')+1]
(control/('cleanup_'+start_id+'.json')).write_text(canonical_json({'abaqus_calls':0,'normal_owner_return':True,
    'start_id':start_id,
    'handles':[{'scope_closed':s.handle is None,'root_closed':p.handle is None} for s,p in handles]}))
