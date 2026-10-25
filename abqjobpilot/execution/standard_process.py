"""Read-only host admission and bounded OS observation for the opt-in Backend.

Adapted from Run011 windows_host's observed-subset collector. No Job mutation,
breakaway, adoption or termination. A descendant candidate is NOT a complete
Solver membership proof. All retained handles are non-inheritable.
"""
import ctypes
import os
from pathlib import Path
import sys

from .models import now, require
from .process_handles import ProcessReference


def kernel():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    k.GetStdHandle.argtypes = [ctypes.c_uint32]; k.GetStdHandle.restype = ctypes.c_void_p
    k.GetFileType.argtypes = [ctypes.c_void_p]
    return k


def check_host(config):
    require(sys.platform == 'win32', 'HOST_UNVERIFIED', 'Windows service host required')
    k = kernel(); member = ctypes.c_int()
    ok = bool(k.IsProcessInJob(k.GetCurrentProcess(), None, ctypes.byref(member)))
    with_reference = ProcessReference(os.getpid())
    try: identity = with_reference.identity
    finally: with_reference.close()
    handles = [k.GetFileType(k.GetStdHandle(ctypes.c_uint32(n))) for n in (-11,-12)]
    # This policy permits a recorded Job under a *new*, limited service-session
    # contract. It promises no survival across owner failure, Job/session closure.
    # It does not reuse the PowerShell host PASS or inspect a single Job flag.
    eligible = ok and Path(sys.executable) == Path(config.value()['interpreter']) and handles == [1,1]
    return {'policy':config.value()['host_policy'],'observed_at':now(),'process':identity,
        'job_query_succeeded':ok,'in_any_job':bool(member.value) if ok else None,
        'standard_file_handles':handles,'eligible':eligible,
        'scope':'independent_owner_while_windows_session_remains_alive',
        'full_job_hierarchy':'UNKNOWN','abaqus_survival':'NOT_VALIDATED',
        'owner_or_session_exit_survival':'NOT_PROMISED'}


def process_rows():
    class Entry(ctypes.Structure):
        _fields_ = [('size',ctypes.c_uint32),('usage',ctypes.c_uint32),('pid',ctypes.c_uint32),
            ('heap',ctypes.c_size_t),('module',ctypes.c_uint32),('threads',ctypes.c_uint32),
            ('parent',ctypes.c_uint32),('priority',ctypes.c_long),('flags',ctypes.c_uint32),('exe',ctypes.c_wchar*260)]
    k=kernel()
    k.CreateToolhelp32Snapshot.argtypes=[ctypes.c_uint32,ctypes.c_uint32]; k.CreateToolhelp32Snapshot.restype=ctypes.c_void_p
    k.Process32FirstW.argtypes=[ctypes.c_void_p,ctypes.POINTER(Entry)]
    k.Process32NextW.argtypes=[ctypes.c_void_p,ctypes.POINTER(Entry)]
    k.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=k.CreateToolhelp32Snapshot(2,0)
    require(handle not in (None,ctypes.c_void_p(-1).value),'PROCESS_IDENTITY_UNKNOWN','Process snapshot unavailable')
    rows=[]
    try:
        item=Entry(); item.size=ctypes.sizeof(item); ok=k.Process32FirstW(handle,ctypes.byref(item))
        require(bool(ok),'PROCESS_IDENTITY_UNKNOWN','Process snapshot unavailable')
        while ok:
            rows.append((item.pid,item.parent)); require(len(rows)<=16384,'LIMIT_EXCEEDED','Process snapshot bound')
            ok=k.Process32NextW(handle,ctypes.byref(item))
    finally: k.CloseHandle(handle)
    return rows


class Observer:
    def __init__(self, child):
        self.child=child
        # Popen retains the direct object even if it exits before OpenProcess.
        k=kernel(); handle=int(child.handle if hasattr(child,'handle') else child._handle)
        k.GetProcessTimes.argtypes=[ctypes.c_void_p]*5
        k.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p]
        times=[ctypes.c_uint64() for _ in range(4)]
        require(bool(k.GetProcessTimes(handle,*(ctypes.byref(v) for v in times))), 'PROCESS_IDENTITY_UNKNOWN','Direct identity unavailable')
        buf=ctypes.create_unicode_buffer(32768); size=ctypes.c_uint32(32768)
        require(bool(k.QueryFullProcessImageNameW(handle,0,buf,ctypes.byref(size))), 'PROCESS_IDENTITY_UNKNOWN','Direct image unavailable')
        self.direct={'pid':child.pid,'creation_time_100ns':times[0].value,'image_path':buf.value,
                     'role':'wrapper','identity_status':'VERIFIED','observed_at':now()}
        self.refs={}; self.records=[self.direct]; self.exits=[]; self.unknown=set()

    def sample(self):
        if self.child.poll() is not None and not any(e['role']=='wrapper' for e in self.exits):
            self.exits.append({**self.direct,'exit_code':self.child.returncode,'exit_observed_at':now(),
                              'exit_source':'direct_native_handle' if hasattr(self.child,'handle') else 'direct_Popen_handle'})
        live={self.direct['pid']:self.direct} if self.child.poll() is None else {}
        for pid,ref in self.refs.items():
            if ref.exit_evidence() is None: live[pid]=ref.identity
        try:
            rows=process_rows()
            for _ in range(8):
                added=False
                for pid,parent in rows:
                    if pid in self.refs or pid==self.child.pid or parent not in live: continue
                    if len(self.records)>=16: self.unknown.add('MEMBER_LIMIT'); break
                    try:
                        ref=ProcessReference(pid)
                        if ref.identity['creation_time_100ns']<live[parent]['creation_time_100ns']:
                            ref.close(); self.unknown.add('IDENTITY_CONFLICT'); continue
                        self.refs[pid]=ref
                        self.records.append({**ref.identity,'role':'candidate_'+str(pid),'identity_status':'VERIFIED',
                            'observed_at':now(),'attribution':'OS_parent_candidate_not_complete_solver_membership'})
                        if ref.exit_evidence() is None: live[pid]=ref.identity
                        added=True
                    except Exception: self.unknown.add('CANDIDATE_IDENTITY_UNAVAILABLE')
                if not added: break
        except Exception: self.unknown.add('DISCOVERY_INCOMPLETE')
        for record in self.records[1:]:
            if any(e['role']==record['role'] for e in self.exits): continue
            exit=self.refs[record['pid']].exit_evidence()
            if exit: self.exits.append({**record,**exit})
        return {'process_records':list(self.records),'process_exits':list(self.exits),
            'member_completeness':'UNKNOWN','exit_verification':'UNKNOWN',
            'all_observed_exited':len(self.records)==len(self.exits),'observation_unknowns':sorted(self.unknown)}

    def close(self):
        for ref in self.refs.values(): ref.close()

    def in_scope(self,scope):
        handles=[self.child.handle if hasattr(self.child,'handle') else int(self.child._handle)]
        handles.extend(ref.handle for ref in self.refs.values())
        return all(scope.contains(handle) for handle in handles)


def close_reference(child):
    # Explicitly close only our Popen handle. Do not use Popen context manager,
    # communicate(timeout), kill-on-close resources, terminate or forced cleanup.
    if hasattr(child,'handle'):child.close()
    else:
        child._handle.Close()
        child._child_created=False
