"""Read-only result aggregation; only this Run's XML and baseline are inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

batches=[];latest={}
for name in ('unit_01','windows_01','windows_02','windows_03','windows_04','final','legacy','legacy_single','chain_final','ui_final','verified'):
    cases=[]
    for case in ET.parse(OUT/(name+'.xml')).iter('testcase'):
        key=case.attrib['classname']+'::'+case.attrib['name']
        verdict='FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
        item={'id':key,'result':verdict};cases.append(item);latest[key]=item
    batches.append({'batch':name,'count':len(cases),'counts':{k:sum(c['result']==k for c in cases) for k in ('PASS','FAIL','SKIP')},'cases':cases})
save('TEST_RESULTS.json',{'unique_count':len(latest),'latest_counts':{k:sum(c['result']==k for c in latest.values()) for k in ('PASS','FAIL','SKIP')},
                          'batches':batches,'deduplication':'classname + test name including parameters; latest actual result'})
base=json.loads((OUT/'BASELINE.json').read_text(encoding='utf-8'))
changed=[];missing=[]
for name,expected in base['hashes'].items():
    path=ROOT/name
    if not path.is_file():missing.append(name)
    elif hashlib.sha256(path.read_bytes()).hexdigest()!=expected:changed.append(name)
status=subprocess.check_output(['git','status','--porcelain=v1'],cwd=ROOT).decode()
save('FINAL_INTEGRITY.json',{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
    'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT).decode().strip(),
    'conflicts':subprocess.check_output(['git','ls-files','-u'],cwd=ROOT).decode(),'prior_file_count':len(base['hashes']),
    'changed_prior_files':changed,'missing_prior_files':missing,'status':status,
    'live_history_exclusion':'Run016 view.json files were excluded at baseline; no owner queried or operated'})
print(json.dumps({'unique':len(latest),'latest':{k:sum(c['result']==k for c in latest.values()) for k in ('PASS','FAIL','SKIP')},'changed':changed,'missing':missing}))
