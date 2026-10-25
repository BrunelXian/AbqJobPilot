"""Read only this Run's isolated test roots and Dev baseline; append evidence."""
import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
OUT=Path(__file__).resolve().parent;SOURCE=OUT.parents[2]
sys.path.insert(0,str(SOURCE))
b=json.loads((OUT/'BASELINE.json').read_text(encoding='utf-8'));ROOT=Path(b['test_root'])
assert ROOT.name.startswith('AbqJobPilot_Run019_') and ROOT.is_dir()
SUFFIX='_FINAL' if '--final' in sys.argv else ''
def write(name,value):
    name=Path(name).stem+SUFFIX+Path(name).suffix
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
def read(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except UnicodeDecodeError:return json.loads(path.read_bytes().decode('cp936'))
legacy=next(ROOT.glob('legacy_*/legacy.xml'));
if not (OUT/'legacy.xml').exists():shutil.copyfile(legacy,OUT/'legacy.xml')
cases={};batches=[]
for name in ('final','legacy','lifecycle_final02','gui_final03')+(('gui_attachment_final',) if SUFFIX else ()):
    tree=ET.parse(OUT/(name+'.xml'));items=[]
    for item in tree.iter('testcase'):
        result='FAIL' if item.find('failure') is not None or item.find('error') is not None else ('SKIP' if item.find('skipped') is not None else 'PASS')
        key=item.attrib.get('classname','')+'::'+item.attrib['name'];cases[key]={'result':result,'batch':name}
        items.append({'id':key,'result':result})
    batches.append({'batch':name,'count':len(items),'results':{k:sum(i['result']==k for i in items) for k in ('PASS','FAIL','SKIP')},'cases':items})
write('TEST_RESULTS.json',{'batches':batches,'deduplicated':len(cases),'final_counts':{k:sum(c['result']==k for c in cases.values()) for k in ('PASS','FAIL','SKIP')},'cases':cases})
expected={'README.md','README_CN.md','abqjobpilot/execution/client.py','abqjobpilot/execution/store.py',
          'abqjobpilot/execution/supervisor.py','abqjobpilot/execution_gui.py','tests/test_execution_gui.py','tests/test_execution_isolation.py'}
changes=[];unexpected=[]
for old in b['files']:
    p=SOURCE/old['path'];current=hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    if current!=old['sha256']:
        entry={**old,'current_sha256':current};changes.append(entry)
        if old['path'] not in expected:unexpected.append(entry)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()
branch=subprocess.check_output(['git','branch','--show-current'],cwd=SOURCE,text=True).strip()
conflicts=subprocess.check_output(['git','ls-files','-u'],cwd=SOURCE,text=True).strip()
write('FINAL_INTEGRITY.json',{'head':head,'branch':branch,'conflicts':conflicts,'prior_file_changes':changes,
                            'unexpected':unexpected,'excluded_live_views':b['excluded_live_views']})
assert head==b['head'] and branch=='Develop' and not conflicts and not unexpected
# Only recorded identities inside this Run's newly-created root. No process scan.
identities={};credential_files=[];cleanup=[];native=[]
def visit(v):
    if isinstance(v,dict):
        if all(k in v for k in ('pid','creation_time_100ns','image_path')):
            identities[(v['pid'],v['creation_time_100ns'])]={k:v[k] for k in ('pid','creation_time_100ns','image_path')}
        return any(k in {'credential','operator_token'} and isinstance(value,str) and len(value)>=32 or visit(value) for k,value in v.items())
    if isinstance(v,list):return any(visit(i) for i in v)
    return False
for p in ROOT.rglob('*.json'):
    if p.stat().st_size>8*1024*1024:continue
    try:value=read(p)
    except (ValueError,OSError,UnicodeError):continue
    if visit(value):credential_files.append(str(p.relative_to(ROOT)))
    if p.name=='product_cleanup.json':cleanup.append({'path':str(p.relative_to(ROOT)),'result':value})
    if p.name=='cleanup.json' and isinstance(value,dict):native.append({'path':str(p.relative_to(ROOT)),'result':value})
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.models import ExecutionError
post=[]
for identity in identities.values():
    try:
        ref=ProcessReference(identity['pid'],identity)
        try:result=ref.exit_evidence();state='IDENTITY_MATCHED_LIVE' if result is None else 'MATCHED_EXIT_OBSERVED_NOW'
        finally:ref.close()
    except ExecutionError as exc:state=exc.code;result=None
    post.append({'identity':identity,'state':state,'observation':result})
write('CLEANUP.json',{'root':str(ROOT),'product_cleanup':cleanup,'native_cleanup':native,
                    'remaining_private_credential_files':credential_files,'recorded_identity_count':len(identities),
                    'postcheck':post,'live_matches':sum(v['state']=='IDENTITY_MATCHED_LIVE' for v in post),
                    'note':'Postcheck is not retroactive exit proof. Tests hold exact handles for exit evidence. No historical instance or process scan.'})
assert not credential_files and not any(v['state']=='IDENTITY_MATCHED_LIVE' for v in post)
picture=ROOT/'gui_final03/test_product_gui_start_worker_0/gui_A/window.png'

if not (OUT/'windows_final/normal_gui.png').exists():shutil.copyfile(picture,OUT/'windows_final/normal_gui.png')
if SUFFIX:
    folder=ROOT/'gui_attachment_final/test_product_gui_start_worker_0'
    shutil.copyfile(folder/'gui_A/window.png',OUT/'windows_final/normal_gui_final.png')
    shutil.copyfile(folder/'windows_product_lifecycle.json',OUT/'windows_final/gui_attachment_product.json')
race=ROOT/'lifecycle_final02/test_two_os_clients_race_same_0/cross_process_race.json'
if race.exists() and not (OUT/'windows_final/cross_process_race.json').exists():shutil.copyfile(race,OUT/'windows_final/cross_process_race.json')
print(json.dumps({'cases':len(cases),'counts':{k:sum(c['result']==k for c in cases.values()) for k in ('PASS','FAIL','SKIP')},'identities':len(identities),'credentials_remaining':len(credential_files),'unexpected_changes':len(unexpected)}))
