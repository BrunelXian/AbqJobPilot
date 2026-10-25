"""Explicit no-Solver product/input preparation. Does NOT prepare an executable Plan.

The current product/managed-single integration is blocked; this script deliberately
stops at a public offline preview. Never imports an authority or starts a service.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

SOURCE = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
sys.path.insert(0, str(SOURCE))
from abqjobpilot.product_project import create_project, open_project
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution.store import open_existing_read_only
from abqjobpilot.execution.models import canonical_json, digest
from abqjobpilot.abaqus_preview import prepare, inspect
from abqjobpilot.abaqus_preview.preview import PROBE_PROFILE


def guard(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.startfile', 'abqjobpilot.managed_standard_create'}:
        raise AssertionError('Preparation must not create any execution process')


def save(name, value):
    with (OUT/name).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2))


def main():
    assert not (OUT/'PREPARATION_MANIFEST.json').exists(), 'Do not regenerate existing candidate'
    sys.addaudithook(guard)
    location = OUT/'PREPARATION_LOCATION.json'
    if location.exists():
        saved = json.loads(location.read_text(encoding='utf-8-sig'))
        root = Path(saved['root']); suffix = root.name.removeprefix('AbqJobPilot_Run021_')
        manifest = open_project(root)  # Resume our recorded no-service preparation only.
    else:
        suffix = uuid.uuid4().hex
        root = Path(r'C:\Users\wuxia\AppData\Local\Temp')/('AbqJobPilot_Run021_'+suffix)
        manifest = create_project(root, 'Run021 Standard product candidate')
        save('PREPARATION_LOCATION.json', {'root': str(root)})
    engineering = root/'engineering'
    engineering.mkdir(exist_ok=True); (engineering/'scratch').mkdir(exist_ok=True)
    raw = (SOURCE/'docs/agent_first/run_010/axial_bar.inp').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3'
    source = engineering/'axial_bar.inp'
    if source.exists():
        assert source.read_bytes() == raw, 'Never replace changed input'
    else:
        with source.open('xb') as stream: stream.write(raw)
    profile = {'profile_id': 'run021_fixed_standard_2024', 'profile_version': 1,
               'platform': 'windows-local', 'product': 'Abaqus/Standard', 'declared_version': '2024',
               'phase': 'analysis', 'cpus': 1, 'gpus': 0, 'memory_mb': 2048,
               'wall_seconds': 300, 'scratch_relative': 'scratch'}
    project = {k: manifest[k] for k in ('project_id', 'project_instance_id')}
    job = 'r021_bar_'+suffix[:8]
    preview = prepare(project=project, runtime_profile=profile, engineering_root=str(engineering),
                      submission_cwd=str(engineering), main_input='axial_bar.inp', job_name=job,
                      support_profile_version=PROBE_PROFILE)
    inspect(preview)
    save('OFFLINE_PREVIEW.json', preview.to_dict())
    manager = ServiceLifecycleManager(root)
    with open_existing_read_only(manager.context).read() as conn:
        facts = {'counts': {table: conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                           for table in ('plans', 'grants', 'runs', 'receipts', 'consumption', 'events', 'management_grants')},
                 'gate': dict(conn.execute('SELECT * FROM dispatch_gate').fetchone()),
                 'supervisor_started': dict(conn.execute('SELECT * FROM meta'))['supervisor_started']}
    assert all(n == 0 for n in facts['counts'].values()) and facts['gate']['state'] == 'PAUSED'
    assert manager.inspect()['state'] == 'NOT_RUNNING' and facts['supervisor_started'] == '0'
    assert open_project(root) == manifest
    entry = Path(r'D:\ABAQUS2024\Commands\abq2024.bat')
    body = {'format': 'run021-incomplete-preparation-v1', 'experiment_id': 'run021_'+suffix,
            'readiness': 'PARTIAL_NOT_AN_EXECUTION_ACCEPTANCE_PACKAGE', 'project': manifest,
            'root': str(root), 'store': manager.context.execution_store,
            'execution_plan_id': None, 'execution_plan_status': 'NOT_CREATED_BLOCKED_INTEGRATION',
            'offline_preview_digest': preview.to_dict()['content_digest'],
            'input': {'path': str(engineering/'axial_bar.inp'), 'sha256': hashlib.sha256(raw).hexdigest()},
            'entry': {'path': str(entry), 'sha256': hashlib.sha256(entry.read_bytes()).hexdigest(),
                      'evidence': 'STATIC_BYTES_ONLY_NOT_RUNTIME_VALIDATION'},
            'job': job, 'cwd': str(engineering), 'scratch': str(engineering/'scratch'),
            'outputs': str(engineering), 'resources': {'cpus': 1, 'gpus': 0, 'memory_mb': 2048},
            'proposed_budget': {'analysis': 1, 'extra_abaqus_calls': 0, 'observe_seconds': 300,
                                'timeout': 'STOP_OBSERVING_ONLY', 'retry': False, 'terminate': False},
            'dispatch': 'PAUSED_UNCHANGED', 'real_grant': 'NOT_ISSUED', 'run': 'NOT_SUBMITTED',
            'numerical_checks': [{'entity': 'node2 U1', 'reference': '0.01 mm', 'tolerance': '1e-6 mm'},
                                 {'entity': 'element1 ip1 S11', 'reference': '1 MPa', 'tolerance': '1e-4 MPa'},
                                 {'entity': 'node1 RF1', 'reference': '-1 N', 'tolerance': '1e-4 N'}],
            'odb': 'NOT_RUN', 'blocking_items': ['PRODUCT_STANDARD_PROFILE_NOT_IMPLEMENTED',
                'MANAGED_SINGLE_PLAN_NOT_IMPLEMENTED', 'LIVE_OWNER_PRECISE_APPROVAL_NOT_IMPLEMENTED',
                'SINGLE_DISPATCH_AND_RETURN_PAUSED_NOT_IMPLEMENTED', 'STANDARD_IDLE_STOP_NOT_SUPPORTED'],
            'authorization': 'NO_EXECUTION_AUTHORITY; further implementation review required'}
    save('PREPARATION_MANIFEST.json', {'body': body, 'body_sha256': digest(body).split(':', 1)[1],
                                     'digest_rule': 'SHA256 UTF8 canonical_json(body): sorted keys, compact separators; not whole file'})
    save('PREPARATION_FACTS.json', {'facts': facts, 'service': manager.inspect(),
                                  'execution_processes_created': 0, 'abaqus_calls': 0,
                                  'credentials': 'retained protected private files; never exported'})
    print(json.dumps({'root': str(root), 'job': job, 'project': project,
                      'body_sha256': digest(body).split(':', 1)[1], 'execution_plan_id': None}))


if __name__ == '__main__':
    main()
