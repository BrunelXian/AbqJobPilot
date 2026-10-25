"""New explicit product instances only. No external processes in this module."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from abqjobpilot.product_project import create_project, open_project, inspect_project
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.service_discovery import project_identity
from abqjobpilot.execution.models import ExecutionError, canonical_json
from abqjobpilot.execution.store import open_existing_read_only
from abqjobpilot.local_credentials import seal,unseal,host_binding,user_sid,_api


@pytest.fixture(autouse=True)
def no_launch(monkeypatch):
    def blocked(*a,**k):raise AssertionError('Project operations must not launch')
    monkeypatch.setattr(subprocess,'Popen',blocked)
    monkeypatch.setattr(Path,'home',blocked)


def inventory(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def facts(root):
    ctx=project_identity(root)
    with open_existing_read_only(ctx).read() as c:
        return {'counts':{t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in
                ('plans','runs','grants','receipts','management_grants','consumption','events')},
                'gate':dict(c.execute('SELECT * FROM dispatch_gate').fetchone()),'meta':dict(c.execute('SELECT * FROM meta'))}


def test_create_empty_paused_and_readonly_reopen(tmp_path):
    root=tmp_path/'new';manifest=create_project(root,'新 Project')
    assert manifest['display_name']=='新 Project'
    state=facts(root);assert all(v==0 for v in state['counts'].values())
    assert state['gate']['state']=='PAUSED' and state['meta']['supervisor_started']=='0'
    before=inventory(root)
    for _ in range(2):
        assert open_project(root)==manifest
        assert inspect_project(root)['kind']=='AGENT_FIRST_PRODUCT'
        m=ServiceLifecycleManager(root)
        assert m.inspect()['state']=='NOT_RUNNING' and m._profile()['process_config'] is None
        assert m.disconnect()['state']=='DISCONNECTED'
    assert before==inventory(root)
    with pytest.raises(ExecutionError,match='already exists'):create_project(root,'other')
    assert before==inventory(root)


def test_atomic_concurrent_creation(tmp_path):
    def create(_):
        try:return create_project(tmp_path/'new','Project')['project_id']
        except ExecutionError as e:return e.code
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(create,range(2)))
    assert results.count('PROJECT_EXISTS')==1
    assert open_project(tmp_path/'new')['project_id'] in results


@pytest.mark.parametrize('stage',['configuration','publication'])
def test_failed_creation_never_opens_or_reuses(tmp_path,monkeypatch,stage):
    import abqjobpilot.service_lifecycle as lifecycle
    def fail(*a,**k):raise OSError('injected creation failure')
    if stage=='configuration':monkeypatch.setattr(lifecycle,'configure_lifecycle',fail)
    else:monkeypatch.setattr(Path,'rename',fail)
    root=tmp_path/'new'
    with pytest.raises(OSError):create_project(root,'Project')
    assert not (root/'agent_project.json').exists()
    assert inspect_project(root)['reason']=='PROJECT_INCOMPLETE'
    with pytest.raises(ExecutionError) as e:project_identity(root/'project')
    assert e.value.code=='PROJECT_INCOMPLETE'
    with pytest.raises(ExecutionError) as e:create_project(root,'Project')
    assert e.value.code=='PROJECT_EXISTS'


@pytest.mark.parametrize('case',['plain','legacy','future','corrupt','missing_db','journal','moved','copy'])
def test_format_and_copy_boundaries(tmp_path,case):
    root=tmp_path/'new'
    if case in {'plain','legacy'}:
        root.mkdir()
        if case=='legacy':(root/'project.json').write_text('{"format":"old"}')
    else:
        create_project(root,'Project')
        if case=='future':
            p=root/'agent_project.json';v=json.loads(p.read_text());v['version']=99;p.write_text(canonical_json(v))
        if case=='corrupt':(root/'agent_project.json').write_text('{')
        if case=='missing_db':(root/'project/execution.sqlite3').unlink()
        if case=='journal':(root/'project/execution.sqlite3-journal').write_bytes(b'uncertain')
        if case=='moved':root.rename(tmp_path/'moved');root=tmp_path/'moved'
        if case=='copy':shutil.copytree(root,tmp_path/'copy');root=tmp_path/'copy'
    before=inventory(root)
    assert inspect_project(root)['kind']!='AGENT_FIRST_PRODUCT'
    with pytest.raises(ExecutionError):open_project(root)
    assert before==inventory(root)


@pytest.mark.parametrize('name',['',' '*5,'x'*81,'bad\nname'])
def test_invalid_name_no_directory(tmp_path,name):
    with pytest.raises(ExecutionError):create_project(tmp_path/'new',name)
    assert not (tmp_path/'new').exists()


def test_reparse_and_escape_rejected_before_write(tmp_path,monkeypatch):
    with pytest.raises(ExecutionError):create_project(tmp_path/'..'/'escape','x')
    # Local test symlink privileges vary; exercise actual reparse classification without enabling privileges.
    import stat
    original=Path.lstat
    def reparse(path):
        if path==tmp_path:return type('Stat',(),{'st_mode':stat.S_IFDIR,'st_file_attributes':0x400})()
        return original(path)
    monkeypatch.setattr(Path,'lstat',reparse)
    with pytest.raises(ExecutionError):create_project(tmp_path/'new','x')


def test_windows_dpapi_binding_tamper_and_plaintext_downgrade(tmp_path,monkeypatch):
    import abqjobpilot.local_credentials as lc
    create_project(tmp_path/'new','Project');m=ServiceLifecycleManager(tmp_path/'new')
    raw=(m.private/'lifecycle.json').read_text();profile=m._profile();secret=profile['credential']
    assert secret not in raw and m._operator() not in (m.private/'operator.json').read_text()
    enc=seal(m.context,{'secret':secret});assert unseal(m.context,enc)=={'secret':secret}
    enc['ciphertext']=enc['ciphertext'][:-8]+'AAAAAAAA'
    with pytest.raises(ExecutionError):unseal(m.context,enc)
    enc=seal(m.context,{'secret':secret})
    monkeypatch.setattr(lc,'host_binding',lambda:'wrong-user-or-host')
    with pytest.raises(ExecutionError):unseal(m.context,enc)
    monkeypatch.undo()
    (m.private/'lifecycle.json').write_text(canonical_json(profile))
    with pytest.raises(ExecutionError) as e:m._profile()
    assert e.value.code=='LOCAL_CREDENTIAL_UNAVAILABLE' and secret not in str(e.value)


def test_private_acl_restricted_from_creation(tmp_path):
    from ctypes import wintypes as W
    create_project(tmp_path/'new','Project');path=tmp_path/'new/private'
    needed=W.DWORD();get=_api('advapi32','GetFileSecurityW',[W.LPCWSTR,W.DWORD,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)])
    get(str(path),4,None,0,C.byref(needed));assert needed.value>0
    buf=C.create_string_buffer(needed.value);assert get(str(path),4,buf,needed,C.byref(needed))
    value=C.c_void_p()
    assert _api('advapi32','ConvertSecurityDescriptorToStringSecurityDescriptorW',
                [C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_void_p),C.c_void_p])(buf,1,4,C.byref(value),None)
    try:sddl=C.wstring_at(value)
    finally:_api('kernel32','LocalFree',[C.c_void_p],C.c_void_p)(value)
    assert sddl.startswith('D:P') and user_sid() in sddl and ';;;SY)' in sddl
    assert sddl.count('(A;')==2 and ';;;WD)' not in sddl and ';;;BU)' not in sddl
