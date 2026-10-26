"""Explicit local recovery management, sharing the owner lock and management transaction.

Trusted issuance is IN-PROCESS, like closeout.issue, never an IPC capability.
Neither an IPC credential nor a lifecycle/execution token can invoke this API
through the Supervisor. Arbitrary same-user Python/filesystem access remains
the existing trust boundary. No listener, dispatcher, real Backend or process control.
"""
import json
from types import SimpleNamespace

from .closeout import snapshot as closeout_snapshot
from . import closeout
from .models import ExecutionError, canonical_json, digest, fields, identifier, now, require, text, integer
from .store import ReadOnlyStore, document, gate_view, needs_reconciliation, update_run
from .interruption import build_interruption_report

VERSION = 'interrupted-recovery-v1'
ACTION = 'apply_interrupted_recovery'
KEEP = 'KEEP_BLOCKED'
VERIFIED = 'VERIFIED_RECONCILIATION'
ADMIN = 'AUTHORISED_ADMINISTRATIVE_DISPOSITION'
SCOPE = ('run_id', 'expected_run_revision', 'preview_digest', 'evidence_fingerprint',
         'decision', 'subject', 'reason', 'residual_risk_accepted', 'operation_key')


def _data(raw):
    decode = lambda name: [json.loads(row[0]) for row in raw[name]]
    return {'run': decode('run')[0], 'plan': decode('plan')[0], 'gate': raw['gate'],
            'slot': raw['interruption']['slot_run_id'], 'receipts': decode('receipts'),
            'events': decode('events'), 'observations': decode('observations'),
            'validations': decode('validations'), 'decisions': decode('reconciliations'),
            'consumed': raw['interruption']['consumption'][0][1] if raw['interruption']['consumption'] else None}


def _managed(data):
    """Recorded original-handle proof only. Never recreate/reopen a lost Job.

    Reconciliation does NOT mint an automatic-completion flag or infer a Solver
    outcome. Existing automatic dispatch/stop policies remain conservative.
    """
    from .managed_process import check_completion, POLICY
    run, plan, events = data['run'], data['plan'], data['events']
    require(plan.get('process_management', {}).get('policy') == POLICY or
            plan.get('process_fixture', {}).get('managed_scope', {}).get('policy') == POLICY,
            'UNSUPPORTED_EVIDENCE_POLICY', 'Original Plan must require managed creation')
    proof = run.get('managed_scope')
    check_completion(proof, run)
    require(proof.get('binding') == 'CREATE_PROCESS_JOB_LIST' and proof.get('named') is False
            and proof.get('scope') == 'ROOT_AND_INHERITING_CREATEPROCESS_DESCENDANTS'
            and type(proof.get('query_monotonic_ns')) is int and proof['query_monotonic_ns'] > 0,
            'MANAGED_SCOPE_UNKNOWN', 'Original bounded scope query required')
    require(all(type(proof.get(k)) is int for k in ('active_processes','total_processes','limit_terminated_processes','observed_at')),
            'MANAGED_SCOPE_UNKNOWN','Exact integer accounting evidence required')
    prepared = [e for e in events if e['type'] == 'MANAGED_SCOPE_PREPARED']
    observed = [e for e in events if e['type'] == 'MANAGED_SCOPE_OBSERVED']
    require(len(prepared) == 1 and observed and observed[-1]['payload'].get('managed_scope') == proof
            and prepared[0]['run_sequence'] < observed[-1]['run_sequence'],
            'MANAGED_SCOPE_UNKNOWN', 'Prepared and last persisted query must match')
    creation_kind = 'STANDARD_CREATED' if run['backend_id']==closeout.BACKEND else 'MANAGED_ROOT_CREATED'
    created = [e for e in events if e['type']==creation_kind]
    require(len(created)==1 and prepared[0]['run_sequence']<created[0]['run_sequence']<observed[-1]['run_sequence'],
            'MANAGED_SCOPE_UNKNOWN','One recorded root-creation result must precede empty-scope observation')
    if run['backend_id']==closeout.BACKEND:
        require(created[0]['payload'].get('launch_state')=='PROCESS_OBJECT_RETURNED'
                and run.get('launch_state')=='PROCESS_OBJECT_RETURNED',
                'MANAGED_SCOPE_UNKNOWN','Root creation outcome is not confirmed')
    else:
        root = created[0]['payload'].get('managed_scope',{})
        require(root.get('creation_confirmed') is True and root.get('scope_id')==proof['scope_id'],
                'MANAGED_SCOPE_UNKNOWN','Original managed root creation is not bound')
    base = prepared[0]['payload'].get('managed_scope', {})
    for key in ('scope_id','policy','binding','scope','named','kill_on_job_close','breakaway_allowed',
                'project_instance_id','run_id','plan_digest','phase_attempt_id','owner_id','owner_epoch'):
        require(base.get(key) == proof.get(key), 'MANAGED_SCOPE_UNKNOWN', 'Scope identity changed')
        require(all(e['payload'].get('managed_scope',{}).get(key)==proof.get(key) for e in observed),
                'MANAGED_SCOPE_UNKNOWN','Conflicting scope query history')
    require(isinstance(proof.get('scope_id'), str) and proof['scope_id'].startswith('scope_'),
            'MANAGED_SCOPE_UNKNOWN', 'Missing original scope identity')
    # A later failure about containment, query, creation, or persistence cannot
    # be ignored merely because an earlier query happened to see zero.
    allowed = {'STANDARD_PROCESS_OBSERVATION','STANDARD_OBSERVATION_ENDED','PROCESS_COMPLETED'}
    require(all(e['type'] in allowed for e in events if e['run_sequence'] > observed[-1]['run_sequence']),
            'MANAGED_SCOPE_UNKNOWN', 'Later evidence prevents recorded-scope reconciliation')
    require(run.get('launch_state') not in {'CALL_ENTERED_OUTCOME_UNKNOWN','NOT_CALLED'}
            or run['backend_id'] == 'python-process-fixture-v1',
            'MANAGED_SCOPE_UNKNOWN', 'Unresolved root creation')
    require(not run.get('administrative_closeout') and data['slot'] == run['run_id']
            and needs_reconciliation(run), 'NOT_RECONCILABLE', 'No pending scope to reconcile')
    return {'policy': 'recorded-managed-scope-v1', 'scope_id': proof['scope_id'],
            'proof_digest': digest(proof), 'source_refs': [prepared[0]['event_id'], observed[-1]['event_id']]}


