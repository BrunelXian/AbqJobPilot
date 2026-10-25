"""Opt-in fixed Standard contract. No launch, authority factory or default Runtime."""
from dataclasses import dataclass
from pathlib import Path
import re

from .models import (ExecutionPlan, bytes_digest, canonical_json, digest, identifier,
                     integer, now, require)
from .paths import confined, local_path, no_reparse
from .store import document

BACKEND = 'abaqus-standard-axial-2024-v1'
ACTION = 'launch_fixed_standard_analysis_once'
ENTRY = r'D:\ABAQUS2024\Commands\abq2024.bat'
CMD = r'C:\Windows\System32\cmd.exe'
PYTHON = r'D:\XianLab\envs\LangChainEnv\Scripts\python.exe'
INPUT_DIGEST = 'sha256:e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3'
RESOURCES = {'slots': 1, 'cpus': 1, 'gpus': 0, 'memory_mb': 2048, 'observation_seconds': 300, 'launch_budget': 1}
HOST_POLICY = 'independent-service-same-windows-session-v1'


def identity(path, limit=32*1024*1024):
    path = local_path(path); no_reparse(path)
    with path.open('rb') as f:
        before = path.stat(); raw = f.read(limit+1); after = path.stat()
    require(len(raw) <= limit and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) and len(raw) == before.st_size,
            'PLAN_STALE', 'Pinned file changed or exceeded size limit')
    return {'path': str(path), 'size': len(raw), 'digest': bytes_digest(raw)}


@dataclass(frozen=True)
class StandardConfig:
    """Trusted constructor only. Pins declared installation files, never evaluates them."""
    _json: str

    @classmethod
    def fixed(cls, installation_files, *, managed=False):
        paths = [ENTRY, CMD, PYTHON, *installation_files]
        require(len(paths) == len(set(paths)) and len(paths) <= 32, 'INVALID_REQUEST', 'Bounded explicit installation list required')
        value={'backend_id': BACKEND, 'backend_version': 1,
            'entry': ENTRY, 'cmd': CMD, 'interpreter': PYTHON, 'host_policy': HOST_POLICY,
            'materials': [identity(p) for p in paths]}
        if managed:value['process_management']=management_binding()
        return cls(canonical_json(value))

    def value(self):
        import json
        return json.loads(self._json)

    def verify(self):
        value = self.value()
        require(value['backend_id'] == BACKEND and value['backend_version'] == 1 and
                value['entry'] == ENTRY and value['cmd'] == CMD and value['interpreter'] == PYTHON and
                value['host_policy'] == HOST_POLICY, 'PLAN_STALE', 'Fixed Standard configuration changed')
        require(all(identity(m['path']) == m for m in value['materials']), 'PLAN_STALE', 'Runtime declaration identity changed')
        if 'process_management' in value:
            require(value['process_management']==management_binding(),'PLAN_STALE','Managed creation implementation changed')


def management_binding():
    from .managed_process import POLICY
    return {'policy':POLICY,'stdio':'explicit-file-handle-list-v1',
            'implementation_digest':identity(Path(__file__).with_name('managed_process.py'))['digest']}


