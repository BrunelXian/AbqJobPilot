"""Read-only observations of this Windows host, not proof of the outer Job hierarchy."""
import ctypes as C
import sys
from .execution.models import now, require
from .execution.ownership import current_process_identity


def observe_host(*, disk_output=False):
    from .execution.managed_process import ExtendedLimits
    require(sys.platform=='win32','UNSUPPORTED_PLATFORM','Service host requires Windows')
    api=C.WinDLL('kernel32',use_last_error=True)
    api.GetCurrentProcess.restype=C.c_void_p
    api.IsProcessInJob.argtypes=[C.c_void_p,C.c_void_p,C.POINTER(C.c_int)]
    inside=C.c_int()
    require(bool(api.IsProcessInJob(api.GetCurrentProcess(),None,C.byref(inside))),
            'HOST_UNCONFIRMED','Cannot query service host Job association')
    flags=None
    if inside.value:
        value=ExtendedLimits()
        api.QueryInformationJobObject.argtypes=[C.c_void_p,C.c_int,C.c_void_p,C.c_uint32,C.c_void_p]
        require(bool(api.QueryInformationJobObject(None,9,C.byref(value),C.sizeof(value),None)),
                'HOST_UNCONFIRMED','Cannot query direct host Job limits')
        flags=value.BasicLimitInformation.LimitFlags
    api.GetStdHandle.argtypes=[C.c_uint32];api.GetStdHandle.restype=C.c_void_p
    api.GetFileType.argtypes=[C.c_void_p];api.GetFileType.restype=C.c_uint32
    outputs={name:api.GetFileType(api.GetStdHandle(number & 0xffffffff))
             for name,number in [('stdout',-11),('stderr',-12)]}
    if disk_output:require(all(v==1 for v in outputs.values()),'HOST_UNCONFIRMED','Owner output must be independent disk files')
    return {'process':current_process_identity(),'observed_at':now(),'in_any_job':bool(inside.value),
            'direct_job_flags':flags,'direct_kill_on_close':bool(flags & 0x2000) if flags is not None else None,
            'output_file_types':outputs,'outer_job_hierarchy':'UNKNOWN',
            'policy':'ordinary-create-no-breakaway; retained desktop session; GUI-exit acceptance only'}
