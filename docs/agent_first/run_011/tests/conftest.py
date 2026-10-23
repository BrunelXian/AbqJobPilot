import os
from pathlib import Path
import sys
import ctypes

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'controller'))
sys.path.insert(0, r'D:\Projects\abqjobpilot_dev')
REAL_ROOT = r'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a'.lower()


def sentinel(event, args):
    if event == 'subprocess.Popen':
        exe, argv, cwd, env = args
        # Windows subprocess audit receives the already-quoted command string.
        if isinstance(argv, str):
            count = ctypes.c_int()
            shell = ctypes.WinDLL('shell32', use_last_error=True)
            shell.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
            shell.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
            pointer = shell.CommandLineToArgvW(argv, ctypes.byref(count))
            assert pointer
            try: argv = [pointer[i] for i in range(count.value)]
            finally:
                kernel = ctypes.WinDLL('kernel32')
                kernel.LocalFree.argtypes = [ctypes.c_void_p]
                kernel.LocalFree(pointer)
        assert Path(exe or argv[0]) in {Path(r'D:\Program Files\Python312\python.exe'),
                             Path(r'D:\XianLab\envs\LangChainEnv\Scripts\python.exe')}
        assert type(argv) is list and len(argv) >= 3 and argv[1] == '-B'
        script = Path(argv[2])
        assert script in {HERE / 'fixture_driver.py', HERE / 'fixture_process.py',
                          HERE / 'readonly_driver.py', HERE.parent / 'controller/probe.py'}
        if script.name == 'probe.py':
            assert 'execute' not in argv
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = os.fsdecode(args[0]).lower().replace('/', '\\')
        assert not path.startswith('d:\\projects\\abqjobpilot\\')
        mode, flags = args[1:]
        if path.startswith(REAL_ROOT):
            assert not ((flags or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
    if event in {'os.system','os.startfile','sqlite3.connect'}:
        raise AssertionError('No shell/database/default execution in candidate tests')


sys.addaudithook(sentinel)
