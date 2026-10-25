"""Only the exact new Run021B test roots; never the retained candidate.

No termination. Later identity absence is not historical exit evidence.
"""
import json
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SOURCE))
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.models import ExecutionError
from abqjobpilot.execution.paths import no_reparse

OUT = Path(__file__).parent
ROOTS = [Path(r'C:\Users\wuxia\AppData\Local\Temp')/n for n in
         ('AbqJobPilot_Run021B_unit_001','AbqJobPilot_Run021B_windows_001','AbqJobPilot_Run021B_windows_002','AbqJobPilot_Run021B_windows_003','AbqJobPilot_Run021B_regression_001','AbqJobPilot_Run021B_regression_002','AbqJobPilot_Run021B_regression_003','AbqJobPilot_Run021B_control_final','AbqJobPilot_Run021B_control_verified','AbqJobPilot_Run021B_isolation_final','AbqJobPilot_Run021B_isolation_verified','AbqJobPilot_Run021B_legacy_001')]
identities = {}; secrets = set()


def collect(value):
    if isinstance(value, dict):
        if type(value.get('pid')) is int and type(value.get('creation_time_100ns')) is int and type(value.get('image_path')) is str:
            identities[(value['pid'], value['creation_time_100ns'])] = {k:value[k] for k in ('pid','creation_time_100ns','image_path')}
        for k, v in value.items():
            if k in {'credential','operator_token'} and isinstance(v,str) and len(v)>=32:
                secrets.add(v)
            collect(v)
    elif isinstance(value,list):
        for v in value: collect(v)


ROOTS.append(Path(r'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run021B_windows_verified'))

for root in ROOTS:
    no_reparse(root)
    if not root.exists(): continue
    for p in root.rglob('*.json'):
        no_reparse(p)
        if p.stat().st_size > 4*1024*1024: continue
        try: collect(json.loads(p.read_text(encoding='utf-8')))
        except (UnicodeError,ValueError,OSError): pass
    from abqjobpilot.service_lifecycle import ServiceLifecycleManager
    for p in root.rglob('agent_project.json'):
        try:
            m=ServiceLifecycleManager(p.parent)
            # Test profiles deliberately cannot pass production StandardConfig
            # verification. Decrypt only for the local no-output secret scan;
            # do not configure/instantiate a Backend or weaken its validator.
            from abqjobpilot.local_credentials import read_private
            for name in ('lifecycle.json','operator.json','standard-operator.json'):
                if m._path(name).exists():collect(read_private(m.context,m._path(name)))
        except (ExecutionError,KeyError): pass

observed=[]; alive=[]
for identity in identities.values():
    try:
        ref=ProcessReference(identity['pid'],identity)
        try:
            exited=ref.exit_evidence()
            if exited is None: alive.append(identity)
            observed.append({'identity':identity,'exit_observed_now':exited,'state':'MATCHED_ALIVE' if exited is None else 'EXIT_OBSERVED_NOW'})
        finally: ref.close()
    except ExecutionError as exc:
        observed.append({'identity':identity,'state':exc.code,'historical_exit_not_inferred':True})
leaks=[]
for p in OUT.rglob('*'):
    if p.is_file() and p.suffix in {'.json','.txt','.xml','.md'}:
        content=p.read_text(encoding='utf-8',errors='replace')
        if any(secret in content for secret in secrets): leaks.append(str(p.relative_to(OUT)))
assert not alive and not leaks, 'No cleanup while own matching process lives or report leaks secrets'
removed=[]
for root in ROOTS:
    if not root.exists(): continue
    for p in root.rglob('*.json'):
        private=(p.parent.name=='private' and p.name in {'lifecycle.json','operator.json','standard-profile.json','standard-operator.json','connection.json','offer.json'})
        private=private or p.name in {'private-bootstrap.json','private-process.json','gui-private-connection.json'}
        private=private or (p.name in {'bootstrap.json','connection.json'} and p.parent.name.startswith('test_'))
        if private:
            no_reparse(p); assert p.resolve().is_relative_to(root.resolve())
            p.unlink(); removed.append(str(p))
result={'roots':[str(p) for p in ROOTS],'identity_count':len(identities),'matched_alive':alive,
        'observations':observed,'report_secret_leaks':leaks,'removed_private_files':removed,
        'terminated_processes':0,'candidate_credentials':'retained outside these roots; no candidate owner started',
        'abaqus_calls':0}
with (OUT/'CLEANUP_FINAL.json').open('x',encoding='utf-8') as f:f.write(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'identities':len(identities),'matched_alive':len(alive),'removed_private_files':len(removed),'secret_leaks':len(leaks)}))
