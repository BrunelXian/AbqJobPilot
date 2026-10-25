"""Thin fixed-Standard public client. No authority, owner, store or process APIs."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.models import require,canonical_json


def read(path):
    with path.open('rb') as f: raw=f.read(65537)
    require(len(raw)<=65536,'LIMIT_EXCEEDED','Private handoff exceeds bound')
    return json.loads(raw)


def submit(connection,offer,session):
    data=read(connection);client=FakeClient(data['endpoint'],data['credential']);request=read(offer)
    plan=client.inspect_plan(request['plan_id'],request['plan_digest'])
    require(plan['backend_id']=='abaqus-standard-axial-2024-v1' and
            plan['project_instance_id']==data['endpoint']['project_instance_id'],
            'PROJECT_IDENTITY_MISMATCH','Public fixed plan differs')
    receipt=client.submit(request)
    # Public session never contains execution or IPC credentials.
    target=session/'receipt.json'
    if target.exists(): require(read(target)['receipt']==receipt['receipt'],'STATE_CONFLICT','Saved receipt differs')
    else:
        with target.open('x',encoding='utf-8') as f:f.write(canonical_json(receipt))
    return receipt


def main():
    p=argparse.ArgumentParser(description='Submit only an operator-provisioned fixed Standard Plan')
    for name in ('connection','offer','session'):p.add_argument('--'+name,required=True,type=Path)
    args=p.parse_args()
    try: print(canonical_json(submit(args.connection,args.offer,args.session)));return 0
    except Exception as exc:
        print(canonical_json({'status':'NOT_CONFIRMED','reason':getattr(exc,'code','CLIENT_IO_FAILED'),
            'next_step':'Query original key; never infer no-start or retry with a new key'}));return 1


if __name__=='__main__':raise SystemExit(main())
