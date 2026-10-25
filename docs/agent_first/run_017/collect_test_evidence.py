"""Audit only the two explicit Run017 roots. Never stop processes or clean old data."""
import collections
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent
SOURCE = OUT.parents[2]
sys.path.insert(0, str(SOURCE))
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.models import ExecutionError

root = Path(json.loads((OUT / 'TEST_SELECTION.json').read_text())['root'])
legacy = Path(next(s.split('=', 1)[1] for s in (OUT / 'LEGACY_TEST_LOG.txt').read_text().splitlines()
                   if s.startswith('ISOLATED_ROOT=')))
results = []
for label, path in [('initial', root/'logs/regression.xml'),
                    ('isolated_recheck', root/'logs/isolation_recheck.xml'), ('legacy', legacy/'result.xml')]:
    tree = ET.parse(path)
    cases = [{'id': n.attrib['classname'] + '::' + n.attrib['name'],
              'result': 'FAIL' if n.find('failure') is not None or n.find('error') is not None else
                        'SKIP' if n.find('skipped') is not None else 'PASS'} for n in tree.iter('testcase')]
    results.append({'batch': label, 'counts': dict(collections.Counter(c['result'] for c in cases)),
                    'tests': cases})
    shutil.copyfile(path, OUT / (label + '.xml'))
shutil.copyfile(root/'logs/regression.txt', OUT/'INITIAL_TEST_LOG.txt')
latest = {c['id']: c['result'] for r in results for c in r['tests']}
(OUT/'TEST_RESULTS.json').write_text(json.dumps({'batches':results,'distinct_last_result':dict(collections.Counter(latest.values()))}, indent=2))

identities = {}
def walk(x):
    if isinstance(x, dict):
        if type(x.get('pid')) is int and type(x.get('creation_time_100ns')) is int and x.get('image_path'):
            # Real timestamps from this test session only, not old fixture history.
            if x['creation_time_100ns'] >= 134373080000000000:
                identities[(x['pid'],x['creation_time_100ns'],x['image_path'])] = {
                    k:x[k] for k in ('pid','creation_time_100ns','image_path')}
        for v in x.values(): walk(v)
    elif isinstance(x, list):
        for v in x: walk(v)
lifecycle, inventories, cleanups = [], [], []
for p in root.rglob('*.json'):
    try: value=json.loads(p.read_text(encoding='utf-8'))
    except (ValueError,UnicodeError,OSError):continue
    walk(value)
    if p.name == 'lifecycle.json': lifecycle.extend(value if isinstance(value,list) else [])
    if p.name == 'inventory.json' and isinstance(value,dict) and 'all_owned_processes_exited' in value:
        inventories.append({'path':str(p.relative_to(root)),**{k:value[k] for k in
           ('all_owned_processes_exited','credential_absent_from_remaining_files','recent_unchanged') if k in value}})
    if p.name == 'cleanup.json':cleanups.append({'path':str(p.relative_to(root)), 'record':value})
current=[]
for ident in identities.values():
    try:
        ref=ProcessReference(ident['pid'],ident)
        try:
            evidence=ref.exit_evidence()
            current.append({'identity':ident,'observation':'MATCHED_EXITED' if evidence else 'MATCHED_LIVE', 'exit':evidence})
        finally:ref.close()
    except ExecutionError as exc:
        current.append({'identity':ident,'observation':exc.code,
                        'meaning':'No matching process confirmed now; not retrospective exit proof'})
private=[str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and 'private' in p.parts]
def has_exit(v):
    return bool((v.get('actual_process_handle_signaled') and v.get('exited')) or
                (v.get('handle_closed') and v.get('exit', {}).get('exit_source') == 'retained_windows_handle'
                 and type(v['exit'].get('exit_code')) is int))
out={'test_root':str(root),'legacy_root':str(legacy), 'lifecycle_entries':len(lifecycle),
     'lifecycle_all_signaled_or_retained_exit':all(has_exit(v) for v in lifecycle),
     'inventories':inventories,'native_cleanup':cleanups,'current_exact_identity_observations':current,
     'current_counts':dict(collections.Counter(v['observation'] for v in current)),
     'private_directory_files_remaining':private,
     'termination_by_this_audit':False,'files_deleted_by_this_audit':0,
     'scope':'Only newly created Run017 tests; no Run016 owner discovery or query'}
(OUT/'TEST_CLEANUP.json').write_text(json.dumps(out,indent=2))
dest=OUT/'windows_evidence';dest.mkdir(exist_ok=True)
for p in (root/'evidence').iterdir():
    if p.suffix in ('.json','.png'):shutil.copyfile(p,dest/p.name)
print(json.dumps({'results':dict(collections.Counter(latest.values())),'lifecycle':len(lifecycle),
                 'inventories':len(inventories),'current':out['current_counts'],'private':len(private)}))
