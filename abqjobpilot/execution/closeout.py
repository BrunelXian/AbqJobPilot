"""Recorded Standard closeout assessment and explicit administrative policy.

No process probes, artifact IO, launch or recovery. Administrative disposition
never changes historical execution/exit/Solver/validation evidence.
"""
import json
from pathlib import Path
import sqlite3
import time

from .models import canonical_json, digest, fields, identifier, integer, now, require, text, ExecutionError
from .store import gate_view, needs_reconciliation, update_run, _connection

POLICY = 'standard-closeout-v1'
BACKEND = 'abaqus-standard-axial-2024-v1'
RETAIN = 'retain_standard_resources'
RELEASE = 'release_standard_logical_slot'
ACTIONS = (RETAIN, RELEASE)
SCOPE = ('run_id', 'expected_run_revision', 'preview_digest', 'evidence_fingerprint', 'reason')
GRANT_KIND = 'EXPLICIT_STANDARD_DISPOSITION'


def _rows(c, table, run_id, limit=128):
    rows = c.execute(f'SELECT length(CAST(body AS BLOB)), CASE WHEN length(CAST(body AS BLOB))<=262144 THEN body END '
                     f'FROM {table} WHERE run_id=? ORDER BY rowid LIMIT ?', (run_id, limit+1)).fetchall()
    require(len(rows) <= limit and all(r[1] is not None for r in rows)
            and sum(r[0] for r in rows) <= 1048576, 'LIMIT_EXCEEDED', 'Closeout snapshot exceeds bound')
    return [json.loads(r[1]) for r in rows]


def snapshot(c, run_id):
    def one(table,key,value):
        row=c.execute(f'SELECT CASE WHEN length(CAST(body AS BLOB))<=262144 THEN body END FROM {table} WHERE {key}=?',(value,)).fetchone()
        require(row is not None,'NOT_FOUND','Historical record missing')
        require(row[0] is not None,'LIMIT_EXCEEDED','Closeout record exceeds bound')
        return json.loads(row[0])
    run = one('runs', 'run_id', run_id)
    plan = one('plans', 'plan_id', run['plan_id'])
    require(len(canonical_json(run))+len(canonical_json(plan)) <= 262144, 'LIMIT_EXCEEDED', 'Closeout record too large')
    consumed=c.execute('SELECT run_id FROM consumption WHERE grant_id=?',(run['grant_id'],)).fetchone()
    require(consumed is not None,'EVIDENCE_INSUFFICIENT','Original execution consumption is missing')
    return {'run':run, 'plan':plan, 'gate':gate_view(c),
            'slot':c.execute('SELECT run_id FROM slot WHERE id=1').fetchone()[0],
            'receipts':_rows(c,'receipts',run_id,1), 'events':_rows(c,'events',run_id),
            'observations':_rows(c,'observations',run_id,16), 'validations':_rows(c,'validations',run_id,16),
            'decisions':_rows(c,'reconciliations',run_id,16),
            'consumed':consumed[0]}


def _path_ref(context, value):
    path, root = Path(value), Path(context.test_root)
    require(path.is_absolute() and path.is_relative_to(root) and '..' not in path.parts,
            'EVIDENCE_INSUFFICIENT', 'Historical resource scope is invalid')
    return path.relative_to(root).as_posix()


