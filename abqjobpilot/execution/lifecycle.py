"""Idle-only lifecycle policy, under the existing owner/session/SQLite locks.

No process termination, permission minting, execution recovery or schema changes.
"""
import hmac
import json
import threading
from .models import ExecutionError, canonical_json, digest, fields, identifier, now, require, text

STOP = 'lifecycle_stop_idle_v1'


def require_idle(connection, *, active_dispatches=0, standard_binding=None):
    require(active_dispatches == 0, 'SERVICE_NOT_IDLE', 'Execution worker still owns an active dispatch')
    require(connection.execute('SELECT run_id FROM slot WHERE id=1').fetchone()[0] is None,
            'SERVICE_NOT_IDLE', 'Execution slot remains occupied')
    # This first product launcher is deliberately TEST_ONLY. Even completed
    # real runs may retain engineering/output quarantine, so do not adopt them.
    rows=connection.execute('SELECT CASE WHEN length(body)<=65536 THEN body END FROM runs LIMIT 513').fetchall()
    require(len(rows)<=512 and all(r[0] for r in rows),'LIMIT_EXCEEDED','Lifecycle inventory bound exceeded')
    for row in rows:
        r=json.loads(row[0])
        product = standard_binding is not None and r['backend_id']=='abaqus-standard-axial-2024-v1'
        require(product or r['backend_id'] in {'fake-v1','python-process-fixture-v1'},
                'LIFECYCLE_SCOPE_UNSUPPORTED','Only isolated TEST_ONLY stores are supported')
        require(r['execution']=='FINISHED' and r['reconciliation']=='NONE'
                and r['queue_state']!='PENDING' and not r.get('administrative_closeout'),
                'SERVICE_NOT_IDLE','Pending, uncertain or unresolved Run prevents lifecycle change')
        if product:
            from .managed_process import check_completion
            require(all(r[k] == standard_binding[k] for k in ('plan_id','plan_digest')),
                    'LIFECYCLE_SCOPE_UNSUPPORTED', 'Run differs from fixed product profile')
            check_completion(r.get('managed_scope'), r)
            require(connection.execute("SELECT 1 FROM events WHERE run_id=? AND json_extract(body,'$.type')='STANDARD_MANAGED_COMPLETED'",(r['run_id'],)).fetchone() is not None,
                    'SERVICE_NOT_IDLE', 'Committed original managed completion event required')
        if product or r['backend_id']=='python-process-fixture-v1':
            require(r.get('managed_completion')=='COMMITTED_EMPTY_SCOPE',
                    'SERVICE_NOT_IDLE','Original managed completion is required; no inferred exit')
    plans=connection.execute('SELECT CASE WHEN length(body)<=65536 THEN body END FROM plans LIMIT 513').fetchall()
    require(len(plans)<=512 and all(p[0] for p in plans),'LIMIT_EXCEEDED','Lifecycle plan bound exceeded')
    def allowed(raw):
        p=json.loads(raw)
        if standard_binding is not None:
            from .product_standard import shape
            shape(p)
            return all(p[k]==standard_binding[k] for k in ('plan_id','plan_digest'))
        return p['backend_id'] in {'fake-v1','python-process-fixture-v1'}
    require(all(allowed(p[0]) for p in plans),
            'LIFECYCLE_SCOPE_UNSUPPORTED','Real execution plans are not enabled by this lifecycle profile')


class LifecycleControl:
    def __init__(self, operator_digest, start_id, *, product_host=False, standard_binding=None):
        text(operator_digest);text(start_id)
        self.operator_digest,self.start_id=operator_digest,start_id
        self.stop_requested=threading.Event()
        self.receipt=None
        self.product_host=product_host
        self.standard_binding=standard_binding

    def admit(self, context):
        # Called with the original OS owner lock held, before owner metadata or
        # dispatch writes. An abandoned/partial claim can never be reused.
        if not self.product_host:return
        from ..service_lifecycle import ServiceLifecycleManager, write_new
        manager=ServiceLifecycleManager(context.root)
        current=manager._current();profile=manager._profile()
        require(current and current['start_id']==self.start_id and current['profile_digest']==digest(profile),
                'START_UNCONFIRMED','Startup reservation changed before ownership acquisition')
        write_new(manager._path(self.start_id+'/claimed.json'),
                  {'start_id':self.start_id,'context_digest':context.context_digest,'recorded_at':now()})

    def stop(self, service, request):
        fields(request,('owner_id','operation_key','operator_token'))
        for v in request.values():text(v)
        require(hmac.compare_digest(digest(request['operator_token']),self.operator_digest),
                'LIFECYCLE_PERMISSION_REQUIRED','Connection permission is not lifecycle permission')
        store=service.store;s=store._session;ctx=store.context
        require(request['owner_id']==s.owner_id,'ENDPOINT_IDENTITY_MISMATCH','Wrong lifecycle owner')
        namespace=canonical_json([ctx.project_instance_id,service.client_namespace,STOP])
        fingerprint=digest({'owner_id':s.owner_id,'start_id':self.start_id,'action':STOP,'key':request['operation_key']})
        with s.lock:
            with store.read() as c:
                prior=c.execute('SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?',
                                (namespace,request['operation_key'])).fetchone()
            if prior:
                require(prior[0]==fingerprint,'IDEMPOTENCY_CONFLICT','Lifecycle key names another request')
                # A commit response may have been lost while this owner stayed
                # alive. Complete the SAME durable idle stop; never a new epoch.
                self.receipt=json.loads(prior[1]);s.stopping=True;self.stop_requested.set()
                return {'replayed':True,'receipt':self.receipt}
            require(not s.stopping,'SERVICE_STOPPING','A stop is already committed or uncertain')
            try:
                with store.transaction('lifecycle_stop') as c:
                    # Same transaction and owner mutex: failed idle checks roll
                    # back PAUSED. Successful ones exclude concurrent dispatch.
                    c.execute("UPDATE dispatch_gate SET state='PAUSED',version=version+1 WHERE id=1")
                    require_idle(c,active_dispatches=s.active_dispatches,standard_binding=self.standard_binding)
                    receipt={'operation_id':identifier('stop'),'action':STOP,'owner_id':s.owner_id,
                        'project_instance_id':ctx.project_instance_id,'start_id':self.start_id,
                        'operation_key':request['operation_key'],'recorded_at':now(),'state':'STOP_COMMITTED',
                        'source':'explicit_lifecycle_operator_capability','effects':['PAUSED','orderly_idle_stop'],
                        'not_evidence_of':'Solver or unknown descendant exit'}
                    c.execute('INSERT INTO management_receipts VALUES(?,?,?,?,?)',
                        (namespace,request['operation_key'],fingerprint,receipt['operation_id'],canonical_json(receipt)))
                    c.execute('INSERT INTO control_events(body) VALUES(?)',(canonical_json(receipt),))
                s.stopping=True
            except ExecutionError as exc:
                if exc.code=='ACCEPTANCE_UNKNOWN':s.stopping=True
                raise
            self.receipt=receipt
            self.stop_requested.set()
        return {'replayed':False,'receipt':receipt}
