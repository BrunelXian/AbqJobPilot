"""TEST_ONLY qualification commands. Not a public product API."""
import json
from pathlib import Path
import sys
from .qualification import ACTIVE, load
from .execution.models import require, identifier
from .service_lifecycle import write_new


def main(argv):
    require(len(argv) == 4 and argv[0] == '--test-only-ap-d02'
            and argv[1] in {'provision', 'start', 'gui', 'classic-probe'},
            'INVALID_REQUEST', 'Fixed qualification command required')
    config = load(argv[2], argv[3])
    from .application_runtime import executable_role
    require(executable_role() == 'gui', 'CAPABILITY_UNAVAILABLE', 'Qualification GUI role required')
    token = ACTIVE.set(config)
    try:
        project = Path(config['project'])
        evidence = Path(config['evidence'])
        require(evidence.is_dir(), 'NOT_FOUND', 'Explicit evidence directory required')
        operation = argv[1]
        if operation == 'provision':
            require(config['project_instance_id'] is None and not project.exists(),
                    'PROJECT_EXISTS', 'Initial Factory creation only')
            from .product_project import create_project
            identity = create_project(project, 'AP-D02 fixed TEST_ONLY Fixture',
                                      test_fixture_profile='AP-D01C-P2B-R3-FIXED-NORMAL-MANAGED')
            binding = {k: identity[k] for k in ('project_id', 'project_instance_id', 'context_digest')}
            binding.update(build_id=config['build_id'], scenario=config['scenario'], max_runs=1)
            write_new(Path(config['sandbox']) / 'factory-binding.json', binding)
            write_new(evidence / 'provision.json', binding)
            return 0
        from .product_project import open_project
        identity = open_project(project)
        require(identity['project_instance_id'] == config['project_instance_id'],
                'PROJECT_IDENTITY_MISMATCH', 'Acceptance Project instance differs')
        if operation == 'start':
            from .service_lifecycle import ServiceLifecycleManager
            manager = ServiceLifecycleManager(project)
            result = manager.start(operator_file=str(project / 'private' / 'operator.json'))
            client, context, health = manager.connect()
            write_new(evidence / (identifier('start') + '.json'),
                      {'start': result, 'owner': client.endpoint, 'health': health})
            return 0
        if operation == 'classic-probe':
            return classic_probe(evidence)
        # Real Tk window, explicit Project, normal close callback. No Recent selection.
        from .gui_app import AbqJobPilotApp
        app = AbqJobPilotApp(attachment_mode=True, native_workspace=True)
        app.execution_view.attach_project(str(project))
        app.mainloop()
        return 0
    finally:
        ACTIVE.reset(token)


def classic_probe(evidence):
    from .execution.models import ExecutionError
    from .application_runtime import require_classic_source
    from .desktop_workspace import DesktopWorkspace
    from .gui_app import _load_legacy
    results = {}
    for name, call in {'boundary': require_classic_source, 'lazy_legacy': _load_legacy,
                       'open_classic': lambda: DesktopWorkspace.open_classic(None, 'unused'),
                       'navigate': lambda: DesktopWorkspace.navigate(None, 'classic')}.items():
        try:
            call()
        except ExecutionError as exc:
            require(exc.code == 'CLASSIC_EXECUTION_UNAVAILABLE', 'TEST_AUTHORITY_SCOPE', 'Unexpected refusal')
            results[name] = exc.code
        else:
            raise AssertionError('Frozen Classic boundary accepted')
    # This module is deliberately excluded from the Frozen distribution.
    try:
        from . import runner_core
    except ImportError:
        results['runner_module'] = 'EXCLUDED'
    else:
        try:
            runner_core._run_command({}, 'TEST', [])
        except ExecutionError as exc:
            require(exc.code == 'CLASSIC_EXECUTION_UNAVAILABLE', 'TEST_AUTHORITY_SCOPE', 'Unexpected execution refusal')
            results['runner_module'] = exc.code
        else:
            raise AssertionError('Frozen legacy execution accepted')
    write_new(evidence / 'classic-probe.json', results)
    return 0
