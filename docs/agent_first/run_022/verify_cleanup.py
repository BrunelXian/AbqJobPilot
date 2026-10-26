"""Only Run022 roots recorded by run_safe_tests; no termination or external scan."""
import json
import os
from pathlib import Path
import sys
from datetime import datetime,timezone
from audit_redaction import redact

SOURCE=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(SOURCE))
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.models import ExecutionError
from abqjobpilot.execution.paths import no_reparse

roots=[]
for p in OUT.glob('*_ROOT.json'):
    r=Path(json.loads(p.read_text())['root']).resolve();no_reparse(r)
    assert r.name.startswith('AbqJobPilot_Run022_') and r not in SOURCE.parents
    if r not in roots:roots.append(r)
identities={};secrets=set();lifecycle=[];native=[];skipped=[]
def files(root):
    for directory,dirs,names in os.walk(root,followlinks=False):
        safe=[]
        for name in dirs:
            p=Path(directory)/name
            try:no_reparse(p);safe.append(name)
            except ExecutionError:skipped.append(str(p))
        dirs[:]=safe
        for name in names:
            p=Path(directory)/name
            try:no_reparse(p)
            except ExecutionError:skipped.append(str(p));continue
            yield p
def collect(v):
    if isinstance(v,dict):
        if type(v.get('pid')) is int and type(v.get('creation_time_100ns')) is int and type(v.get('image_path')) is str:
            identities[(v['pid'],v['creation_time_100ns'])]={k:v[k] for k in ('pid','creation_time_100ns','image_path')}
        for k,x in v.items():
            if k in {'credential','operator_token'} and isinstance(x,str) and len(x)>=32:secrets.add(x)
            collect(x)
    elif isinstance(v,list):
        for x in v:collect(x)
for r in roots:
    if not r.exists():continue
    paths=list(files(r))
    for p in paths:
        if p.suffix!='.json':continue
        if p.stat().st_size>8*1024*1024:continue
        try:v=json.loads(p.read_text(encoding='utf-8'))
        except (ValueError,UnicodeError,OSError):continue
        collect(v)
        if 'lifecycle' in p.name or p.name in {'inventory.json','product_cleanup.json'}:
            lifecycle.append({'path':str(p),'record':redact(v)})
        if 'cleanup' in p.name and 'native' in p.name:native.append({'path':str(p),'record':redact(v)})
    from abqjobpilot.service_lifecycle import ServiceLifecycleManager
    from abqjobpilot.local_credentials import read_private
    for p in paths:
        if p.name!='agent_project.json':continue
        try:
            m=ServiceLifecycleManager(p.parent)
            for n in ('lifecycle.json','operator.json','standard-operator.json'):
                if m._path(n).exists():collect(read_private(m.context,m._path(n)))
        except (ExecutionError,KeyError):pass  # negative copied/incomplete identity fixtures
observed=[];alive=[]
for ident in identities.values():
    try:
        ref=ProcessReference(ident['pid'],ident)
        try:
            exit_fact=ref.exit_evidence()
            if exit_fact is None:alive.append(ident)
            observed.append({'identity':ident,'state':'MATCHED_ALIVE' if exit_fact is None else 'EXIT_OBSERVED_NOW','exit_observed_now':exit_fact})
        finally:ref.close()
    except ExecutionError as e:observed.append({'identity':ident,'state':e.code,'historical_exit_not_inferred':True})
leaks=[]
for p in OUT.rglob('*'):
    if p.is_file() and p.suffix in {'.json','.txt','.xml','.md'}:
        text=p.read_text(encoding='utf-8',errors='replace')
        if any(s in text for s in secrets):leaks.append(str(p.relative_to(OUT)))
result={'observed_at':datetime.now(timezone.utc).isoformat(),'roots':[str(r) for r in roots],
        'identity_count':len(identities),'observations':observed,'matched_alive':alive,
        'report_secret_leaks':leaks,'lifecycle_records':lifecycle,'native_records':native,
        'abaqus_calls':0,'audit_terminated_processes':0,'removed_private_files':[],
        'reparse_paths_not_followed':sorted(set(skipped))}
if not alive and not leaks:
    for r in roots:
        if not r.exists():continue
        for p in files(r):
            if p.suffix!='.json':continue
            private=(p.parent.name=='private' and p.name in {'lifecycle.json','operator.json','standard-profile.json','standard-operator.json','connection.json','offer.json'})
            private=private or p.name in {'private-bootstrap.json','private-process.json','gui-private-connection.json'}
            private=private or (p.name in {'bootstrap.json','connection.json'} and p.parent.name.startswith('test_'))
            if private:
                no_reparse(p);assert p.resolve().is_relative_to(r)
                p.unlink();result['removed_private_files'].append(str(p))
with (OUT/'CLEANUP.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps({'identities':len(identities),'alive':len(alive),'leaks':len(leaks),
                  'private_removed':len(result['removed_private_files']),'lifecycle_files':len(lifecycle),'native_files':len(native)}))
assert not alive and not leaks,'Stop: no cleanup of living identities; review exact evidence'
