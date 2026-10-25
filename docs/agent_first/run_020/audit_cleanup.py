"""Run020 exact temporary roots only. No process termination, recursive deletion or DB writes.

Retained-handle exit evidence in tests is distinct from this later absence check.
Remove only this Run's private capability files after no matching process remains.
"""
import json
from pathlib import Path
import sys
import argparse

SOURCE=Path(__file__).resolve().parents[3];sys.path.insert(0,str(SOURCE))
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.models import ExecutionError
from abqjobpilot.execution.paths import no_reparse

TEMP=Path(r'C:\Users\wuxia\AppData\Local\Temp')
ROOTS=[TEMP/n for n in (
    'AbqJobPilot_Run020_smoke_gp3c3d9i','AbqJobPilot_Run020_unit_01',
    'AbqJobPilot_Run020_windows_01','AbqJobPilot_Run020_windows_02','AbqJobPilot_Run020_windows_03',
    'AbqJobPilot_Run020_windows_04','AbqJobPilot_Run020_final','AbqJobPilot_Run020_chain','AbqJobPilot_Run020_legacy',
    'AbqJobPilot_Run020_ui_final','AbqJobPilot_Run020_verified')]
identities={};documents=[];secrets=set()
def collect(value):
    if isinstance(value,dict):
        if type(value.get('pid')) is int and type(value.get('creation_time_100ns')) is int and type(value.get('image_path')) is str:
            identities[(value['pid'],value['creation_time_100ns'])]={k:value[k] for k in ('pid','creation_time_100ns','image_path')}
        for k,v in value.items():
            if k in {'credential','operator_token'} and isinstance(v,str) and len(v)>=32:secrets.add(v)
            collect(v)
    elif isinstance(value,list):
        for v in value:collect(v)

for root in ROOTS:
    assert root.is_relative_to(TEMP) and root.name.startswith('AbqJobPilot_Run020_');no_reparse(root)
    if not root.exists():continue
    for path in root.rglob('*.json'):
        no_reparse(path)
        if path.stat().st_size>4*1024*1024:continue
        try:collect(json.loads(path.read_text(encoding='utf-8')))
        except (UnicodeError,ValueError,OSError):continue
    # Inspect protected profiles in memory only; nothing decrypted is exported.
    from abqjobpilot.service_lifecycle import ServiceLifecycleManager
    for manifest in root.rglob('agent_project.json'):
        try:
            m=ServiceLifecycleManager(manifest.parent);secrets.add(m._profile()['credential']);secrets.add(m._operator())
        except ExecutionError:pass

observed=[];alive=[]
for identity in identities.values():
    try:
        ref=ProcessReference(identity['pid'],identity)
        try:
            exit=ref.exit_evidence()
            if exit is None:alive.append(identity)
            observed.append({'identity':identity,'state':'MATCHED_ALIVE' if exit is None else 'EXIT_OBSERVED_NOW','exit':exit})
        finally:ref.close()
    except ExecutionError as exc:
        observed.append({'identity':identity,'state':exc.code,'meaning':'not historical exit evidence'})

OUT=Path(__file__).parent
leaks=[]
for path in OUT.rglob('*'):
    if path.is_file() and path.suffix in {'.json','.xml','.txt','.md'}:
        data=path.read_text(encoding='utf-8',errors='replace')
        if any(secret in data for secret in secrets):leaks.append(str(path.relative_to(OUT)))
result={'roots':[str(r) for r in ROOTS],'identity_count':len(identities),'matched_alive':alive,
        'observations':observed,'report_secret_leaks':leaks,'private_files_removed':[],
        'abaqus_calls':0,'terminated_processes':0,'historical_instances_accessed':False}
assert not leaks,'Do not publish private capability values'
if not alive:
    for root in ROOTS:
        if not root.exists():continue
        for p in root.rglob('*.json'):
            private=(p.parent.name=='private' and p.name in {'lifecycle.json','operator.json','connection.json','offer.json'})
            private=private or p.name in {'private-bootstrap.json','private-process.json','gui-private-connection.json'}
            # Controlled Standard-substitute bootstrap/connection names.
            private=private or (p.name in {'bootstrap.json','connection.json'} and p.parent.name.startswith('test_'))
            if private:
                no_reparse(p);assert p.resolve().is_relative_to(root.resolve())
                p.unlink();result['private_files_removed'].append(str(p))
parser=argparse.ArgumentParser();parser.add_argument('--report',choices=['CLEANUP_FINAL.json','CLEANUP_UI_FINAL.json'],required=True)
args=parser.parse_args()
with (OUT/args.report).open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'identities':len(identities),'matched_alive':len(alive),'private_files_removed':len(result['private_files_removed']),
                  'report_secret_leaks':len(leaks),'terminated_processes':0}))
assert not alive,'Matching live test process: no further cleanup; report explicitly'
