"""Bounded, portable TEST_ONLY Project Factory for the current Frozen package."""
import hashlib
import json
from pathlib import Path

PROFILE = 'AP-D01C-P2B-R3-FIXED-NORMAL-MANAGED'
FORMAT_BINDING = 'abqjobpilot-portable-test-factory-binding-v1'
FORMAT_RECEIPT = 'abqjobpilot-portable-test-factory-receipt-v1'


def _manifest():
    from .application_runtime import _read_portable_test_manifest
    return _read_portable_test_manifest()


def _no_reparse(path):
    from .execution.models import require
    path = Path(path)
    for item in (path, *path.parents):
        require(not item.is_symlink()
                and not (hasattr(item, 'is_junction') and item.is_junction()),
                'PATH_REJECTED', 'TEST_ONLY UAT paths cannot contain reparse points')


def _target(path, *, exists):
    """Accept only <explicit-local-UAT-root>/fixture/Project."""
    from .application_runtime import application_install_root
    from .execution.models import require
    supplied = Path(path)
    require(supplied.is_absolute(), 'PROJECT_SCOPE_DENIED',
            'An explicit absolute local TEST_ONLY Project path is required')
    root = supplied.parent.parent
    require(root.is_dir(), 'NOT_FOUND', 'An existing local UAT root is required')
    _no_reparse(root)
    install = application_install_root().resolve(strict=True)
    resolved = supplied.resolve(strict=exists)
    expected = (root / 'fixture' / 'Project').resolve(strict=False)
    require(resolved == expected and resolved.name == 'Project'
            and resolved.parent.name == 'fixture'
            and not root.resolve(strict=True).is_relative_to(install),
            'PROJECT_SCOPE_DENIED', 'Project must be under an explicit external UAT root')
    if exists:
        require(resolved.is_dir() and resolved.parent.is_dir(), 'NOT_FOUND',
                'Existing TEST_ONLY Project and fixture directory are required')
    else:
        require(not resolved.exists(), 'PROJECT_EXISTS', 'Existing Project is never overwritten')
        require(not resolved.parent.exists() or resolved.parent.is_dir(), 'PATH_REJECTED',
                'Fixture parent is not a directory')
    _no_reparse(resolved.parent if exists else root)
    return resolved


def _root_for_project(path, *, exists):
    target = _target(path, exists=exists)
    return target.parent.parent


def _build_identity():
    from .application_runtime import _read_build_identity, executable_role, is_test_only_build
    from .execution.models import require
    require(is_test_only_build() and executable_role() == 'gui', 'CAPABILITY_UNAVAILABLE',
            'Portable TEST_ONLY Factory is available only from its Frozen GUI')
    _manifest()
    return _read_build_identity()


def _binding_path(root):
    return root / 'fixture.binding.json'


def _read_binding(root, project):
    from .application_runtime import frozen_fixture_identity
    from .execution.models import require
    from .product_project import open_project
    binding_path = _binding_path(root)
    require(binding_path.is_file() and not binding_path.is_symlink(),
            'PROJECT_SCOPE_DENIED', 'Portable Factory binding record is required')
    binding = json.loads(binding_path.read_text(encoding='utf-8'))
    identity = open_project(project)
    build = _build_identity()
    manifest = _manifest()
    fixture = frozen_fixture_identity()
    expected = {'format': FORMAT_BINDING, 'build_id': build['build_id'],
                'manifest_sha256': manifest['manifest_sha256'],
                'gui_executable_digest': manifest['role_sha256']['gui'],
                'project_id': identity['project_id'],
                'project_instance_id': identity['project_instance_id'],
                'context_digest': identity['context_digest'],
                'owner_executable_digest': fixture['interpreter_digest']}
    require(binding == expected, 'PROJECT_SCOPE_DENIED',
            'Project, local credentials and Frozen candidate binding differs')
    return binding


