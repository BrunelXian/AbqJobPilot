"""Explicit isolated TEST_ONLY setup + public lifecycle/client examples.

prepare is a trusted developer provisioning step; start/submit/stop are separate.
No arguments/help/import creates a Project, service or task. No real Backend.
"""
import argparse
from contextlib import closing
from pathlib import Path
import sys

SOURCE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(SOURCE))


def prepare(root):
    from abqjobpilot.execution import create_experiment,ExperimentStore,ExecutionService,JobSpec,ConfigSnapshot
    from abqjobpilot.execution.models import RESOURCES,CONTRACT,now
    from abqjobpilot.execution.process_backend import ProcessFixtureConfig
    from abqjobpilot.execution.paths import local_path,no_reparse
    from abqjobpilot.execution.test_authority import issue_process_execution
    from abqjobpilot.service_lifecycle import configure_lifecycle,write_new
    root=local_path(root);no_reparse(root);root.mkdir(exist_ok=False)
    (root/'recent-fixture.json').write_text('{"untouched":true}',encoding='utf-8')
    source=root/'input.txt';source.write_text('Explicit product lifecycle TEST_ONLY input',encoding='utf-8')
    ctx=create_experiment(root,root/'project');config=ProcessFixtureConfig.current(managed_scope=True)
    with closing(ExperimentStore(ctx)) as store:
        service=ExecutionService(ctx,store,process_config=config,client_namespace='product-lifecycle-demo')
        spec=JobSpec.from_dict({'job_id':'lifecycle_test','revision':1,'project_id':ctx.project_id,
            'project_instance_id':ctx.project_instance_id,'input_refs':[str(source)],'resources':dict(RESOURCES),
            'metadata':{'label':'TEST_ONLY product lifecycle'}})
        plan=service.prepare(ctx,spec,ConfigSnapshot.from_dict({'config_revision':1,'values':{'label':'test'}}),
                             expires_at=now()+1800,process_scenario='normal').to_dict()
        grant=issue_process_execution(service,plan['plan_id'],expires_at=now()+1800)
        configure_lifecycle(service,process_config=config)
        write_new(root/'private'/'offer.json',{'contract_version':CONTRACT,'operation':'submit',
            'project_id':ctx.project_id,'project_instance_id':ctx.project_instance_id,
            'job_id':plan['job_id'],'job_revision':plan['job_revision'],'plan_id':plan['plan_id'],
            'plan_digest':plan['plan_digest'],'grant_id':grant,'idempotency_key':'lifecycle-demo-one','retry_of':None})
    return {'project':ctx.root,'scope':'TEST_ONLY','service_started':False,'task_submitted':False}


def main():
    from abqjobpilot.service_lifecycle import ServiceLifecycleManager
    from abqjobpilot.service_discovery import read_document
    from abqjobpilot.execution.models import canonical_json,ExecutionError
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['prepare','inspect','start','submit','stop'])
    parser.add_argument('--root',required=True,type=Path,help='Explicit NEW isolated instance root for prepare')
    parser.add_argument('--owner',help='Exact authenticated owner required by stop')
    args=parser.parse_args()
    try:
        if args.operation=='prepare':result=prepare(args.root)
        else:
            manager=ServiceLifecycleManager(args.root/'project')
            if args.operation=='inspect':result=manager.inspect()
            elif args.operation=='start':result=manager.start()
            elif args.operation=='submit':
                client,_,_=manager.connect();result=client.submit(read_document(args.root/'private'/'offer.json'))
            else:
                if not args.owner:parser.error('--owner is required for explicit stop')
                result=manager.stop(owner_id=args.owner,operation_key='operator-stop-'+args.owner)
        print(canonical_json(result))
    except ExecutionError as exc:
        print(canonical_json({'error':exc.code,'state':'BLOCKED'}));return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
