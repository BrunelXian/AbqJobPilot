"""Collect handle-backed membership evidence for one existing Windows Job."""

import ctypes as C
from ctypes import wintypes as W
import threading

from .models import ExecutionError, canonical_json, now, require
from .process_handles import ProcessReference, read_process_identity

MAX_MEMBERS = 128
MAX_RECORD_BYTES = 48 * 1024
MAX_EXCERPT_MEMBERS = 16
MAX_EXCERPT_BYTES = 4 * 1024
SOURCE = "JOB_NOTIFICATION_AND_PID_LIST_WITH_RETAINED_HANDLES"
NEW_PROCESS = 6
PORT_KEY = 1
ERROR_MORE_DATA = 234
WAIT_TIMEOUT = 258


class PortAssociation(C.Structure):
    _fields_ = [("key", C.c_void_p), ("port", W.HANDLE)]


class JobProcessIds(C.Structure):
    _fields_ = [("assigned", W.DWORD), ("listed", W.DWORD),
                ("pids", C.c_size_t * MAX_MEMBERS)]


class JobProcessObserver:
    """Observe the owned scope before its root runs, independently of Store writes."""

    def __init__(self, scope, *, capture_provenance=False):
        self.scope = scope
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.references = {}
        self.records = {}
        self.exits = {}
        self.root = None
        self.root_key = None
        self.unknowns = set()
        self.hints_unresolved = set()
        self.partial_live_snapshots = 0
        self.record_bytes = 0
        api = scope.api
        self.provenance = None
        if capture_provenance:
            from .job_provenance import JobProvenance
            self.provenance = JobProvenance(api)
        api.CreateIoCompletionPort.argtypes = [W.HANDLE, W.HANDLE, C.c_size_t, W.DWORD]
        api.CreateIoCompletionPort.restype = W.HANDLE
        api.GetQueuedCompletionStatus.argtypes = [W.HANDLE, C.POINTER(W.DWORD), C.POINTER(C.c_size_t),
                                                   C.POINTER(C.c_void_p), W.DWORD]
        api.GetQueuedCompletionStatus.restype = W.BOOL
        self.port = api.CreateIoCompletionPort(C.c_void_p(-1).value, None, 0, 1)
        require(self.port, "MANAGED_OBSERVATION_UNAVAILABLE", "Cannot create the Job observation port")
        self.thread = threading.Thread(target=self._watch, name="standard-job-observer", daemon=True)
        try:
            association = PortAssociation(PORT_KEY, self.port)
            require(api.SetInformationJobObject(scope.handle, 7, C.byref(association), C.sizeof(association)),
                    "MANAGED_OBSERVATION_UNAVAILABLE", "Cannot subscribe to the empty Job before launch")
            self.thread.start()
        except BaseException:
            api.CloseHandle(self.port)
            raise

    def _poll_job(self):
        pids = JobProcessIds()
        ok = self.scope.api.QueryInformationJobObject(self.scope.handle, 3, C.byref(pids), C.sizeof(pids), None)
        if (not ok and C.get_last_error() == ERROR_MORE_DATA) or (ok and pids.assigned > MAX_MEMBERS):
            self.unknowns.add("MEMBER_LIMIT")
            return
        require(ok and pids.listed <= pids.assigned <= MAX_MEMBERS, "MANAGED_SCOPE_UNKNOWN",
                "Job's live membership snapshot unavailable")
        if pids.listed < pids.assigned:
            # A successful live query can be partial during concurrent exits.
            # Treat listed PIDs as hints. Terminal proof uses cumulative Job
            # accounting and independently verified, handle-backed exits.
            self.partial_live_snapshots += 1
        for pid in pids.pids[:pids.listed]:
            self._remember(pid)

    def _notification(self, timeout):
        kind, key, pid = W.DWORD(), C.c_size_t(), C.c_void_p()
        ok = self.scope.api.GetQueuedCompletionStatus(self.port, C.byref(kind), C.byref(key), C.byref(pid), timeout)
        if not ok and not pid.value and C.get_last_error() == WAIT_TIMEOUT:
            return False
        require(ok and key.value == PORT_KEY, "MANAGED_SCOPE_UNKNOWN", "Invalid Job notification")
        if kind.value == NEW_PROCESS and pid.value:
            with self.lock:
                self._remember(pid.value)
        return True

    def _watch(self):
        try:
            while not self.stopping.is_set():
                self._notification(8)
                # Drain pending births without making Store or filesystem calls.
                for _ in range(MAX_MEMBERS):
                    if not self._notification(0):
                        break
                with self.lock:
                    self._poll_job()
                    self._collect_exits()
        except Exception:
            with self.lock:
                self.unknowns.add("JOB_OBSERVATION_FAILED")

    @staticmethod
    def _key(identity):
        return identity["pid"], identity["creation_time_100ns"]

    def _store_identity(self, identity, role, *, root=False):
        key = self._key(identity)
        old = self.records.get(key)
        record = {**identity, "identity_status": "VERIFIED", "role": role, "observed_at": now()}
        if not old:
            size = _record_reservation(record)
            if (len(identity["image_path"]) > 1024 or len(self.records) >= MAX_MEMBERS
                    or self.record_bytes + size > MAX_RECORD_BYTES):
                self.unknowns.add("MEMBER_LIMIT")
                return None
            self.record_bytes += size
        if not old or root:
            self.records[key] = record
        return key

    def _remember(self, pid):
        # A notification carries a PID, never an identity. Count only a
        # retained handle that Windows verifies belongs to this exact Job.
        if self.root_key is not None and pid == self.root_key[0]:
            if self.root_key not in self.exits:
                return
        # Most live PIDs were already pinned on their birth notification.
        if any(key[0] == pid and key not in self.exits for key in self.references):
            return
        ref = None
        try:
            ref = ProcessReference(pid)
            if not self.scope.contains(ref.handle):
                return
            key = self._key(ref.identity)
            if key not in self.records:
                require(self.root_key is None or key[1] >= self.root_key[1],
                        "PROCESS_IDENTITY_MISMATCH", "Member appears to predate original Job root")
                if self._store_identity(ref.identity, "member_" + str(len(self.records))) is not None:
                    self.references[key] = ref
                    handle = ref.handle
                    ref = None
                    if self.provenance is not None:
                        self.provenance.capture(key, handle)
        except (ExecutionError, OSError):
            # Even a late hint can race a process exit or refer to its old
            # PID. Coverage is decided by native Job totals plus handle evidence.
            if len(self.hints_unresolved) < MAX_MEMBERS:
                self.hints_unresolved.add(pid)
        finally:
            if ref is not None:
                ref.close()

    def bind_root(self, child):
        identity = read_process_identity(child.handle, child.pid)
        with self.lock:
            require(self.root is None and self.scope.contains(child.handle),
                    "MANAGED_SCOPE_UNKNOWN", "Original root creation handle is not in the Job")
            key = self._store_identity(identity, "wrapper", root=True)
            require(key is not None, "MANAGED_OBSERVATION_UNAVAILABLE", "Cannot retain original Job root record")
            self.root, self.root_key = child, key
            if self.provenance is not None:
                self.provenance.capture(key, child.handle)
            duplicate = self.references.pop(key, None)
            if duplicate is not None:
                duplicate.close()
            self.exits.pop(key, None)

    def _collect_exits(self):
        if self.root_key is not None and self.root_key not in self.exits:
            try:
                code = self.root.poll()
                if code is not None:
                    self.exits[self.root_key] = {**self.records[self.root_key], "exit_code": code,
                                                 "exit_observed_at": now(), "exit_source": "direct_native_handle"}
                    if self.provenance is not None:
                        self.provenance.capture(self.root_key, self.root.handle, exited=True)
            except (ExecutionError, OSError):
                self.unknowns.add("MEMBER_EXIT_UNAVAILABLE")
        for key, ref in self.references.items():
            if key not in self.exits:
                try:
                    evidence = ref.exit_evidence()
                    if evidence is not None:
                        self.exits[key] = {**self.records[key], **evidence}
                        if self.provenance is not None:
                            self.provenance.capture(key, ref.handle, exited=True)
                except (ExecutionError, OSError):
                    self.unknowns.add("MEMBER_EXIT_UNAVAILABLE")

    def sample(self, completion=None):
        if completion is not None:
            self.stopping.set()
            self.thread.join()
            try:
                for _ in range(MAX_MEMBERS):
                    if not self._notification(0):
                        break
            except ExecutionError:
                self.unknowns.add("JOB_OBSERVATION_FAILED")
        with self.lock:
            self._collect_exits()
            missing = set(self.unknowns)
            verified = False
            if completion is not None:
                total = completion["total_processes"]
                if len(self.records) != total:
                    missing.add("JOB_MEMBER_COUNT_MISMATCH")
                if len(self.exits) != len(self.records) or self.root_key not in self.exits:
                    missing.add("MEMBER_EXIT_UNAVAILABLE")
                if completion["scope_id"] != self.scope.scope_id:
                    missing.add("JOB_SCOPE_MISMATCH")
                verified = not missing and completion["state"] == "EMPTY_CONFIRMED" and completion["active_processes"] == 0
            keys = sorted(self.records, key=lambda key: key != self.root_key)
            view = {"process_records": [self.records[key] for key in keys],
                    "process_exits": [self.exits[key] for key in keys if key in self.exits],
                    "all_observed_exited": self.root_key is not None and len(self.records) == len(self.exits),
                    "member_completeness": "VERIFIED_FOR_JOB" if verified else "UNKNOWN",
                    "exit_verification": "VERIFIED" if verified else "UNKNOWN",
                    "observation_unknowns": sorted(missing)}
            if completion is not None:
                view["membership_evidence"] = {"source": SOURCE, "scope_id": self.scope.scope_id,
                    "job_total_processes": total, "verified_members": len(self.records),
                    "verified_exits": len(self.exits), "unresolved_hint_pids": len(self.hints_unresolved),
                    "partial_live_snapshots": self.partial_live_snapshots,
                    "complete": verified}
                if self.provenance is not None:
                    view["process_provenance"] = self.provenance.archive(self.records)
            return view

    def in_scope(self, scope):
        # Each retained handle was checked before acceptance. The fixed Job
        # forbids breakaway; completed handles need not occur in a live list.
        return scope is self.scope and self.root_key is not None

    def close(self):
        if self.port is None:
            return
        self.stopping.set()
        self.thread.join()
        self.scope.api.CloseHandle(self.port)
        self.port = None
        for ref in self.references.values():
            ref.close()
        self.references.clear()


def event_excerpt(view):
    """Fit existing Run and event readers while preserving the complete view privately."""
    records, exits = [], []
    exit_by_identity = {JobProcessObserver._key(record): record for record in view["process_exits"]}
    remaining = MAX_EXCERPT_BYTES
    for record in view["process_records"][:MAX_EXCERPT_MEMBERS]:
        exit_record = exit_by_identity.get(JobProcessObserver._key(record))
        remaining -= _record_reservation(record)
        if remaining < 0:
            break
        records.append(record)
        if exit_record is not None:
            exits.append(exit_record)
    public = {key: value for key, value in view.items() if key != "process_provenance"}
    return {**public, "process_records": records, "process_exits": exits,
            "process_excerpt_truncated": len(records) < len(view["process_records"])}


def _record_reservation(record):
    # Reserve a future exit entry as well so the excerpt never shrinks at exit.
    exit_record = {**record, "exit_code": 2**32 - 1, "exit_observed_at": 2**63 - 1,
                   "exit_source": "retained_windows_handle"}
    return len(canonical_json([record, exit_record]).encode("utf-8")) + 2
