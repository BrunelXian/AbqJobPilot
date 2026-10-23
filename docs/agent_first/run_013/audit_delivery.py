"""Read-only delivery audit; writes only new Run013 audit evidence, never launches."""
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from abqjobpilot.execution.models import ProjectContext,canonical_json,digest
from abqjobpilot.execution.store import ReadOnlyStore
from abqjobpilot.execution.standard_backend import call_data

HERE=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,value):
    with (HERE/name).open('x',encoding='utf-8') as f:f.write(canonical_json(value))

baseline=read(HERE/'BASELINE_FILES.json')
changed=[v['path'] for v in baseline if not Path(v['path']).exists() or sha(Path(v['path']))!=v['sha256']]
protected=[v for v in baseline if '/run_010/' in v['path'].replace('\\','/') or '/run_011/' in v['path'].replace('\\','/')]
assert not any(v['path'] in changed for v in protected)
original=read(ROOT/'docs/agent_first/run_010/EXPERIMENT_MANIFEST.json')
assert digest(original['body'])=='sha256:04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6'
frozen=[]
for material in original['body']['materials']:
    path=Path(material['path'])
    assert not str(path).lower().startswith('d:\\projects\\abqjobpilot\\')
    match=sha(path)==material['sha256'];assert match,str(path)
    frozen.append({'path':str(path),'matches':match})
manifest=read(HERE/'ACCEPTANCE_MANIFEST.json');body=manifest['body'];assert digest(body)==manifest['content_digest']
ctx=ProjectContext(**body['context']);store=ReadOnlyStore(ctx)
with store.read() as db:
    counts={t:db.execute('select count(*) from '+t).fetchone()[0] for t in ('plans','grants','runs','receipts','consumption','observations','validations')}
assert counts=={'plans':1,'grants':0,'runs':0,'receipts':0,'consumption':0,'observations':0,'validations':0},counts
root=Path(ctx.test_root);plan=body['plan']
assert not list(Path(plan['engineering']).glob(plan['job_name']+'.*'))
assert not (Path(plan['engineering'])/('.'+plan['job_name']+'.intent.json')).exists()
call=call_data(ctx,plan,{'run_id':'ASSIGNED_BY_ACCEPT_TRANSACTION'})
save('CALL_REVIEW.json',{'source_manifest':manifest['content_digest'],'derived_from':'standard_backend.call_data',
    'application':call['application'],'command_line':call['command_line'],'cwd':call['cwd'],
    'output_template':str(Path(ctx.runtime_root)/'standard_runs/{run_id}'),'environment_policy':plan['environment_policy'],
    'calls_permitted_this_round':0,'launches_this_round':0})
passed={};skipped=[];failures=[]
for name in ('REGRESSION_02.xml','ADMISSION_02.xml','LEGACY_GUI.xml','LEGACY_GUI_RETRY.xml'):
    for item in ET.parse(HERE/name).iter('testcase'):
        key=item.attrib['classname']+'::'+item.attrib['name']
        if item.find('failure') is not None:failures.append(key)
        elif item.find('skipped') is not None:skipped.append(key)
        else:passed[key]=name
assert not failures and all(v in passed for v in skipped)
save('DELIVERY_AUDIT.json',{'baseline_file_count':len(baseline),'prior_changed':changed,
    'protected_run010_011_files':len(protected),'protected_files_unchanged':True,'original_frozen_materials':frozen,
    'candidate_digest':manifest['content_digest'],'new_acceptance_store_counts':counts,
    'output_conflicts':False,'effective_unique_passed':len(passed),'skipped_then_individually_passed':skipped,
    'abaqus_calls_this_round':0,'test_case_sources':passed})
print(canonical_json({'unique_passed':len(passed),'original_materials_verified':len(frozen),
    'protected_files':len(protected),'acceptance_store':counts,'digest':manifest['content_digest']}))
