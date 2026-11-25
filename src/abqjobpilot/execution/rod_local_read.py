"""Read-only accepted/started/stop evidence, independent of successful DAT."""
import json
from .models import canonical_json, digest, require
from .store import document
from .rod_local_hil import local


def check_accepted_grant(grant, plan, run, receipt):
    from .product_standard import scope
    require(grant['issuer'] == 'TrustedStandardOperator' and grant['grant_kind'] == 'REAL_ROD_STANDARD'
            and grant['plan_id'] == plan['plan_id'] and grant['plan_digest'] == plan['plan_digest']
            and grant['project_instance_id'] == run['project_instance_id']
            and grant['grant_id'] == run['grant_id'] and grant['max_runs'] == 1
            and grant['product_scope'] == scope(plan) and grant['approval_owner'] == run['owner_id']
            and receipt['accepted_at'] <= grant['expires_at'],
            'REAL_GRANT_REQUIRED', 'Original real exact authorization required, not TEST_ONLY')


def acceptance(reader, *, plan_id, expected_plan_digest, request_key):
    ctx = reader.context
    with reader.store.read() as conn:
        plan = document(conn, 'plans', 'plan_id', plan_id)
        original = dict(plan)
        require(original.pop('plan_digest') == expected_plan_digest == digest(original)
                and local(plan) and plan['project_instance_id'] == ctx.project_instance_id,
                'PLAN_STALE', 'Original local Plan required')
        namespace = canonical_json([ctx.project_instance_id, reader.client_namespace, 'submit'])
        row = conn.execute('SELECT body FROM receipts WHERE namespace=? AND key=?', (namespace, request_key)).fetchone()
        require(row is not None, 'ACCEPTANCE_UNKNOWN', 'Absent receipt is not nonacceptance proof')
        receipt = json.loads(row[0])
        run = document(conn, 'runs', 'run_id', receipt['run_id'])
        grant = document(conn, 'grants', 'grant_id', run['grant_id'])
        check_accepted_grant(grant, plan, run, receipt)
        consumption = conn.execute('SELECT run_id FROM consumption WHERE grant_id=?', (run['grant_id'],)).fetchone()
        event = conn.execute('SELECT body FROM events WHERE sequence=?', (receipt['accepted_sequence'],)).fetchone()
        require(consumption is not None and consumption[0] == run['run_id'] and event is not None
                and run['plan_id'] == plan_id and run['plan_digest'] == expected_plan_digest
                and receipt['request_status'] == 'ACCEPTED' and receipt['idempotency_key'] == request_key
                and receipt['namespace'] == namespace and receipt['job_id'] == run['job_id'] == plan['job_id'],
                'ACCEPTANCE_UNKNOWN', 'Atomic original acceptance records disagree')
        event = {**json.loads(event[0]), 'project_sequence': receipt['accepted_sequence']}
    return {'schema': 'af-local-acceptance-v2', 'project_id': ctx.project_id,
            'project_instance_id': ctx.project_instance_id, 'plan_id': plan_id, 'plan_digest': expected_plan_digest,
            'request_key': request_key, 'receipt': receipt, 'event': event,
            'run': {k: run[k] for k in ('run_id', 'plan_id', 'plan_digest', 'project_id', 'project_instance_id',
                                       'simulation', 'backend_id', 'grant_id')},
            'consumption': {'grant_id': run['grant_id'], 'run_id': run['run_id']}}


def orderly_stop(reader, manager, **refs):
    accepted = acceptance(reader, **refs)
    marker = manager._stopped(manager._current())
    require(marker is not None, 'OWNER_STOP_UNKNOWN', 'Original orderly marker and committed receipt required')
    with reader.store.read() as conn:
        run = document(conn, 'runs', 'run_id', accepted['run']['run_id'])
        from .managed_process import check_completion
        require(run['execution'] == 'FINISHED' and run['reconciliation'] == 'NONE'
                and run['managed_completion'] == 'COMMITTED_EMPTY_SCOPE'
                and run['owner_id'] == marker['receipt']['owner_id']
                and conn.execute('SELECT run_id FROM slot WHERE id=1').fetchone()[0] is None,
                'OWNER_STOP_UNKNOWN', 'Exact finished empty original Run required')
        check_completion(run.get('managed_scope'), run)
    return {'schema': 'af-local-orderly-stop-v2', 'project_instance_id': reader.context.project_instance_id,
            'run_id': run['run_id'], 'owner_id': run['owner_id'],
            'receipt': marker['receipt'], 'scope': 'EMPTY_CONFIRMED'}


def started(reader, **refs):
    accepted = acceptance(reader, **refs)
    with reader.store.read() as conn:
        rows = [json.loads(r[0]) for r in conn.execute('SELECT body FROM events WHERE run_id=?',
                                                      (accepted['run']['run_id'],))]
    created = [e for e in rows if e['type'] == 'STANDARD_CREATED']
    require(len(created) == 1, 'START_UNKNOWN', 'One original creation event required')
    return {'schema': 'af-local-started-v2', 'acceptance': accepted, 'event': created[0]}


def denial(reader, *, plan_id, expected_plan_digest, request_key):
    from .rod_local_hil import decision_namespace
    with reader.store.read() as conn:
        plan = document(conn, 'plans', 'plan_id', plan_id)
        require(local(plan) and plan['plan_digest'] == expected_plan_digest,
                'PLAN_STALE', 'Exact local Plan required')
        rows = conn.execute('SELECT request_digest,body FROM management_receipts WHERE namespace=?',
                            (decision_namespace(reader.context, plan),)).fetchall()
        require(len(rows) == 1 and all(conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] == 0
                                      for t in ('grants', 'runs', 'receipts', 'consumption')),
                'DENIAL_UNKNOWN', 'Terminal denial must precede acceptance')
        value = json.loads(rows[0][1])
        require(rows[0][0] == digest(value) and value['decision'] == 'DENY_TERMINAL'
                and value['plan_digest'] == expected_plan_digest,
                'DENIAL_UNKNOWN', 'Original denial required')
    return {'schema': 'af-local-denial-v2', 'project_instance_id': reader.context.project_instance_id,
            'plan_id': plan_id, 'plan_digest': expected_plan_digest, 'decision': value, 'no_acceptance': True}
