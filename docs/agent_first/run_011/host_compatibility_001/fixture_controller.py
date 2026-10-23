"""Host experiment ONLY: reuse frozen engine + fixed ten-second Python worker.

Not an execution entry, authorization mechanism, or change to probe.py admission.
PowerShell remains the independent observer; no persistent Python harness ancestor.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
SOURCE = RUN.parents[2]
VENV = Path(r'D:\XianLab\envs\LangChainEnv\Scripts\python.exe')
BASE = Path(r'D:\Program Files\Python312\python.exe')
TEMP = Path(r'C:\Users\wuxia\AppData\Local\Temp')
WORKER = RUN / 'tests/fixture_process.py'
sys.path.insert(0, str(RUN / 'controller'))
sys.path.insert(0, str(SOURCE))
from records import require, safe_path, write_new, read_json, stamp
from windows_host import current_host, process_rows, handle_identity, api
from engine import run_once
from abqjobpilot.execution.process_handles import ProcessReference


def case_path(value):
    path = safe_path(value)
    require(path.parent.parent == TEMP and path.name == 'case_host'
            and path.parent.name.startswith('AbqJobPilot_Run011_Host_')
            and len(path.parent.name.removeprefix('AbqJobPilot_Run011_Host_')) == 32,
            'FIXTURE_ROOT_REQUIRED')
    require(path.is_dir(), 'FIXTURE_ROOT_MISSING')
    return path


def publish(root, name, data):
    write_new(root / name, data)
    with (root / (name + '.ready')).open('xb'):
        pass


def await_record(root, name, seconds=6):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if (root / (name + '.ready')).exists():
            return read_json(root / name)
        time.sleep(.01)
    raise RuntimeError('FIXTURE_HANDSHAKE_TIMEOUT_' + name)


def audit_for(root):
    expected = subprocess.list2cmdline([str(VENV), '-B', str(WORKER), 'worker', str(root)])
    def audit(event, args):
        if event == 'subprocess.Popen':
            exe, command, cwd, env = args
            require(isinstance(exe, str) and Path(exe) == VENV and command == expected and Path(cwd) == root,
                    'ONLY_FIXED_PYTHON_WORKER_ALLOWED')
            require(env == {'SystemRoot':r'C:\Windows', 'TEMP':str(root), 'TMP':str(root)},
                    'FIXTURE_ENV_CHANGED')
        if event in {'os.system','os.startfile','sqlite3.connect','socket.connect'}:
            raise RuntimeError('FIXTURE_NO_SHELL_DATABASE_NETWORK')
        if event == 'open' and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0]))
            mode, flags = args[1:]
            if path == Path(os.devnull) and not (flags or 0) & (os.O_CREAT | os.O_TRUNC):
                return  # Popen's fixed stdin=DEVNULL; no filesystem output.
            if (flags or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                require(path.is_absolute() and path.is_relative_to(root), 'FIXTURE_WRITE_ESCAPE')
    return audit


def verified_chain(context):
    """Parent links are controller OS snapshot facts, independently checked IDs below."""
    host = current_host()
    require(host['job_query_succeeded'] is True, 'HOST_QUERY_UNKNOWN')
    require(Path(sys.executable) == VENV and Path(host['identity']['image_path']) == BASE,
            'REGISTERED_VENV_REQUIRED')
    links = dict(process_rows())
    launcher = context['launcher']
    shell = context['powershell']
    require(links.get(os.getpid()) == launcher['pid'] and
            links.get(launcher['pid']) == shell['pid'], 'UNEXPECTED_CONTROLLER_CHAIN')
    references = []
    try:
        for identity in (launcher, shell):
            ref = ProcessReference(identity['pid'], identity)
            references.append(ref)
            require(ref.exit_evidence() is None, 'CHAIN_MEMBER_ALREADY_EXITED')
        require(Path(launcher['image_path']) == VENV, 'VENV_LAUNCHER_IMAGE_MISMATCH')
        return host, {'source':'controller_OS_Toolhelp_parent_links_and_retained_identities',
                      'powershell':shell, 'venv_launcher':launcher,
                      'controller':host['identity']}
    finally:
        for ref in references:
            ref.close()


def run(root):
    sys.addaudithook(audit_for(root))
    context = await_record(root, 'observer_context.json')
    host, chain = verified_chain(context)
    publish(root, 'controller_ready.json', {'host':host, 'chain':chain,
        'fixture_admission_only':'Job membership recorded, not used as real admission'})
    await_record(root, 'controller_reference_held.json')
    actual_child = None

    def spawn(out, err):
        nonlocal actual_child
        actual_child = subprocess.Popen([str(VENV), '-B', str(WORKER), 'worker', str(root)],
            executable=str(VENV), cwd=root, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
            shell=False, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW,
            env={'SystemRoot':r'C:\Windows', 'TEMP':str(root), 'TMP':str(root)})
        publish(root, 'worker_launcher.json', {
            'source':'controller_direct_Popen_handle',
            'identity':handle_identity(int(actual_child._handle), actual_child.pid)})
        return actual_child

    def barrier(phase):
        if phase == 'process_created':
            # Observer must hold both worker and its venv redirector before controller closes.
            await_record(root, 'worker_references_held.json', seconds=4)

    # Same explicit test-only DI seam as original fixture_driver.py; never real CLI.
    injected = {**host, 'in_any_job':False, 'test_only_admission_injected':True,
                'actual_job_observation':host}
    spec = {'root':str(root), 'job':'test_job', 'experiment_id':'host_fixture_only',
            'original_digest':'test-only', 'output_identity':'fixture-output', 'budget_seconds':.6}
    report = run_once(spec, 'HOST_FIXTURE_NOT_REAL_CANDIDATE', lambda:None,
                      lambda:injected, spawn, checkpoint=barrier)
    publish(root, 'function_returned.json', {'observed_at_ns':stamp(),
        'source':'controller_self_report_after_run_once_return', 'controller_identity':host['identity'],
        'report':report, 'not_OS_exit_evidence':True})
    return 0 if report.get('deadline_reached') and 'failure' not in report else 2


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Use the fixed run_host_check.ps1 in the operator PowerShell; no Solver operation exists.')
        raise SystemExit(2)
    target = case_path(sys.argv[1])
    try:
        code = run(target)
    except Exception as exc:
        publish(target, 'controller_failure.json', {'code':getattr(exc, 'code', type(exc).__name__),
                                                   'abaqus_calls':0})
        code = 2
    raise SystemExit(code)
