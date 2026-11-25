"""Trusted local preparation/operator facade for one fixed product Standard Plan.

Preparation creates no Grant, Run, service or dispatch permission. Operator
methods require a separately protected capability, not the IPC/lifecycle token.
There are deliberately no GUI/CLI/MCP automatic approval paths.
"""
import secrets

from .execution.models import canonical_json, digest, fields, require
from .execution.product_standard import ProductStandardControl
from .execution.rod_local_hil import FORMAT as LOCAL_FORMAT
from .local_credentials import read_private, private_value
from .service_lifecycle import ServiceLifecycleManager, write_new

FORMAT = 'product-fixed-standard-profile-v1'
ROD_FORMAT = 'product-protected-rod-a-only-v1'
HIL_FORMAT = 'product-real-t3d2-hil-v1'


def read_extension(manager, base):
    path = manager._path('standard-profile.json')
    if not path.exists():
        return None
    value = read_private(manager.context, path)
    fields(value, ('format', 'context_digest', 'base_profile_digest', 'standard_config', 'binding'))
    require(value['format'] in (FORMAT, ROD_FORMAT, LOCAL_FORMAT, HIL_FORMAT) and value['context_digest'] == manager.context.context_digest
            and value['base_profile_digest'] == digest(base),
            'PROJECT_IDENTITY_MISMATCH', 'Fixed Standard profile belongs to another product configuration')
    require(base['process_config'] is None, 'LIFECYCLE_SCOPE_UNSUPPORTED', 'No mixed test/real profile')
    require((value['format'] == HIL_FORMAT) == ('hil_digest' in value['binding']),
            'HIL_SCOPE_MISMATCH', 'HIL requires its separate sealed profile')
    ProductStandardControl(value['binding'])
    from .execution.standard_contract import StandardConfig
    config = StandardConfig(canonical_json(value['standard_config']))
    config.verify()
    require(bool(config.value().get('process_management')), 'PLAN_STALE', 'Managed product configuration required')
    if value['format'] == ROD_FORMAT:
        from .execution.rod_authority import protected_context
        from .execution.store import open_existing_read_only, document
        with open_existing_read_only(manager.context).read() as conn:
            plan = document(conn, 'plans', 'plan_id', value['binding']['plan_id'])
        proof = protected_context(manager.context, plan, config)
        require(value['binding'].get('authority_digest') == proof['manifest_digest'],
                'HIL_DEPLOYMENT_UNQUALIFIED', 'Protected profile changed')
    if value['format'] == LOCAL_FORMAT:
        from types import SimpleNamespace
        from .execution.rod_local_hil import qualified
        from .execution.store import open_existing_read_only, document
        with open_existing_read_only(manager.context).read() as conn:
            plan = document(conn, 'plans', 'plan_id', value['binding']['plan_id'])
        qualified(SimpleNamespace(_standard_backend=SimpleNamespace(config=config)), plan, value['binding'])
    return value


def prepare_product(project, engineering, job_name, config, *, expires_at, sanity=None):
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
    manager = ServiceLifecycleManager(project)
    base = manager._profile()
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
        plan = prepare(service, engineering, job_name, expires_at=expires_at, product_single=True, sanity=sanity).to_dict()
        token = secrets.token_hex(32)
        binding = {k: plan[k] for k in ('plan_id', 'plan_digest')}
        binding['operator_digest'] = digest(token)
        format_name = FORMAT
        if 'hil' in plan.get('sanity', {}):
            binding['hil_digest'] = digest(plan['sanity']['hil'])
            format_name = HIL_FORMAT
        value = {'format': format_name, 'context_digest': manager.context.context_digest,
                 'base_profile_digest': digest(base), 'standard_config': config.value(), 'binding': binding}
        write_new(manager._path('standard-operator.json'), private_value(manager.context,
            {'format': format_name, 'context_digest': manager.context.context_digest, 'operator_token': token}))
        write_new(manager._path('standard-profile.json'), private_value(manager.context, value))
        return plan
    finally:
        store.close()


class StandardOperator:
    """Explicit trusted operator, calls the SAME public IPC and active owner.

    Capability retrieval requires the private current-user DPAPI file. Holding
    an ordinary FakeClient alone never provides this capability.
    """
    def __init__(self, project):
        self.manager = ServiceLifecycleManager(project)

    def request(self, action, arguments, *, operation_key, owner_id=None):
        manager = self.manager
        profile = manager._profile()
        require('standard_extension' in profile, 'CAPABILITY_UNAVAILABLE', 'No fixed product Standard preparation')
        secret = read_private(manager.context, manager._path('standard-operator.json'))
        fields(secret, ('format', 'context_digest', 'operator_token'))
        require(secret['format'] == profile['standard_extension']['format']
                and secret['format'] in (FORMAT, ROD_FORMAT, LOCAL_FORMAT, HIL_FORMAT)
                and secret['context_digest'] == manager.context.context_digest,
                'REAL_OPERATOR_REQUIRED', 'Wrong Project operator capability')
        client, _, _ = manager.connect()
        request = {'action': action, 'owner_id': owner_id or client.endpoint['owner_id'],
            'operation_key': operation_key, 'operator_token': secret['operator_token'], 'arguments': arguments}
        return client.call('product_standard_control', {'request': request})


