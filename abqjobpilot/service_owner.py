"""Fixed TEST_ONLY product host. Explicit start reservation; no generic commands."""
import argparse
from pathlib import Path
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    from abqjobpilot.service_lifecycle import ServiceLifecycleManager, write_new
    from abqjobpilot.service_host import observe_host
    from abqjobpilot.execution.models import digest, require, now
    from abqjobpilot.execution.lifecycle import LifecycleControl
    from abqjobpilot.execution.process_backend import ProcessFixtureConfig
    from abqjobpilot.execution.supervisor import FakeSupervisor
    parser=argparse.ArgumentParser(description='Explicit provisioned TEST_ONLY Supervisor host')
    parser.add_argument('--project',required=True);parser.add_argument('--start-id',required=True)
    args=parser.parse_args()
    manager=ServiceLifecycleManager(args.project);intent=manager._current();profile=manager._profile()
    require(intent and intent['start_id']==args.start_id and intent['profile_digest']==digest(profile),
            'START_UNCONFIRMED','Fixed reservation changed')
    attempt=manager._path(intent['start_id'])
    # No lease or execution writes before host, profile and fixed backend checks.
    host=observe_host(disk_output=True)
    config=ProcessFixtureConfig(**profile['process_config']) if profile['process_config'] else None
    if config:
        require(config.managed_scope,'LIFECYCLE_SCOPE_UNSUPPORTED','Managed fixture only')
        config.verify(config.binding('normal'))
    extension=profile.get('standard_extension');standard=None
    if extension:
        from abqjobpilot.execution.standard_contract import StandardConfig
        from abqjobpilot.execution.models import canonical_json
        standard=StandardConfig(canonical_json(extension['standard_config']));standard.verify()
    lifecycle=LifecycleControl(profile['operator_digest'],intent['start_id'],product_host=True,
                               standard_binding=extension['binding'] if extension else None)
    bootstrap={k:profile[k] for k in ('authority_instance','credential','client_namespace')}
    bootstrap['endpoint_file']=str(attempt/'endpoint.json')
    supervisor=FakeSupervisor(manager.context,bootstrap,process_config=config,lifecycle=lifecycle,standard_config=standard)
    try:
        write_new(attempt/'host.json',host)
        connection=manager._path('connection.json');tmp=attempt/'connection.next.json'
        from abqjobpilot.local_credentials import private_value
        write_new(tmp,private_value(manager.context,{'endpoint':supervisor.endpoint,'credential':profile['credential']}));tmp.replace(connection)
        write_new(attempt/'ready.json',{'owner_id':supervisor.endpoint['owner_id'],'start_id':intent['start_id'],
                                     'recorded_at':now(),'process':host['process']})
        supervisor.serve()
    finally:
        if not supervisor.store._session.closed:supervisor.store.close()
    if lifecycle.stop_requested.is_set() and lifecycle.receipt:
        write_new(attempt/'stopped.json',{'start_id':intent['start_id'],'context_digest':manager.context.context_digest,
                                        'receipt':lifecycle.receipt,'recorded_at':now()})


if __name__=='__main__':
    # Fixed public errors only; never emit private bootstrap objects or traceback.
    try:main()
    except Exception as exc:
        from abqjobpilot.execution.models import ExecutionError
        print(exc.code if isinstance(exc,ExecutionError) else 'SERVICE_HOST_FAILED',file=sys.stderr)
        sys.exit(2)
