"""Private Windows creation-time Job scope. No termination, reopen or adoption API.

Only fixed, explicitly configured Backends use this seam. An unnamed, non-inherited Job is
owned by one execution attempt. CreateProcess's JOB_LIST binds before user code
can run; failed association never falls back. External services/WMI launches
are outside this declared scope. Outer host Job policies remain independent.
"""
import ctypes as C
from ctypes import wintypes as W
import msvcrt
import subprocess
import sys
import time

from .models import ExecutionError, identifier, now, require

POLICY = 'windows-job-list-v1'
JOB_LIST = 0x0002000D  # ProcThreadAttributeValue(JobList=13, input=True)
HANDLE_LIST = 0x00020002


class StartupInfo(C.Structure):
    _fields_ = [('cb',W.DWORD),('lpReserved',W.LPWSTR),('lpDesktop',W.LPWSTR),('lpTitle',W.LPWSTR),
                *[(n,W.DWORD) for n in ('dwX','dwY','dwXSize','dwYSize','dwXCountChars','dwYCountChars','dwFillAttribute','dwFlags')],
                ('wShowWindow',W.WORD),('cbReserved2',W.WORD),('lpReserved2',C.c_void_p),
                ('hStdInput',W.HANDLE),('hStdOutput',W.HANDLE),('hStdError',W.HANDLE)]


class StartupInfoEx(C.Structure):
    _fields_ = [('StartupInfo',StartupInfo),('lpAttributeList',C.c_void_p)]


class ProcessInfo(C.Structure):
    _fields_ = [('hProcess',W.HANDLE),('hThread',W.HANDLE),('dwProcessId',W.DWORD),('dwThreadId',W.DWORD)]


