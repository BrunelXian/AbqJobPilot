"""Windows local ownership. Metadata is diagnostic; only the held OS lock owns."""

import ctypes
import os
from pathlib import Path
import sys

if sys.platform == "win32":
    import msvcrt

from .models import ExecutionError, require
from .paths import confined


def current_process_identity():
    require(sys.platform == "win32", "UNSUPPORTED_PLATFORM", "Experimental owner requires Windows")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetCurrentProcess.restype = ctypes.c_void_p
    api.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.c_void_p] * 4
    times = [ctypes.c_uint64() for _ in range(4)]
    if not api.GetProcessTimes(api.GetCurrentProcess(), *(ctypes.byref(t) for t in times)):
        raise OSError(ctypes.get_last_error(), "Cannot identify owner process")
    api.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
    buffer, size = ctypes.create_unicode_buffer(32768), ctypes.c_uint32(32768)
    if not api.QueryFullProcessImageNameW(api.GetCurrentProcess(), 0, buffer, ctypes.byref(size)):
        raise OSError(ctypes.get_last_error(), "Cannot identify process image")
    return {"pid": os.getpid(), "parent_pid": os.getppid(), "creation_time_100ns": times[0].value,
            "executable": str(Path(sys.executable).resolve()), "image_path": buffer.value}


class LocalOwnerLock:
    """Non-inheritable handle, nonblocking byte lock; never unlink the lock file."""

    def __init__(self, context):
        self.process = current_process_identity()
        self.path = confined(context.test_root, Path(context.root) / "owner.lock", exists=True)
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
        require(api.GetDriveTypeW(self.path.anchor) == 3, "UNSUPPORTED_PLATFORM",
                "Experimental owner requires a local fixed drive")
        self.stream = self.path.open("r+b", buffering=0)
        self.identity = os.fstat(self.stream.fileno())
        self.closed = False
        try:
            os.set_inheritable(self.stream.fileno(), False)
            # Windows permits a byte lock beyond EOF. Diagnostic readers/copying
            # can still read the lock file; the reserved byte is never written.
            self.stream.seek(4096)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            self.stream.close()
            self.closed = True
            raise ExecutionError("OWNER_BUSY", "The experiment already has an OS lock owner", stage="OWNERSHIP") from exc

    def check(self):
        require(not self.closed and self.process["pid"] == os.getpid(),
                "OWNER_UNCONFIRMED", "No live local ownership handle")
        info = self.path.stat()
        require((info.st_dev, info.st_ino) == (self.identity.st_dev, self.identity.st_ino),
                "OWNER_UNCONFIRMED", "Ownership lock identity changed")

    def close(self):
        if not self.closed:
            self.stream.seek(4096)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            self.stream.close()
            self.closed = True
