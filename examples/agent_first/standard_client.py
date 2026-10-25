"""Thin fixed-Standard public client. No authority, owner, store or process APIs."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.models import require,canonical_json


def read(path):
    with path.open('rb') as f: raw=f.read(65537)
    require(len(raw)<=65536,'LIMIT_EXCEEDED','Private handoff exceeds bound')
    return json.loads(raw)


def submit(connection,offer,session):
    data=read(connection);client=FakeClient(data['endpoint'],data['credential']);request=read(offer)
    return submit_known(client,data,request,session)


def submit_known(client,data,request,session):
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


def run_pair(connection,offer,session):
    """Ordinary client sequencing; the server independently enforces every gate.

    No reconnect/retry loop after an IPC failure. An accepted B is persistent:
    communication loss is NOT a cancellation or proof of no launch.
    """
    data=read(connection);client=FakeClient(data['endpoint'],data['credential']);requests=read(offer)['requests']
    require(len(requests)==2,'INVALID_REQUEST','Exact A/B handoff required')
    for index,request in enumerate(requests):
        plan=client.inspect_plan(request['plan_id'],request['plan_digest'])
        require(plan.get('standard_sequence',{}).get('position')=='AB'[index], 'PLAN_STALE','Expected fixed pair position')
    a_dir=session/'A';b_dir=session/'B';a_dir.mkdir(exist_ok=True);b_dir.mkdir(exist_ok=True)
    a=submit_known(client,data,requests[0],a_dir)['receipt'];deadline=a['accepted_at']+630
    while True:
        run=client.run(a['run_id'])
        if run['execution'] in ('FINISHED','BLOCKED'):break
        if time.time()>=a['accepted_at']+330:
            return {'status':'A_WAIT_ENDED_B_NOT_SUBMITTED','run_id':a['run_id'],'solver_stop':False}
        time.sleep(.2)
    require(time.time()<a['accepted_at']+330 and run.get('managed_completion')=='COMMITTED_EMPTY_SCOPE'
            and run['execution']=='FINISHED' and run.get('solver_conclusion')=='COMPLETED_TEXT_EVIDENCE'
            and run.get('numerical_validation')=='PRIMARY_THREE_PASS' and run.get('backend_outcome')=='COMPLETED',
            'PREDECESSOR_NOT_QUALIFIED','B not submitted; inspect original A and dispatch gate')
    b=submit_known(client,data,requests[1],b_dir)['receipt']
    while time.time()<deadline:
        current=client.run(b['run_id'])
        if current['execution'] in ('FINISHED','BLOCKED'):
            return {'status':'PAIR_OBSERVED','a_run':a['run_id'],'b_run':b['run_id'],
                'b_execution':current['execution'],'b_managed_completion':current.get('managed_completion'),
                'b_solver':current['solver_conclusion'],'b_numerical':current.get('numerical_validation')}
        time.sleep(.2)
    return {'status':'B_OBSERVATION_ENDED_NOT_PROCESS_STOPPED','a_run':a['run_id'],'b_run':b['run_id']}


def main():
    p=argparse.ArgumentParser(description='Submit only an operator-provisioned fixed Standard Plan')
    for name in ('connection','offer','session'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--pair',action='store_true')
    args=p.parse_args()
    try: print(canonical_json((run_pair if args.pair else submit)(args.connection,args.offer,args.session)));return 0
    except Exception as exc:
        print(canonical_json({'status':'NOT_CONFIRMED','reason':getattr(exc,'code','CLIENT_IO_FAILED'),
            'next_step':'Query original key; never infer no-start or retry with a new key'}));return 1


if __name__=='__main__':raise SystemExit(main())