def _policy(context, data):
    run = data['run']
    if run.get('managed_scope') or data['plan'].get('process_management') or data['plan'].get('process_fixture',{}).get('managed_scope'):
        try: return VERIFIED, _managed(data), []
        except ExecutionError as exc: managed_reason = exc.code
    else: managed_reason = 'NO_MANAGED_SCOPE'
    if run['backend_id'] == closeout.BACKEND:
        assessment = closeout.assess(context, data, owner_id=data['gate']['owner_id'], active_dispatches=0)
        if any(a['action'] == closeout.RELEASE and a['eligible'] for a in assessment['actions']):
            return ADMIN, assessment, []
        return KEEP, assessment, list(dict.fromkeys([managed_reason, *assessment['reasons']]))
    if run['backend_id']=='python-process-fixture-v1' and managed_reason=='NO_MANAGED_SCOPE':
        from .process_reconciliation import inspect
        facade=SimpleNamespace(context=context,store=SimpleNamespace(_session=SimpleNamespace(
            owner_id=data['gate']['owner_id'],active_dispatches=0)))
        with ReadOnlyStore(context).read() as c:
            c.execute('BEGIN');assessment=inspect(facade,c,run['run_id'])
        if assessment['candidate_action']:
            require(assessment['run_revision']==run['revision'],'STALE_PREVIEW','Read version changed')
            return VERIFIED,assessment,[]
        return KEEP,assessment,[v['code'] for v in assessment['reasons']]
    return KEEP, None, [managed_reason, 'NO_SUPPORTED_RELEASE_POLICY']


def _activity(context, run):
    from .interruption_probe import observe
    observed = observe(context, run)
    admissible = {'EXACT_IDENTITY_EXITED','PROCESS_UNAVAILABLE','IDENTITY_MISMATCH'}
    require(observed['owner']['state'] in admissible and all(m['state'] in admissible for m in observed['members'])
            and len(observed['members'])==len(run.get('process_records',[])),
            'RECOVERY_ACTIVITY_UNRESOLVED', 'Recorded owner/member is active or cannot be checked')
    return observed