def verify_fixture_project_target(path):
    from .execution.models import require
    import sqlite3
    from .product_project import MARKER, MANIFEST

    target = _target(path, exists=True)
    require(target.is_dir(), 'PROJECT_SCOPE_DENIED', 'Fixture target must be a directory')
    require((target / MARKER).is_file() and not (target / MANIFEST).exists()
            and not (target / 'agent_project.pending.json').exists(),
            'PROJECT_SCOPE_DENIED', 'Only unpublished initial Project creation is permitted')
    marker = json.loads((target / MARKER).read_text(encoding='utf-8'))
    require(marker.get('creation_state') == 'RESERVED'
            and marker.get('format') == 'abqjobpilot-agent-first-project',
            'PROJECT_SCOPE_DENIED', 'Factory requires a fresh Product Project reservation')
    forbidden = (target / 'project' / 'owner.json', target / 'private' / 'connection.json',
                 target / 'private' / 'lifecycle-current.json', target / 'private' / 'lifecycle.json',
                 target / 'private' / 'operator.json', target / 'private' / 'standard-profile.json')
    require(not any(item.exists() for item in forbidden), 'PROJECT_SCOPE_DENIED',
            'Owner, credentials or lifecycle configuration already exists')
    database = target / 'project' / 'execution.sqlite3'
    require(database.is_file(), 'PROJECT_SCOPE_DENIED', 'Initial empty execution Store is required')
    connection = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA query_only=ON')
        counts = [connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                  for table in ('plans', 'grants', 'management_grants', 'runs')]
        slot = connection.execute('SELECT run_id FROM slot WHERE id=1').fetchone()[0]
        gate = connection.execute('SELECT state FROM dispatch_gate WHERE id=1').fetchone()
    finally:
        connection.close()
    require(counts == [0, 0, 0, 0] and slot is None and gate is not None and gate[0] == 'PAUSED',
            'PROJECT_SCOPE_DENIED', 'Factory Project must be PAUSED with 0 Plan/Grant/Run and an empty slot')


def _write_receipt(path, value):
    from .execution.models import canonical_json
    with path.open('x', encoding='utf-8') as stream:
        stream.write(canonical_json(value))
        stream.flush()


def create_fixture_project(path):
    from .application_runtime import frozen_fixture_identity
    from .execution.models import require
    from .product_project import create_project

    target = _target(path, exists=False)
    root = target.parent.parent
    require(not any(root.iterdir()), 'PROJECT_EXISTS',
            'UAT root must be a new empty directory; existing state is never adopted')
    require(not _binding_path(root).exists(), 'PROJECT_EXISTS', 'Factory binding already exists')
    build = _build_identity()
    manifest = _manifest()
    fixture = frozen_fixture_identity()
    target.parent.mkdir()
    identity = create_project(target, 'AbqJobPilot TEST_ONLY ProcessFixture UAT',
                              test_fixture_profile=PROFILE)
    from .local_credentials import read_private
    from .service_lifecycle import ServiceLifecycleManager
    manager = ServiceLifecycleManager(target)
    profile = read_private(manager.context, target / 'private' / 'lifecycle.json')
    from .execution.process_backend import ProcessFixtureConfig
    expected = ProcessFixtureConfig.current(managed_scope=True)
    require(profile.get('process_config') == expected.__dict__, 'PROJECT_SCOPE_DENIED',
            'Initial fixed TEST_ONLY ProcessFixture profile differs')
    binding = {'format': FORMAT_BINDING, 'build_id': build['build_id'],
               'manifest_sha256': manifest['manifest_sha256'],
               'gui_executable_digest': manifest['role_sha256']['gui'],
               'project_id': identity['project_id'],
               'project_instance_id': identity['project_instance_id'],
               'context_digest': identity['context_digest'],
               'owner_executable_digest': fixture['interpreter_digest']}
    _write_receipt(_binding_path(root), binding)
    result = {'format': FORMAT_RECEIPT, 'operation': 'create_fixture_project', **binding,
              'project': str(target.resolve()), 'profile': PROFILE,
              'initial_dispatch': identity['initial_dispatch'], 'run_count': 0, 'grant_count': 0}
    _write_receipt(root / 'fixture.provision.json', result)
    return result