def assess(context, data, *, owner_id=None, active_dispatches=None):
    r,p,g = data['run'],data['plan'],data['gate']
    require(r['project_instance_id']==context.project_instance_id and r['project_id']==context.project_id
            and p['context_digest']==context.context_digest and p['project_instance_id']==context.project_instance_id,
            'PROJECT_IDENTITY_MISMATCH','Historical context differs')
    require(r['backend_id']==p['backend_id']==BACKEND and p['backend_version']==1,
            'UNSUPPORTED_EVIDENCE_POLICY','This closeout policy only covers fixed Standard v1')
    require(p['plan_digest']==r['plan_digest']==digest({k:v for k,v in p.items() if k!='plan_digest'}),
            'EVIDENCE_INSUFFICIENT','Historical Plan differs')
    events=data['events']; kinds=[e['type'] for e in events]
    require(kinds.count('REQUEST_ACCEPTED')==kinds.count('START_INTENT')==1 and data['consumed']==r['run_id']
            and len(data['receipts'])==1 and data['receipts'][0]['run_id']==r['run_id'],
            'EVIDENCE_INSUFFICIENT','Accepted single attempt and consumption required')
    intent=r.get('launch_intent',{})
    require(intent.get('run_id')==r['run_id'] and intent.get('plan_digest')==r['plan_digest']
            and intent.get('phase_attempt_id')==r['phase_attempt_id'] and intent.get('output_key')==p['output_key'],
            'EVIDENCE_INSUFFICIENT','Persisted output intent binding missing')
    members=r.get('process_records',[]); exits=r.get('process_exits',[])
    def key(v):return (v.get('role'),v.get('pid'),v.get('creation_time_100ns'),v.get('image_path'))
    valid_exits=(bool(members) and len(members)==len(exits) and len({key(m) for m in members})==len(members)
        and sum(m.get('role')=='wrapper' for m in members)==1
        and r.get('all_observed_exited') is True and r.get('launch_state')=='PROCESS_OBJECT_RETURNED')
    valid_exits=valid_exits and {key(m) for m in members}=={key(e) for e in exits}
    valid_exits=valid_exits and all(type(m.get('pid')) is int and m['pid']>0
        and type(m.get('creation_time_100ns')) is int and m['creation_time_100ns']>0
        and isinstance(m.get('image_path'),str) and bool(m['image_path'])
        and m.get('identity_status')=='VERIFIED' for m in members)
    valid_exits=valid_exits and all(type(e.get('exit_code')) is int and type(e.get('exit_observed_at')) is int
        and e.get('identity_status')=='VERIFIED'
        and e.get('exit_source') in ('direct_Popen_handle','retained_windows_handle') for e in exits)
    observations=[e['payload'] for e in events if e['type']=='STANDARD_PROCESS_OBSERVATION']
    valid_exits=valid_exits and bool(observations) and observations[-1].get('process_records')==members and observations[-1].get('process_exits')==exits
    ended=r.get('observation_deadline_reached') is True and kinds.count('STANDARD_OBSERVATION_ENDED')==1
    applicable=(needs_reconciliation(r) and r.get('execution')=='BLOCKED' and data['slot']==r['run_id']
                and g['state']=='PAUSED' and not r.get('administrative_closeout'))
    live=owner_id==g['owner_id'] and active_dispatches==0
    conditions=[]
    if not applicable:conditions.append('RUN_OR_SLOT_NOT_PENDING_CLOSEOUT')
    if not ended:conditions.append('OBSERVATION_END_NOT_RECORDED')
    if not valid_exits:conditions.append('OBSERVED_MEMBER_EXIT_EVIDENCE_INCOMPLETE')
    if not live:conditions.append('CURRENT_QUIESCENT_OWNER_REQUIRED')
    base={'policy':POLICY,'assessment_version':1,'project_id':context.project_id,
        'project_instance_id':context.project_instance_id,'context_digest':context.context_digest,
        'run_id':r['run_id'],'run_revision':r['revision'],'plan_id':r['plan_id'],'plan_digest':r['plan_digest'],
        'phase_attempt_id':r['phase_attempt_id'],'owner_id':owner_id,'recorded_gate':g,
        'evidence_fingerprint':digest(data),
        'scope':'recorded database snapshot only; no OS or artifact revalidation',
        'historical_facts':{k:r.get(k) for k in ('execution','execution_phase','launch_state','process_observation',
            'all_observed_exited','member_completeness','overall_exit','exit_verification','solver_conclusion',
            'numerical_validation','artifact_validation','odb_content_validation','administrative_closeout')},
        'observation_ended_recorded':ended,'observed_exits_matched':valid_exits,
        'unknowns':['COMPLETE_SOLVER_MEMBERSHIP','OVERALL_PROCESS_EXIT','PHYSICAL_RESOURCES_RETURNED','CURRENT_OS_STATE'],
        'source_refs':[e['event_id'] for e in events]+[v['validation_id'] for v in data['validations']]
                       +[o['observation_id'] for o in data['observations']]+[d['reconciliation_id'] for d in data['decisions']],
        'resources':{'slot_run_id':data['slot'],'engineering_ref':_path_ref(context,p['engineering']),
            'scratch_ref':_path_ref(context,p['scratch']),'output_key':p['output_key'],'job_name':p['job_name'],
            'retention':'RETAINED_NO_REUSE','intent':'historical persisted intent; file not reread'},
        'automatic_evidence_closeout':{'eligible':False,'reason':
            ('MANAGED_COMPLETION_ALREADY_RECORDED' if r.get('managed_completion')=='COMMITTED_EMPTY_SCOPE'
             else 'MANAGED_SCOPE_COMPLETION_NOT_COMMITTED') if p.get('process_management')
            else 'NO_COMPLETE_MANAGED_PROCESS_SCOPE_CONTRACT'},
        'actions':[
            {'action':RETAIN,'eligible':applicable and live,'changes':['append disposition and revision'],
             'preserves':['slot','engineering/output quarantine','UNKNOWN','PAUSED','all execution evidence']},
            {'action':RELEASE,'eligible':applicable and live and ended and valid_exits,
             'changes':['append administrative disposition','release logical slot only','increment gate version, remain PAUSED'],
             'requires':['exact independent operator grant','explicit residual uncertainty acceptance'],
             'preserves':['engineering/output quarantine','UNKNOWN','all execution evidence','no retry','PAUSED']}],
        'reasons':conditions,
        'resume_dispatch':'separate permission; never implied by a closeout receipt',
        'stop_owner':'separate operator action; requires quiescent worker and durable store; never Solver exit evidence'}
    require(len(canonical_json(base).encode('utf-8'))<=65536,'LIMIT_EXCEEDED','Closeout report exceeds bound')
    return {**base,'preview_digest':digest(base)}