def prepare(service, engineering, job_name, *, expires_at, sequence=None, product_single=False):
    """Trusted explicit preparation; not a conversion or execution of an offline preview."""
    context = service.context
    require(service._standard_backend is not None, 'BACKEND_DISABLED', 'Standard capability not configured')
    service._standard_backend.config.verify()
    managed=service._standard_backend.config.value().get('process_management')
    require(not product_single or (managed and sequence is None), 'INVALID_REQUEST', 'Single product Plan requires managed creation')
    pattern = r'r021_bar_[a-f0-9]{8}' if product_single else (r'r016_bar_[ab]_[a-f0-9]{8}' if managed else r'r013_bar_[a-f0-9]{8}')
    require(type(job_name) is str and re.fullmatch(pattern, job_name), 'INVALID_REQUEST', 'Fixed acceptance Job name required')
    root = confined(context.test_root, engineering, exists=True)
    require(not root.is_relative_to(Path(context.root)), 'OUTPUT_SCOPE_VIOLATION', 'External engineering directory required')
    # Windows cmd quoting: reject expansion/metacharacters in all variable paths.
    require(not any(c in str(root) for c in '\"%!?&|<>^\r\n'), 'OUTPUT_SCOPE_VIOLATION', 'Unsupported command path characters')
    source = confined(context.test_root, root/'axial_bar.inp', exists=True)
    data = identity(source, 65536)
    require(data['digest'] == INPUT_DIGEST, 'PLAN_STALE', 'Only the frozen axial model bytes are supported')
    scratch = confined(context.test_root, root/'scratch', exists=True)
    require(scratch.is_dir(), 'OUTPUT_SCOPE_VIOLATION', 'Explicit scratch required')
    integer(expires_at); require(expires_at > now(), 'PLAN_EXPIRED', 'Plan expired')
    job_id = identifier('job')
    body = {'plan_id': identifier('plan'), 'job_id': job_id, 'job_revision': 1,
        'job_spec': {'job_id': job_id, 'revision': 1}, 'project_instance_id': context.project_instance_id,
        'context_digest': context.context_digest, 'backend_id': BACKEND, 'backend_version': 1,
        'action': ACTION, 'phases': ['STANDARD_ANALYSIS'], 'resources': dict(RESOURCES),
        'runtime_binding': service._standard_backend.config.value(), 'input_manifest': [data],
        'engineering': str(root), 'scratch': str(scratch), 'job_name': job_name,
        'output_key': digest({'cwd': str(root).casefold(), 'job': job_name.casefold()}),
        'output_policy': {'overwrite': False, 'reservation': 'exclusive_intent_file_at_dispatch', 'scope': 'same_output_directory_protocol_participants'},
        'validation_policy': 'fixed-2024-axial-dat-v1', 'expires_at': expires_at,
        'canonicalization': 'af-experiment-json-v1', 'plan_schema': 'standard-fixed-plan-v1',
        'environment_policy': 'isolated_home_temp_minimal_windows_v1', 'extra_abaqus_calls': 0,
        'member_completeness_policy': 'UNKNOWN_no_automatic_release', 'host_policy': HOST_POLICY}
    if managed:
        body.update(process_management=managed,standard_sequence=sequence,plan_schema='standard-managed-pair-plan-v1',
                    member_completeness_policy='ROOT_AND_INHERITING_CREATEPROCESS_DESCENDANTS_ONLY')
        if product_single:
            from .product_standard import SCHEMA, POLICY
            body.pop('standard_sequence')
            body.update(plan_schema=SCHEMA, product_dispatch=dict(POLICY))
    body['plan_digest'] = digest(body)
    check_plan(service, body)
    with service.store.transaction('prepare_standard') as conn:
        conn.execute('INSERT INTO jobs VALUES(?,?,?)', (job_id,1,canonical_json(body['job_spec'])))
        conn.execute('INSERT INTO plans VALUES(?,?,?,?)', (body['plan_id'],job_id,1,canonical_json(body)))
    return ExecutionPlan.from_dict(body)


