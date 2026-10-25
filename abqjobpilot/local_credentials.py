"""Windows-local storage protection for existing IPC and operator capabilities.

No new authentication protocol. DPAPI current-user + host/instance entropy;
private directories are created with a protected user/SYSTEM DACL. Never emit
decrypted objects in diagnostics. Same-user arbitrary code is not isolated.
"""
import base64
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path

from .execution.models import ExecutionError, canonical_json, digest, fields, require
from .execution.paths import no_reparse

FORMAT = 'windows-user-dpapi-v1'


def _api(dll, name, args, result=W.BOOL):
    fn = getattr(C.WinDLL(dll, use_last_error=True), name)
    fn.argtypes, fn.restype = args, result
    return fn


def _ok(result):
    require(bool(result), 'LOCAL_CREDENTIAL_UNAVAILABLE', 'Local Windows credential protection failed')


def user_sid():
    require(os.name == 'nt', 'HOST_UNSUPPORTED', 'Windows user protection is required')
    handle = W.HANDLE(); size = W.DWORD()
    current = _api('kernel32', 'GetCurrentProcess', [], W.HANDLE)()
    _ok(_api('advapi32', 'OpenProcessToken', [W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)])(current,8,C.byref(handle)))
    try:
        get = _api('advapi32','GetTokenInformation',[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)])
        get(handle,1,None,0,C.byref(size))
        require(0 < size.value < 65536, 'LOCAL_CREDENTIAL_UNAVAILABLE','Invalid user identity size')
        buf=C.create_string_buffer(size.value);_ok(get(handle,1,buf,size,C.byref(size)))
        sid=C.cast(buf,C.POINTER(C.c_void_p))[0]; output=C.c_void_p()
        _ok(_api('advapi32','ConvertSidToStringSidW',[C.c_void_p,C.POINTER(C.c_void_p)])(sid,C.byref(output)))
        try:return C.wstring_at(output)
        finally:_api('kernel32','LocalFree',[C.c_void_p],C.c_void_p)(output)
    finally:_api('kernel32','CloseHandle',[W.HANDLE])(handle)


def host_binding():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            machine=winreg.QueryValueEx(key,'MachineGuid')[0]
        return digest({'user':user_sid(),'machine':machine})
    except OSError:
        raise ExecutionError('LOCAL_CREDENTIAL_UNAVAILABLE','Local host identity unavailable') from None


def private_directory(path):
    """Exclusive new directory, restricted from its first instant; no ACL repair."""
    path=Path(path);no_reparse(path)
    class SA(C.Structure):
        _fields_=[('length',W.DWORD),('descriptor',C.c_void_p),('inherit',W.BOOL)]
    sd=C.c_void_p()
    sddl='D:P(A;OICI;FA;;;'+user_sid()+')(A;OICI;FA;;;SY)'
    _ok(_api('advapi32','ConvertStringSecurityDescriptorToSecurityDescriptorW',
             [W.LPCWSTR,W.DWORD,C.POINTER(C.c_void_p),C.c_void_p])(sddl,1,C.byref(sd),None))
    try:
        sa=SA(C.sizeof(SA),sd,False)
        _ok(_api('kernel32','CreateDirectoryW',[W.LPCWSTR,C.POINTER(SA)])(str(path),C.byref(sa)))
    finally:_api('kernel32','LocalFree',[C.c_void_p],C.c_void_p)(sd)


def _crypt(data, entropy, decrypt=False):
    class Blob(C.Structure):
        _fields_=[('size',W.DWORD),('data',C.c_void_p)]
    buf=C.create_string_buffer(data);ebuf=C.create_string_buffer(entropy)
    src=Blob(len(data),C.cast(buf,C.c_void_p)); ent=Blob(len(entropy),C.cast(ebuf,C.c_void_p));out=Blob()
    fn=_api('crypt32','CryptUnprotectData' if decrypt else 'CryptProtectData',
            [C.POINTER(Blob),C.c_void_p,C.POINTER(Blob),C.c_void_p,C.c_void_p,W.DWORD,C.POINTER(Blob)])
    _ok(fn(C.byref(src),None,C.byref(ent),None,None,1,C.byref(out)))  # UI_FORBIDDEN, never LOCAL_MACHINE
    try:
        require(out.size<=65536,'LIMIT_EXCEEDED','Protected document exceeds bound')
        return C.string_at(out.data,out.size)
    finally:_api('kernel32','LocalFree',[C.c_void_p],C.c_void_p)(out.data)


def seal(context, value):
    binding=host_binding();raw=canonical_json(value).encode()
    require(len(raw)<=32768,'LIMIT_EXCEEDED','Private document exceeds bound')
    encrypted=_crypt(raw,(context.context_digest+binding).encode())
    return {'format':FORMAT,'context_digest':context.context_digest,'host_binding':binding,
            'ciphertext':base64.b64encode(encrypted).decode('ascii')}


def unseal(context, value):
    try:
        fields(value,('format','context_digest','host_binding','ciphertext'))
        require(value['format']==FORMAT and value['context_digest']==context.context_digest
                and value['host_binding']==host_binding(), 'LOCAL_CREDENTIAL_UNAVAILABLE','Credential host or instance mismatch')
        raw=base64.b64decode(value['ciphertext'],validate=True)
        return json.loads(_crypt(raw,(context.context_digest+value['host_binding']).encode(),True))
    except (ValueError,TypeError,KeyError,ExecutionError):
        raise ExecutionError('LOCAL_CREDENTIAL_UNAVAILABLE','Local protected credential cannot be used; no fallback') from None


def protected_project(context):
    # Permanent creation marker also prevents downgrade before publication.
    return (Path(context.test_root)/'.agent-first-creation.json').exists() or (Path(context.test_root)/'agent_project.json').exists()


def read_private(context, path):
    from .service_discovery import read_document
    value=read_document(path)
    if protected_project(context):return unseal(context,value)
    return value  # Historical experimental handoffs retain their original contract.


def private_value(context, value):
    return seal(context,value) if protected_project(context) else value
