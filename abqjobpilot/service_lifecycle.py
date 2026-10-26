"""Explicit product lifecycle for configured, idle local Projects (test execution only).

Discovery is read-only. Start and stop require a separate operator capability.
No task approval, dispatch resume, migration, process kill or
automatic replacement. Same owner.lock serializes every start reservation.
"""
from dataclasses import asdict
import hmac
import os
from pathlib import Path
import secrets
import subprocess
import time

from .execution.models import ExecutionError, canonical_json, digest, fields, identifier, now, require
from .execution.paths import confined
from .service_discovery import discover, project_identity, read_document

from .application_runtime import console_interpreter, validate_runtime

PYTHON=console_interpreter()
PROFILE='product-test-lifecycle-v1'


def write_new(path, value):
    with path.open('x',encoding='utf-8') as out:
        out.write(canonical_json(value));out.flush();os.fsync(out.fileno())


def configure_lifecycle(service, *, process_config=None):
    """Trusted initial provisioning only, including explicit product New.

    Caller must already hold the original initial-store owner lease. This
    registers service operation permission, NOT an execution Grant. Only the
    project-management core invokes this on GUI creation; reads never do.
    """
    store=service.store;ctx=store.context;store._session.lease.check()
    from .execution.lifecycle import require_idle
    with store.read() as c:
        require_idle(c)
        require(dict(c.execute('SELECT key,value FROM meta'))['supervisor_started']=='0'
                and c.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==0,
                'LIFECYCLE_PROVISIONING_CLOSED','Configuration is only allowed before any owner or Run')
    if process_config:
        require(process_config.managed_scope,'LIFECYCLE_SCOPE_UNSUPPORTED','Managed test process profile required')
        process_config.verify(process_config.binding('normal'))
        require(Path(process_config.interpreter)==PYTHON,'HOST_UNCONFIRMED','Fixture must bind the application interpreter')
    from .local_credentials import protected_project, private_directory, private_value
    private=confined(ctx.test_root,Path(ctx.test_root)/'private')
    if protected_project(ctx):private_directory(private)
    else:private.mkdir(exist_ok=True)
    operator=secrets.token_hex(32)
    profile={'format':PROFILE,'context_digest':ctx.context_digest,'authority_instance':store._session.authority_instance,
             'client_namespace':service.client_namespace,'credential':secrets.token_hex(32),
             'operator_digest':digest(operator),'process_config':asdict(process_config) if process_config else None}
    write_new(private/'lifecycle.json',private_value(ctx,profile))
    write_new(private/'operator.json',private_value(ctx,{'format':PROFILE,'context_digest':ctx.context_digest,'operator_token':operator}))
    return {'project':ctx.root,'operator_file':str(private/'operator.json')}


