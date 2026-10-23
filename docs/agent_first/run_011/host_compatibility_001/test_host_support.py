"""Narrow non-Solver tests for new support. Does not call real controller CLI."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('host_fixture_controller', HERE / 'fixture_controller.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def test_readonly_import_did_not_import_real_entry():
    assert 'probe' not in sys.modules
    assert 'frozen' not in sys.modules


@pytest.mark.parametrize('path', [r'C:\Windows', r'D:\Projects\abqjobpilot_dev',
    r'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a'])
def test_real_or_unrelated_roots_rejected(path):
    with pytest.raises(Exception, match='FIXTURE_ROOT_REQUIRED'):
        driver.case_path(path)


@pytest.mark.parametrize('succeeded', [False, None])
def test_failed_or_unknown_job_query_never_reaches_spawn(monkeypatch, succeeded):
    monkeypatch.setattr(driver, 'current_host', lambda: {'job_query_succeeded':succeeded})
    monkeypatch.setattr(driver, 'process_rows', lambda: pytest.fail('No chain discovery after query failure'))
    with pytest.raises(Exception, match='HOST_QUERY_UNKNOWN'):
        driver.verified_chain({})


def test_chain_gap_is_refused(monkeypatch):
    monkeypatch.setattr(driver, 'current_host', lambda: {'job_query_succeeded':True,
        'identity':{'image_path':str(driver.BASE)}})
    monkeypatch.setattr(driver, 'process_rows', lambda: [])
    with pytest.raises(Exception, match='UNEXPECTED_CONTROLLER_CHAIN'):
        driver.verified_chain({'launcher':{'pid':100}, 'powershell':{'pid':101}})


def test_spawn_sentinel_only_allows_fixed_worker():
    root = driver.TEMP / ('AbqJobPilot_Run011_Host_'+uuid.uuid4().hex) / 'case_host'
    audit = driver.audit_for(root)
    argv = subprocess.list2cmdline([str(driver.VENV), '-B', str(driver.WORKER), 'worker', str(root)])
    env = {'SystemRoot':r'C:\Windows','TEMP':str(root),'TMP':str(root)}
    audit('subprocess.Popen',(str(driver.VENV),argv,str(root),env))
    for command in [argv.replace('worker','launcher'), argv+' extra', 'cmd.exe /c anything']:
        with pytest.raises(Exception, match='ONLY_FIXED_PYTHON_WORKER_ALLOWED'):
            audit('subprocess.Popen',(str(driver.VENV),command,str(root),env))
    with pytest.raises(Exception, match='FIXTURE_ENV_CHANGED'):
        audit('subprocess.Popen',(str(driver.VENV),argv,str(root),{}))


def test_partial_handoff_is_not_consumed(tmp_path):
    (tmp_path / 'handoff.json').write_bytes(b'{')
    with pytest.raises(RuntimeError, match='FIXTURE_HANDSHAKE_TIMEOUT'):
        driver.await_record(tmp_path,'handoff.json',seconds=.02)


def test_unknown_chain_identity_is_not_forgiven(monkeypatch):
    monkeypatch.setattr(driver, 'current_host', lambda: {'job_query_succeeded':True,
        'identity':{'image_path':str(driver.BASE)}})
    monkeypatch.setattr(driver, 'process_rows', lambda: [(driver.os.getpid(),100),(100,101)])
    monkeypatch.setattr(driver, 'ProcessReference', lambda *a: (_ for _ in ()).throw(RuntimeError('IDENTITY_UNKNOWN')))
    with pytest.raises(RuntimeError, match='IDENTITY_UNKNOWN'):
        driver.verified_chain({'launcher':{'pid':100},'powershell':{'pid':101}})


def test_retained_OS_reference_rejects_same_pid_wrong_creation_time():
    identity = driver.current_host()['identity']
    mismatch = {**identity, 'creation_time_100ns':identity['creation_time_100ns']+1}
    with pytest.raises(Exception, match='Process candidate does not match'):
        driver.ProcessReference(identity['pid'], mismatch)


def test_write_escape_and_shell_or_db_are_denied():
    root = driver.TEMP / ('AbqJobPilot_Run011_Host_'+uuid.uuid4().hex) / 'case_host'
    audit = driver.audit_for(root)
    audit('open',(driver.os.devnull,None,driver.os.O_RDWR))
    with pytest.raises(Exception, match='FIXTURE_WRITE_ESCAPE'):
        audit('open',(str(HERE / 'candidate.py'),'w',driver.os.O_CREAT))
    for event in ('os.system','os.startfile','sqlite3.connect','socket.connect'):
        with pytest.raises(RuntimeError, match='FIXTURE_NO_SHELL_DATABASE_NETWORK'):
            audit(event,())


def test_fixed_existing_worker_has_deadline_and_no_release_from_driver():
    source = driver.WORKER.read_text()
    assert 'deadline = time.monotonic() + 10' in source
    assert 'worker_done.json' in source
    assert "'release'" not in (HERE / 'fixture_controller.py').read_text()