def check_plan(service, plan, *, started=False):
    backend = service._standard_backend
    require(backend is not None, 'BACKEND_DISABLED', 'Standard capability not configured')
    original = dict(plan); claimed = original.pop('plan_digest', None)
    require(claimed == digest(original), 'PLAN_STALE', 'Fixed plan digest mismatch')
    ctx = service.context
    require(plan['context_digest'] == ctx.context_digest and plan['project_instance_id'] == ctx.project_instance_id,
            'PROJECT_IDENTITY_MISMATCH', 'Standard plan context differs')
    require(plan['backend_id'] == BACKEND and plan['backend_version'] == 1 and plan['action'] == ACTION
            and plan['resources'] == RESOURCES and plan['phases'] == ['STANDARD_ANALYSIS']
            and plan['validation_policy'] == 'fixed-2024-axial-dat-v1' and plan['extra_abaqus_calls'] == 0
            and plan['host_policy'] == HOST_POLICY, 'PLAN_STALE', 'Fixed execution policy differs')
    require(plan['expires_at'] > now(), 'PLAN_EXPIRED', 'Fixed plan expired')
    backend.config.verify()
    require(plan['runtime_binding'] == backend.config.value(), 'PLAN_STALE', 'Runtime configuration differs')
    managed=backend.config.value().get('process_management')
    if managed:
        from .standard_sequence import check_shape
        from .product_standard import single, shape
        require(plan.get('process_management')==managed and (single(plan) or plan['plan_schema']=='standard-managed-pair-plan-v1')
                and plan['member_completeness_policy']=='ROOT_AND_INHERITING_CREATEPROCESS_DESCENDANTS_ONLY',
                'PLAN_STALE','Explicit managed Plan required; no fallback')
        shape(plan) if single(plan) else check_shape(plan)
    else:
        require('process_management' not in plan and 'standard_sequence' not in plan,
                'PLAN_STALE','Unmanaged capability cannot dispatch a managed Plan')
    root = confined(ctx.test_root, plan['engineering'], exists=True)
    from .product_standard import single
    pattern = r'r021_bar_[a-f0-9]{8}' if single(plan) else (r'r016_bar_[ab]_[a-f0-9]{8}' if managed else r'r013_bar_[a-f0-9]{8}')
    require(plan['input_manifest'] == [identity(root/'axial_bar.inp',65536)] and
            plan['input_manifest'][0]['digest'] == INPUT_DIGEST and
            plan['scratch'] == str(root/'scratch') and re.fullmatch(pattern,plan['job_name']) and
            plan['output_key'] == digest({'cwd': str(root).casefold(), 'job': plan['job_name'].casefold()}),
            'PLAN_STALE', 'Input, working directory or output changed')
    no_reparse(root/'scratch')
    from .closeout import check_retained_paths
    # During standalone no-Solver checks, the existing read adapter has no Store.
    # Use the same explicit read-only store; no initialization or ownership claim.
    if not hasattr(service,'store'):
        from .store import ReadOnlyStore
        service.store=ReadOnlyStore(ctx)
    check_retained_paths(service,plan)
    require(not (root/'abaqus_v6.env').exists(), 'PLAN_STALE', 'Job environment files are outside the fixed profile')
    require(not any(c in str(root) for c in '\"%!?&|<>^\r\n'), 'OUTPUT_SCOPE_VIOLATION', 'Unsupported command path')
    if not started:
        require(not list(root.glob(plan['job_name']+'.*')) and not list(root.glob('.*.intent.json')),
                'OUTPUT_CONFLICT', 'Output or durable attempt already exists; no retry permitted')
        require(not any((root/'scratch').iterdir()), 'OUTPUT_CONFLICT', 'Scratch must be empty before first launch')


def issue_execution(service, plan_id, *, expires_at, approval_source):
    """Trusted local operator, before owner startup. No RPC mint; no self-reported booleans.

    Same OS user/code access is the trust boundary. Source is an audit reference,
    not cryptographic human authentication. Caller must have explicit approval.
    """
    require(type(approval_source) is str and 1 <= len(approval_source) <= 128, 'GRANT_REQUIRED', 'Explicit authorization source required')
    with service.store.transaction('grant_standard') as conn:
        plan = document(conn,'plans','plan_id',plan_id); check_plan(service,plan)
        from .product_standard import single
        require(not single(plan), 'REAL_OPERATOR_REQUIRED', 'Product approval requires active-owner exact operator control')
        require('standard_sequence' not in plan,'GRANT_SCOPE_MISMATCH','Managed pair requires one exact pair registration')
        grant = _issue(service,conn,plan,expires_at,approval_source)
    return grant


