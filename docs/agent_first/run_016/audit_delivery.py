"""Read-only evidence audit; writes only this delivery's FINAL_AUDIT.json."""
import hashlib,json,sys,xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[3];sys.path.insert(0,str(SOURCE))
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.models import ExecutionError,canonical_json
p=Path(__file__).parent
base=json.loads((p/'BASELINE.json').read_text(encoding='utf-8'))
protected=[x['path'] for x in base['protected'] if not Path(x['path']).exists() or hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()!=x['sha256']]
latest={};batches=[]
for name in ('unit_001','windows_001','windows_002','regression_001','final_affected','deadline_final','client_cleanup'):
    root=ET.parse(p/(name+'.xml')).getroot();counts=Counter()
    for c in root.iter('testcase'):
        state='FAIL' if c.find('failure') is not None or c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
        counts[state]+=1;latest[(c.get('classname'),c.get('name'))]={'state':state,'batch':name}
    batches.append({'batch':name,'counts':dict(counts),'seconds':root.find('testsuite').get('time')})
roots=[]
for name in ('UNIT_TEMP_001.txt','WINDOWS_TEMP_001.txt','WINDOWS_TEMP_002.txt','REGRESSION_TEMP.txt','FINAL_TEMP.txt','DEADLINE_TEMP.txt','CLIENT_TEMP.txt'):
    root=Path((p/name).read_text(encoding='utf-8-sig').strip())
    assert root.is_absolute() and root.name.startswith(('AbqJobPilot_Run016_','AbqJobPilot_R16_'))
    roots.append(root)
identities={};parse_count=0;private=[];native=[]
def walk(v):
    if isinstance(v,dict):
        if type(v.get('pid')) is int and type(v.get('creation_time_100ns')) is int and isinstance(v.get('image_path'),str):
            image=Path(v['image_path'])
            if image.name.lower() in ('python.exe','pythonw.exe') and str(image).lower().startswith(('d:\\program files\\python312\\','d:\\xianlab\\envs\\langchainenv\\')):
                identities[(v['pid'],v['creation_time_100ns'])]={k:v[k] for k in ('pid','creation_time_100ns','image_path')}
        for child in v.values():walk(child)
    elif isinstance(v,list):
        for child in v:walk(child)
for root in roots:
    for f in root.rglob('*.json'):
        if f.stat().st_size>4*1024*1024:continue
        if f.name in ('bootstrap.json','connection.json','private-process.json','gui-private-connection.json') or f.parent.name=='private':private.append(str(f))
        try:v=json.loads(f.read_text(encoding='utf-8'));walk(v);parse_count+=1
        except (ValueError,UnicodeError):continue
        if f.name=='cleanup.json' and isinstance(v,dict) and 'native_handles' in v:native.append({'path':str(f),'facts':v})
observations=[]
for ident in identities.values():
    ref=None
    try:
        ref=ProcessReference(ident['pid'],ident);exit=ref.exit_evidence()
        state='MATCHING_LIVE' if exit is None else 'MATCHING_EXITED'
    except ExecutionError as exc:state=exc.code;exit=None
    finally:
        if ref:ref.close()
    observations.append({'identity':ident,'current_status':state,'current_exit_observation':exit})
changed=[x['path'] for x in base['sources'] if hashlib.sha256((SOURCE/x['path']).read_bytes()).hexdigest()!=x['sha256']]
audit={'protected_count':len(base['protected']),'protected_changed':protected,'changed_prior_sources':changed,
    'test_batches':batches,'latest_unique':dict(Counter(x['state'] for x in latest.values())),
    'latest_results':[{'test':a+'::'+b,**v} for (a,b),v in latest.items()],
    'temporary_roots':[str(r) for r in roots],'json_evidence_files':parse_count,
    'recorded_python_identities_checked':len(identities),'current_process_status_counts':dict(Counter(x['current_status'] for x in observations)),
    'process_observations':observations,'private_connection_material_remaining':private,'native_closure_records':native,'abaqus_calls':0,
    'limits':'Current absence is not historical exit evidence. Early failed harness native handles may close only at owner OS exit; final successful cases record explicit closure.'}
(p/'FINAL_AUDIT.json').write_text(canonical_json(audit),encoding='utf-8')
print(json.dumps({k:audit[k] for k in ('protected_count','protected_changed','changed_prior_sources','test_batches','latest_unique',
    'json_evidence_files','recorded_python_identities_checked','current_process_status_counts','private_connection_material_remaining')},indent=2))
