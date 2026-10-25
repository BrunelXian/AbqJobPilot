"""Append-only evidence review for this completed acceptance. No control calls."""
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, r'D:\Projects\abqjobpilot_dev')
from examples.agent_first.product_standard_acceptance import verify
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution.store import open_existing_read_only
from abqjobpilot.execution.process_handles import ProcessReference

OUT = Path(__file__).parent
EXPECTED = 'efdee66a3639bbfe95d084e90036e6376eaa3120c975918423afedf0b72220e1'

def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))

def save(name, value):
    with (OUT / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)

body = verify(OUT.parent / 'ACCEPTANCE_MANIFEST.json', EXPECTED)
manager = ServiceLifecycleManager(body['root'])
client, context, health = manager.connect()
receipt = client.receipt(body['operation_keys']['submit'])
run = client.run(receipt['run_id'])
view = client.project_view()
store = open_existing_read_only(context)
with store.read() as db:
    db.execute('BEGIN')
    counts = {t: db.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
              for t in ('plans', 'grants', 'runs', 'receipts', 'consumption',
                        'events', 'validations', 'reconciliations')}
    slot = db.execute('SELECT run_id FROM slot WHERE id=1').fetchone()[0]
    stored_plan = json.loads(db.execute('SELECT body FROM plans WHERE plan_id=?',
                                      (body['plan']['plan_id'],)).fetchone()[0])
    consumed = [dict(r) for r in db.execute('SELECT grant_id,run_id FROM consumption')]
    db.rollback()
service = manager.inspect()
ref = ProcessReference(service['process']['pid'], service['process'])
try:
    owner_os = {'identity': ref.identity, 'exit': ref.exit_evidence()}
finally:
    ref.close()
before = read('RESULT_BEFORE_STOP.json')
save('FINAL_READONLY_STATE.json', {
    'observed_at': time.time(), 'manifest_body_sha256': EXPECTED,
    'referenced_material_count': len(body['materials']), 'materials': 'MATCH',
    'stored_plan_matches_manifest': stored_plan == body['plan'],
    'counts': counts, 'consumption': consumed, 'slot_run_id': slot,
    'owner_id': client.endpoint['owner_id'], 'owner_os': owner_os,
    'gate': client.dispatch_gate(), 'project_view': view,
    'receipt_equal_before_stop': receipt == before['receipt'],
    'run_equal_before_stop': run == before['run'],
    'run_revision': run['revision'], 'attempt_no': run['attempt_no'],
    'abaqus_calls_this_audit': 0, 'mutation_calls_this_audit': 0,
})

engineering = Path(body['plan']['engineering'])
validation = read('PERSISTED_EVIDENCE.json')['validations'][0]
review = {'read_at': time.time(), 'files': [], 'runtime_lines': [],
          'selected_dat_lines': [], 'completion_lines': [],
          'source': 'post_execution_read_only_review_no_service_evidence_written'}
for ext in ('dat', 'sta', 'msg'):
    p = engineering / (body['plan']['job_name'] + '.' + ext)
    s = p.stat()
    assert s.st_size <= 1048576
    raw = p.read_bytes()
    after = p.stat()
    assert (s.st_ino, s.st_size, s.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns)
    digest = hashlib.sha256(raw).hexdigest()
    original = next(x for x in validation['details']['artifacts'] if x['logical_ref'] == 'output:' + ext)
    review['files'].append({'path': str(p), 'sha256': digest, 'size': len(raw),
        'same_as_service_validation': original['digest'] == 'sha256:' + digest,
        'same_file_identity': original['device'] == s.st_dev and original['inode'] == s.st_ino,
        'mtime_ns': s.st_mtime_ns, 'ctime_ns': s.st_ctime_ns,
        'not_older_than_intent': min(s.st_mtime_ns, s.st_ctime_ns) >= run['launch_intent']['intent_at_ns']})
    for n, line in enumerate(raw.decode('cp936', errors='strict').splitlines(), 1):
        if 'Abaqus 2024' in line or 'ABAQUS 2024' in line:
            review['runtime_lines'].append({'file': ext, 'line': n, 'text': line.strip()})
        if 'ANALYSIS HAS' in line or 'ANALYSIS COMPLETE' in line or 'JOB TIME SUMMARY' in line:
            review['completion_lines'].append({'file': ext, 'line': n, 'text': line.strip()})
        if ext == 'dat' and n in (183,187,200,203,215,218,224,227,228,231,235):
            review['selected_dat_lines'].append({'line': n, 'text': line.strip()})
review['primary_comparisons'] = [x for x in validation['details']['comparisons'] if x['group'] == 'primary']
review['odb_content_validation'] = 'NOT_RUN'
review['log_present'] = (engineering / (body['plan']['job_name'] + '.log')).exists()
output = Path(context.runtime_root) / 'standard_runs' / run['run_id']
review['stdio'] = []
for name in ('stdout.bin', 'stderr.bin'):
    p = output / name
    raw = p.read_bytes()
    assert len(raw) <= 1048576
    # Raw output remains at source. Only bounded product/completion lines leave it.
    lines = raw.decode('cp936', errors='replace').splitlines()
    review['stdio'].append({'path': str(p), 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
        'selected_lines': [{'line': i, 'text': t.strip()} for i,t in enumerate(lines,1)
            if name == 'stdout.bin' and ('Abaqus JOB ' in t or 'Abaqus 2024' in t
                or t.startswith('Begin Abaqus/Standard') or t.startswith('End Abaqus/Standard'))]})
save('TEXT_REVIEW.json', review)

rows = [json.loads(line) for line in (OUT / 'OBSERVATIONS.jsonl').read_text().splitlines()]
first_exits = {}
for row in rows:
    for name, data in row['os'].items():
        if data.get('exit') is not None and name not in first_exits:
            first_exits[name] = {'sample_at': row['observed_at'], **data}
closed = lambda row: all(row['os'].get(k, {}).get('exit') is not None for k in ('gui','gui_venv'))
solver_alive = lambda row: any(d.get('identity',{}).get('pid') == 7604 and d.get('exit') is None
                              and 'error' not in d for d in row['os'].values())
both = [r['observed_at'] for r in rows if closed(r) and solver_alive(r)]
owner_survives = [r['observed_at'] for r in rows if closed(r) and r['os']['owner'].get('exit') is None]
alive_times = [r['observed_at'] for r in rows if solver_alive(r)]
save('OS_TIMELINE_REVIEW.json', {
    'first_sample': rows[0]['observed_at'], 'last_sample': rows[-1]['observed_at'],
    'first_exit_observations': first_exits,
    'last_observed_solver_alive': max(alive_times) if alive_times else None,
    'gui_and_venv_exited_solver_alive_samples': both,
    'gui_and_venv_exited_owner_alive_first_sample': owner_survives[0] if owner_survives else None,
    'cross_gui_close_solver_liveness': 'OBSERVED' if both else 'NOT_OBSERVED',
    'observer_closed': read('OBSERVER_CLOSED.json'),
    'meaning': 'Sample and retained-handle observations, not inferred exact exit times.'
})
print(json.dumps({'materials': 'MATCH', 'counts': counts, 'slot': slot,
    'run_preserved': run == before['run'], 'receipt_preserved': receipt == before['receipt'],
    'cross_gui_close_solver_liveness': 'OBSERVED' if both else 'NOT_OBSERVED',
    'extra_abaqus_calls': 0}))
