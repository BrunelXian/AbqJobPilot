"""Independent ordinary API consumer. No test helpers, SQL, grants or owner imports."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from abqjobpilot.product_project import open_project
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution.models import canonical_json,ExecutionError

p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--out',required=True,type=Path)
p.add_argument('--offer',type=Path);p.add_argument('--start',action='store_true')
args=p.parse_args()
try:
    project=open_project(args.project);m=ServiceLifecycleManager(args.project)
    result={'project_id':project['project_id'],'initial':m.inspect()}
    if args.start:result['start']=m.start()
    client,ctx,health=m.connect()
    result.update(owner=health['process'],owner_id=client.endpoint['owner_id'],view=client.project_view())
    if args.offer:result['submission']=client.submit(json.loads(args.offer.read_text(encoding='utf-8')))
    result['disconnect']=m.disconnect()
except ExecutionError as exc:result={'error':exc.code}
args.out.write_text(canonical_json(result),encoding='utf-8')
