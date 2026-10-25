"""R14 trusted test-only extension of the R13 fixed Python owner harness.

All creation still goes through run013_process's fixed substitute + global trap.
No product request selects these seams or supplies callable code.
"""
import json
from pathlib import Path
import runpy
import sys
import threading
import time

SOURCE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SOURCE))
root=Path(sys.argv[2])
from abqjobpilot.execution.supervisor import FakeSupervisor
from abqjobpilot.execution.models import canonical_json,now
from abqjobpilot.execution import closeout, supervisor


class HarnessOwner(FakeSupervisor):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.control_thread=threading.Thread(target=self.control)
        self.control_thread.start()
        def checkpoint(name):
            if name=='management:before_commit' and (root/'crash-before-commit').exists():
                (root/'crash-ready.json').write_text(canonical_json({'phase':name,'owner':self.endpoint['process']}))
                # Deterministic real crash window. No normal cleanup is simulated.
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:time.sleep(.02)
                raise OSError('test controller did not terminate owner')
        self.store._checkpoint=checkpoint

    def control(self):
        while not self._stop.wait(.02):
            marker=root/'approve-test.json'
            if marker.exists() and not (root/'management-request.json').exists():
                try:
                    request=json.loads(marker.read_text())
                    preview=self.service.preview_closeout(self.context,request['run_id'])
                    request=closeout.issue(self.service,preview,request['action'],reason='isolated R14 test only',
                        approval_source='TRUSTED_TEST_HARNESS_NOT_REAL_APPROVAL',expires_at=now()+60)
                    (root/'management-request.json').write_text(canonical_json(request))
                except Exception as exc:
                    (root/'approval-error.json').write_text(canonical_json({'error':type(exc).__name__,'code':getattr(exc,'code','UNKNOWN')}))
                    return

    def _checkpoint(self,name):
        if name=='management:before_response' and (root/'drop-response').exists():
            (root/'drop-response').unlink()
            raise EOFError('test response lost after durable commit')

    def serve(self,*a,**kw):
        try:return super().serve(*a,**kw)
        finally:
            self._stop.set();self.control_thread.join()

supervisor.FakeSupervisor=HarnessOwner
runpy.run_path(str(SOURCE/'tests/run013_process.py'),run_name='__main__')
