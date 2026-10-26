"""Deployment policy only. No real execution, grants or external installation."""
import builtins
import importlib.util
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from abqjobpilot import application_runtime as runtime
from abqjobpilot.execution.models import ExecutionError


def test_console_sibling_for_windowed_python(monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'executable',str(tmp_path/'pythonw.exe'))
    assert runtime.console_interpreter()==tmp_path/'python.exe'


def test_current_interpreter_is_application_policy():
    from abqjobpilot.service_lifecycle import PYTHON
    assert runtime.validate_runtime()==PYTHON==Path(sys.executable).resolve()


@pytest.mark.parametrize('bad',[(3,9),(3,11),(3,13)])
def test_unqualified_python_version_refused(monkeypatch,bad):
    monkeypatch.setattr(sys,'version_info',bad)
    with pytest.raises(ExecutionError):runtime.validate_runtime()


def test_missing_console_refused(monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'executable',str(tmp_path/'pythonw.exe'))
    with pytest.raises(ExecutionError):runtime.validate_runtime()


def test_nonwindows_refused(monkeypatch):
    monkeypatch.setattr(sys,'platform','other')
    with pytest.raises(ExecutionError):runtime.validate_runtime()


def launcher():
    import abqjobpilot
    spec=importlib.util.spec_from_file_location('checked_launcher',Path(abqjobpilot.__file__).resolve().parents[1]/'launch_gui.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_preflight_no_process_or_project(monkeypatch,tmp_path):
    import subprocess
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('preflight launched a process'))
    m=launcher();result=m.inspect()
    assert result['status']=='READY' and result['service_started'] is False and result['Abaqus_calls']==0
    assert not list(tmp_path.iterdir())


def test_missing_tk_structured_error(monkeypatch):
    original=builtins.__import__
    def checked(name,*args,**kwargs):
        if name=='tkinter':raise ImportError('not reported private payload')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',checked)
    result=launcher().inspect()
    assert result['errors']==['TK_UNAVAILABLE_OR_BROKEN'] and 'private payload' not in str(result)


def test_standard_runtime_binding_rejected_before_intent(tmp_path,monkeypatch):
    from test_service_lifecycle import prepared
    with prepared(tmp_path) as (h,m):
        original=m._profile
        def wrong_runtime():
            value=original();value['standard_extension']={'standard_config':{'interpreter':str(tmp_path/'other/python.exe')}}
            return value
        monkeypatch.setattr(m,'_profile',wrong_runtime)
        with pytest.raises(ExecutionError) as exc:m.start()
        assert exc.value.code=='HOST_UNCONFIRMED'
        assert not m._path('lifecycle-current.json').exists()


def test_fixed_fixture_runtime_cannot_be_silently_changed(tmp_path,monkeypatch):
    from test_service_lifecycle import prepared
    with prepared(tmp_path,['normal']) as (h,m):
        original=m._profile
        def wrong_runtime():
            value=original();value['process_config']['interpreter']=str(tmp_path/'other/python.exe');return value
        monkeypatch.setattr(m,'_profile',wrong_runtime)
        with pytest.raises(ExecutionError) as exc:m.start()
        assert exc.value.code=='HOST_UNCONFIRMED'
        assert not m._path('lifecycle-current.json').exists()