def _issue(service,conn,plan,expires_at,approval_source,sequence_grant=None):
        plan_id=plan['plan_id']
        require(conn.execute('SELECT COUNT(*) FROM grants WHERE plan_id=?',(plan_id,)).fetchone()[0] == 0,
                'GRANT_CONSUMED','A Plan receives at most one real execution approval')
        integer(expires_at); require(now() < expires_at <= plan['expires_at'], 'GRANT_EXPIRED', 'Approval validity outside Plan')
        grant = {'grant_id':identifier('grant'),'issuer':'TrustedStandardOperator','grant_kind':'REAL_FIXED_STANDARD',
            'authority_instance':service.store._session.authority_instance,'project_instance_id':service.context.project_instance_id,
            'context_digest':service.context.context_digest,'plan_id':plan_id,'plan_digest':plan['plan_digest'],
            'allowed_action':ACTION,'output_key':plan['output_key'],'resource_limits':RESOURCES,
            'expires_at':expires_at,'max_runs':1,'approval_source':approval_source}
        if sequence_grant:
            grant.update(process_management=plan['process_management'],standard_sequence=plan['standard_sequence'],
                         sequence_grant=sequence_grant)
        conn.execute('INSERT INTO grants VALUES(?,?,?)',(grant['grant_id'],plan_id,canonical_json(grant)))
        return grant


def check_grant(service, plan, grant, consumed, run_id):
    require(grant is not None, 'GRANT_REQUIRED', 'Registered real fixed execution approval required')
    expected = {'issuer':'TrustedStandardOperator','grant_kind':'REAL_FIXED_STANDARD',
        'authority_instance':service.store._session.authority_instance,'project_instance_id':service.context.project_instance_id,
        'context_digest':service.context.context_digest,'plan_id':plan['plan_id'],'plan_digest':plan['plan_digest'],
        'allowed_action':ACTION,'output_key':plan['output_key'],'resource_limits':RESOURCES,'max_runs':1}
    require(all(type(grant.get(k)) is type(v) and grant[k] == v for k,v in expected.items()),
            'REAL_GRANT_REQUIRED', 'TEST_ONLY or mismatched authority cannot authorize Standard')
    require(grant['expires_at'] > now(), 'GRANT_EXPIRED', 'Real fixed approval expired')
    require(consumed is None or consumed == run_id, 'GRANT_CONSUMED', 'Approval consumed by another Run')
    if 'process_management' in plan:
        from .product_standard import single, scope
        if single(plan):
            require(grant.get('product_scope') == scope(plan) and grant.get('project_id') == service.context.project_id
                    and grant.get('approval_owner') == service.store._session.owner_id,
                    'REAL_GRANT_REQUIRED', 'Exact product approval and current owner required')
        else: require(grant.get('process_management')==plan['process_management'] and
                grant.get('standard_sequence')==plan['standard_sequence'], 'REAL_GRANT_REQUIRED','Managed scope/sequence approval differs')


def inspect(service, plan_id, expected_digest):
    with service.store.read() as conn: plan = document(conn,'plans','plan_id',plan_id)
    require(plan['plan_digest'] == expected_digest, 'PLAN_STALE', 'Expected plan digest differs')
    original = dict(plan); original.pop('plan_digest')
    require(digest(original) == expected_digest, 'PLAN_STALE', 'Stored plan digest differs')
    result={k:plan[k] for k in ('plan_id','plan_digest','backend_id','backend_version','project_instance_id',
        'resources','action','job_name','output_key','validation_policy','host_policy','expires_at')}
    if 'process_management' in plan:
        result.update(process_management=plan['process_management'])
        if 'standard_sequence' in plan:result['standard_sequence']=plan['standard_sequence']
        if 'product_dispatch' in plan:result['product_dispatch']=plan['product_dispatch']
    return result
