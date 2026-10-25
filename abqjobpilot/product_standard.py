"""Trusted local preparation/operator facade for one fixed product Standard Plan.

Preparation creates no Grant, Run, service or dispatch permission. Operator
methods require a separately protected capability, not the IPC/lifecycle token.
There are deliberately no GUI/CLI/MCP automatic approval paths.
"""
from pathlib import Path
import secrets

from .execution.models import canonical_json, digest, fields, require
from .execution.product_standard import ProductStandardControl
from .local_credentials import read_private, private_value
from .service_lifecycle import ServiceLifecycleManager, write_new

FORMAT = 'product-fixed-standard-profile-v1'


def read_extension(manager, base):
    path = manager._path('standard-profile.json')
    if not path.exists(): return None
    value = read_private(manager.context, path)
    fields(value, ('format', 'context_digest', 'base_profile_digest', 'standard_config', 'binding'))
    require(value['format'] == FORMAT and value['context_digest'] == manager.context.context_digest
            and value['base_profile_digest'] == digest(base),
            'PROJECT_IDENTITY_MISMATCH', 'Fixed Standard profile belongs to another product configuration')
    require(base['process_config'] is None, 'LIFECYCLE_SCOPE_UNSUPPORTED', 'No mixed test/real profile')
    ProductStandardControl(value['binding'])
    from .execution.standard_contract import StandardConfig
    config = StandardConfig(canonical_json(value['standard_config']))
    config.verify()
    require(bool(config.value().get('process_management')), 'PLAN_STALE', 'Managed product configuration required')
    return value


def prepare_product(project, engineering, job_name, config, *, expires_at):
    """Explicit trusted initial lease only, before any service/Run/Grant.

    Partial preparation fails closed: a Plan without the protected profile is
    refused by the unchanged TEST_ONLY lifecycle. Reads never repair it.
    """
    from .product_project import open_project
    from .execution.store import acquire_initial_preparation_store
    from .execution.service import ExecutionService
    from .execution.lifecycle import require_idle
    from .execution.standard_contract import prepare, StandardConfig
    open_project(project)
    manager = ServiceLifecycleManager(project); base = manager._profile()
    require('standard_extension' not in base and base['process_config'] is None,
            'LIFECYCLE_PROVISIONING_CLOSED', 'Initial empty product configuration required')
    require(type(config) is StandardConfig, 'INVALID_REQUEST', 'Fixed trusted Standard configuration required')
    config.verify()
    store = acquire_initial_preparation_store(manager.context, base['authority_instance'])
    try:
        with store.read() as conn:
            require_idle(conn)
            require(conn.execute('SELECT COUNT(*) FROM plans').fetchone()[0] == 0 and
                    conn.execute('SELECT COUNT(*) FROM grants').fetchone()[0] == 0 and
                    conn.execute('SELECT state FROM dispatch_gate WHERE id=1').fetchone()[0] == 'PAUSED',
                    'LIFECYCLE_PROVISIONING_CLOSED', 'Empty PAUSED Project required')
        service = ExecutionService(manager.context, store, client_namespace=base['client_namespace'], standard_config=config)
        plan = prepare(service, engineering, job_name, expires_at=expires_at, product_single=True).to_dict()
        token = secrets.token_hex(32)
        binding = {k: plan[k] for k in ('plan_id', 'plan_digest')}
        binding['operator_digest'] = digest(token)
        value = {'format': FORMAT, 'context_digest': manager.context.context_digest,
                 'base_profile_digest': digest(base), 'standard_config': config.value(), 'binding': binding}
        write_new(manager._path('standard-operator.json'), private_value(manager.context,
            {'format': FORMAT, 'context_digest': manager.context.context_digest, 'operator_token': token}))
        write_new(manager._path('standard-profile.json'), private_value(manager.context, value))
        return plan
    finally: store.close()


class StandardOperator:
    """Explicit trusted operator, calls the SAME public IPC and active owner.

    Capability retrieval requires the private current-user DPAPI file. Holding
    an ordinary FakeClient alone never provides this capability.
    """
    def __init__(self, project):
        self.manager = ServiceLifecycleManager(project)

    def request(self, action, arguments, *, operation_key, owner_id=None):
        manager = self.manager; profile = manager._profile()
        require('standard_extension' in profile, 'CAPABILITY_UNAVAILABLE', 'No fixed product Standard preparation')
        secret = read_private(manager.context, manager._path('standard-operator.json'))
        fields(secret, ('format', 'context_digest', 'operator_token'))
        require(secret['format'] == FORMAT and secret['context_digest'] == manager.context.context_digest,
                'REAL_OPERATOR_REQUIRED', 'Wrong Project operator capability')
        client, _, _ = manager.connect()
        request = {'action': action, 'owner_id': owner_id or client.endpoint['owner_id'],
            'operation_key': operation_key, 'operator_token': secret['operator_token'], 'arguments': arguments}
        return client.call('product_standard_control', {'request': request})


def inspect_preparation(project):
    """Bounded read-only fixed Plan preflight; no owner acquisition or launch."""
    from types import SimpleNamespace
    from .execution.store import open_existing_read_only, document
    from .execution.standard_contract import StandardConfig, check_plan
    manager=ServiceLifecycleManager(project);profile=manager._profile()
    extension=profile.get('standard_extension')
    require(extension is not None,'CAPABILITY_UNAVAILABLE','No fixed product Standard preparation')
    store=open_existing_read_only(manager.context)
    with store.read() as conn:
        plan=document(conn,'plans','plan_id',extension['binding']['plan_id'])
        counts={t:conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]
                for t in ('plans','grants','runs','receipts','consumption')}
        started=dict(conn.execute('SELECT key,value FROM meta'))['supervisor_started']
    ProductStandardControl(extension['binding']).check_plan(plan)
    reader=SimpleNamespace(context=manager.context,store=store,
        _standard_backend=SimpleNamespace(config=StandardConfig(canonical_json(extension['standard_config']))))
    check_plan(reader,plan)
    return {'plan':plan,'counts':counts,'gate':store.gate(),'supervisor_started':started,
            'scope':'READ_ONLY_PRELAUNCH_NOT_AUTHORIZATION'}
