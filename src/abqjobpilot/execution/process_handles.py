"""Windows retained process references. Absence is never exit evidence."""

import ctypes
from pathlib import Path

from .models import ExecutionError, now, require


def native_process_error(code, message, operation, winerror):
    """Attach the native operation and code without changing the error code."""
    error = ExecutionError(code, message)
    error.native_operation = operation
    if type(winerror) is int and 0 <= winerror <= 0xFFFFFFFF:
        error.winerror = winerror
    return error


def read_process_identity(handle, pid, *, api=None):
    api = api if api is not None else ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetProcessTimes.argtypes = [ctypes.c_void_p] * 5
    api.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
    times = [ctypes.c_uint64() for _ in range(4)]
    if not api.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
        raise native_process_error("PROCESS_IDENTITY_UNKNOWN", "Process creation identity unavailable",
                                   "GetProcessTimes", ctypes.get_last_error())
    buffer, size = ctypes.create_unicode_buffer(32768), ctypes.c_uint32(32768)
    if not api.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
        raise native_process_error("PROCESS_IDENTITY_UNKNOWN", "Process image unavailable",
                                   "QueryFullProcessImageNameW", ctypes.get_last_error())
    return {"pid": pid, "creation_time_100ns": times[0].value, "image_path": buffer.value}


class ProcessReference:
    def __init__(self, pid, expected=None, *, cleanup=False):
        require(type(pid) is int and pid > 0, "PROCESS_IDENTITY_UNKNOWN", "Invalid process candidate")
        self.api = api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        api.OpenProcess.restype = ctypes.c_void_p
        api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        api.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        self.handle = api.OpenProcess(0x100000 | 0x1000 | (1 if cleanup else 0), False, pid)
        if not self.handle:
            winerror = ctypes.get_last_error()
            failure = native_process_error("PROCESS_IDENTITY_UNKNOWN",
                                           "Cannot open exact process; no exit inferred",
                                           "OpenProcess", winerror)
            # Read-only diagnostic provenance. Access denied or later identity
            # query failures must never be interpreted as an absent PID.
            failure.pid_absent = winerror == 87  # ERROR_INVALID_PARAMETER for a nonzero PID
            raise failure
        try:
            self.identity = read_process_identity(self.handle, pid, api=api)
            if expected is not None:
                require(expected.get("pid") == pid
                        and expected.get("creation_time_100ns") == self.identity["creation_time_100ns"]
                        and Path(expected.get("image_path", "")).resolve() == Path(self.identity["image_path"]).resolve(),
                        "PROCESS_IDENTITY_MISMATCH", "Process candidate does not match retained OS identity")
        except BaseException:
            self.close()
            raise

    def exit_evidence(self):
        wait = self.api.WaitForSingleObject(self.handle, 0)
        if wait == 0xFFFFFFFF:  # WAIT_FAILED
            raise native_process_error("PROCESS_EXIT_UNKNOWN", "Retained process wait failed",
                                       "WaitForSingleObject", ctypes.get_last_error())
        if wait == 258:
            return None
        require(wait == 0, "PROCESS_EXIT_UNKNOWN", "Retained process wait failed")
        code = ctypes.c_uint32()
        if not self.api.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            raise native_process_error("PROCESS_EXIT_UNKNOWN", "Exact process exited but exit code unavailable",
                                       "GetExitCodeProcess", ctypes.get_last_error())
        return {**self.identity, "exit_code": code.value, "exit_observed_at": now(),
                "exit_source": "retained_windows_handle"}

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
