"""Local read-only preservation and own-test identity verification. No cleanup actions."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parents[2]
sys.path.insert(0,str(SOURCE))
baseline=json.loads((HERE/'BASELINE.json').read_text(encoding='utf-8'))
ROOT=Path(baseline['test_root'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','--no-optional-locks','-c','core.quotepath=false',*args],cwd=SOURCE,text=True,encoding='utf-8').strip()
head=git('rev-parse','HEAD');branch=git('branch','--show-current');conflicts=git('ls-files','-u')
assert head==baseline['head'] and branch=='Develop' and not conflicts
changed=[];missing=[]
for old in baseline['entries']:
    p=SOURCE/old['path']
    if not p.exists():missing.append(old['path'])
    elif sha(p)!=old['sha256']:changed.append(old['path'])
expected={'README.md','README_CN.md','abqjobpilot/execution/client.py','abqjobpilot/execution/service.py',
    'abqjobpilot/execution/store.py','abqjobpilot/execution/supervisor.py','abqjobpilot/execution_gui.py',
    'abqjobpilot/gui_app.py','tests/supervisor_helpers.py','tests/test_execution_gui.py'}
assert not missing and set(changed)==expected,(changed,missing)
old_paths={i['path'] for i in baseline['entries']}|set(baseline['volatile_excluded'])
files=git('ls-files','--cached','--others','--exclude-standard').splitlines()
new=sorted(set(files)-old_paths)
external_new=[p for p in new if p=='docs/agent_first/run_016/real_001/gui_B/exit.json']
new=[p for p in new if p not in external_new]
assert all(p.startswith('docs/agent_first/run_018/') or p in {'Open_Dev_GUI.vbs','abqjobpilot/service_discovery.py',
    'tests/run018_gui.py','tests/test_project_view.py','tests/test_service_attachment.py','tests/test_attachment_gui.py'} for p in new)

from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.models import ExecutionError
identities={}
for name in ('identity.json','owner-identity.json','worker.json','launcher.json','worker_transport.json','launcher_transport.json','branch.json','leaf.json'):
    for p in ROOT.rglob(name):
        try:
            v=json.loads(p.read_text(encoding='utf-8'));v=v.get('process',v)
            if all(k in v for k in ('pid','creation_time_100ns','image_path')):
                identities[(v['pid'],v['creation_time_100ns'],v['image_path'])]=v
        except (ValueError,AttributeError):pass
observations=[]
for v in identities.values():
    try:
        r=ProcessReference(v['pid'],v)
        try:
            exited=r.exit_evidence()
            result='MATCHING_EXITED' if exited else 'MATCHING_ACTIVE'
        finally:r.close()
    except ExecutionError as exc:result=exc.code
    observations.append({'pid':v['pid'],'creation_time_100ns':v['creation_time_100ns'],'result':result})
assert not any(v['result']=='MATCHING_ACTIVE' for v in observations)
cleanup=json.loads((HERE/'CLEANUP.json').read_text(encoding='utf-8'))
assert not cleanup['remaining_possible_private_files']
assert all(v['value']['all_owned_processes_exited'] and v['value']['credential_absent_from_remaining_files']
           and v['value']['recent_unchanged'] for v in cleanup['inventories'])
assert all(r['actual_process_handle_signaled'] and r['exited'] for group in cleanup['lifecycles'] for r in group['value'])
assert all(r['job_handle_closed'] and r['root_handle_closed'] for group in cleanup['managed_handles'] for r in group['value'])
report={'branch':branch,'head':head,'conflicts':conflicts,'changed_prior_files':changed,'new_files':new,
    'external_new_paths_not_read_or_modified':external_new,
    'unchanged_prior_files':len(baseline['entries'])-len(changed),'missing_prior_files':missing,
    'excluded_retained_gui_views':baseline['volatile_excluded'],
    'own_test_identity_followup':observations,'note':'Absent/mismatched now does not retroactively prove historical exit; retained-handle evidence remains authoritative',
    'cleanup_counts':{k:len(cleanup[k]) for k in ('inventories','lifecycles','managed_handles')},
    'abaqus_calls':0,'historical_instance_queried_or_stopped':False}
(HERE/'FINAL_CHECKS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in {'new_files','own_test_identity_followup'}}))
