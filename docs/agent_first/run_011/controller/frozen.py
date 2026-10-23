"""Fixed Run010 object + separately frozen Run011 candidate. No dynamic commands."""
import importlib.util
import os
from pathlib import Path
import sys

from records import digest, require, stable_read, read_json, safe_path

SOURCE = Path(r'D:\Projects\abqjobpilot_dev')
PACKAGE = SOURCE / 'docs/agent_first/run_011'
ORIGINAL = SOURCE / 'docs/agent_first/run_010/EXPERIMENT_MANIFEST.json'
ORIGINAL_DIGEST = 'sha256:04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6'
ROOT = Path(r'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a')
INTERPRETER = Path(r'D:\XianLab\envs\LangChainEnv\Scripts\python.exe')
BASE_INTERPRETER = Path(r'D:\Program Files\Python312\python.exe')
EXPERIMENT = 'abq2024_r010_a19d17ea'
JOB = 'r010_bar_a19d17ea'
LOCAL_FILES = ['probe.py', 'frozen.py', 'records.py', 'engine.py', 'windows_host.py', 'printed_results.py']
REUSED_FILES = ['abqjobpilot/__init__.py', 'abqjobpilot/execution/__init__.py',
    'abqjobpilot/execution/models.py', 'abqjobpilot/execution/paths.py',
    'abqjobpilot/execution/process_handles.py', 'abqjobpilot/abaqus_preview/__init__.py',
    'abqjobpilot/abaqus_preview/inputs.py', 'abqjobpilot/abaqus_preview/preview.py',
    'examples/agent_first/abaqus_probe_review.py']


def original():
    value = read_json(ORIGINAL)
    require(set(value) == {'body', 'content_digest'} and
            digest(value['body']) == value['content_digest'] == ORIGINAL_DIGEST, 'ORIGINAL_CHANGED')
    return value


def material_paths():
    return [PACKAGE / 'controller' / p for p in LOCAL_FILES] + [SOURCE / p for p in REUSED_FILES] + [
        ORIGINAL, INTERPRETER, BASE_INTERPRETER, BASE_INTERPRETER.parent / 'python312.dll',
        INTERPRETER.parent.parent / 'pyvenv.cfg', BASE_INTERPRETER.parent / 'Lib/subprocess.py']


def configuration(body):
    require(body['experiment_id'] == EXPERIMENT and
            Path(body['directories']['experiment_root']) == ROOT and
            body['output']['job_name'] == JOB, 'FIXED_OBJECT_MISMATCH')
    return {'schema':'r011-fixed-controller-candidate-v1', 'experiment_id':EXPERIMENT,
        'original_manifest':str(ORIGINAL), 'original_digest':ORIGINAL_DIGEST,
        'controller':str(PACKAGE / 'controller/probe.py'),
        'interpreter':str(INTERPRETER), 'base_interpreter':str(BASE_INTERPRETER),
        'python_version':'3.12.10', 'windows_call':body['windows_call'],
        'environment_policy':body['environment_policy'], 'actions':body['actions'],
        'additional_abaqus_calls':0, 'budget_seconds':300,
        'host_admission':'same actual controller: IsProcessInJob succeeds AND false; no bypass',
        'attempt_path':str(ROOT / 'observations/attempt.json'),
        'attempt_scope':'fixed experiment and output identity, independent of candidate version',
        'output_identity':body['output']['candidate_key'],
        'records':{'events':str(ROOT / 'observations/controller_events.jsonl'),
                   'report':str(ROOT / 'observations/controller_report.json')},
        'stop_policy':body['stop_policy'], 'numeric_reference':body['acceptance_reference'],
        'authorization':'NONE; candidate identity only; execute requires separate operator approval',
        'process_completeness':'UNKNOWN; never promoted from observed subset',
        'report_scope':'external controller observations, not ExecutionService/Project Run history',
        'dat_layout':'r011-explicit-dat-tables-v1; actual 2024 layout unverified'}


def verify_materials(items):
    require(type(items) is list and 0 < len(items) <= 64, 'MATERIAL_LIMIT')
    for item in items:
        _, identity = stable_read(item['path'])
        require(identity['bytes'] == item['bytes'] and identity['sha256'] == item['sha256'],
                'MATERIAL_CHANGED')


def load_candidate(expected=None):
    old = original()
    candidate = read_json(PACKAGE / 'CANDIDATE_MANIFEST.json')
    require(set(candidate) == {'body','content_digest'}, 'CANDIDATE_SCHEMA')
    body = candidate['body']
    require(candidate['content_digest'] == digest(body) and
            (expected is None or expected == candidate['content_digest']), 'CANDIDATE_CHANGED')
    require({k:v for k,v in body.items() if k != 'materials'} == configuration(old['body']),
            'CANDIDATE_CONFIGURATION_CHANGED')
    require([p['path'] for p in body['materials']] == [str(p) for p in material_paths()],
            'CANDIDATE_MATERIAL_SET_CHANGED')
    verify_materials(body['materials'])
    verify_materials(old['body']['materials'])
    require(Path(sys.executable) == INTERPRETER and sys.version.split()[0] == '3.12.10',
            'INTERPRETER_MISMATCH')
    for value in old['body']['directories'].values():
        require(safe_path(value).is_dir(), 'DIRECTORY_UNAVAILABLE')
    # Source imports follow integrity checks. No legacy config/runtime/Project imports.
    sys.path.insert(0, str(SOURCE)) if str(SOURCE) not in sys.path else None
    return old, candidate


def verify_before_attempt(expected):
    old, candidate = load_candidate(expected)
    path = SOURCE / 'examples/agent_first/abaqus_probe_review.py'
    module_spec = importlib.util.spec_from_file_location('r011_original_readonly_review', path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.review(old, ORIGINAL_DIGEST)
    return old, candidate


def execution_spec():
    body = original()['body']
    return {'root':str(ROOT), 'experiment_id':EXPERIMENT, 'job':JOB,
            'original_digest':ORIGINAL_DIGEST, 'output_identity':body['output']['candidate_key'],
            'input_path':str(ROOT / 'engineering/axial_bar.inp'), 'input_digest':body['input_digest'],
            'budget_seconds':300}


def spawn_frozen(stdout, stderr):
    """Called only by explicit execute operation, after same-process gate + durable intent."""
    import subprocess
    body = original()['body']
    call = body['windows_call']
    # Exact Windows command line and executable, not list2cmdline reconstruction.
    return subprocess.Popen(call['command_line'], executable=call['application'],
        cwd=call['cwd'], env=body['environment_policy']['values'], shell=False,
        close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
