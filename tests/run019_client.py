"""Fixed two-process lifecycle race driver; no execution requests or authority minting."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from abqjobpilot.execution.ownership import current_process_identity
from abqjobpilot.execution.models import canonical_json,ExecutionError
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
project,control=map(Path,sys.argv[1:])
(control/'identity.json').write_text(canonical_json(current_process_identity()),encoding='utf-8')
deadline=time.monotonic()+15
while not (control.parent/'release.json').exists():
    if time.monotonic()>deadline:raise SystemExit(2)
    time.sleep(.01)
try:result=ServiceLifecycleManager(project).start()
except ExecutionError as exc:result={'state':'BLOCKED','reason':exc.code}
(control/'result.json').write_text(canonical_json(result),encoding='utf-8')
