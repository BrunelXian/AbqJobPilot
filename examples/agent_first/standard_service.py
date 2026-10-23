"""Explicit operator setup for ONE Standard service acceptance; not a runner.

prepare/check issue no execution permission. authorize is a trusted local operator
operation after separate approval, never a client RPC. submit uses the public
client; all actual dispatch belongs to the existing Supervisor worker.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import uuid

SOURCE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(SOURCE))
MANIFEST=SOURCE/'docs/agent_first/run_013/ACCEPTANCE_MANIFEST.json'
KEY='run013-standard-once'


def read(path):
    with Path(path).open('rb') as f: raw=f.read(262145)
    if len(raw)>262144: raise ValueError('Bound exceeded')
    return json.loads(raw)


def write(path,value):
    from abqjobpilot.execution.standard_backend import write_new
    write_new(Path(path),value)


def package():
    from abqjobpilot.execution.models import digest,require,ProjectContext
    from abqjobpilot.execution.standard_contract import identity,StandardConfig
    value=read(MANIFEST); body=value['body']
    require(digest(body)==value['content_digest'],'PLAN_STALE','Acceptance manifest digest mismatch')
    require(all(identity(v['path'])==v for v in body['materials']),'PLAN_STALE','Acceptance code/material identity changed')
    ctx=ProjectContext(**body['context']); config=StandardConfig(body['standard_config'])
    config.verify()
    return value,ctx,config


def prepare():
    from abqjobpilot.execution import create_experiment,ExperimentStore,ExecutionService
    from abqjobpilot.execution.models import canonical_json,digest,now
    from abqjobpilot.execution.standard_contract import StandardConfig,prepare as fixed_plan,identity,ENTRY,CMD,PYTHON
    if MANIFEST.exists(): raise ValueError('Acceptance package already exists; never replace')
    root=Path(tempfile.gettempdir())/('AbqJobPilot_Run013_'+uuid.uuid4().hex)
    root.mkdir()
    for name in ('engineering/scratch','private','control','logs','session','non_repository_cwd'):
        (root/name).mkdir(parents=True)
    (root/'engineering/axial_bar.inp').write_bytes((SOURCE/'docs/agent_first/run_010/axial_bar.inp').read_bytes())
    # Only explicit previously recorded runtime paths; no installation search/evaluation.
    paths=[v['path'] for v in read(SOURCE/'docs/agent_first/run_010/RUNTIME_STATIC_IDENTITIES.json')
           if v['path'] not in (ENTRY,CMD,PYTHON)]
    config=StandardConfig.fixed(paths)
    ctx=create_experiment(root,root/'project'); job='r013_bar_'+uuid.uuid4().hex[:8]
    with closing(ExperimentStore(ctx)) as store:
        service=ExecutionService(ctx,store,client_namespace='run013-standard',standard_config=config)
        plan=fixed_plan(service,root/'engineering',job,expires_at=now()+30*86400).to_dict()
        write(root/'private/bootstrap.json',{'context':ctx.to_dict(),'authority_instance':store._session.authority_instance,
            'credential':secrets.token_urlsafe(36),'client_namespace':'run013-standard','endpoint_file':str(root/'endpoint.json')})
    paths=list((SOURCE/'abqjobpilot/execution').glob('*.py')) + [SOURCE/'abqjobpilot/execution_gui.py',SOURCE/'abqjobpilot/gui_app.py',
        SOURCE/'abqjobpilot/__init__.py',Path(__file__).resolve(),SOURCE/'examples/agent_first/dev_gui_demo.py',
        SOURCE/'examples/agent_first/standard_client.py',root/'engineering/axial_bar.inp'] + list((SOURCE/'examples/agent_first').glob('R13_*.vbs'))
    body={'schema':'standard-service-acceptance-v1','experiment_id':'run013_'+root.name[-32:],
        'context':ctx.to_dict(),'standard_config':config._json,'plan':plan,'request_key':KEY,
        'authority':'NOT_ISSUED','run_id':'CREATED_ONLY_BY_ACCEPTANCE_TRANSACTION',
        'materials':[identity(p) for p in paths],
        'resources':plan['resources'],'entry':ENTRY,'extra_abaqus_calls':0,
        'stop':'300 seconds ends observation; no terminate/retry; slot remains blocked for unknown membership',
        'host_scope':'same Windows session, independent service; GUI exit not owner exit; no old PowerShell admission inheritance',
        'numerics':{'node2_U1':['0.01','0.000001'],'element1_S11':['1','0.0001'],'node1_RF1':['-1','0.0001']},
        'odb_content_validation':'NOT_RUN','production_migration':False}
    value={'body':body,'content_digest':digest(body)}; write(MANIFEST,value)
    return {'status':'PREPARED_NO_GRANT_NO_RUN','digest':value['content_digest'],'root':str(root),'plan_id':plan['plan_id']}


def main_action(action, approval_source=None):
    # Connect-only viewing/submission/reporting never acquires a store or reads
    # installation configuration. Public IPC remains the authority for Run views.
    if action in ('gui','submit','report'):
        from abqjobpilot.execution.models import digest,require
        value=read(MANIFEST);require(digest(value['body'])==value['content_digest'],'PLAN_STALE','Manifest changed')
        root=Path(value['body']['context']['test_root'])
        if action=='gui':
            from abqjobpilot.gui_app import AbqJobPilotApp
            app=AbqJobPilotApp(execution_connection=root/'private/connection.json',request_key=KEY);app.mainloop()
            return {'status':'GUI_CLOSED_NO_OWNER_ACTION'}
        if action=='submit':
            from standard_client import submit
            return submit(root/'private/connection.json',root/'private/offer.json',root/'session')
        from abqjobpilot.execution.client import FakeClient
        connection=read(root/'private/connection.json');client=FakeClient(connection['endpoint'],connection['credential'])
        receipt=client.receipt(KEY);report=client.diagnose(receipt['run_id'])
        target=root/'session'/('diagnostic_'+uuid.uuid4().hex+'.json')
        client.export_diagnostic(report,export_root=root/'session',target=target)
        return {'status':'HISTORICAL_READ_ONLY_REPORT','path':str(target),'run_id':receipt['run_id']}
    from abqjobpilot.execution import ExperimentStore,ExecutionService
    from abqjobpilot.execution.models import CONTRACT,canonical_json,now,require
    from abqjobpilot.execution.standard_contract import check_plan,issue_execution
    from abqjobpilot.execution.supervisor import load_bootstrap,FakeSupervisor
    from abqjobpilot.execution.client import FakeClient
    from abqjobpilot.execution.store import ReadOnlyStore
    if action=='prepare': return prepare()
    value,ctx,config=package(); body=value['body']; root=Path(ctx.test_root)
    context,bootstrap=load_bootstrap(root,root/'private/bootstrap.json')
    if action in ('check','authorize'):
        # Authorization needs the existing exclusive writer lease; active owner
        # cannot be bypassed. Check uses only readonly paths and no ownership.
        if action=='check':
            store=ReadOnlyStore(ctx)
            class ReadService: pass
            service=ReadService();service.context=ctx
            service._standard_backend=type('Binding',(),{'config':config})()
            check_plan(service,body['plan'])
            return {'status':'MATERIALS_MATCH_NO_EXECUTION','manifest_digest':value['content_digest'],
                    'host_admission':'MUST_BE_CHECKED_IN_ACTUAL_OWNER','grant_issued':False,'abaqus_calls':0}
        require(approval_source is not None,'GRANT_REQUIRED','Separate explicit human authorization source required')
        require(not (root/'private/offer.json').exists(),'GRANT_CONSUMED','Offer already registered; do not repeat')
        from abqjobpilot.execution.store import acquire_initial_preparation_store
        with closing(acquire_initial_preparation_store(ctx,bootstrap['authority_instance'])) as store:
            service=ExecutionService(ctx,store,client_namespace='run013-standard',standard_config=config)
            grant=issue_execution(service,body['plan']['plan_id'],expires_at=min(now()+86400,body['plan']['expires_at']),approval_source=approval_source)
        plan=body['plan']
        request={'contract_version':CONTRACT,'operation':'submit','project_id':ctx.project_id,'project_instance_id':ctx.project_instance_id,
            'job_id':plan['job_id'],'job_revision':1,'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],
            'grant_id':grant['grant_id'],'idempotency_key':KEY,'retry_of':None}
        write(root/'private/offer.json',request)
        return {'status':'EXACT_GRANT_REGISTERED_NOT_SUBMITTED','plan_id':plan['plan_id']}
    if action=='start':
        require((root/'private/offer.json').exists(),'GRANT_REQUIRED','No real execution approval has been registered')
        require(not (root/'endpoint.json').exists(),'OWNER_UNCONFIRMED','Existing endpoint retained; no automatic owner restart')
        from dev_gui_demo import spawn
        child=spawn(root,[str(Path(__file__).resolve()),'owner'],'standard-owner')
        from abqjobpilot.execution.process_handles import ProcessReference
        with closing(ProcessReference(child.pid)) as ref: write(root/'control/owner-transport.json',ref.identity)
        return {'status':'OWNER_START_REQUESTED','submission':'NOT_PERFORMED'}
    if action=='owner':
        owner=FakeSupervisor(ctx,bootstrap,standard_config=config)
        write(root/'private/connection.json',{'endpoint':owner.endpoint,'credential':bootstrap['credential']})
        write(root/'control/owner.json',owner.endpoint['process'])
        stopped=threading.Event()
        def stop_request():
            while not stopped.wait(.1):
                # Keep IPC responsive during observation even after an explicit
                # stop request. Never stop/kill Solver or delete private material.
                if (root/'control/stop.json').exists() and owner.store._session.active_dispatches==0:
                    stopped.set()
        watcher=threading.Thread(target=stop_request);watcher.start()
        try: owner.serve(stopped)
        finally: stopped.set();watcher.join();write(root/'control/owner-stopped.json',{'solver_termination':False,'unresolved_records_preserved':True})
        return {'status':'OWNER_STOPPED_NOT_SOLVER_STOPPED'}
    if action=='stop':
        write(root/'control/stop.json',{'request':'orderly_owner_stop_after_observation'})
        return {'status':'OWNER_STOP_REQUESTED_NO_SOLVER_STOP'}
    raise ValueError('Unsupported operator action')


def main():
    p=argparse.ArgumentParser(description='Fixed Standard service acceptance; default is no-Solver check')
    p.add_argument('action',nargs='?',default='check',choices=['prepare','check','authorize','start','owner','submit','gui','report','stop'])
    p.add_argument('--approval-source',help='Trusted operator only, audit reference to separately granted authorization')
    p.add_argument('--notice',action='store_true')
    args=p.parse_args()
    try: result=main_action(args.action,args.approval_source);code=0
    except Exception as e: result={'status':'BLOCKED','reason':getattr(e,'code',type(e).__name__)};code=1
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.notice and args.action!='gui':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,text,'AbqJobPilot Standard candidate',0 if code==0 else 16)
    elif sys.stdout: print(text)
    return code


if __name__=='__main__': raise SystemExit(main())
