"""Project-scoped attach only: bounded metadata, original credentials, authenticated IPC.

No database, authority, owner startup, port scan, Recent lookup or repair.
"""
import json
from pathlib import Path

from .execution.client import FakeClient
from .execution.models import FORMAT, ProjectContext, ExecutionError, digest, fields, require
from .execution.paths import local_path, no_reparse, confined
from .execution.process_handles import ProcessReference


def read_document(path):
    path = local_path(path); no_reparse(path)
    try:
        with path.open('rb') as stream: data = stream.read(65537)
        require(len(data) <= 65536, 'LIMIT_EXCEEDED', 'Connection metadata exceeds bound')
        return json.loads(data)
    except (OSError, ValueError) as exc:
        raise ExecutionError('DISCOVERY_UNAVAILABLE', 'Selected Project connection material is unavailable') from None


def project_identity(project_root):
    root=local_path(project_root); no_reparse(root)
    require(root.is_dir(), 'NOT_FOUND', 'Select an existing Agent-first Project directory')
    root=root.resolve()
    if (root/'agent_project.json').exists() or (root/'.agent-first-creation.json').exists():
        require((root/'agent_project.json').exists(),'PROJECT_INCOMPLETE','Project creation has not committed')
        root=root/'project'
    elif not (root/'experiment.json').exists():
        require(not (root/'project.json').exists(),'LEGACY_PROJECT','Use Legacy Open; no migration')
        raise ExecutionError('NOT_AN_AGENT_FIRST_PROJECT','No supported Project manifest in selected directory')
    manifest=read_document(root/'experiment.json')
    fields(manifest, ('format_id','schema_version','project_id','project_instance_id','storage_generation','root','test_root'))
    require(manifest['format_id']==FORMAT and type(manifest['schema_version']) is int
            and manifest['schema_version']==3, 'UNSUPPORTED_FORMAT', 'Agent-first format 3 is required; no migration')
    require(manifest['root']==str(root), 'PROJECT_IDENTITY_MISMATCH', 'Project root differs from manifest')
    boundary=local_path(manifest['test_root'])
    # Existing isolated instances use <explicit root>/project. Never search ancestors.
    require(root.parent==boundary, 'DISCOVERY_LAYOUT_UNSUPPORTED', 'Project must be directly inside its explicit instance root')
    confined(boundary,root,exists=True)
    confined(boundary,root/'execution.sqlite3',exists=True)
    confined(boundary,root/'runtime',exists=True)
    st=root.stat()
    context = ProjectContext(manifest['project_id'],manifest['project_instance_id'],str(boundary),str(root),
        str(root/'runtime'),str(root/'execution.sqlite3'),FORMAT,3,manifest['storage_generation'],
        digest(manifest),st.st_dev,st.st_ino)
    from .local_credentials import protected_project
    if protected_project(context):
        from .product_project import validate_product
        validate_product(context)
    return context


def discover(project_root, connection_file=None):
    """Every connect/reconnect authenticates the selected Project and live owner identity."""
    try:
        context=project_identity(project_root)
        root=Path(context.root)
        # Known handoff location used by existing trusted examples, not a scan.
        path=Path(connection_file) if connection_file else root.parent/'private'/'connection.json'
        path=confined(context.test_root,path,exists=True)
        require(not path.is_relative_to(root), 'INVALID_REQUEST', 'Private connection material must be outside Project')
        from .local_credentials import read_private
        value=read_private(context,path); fields(value, ('endpoint','credential'))
        endpoint=read_document(root/'owner.json')
        require(endpoint==value['endpoint'], 'ENDPOINT_IDENTITY_MISMATCH', 'Connection and Project owner metadata differ')
        client=FakeClient(endpoint,value['credential'])
        require(endpoint['project_id']==context.project_id and endpoint['project_instance_id']==context.project_instance_id
                and endpoint['context_digest']==context.context_digest and endpoint['execution_store']==context.execution_store,
                'PROJECT_IDENTITY_MISMATCH', 'Service does not belong to selected Project instance')
        identity=endpoint['process']
        fields(identity, ('pid','parent_pid','creation_time_100ns','image_path','executable'))
        ref=ProcessReference(identity['pid'],identity)
        try:
            require(ref.exit_evidence() is None, 'OWNER_NOT_RUNNING', 'Recorded owner has exited')
            health=client.health()
            require(health.get('process')==identity, 'ENDPOINT_IDENTITY_MISMATCH', 'Authenticated owner process changed')
            require('project_view' in health.get('operations',[]), 'CAPABILITY_UNAVAILABLE', 'Existing owner lacks Project listing; no automatic restart')
            require(ref.exit_evidence() is None, 'OWNER_NOT_RUNNING', 'Owner exited during handshake')
        finally: ref.close()
        return client, context, health
    except ExecutionError: raise
    except (OSError, ValueError, TypeError, KeyError):
        raise ExecutionError('DISCOVERY_UNAVAILABLE', 'Project connection check failed; no automatic repair') from None
