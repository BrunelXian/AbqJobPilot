"""Windows retained process references. Absence is never exit evidence."""

import ctypes
from pathlib import Path

from .models import ExecutionError, now, require


class ProcessReference:
    def __init__(self, pid, expected=None, *, cleanup=False):
        require(type(pid) is int and pid > 0, "PROCESS_IDENTITY_UNKNOWN", "Invalid process candidate")
        self.api = api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        api.OpenProcess.restype = ctypes.c_void_p
        api.GetProcessTimes.argtypes = [ctypes.c_void_p] * 5
        api.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
        api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        api.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        self.handle = api.OpenProcess(0x100000 | 0x1000 | (1 if cleanup else 0), False, pid)
        if not self.handle:
            failure = ExecutionError("PROCESS_IDENTITY_UNKNOWN", "Cannot open exact process; no exit inferred")
            # Read-only diagnostic provenance. Access denied or later identity
            # query failures must never be interpreted as an absent PID.
            failure.pid_absent = ctypes.get_last_error() == 87  # ERROR_INVALID_PARAMETER for a nonzero PID
            raise failure
        try:
            times = [ctypes.c_uint64() for _ in range(4)]
            require(bool(api.GetProcessTimes(self.handle, *(ctypes.byref(t) for t in times))),
                    "PROCESS_IDENTITY_UNKNOWN", "Process creation identity unavailable")
            buffer, size = ctypes.create_unicode_buffer(32768), ctypes.c_uint32(32768)
            require(bool(api.QueryFullProcessImageNameW(self.handle, 0, buffer, ctypes.byref(size))),
                    "PROCESS_IDENTITY_UNKNOWN", "Process image unavailable")
            self.identity = {"pid": pid, "creation_time_100ns": times[0].value, "image_path": buffer.value}
            if expected is not None:
                require(expected.get("pid") == pid and expected.get("creation_time_100ns") == times[0].value
                        and Path(expected.get("image_path", "")).resolve() == Path(buffer.value).resolve(),
                        "PROCESS_IDENTITY_MISMATCH", "Process candidate does not match retained OS identity")
        except BaseException:
            self.close()
            raise

    def exit_evidence(self):
        wait = self.api.WaitForSingleObject(self.handle, 0)
        if wait == 258:
            return None
        require(wait == 0, "PROCESS_EXIT_UNKNOWN", "Retained process wait failed")
        code = ctypes.c_uint32()
        require(bool(self.api.GetExitCodeProcess(self.handle, ctypes.byref(code))),
                "PROCESS_EXIT_UNKNOWN", "Exact process exited but exit code unavailable")
        return {**self.identity, "exit_code": code.value, "exit_observed_at": now(),
                "exit_source": "retained_windows_handle"}

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