def preview_store(store, context, run_id, *, owner_id=None, active_dispatches=None):
    """Same assessor for public live owner and explicitly labelled offline audit."""
    require(store.context==context,'PROJECT_IDENTITY_MISMATCH','Explicit matching store required');text(run_id)
    c=None;deadline=time.monotonic()+.75
    try:
        c=_connection(context,read_only=True,timeout=.2,deadline=deadline)
        c.execute('BEGIN'); data=snapshot(c,run_id)
        require(time.monotonic()<deadline,'STORE_UNAVAILABLE','Closeout read budget exceeded')
    except (sqlite3.Error,OSError,ValueError,KeyError,TypeError) as exc:
        raise ExecutionError('STORE_UNAVAILABLE','Closeout read refused; no records changed',stage='QUERY') from None
    finally:
        if c is not None:c.close()
    return {**assess(context,data,owner_id=owner_id,active_dispatches=active_dispatches),'read_at':now()}


def preview(service, context, run_id):
    from .reconciliation import _owner
    service._context(context);_owner(service)
    lock=service.store._session.lock
    require(lock.acquire(timeout=.2),'STORE_UNAVAILABLE','Owner is busy; closeout read refused')
    try:
        return preview_store(service.store,context,run_id,owner_id=service.store._session.owner_id,
                             active_dispatches=service.store._session.active_dispatches)
    finally:lock.release()


def check_permission(context, grant, authority, owner, action, scope, consumed):
    require(grant is not None,'MANAGEMENT_GRANT_REQUIRED','Explicit operator disposition grant required')
    fields(grant,('grant_id','issuer','authority_instance','grant_kind','project_instance_id','context_digest',
                  'owner_id','action','scope','expires_at','max_uses','approval_source'))
    expected={'issuer':'TrustedStandardOperator','authority_instance':authority,'grant_kind':GRANT_KIND,
        'project_instance_id':context.project_instance_id,'context_digest':context.context_digest,
        'owner_id':owner,'action':action,'scope':scope,'max_uses':1}
    require(canonical_json({k:grant[k] for k in expected})==canonical_json(expected),
            'MANAGEMENT_SCOPE_MISMATCH','TEST_ONLY, execution or mismatched grants cannot approve disposition')
    text(grant['approval_source']);integer(grant['expires_at'])
    require(grant['expires_at']>now(),'MANAGEMENT_GRANT_EXPIRED','Disposition grant expired')
    require(not consumed,'MANAGEMENT_GRANT_CONSUMED','Disposition grant already used')