def _invariants(c, run_id):
    result = {}
    for table in ('grants','consumption','receipts','observations','validations','plans','management_grants'):
        if table != 'consumption':
            count, size = c.execute('SELECT COUNT(*),COALESCE(SUM(length(CAST(body AS BLOB))),0) FROM '
                                   '(SELECT body FROM '+table+' LIMIT 2049)').fetchone()
            require(count<=2048 and size<=4194304,'LIMIT_EXCEEDED','Recovery audit exceeds bound')
        rows = c.execute('SELECT * FROM '+table+' ORDER BY rowid LIMIT 2049').fetchall()
        require(len(rows)<=2048, 'LIMIT_EXCEEDED', 'Recovery audit exceeds bound')
        value = [list(r) for r in rows]
        require(len(canonical_json(value))<=4194304, 'LIMIT_EXCEEDED', 'Recovery audit exceeds byte bound')
        result[table] = digest(value)
    count,size=c.execute('SELECT COUNT(*),COALESCE(SUM(length(CAST(body AS BLOB))),0) FROM '
                        '(SELECT body FROM runs WHERE run_id<>? LIMIT 2049)',(run_id,)).fetchone()
    require(count<=2048 and size<=4194304,'LIMIT_EXCEEDED','Recovery audit exceeds other-Run bound')
    others=c.execute('SELECT body FROM runs WHERE run_id<>? ORDER BY run_id LIMIT 2049',(run_id,)).fetchall()
    require(len(others)<=2048,'LIMIT_EXCEEDED','Recovery audit exceeds Run bound')
    result['other_runs']=digest([r[0] for r in others])
    return result


def preview_interrupted_recovery(project_context, run_id):
    """No lease, OS queries, files, permission issuance or business writes."""
    raw = ReadOnlyStore(project_context)._diagnostic_snapshot(project_context, run_id, interruption=True)
    diagnostic = build_interruption_report(project_context, raw)
    data = _data(raw)
    decision, policy, reasons = KEEP, None, []
    if diagnostic['body']['diagnosis']['classification'] == 'EVIDENCE_CONFLICT':
        reasons = ['EVIDENCE_CONFLICT']
    elif data['gate']['state'] != 'PAUSED': reasons = ['EXPLICIT_PAUSED_MANAGEMENT_REQUIRED']
    elif not needs_reconciliation(data['run']) or data['run'].get('administrative_closeout'):
        reasons = ['NO_PENDING_RECOVERY']
    else:
        try: decision, policy, reasons = _policy(project_context, data)
        except (ExecutionError, KeyError, TypeError) as exc:
            reasons = [exc.code if isinstance(exc, ExecutionError) else 'EVIDENCE_INSUFFICIENT']
    if policy and policy.get('policy')=='recorded-process-reconciliation-v1':
        confirm=ReadOnlyStore(project_context)._diagnostic_snapshot(project_context,run_id,interruption=True)
        require(build_interruption_report(project_context,confirm)['body']['view']['snapshot_digest']==
                diagnostic['body']['view']['snapshot_digest'],'STALE_PREVIEW','Evidence changed across recorded-exit assessment')
    body = {'version': VERSION, 'project_id': project_context.project_id,
        'project_instance_id': project_context.project_instance_id, 'context_digest': project_context.context_digest,
        'run_id': run_id, 'phase_attempt_id': data['run']['phase_attempt_id'],
        'run_revision': data['run']['revision'], 'owner_id': data['gate']['owner_id'],
        'snapshot_digest': diagnostic['body']['view']['snapshot_digest'],
        'decision': decision, 'policy': policy, 'reasons': reasons,
        'effects': ([] if decision == KEEP else ['append audited decision', 'release logical slot', 'keep PAUSED']),
        'preserves': ['original execution evidence','Solver','validation','old outputs','execution grants and consumption','other Runs'],
        'requires': ['trusted local issuance','original exclusive owner.lock','fresh lock-held preview',
                     'bounded exact authorization','current recorded identities not active or query-unknown'],
        'forbidden': ['resume_dispatch','retry','requeue','new_attempt','solver_resume','stop_owner','delete_output'],
        'apply_allowed': False, 'diagnostic_digest': diagnostic['body']['decision_digest']}
    return {'body': body, 'preview_digest': digest(body), 'read_at': raw['read_at'], 'diagnostic': diagnostic}


def _stable(context, run_id):
    p = preview_interrupted_recovery(context, run_id)
    return p, p['body']


