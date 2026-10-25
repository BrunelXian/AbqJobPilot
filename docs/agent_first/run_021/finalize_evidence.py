"""Append final read-only evidence for this Run; no service mutation."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

SOURCE=Path(__file__).resolve().parents[3]; OUT=Path(__file__).parent
sys.path.insert(0,str(SOURCE))
from abqjobpilot.execution.models import canonical_json, digest
from abqjobpilot.product_project import open_project
from abqjobpilot.service_discovery import project_identity
from abqjobpilot.execution.store import open_existing_read_only


def save(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2))


latest={};batches=[]
for name in ('regression_001','legacy'):
    cases=[]
    for case in ET.parse(OUT/(name+'.xml')).iter('testcase'):
        key=case.attrib['classname']+'::'+case.attrib['name']
        verdict='FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
        row={'id':key,'result':verdict};cases.append(row);latest[key]=row
    batches.append({'batch':name,'cases':cases,'count':len(cases)})
save('TEST_RESULTS.json',{'unique_count':len(latest),'counts':{k:sum(x['result']==k for x in latest.values()) for k in ('PASS','FAIL','SKIP')},
    'batches':batches,'deduplication':'classname + parameterized name; latest actual execution',
    'not_covered':'unimplemented product Standard combined authorization/dispatch/idle-stop path'})
base=json.loads((OUT/'BASELINE.json').read_text(encoding='utf-8-sig'))
changed=[];missing=[]
for name,h in base['files'].items():
    p=SOURCE/name
    if not p.is_file():missing.append(name)
    elif hashlib.sha256(p.read_bytes()).hexdigest()!=h:changed.append(name)
def git(*args):return subprocess.check_output(['git',*args],cwd=SOURCE).decode().strip()
save('FINAL_INTEGRITY.json',{'head':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),
    'conflicts':git('ls-files','-u'),'baseline_count':len(base['files']),'changed_prior_files':changed,
    'missing_prior_files':missing,'status':git('status','--porcelain'),'application_patch_written':False})
candidate=json.loads((OUT/'PREPARATION_MANIFEST.json').read_text(encoding='utf-8'))
assert digest(candidate['body']).split(':')[1]==candidate['body_sha256']
body=candidate['body'];root=Path(body['root']);project=open_project(root);ctx=project_identity(root)
with open_existing_read_only(ctx).read() as conn:
    counts={t:conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('plans','grants','runs','receipts','consumption','events','management_grants')}
    gate=dict(conn.execute('SELECT * FROM dispatch_gate').fetchone())
    started=dict(conn.execute('SELECT * FROM meta'))['supervisor_started']
assert all(v==0 for v in counts.values()) and gate['state']=='PAUSED' and started=='0'
assert hashlib.sha256(Path(body['input']['path']).read_bytes()).hexdigest()==body['input']['sha256']
assert not list((root/'engineering').glob(body['job']+'.*'))
assert not list((root/'engineering').glob('.*.intent.json'))
save('CANDIDATE_FINAL_CHECK.json',{'body_sha256':candidate['body_sha256'],'counts':counts,'gate':gate,
    'supervisor_started':started,'input_matches':True,'job_outputs':0,'launch_intents':0,
    'credentials':'retained encrypted private material; no exported values','execution_plan_id':None})
cases=Path(r'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run021_regression_001\cases')
for test,label in (('test_gui_new_empty_product_sta0','empty_gui_cleanup'),
                   ('test_fixed_worker_product_gui0','worker_gui_cleanup'),
                   ('test_public_readonly_example_i0','public_client_cleanup')):
    matches=list((cases/test).rglob('test_cleanup.json')) if (cases/test).exists() else []
    for i,p in enumerate(matches):shutil.copyfile(p,OUT/'windows_product'/f'{label}_{i}.json')
print(json.dumps({'unique':len(latest),'changed':changed,'missing':missing,'candidate':'EMPTY_PAUSED_NO_PLAN_GRANT_RUN'}))