def issue(service, assessment, action, *, reason, approval_source, expires_at):
    """Trusted IN-OWNER entry, no RPC mint. Source records actual human authority.

    Requires the live exclusive owner, same as existing trusted issuance; no
    supported out-of-process database writes. Arbitrary same-user code is trusted.
    """
    from .reconciliation import _owner, MANAGEMENT_CONTRACT
    _owner(service);text(reason);text(approval_source);integer(expires_at)
    require(action in ACTIONS and now()<expires_at<=now()+3600,'INVALID_REQUEST','Bounded exact disposition required')
    session=service.store._session
    with service.store.transaction('grant_closeout') as c:
        current=assess(service.context,snapshot(c,assessment['run_id']),owner_id=session.owner_id,active_dispatches=session.active_dispatches)
        require(current['preview_digest']==assessment['preview_digest'],'STALE_PREVIEW','Review current assessment first')
        require(any(a['action']==action and a['eligible'] for a in current['actions']),
                'CLOSEOUT_PRECONDITION_FAILED','No applicable disposition under this policy')
        scope={'run_id':current['run_id'],'expected_run_revision':current['run_revision'],
               'preview_digest':current['preview_digest'],'evidence_fingerprint':current['evidence_fingerprint'],'reason':reason}
        grant={'grant_id':identifier('mg'),'issuer':'TrustedStandardOperator','grant_kind':GRANT_KIND,
            'authority_instance':session.authority_instance,'project_instance_id':service.context.project_instance_id,
            'context_digest':service.context.context_digest,'owner_id':session.owner_id,'action':action,'scope':scope,
            'expires_at':expires_at,'max_uses':1,'approval_source':approval_source}
        check_permission(service.context,grant,session.authority_instance,session.owner_id,action,scope,False)
        c.execute('INSERT INTO management_grants VALUES(?,?)',(grant['grant_id'],canonical_json(grant)))
    return {'contract_version':MANAGEMENT_CONTRACT,'operation':action,'project_id':service.context.project_id,
        'project_instance_id':service.context.project_instance_id,'owner_id':session.owner_id,
        'management_grant_id':grant['grant_id'],'idempotency_key':identifier('closeout-request'),**scope}


def apply_recorded(service,c,request,operation_id,gate):
    session=service.store._session
    data=snapshot(c,request['run_id']);current=assess(service.context,data,owner_id=session.owner_id,active_dispatches=session.active_dispatches)
    require(current['preview_digest']==request['preview_digest'] and current['run_revision']==request['expected_run_revision']
            and current['evidence_fingerprint']==request['evidence_fingerprint'],'STALE_PREVIEW','Evidence or control preconditions changed')
    action=request['operation']
    require(any(a['action']==action and a['eligible'] for a in current['actions']),
            'CLOSEOUT_PRECONDITION_FAILED','No applicable administrative disposition')
    grant=json.loads(c.execute('SELECT body FROM management_grants WHERE grant_id=?',(request['management_grant_id'],)).fetchone()[0])
    record={'reconciliation_id':identifier('disposition'),'operation_id':operation_id,'run_id':request['run_id'],
        'owner_id':session.owner_id,'recorded_at':now(),'action':action,'policy':POLICY,
        'source':'EXPLICIT_OPERATOR_POLICY_NOT_EXIT_EVIDENCE','approval_source':grant['approval_source'],
        'reason':request['reason'],'assessment':current,'evidence_refs':current['source_refs'],
        'retention':{'engineering':data['plan']['engineering'],'scratch':data['plan']['scratch'],
            'output_key':data['plan']['output_key'],'state':'RETAINED_NO_REUSE'},
        'effect':'LOGICAL_SLOT_RELEASED_ONLY' if action==RELEASE else 'ALL_RESOURCES_RETAINED'}
    c.execute('INSERT INTO reconciliations VALUES(?,?,?)',(record['reconciliation_id'],request['run_id'],canonical_json(record)))
    changes={'disposition_record_id':record['reconciliation_id'],'disposition_action':action}
    if action==RELEASE:
        require(c.execute('UPDATE slot SET run_id=NULL WHERE id=1 AND run_id=?',(request['run_id'],)).rowcount==1,
                'STATE_CONFLICT','Slot no longer belongs to this Run')
        changes['administrative_closeout']='LOGICAL_SLOT_RELEASED_WITH_RESIDUAL_UNCERTAINTY'
    updated=update_run(c,data['run'],'STANDARD_DISPOSITION_RECORDED',evidence_refs=[record['reconciliation_id']],**changes)
    c.execute("UPDATE dispatch_gate SET state='PAUSED',version=version+1 WHERE id=1")
    event={'event_id':identifier('control'),'operation_id':operation_id,'type':'STANDARD_DISPOSITION_RECORDED',
        'recorded_at':now(),'owner_id':session.owner_id,'run_id':request['run_id'],'action':action,'gate':gate_view(c)}
    c.execute('INSERT INTO control_events(body) VALUES(?)',(canonical_json(event),))
    return [record['reconciliation_id'],event['event_id']],{'run_id':request['run_id'],'run_revision':updated['revision'],
        'effect':record['effect'],'gate':gate_view(c),'evidence_conclusions_unchanged':True}


