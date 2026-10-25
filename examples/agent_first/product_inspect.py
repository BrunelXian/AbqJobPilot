"""Read-only ordinary Python client; explicit Project, no test internals or SQL.

No create/start/stop/approve/submit here. Use the shared APIs for explicit actions.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


def inspect_snapshot(project):
    from abqjobpilot.product_project import open_project
    from abqjobpilot.service_lifecycle import ServiceLifecycleManager
    document=open_project(project);manager=ServiceLifecycleManager(project)
    state=manager.inspect()
    report={'project_id':document['project_id'],'project_instance_id':document['project_instance_id'],
            'display_name':document['display_name'],'service':state}
    if state['state']=='CONNECTED':
        client,_,_=manager.connect()
        report['runs']=client.project_view()
    manager.disconnect()
    return report


def main():
    from abqjobpilot.execution.models import ExecutionError,canonical_json
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project',required=True)
    args=parser.parse_args()
    try:print(canonical_json(inspect_snapshot(args.project)));return 0
    except ExecutionError as exc:print(canonical_json({'error':exc.code}));return 2


if __name__=='__main__':raise SystemExit(main())
