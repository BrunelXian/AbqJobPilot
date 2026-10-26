"""Deterministic no-secret source packaging, no processes or shared runtime."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tkinter as tk
from unittest.mock import patch
import zipfile
import pytest

SPEC=importlib.util.spec_from_file_location('source_builder',Path(__file__).resolve().parents[1]/'scripts/build_source_candidate.py')
builder=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(builder)

def manifest(tmp_path):
    root=tmp_path/'input';(root/'scripts').mkdir(parents=True)
    (root/'app.py').write_bytes(b'print("safe")\r\n')
    data={'format':1,'version':'0.3.0.dev0','base_commit':'test',
          'files':[{'path':'app.py','sha256':hashlib.sha256(b'print("safe")\n').hexdigest(),'allow_crlf_checkout':True}]}
    (root/'scripts/release_inputs.json').write_text(json.dumps(data))
    (root/'private.json').write_text('not a real credential; must not be packaged')
    return root,data

def test_build_deterministic_exact_inputs_without_git(tmp_path):
    root,_=manifest(tmp_path)
    a=builder.build(root,tmp_path/'a');b=builder.build(root,tmp_path/'b')
    assert a['package_sha256']==b['package_sha256']
    assert a['file_count']==1
    with zipfile.ZipFile(tmp_path/'a'/a['package']) as z:
        assert z.namelist()==['AbqJobPilot/app.py']
        assert z.read(z.namelist()[0])==b'print("safe")\n'
    assert (root/'app.py').read_bytes().endswith(b'\r\n')
    with pytest.raises(FileExistsError):builder.build(root,tmp_path/'a')

def test_changed_input_fails_before_output(tmp_path):
    root,_=manifest(tmp_path);(root/'app.py').write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash mismatch'):builder.build(root,tmp_path/'output')
    assert not (tmp_path/'output').exists()

@pytest.mark.parametrize('path',['../outside','/absolute','C:/local','a\\b','a/./b','a//b'])
def test_path_escape_rejected(tmp_path,path):
    root,data=manifest(tmp_path);data['files'][0]['path']=path
    with pytest.raises(ValueError,match='Invalid manifest path'):builder.load_inputs(root,data)

def test_duplicate_input_rejected(tmp_path):
    root,data=manifest(tmp_path);data['files']*=2
    with pytest.raises(ValueError,match='Duplicate'):builder.load_inputs(root,data)

@pytest.mark.parametrize('exists',[False,True])
def test_optional_missing_or_invalid_icon_retains_native_default(exists):
    from abqjobpilot.gui_app import AbqJobPilotApp
    calls=[]
    class FakeWindow:
        def iconbitmap(self,path):
            calls.append(path);raise tk.TclError('invalid icon')
    with patch.object(Path,'exists',return_value=exists):
        AbqJobPilotApp._apply_icon(FakeWindow())
    assert len(calls)==int(exists)
