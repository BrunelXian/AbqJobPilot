"""Bounded local provenance for handles already verified in one Windows Job."""

import ctypes as C
from ctypes import wintypes as W

from .models import canonical_json

POLICY = "windows-retained-job-provenance-v1"
MAX_PROVENANCE_BYTES = 128 * 1024
MAX_COMMAND_TOTAL = 64 * 1024
MAX_COMMAND_UTF16 = 4096
PROCESS_BASIC_INFORMATION = 0
# Internal Windows information class. Unsupported systems return UNKNOWN.
PROCESS_COMMAND_LINE_INFORMATION = 60


class UnicodeString(C.Structure):
    _fields_ = [("length", W.USHORT), ("maximum_length", W.USHORT), ("buffer", C.c_void_p)]


class ProcessBasicInformation(C.Structure):
    _fields_ = [("exit_status", C.c_long), ("peb", C.c_void_p), ("affinity", C.c_size_t),
                ("priority", C.c_long), ("pid", C.c_size_t), ("parent_pid", C.c_size_t)]


class JobProvenance:
    """Use existing native process handles only. Keep raw commands out of events and IPC."""

    def __init__(self, api):
        self.times = api.GetProcessTimes
        self.times.argtypes = [W.HANDLE] + [C.POINTER(C.c_uint64)] * 4
        self.times.restype = W.BOOL
        try:
            self.query = C.WinDLL("ntdll").NtQueryInformationProcess
        except (OSError, AttributeError):
            self.query = None
        if self.query is not None:
            self.query.argtypes = [W.HANDLE, W.ULONG, C.c_void_p, W.ULONG, C.POINTER(W.ULONG)]
            self.query.restype = C.c_long
        self.observations = {}
        self.command_bytes = 0

    def _command(self, handle):
        if self.query is None:
            return {"command_status": "API_UNAVAILABLE"}
        # Query into an owner buffer. Never dereference a pointer outside it.
        buffer = C.create_string_buffer(C.sizeof(UnicodeString) + MAX_COMMAND_UTF16 + 2)
        received = W.ULONG()
        try:
            status = self.query(handle, PROCESS_COMMAND_LINE_INFORMATION, buffer, len(buffer), C.byref(received))
        except OSError:
            return {"command_status": "QUERY_UNAVAILABLE"}
        if status != 0:
            return {"command_status": "COMMAND_LIMIT" if received.value > len(buffer) else "QUERY_UNAVAILABLE",
                    "command_ntstatus": status & 0xFFFFFFFF}
        string = UnicodeString.from_buffer(buffer)
        base = C.addressof(buffer)
        if (not string.buffer or not 0 < string.length <= MAX_COMMAND_UTF16 or string.length % 2
                or string.length > string.maximum_length
                or not base + C.sizeof(string) <= string.buffer
                <= base + min(len(buffer), received.value) - string.length):
            return {"command_status": "INVALID_RESPONSE"}
        try:
            command_line = C.string_at(string.buffer, string.length).decode("utf-16-le")
            size = len(canonical_json(command_line).encode("utf-8"))
        except UnicodeError:
            return {"command_status": "INVALID_RESPONSE"}
        if self.command_bytes + size > MAX_COMMAND_TOTAL:
            return {"command_status": "COMMAND_BUDGET"}
        self.command_bytes += size
        return {"command_status": "HANDLE_OBSERVED", "command_line": command_line}

    def _parent(self, handle, pid):
        if self.query is None:
            return {"parent_pid_status": "API_UNAVAILABLE"}
        basic = ProcessBasicInformation()
        try:
            status = self.query(handle, PROCESS_BASIC_INFORMATION, C.byref(basic), C.sizeof(basic), None)
        except OSError:
            return {"parent_pid_status": "QUERY_UNAVAILABLE"}
        if status != 0:
            return {"parent_pid_status": "QUERY_UNAVAILABLE", "parent_ntstatus": status & 0xFFFFFFFF}
        if basic.pid != pid or basic.parent_pid <= 0 or basic.parent_pid == pid:
            return {"parent_pid_status": "INVALID_RESPONSE"}
        return {"parent_pid_status": "HANDLE_OBSERVED", "parent_pid_hint": basic.parent_pid}

    def capture(self, key, handle, *, exited=False):
        observed = self.observations.setdefault(key, {})
        if observed.get("command_status") not in {
                "HANDLE_OBSERVED", "COMMAND_LIMIT", "COMMAND_BUDGET", "API_UNAVAILABLE"}:
            attempt = self._command(handle)
            observed.update(attempt)
            if "command_ntstatus" not in attempt:
                observed.pop("command_ntstatus", None)
            observed["command_stage"] = "EXIT" if exited else "FIRST_HANDLE"
        if observed.get("parent_pid_status") != "HANDLE_OBSERVED":
            attempt = self._parent(handle, key[0])
            observed.update(attempt)
            if "parent_ntstatus" not in attempt:
                observed.pop("parent_ntstatus", None)
        if exited:
            times = [C.c_uint64() for _ in range(4)]
            try:
                ok = self.times(handle, *(C.byref(value) for value in times))
            except OSError:
                ok = False
            if ok and times[0].value == key[1] and times[1].value >= key[1]:
                observed["exit_time_100ns"] = times[1].value
                observed["exit_time_source"] = "GET_PROCESS_TIMES_RETAINED_HANDLE"
            else:
                observed["exit_time_source"] = "UNKNOWN"

    def archive(self, records):
        """Bind a nominated parent only if its retained lifetime spans the child creation."""
        by_pid = {}
        for pid, created in records:
            by_pid.setdefault(pid, []).append((pid, created))
        members = []
        for key, record in records.items():
            observed = self.observations.get(key, {})
            parent = resolve_parent(key, observed.get("parent_pid_hint"),
                                    by_pid, self.observations, records)
            members.append({"role": record["role"], "pid": key[0], "creation_time_100ns": key[1],
                            **observed, **parent})
        return {"policy": POLICY, "members": members, "output": {
            "stdout": "stdout.bin", "stderr": "stderr.bin", "scope": "SHARED_RUN_STDIO",
            "per_process_attribution": "UNKNOWN",
        }}


def resolve_parent(child, parent_pid, by_pid, observations, records):
    if parent_pid is None:
        return {"parent_status": "PID_UNAVAILABLE"}
    candidates = []
    for key in by_pid.get(parent_pid, ()):
        end = observations.get(key, {}).get("exit_time_100ns")
        if key[1] <= child[1] and (end is None or end >= child[1]):
            candidates.append((key, end))
    if len(candidates) == 1:
        key, end = candidates[0]
        if end is not None and key[1] < child[1] < end:
            return {"parent_status": "VERIFIED_JOB_LIFETIME", "parent": {
                "pid": key[0], "creation_time_100ns": key[1], "role": records[key]["role"],
            }}
    return {"parent_status": "LIFETIME_UNVERIFIED" if candidates else "NO_MATCHING_JOB_MEMBER"}