class ServiceLifecycleManager:
    def __init__(self, project, connection_file=None):
        self.context=project_identity(project)
        self.project=Path(self.context.root)
        self.private=confined(self.context.test_root,Path(self.context.test_root)/'private')
        self.connection_file=connection_file

    def _path(self, name):
        return confined(self.context.test_root,self.private/name)

    def _profile(self):
        from .local_credentials import read_private
        value=read_private(self.context,self._path('lifecycle.json'))
        fields(value,('format','context_digest','authority_instance','client_namespace','credential','operator_digest','process_config'))
        require(value['format']==PROFILE and value['context_digest']==self.context.context_digest,
                'PROJECT_IDENTITY_MISMATCH','Lifecycle profile belongs to another instance')
        from .product_standard import read_extension
        extension=read_extension(self,value)
        if extension is not None:value['standard_extension']=extension
        return value

    def _operator(self, path=None):
        profile=self._profile()
        from .local_credentials import read_private
        value=read_private(self.context,confined(self.context.test_root,Path(path) if path else self._path('operator.json'),exists=True))
        fields(value,('format','context_digest','operator_token'))
        require(value['format']==PROFILE and value['context_digest']==self.context.context_digest
                and hmac.compare_digest(digest(value['operator_token']),profile['operator_digest']),
                'LIFECYCLE_PERMISSION_REQUIRED','Separate exact Project operator capability required')
        return value['operator_token']

    def connect(self):
        return discover(self.project,self.connection_file)

    def disconnect(self):
        # Connections are bounded request/response sockets. Nothing owns the service here.
        return {'state':'DISCONNECTED','project_instance_id':self.context.project_instance_id}

    def _current(self):
        path=self._path('lifecycle-current.json')
        if not path.exists():return None
        value=read_document(path)
        fields(value,('start_id','context_digest','profile_digest','recorded_at','requester_host'))
        require(value['context_digest']==self.context.context_digest and value['start_id'].startswith('start_')
                and len(value['start_id'])==38 and value['start_id'][6:].isalnum(),
                'START_UNCONFIRMED','Invalid durable startup reservation')
        return value

    def _stopped(self, current):
        if not current:return None
        path=self._path(current['start_id']+'/stopped.json')
        if not path.exists():return None
        value=read_document(path)
        require(value['start_id']==current['start_id'] and value['context_digest']==self.context.context_digest,
                'START_UNCONFIRMED','Clean-stop marker identity mismatch')
        require(read_document(self.project/'owner.json')['owner_id']==value['receipt']['owner_id'],
                'START_UNCONFIRMED','Owner metadata no longer names the orderly-stopped owner')
        # Marker alone is not authority: verify original committed receipt too.
        from .execution.store import open_existing_read_only
        with open_existing_read_only(self.context).read() as c:
            row=c.execute('SELECT body FROM management_receipts WHERE operation_id=?',(value['receipt']['operation_id'],)).fetchone()
            require(row is not None and row[0]==canonical_json(value['receipt']),
                    'START_UNCONFIRMED','No matching persistent stop receipt')
        return value

    def inspect(self):
        try:
            client,ctx,health=self.connect()
            return {'state':'CONNECTED','project_instance_id':ctx.project_instance_id,'owner_id':client.endpoint['owner_id'],
                    'process':health['process'],'lifecycle_supported':'lifecycle_stop' in health['operations']}
        except ExecutionError as exc:
            try:
                current=self._current()
                if self._stopped(current):return {'state':'NOT_RUNNING','reason':'ORDERLY_STOP_RECORDED'}
                if current:return {'state':'BLOCKED','reason':'START_UNCONFIRMED','start_id':current['start_id']}
                if not (self.project/'owner.json').exists() and not self._path('connection.json').exists():
                    self._profile()
                    from .execution.store import open_existing_read_only
                    with open_existing_read_only(self.context).read() as c:
                        c.execute('SELECT value FROM meta WHERE key=?',('owner_id',)).fetchone()
                    return {'state':'NOT_RUNNING','reason':'EXPLICIT_START_REQUIRED'}
            except (ExecutionError,KeyError,TypeError):pass
            return {'state':'BLOCKED','reason':exc.code}

    def _checkpoint(self, name):
        """Private test injection seam; no configuration or IPC can select it."""

    def start(self, *, operator_file=None, wait_seconds=8):
        require(type(wait_seconds) in (int,float) and 0<=wait_seconds<=10,'INVALID_REQUEST','Bounded startup wait required')
        self._operator(operator_file)
        status=self.inspect()
        if status['state']=='CONNECTED':return {**status,'created':False}
        require(status['state']=='NOT_RUNNING','START_BLOCKED',status.get('reason','Owner status uncertain'))
        require(validate_runtime()==PYTHON,'HOST_UNSUPPORTED','Application interpreter changed')
        from .execution.ownership import LocalOwnerLock
        from .execution.store import open_existing_read_only
        from .execution.lifecycle import require_idle
        from .service_host import observe_host
        lease=LocalOwnerLock(self.context)
        try:
            profile=self._profile();current=self._current()
            # Deployment selection never changes a fixed TEST or real Plan pin.
            if profile['process_config']:
                require(Path(profile['process_config']['interpreter'])==PYTHON,
                        'HOST_UNCONFIRMED','Use the interpreter bound to this fixture Project')
            if profile.get('standard_extension'):
                require(Path(profile['standard_extension']['standard_config']['interpreter'])==PYTHON,
                        'HOST_UNCONFIRMED','Fixed Standard interpreter binding is unchanged')
            if current:
                require(self._stopped(current) is not None,'START_UNCONFIRMED','A startup is reserved; connect or inspect only')
            else:
                require(not (self.project/'owner.json').exists() and not self._path('connection.json').exists(),
                        'START_UNCONFIRMED','Unexplained owner metadata prevents startup')
            with open_existing_read_only(self.context).read() as c:
                extension=profile.get('standard_extension')
                require_idle(c,standard_binding=extension['binding'] if extension else None)
                require(dict(c.execute('SELECT key,value FROM meta'))['authority_instance']==profile['authority_instance'],
                        'GRANT_SCOPE_MISMATCH','Provisioned authority differs')
            host=observe_host()
            start_id=identifier('start');attempt=self._path(start_id);attempt.mkdir()
            intent={'start_id':start_id,'context_digest':self.context.context_digest,'profile_digest':digest(profile),
                    'recorded_at':now(),'requester_host':host}
            write_new(attempt/'intent.json',intent)
            if current:
                temporary=self._path(start_id+'.next.json');write_new(temporary,intent)
                temporary.replace(self._path('lifecycle-current.json'))
            else:write_new(self._path('lifecycle-current.json'),intent)
        finally:lease.close()
        # Reservation survives every failure after this point. Never retry creation.
        self._checkpoint('intent_persisted')
        try:
            with (attempt/'stdout.log').open('xb',buffering=0) as out,(attempt/'stderr.log').open('xb',buffering=0) as err:
                child=subprocess.Popen([str(PYTHON),'-I','-S','-B',str(Path(__file__).with_name('service_owner.py')),
                                        '--project',str(self.project),'--start-id',start_id],
                    stdin=subprocess.DEVNULL,stdout=out,stderr=err,cwd=str(attempt),close_fds=True,
                    shell=False,creationflags=subprocess.CREATE_NO_WINDOW,
                    env={'SystemRoot':os.environ['SystemRoot'],'TEMP':str(attempt),'TMP':str(attempt)})
            # This PID is creation telemetry only; discovery authenticates actual Python identity.
            write_new(attempt/'created.json',{'start_id':start_id,'transport_pid':child.pid,'recorded_at':now()})
            self._checkpoint('created')
        except Exception:
            raise ExecutionError('START_UNCONFIRMED','Startup creation outcome uncertain; inspect existing reservation, do not retry') from None
        deadline=time.monotonic()+wait_seconds
        while time.monotonic()<deadline:
            try:
                client,ctx,health=self.connect()
                require(health.get('lifecycle_start_id')==start_id,'START_UNCONFIRMED','Connected owner is not this startup')
                return {'state':'CONNECTED','owner_id':client.endpoint['owner_id'],'start_id':start_id,'created':True}
            except ExecutionError:time.sleep(.05)
        return {'state':'STARTING','reason':'START_UNCONFIRMED','start_id':start_id,'created':True}

    def stop(self, *, owner_id, operation_key, operator_file=None):
        token=self._operator(operator_file)
        current=self._current();prior=self._stopped(current)
        if prior:
            receipt=prior['receipt']
            require(receipt['owner_id']==owner_id and receipt['operation_key']==operation_key,
                    'IDEMPOTENCY_CONFLICT','Stopped service has a different stop receipt')
            return {'replayed':True,'receipt':receipt}
        client,ctx,health=self.connect()
        require('lifecycle_stop' in health['operations'],'CAPABILITY_UNAVAILABLE','Existing owner cannot be replaced or stopped')
        require(client.endpoint['owner_id']==owner_id,'ENDPOINT_IDENTITY_MISMATCH','Stop must name current owner')
        return client.stop_service(owner_id,operation_key,token)
