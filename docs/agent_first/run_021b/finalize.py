"""Final append-only read audit, no owner or business writes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

SOURCE=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path.insert(0,str(SOURCE))
from abqjobpilot.execution.models import digest
from abqjobpilot.product_standard import inspect_preparation
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution.standard_contract import identity

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(name,v):
    with (OUT/name).open('x',encoding='utf-8') as f:f.write(json.dumps(v,ensure_ascii=False,indent=2))

base=read(OUT/'BASELINE.json');changed=[];missing=[]
for name,h in base['files'].items():
    p=SOURCE/name
    if not p.is_file():missing.append(name)
    elif hashlib.sha256(p.read_bytes()).hexdigest()!=h:changed.append(name)
allowed={'abqjobpilot/execution/store.py','abqjobpilot/execution/service.py','abqjobpilot/execution/client.py',
    'abqjobpilot/execution/standard_contract.py','tests/test_execution_isolation.py','abqjobpilot/service_owner.py',
    'abqjobpilot/execution/lifecycle.py','abqjobpilot/execution/supervisor.py','abqjobpilot/service_lifecycle.py'}
assert not missing and set(changed)==allowed
def git(*a):return subprocess.check_output(['git',*a],cwd=SOURCE,text=True).strip()
assert git('branch','--show-current')=='Develop' and git('rev-parse','HEAD')==base['head'] and not git('ls-files','-u')
save('FINAL_INTEGRITY.json',{'head':base['head'],'branch':'Develop','baseline_count':len(base['files']),
     'changed_prior_files':changed,'missing_prior_files':missing,'other_prior_files_unchanged':True,'conflicts':[],
     'status':git('status','--porcelain'),'version':'0.3.0.dev0'})

package=read(OUT/'ACCEPTANCE_MANIFEST.json');body=package['body']
assert digest(body).split(':')[1]==package['body_sha256']
assert all(identity(m['path'])==m for m in body['materials'])
prepared=inspect_preparation(body['root']);m=ServiceLifecycleManager(body['root'])
assert prepared['plan']==body['plan']
assert prepared['counts']==dict(plans=1,grants=0,runs=0,receipts=0,consumption=0)
assert prepared['gate']['state']=='PAUSED' and prepared['gate']['version']==1 and prepared['supervisor_started']=='0'
assert m.inspect()['state']=='NOT_RUNNING'
root=Path(body['root']);assert not list((root/'engineering').glob(body['job']+'.*'))
assert not list((root/'engineering').glob('.*.intent.json'))
assert not list((root/'private').glob('acceptance-*.json'))
save('CANDIDATE_FINAL_CHECK.json',{'body_sha256':package['body_sha256'],'plan_id':body['plan']['plan_id'],
    'materials_matching':len(body['materials']),'counts':prepared['counts'],'gate':prepared['gate'],
    'supervisor_started':'0','service':m.inspect(),'job_outputs':0,'attempts':0,'operator_action_records':0,'abaqus_calls':0})

files=['regression_002.xml','regression_003.xml','control_verified.xml','isolation_verified.xml','legacy.xml','windows_verified.xml']
cases={};batches=[]
for name in files:
    rows=[]
    for c in ET.parse(OUT/name).iter('testcase'):
        key=c.get('classname')+'::'+c.get('name')
        result='FAIL' if c.find('failure') is not None or c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
        cases[key]={'result':result,'source':name};rows.append({'id':key,'result':result})
    batches.append({'file':name,'rows':rows})
assert len(cases)==392 and all(v['result']=='PASS' for v in cases.values())
save('TEST_RESULTS_FINAL.json',{'unique_count':len(cases),'PASS':len(cases),'FAIL':0,'SKIP':0,
    'deduplication':'classname::parameterized name; final verified result, retries not extra cases',
    'cases':cases,'batches':batches})
print(json.dumps({'candidate':package['body_sha256'],'unique_pass':len(cases),'baseline_changed':len(changed),'all_other_prior_files_unchanged':True}))
