"""Single-use audit orchestration of existing trusted Run014 APIs; not a new API.

User authorization is in the current conversation, referenced by the adjacent
AUTHORIZATION_SOURCE.md. No SQL writes, backend, Supervisor or child processes.
Existing journal/owner refusals are fatal. This file must not be rerun to retry.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

REPO = Path(r'D:\Projects\abqjobpilot_dev')
OUT = Path(__file__).resolve().parent
ROOT = Path(r'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e')
RID = 'r_609c9bbfd9c54b3ca2fce23bbd6059e4'
sys.path.insert(0, str(REPO))

def no_external_process(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.kill', 'os.startfile', 'os.startfile/2'}:
        raise RuntimeError('Process creation/control forbidden in disposition audit')

sys.addaudithook(no_external_process)

from abqjobpilot.execution import ExecutionService
from abqjobpilot.execution.closeout import RELEASE, issue, snapshot, administratively_released
from abqjobpilot.execution.models import now, digest, require, ExecutionError
from abqjobpilot.execution.store import ReadOnlyStore, acquire_supervisor_store
from abqjobpilot.execution.supervisor import load_bootstrap

def save(name, value):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def at():
    return datetime.now(timezone.utc).isoformat()

TABLES = ('runs', 'events', 'consumption', 'observations', 'validations',
          'reconciliations', 'management_grants', 'management_receipts',
          'management_consumption', 'control_events')

def read_state(store):
    with store.read() as c:
        c.execute('BEGIN')
        data = snapshot(c, RID)
        data['audit'] = {
            'counts': {t: c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in TABLES},
            'execution_grants_digest': digest([dict(r) for r in c.execute('SELECT * FROM grants ORDER BY grant_id')]),
            'execution_consumption': [dict(r) for r in c.execute('SELECT * FROM consumption')],
            'already_disposed': administratively_released(c, data['run']),
            'management_receipts': [json.loads(r[0]) for r in c.execute('SELECT body FROM management_receipts')],
        }
        return data

def files_before():
    # Read only the explicitly scoped experiment; ODB is stat-only, never opened.
    entries = {}
    for p in sorted((ROOT/'engineering').rglob('*')):
        if p.is_file():
            s = p.stat()
            entries[str(p)] = {'size': s.st_size, 'mtime_ns': s.st_mtime_ns,
                              'sha256': None if p.suffix.lower()=='.odb' else sha(p)}
    for rel in ('private/bootstrap.json', 'private/connection.json', 'project/owner.json', 'project/owner.lock'):
        p = ROOT/rel
        if p.is_file():
            s=p.stat(); entries[str(p)]={'size':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256':sha(p)}
    return entries

def matching_history(before, after):
    return all(before[k] == after[k] for k in ('run','plan','slot','receipts','events','observations','validations','decisions','consumed'))

def main():
    save('INVOCATION_STARTED.json', {'at':at(),'run_id':RID,'python':sys.executable,'version':sys.version,
                                   'no_automatic_retry':True})
    expected = json.loads((REPO/'docs/agent_first/run_014/FINAL_AUDIT.json').read_text())
    for r in expected['changed_source_files']:
        require(sha(REPO/r['path'])==r['sha256'],'MATERIAL_CHANGED','Run014 reviewed source changed')
    manifest=json.loads((REPO/'docs/agent_first/run_013/ACCEPTANCE_MANIFEST.json').read_text())
    require(digest(manifest['body'])==manifest['content_digest'],'MATERIAL_CHANGED','Original manifest differs')
    locks=[]
    for r in manifest['body']['materials']:
        if Path(r['path']).name in ('ownership.py','store.py'):
            require('sha256:'+sha(Path(r['path']))==r['digest'],'MATERIAL_CHANGED','Original ownership mechanism changed')
            locks.append(r)
    require(len(locks)==2,'MATERIAL_CHANGED','Missing original lock/store binding')
    protected=json.loads((REPO/'docs/agent_first/run_014/PROTECTED_BASELINE.json').read_text())
    require(all(Path(r['path']).is_relative_to(REPO) for r in protected),'INVALID_PATH','Historical scope differs')
    require(all(sha(Path(r['path']))==r['sha256'] for r in protected),'MATERIAL_CHANGED','Protected historical evidence changed')
    old_reports={str(p):sha(p) for p in OUT.parent.rglob('*') if p.is_file() and not p.is_relative_to(OUT)}
    save('PROTECTED_BEFORE.json',{'historical_count':len(protected),'run014_files':old_reports,'execution_files':expected['changed_source_files']})
    original_files=files_before();save('EXPERIMENT_FILES_BEFORE.json',original_files)
    ctx, boot=load_bootstrap(str(ROOT),str(ROOT/'private/bootstrap.json'))
    store=ReadOnlyStore(ctx)
    before=read_state(store); save('BEFORE.json',before)
    if before['audit']['already_disposed']:
        decision=next(d for d in before['decisions'] if d['reconciliation_id']==before['run']['disposition_record_id'])
        receipt=next(r for r in before['audit']['management_receipts'] if r['operation_id']==decision['operation_id'])
        prior=store.management_receipt(boot['client_namespace'],RELEASE,receipt['idempotency_key'])
        save('ALREADY_APPLIED.json',{'receipt':prior,'no_new_grant_or_write':True});return
    prior=json.loads((OUT.parent/'CURRENT_READONLY.json').read_text())
    require(before['run']==prior['run'],'STATE_CHANGED','Run differs from reviewed revision20; stop for review')
    require(before['gate']['state']=='PAUSED' and before['slot']==RID,'STATE_CHANGED','Gate or slot changed')
    require(before['audit']['counts']['runs']==1 and before['audit']['counts']['management_grants']==0
            and not before['decisions'],'STATE_CHANGED','Unexpected existing operation; inspect rather than retry')
    management=None
    try:
        # Exact existing owner lock: project/owner.lock, offset4096,length1,
        # Windows LK_NBLCK. No lock deletion, timeout inference or PID assumption.
        management=acquire_supervisor_store(ctx,boot['authority_instance'])
        session=management._session
        save('EXCLUSIVE_MANAGEMENT.json',{'at':at(),'same_original_ownership_sources':locks,
            'owner_id':session.owner_id,'process':session.lease.process,'lock_path':str(session.lease.path),
            'lock_offset':4096,'lock_length':1,'lock_operation':'msvcrt.LK_NBLCK',
            'handle_non_inheritable':not os.get_inheritable(session.lease.stream.fileno()),
            'lock_file_identity':{'device':session.lease.identity.st_dev,'inode':session.lease.identity.st_ino},
            'supervisor_created':False,'dispatch_threads_created':0,'old_owner_process_operations':0})
        locked=read_state(management);save('LOCKED_BEFORE.json',locked)
        require(matching_history(before,locked),'STATE_CHANGED','New evidence/state under lock; stop')
        require(locked['gate']['state']=='PAUSED' and locked['gate']['owner_id']==session.owner_id
                and session.active_dispatches==0,'OWNER_UNCONFIRMED','Management must remain quiescent/paused')
        require(files_before()==original_files,'STATE_CHANGED','Experiment files changed before decision')
        service=ExecutionService(ctx,management,client_namespace=boot['client_namespace'])
        assessment=service.preview_closeout(ctx,RID);save('LOCKED_ASSESSMENT.json',assessment)
        require(not assessment['reasons'] and any(a['action']==RELEASE and a['eligible'] for a in assessment['actions']),
                'CLOSEOUT_PRECONDITION_FAILED','No eligible release under locked current view')
        request=issue(service,assessment,RELEASE,
            reason='User explicitly accepts residual member-set/overall-exit uncertainty for this Run only; release logical slot, retain paths and PAUSED; no physical-exit assertion.',
            approval_source=str(OUT/'AUTHORIZATION_SOURCE.md'),expires_at=now()+300)
        save('EXACT_REQUEST.json',request)  # durable original key before apply
        try:
            result=service.apply_closeout(ctx,request)
            save('APPLY_RESPONSE.json',result)
        except ExecutionError as exc:
            save('APPLY_ERROR.json',{'code':exc.code,'query_same_key_only':True})
            # No re-apply, alternate key or grant. Query even on uncertain response.
        receipt=management.management_receipt(boot['client_namespace'],RELEASE,request['idempotency_key'])
        save('DURABLE_RECEIPT.json',receipt)
        after=read_state(management);save('AFTER_COMMIT.json',after)
        changes={k for k in set(before['run'])|set(after['run']) if before['run'].get(k)!=after['run'].get(k)}
        decision=next(d for d in after['decisions'] if d['reconciliation_id']==after['run']['disposition_record_id'])
        checks={
            'logical_slot_released':after['slot'] is None,
            'dispatch_still_paused':after['gate']['state']=='PAUSED',
            'revision_incremented_once':after['run']['revision']==before['run']['revision']+1,
            'only_disposition_projection_changed':changes=={'revision','disposition_record_id','disposition_action','administrative_closeout'},
            'original_receipt_plan_observations_validations_unchanged':all(after[k]==before[k] for k in ('receipts','plan','observations','validations','consumed')),
            'original_events_unchanged':after['events'][:-1]==before['events'] and after['events'][-1]['type']=='STANDARD_DISPOSITION_RECORDED',
            'original_execution_grant_consumption_unchanged':all(after['audit'][k]==before['audit'][k] for k in ('execution_grants_digest','execution_consumption')),
            'exact_one_management_change':all(after['audit']['counts'][t]==before['audit']['counts'][t]+1 for t in ('events','reconciliations','management_grants','management_receipts','management_consumption','control_events')),
            'retention_persisted':decision['retention']=={'engineering':before['plan']['engineering'],'scratch':before['plan']['scratch'],'output_key':before['plan']['output_key'],'state':'RETAINED_NO_REUSE'},
            'committed_release_linkage_valid':after['audit']['already_disposed'],
            'original_experiment_files_unchanged':files_before()==original_files,
            'reviewed_code_unchanged':all(sha(REPO/r['path'])==r['sha256'] for r in expected['changed_source_files']),
            'historical_reports_unchanged':all(sha(Path(p))==h for p,h in old_reports.items()) and all(sha(Path(r['path']))==r['sha256'] for r in protected),
        }
        save('VERIFICATION.json',{'at':at(),'checks':checks,'run_changes':sorted(changes),'before_revision':before['run']['revision'],
            'after_revision':after['run']['revision'],'before_gate':before['gate'],'management_gate':locked['gate'],'after_gate':after['gate'],
            'decision':decision,'receipt':receipt,'abaqus_calls':0,'old_owner_started_stopped_adopted':False})
        require(all(checks.values()),'POSTCONDITION_FAILED','Commit exists; see durable receipt/verification, do not reapply')
    finally:
        if management is not None:
            management.close()  # closes only this process's management byte-lock handle
            save('MANAGEMENT_LEASE_CLOSED.json',{'at':at(),'owner_id':management._session.owner_id,
                                               'closed':management._session.lease.closed,'old_owner_untouched':True})
    final=read_state(ReadOnlyStore(ctx));save('AFTER_LEASE_CLOSE.json',final)
    require(final==after,'STATE_CHANGED_AFTER_COMMIT','Later state changed; no repeat action')
    save('RESULT.json',{'status':'APPLIED_VERIFIED','run_id':RID,'operation_id':receipt['operation_id'],
                        'revision':final['run']['revision'],'slot':final['slot'],'gate':final['gate'],
                        'abaqus_calls':0,'old_owner_operations':0})
    print(json.dumps({'status':'APPLIED_VERIFIED','operation_id':receipt['operation_id'],'revision':final['run']['revision'],'slot':final['slot'],'gate':final['gate']}))

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        info={'at':at(),'status':'STOPPED_NO_AUTOMATIC_RETRY','code':getattr(exc,'code',type(exc).__name__)}
        if not (OUT/'STOPPED.json').exists():save('STOPPED.json',info)
        print(json.dumps(info));raise SystemExit(2)