class RecoveryManagementSession:
    """TRUSTED LOCAL operator entry; not a client or authentication protocol.

    Opening explicitly obtains management ownership and persists PAUSED, but
    does not approve a disposition. Call preview again inside this session.
    No method is exported over IPC; tokens/approved JSON are not accepted.
    """
    def __init__(self, context, authority_instance, run_id):
        from .store import acquire_supervisor_store
        from .service import ExecutionService
        self.context, self.run_id = context, run_id
        self.store = None
        def admit(ctx, connection):
            data = closeout_snapshot(connection, run_id)
            require(data['run']['execution'] != 'PLANNED', 'RECOVERY_NOT_APPLICABLE', 'No recovery of an unstarted request')
            require(data['consumed'] == run_id, 'EVIDENCE_INSUFFICIENT', 'Original attempt binding required')
            _activity(ctx, data['run'])
        # Same OS byte lock as every Supervisor. Callback runs while it is held,
        # before owner/gate mutation. Rejected opens do not acquire business state.
        self.store = acquire_supervisor_store(context, authority_instance, management_admit=admit)
        try:
            self.service = ExecutionService(context, self.store, client_namespace='trusted-recovery-v1')
            require(self.store.gate()['state'] == 'PAUSED', 'GATE_PRECONDITION_FAILED', 'Recovery must be paused')
        except BaseException:
            self.close(); raise

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def close(self):
        if self.store is not None: self.store.close(); self.store = None
    def preview(self): return preview_interrupted_recovery(self.context, self.run_id)

    def authorize(self, preview, *, subject, source, reason, expires_at, operation_key, residual_risk_accepted=False):
        """Trusted local issuance into existing management_grants; never a remote mint."""
        require(type(preview) is dict and type(preview.get('preview_digest')) is str,
                'INVALID_REQUEST','Structured recovery preview required')
        for value in (subject,source,reason,operation_key):
            text(value); require(len(value)<=256, 'LIMIT_EXCEEDED', 'Bounded authorization reference required')
        integer(expires_at)
        require(type(residual_risk_accepted) is bool and now()<expires_at<=now()+600,
                'INVALID_REQUEST', 'Bounded explicit authorization required')
        session = self.store._session
        with self.store.transaction('grant_recovery') as c:
            current, body = _stable(self.context, self.run_id)
            require(preview['preview_digest'] == current['preview_digest'], 'STALE_PREVIEW', 'Review lock-held current preview')
            require(body['owner_id']==session.owner_id and session.active_dispatches==0,
                    'OWNER_NOT_QUIESCENT','Current management ownership required')
            require(body['decision'] in (VERIFIED, ADMIN), 'RECOVERY_KEEP_BLOCKED', 'No supported candidate')
            require(body['decision'] != ADMIN or residual_risk_accepted, 'RESIDUAL_RISK_REQUIRED', 'Administrative residual risk must be explicitly accepted')
            _activity(self.context, document(c,'runs','run_id',self.run_id))
            scope = {'run_id':self.run_id, 'expected_run_revision':body['run_revision'],
                'preview_digest':current['preview_digest'], 'evidence_fingerprint':body['snapshot_digest'],
                'decision':body['decision'], 'subject':subject, 'reason':reason,
                'residual_risk_accepted':residual_risk_accepted, 'operation_key':operation_key}
            grant = {'grant_id':identifier('mg'), 'issuer':'TrustedStandardOperator',
                'grant_kind':closeout.GRANT_KIND, 'authority_instance':session.authority_instance,
                'project_instance_id':self.context.project_instance_id, 'context_digest':self.context.context_digest,
                'owner_id':session.owner_id, 'action':ACTION, 'scope':scope, 'expires_at':expires_at,
                'max_uses':1, 'approval_source':source}
            closeout.check_permission(self.context,grant,session.authority_instance,session.owner_id,ACTION,scope,False)
            c.execute('INSERT INTO management_grants VALUES(?,?)',(grant['grant_id'],canonical_json(grant)))
        return {'contract_version':'af-management-v1','operation':ACTION,'project_id':self.context.project_id,
            'project_instance_id':self.context.project_instance_id,'owner_id':session.owner_id,
            'management_grant_id':grant['grant_id'],'idempotency_key':operation_key,**scope}

    def apply(self, request):
        from .reconciliation import manage
        require(type(request) is dict,'INVALID_REQUEST','Structured recovery request required')
        require(request.get('run_id') == self.run_id, 'PROJECT_IDENTITY_MISMATCH', 'Session binds one Run')
        result = manage(self.service,self.context,request,ACTION)
        try: verification = verify_interrupted_recovery(self.context,request)
        except ExecutionError as exc:
            # A committed receipt must not disappear when a later audit read
            # fails or later legitimate state differs. Never re-apply to fix it.
            verification = {'recovery_status':'RECOVERY_APPLIED','current_verification':'NOT_CONFIRMED',
                            'execution_verified':False,'error':exc.to_dict()['error']}
        return {**result, 'verification': verification}