def prepare_rod_a_only(project, config, *, plan_id, plan_digest, expected_contract):
    """Future protected issuer setup, no Grant/Owner/dispatch. Never automatic.

    Administrator-controlled manifest, exact code/runtime closure, effective issuer
    rights and distinct kernel identity must already qualify. Ordinary callers
    cannot provide a qualification callback or create the required manifest here.
    Partial file publication stays closed and is not repaired/retried by this API.
    """
    from .product_rod import RodProduct
    from .execution.rod_authority import protected_context
    from .execution.store import acquire_initial_preparation_store, document
    product = RodProduct(project)
    product.preflight_real(plan_id, plan_digest, config=config, expected_contract=expected_contract)
    manager = ServiceLifecycleManager(project)
    base = manager._profile()
    require('standard_extension' not in base and base['process_config'] is None,
            'LIFECYCLE_PROVISIONING_CLOSED', 'Fresh dynamic provisioning only')
    store = acquire_initial_preparation_store(manager.context, base['authority_instance'])
    try:
        with store.read() as conn:
            plan = document(conn, 'plans', 'plan_id', plan_id)
            require(plan['plan_digest'] == plan_digest, 'PLAN_STALE', 'Exact reviewed Plan required')
            require(dict(conn.execute('SELECT key,value FROM meta'))['supervisor_started'] == '0'
                    and conn.execute('SELECT COUNT(*) FROM plans').fetchone()[0] == 1
                    and all(conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] == 0
                            for table in ('runs', 'grants', 'receipts', 'consumption')),
                    'LIFECYCLE_PROVISIONING_CLOSED', 'Unstarted one-Plan Project required')
        proof = protected_context(manager.context, plan, config)
        token = secrets.token_hex(32)
        binding = {'plan_id': plan_id, 'plan_digest': plan_digest,
                   'operator_digest': digest(token), 'authority_digest': proof['manifest_digest']}
        value = {'format': ROD_FORMAT, 'context_digest': manager.context.context_digest,
                 'base_profile_digest': digest(base), 'standard_config': config.value(), 'binding': binding}
        # Same protected file format and existing lifecycle/Owner path as fixed Standard.
        write_new(manager._path('standard-operator.json'), private_value(manager.context,
            {'format': ROD_FORMAT, 'context_digest': manager.context.context_digest, 'operator_token': token}))
        write_new(manager._path('standard-profile.json'), private_value(manager.context, value))
        return {'schema': 'protected-rod-a-provision-result-v1', 'plan_id': plan_id,
                'plan_digest': plan_digest, 'authority_digest': proof['manifest_digest'],
                'status': 'PROVISIONED_NO_GRANT', 'grant_id': None, 'execution_authorized': False}
    finally:
        store.close()


def review_rod_a_console(project, packet, *, choice, operation_key):
    """Future human-run issuer console adapter. Does not issue or dispatch a Grant.

    Caller UI displays the exact packet and sends APPROVE_EXACT or DENY_TERMINAL.
    Kernel/custody validation is repeated both here and by the original server.
    No free-text subject or purported SID is accepted as identity evidence.
    """
    fields(packet, ('schema', 'plan_id', 'plan_digest', 'scope', 'scope_digest',
                    'nonce', 'not_before', 'expires_at', 'execution_authorized'))
    require(packet['schema'] == 'rod-a-only-application-v1'
            and packet['execution_authorized'] is False and digest(packet['scope']) == packet['scope_digest'],
            'HIL_SCOPE_MISMATCH', 'Exact non-executable A packet required')
    require(choice in ('APPROVE_EXACT', 'DENY_TERMINAL'), 'INVALID_REQUEST', 'Explicit human decision required')
    inspected = inspect_preparation(project)
    from .execution.rod_local_hil import local
    require(not local(inspected['plan']), 'LOCAL_HUMAN_TERMINAL_REQUIRED',
            'Legacy choice adapter cannot approve TRUSTED_LOCAL_HIL')
    from .execution.product_standard import scope
    require(inspected['plan']['plan_id'] == packet['plan_id']
            and inspected['plan']['plan_digest'] == packet['plan_digest']
            and scope(inspected['plan']) == packet['scope'],
            'HIL_SCOPE_MISMATCH', 'Current exact Plan differs from displayed packet')
    return StandardOperator(project).request('review_a', {
        'plan_id': packet['plan_id'], 'plan_digest': packet['plan_digest'],
        'scope_digest': packet['scope_digest'], 'decision': choice, 'nonce': packet['nonce'],
        'not_before': packet['not_before'], 'expires_at': packet['expires_at']}, operation_key=operation_key)


