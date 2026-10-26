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
        from abqjobpilot.application_runtime import validate_runtime
        validate_runtime()
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


def main():
    if sys.argv[1:] not in ([], ['--check']):
        print('Only --check is supported', file=sys.stderr)
        return 2
    facts = inspect()
    if sys.argv[1:] == ['--check']:
        print(json.dumps(facts, ensure_ascii=False))
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
        message += '\nRun launch_gui.py --check with the configured Python. No service is started by this launcher.'
        print(message, file=sys.stderr)
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, 'AbqJobPilot startup', 16)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
