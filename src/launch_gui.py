"""Visible-failure native GUI bootstrap; no Project/service/Grant initialization."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def inspect():
    facts = {'errors': [], 'service_started': False, 'Abaqus_calls': 0,
             'python': sys.version.split()[0], 'interpreter': sys.executable}
    try:
        from abqjobpilot.application_runtime import executable_role, is_frozen_runtime, validate_runtime
        validate_runtime()
        facts['runtime'] = 'frozen' if is_frozen_runtime() else 'source'
        facts['role'] = executable_role()
    except Exception:
        facts['errors'].append('WINDOWS_CPYTHON_312_X64_REQUIRED')
    try:
        import tkinter
        facts['tk'] = tkinter.Tcl().eval('info patchlevel')
    except Exception:
        facts['errors'].append('TK_UNAVAILABLE_OR_BROKEN')
    if not facts['errors']:
        try:
            from abqjobpilot.gui_app import main
            facts['gui_import'] = callable(main)
        except Exception:
            facts['errors'].append('PRODUCT_IMPORT_INCOMPLETE')
    facts['status'] = 'BLOCKED' if facts['errors'] else 'READY'
    return facts


def _frozen_owner(argv):
    if not argv:
        print('Owner role requires one fixed internal command', file=sys.stderr)
        return 2
    if argv[0] == '--service-owner':
        from abqjobpilot.service_owner import main as owner_main
        try:
            owner_main(argv[1:])
            return 0
        except Exception as exc:
            from abqjobpilot.execution.models import ExecutionError
            code = exc.code if isinstance(exc, ExecutionError) else 'SERVICE_HOST_FAILED'
            if sys.stderr is not None:
                print(code, file=sys.stderr)
            return 2
    if argv[0] == '--fixture-role':
        import argparse
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--role', choices=('launcher', 'worker', 'branch', 'leaf', 'burst'), required=True)
        parser.add_argument('--directory', required=True)
        parser.add_argument('--index', type=int, choices=range(6), default=0)
        try:
            args = parser.parse_args(argv[1:])
        except SystemExit:
            return 2
        from abqjobpilot.execution.process_fixture import main as fixture_main
        return fixture_main(['--role', args.role, '--directory', args.directory, '--index', str(args.index)])
    if sys.stderr is not None:
        print('Unsupported Owner role command', file=sys.stderr)
    return 2


def _report(message, title='AbqJobPilot startup', *, interactive=True, diagnostic_path=None):
    stream = sys.stderr if sys.stderr is not None else (sys.stdout if sys.stdout is not None else None)
    if not interactive and diagnostic_path is not None:
        path = Path(diagnostic_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        stage = path.with_suffix(path.suffix + '.tmp')
        stage.write_text(message + '\n', encoding='utf-8')
        stage.replace(path)
        return
    if stream is not None:
        print(message, file=stream)
    elif not interactive:
        from os import environ
        destination = diagnostic_path
        if destination is None:
            local = environ.get('LOCALAPPDATA')
            destination = str(Path(local) / 'AbqJobPilot' / 'diagnostics' / 'last-check.json') if local else None
        if destination:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            stage = path.with_suffix(path.suffix + '.tmp')
            stage.write_text(message + '\n', encoding='utf-8')
            stage.replace(path)
    elif sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, title, 16)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    check_mode = bool(argv and argv[0] == '--check')
    diagnostic_path = argv[2] if len(argv) == 3 and argv[0] == '--check' and argv[1] == '--diagnostic-file' else None
    if argv and argv[0] == '--mcp-server':
        from abqjobpilot.application_runtime import validate_runtime
        validate_runtime()
        from abqjobpilot.mcp.server import main as mcp_main
        return mcp_main(argv[1:])
    try:
        from abqjobpilot.application_runtime import executable_role, is_frozen_runtime, validate_runtime
        if is_frozen_runtime():
            validate_runtime()
            role = executable_role()
            if role == 'owner':
                return _frozen_owner(argv)
            if argv and argv[0].startswith('--test-only-'):
                from abqjobpilot.frozen_test_adapter import main as test_main
                return test_main(argv)
            if (role == 'gui' and len(argv) == 4 and argv[0] == '--execution-connection'
                    and argv[2] == '--request-key'):
                from abqjobpilot.gui_app import main as gui_main
                return gui_main()
    except Exception:
        _report('FROZEN_RUNTIME_IDENTITY_INVALID', interactive=not check_mode, diagnostic_path=diagnostic_path)
        return 2
    if len(argv) == 3 and argv[0] == '--check' and argv[1] == '--diagnostic-file':
        diagnostic_path = argv[2]
        argv = ['--check']
    if argv not in ([], ['--check']):
        _report('Only --check is supported')
        return 2
    facts = inspect()
    if argv == ['--check']:
        _report(json.dumps(facts, ensure_ascii=False, sort_keys=True), title='AbqJobPilot runtime check',
                interactive=False, diagnostic_path=diagnostic_path)
        return 2 if facts['errors'] else 0
    try:
        if facts['errors']:
            raise RuntimeError(', '.join(facts['errors']))
        from abqjobpilot.gui_app import main as gui_main
        gui_main()
        return 0
    except Exception:
        # Do not print arbitrary exception text: it may contain private input.
        message = ('Startup failed: ' + ', '.join(facts['errors'])) if facts['errors'] else 'GUI_START_FAILED'
        message += '\nRun AbqJobPilot.exe --check for the Frozen runtime or launch_gui.py --check in Source mode. No service is started by this launcher.'
        _report(message)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
