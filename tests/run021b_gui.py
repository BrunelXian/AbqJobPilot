"""Normal GUI harness, with the service child replaced ONLY in test code."""
from pathlib import Path
import runpy
import subprocess
import sys
SOURCE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SOURCE))
from abqjobpilot.execution.standard_contract import StandardConfig
StandardConfig.verify=lambda s:None
original=subprocess.Popen
def fixed(args,*a,**kw):
    args=list(args)
    expected=str(SOURCE/'abqjobpilot/service_owner.py')
    assert expected in args
    args[args.index(expected)]=str(SOURCE/'tests/run021b_service_owner.py')
    return original(args,*a,**kw)
subprocess.Popen=fixed
runpy.run_path(str(SOURCE/'tests/run020_gui.py'),run_name='__main__')