class BasicLimits(C.Structure):
    _fields_ = [('PerProcessUserTimeLimit',C.c_int64),('PerJobUserTimeLimit',C.c_int64),('LimitFlags',W.DWORD),
                ('MinimumWorkingSetSize',C.c_size_t),('MaximumWorkingSetSize',C.c_size_t),
                ('ActiveProcessLimit',W.DWORD),('Affinity',C.c_size_t),('PriorityClass',W.DWORD),('SchedulingClass',W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [('BasicLimitInformation',BasicLimits),('IoInfo',C.c_uint64*6),
                ('ProcessMemoryLimit',C.c_size_t),('JobMemoryLimit',C.c_size_t),
                ('PeakProcessMemoryUsed',C.c_size_t),('PeakJobMemoryUsed',C.c_size_t)]


class Accounting(C.Structure):
    _fields_ = [(n,C.c_int64) for n in ('TotalUserTime','TotalKernelTime','ThisPeriodTotalUserTime','ThisPeriodTotalKernelTime')] + [
        (n,W.DWORD) for n in ('TotalPageFaultCount','TotalProcesses','ActiveProcesses','TotalTerminatedProcesses')]


def api():
    require(sys.platform=='win32','UNSUPPORTED_PLATFORM','Managed scope requires Windows')
    k=C.WinDLL('kernel32',use_last_error=True)
    signatures={
        'CreateJobObjectW':([C.c_void_p,W.LPCWSTR],W.HANDLE),
        'CloseHandle':([W.HANDLE],W.BOOL),
        'QueryInformationJobObject':([W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p],W.BOOL),
        'InitializeProcThreadAttributeList':([C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)],W.BOOL),
        'UpdateProcThreadAttribute':([C.c_void_p,W.DWORD,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p],W.BOOL),
        'DeleteProcThreadAttributeList':([C.c_void_p],None),
        'CreateProcessW':([W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.c_void_p,C.POINTER(ProcessInfo)],W.BOOL),
        'IsProcessInJob':([W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)],W.BOOL),
        'WaitForSingleObject':([W.HANDLE,W.DWORD],W.DWORD),
        'GetExitCodeProcess':([W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
        'GetCurrentProcess':([],W.HANDLE),
        'DuplicateHandle':([W.HANDLE,W.HANDLE,W.HANDLE,C.POINTER(W.HANDLE),W.DWORD,W.BOOL,W.DWORD],W.BOOL),
    }
    for n,(args,result) in signatures.items():
        f=getattr(k,n);f.argtypes=args;f.restype=result
    return k


def checked(result, code):
    if not result:
        raise ExecutionError(code, 'Windows managed scope operation failed; no fallback',stage='MANAGED_SCOPE')


class CreatedProcess:
    """Retained native creation handle; closing never terminates the process."""
    def __init__(self,k,info):
        self.api,self.handle,self.pid=k,info.hProcess,int(info.dwProcessId)
        self.returncode=None
        k.CloseHandle(info.hThread)

    def poll(self):
        value=self.api.WaitForSingleObject(self.handle,0)
        if value==258:return None
        require(value==0,'PROCESS_EXIT_UNKNOWN','Native creation handle wait failed')
        code=W.DWORD();checked(self.api.GetExitCodeProcess(self.handle,C.byref(code)),'PROCESS_EXIT_UNKNOWN')
        self.returncode=code.value
        return self.returncode

    def wait(self,timeout=None):
        require(timeout is not None and 0<=timeout<=5,'INVALID_REQUEST','Only bounded process wait supported')
        value=self.api.WaitForSingleObject(self.handle,int(timeout*1000))
        if value==258:raise ExecutionError('PROCESS_EXIT_UNKNOWN','Bounded process wait expired')
        return self.poll()

    def close(self):
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None


class ManagedScope:
    def __init__(self,run):
        self.api=api();self.handle=None;self.started=False;self.attempted=False
        self.binding={k:run[k] for k in ('project_instance_id','run_id','plan_digest','phase_attempt_id','owner_id','owner_epoch')}
        self.scope_id=identifier('scope')
        self.handle=self.api.CreateJobObjectW(None,None)  # unnamed: cannot reopen a same-name replacement
        checked(self.handle,'MANAGED_SCOPE_UNAVAILABLE')
        try:self._limits()
        except BaseException:self.close();raise

    def _limits(self):
        require(self.handle is not None,'MANAGED_SCOPE_UNKNOWN','Original scope handle is unavailable')
        limits=ExtendedLimits()
        checked(self.api.QueryInformationJobObject(self.handle,9,C.byref(limits),C.sizeof(limits),None),'MANAGED_SCOPE_UNKNOWN')
        require(limits.BasicLimitInformation.LimitFlags==0,'MANAGED_SCOPE_POLICY_CHANGED','Unexpected scope limits or breakaway policy')

    def description(self):
        return {**self.binding,'scope_id':self.scope_id,'policy':POLICY,'binding':'CREATE_PROCESS_JOB_LIST',
                'scope':'ROOT_AND_INHERITING_CREATEPROCESS_DESCENDANTS','kill_on_job_close':False,
                'breakaway_allowed':False,'named':False,'observed_at':now()}

    def create(self,command,*,cwd,env):
        sys.audit('abqjobpilot.managed_create',tuple(command),cwd,dict(env))
        return self._create(command[0],subprocess.list2cmdline(command),cwd,env,())

    def create_standard(self,call,out,err):
        """Private fixed-Backend seam; exact batch quoting is supplied by call_data.

        Only duplicate stdin NUL and the two per-Run files. HANDLE_LIST prevents
        inheriting the Job, owner lock, SQLite, IPC or other live handles.
        """
        sys.audit('abqjobpilot.managed_standard_create',call['application'],call['command_line'],call['cwd'])
        duplicates=[]
        try:
            with open('NUL','rb') as stdin:
                current=self.api.GetCurrentProcess()
                for stream in (stdin,out,err):
                    handle=W.HANDLE()
                    checked(self.api.DuplicateHandle(current,msvcrt.get_osfhandle(stream.fileno()),current,
                        C.byref(handle),0,True,2),'MANAGED_STDIO_UNAVAILABLE')
                    duplicates.append(handle.value)
                require(type(call.get('start_not_after')) is int,'START_WINDOW_EXPIRED','Explicit fixed creation deadline required')
                return self._create(call['application'],call['command_line'],call['cwd'],call['environment'],duplicates,call['start_not_after'])
        finally:
            for handle in duplicates:self.api.CloseHandle(handle)

    def _create(self,application,command_line,cwd,env,std_handles,start_not_after=None):
        require(not self.attempted,'START_ALREADY_ATTEMPTED','A scope accepts exactly one root creation attempt')
        self.attempted=True;self._limits()
        size=C.c_size_t();k=self.api
        count=2 if std_handles else 1
        k.InitializeProcThreadAttributeList(None,count,0,C.byref(size))
        require(0<size.value<65536,'MANAGED_SCOPE_UNAVAILABLE','Attribute list size unavailable')
        buffer=C.create_string_buffer(size.value);attrs=C.cast(buffer,C.c_void_p)
        checked(k.InitializeProcThreadAttributeList(attrs,count,0,C.byref(size)),'MANAGED_SCOPE_UNAVAILABLE')
        try:
            jobs=(W.HANDLE*1)(self.handle)
            checked(k.UpdateProcThreadAttribute(attrs,0,JOB_LIST,jobs,C.sizeof(jobs),None,None),'MANAGED_SCOPE_UNAVAILABLE')
            startup=StartupInfoEx();startup.StartupInfo.cb=C.sizeof(startup);startup.lpAttributeList=attrs
            startup.StartupInfo.dwFlags=0x100  # explicit null std handles; no inherited console/pipe/secret handles
            if std_handles:
                require(len(std_handles)==3,'MANAGED_STDIO_UNAVAILABLE','Exactly three explicit std handles required')
                handles=(W.HANDLE*3)(*std_handles)
                checked(k.UpdateProcThreadAttribute(attrs,0,HANDLE_LIST,handles,C.sizeof(handles),None,None),'MANAGED_STDIO_UNAVAILABLE')
                startup.StartupInfo.hStdInput,startup.StartupInfo.hStdOutput,startup.StartupInfo.hStdError=std_handles
            line=C.create_unicode_buffer(command_line)
            environment=C.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted(env.items()))+'\0\0')
            info=ProcessInfo()
            if start_not_after is not None:
                require(now()<start_not_after,'START_WINDOW_EXPIRED','Native creation window elapsed; no deferred launch')
            checked(k.CreateProcessW(application,line,None,None,bool(std_handles),0x00080000|0x08000000|0x00000400,
                                     environment,cwd,C.byref(startup),C.byref(info)),'MANAGED_CREATE_FAILED')
            process=CreatedProcess(k,info)
            try:
                belongs=W.BOOL()
                checked(k.IsProcessInJob(process.handle,self.handle,C.byref(belongs)),'MANAGED_SCOPE_UNKNOWN')
                require(bool(belongs.value),'MANAGED_SCOPE_UNKNOWN','Created root membership could not be verified')
                self.started=True
                return process
            except BaseException:process.close();raise
        finally:k.DeleteProcThreadAttributeList(attrs)

    def query(self):
        self._limits();data=Accounting()
        checked(self.api.QueryInformationJobObject(self.handle,1,C.byref(data),C.sizeof(data),None),'MANAGED_SCOPE_UNKNOWN')
        return {**self.description(),'source':'QueryInformationJobObject.BasicAccounting',
                'query_monotonic_ns':time.monotonic_ns(),'creation_confirmed':self.started,
                'pending_additions':False,'active_processes':data.ActiveProcesses,'total_processes':data.TotalProcesses,
                'limit_terminated_processes':data.TotalTerminatedProcesses,
                'state':'EMPTY_CONFIRMED' if self.started and data.TotalProcesses>0 and data.ActiveProcesses==0 else 'NOT_COMPLETE'}

    def contains(self,process_handle):
        self._limits();member=W.BOOL()
        checked(self.api.IsProcessInJob(process_handle,self.handle,C.byref(member)),'MANAGED_SCOPE_UNKNOWN')
        return bool(member.value)

    def close(self):
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None


def check_completion(proof,run):
    require(isinstance(proof,dict) and proof.get('policy')==POLICY and proof.get('state')=='EMPTY_CONFIRMED'
            and proof.get('creation_confirmed') is True and proof.get('pending_additions') is False
            and proof.get('active_processes')==0 and proof.get('total_processes',0)>0
            and proof.get('limit_terminated_processes')==0 and proof.get('kill_on_job_close') is False
            and proof.get('breakaway_allowed') is False and proof.get('source')=='QueryInformationJobObject.BasicAccounting'
            and all(proof.get(k)==run[k] for k in ('project_instance_id','run_id','plan_digest','phase_attempt_id','owner_id','owner_epoch')),
            'MANAGED_SCOPE_UNKNOWN','No bound successful-creation empty-scope evidence; keep slot')
