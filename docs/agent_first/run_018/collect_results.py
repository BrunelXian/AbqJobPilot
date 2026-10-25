"""Collect only this Run018's explicit test root. Never inspect retained owners."""
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=Path(r'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run018_eobivebj')
def write(name, value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

dest=HERE/'test_evidence';dest.mkdir(exist_ok=True)
batches=[];unique={}
for label,path in [('attach01',ROOT/'attach01.xml'),('attach02',ROOT/'attach02.xml'),
        ('regression',ROOT/'regression.xml'),('legacy',next(ROOT.glob('legacy_*/legacy.xml'))),
        ('final_attachment',ROOT/'final_attachment.xml')]:
    tree=ET.parse(path);cases=[]
    for c in tree.iter('testcase'):
        key=c.attrib['classname']+'::'+c.attrib['name']
        # Wording-only rename: initial name overclaimed reparse testing; one case.
        key=key.replace('::test_legacy_directory_and_reparse_rejected','::test_legacy_directory_rejected')
        result='FAIL' if c.find('failure') is not None or c.find('error') is not None else ('SKIP' if c.find('skipped') is not None else 'PASS')
        item={'id':key,'result':result,'batch':label,'seconds':c.get('time')}
        cases.append(item);unique[key]=item
    batches.append({'batch':label,'path':str(path),'count':len(cases),
        'results':{s:sum(c['result']==s for c in cases) for s in ['PASS','FAIL','SKIP']}})
    shutil.copyfile(path,dest/(label+'.xml'))
for name in ['attach01','attach02','regression','legacy','legacy02','final_attachment']:
    path=ROOT/(name+'.log')
    if path.exists():shutil.copyfile(path,dest/(name+'.log'))
write('TEST_RESULTS.json',{'batches':batches,'xml_executed':sum(b['count'] for b in batches),
    'initial_console_only':{'selection':'tests/test_project_view.py before namespace projection case was added',
       'count':14,'pass':14,'fail':0,'skip':0,'seconds':11.26,'source':'exec output session 27856; included again in regression'},
    'unique_count':len(unique),'last_results':{s:sum(c['result']==s for c in unique.values()) for s in ['PASS','FAIL','SKIP']},
    'cases':list(unique.values())})

windows=HERE/'windows_evidence';windows.mkdir(exist_ok=True)
for folder in [ROOT/'regression_evidence/r12',ROOT/'regression_evidence/r15',ROOT/'regression_evidence/r16',ROOT/'final_evidence']:
    for path in folder.glob('*'):
        if path.suffix in {'.json','.png'}:shutil.copyfile(path,windows/path.name)

inventories=[];lifecycles=[];native=[];private_files=[]
for path in ROOT.rglob('inventory.json'):
    inventories.append({'path':str(path.relative_to(ROOT)),'value':json.loads(path.read_text(encoding='utf-8'))})
for path in ROOT.rglob('lifecycle.json'):
    lifecycles.append({'path':str(path.relative_to(ROOT)),'value':json.loads(path.read_text(encoding='utf-8'))})
for path in ROOT.rglob('io.json'):
    v=json.loads(path.read_text(encoding='utf-8'))
    if v.get('managed_handle_cleanup'):native.append({'path':str(path.relative_to(ROOT)),'value':v['managed_handle_cleanup']})
for path in ROOT.rglob('*'):
    if path.is_file() and (path.name in {'private-bootstrap.json','private-process.json','gui-private-connection.json'}
            or path.parent.name=='private' or path.name in {'bootstrap.json','connection.json'}):
        private_files.append(str(path.relative_to(ROOT)))
write('CLEANUP.json',{'scope':'only Run018 new test root; no other process inspected or stopped',
    'root':str(ROOT),'inventories':inventories,'lifecycles':lifecycles,'managed_handles':native,
    'remaining_possible_private_files':private_files})
print(json.dumps({'batches':batches,'unique':len(unique),'remaining_possible_private_files':private_files}))
