"""Explicit TEST_ONLY operator entries; GUI is connect-only and submit is public IPC.

No real Backend, system service, task scheduler, breakaway or process-name cleanup.
"""
import argparse
from contextlib import closing
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import uuid

SOURCE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE))
PYTHON = Path(r'D:\XianLab\envs\LangChainEnv\Scripts\python.exe')
POINTER = SOURCE / 'docs/agent_first/run_012/LOCAL_DEMO.json'
KEY = 'dev-gui-demo-request-1'


def read(path):
    with path.open('rb') as f: raw = f.read(65537)
    if len(raw) > 65536: raise ValueError('Material exceeds bound')
    return json.loads(raw)


def write(path, value):
    from abqjobpilot.execution.models import canonical_json
    with path.open('x', encoding='utf-8') as f:
        f.write(canonical_json(value)); f.flush(); os.fsync(f.fileno())


def prepare(root, *, managed_scope=False):
    from abqjobpilot.execution import ConfigSnapshot, ExecutionService, ExperimentStore, JobSpec, create_experiment
    from abqjobpilot.execution.models import CONTRACT, RESOURCES, now
    from abqjobpilot.execution.process_backend import ProcessFixtureConfig
    from abqjobpilot.execution.test_authority import issue_process_execution
    root.mkdir(exist_ok=False)
    for name in ('private','session','control','logs','non_repository_cwd'): (root/name).mkdir()
    write(root/'recent-fixture.json', {'untouched':True})
    source = root/'input.txt'; source.write_text('Dev GUI fixed TEST_ONLY process',encoding='utf-8')
    ctx = create_experiment(root,root/'project')
    config = replace(ProcessFixtureConfig.current(managed_scope=managed_scope),max_seconds=60)
    with closing(ExperimentStore(ctx)) as store:
        service = ExecutionService(ctx,store,client_namespace='dev-gui-demo',process_config=config)
        spec = JobSpec.from_dict({'job_id':'gui_demo','revision':1,'project_id':ctx.project_id,
            'project_instance_id':ctx.project_instance_id,'input_refs':[str(source)],
            'resources':dict(RESOURCES),'metadata':{'label':'TEST_ONLY GUI demo'}})
        plan = service.prepare(ctx,spec,ConfigSnapshot.from_dict({'config_revision':1,'values':{'label':'explicit demo'}}),
                               expires_at=now()+900,process_scenario='result_wait').to_dict()
        grant = issue_process_execution(service,plan['plan_id'],expires_at=now()+900)
        credential = secrets.token_urlsafe(36)
        write(root/'private/bootstrap.json',{'context':ctx.to_dict(),'authority_instance':store._session.authority_instance,
              'credential':credential,'client_namespace':'dev-gui-demo','endpoint_file':str(root/'endpoint.json')})
        write(root/'private/setup.json',{'process_config':asdict(config),'plan_id':plan['plan_id']})
        request = {'contract_version':CONTRACT,'operation':'submit','project_id':ctx.project_id,
            'project_instance_id':ctx.project_instance_id,'job_id':plan['job_id'],'job_revision':plan['job_revision'],
            'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],'grant_id':grant,'idempotency_key':KEY,'retry_of':None}
        offer={'request':request}
        if managed_scope:
            second=service.prepare(ctx,JobSpec.from_dict({**plan['job_spec'],'job_id':'gui_demo_second'}),
                ConfigSnapshot.from_dict({'config_revision':1,'values':{'label':'explicit demo'}}),
                expires_at=now()+900,process_scenario='normal').to_dict()
            second_grant=issue_process_execution(service,second['plan_id'],expires_at=now()+900)
            offer['additional_requests']=[{**request,'job_id':second['job_id'],'plan_id':second['plan_id'],
                'plan_digest':second['plan_digest'],'grant_id':second_grant,'idempotency_key':KEY+'-2'}]
        write(root/'private/offer.json',offer)
    return ctx


def spawn(root, arguments, label):
    # Only this trusted operator launches the fixed owner/client entry. The GUI
    # never calls spawn, prepares a grant or owns the Supervisor's handles.
    env = {'SystemRoot':os.environ['SystemRoot'],'TEMP':str(root),'TMP':str(root),'PYTHONDONTWRITEBYTECODE':'1'}
    with (root/'logs'/f'{label}.stdout.txt').open('xb') as out, (root/'logs'/f'{label}.stderr.txt').open('xb') as err:
        return subprocess.Popen([str(PYTHON),'-B',*arguments],cwd=str(root/'non_repository_cwd'),
                                env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                                shell=False,close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW)


def serve(root):
    from abqjobpilot.execution.supervisor import FakeSupervisor, load_bootstrap
    from abqjobpilot.execution.process_backend import ProcessFixtureConfig
    from abqjobpilot.execution.process_handles import ProcessReference
    from abqjobpilot.execution.models import ExecutionError
    ctx, bootstrap = load_bootstrap(root,root/'private/bootstrap.json')
    setup = read(root/'private/setup.json')
    owner = FakeSupervisor(ctx,bootstrap,process_config=ProcessFixtureConfig(**setup['process_config']))
    write(root/'control/owner-identity.json',owner.endpoint['process'])
    write(root/'private/connection.json',{'endpoint':owner.endpoint,'credential':bootstrap['credential']})
    stopped = threading.Event()
    deadline = time.monotonic()+900
    def commands():
        first_seen = None
        while not stopped.wait(.05):
            if (root/'control/stop.json').exists() or time.monotonic() >= deadline:
                stopped.set(); return
            try: receipt = owner.store.query_receipt(ctx,'dev-gui-demo',KEY)
            except ExecutionError as e:
                if e.code == 'NOT_FOUND': continue
                stopped.set(); return
            # Trusted, fixed test scenario control, never a GUI or ordinary RPC action.
            fixture = Path(ctx.runtime_root)/'process_runs'/receipt['run_id']
            if (fixture/'progress.jsonl').exists():
                first_seen = first_seen or time.monotonic()
                if time.monotonic()-first_seen >= 45 and not (fixture/'release.json').exists():
                    write(fixture/'release.json',{})
    watcher = threading.Thread(target=commands,name='bounded-trusted-demo-control')
    watcher.start()
    try: owner.serve(stopped)
    finally:
        stopped.set(); watcher.join(2)
        # serve joins its fixed worker before returning; it never kills processes.
        # Preserve all public evidence; remove only this operator's private files.
        removed=[]
        for name in ('bootstrap.json','setup.json','offer.json','connection.json'):
            path=root/'private'/name
            if path.exists(): path.unlink(); removed.append(name)
        write(root/'control/cleanup.json',{'owner_serve_returned':True,'private_removed':removed,
               'private_remaining':len(list((root/'private').iterdir())),
               'process_termination_used':False,'reason':'explicit_stop_or_900_second_demo_lifetime'})


def entry(action, root=None, *, managed_scope=False, task=1):
    from abqjobpilot.execution.paths import confined
    publish = root is None
    pointer=SOURCE/'docs/agent_first/run_015/LOCAL_DEMO.json' if managed_scope else POINTER
    if root is None:
        if action == 'start':
            if pointer.exists(): raise ValueError('Existing demo retained. Use View or Stop; no automatic replacement.')
            root = Path(tempfile.gettempdir())/(('AbqJobPilot_Run015_' if managed_scope else 'AbqJobPilot_Run012_')+uuid.uuid4().hex)
        else: root=Path(read(pointer)['root'])
    root=confined(Path(tempfile.gettempdir()),root)
    if action=='start':
        ctx=prepare(root,managed_scope=managed_scope)
        if publish: write(pointer,{'root':str(root),'project_instance_id':ctx.project_instance_id,'request_key':KEY})
        child=spawn(root,[str(Path(__file__).resolve()),'owner','--root',str(root)],'owner')
        from abqjobpilot.execution.process_handles import ProcessReference
        with closing(ProcessReference(child.pid)) as ref: write(root/'control/owner-transport.json',ref.identity)
        return {'status':'OWNER_START_REQUESTED','root':str(root),'task_submitted':False}
    if action=='owner': return serve(root)
    if action=='gui':
        from abqjobpilot.gui_app import AbqJobPilotApp
        if task==2 and not managed_scope:raise ValueError('Second task belongs only to managed demo')
        app=AbqJobPilotApp(execution_connection=root/'private/connection.json',request_key=KEY+('-2' if task==2 else ''))
        app.mainloop()
        return {'status':'VIEW_CLOSED_NO_OWNER_ACTION'}
    if action=='submit':
        from abqjobpilot.execution.client import FakeClient
        connection=read(root/'private/connection.json')
        client=FakeClient(connection['endpoint'],connection['credential'])
        offer=read(root/'private/offer.json');request=offer['request']
        client.inspect_plan(request['plan_id'],request['plan_digest'])
        accepted=client.submit(request)
        if not (root/'session/accepted.json').exists(): write(root/'session/accepted.json',accepted)
        if offer.get('additional_requests'):
            subsequent=[]
            for other in offer['additional_requests']:
                client.inspect_plan(other['plan_id'],other['plan_digest']);subsequent.append(client.submit(other))
            return {'first':accepted,'subsequent':subsequent,'scope':'TEST_ONLY_MANAGED_PYTHON'}
        return accepted
    if action=='stop':
        # Explicit trusted stop, outside the GUI. No RPC stop/cancel or process kill.
        if not (root/'control/stop.json').exists(): write(root/'control/stop.json',{})
        return {'status':'ORDERLY_OWNER_STOP_REQUESTED','running_fixture':'allowed_to_finish_within_fixed_budget'}


def main():
    parser=argparse.ArgumentParser(description='Explicit isolated TEST_ONLY Dev GUI demonstration')
    parser.add_argument('action',choices=['start','submit','gui','stop','owner'])
    parser.add_argument('--root',type=Path,help='Explicit temporary demo root; trusted operator only')
    parser.add_argument('--notice',action='store_true',help='Show a local result message for click entries')
    parser.add_argument('--managed-scope',action='store_true',help='New isolated two-task Windows Job demonstration; TEST_ONLY')
    parser.add_argument('--task',type=int,choices=(1,2),default=1,help='GUI request selection only; never submits')
    args=parser.parse_args()
    try:
        result=entry(args.action,args.root,managed_scope=args.managed_scope,task=args.task)
        if args.notice and args.action!='gui':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,json.dumps(result,ensure_ascii=False,indent=2),'AbqJobPilot TEST_ONLY',0)
        elif sys.stdout: print(json.dumps(result,ensure_ascii=False))
        return 0
    except Exception as exc:
        from abqjobpilot.execution.models import ExecutionError
        message=exc.code if isinstance(exc,ExecutionError) else str(exc)[:200]
        if args.notice:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,message,'AbqJobPilot TEST_ONLY — blocked',16)
        elif sys.stderr: print(message,file=sys.stderr)
        return 1


if __name__=='__main__': raise SystemExit(main())