def apply_recorded(service, c, request, operation_id, gate):
    current, body = _stable(service.context,request['run_id'])
    require(current['preview_digest']==request['preview_digest'] and body['run_revision']==request['expected_run_revision']
            and body['snapshot_digest']==request['evidence_fingerprint'], 'STALE_PREVIEW', 'Evidence or control state changed')
    require(body['decision']==request['decision'] and body['decision'] in (ADMIN,VERIFIED),
            'RECOVERY_KEEP_BLOCKED','No applicable requested decision')
    run = document(c,'runs','run_id',request['run_id'])
    observed = _activity(service.context,run)
    # Re-read after OS observations. The original owner mutex/OS lock and SQL
    # transaction exclude supported writers; OS + DB still are not atomic.
    again,_ = _stable(service.context,request['run_id'])
    require(again['preview_digest']==current['preview_digest'], 'STALE_PREVIEW', 'State changed during observation')
    mutable = ['revision']
    if request['decision']==ADMIN:
        mutable += ['disposition_record_id','disposition_action','administrative_closeout']
    else:
        mutable += ['execution','reconciliation','reconciled_at','recovery_scope_completion']
        if body['policy'].get('candidate_action'):
            mutable += ['backend_outcome','backend_outcome_basis','process_observation','exit_verification','error']
    historical = {k:v for k,v in run.items() if k not in mutable}
    grant = json.loads(c.execute('SELECT body FROM management_grants WHERE grant_id=?',
                                (request['management_grant_id'],)).fetchone()[0])
    closeout.check_permission(service.context,grant,service.store._session.authority_instance,
        service.store._session.owner_id,ACTION,{k:request[k] for k in SCOPE},False)
    invariants = _invariants(c,run['run_id'])
    original_events = [r[0] for r in c.execute('SELECT body FROM events WHERE run_id=? ORDER BY sequence',(run['run_id'],))]
    if request['decision']==ADMIN:
        require(request['residual_risk_accepted'] is True, 'RESIDUAL_RISK_REQUIRED','Explicit residual acceptance required')
        # Exact old policy and mutations reused, not a relaxed missing-exit policy.
        old = body['policy']
        delegated = {**request,'operation':closeout.RELEASE,'preview_digest':old['preview_digest'],
                     'evidence_fingerprint':old['evidence_fingerprint']}
        refs,projection = closeout.apply_recorded(service,c,delegated,operation_id,gate)
    elif body['policy'].get('candidate_action'):
        from .process_reconciliation import apply_recorded as recorded, SCOPE_FIELDS, RECONCILE_PROCESS
        old=body['policy']
        delegated={**request,'operation':RECONCILE_PROCESS,**{k:old['run_revision'] if k=='expected_run_revision' else old[k] for k in SCOPE_FIELDS}}
        refs,projection=recorded(service,c,delegated,operation_id,gate)
    else:
        proof = _managed(closeout.snapshot(c,run['run_id']))
        rec = {'reconciliation_id':identifier('rec'),'operation_id':operation_id,'run_id':run['run_id'],
            'owner_id':service.store._session.owner_id,'recorded_at':now(),'action':ACTION,
            'policy':proof['policy'],'source':'EXPLICIT_RECORDED_SCOPE_RECONCILIATION',
            'evidence_refs':proof['source_refs'],'proof_digest':proof['proof_digest'],
            'conclusion':'RECORDED_MANAGED_SCOPE_ENDED_NOT_SOLVER_SUCCESS'}
        c.execute('INSERT INTO reconciliations VALUES(?,?,?)',(rec['reconciliation_id'],run['run_id'],canonical_json(rec)))
        refs = [rec['reconciliation_id'], *proof['source_refs']]
        updated = update_run(c,run,'RECOVERY_MANAGED_RECONCILED',evidence_refs=refs,
            execution='FINISHED',reconciliation='NONE',reconciled_at=now(),
            recovery_scope_completion='RECONCILED_RECORDED_EMPTY_SCOPE')
        require(c.execute('UPDATE slot SET run_id=NULL WHERE id=1 AND run_id=?',(run['run_id'],)).rowcount==1,
                'STATE_CONFLICT','Slot changed')
        projection = {'run_id':run['run_id'],'run_revision':updated['revision'],'gate':gate_view(c),
                      'effect':'RECORDED_MANAGED_SCOPE_RECONCILED'}
    audit = {'event_id':identifier('control'),'operation_id':operation_id,'type':'RECOVERY_APPLIED',
        'run_id':run['run_id'],'decision':request['decision'],'subject':request['subject'],
        'approval_source':grant['approval_source'],'reason':request['reason'],
        'residual_risk_accepted':request['residual_risk_accepted'],'preview_digest':request['preview_digest'],
        'before_revision':run['revision'],'evidence_fingerprint':request['evidence_fingerprint'],
        'historical_digest':digest(historical),'observation':observed,'recorded_at':now()}
    audit.update(invariants=invariants, mutable_run_fields=mutable,
                 original_event_count=len(original_events), original_events_digest=digest(original_events))
    c.execute('INSERT INTO control_events(body) VALUES(?)',(canonical_json(audit),))
    return [*refs,audit['event_id']],{**projection,'recovery_status':'RECOVERY_APPLIED',
        'execution_verified':False,'solver_or_validation_changed':False}