def start_owner(path):
    from .execution.models import require
    from .product_project import open_project
    from .service_lifecycle import ServiceLifecycleManager
    project = _target(path, exists=True)
    root = project.parent.parent
    binding = _read_binding(root, project)
    identity = open_project(project)
    require(not (project / 'project' / 'owner.json').exists()
            and not (project / 'private' / 'connection.json').exists()
            and not (project / 'private' / 'lifecycle-current.json').exists(),
            'START_UNCONFIRMED', 'Factory Owner may be started only once from the new initial Project')
    manager = ServiceLifecycleManager(project)
    result = manager.start(operator_file=str(project / 'private' / 'operator.json'))
    require(result.get('created') is True, 'START_UNCONFIRMED',
            'Factory requires a newly created Owner, not a reused service')
    client, context, health = manager.connect()
    require(context.project_instance_id == binding['project_instance_id']
            and client.endpoint['project_instance_id'] == binding['project_instance_id']
            and health['process'] == client.endpoint['process'],
            'PROJECT_IDENTITY_MISMATCH', 'Owner identity differs from this Project binding')
    record = {'format': FORMAT_RECEIPT, 'operation': 'start_owner', **binding,
              'owner_id': client.endpoint['owner_id'], 'process': client.endpoint['process'],
              'health': health, 'start': result}
    _write_receipt(root / 'fixture.start.json', record)
    return record


def stop_owner(path):
    from .execution.models import identifier
    from .service_lifecycle import ServiceLifecycleManager
    project = _target(path, exists=True)
    root = project.parent.parent
    binding = _read_binding(root, project)
    manager = ServiceLifecycleManager(project)
    client, context, health = manager.connect()
    result = manager.stop(owner_id=client.endpoint['owner_id'], operation_key=identifier('test-stop'),
                          operator_file=str(project / 'private' / 'operator.json'))
    record = {'format': FORMAT_RECEIPT, 'operation': 'stop_owner', **binding,
              'project_instance_id': context.project_instance_id,
              'owner_id': client.endpoint['owner_id'], 'process': health['process'],
              'stop': result, 'post_stop': manager.inspect()}
    _write_receipt(root / 'fixture.stop.json', record)
    return record


def main(argv):
    if argv and argv[0] == '--test-only-ap-d02':
        from .ap_d02_adapter import main as qualify
        try:
            return qualify(argv)
        except Exception as exc:
            try:
                from .qualification import load
                from .service_lifecycle import write_new
                from .execution.models import ExecutionError
                value = load(argv[2], argv[3])
                record = {'operation': argv[1], 'exception_class': type(exc).__name__,
                          'code': exc.code if isinstance(exc, ExecutionError) else 'ADAPTER_FAILURE'}
                for key in ('errno', 'winerror'):
                    number = getattr(exc, key, None)
                    if type(number) is int: record[key] = number
                write_new(Path(value['evidence']) / ('adapter-error-' + argv[1] + '.json'), record)
            except Exception:
                pass
            return 2
    from .execution.models import ExecutionError, require
    require(len(argv) == 2 and argv[0] in {'--test-only-create-fixture',
            '--test-only-start-owner', '--test-only-stop-owner'}, 'INVALID_REQUEST',
            'Fixed TEST_ONLY Factory operation and explicit Project path required')
    try:
        if argv[0] == '--test-only-create-fixture':
            create_fixture_project(argv[1])
        elif argv[0] == '--test-only-start-owner':
            start_owner(argv[1])
        else:
            stop_owner(argv[1])
        return 0
    except (ExecutionError, OSError, ValueError, TypeError) as exc:
        code = exc.code if isinstance(exc, ExecutionError) else type(exc).__name__
        if not isinstance(code, str) or not code.replace('_', '').isalnum() or len(code) > 64:
            code = 'UNCLASSIFIED_ERROR'
        record = {'format': FORMAT_RECEIPT, 'operation': argv[0], 'error_code': code,
                  'exception_class': type(exc).__name__[:64]}
        for name in ('errno', 'winerror'):
            value = getattr(exc, name, None)
            if type(value) is int and 0 <= value <= 0xFFFFFFFF:
                record[name] = value
        try:
            root = _root_for_project(argv[1], exists=argv[0] != '--test-only-create-fixture')
            error_path = root / 'fixture.error.json'
            if root.is_dir() and not error_path.exists():
                _write_receipt(error_path, record)
        except Exception:
            pass
        return 2
