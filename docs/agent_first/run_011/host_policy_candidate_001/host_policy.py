"""Explicit limited operator policy. One evaluator for check and execution admission.

Job membership is observed, not forged or inferred safe. This policy accepts a
weaker lifetime contract than no-Job, subject to NEW candidate approval outside code.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path

from records import require, Refusal
from windows_host import current_host, process_rows, api

POLICY = 'operator_powershell_retained_session_v1'
POWERSHELL = Path(r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe')
VENV = Path(r'D:\XianLab\envs\LangChainEnv\Scripts\python.exe')
BASE = Path(r'D:\Program Files\Python312\python.exe')


def evaluate(host):
    """Pure deterministic result; a passing result is NOT authorization."""
    reasons=[]
    if host.get('policy') != POLICY: reasons.append('HOST_POLICY_MISMATCH')
    if host.get('job_query_succeeded') is not True or type(host.get('in_any_job')) is not bool:
        reasons.append('HOST_JOB_QUERY_UNKNOWN')
    if host.get('interpreter') != str(VENV) or host.get('python') != '3.12.10':
        reasons.append('HOST_INTERPRETER_MISMATCH')
    if host.get('identity',{}).get('image_path') != str(BASE): reasons.append('HOST_IMAGE_MISMATCH')
    if host.get('chain_verified') is not True: reasons.append('HOST_CHAIN_UNVERIFIED')
    roles=host.get('chain',{})
    for role, image in [('venv_launcher',VENV),('powershell',POWERSHELL)]:
        record=roles.get(role,{})
        identity=record.get('identity',{})
        if identity.get('image_path') != str(image) or type(identity.get('creation_time_100ns')) is not int:
            reasons.append('HOST_PARENT_IDENTITY_MISMATCH')
        if record.get('observed_alive') is not True: reasons.append('HOST_PARENT_NOT_OBSERVED_ALIVE')
        if record.get('job_query_succeeded') is not True or type(record.get('in_any_job')) is not bool:
            reasons.append('HOST_PARENT_JOB_QUERY_UNKNOWN')
    session=host.get('session_id')
    if type(session) is not int or session <= 0 or any(r.get('session_id')!=session for r in roles.values()):
        reasons.append('HOST_SESSION_MISMATCH')
    if host.get('powershell_attached_to_same_console') is not True:
        reasons.append('HOST_CONSOLE_UNVERIFIED')
    return {'policy':POLICY, 'eligible':not reasons, 'reasons':sorted(set(reasons)),
            'lifetime_claim':'CONDITIONAL_OPERATOR_SESSION_RETAINED',
            'full_job_hierarchy':'UNKNOWN', 'terminal_closure_survival':'NOT_VERIFIED',
            'abaqus_chain':'NOT_VERIFIED', 'authorization':'NOT_GRANTED'}


def admit(host):
    result=evaluate(host)
    require(result['eligible'], result['reasons'][0] if result['reasons'] else 'HOST_POLICY_BLOCKED')


def observe():
    """Fresh OS queries in the actual check/execute process, no Job configuration."""
    from abqjobpilot.execution.process_handles import ProcessReference
    value=current_host()
    value.update(policy=POLICY, chain={}, chain_verified=False,
                 powershell_attached_to_same_console=False)
    k=api()
    k.ProcessIdToSessionId.argtypes=[wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
    k.ProcessIdToSessionId.restype=wintypes.BOOL
    k.GetConsoleProcessList.argtypes=[ctypes.POINTER(wintypes.DWORD),wintypes.DWORD]
    k.GetConsoleProcessList.restype=wintypes.DWORD
    def session(pid):
        result=wintypes.DWORD()
        require(bool(k.ProcessIdToSessionId(pid,ctypes.byref(result))), 'HOST_SESSION_QUERY_FAILED')
        return result.value
    refs=[]
    try:
        value['session_id']=session(os.getpid())
        parents=dict(process_rows())
        launcher=parents.get(os.getpid())
        parent=parents.get(launcher)
        require(type(launcher) is int and type(parent) is int, 'HOST_PARENT_MISSING')
        for role,pid,expected in [('venv_launcher',launcher,VENV),('powershell',parent,POWERSHELL)]:
            ref=ProcessReference(pid); refs.append(ref)
            require(Path(ref.identity['image_path']) == expected, 'HOST_PARENT_IMAGE_MISMATCH')
            flag=wintypes.BOOL()
            ok=bool(k.IsProcessInJob(ref.handle,None,ctypes.byref(flag)))
            value['chain'][role]={'identity':ref.identity,'observed_alive':ref.exit_evidence() is None,
                'session_id':session(pid),'job_query_succeeded':ok,'in_any_job':bool(flag.value) if ok else None}
        console=(wintypes.DWORD*64)()
        count=k.GetConsoleProcessList(console,64)
        require(0 < count <= 64, 'HOST_CONSOLE_QUERY_FAILED')
        value['powershell_attached_to_same_console']=parent in list(console[:count])
        # Recheck links/retained identities after collecting the bounded view.
        again=dict(process_rows())
        require(again.get(os.getpid())==launcher and again.get(launcher)==parent, 'HOST_CHAIN_CHANGED')
        require(all(r.exit_evidence() is None for r in refs), 'HOST_PARENT_EXITED')
        own=value['identity']['creation_time_100ns']
        require(refs[1].identity['creation_time_100ns'] <= refs[0].identity['creation_time_100ns'] <= own,
                'HOST_CHAIN_IDENTITY_ORDER')
        value['chain_verified']=True
        return value
    finally:
        for ref in refs: ref.close()
