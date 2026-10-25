"""Run014 explicit read-only audit; no owner acquisition, probing or mutations.

Creates a new audit JSON in this Run014 folder. Refuses overwrite. No source
materials, database records, artifacts, permits or execution controls are edited.
"""
import hashlib
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[3];sys.path.insert(0,str(REPO))
from abqjobpilot.execution.models import ProjectContext,canonical_json,digest
from abqjobpilot.execution.store import ReadOnlyStore
from abqjobpilot.execution.closeout import preview_store


def main():
    package=json.loads((REPO/'docs/agent_first/run_013/ACCEPTANCE_MANIFEST.json').read_text(encoding='utf-8'))
    assert digest(package['body'])=='sha256:3c59461d53e658eb9894d6936bd405f85a7f27b6ebc3deb5343c81d8411ceebe'
    ctx=ProjectContext(**package['body']['context'])
    assert Path(ctx.test_root).name=='AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e'
    rid='r_609c9bbfd9c54b3ca2fce23bbd6059e4'
    db=Path(ctx.execution_store);before=hashlib.sha256(db.read_bytes()).hexdigest()
    store=ReadOnlyStore(ctx)
    assessment=preview_store(store,ctx,rid)
    with store.read() as c:
        c.execute('BEGIN')
        run=json.loads(c.execute('SELECT body FROM runs WHERE run_id=?',(rid,)).fetchone()[0])
        counts={t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in
            ('runs','events','consumption','validations','reconciliations','management_receipts')}
    after=hashlib.sha256(db.read_bytes()).hexdigest()
    original=json.loads(Path(__file__).with_name('CURRENT_READONLY.json').read_text(encoding='utf-8'))
    value={'source':'strict_read_only_current_database; no responsive owner attested',
        'assessment':assessment,'database_bytes_unchanged_by_read':before==after,'database_sha256':after,
        'run_unchanged_since_initial_read':run==original['run'],
        'counts_unchanged_since_initial_read':counts==original['counts'],'counts':counts,
        'gate_unchanged_since_initial_read':assessment['recorded_gate']==original['gate'],
        'slot_unchanged_since_initial_read':assessment['resources']['slot_run_id']==original['slot_run_id'],
        'permission_issued':False,'disposition_applied':False,'owner_acquired_or_stopped':False,'abaqus_calls':0}
    target=Path(__file__).with_name('CURRENT_CLOSEOUT_PREVIEW.json')
    with target.open('x',encoding='utf-8') as f:f.write(canonical_json(value))
    print(canonical_json({k:v for k,v in value.items() if k!='assessment'}))


if __name__=='__main__':main()
