"""One independently pinned vertical T3D2 in N/mm/MPa. Only a negative global F2 changes."""
from contextlib import contextmanager
import hashlib
import os
import re
from decimal import Decimal
from pathlib import Path

from .models import require
from .paths import local_path, no_reparse

BASELINE = "189e9b438c117e86eba0997ca12ef5d786ee013631e05c2e2cede39d2a70fe68"
MODEL_TITLE = "TEST_ONLY vertical truss - N mm MPa"
PROFILE = "t3d2-tip-global-u2-v1"
SLOT = re.compile(rb"(?m)^(\*CLOAD\n2, 2, )(-?(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,9})?)\n")
SELECTOR = {"step": 1, "increment": "LAST_COMPLETED", "region": "TIP", "node": 2, "component": "U2", "sign": -1, "unit": "mm"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_bytes(path, limit):
    path = local_path(path)
    no_reparse(path)
    before = path.stat()
    require(path.is_file() and before.st_nlink == 1 and 0 < before.st_size <= limit, "FILE_IDENTITY_INVALID", "Bound regular file required")
    with path.open("rb") as stream:
        opened=os.fstat(stream.fileno())
        require((opened.st_dev,opened.st_ino)==(before.st_dev,before.st_ino),'FILE_CHANGED','Opened identity differs')
        data = stream.read(limit + 1)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, len(data), after.st_mtime_ns), "FILE_CHANGED", "File changed during read")
    return data


def force(value):
    require(isinstance(value, str) and re.fullmatch(r"(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,9})?", value),
            "INVALID_LOAD", "Use positive magnitude in N as a decimal string")
    amount = Decimal(value)
    require(amount <= 200, "LOAD_OUTSIDE_SCOPE", "Reviewed envelope is 0 through 200 N")
    return amount


def candidate(raw, f, lower, upper):
    matches = list(SLOT.finditer(raw))
    require(len(raw) < 8192 and len(matches) == 1, "MODEL_CONTRACT_MISMATCH", "Exactly one approved CLOAD row required")
    m = matches[0]
    require(force(lower) <= force(f) <= force(upper) and Decimal(m[2].decode()) == -force(f),
            "LOAD_OUTSIDE_SCOPE", "F, unit, range or signed component changed")
    restored = raw[:m.start(2)] + b"-1" + raw[m.end(2):]
    require(sha(restored) == BASELINE, "MODEL_CONTRACT_MISMATCH",
            "Step, material, BCs, coordinates, outputs and all other deck bytes must match the reviewed baseline")
    return sha(raw)


@contextmanager
def hold_candidate(plan):
    """Deny concurrent write, rename and delete while the native solver can reopen its input."""
    import ctypes
    from ctypes import wintypes
    path=local_path(plan['input_manifest'][0]['path'])
    no_reparse(path)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    open_file=kernel.CreateFileW
    open_file.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,
                        wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    open_file.restype=wintypes.HANDLE
    close=kernel.CloseHandle
    close.argtypes=[wintypes.HANDLE]
    close.restype=wintypes.BOOL
    handle=open_file(str(path),0x80000000,1,None,3,0x00200080,None)
    require(handle not in (None,ctypes.c_void_p(-1).value),'INPUT_BUSY','Cannot retain a read-only sharing handle')
    try:
        require(sha(file_bytes(path,8192))==plan['sanity']['candidate_sha256'],
                'INPUT_DIGEST_MISMATCH','Pinned candidate changed before launch')
        yield
    finally:
        close(handle)