def verify_interrupted_recovery(context, request):
    """Query original key, including after lost response/new management owner."""
    fields(request,('contract_version','operation','project_id','project_instance_id','owner_id',
                    'management_grant_id','idempotency_key',*SCOPE))
    store = ReadOnlyStore(context)
    receipt = store.management_receipt('trusted-recovery-v1',ACTION,request['idempotency_key'])
    require(receipt is not None,'NOT_FOUND','No committed recovery receipt; do not generate a new key')
    require(receipt['request_digest']==digest({k:v for k,v in request.items() if k!='idempotency_key'}),
            'IDEMPOTENCY_CONFLICT','Original request content required')
    with store.read() as c:
        c.execute('BEGIN')
        run=document(c,'runs','run_id',request['run_id']); gate=gate_view(c)
        used=c.execute('SELECT operation_id FROM management_consumption WHERE grant_id=?',(request['management_grant_id'],)).fetchone()
        audits=[json.loads(r[0]) for r in c.execute('SELECT body FROM control_events WHERE json_extract(body,\'$.operation_id\')=?',(receipt['operation_id'],))]
        audit=next((a for a in audits if a.get('type')=='RECOVERY_APPLIED'),None)
        require(used and used[0]==receipt['operation_id'] and audit,'RECOVERY_VERIFICATION_FAILED','Incomplete committed audit')
        historical={k:v for k,v in run.items() if k not in audit['mutable_run_fields']}
        require(digest(historical)==audit['historical_digest'] and gate['state']=='PAUSED'
            and c.execute('SELECT run_id FROM slot WHERE id=1').fetchone()[0]!=run['run_id'],
            'RECOVERY_VERIFICATION_FAILED','Evidence or resource policy changed after disposition')
        require(_invariants(c,run['run_id'])==audit['invariants'], 'RECOVERY_VERIFICATION_FAILED', 'Protected records changed')
        events=[r[0] for r in c.execute('SELECT body FROM events WHERE run_id=? ORDER BY sequence LIMIT ?',
                                      (run['run_id'],audit['original_event_count']))]
        require(digest(events)==audit['original_events_digest'], 'RECOVERY_VERIFICATION_FAILED', 'Original events changed')
    return {'recovery_status':'RECOVERY_APPLIED','execution_verified':False,'receipt':receipt,
            'current_revision':run['revision'],'dispatch':'PAUSED','old_outputs':'RETAINED_NO_REUSE',
            'solver_conclusion':run.get('solver_conclusion'),'artifact_validation':run.get('artifact_validation'),
            'managed_completion':run.get('managed_completion'),
            'recovery_scope_completion':run.get('recovery_scope_completion'),
            'scope':'committed disposition and current database only; no new OS exit assertion'}
