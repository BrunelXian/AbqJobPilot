"""Explicit new Agent-first product Projects; never adopt or migrate a folder.

Public creation is a trusted local filesystem operation, not a task approval.
Publication of agent_project.json is the commit point. Failed creation is kept
recognizably incomplete; open never repairs it. Execution format remains 3.
"""
from pathlib import Path

from .execution.models import ExecutionError, fields, require, now
from .execution.paths import local_path, no_reparse

FORMAT='abqjobpilot-agent-first-project'
MARKER='.agent-first-creation.json'
MANIFEST='agent_project.json'


def validate_product(context):
    from .service_discovery import read_document
    from .local_credentials import host_binding
    root=Path(context.test_root)
    require((root/MANIFEST).is_file(),'PROJECT_INCOMPLETE','Project creation has not committed; no repair')
    value=read_document(root/MANIFEST)
    fields(value,('format','version','display_name','project_id','project_instance_id','context_digest',
                  'store_directory','store_format_version','credential_policy','host_binding','created_at','initial_dispatch'))
    require(value['format']==FORMAT and type(value['version']) is int and value['version']==1
            and value['store_format_version']==3 and value['store_directory']=='project'
            and value['credential_policy']=='windows-user-dpapi-v1' and value['initial_dispatch']=='PAUSED',
            'UNSUPPORTED_FORMAT','Unsupported product Project; no migration')
    require(value['project_id']==context.project_id and value['project_instance_id']==context.project_instance_id
            and value['context_digest']==context.context_digest and Path(context.root)==root/'project',
            'PROJECT_IDENTITY_MISMATCH','Product Project was copied, moved or changed; no automatic rebind')
    require(value['host_binding']==host_binding(),'LOCAL_CREDENTIAL_UNAVAILABLE','Project requires its original local user and host')
    _name(value['display_name'])
    return value


def _name(value):
    require(type(value) is str and 1<=len(value.strip())<=80 and not any(ord(c)<32 for c in value),
            'INVALID_REQUEST','Display name must contain 1..80 printable characters')
    return value.strip()


def create_project(directory, display_name):
    """Create a new empty, PAUSED Project, no Grant/Run/service or engineering copy.

    The parent must exist. All local state stays below the explicit new directory.
    Existing targets (including empty directories) are never reused.
    """
    from .local_credentials import host_binding
    from .service_lifecycle import PYTHON, configure_lifecycle, write_new
    from .execution.store import create_experiment, ExperimentStore
    from .execution.service import ExecutionService
    import sys
    name=_name(display_name)
    root=local_path(directory);no_reparse(root)
    require(root.parent.is_dir(),'NOT_FOUND','Explicit existing parent required')
    require(not root.exists(),'PROJECT_EXISTS','Target already exists; nothing overwritten')
    require(Path(sys.executable).resolve() in (PYTHON,PYTHON.with_name('pythonw.exe')),
            'HOST_UNSUPPORTED','Use registered product Python interpreter')
    binding=host_binding()  # Fail before directory creation on unsupported host.
    try:root.mkdir()
    except FileExistsError:raise ExecutionError('PROJECT_EXISTS','Concurrent creation already reserved target') from None
    root=root.resolve()
    write_new(root/MARKER,{'format':FORMAT,'creation_state':'RESERVED','created_at':now()})
    context=create_experiment(root,root/'project')
    store=ExperimentStore(context)
    try:
        with store.transaction('product_initial_policy') as connection:
            connection.execute("UPDATE dispatch_gate SET state='PAUSED' WHERE id=1")
        configure_lifecycle(ExecutionService(context,store,client_namespace='product-client'))
        manifest={'format':FORMAT,'version':1,'display_name':name,'project_id':context.project_id,
                  'project_instance_id':context.project_instance_id,'context_digest':context.context_digest,
                  'store_directory':'project','store_format_version':3,'credential_policy':'windows-user-dpapi-v1',
                  'host_binding':binding,'created_at':now(),'initial_dispatch':'PAUSED'}
    finally:store.close()
    # Payload and DB are durable before atomic publication. No rename of the
    # instance directory: its existing physical identity is part of the context.
    pending=root/'agent_project.pending.json';write_new(pending,manifest)
    pending.rename(root/MANIFEST)
    return open_project(root)


def open_project(directory):
    """Read-only validate, no migration, credential issuance or service startup."""
    from .service_discovery import project_identity
    from .execution.store import open_existing_read_only
    context=project_identity(directory)
    manifest=validate_product(context)
    with open_existing_read_only(context).read() as connection:
        connection.execute('SELECT run_id FROM slot WHERE id=1').fetchone()
    return manifest


def inspect_project(directory):
    """Public classification without reading legacy databases or default Recent."""
    from .service_discovery import project_identity
    root=local_path(directory);no_reparse(root)
    require(root.is_dir(),'NOT_FOUND','Select an existing directory')
    if (root/MANIFEST).exists() or (root/MARKER).exists():
        try:return {'kind':'AGENT_FIRST_PRODUCT',**open_project(root)}
        except ExecutionError as exc:return {'kind':'UNAVAILABLE','reason':exc.code}
    if (root/'experiment.json').exists():
        try:
            ctx=project_identity(root)
            return {'kind':'AGENT_FIRST_EXPERIMENT','project_id':ctx.project_id,'project_instance_id':ctx.project_instance_id}
        except ExecutionError as exc:return {'kind':'UNAVAILABLE','reason':exc.code}
    if (root/'project.json').exists():return {'kind':'LEGACY_PROJECT','reason':'USE_LEGACY_OPEN'}
    return {'kind':'UNINITIALIZED_DIRECTORY','reason':'NOT_AN_AGENT_FIRST_PROJECT'}