def administratively_released(c, run):
    """Never trust a projection flag alone; require the committed linked decision."""
    if run.get('administrative_closeout')!='LOGICAL_SLOT_RELEASED_WITH_RESIDUAL_UNCERTAINTY':return False
    row=c.execute('SELECT body FROM reconciliations WHERE reconciliation_id=? AND run_id=?',
                  (run.get('disposition_record_id'),run['run_id'])).fetchone()
    if not row:return False
    record=json.loads(row[0])
    committed=c.execute('SELECT 1 FROM management_receipts m JOIN management_consumption g ON g.operation_id=m.operation_id '
                        'WHERE m.operation_id=?',(record.get('operation_id'),)).fetchone()
    return bool(committed and record.get('policy')==POLICY and record.get('action')==RELEASE
                and record.get('retention',{}).get('state')=='RETAINED_NO_REUSE')


def blocks_dispatch(c, run):
    return needs_reconciliation(run) and not administratively_released(c,run)


def issue_resume(service, *, expected_gate_version, approval_source, expires_at):
    """Separate exact real-policy resumption grant, never implied by slot release."""
    from .reconciliation import _owner, RESUME, MANAGEMENT_CONTRACT
    _owner(service);text(approval_source);integer(expected_gate_version,1);integer(expires_at)
    require(now()<expires_at<=now()+3600,'INVALID_REQUEST','Bounded resumption permission required')
    session=service.store._session;ctx=service.context;scope={'expected_gate_version':expected_gate_version}
    with service.store.transaction('grant_closeout_resume') as c:
        gate=gate_view(c);runs=[json.loads(r[0]) for r in c.execute('SELECT body FROM runs')]
        require(gate['state']=='PAUSED' and gate['version']==expected_gate_version and gate['owner_id']==session.owner_id
                and session.active_dispatches==0,'GATE_PRECONDITION_FAILED','Current paused quiescent owner required')
        require(any(administratively_released(c,r) for r in runs) and not any(blocks_dispatch(c,r) for r in runs)
                and c.execute('SELECT run_id FROM slot WHERE id=1').fetchone()[0] is None,
                'RECONCILIATION_REQUIRED','Other uncertainty or occupied slot blocks resumption')
        grant={'grant_id':identifier('mg'),'issuer':'TrustedStandardOperator','grant_kind':GRANT_KIND,
            'authority_instance':session.authority_instance,'project_instance_id':ctx.project_instance_id,
            'context_digest':ctx.context_digest,'owner_id':session.owner_id,'action':RESUME,'scope':scope,
            'expires_at':expires_at,'max_uses':1,'approval_source':approval_source}
        c.execute('INSERT INTO management_grants VALUES(?,?)',(grant['grant_id'],canonical_json(grant)))
    return {'contract_version':MANAGEMENT_CONTRACT,'operation':RESUME,'project_id':ctx.project_id,
        'project_instance_id':ctx.project_instance_id,'owner_id':session.owner_id,
        'management_grant_id':grant['grant_id'],'idempotency_key':identifier('resume-request'),**scope}


def check_retained_paths(service, plan):
    """Within this store, old Standard engineering/scratch remain quarantined.

    Existing intent also protects the exact directory across compliant owners.
    This is not a host-wide or arbitrary cross-Project filesystem reservation.
    """
    candidate=[Path(plan['engineering']),Path(plan['scratch'])]
    with service.store.read() as c:
        rows=c.execute('SELECT p.body FROM runs r JOIN plans p ON p.plan_id=r.plan_id WHERE r.plan_id<>? LIMIT 1025',
                       (plan['plan_id'],)).fetchall()
    require(len(rows)<=1024,'LIMIT_EXCEEDED','Retained path index exceeds bound')
    for row in rows:
        old=json.loads(row[0])
        if old['backend_id']!=BACKEND:continue
        held=[Path(old['engineering']),Path(old['scratch'])]
        require(not any(a.is_relative_to(b) or b.is_relative_to(a) for a in candidate for b in held),
                'RESOURCE_RETAINED','Old Standard engineering/output scope remains quarantined')

