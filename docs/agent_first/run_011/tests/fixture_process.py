"""Fixed ordinary Python fixture. Never imports the real CLI or real spawn function."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'controller'))
from windows_host import api, handle_identity


def main():
    role, value = sys.argv[1:]
    assert role in {'worker','launcher'}
    root = Path(value)
    assert root.is_absolute() and root.name.startswith('case_') and 'Run011' in str(root)
    identity = handle_identity(api().GetCurrentProcess(), os.getpid())
    (root / ('physical_' + role + '_' + str(os.getpid()) + '.json')).write_text(json.dumps(identity))
    if role == 'launcher':
        with (root / 'worker_stdout.bin').open('xb') as out, (root / 'worker_stderr.bin').open('xb') as err:
            child = subprocess.Popen([sys.executable, '-B', str(HERE / 'fixture_process.py'), 'worker', str(root)],
                cwd=root, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW,
                env={'SystemRoot':r'C:\Windows', 'TEMP':str(root), 'TMP':str(root)})
            deadline = time.monotonic() + 8
            while not (root / 'worker_ready.json').exists() and time.monotonic() < deadline:
                time.sleep(.01)
            child._handle.Close(); child._child_created = False
        return 0 if (root / 'worker_ready.json').exists() else 4
    (root / 'worker_ready.json').write_text(json.dumps(identity))
    deadline = time.monotonic() + 10
    with (root / 'heartbeat.txt').open('xb', buffering=0) as stream:
        while time.monotonic() < deadline and not (root / 'release').exists():
            stream.write((str(time.time_ns()) + '\n').encode())
            time.sleep(.02)
        stream.write(b'finished\n')
    (root / 'worker_done.json').write_text(json.dumps({'identity':identity, 'natural_exit':True}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
