"""Read-only Windows identity/Job queries and bounded candidate discovery.

No Job creation/configuration, breakaway, termination or background thread.
"""
import ctypes as c
from ctypes import wintypes as w
import os
import sys
from pathlib import Path

from records import require, stamp


def api():
    k = c.WinDLL('kernel32', use_last_error=True)
    k.GetCurrentProcess.restype = w.HANDLE
    k.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, c.POINTER(w.BOOL)]
    k.IsProcessInJob.restype = w.BOOL
    k.GetProcessTimes.argtypes = [w.HANDLE] * 5
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
    k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    k.GetExitCodeProcess.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    k.CloseHandle.argtypes = [w.HANDLE]
    k.GetStdHandle.argtypes = [w.DWORD]
    k.GetStdHandle.restype = w.HANDLE
    k.GetFileType.argtypes = [w.HANDLE]
    return k


def handle_identity(handle, pid):
    k = api()
    times = [c.c_uint64() for _ in range(4)]
    require(bool(k.GetProcessTimes(handle, *(c.byref(t) for t in times))), 'IDENTITY_UNKNOWN')
    name, length = c.create_unicode_buffer(32768), w.DWORD(32768)
    require(bool(k.QueryFullProcessImageNameW(handle, 0, name, c.byref(length))), 'IDENTITY_UNKNOWN')
    return {'pid': pid, 'creation_time_100ns': times[0].value, 'image_path': name.value}


def current_host():
    require(os.name == 'nt', 'WINDOWS_REQUIRED')
    k = api()
    member = w.BOOL()
    success = bool(k.IsProcessInJob(k.GetCurrentProcess(), None, c.byref(member)))
    return {'observed_at_ns': stamp(), 'identity': handle_identity(k.GetCurrentProcess(), os.getpid()),
            'interpreter': sys.executable, 'python': sys.version.split()[0],
            'job_query_succeeded': success, 'in_any_job': bool(member.value) if success else None,
            'job_query_error': None if success else c.get_last_error(),
            'controller_standard_handles': {
                name: {'file_type': k.GetFileType(k.GetStdHandle(w.DWORD(number))),
                       'ownership': 'borrowed; never closed by controller'}
                for name, number in [('stdout', -11), ('stderr', -12)]}}


def admit(host):
    require(host.get('job_query_succeeded') is True and host.get('in_any_job') is False,
            'HOST_JOB_BLOCKED')


def process_rows():
    """Snapshot metadata in memory only; unrelated processes are never logged."""
    class Entry(c.Structure):
        _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD),
                    ('heap', c.c_size_t), ('module', w.DWORD), ('threads', w.DWORD),
                    ('parent', w.DWORD), ('priority', w.LONG), ('flags', w.DWORD),
                    ('exe', w.WCHAR * 260)]
    k = api()
    k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    k.CreateToolhelp32Snapshot.restype = w.HANDLE
    k.Process32FirstW.argtypes = [w.HANDLE, c.POINTER(Entry)]
    k.Process32NextW.argtypes = [w.HANDLE, c.POINTER(Entry)]
    handle = k.CreateToolhelp32Snapshot(2, 0)
    require(handle not in (None, c.c_void_p(-1).value), 'PROCESS_SNAPSHOT_UNKNOWN')
    rows = []
    try:
        item = Entry(); item.size = c.sizeof(item)
        ok = k.Process32FirstW(handle, c.byref(item))
        require(bool(ok), 'PROCESS_SNAPSHOT_UNKNOWN')
        while ok:
            rows.append((item.pid, item.parent))
            require(len(rows) <= 16384, 'PROCESS_SNAPSHOT_LIMIT')
            ok = k.Process32NextW(handle, c.byref(item))
    finally:
        k.CloseHandle(handle)
    return rows


class ObservedProcesses:
    def __init__(self, child, journal):
        # Direct OS handle is retained by Popen; never reopen a fast-exiting PID.
        self.child, self.journal = child, journal
        self.direct = handle_identity(int(child._handle), child.pid)
        self.members = {}
        self.seen_exits = {}
        self.unknown = set()
        self.last_sample_at_ns = None
        journal.append('PROCESS_IDENTIFIED', role='direct_cmd_or_test_launcher',
                       source='direct_Popen_handle', identity=self.direct)

    def sample(self):
        from abqjobpilot.execution.process_handles import ProcessReference
        k = api()
        self.last_sample_at_ns = stamp()
        if self.child.poll() is not None and 'direct' not in self.seen_exits:
            record = {**self.direct, 'exit_code': self.child.returncode,
                      'exit_observed_at_ns': stamp(), 'source': 'direct_Popen_handle'}
            self.seen_exits['direct'] = record
            self.journal.append('PROCESS_EXIT_OBSERVED', record=record)
        try:
            rows = process_rows()
            # Only parents whose exact retained identity is still live can anchor discovery.
            live = {self.child.pid: self.direct} if self.child.poll() is None else {}
            for pid, ref in self.members.items():
                if ref.exit_evidence() is None:
                    live[pid] = ref.identity
            for _ in range(8):
                added = False
                for pid, parent in rows:
                    if pid in self.members or pid == self.child.pid or parent not in live:
                        continue
                    if len(self.members) >= 128:
                        self.unknown.add('MEMBER_LIMIT'); break
                    try:
                        ref = ProcessReference(pid)
                        if ref.identity['creation_time_100ns'] < live[parent]['creation_time_100ns']:
                            ref.close(); self.unknown.add('IDENTITY_TIME_CONFLICT'); continue
                        self.members[pid] = ref
                        ref._r011_parent = dict(live[parent])
                        if ref.exit_evidence() is None:
                            live[pid] = ref.identity
                        added = True
                    except Exception:
                        self.unknown.add('CANDIDATE_IDENTITY_UNAVAILABLE')
                if not added:
                    break
        except Exception:
            self.unknown.add('DISCOVERY_INCOMPLETE')
        # Persistence errors must propagate, not become a discovery warning.
        for pid, ref in self.members.items():
            if not getattr(ref, '_r011_recorded', False):
                self.journal.append('PROCESS_CANDIDATE_IDENTIFIED',
                    source='OS_parent_candidate_and_retained_identity', parent=ref._r011_parent,
                    identity=ref.identity, attribution='CANDIDATE_NOT_PROVEN_SOLVER_MEMBER')
                ref._r011_recorded = True
        for pid, ref in self.members.items():
            if str(pid) not in self.seen_exits:
                evidence = ref.exit_evidence()
                if evidence is not None:
                    self.seen_exits[str(pid)] = evidence
                    self.journal.append('PROCESS_EXIT_OBSERVED', record=evidence)
        return self.view()

    def view(self):
        return {'direct_identity': self.direct, 'exits': list(self.seen_exits.values()),
                'candidate_identities': [r.identity for r in self.members.values()],
                'all_observed_exited': len(self.seen_exits) == len(self.members) + 1,
                'member_completeness': 'UNKNOWN', 'overall_exit': 'UNKNOWN',
                'unknowns': sorted(self.unknown), 'last_sample_at_ns': self.last_sample_at_ns}

    def close(self):
        for ref in self.members.values():
            ref.close()


def close_child_reference(child):
    # Python 3.12 Windows-specific, bound in the candidate's interpreter materials.
    # Close our process reference, never wait or terminate. Do not fake a returncode.
    child._handle.Close()
    child._child_created = False  # Prevent destructor polling a closed handle.