def review_hil_console(project, *, subject, approval_ref, expires_at):
    """Display the exact preflight and record one local human choice."""
    import sys
    from .execution import sanity_hil

    require(sys.stdin.isatty(), 'LOCAL_HUMAN_TERMINAL_REQUIRED', 'Use the trusted interactive terminal')
    plan = inspect_preparation(project)['plan']
    packet = sanity_hil.packet(plan)
    plan_digest = plan['plan_digest']
    independent = sanity_hil.independent_registration(plan)
    odb_action = 'REGISTER_ODB' if independent else 'READ_ODB'
    print(canonical_json({**packet, 'subject': subject, 'approval_ref': approval_ref,
                          'decision_expires_at': expires_at, 'odb_options': ['NO_ODB', odb_action]}))
    identity = {}
    if sanity_hil.external(plan):
        answer = input(f"Type SOLVE {plan_digest} or DENY: ").strip()
        require(answer in (f'SOLVE {plan_digest}', 'DENY'),
                'HIL_NOT_CONFIRMED', 'No exact Solver confirmation')
        allow_odb = False
        register_odb = False
        if answer != 'DENY':
            choice = input(f"Separately type {odb_action} {plan_digest} or NO_ODB: ").strip()
            require(choice in (f'{odb_action} {plan_digest}', 'NO_ODB'),
                    'HIL_NOT_CONFIRMED', 'No exact ODB choice')
            allow_odb = not independent and choice.startswith('READ_ODB ')
            register_odb = independent and choice.startswith('REGISTER_ODB ')
        identity = {'project_id': packet['project_id'], 'project_instance_id': plan['project_instance_id'],
                    'input_sha256': plan['input_manifest'][0]['digest']}
        if independent:
            identity[sanity_hil.REGISTRATION_CHOICE] = register_odb
    else:
        answer = input(f"Type SOLVE {plan_digest}, SOLVE_AND_READ_ODB {plan_digest}, or DENY: ").strip()
        require(answer in (f'SOLVE {plan_digest}', f'SOLVE_AND_READ_ODB {plan_digest}', 'DENY'),
                'HIL_NOT_CONFIRMED', 'No exact terminal confirmation')
        allow_odb = answer.startswith('SOLVE_AND_READ_ODB ')
    return StandardOperator(project).request(sanity_hil.REVIEW, {
        'plan_id': plan['plan_id'], 'plan_digest': plan_digest, 'scope_digest': packet['scope_digest'],
        'decision': 'DENY_TERMINAL' if answer == 'DENY' else 'APPROVE_EXACT',
        'allow_odb': allow_odb, 'subject': subject, **identity,
        'approval_ref': approval_ref, 'expires_at': expires_at,
    }, operation_key=packet['request_key'] + '.review')


def review_historical_odb_console(project, target, *, subject, approval_ref, expires_at):
    """Record a dedicated read-only permission after explicit local human confirmation."""
    import sys
    from .execution import odb_history
    from .sanity_admission import recorded_plan

    require(sys.stdin.isatty() and sys.stdout.isatty(), 'LOCAL_HUMAN_TERMINAL_REQUIRED', 'Use the trusted interactive terminal')
    fields(target, odb_history.TARGET)
    operator = StandardOperator(project)
    plan = recorded_plan(operator.manager)
    key = plan['sanity']['request_key'] + '.historical-odb-review'
    preview = operator.request(odb_history.DESCRIBE, target, operation_key=key)
    require(preview['source_grade'] == 'TRUSTED_SOURCE', preview['source_grade'], 'No verified original ODB registration')
    approval = {'subject': subject, 'approval_ref': approval_ref, 'expires_at': expires_at}
    expected = 'READ_ODB ' + odb_history.approval_digest(preview['scope'], approval)
    print(canonical_json({**preview, **approval, 'solver_authorized': False}))
    answer = input('Type ' + expected + ' or DENY: ').strip()
    require(answer == expected, 'ODB_HUMAN_CONFIRMATION_REQUIRED', 'Read approval was declined or differed')
    return operator.request(odb_history.ISSUE, {**target, **approval, 'confirmation': answer},
                            operation_key=key, owner_id=preview['scope']['owner_id'])


def inspect_preparation(project):
    """Bounded read-only fixed Plan preflight; no owner acquisition or launch."""
    from types import SimpleNamespace
    from .execution.store import open_existing_read_only, document
    from .execution.standard_contract import StandardConfig, check_plan
    manager=ServiceLifecycleManager(project)
    profile=manager._profile()
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
