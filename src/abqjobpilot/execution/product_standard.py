"""Exact one-Plan product control. No general resume, retry or authority inference.

The trusted initial provisioner creates a separate local operator capability.
Only the active owner can consume it through authenticated IPC. Same-user code
and filesystem access remain the trust boundary, not production human approval.
The global gate stays PAUSED throughout acceptance, dispatch and completion.
"""
import hmac
import json

from . import sanity_hil
from .models import canonical_json, digest, fields, identifier, integer, now, require, text
from .sanity_simulation import ACTION as SIMULATE, PERMIT_KIND, accepted_receipt, matches
from .store import document, update_run

SCHEMA = 'standard-managed-product-single-v1'
POLICY = {'contract': 'product-standard-once-v1', 'launch_budget': 1,
          'grant_seconds_max': 600, 'start_seconds_max': 30,
          'after_claim': 'PAUSED', 'observation_seconds': 300}


def single(plan):
    return plan.get('plan_schema') in (SCHEMA, 'standard-managed-rod-single-v1')


def shape(plan):
    require(single(plan) and plan.get('product_dispatch') == POLICY and
            'standard_sequence' not in plan, 'PLAN_STALE', 'Exact single dispatch policy required')


def scope(plan):
    # Redundant readable scope binds all physical and semantic execution inputs.
    result = {k: plan[k] for k in ('plan_id', 'plan_digest', 'context_digest', 'project_instance_id',
        'backend_id', 'runtime_binding', 'input_manifest', 'engineering', 'scratch', 'job_name',
        'output_key', 'resources', 'process_management', 'product_dispatch')}
    if 'sanity' in plan:
        result['sanity'] = plan['sanity']
    if plan.get('plan_schema') == 'standard-managed-rod-single-v1':
        result['rod_contract'] = plan['rod_contract']
    return result


class ProductStandardControl:
    def __init__(self, binding):
        fields(binding, ('plan_id', 'plan_digest', 'operator_digest', 'hil_digest')
               if 'hil_digest' in binding else ('plan_id', 'plan_digest', 'operator_digest', 'local_policy_digest')
               if 'local_policy_digest' in binding else ('plan_id', 'plan_digest', 'operator_digest', 'authority_digest')
               if 'authority_digest' in binding else ('plan_id', 'plan_digest', 'operator_digest'))
        for value in binding.values():
            text(value)
        self.binding = dict(binding)
        self.blocked = False

    def check_plan(self, plan):
        shape(plan)
        require(all(plan[k] == self.binding[k] for k in ('plan_id', 'plan_digest')),
                'GRANT_SCOPE_MISMATCH', 'Only the provisioned product Plan is supported')
        hil = plan.get('sanity', {}).get('hil')
        require(self.binding.get('hil_digest') == (digest(hil) if hil else None),
                'HIL_SCOPE_MISMATCH', 'Plan differs from its sealed HIL preparation')

    def accept(self, service, conn, plan):
        self.check_plan(plan)
        require(conn.execute('SELECT state FROM dispatch_gate WHERE id=1').fetchone()[0] == 'PAUSED',
                'DISPATCH_POLICY_MISMATCH', 'Product single dispatch never uses general OPEN')
        require(conn.execute('SELECT run_id FROM slot WHERE id=1').fetchone()[0] is None,
                'SLOT_BUSY', 'Execution slot is occupied')

    def invoke(self, service, request):
        fields(request, ('action', 'owner_id', 'operation_key', 'operator_token', 'arguments'))
        for key in ('action', 'owner_id', 'operation_key', 'operator_token'):
            text(request[key])
        require(hmac.compare_digest(digest(request['operator_token']), self.binding['operator_digest']),
                'REAL_OPERATOR_REQUIRED', 'IPC and lifecycle permissions cannot authorize execution')
        action = request['action']
        args = request['arguments']
        from . import hil_odb, odb_access, odb_history
        if action in odb_history.ACTIONS:
            return odb_history.invoke(service, self, request)
        if action in (hil_odb.EXTRACT, hil_odb.STATUS, odb_access.PREVIEW):
            return odb_access.invoke(service, self, request)
        require(action in ('authorize', 'dispatch_once', 'review_a', sanity_hil.REVIEW, SIMULATE),
                'INVALID_REQUEST', 'Unsupported product control action')
        if action == sanity_hil.REVIEW:
            sanity_hil.decision_input(args)
        elif action == 'authorize':
            fields(args, ('plan_id', 'plan_digest', 'expires_at', 'subject', 'source'))
            integer(args['expires_at'])
            text(args['subject'])
            text(args['source'])
            require(len(args['subject']) <= 128 and len(args['source']) <= 256,
                    'LIMIT_EXCEEDED', 'Bounded actual authorization reference required')
        elif action in ('dispatch_once', SIMULATE):
            fields(args, ('run_id', 'revision', 'gate_version', 'start_not_after'))
            text(args['run_id'])
            integer(args['revision'])
            integer(args['gate_version'])
            integer(args['start_not_after'])
        else:
            fields(args, ('plan_id', 'plan_digest', 'scope_digest', 'decision', 'nonce',
                          'not_before', 'expires_at'))
            for key in ('plan_id', 'plan_digest', 'scope_digest', 'decision', 'nonce'):
                text(args[key])
            integer(args['not_before'])
            integer(args['expires_at'])
            require(args['decision'] in ('APPROVE_EXACT', 'DENY_TERMINAL'),
                    'INVALID_REQUEST', 'Exact approval or terminal denial required')
        store = service.store
        owner = store._session.owner_id
        namespace = canonical_json([service.context.project_instance_id, service.client_namespace, 'product_standard_'+action])
        fingerprint = digest({k: request[k] for k in ('action', 'owner_id', 'operation_key', 'arguments')})
        with store.transaction('management') as conn:
            plan = document(conn, 'plans', 'plan_id', self.binding['plan_id'])
            from . import rod_authority, rod_local_hil
            local = rod_local_hil.local(plan)
            authority = rod_local_hil if local else rod_authority
            dynamic = rod_authority.dynamic(plan)
            qualification = authority.qualified(service, plan, self.binding) if dynamic else None
            hil = sanity_hil.from_plan(plan)
            require(action != 'review_a' or dynamic, 'INVALID_REQUEST', 'A review applies only to dynamic rod')
            require(action != sanity_hil.REVIEW or hil, 'INVALID_REQUEST', 'Expected a dedicated Sanity HIL Plan')
            prior = conn.execute('SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?',
                                 (namespace, request['operation_key'])).fetchone()
            if prior:
                require(prior[0] == fingerprint, 'IDEMPOTENCY_CONFLICT', 'Operation key has different content')
                return {'replayed': True, 'receipt': json.loads(prior[1])}
            require(request['owner_id'] == owner, 'ENDPOINT_IDENTITY_MISMATCH', 'Current owner required for a new operation')
            self.accept(service, conn, plan)
            if action == SIMULATE:
                require(matches(plan) and request['operation_key'] == plan['sanity']['request_key'] + '.simulate',
                        'TEST_GRANT_ONLY', 'Only the exact TEST_ONLY Sanity key can arm simulation')
            from .standard_contract import check_plan, _issue
            check_plan(service, plan)
            receipt = {'operation_id': identifier('op'), 'action': action, 'owner_id': owner,
                'project_id': service.context.project_id, 'project_instance_id': service.context.project_instance_id,
                'plan_id': plan['plan_id'], 'plan_digest': plan['plan_digest'],
                'operation_key': request['operation_key'], 'recorded_at': now(), 'dispatch_state': 'PAUSED'}
            if action == sanity_hil.REVIEW:
                if sanity_hil.external(plan):
                    require(request['operation_key'] == plan['sanity']['request_key'] + '.review',
                            'HIL_SCOPE_MISMATCH', 'Exact HIL approval key required')
                decision = sanity_hil.record_decision(service, conn, plan, args, owner)
                receipt.update(decision=args['decision'], decision_digest=digest(decision),
                               allow_odb=decision['allow_odb'], grant_id=None)
            elif action == 'review_a':
                require(args['plan_id'] == plan['plan_id'] and args['plan_digest'] == plan['plan_digest']
                        and args['scope_digest'] == digest(scope(plan)),
                        'HIL_SCOPE_MISMATCH', 'Decision must display and bind the exact Plan scope')
                require(args['not_before'] <= now() < args['expires_at']
                        <= min(plan['expires_at'], qualification['expires_at'], args['not_before']+600)
                        and len(args['nonce']) <= 96, 'HIL_APPROVAL_EXPIRED', 'Exact short decision window required')
                if local:
                    require(args['nonce'] == plan['rod_contract']['request_nonce'], 'HIL_SCOPE_MISMATCH', 'Exact frozen nonce required')
                final_ns = authority.decision_namespace(service.context, plan)
                require(conn.execute('SELECT COUNT(*) FROM management_receipts WHERE namespace=?',
                                     (final_ns,)).fetchone()[0] == 0,
                        'HIL_DECISION_FINAL', 'A decision cannot be replaced using a new key')
                require(conn.execute('SELECT COUNT(*) FROM grants').fetchone()[0] == 0
                        and conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0] == 0,
                        'HIL_DECISION_FINAL', 'Review precedes all Grants and Runs')
                decision = {'schema': 'protected-rod-A-decision-v1', **args,
                    'authority_digest': qualification.get('manifest_digest'),
                    'issuer_sid': qualification.get('issuer_sid'), 'owner_id': owner,
                    'operation_id': identifier('op'), 'human_channel': 'PROTECTED_ISSUER_CONSOLE'}
                if local:
                    decision.pop('authority_digest')
                    decision.pop('issuer_sid')
                    decision.update(schema='trusted-local-rod-decision-v2',
                        policy_digest=qualification['policy_digest'], subject=qualification['subject'],
                        human_channel='TRUSTED_LOCAL_CONSOLE')
                conn.execute('INSERT INTO management_receipts VALUES(?,?,?,?,?)',
                    (final_ns, args['nonce'], digest(decision), decision['operation_id'], canonical_json(decision)))
                receipt.update(decision=args['decision'], decision_digest=digest(decision), grant_id=None)
            elif action == 'authorize':
                if hil:
                    decision = sanity_hil.require_decision(service, conn, plan)
                    require(args['subject'] == decision['subject']
                            and request['operation_key'] == plan['sanity']['request_key'] + '.grant',
                            'HIL_SCOPE_MISMATCH', 'Grant key and subject must match the approved HIL')
                elif 'sanity' in plan:
                    s = plan['sanity']
                    require(s['launch_budget']==1 and args['source']==s['admission_digest'] and
                            args['subject']==s['research_project'] and request['operation_key']==s['request_key']+'.grant',
                            'SANITY_GRANT_DENIED','Exact admission, key and remaining slot required')
                if dynamic:
                    decision = authority.require_decision(service, conn, plan, self.binding)
                    require(args['subject'] == decision['subject' if local else 'issuer_sid']
                            and args['source'] == digest(decision)
                            and args['expires_at'] <= decision['expires_at'],
                            'HIL_SCOPE_MISMATCH', 'Authorization must reference the protected decision')
                require(args['plan_id'] == plan['plan_id'] and args['plan_digest'] == plan['plan_digest'],
                        'GRANT_SCOPE_MISMATCH', 'Authorization names another Plan')
                require(now() < args['expires_at'] <= now() + POLICY['grant_seconds_max'],
                        'GRANT_EXPIRED', 'Bounded approval validity required')
                grant = _issue(service, conn, plan, args['expires_at'], args['source'])
                grant.update(project_id=service.context.project_id, product_scope=scope(plan),
                    approval_subject=args['subject'], approval_owner=owner, approval_operation=receipt['operation_id'])
                conn.execute('UPDATE grants SET body=? WHERE grant_id=?', (canonical_json(grant), grant['grant_id']))
                receipt.update(grant_id=grant['grant_id'], subject=args['subject'], source=args['source'],
                               expires_at=grant['expires_at'], scope_digest=digest(scope(plan)))
            else:
                if hil:
                    sanity_hil.require_decision(service, conn, plan)
                if action == 'dispatch_once' and 'sanity' in plan:
                    require(plan['sanity']['mode']=='REAL' and request['operation_key']==plan['sanity']['request_key']+'.start',
                            'REAL_OPERATOR_REQUIRED','Test scope cannot dispatch a Standard process')
                if dynamic:
                    authority.require_decision(service, conn, plan, self.binding)
                run = document(conn, 'runs', 'run_id', args['run_id'])
                require(run['plan_id'] == plan['plan_id'] and run['plan_digest'] == plan['plan_digest'] and
                        run['owner_id'] == owner and run['revision'] == args['revision'] and
                        run['execution'] == 'PLANNED' and run['queue_state'] == 'PENDING' and
                        run.get('launch_state') == 'NOT_CALLED' and not run.get('single_dispatch'),
                        'STALE_DISPATCH', 'Exact unattempted Run revision required')
                require(conn.execute('SELECT version FROM dispatch_gate WHERE id=1').fetchone()[0] == args['gate_version'],
                        'STALE_DISPATCH', 'Dispatch view changed')
                require(conn.execute('SELECT COUNT(*) FROM runs').fetchone()[0] == 1,
                        'DISPATCH_SCOPE_CONFLICT', 'One fixed Run only; no other pending work')
                grant = document(conn, 'grants', 'grant_id', run['grant_id'])
                from .standard_contract import check_grant
                consumed = conn.execute('SELECT run_id FROM consumption WHERE grant_id=?', (run['grant_id'],)).fetchone()
                check_grant(service, plan, grant, consumed[0] if consumed else None, run['run_id'])
                require(now() < args['start_not_after'] <= min(now()+POLICY['start_seconds_max'], grant['expires_at']),
                        'START_WINDOW_EXPIRED', 'Exact bounded start window required')
                permit = {'operation_id': receipt['operation_id'], 'owner_id': owner, 'run_id': run['run_id'],
                    'plan_digest': plan['plan_digest'], 'grant_id': run['grant_id'], 'state': 'ARMED',
                    'start_not_after': args['start_not_after']}
                if action == SIMULATE:
                    accepted_receipt(conn, plan, run)
                    permit.update(kind=PERMIT_KIND, phase_attempt_id=run['phase_attempt_id'])
                    receipt.update(phase_attempt_id=run['phase_attempt_id'], simulation=True)
                update_run(conn, run, 'PRODUCT_DISPATCH_AUTHORIZED', single_dispatch=permit,
                           start_not_after=permit['start_not_after'])
                receipt.update(run_id=run['run_id'], grant_id=run['grant_id'], start_not_after=permit['start_not_after'])
            conn.execute('INSERT INTO management_receipts VALUES(?,?,?,?,?)',
                (namespace, request['operation_key'], fingerprint, receipt['operation_id'], canonical_json(receipt)))
            conn.execute('INSERT INTO control_events(body) VALUES(?)', (canonical_json(receipt),))
        store._checkpoint('product_control:after_commit')
        return {'replayed': False, 'receipt': receipt}

    def start_check(self, service, conn, plan, run_id):
        self.check_plan(plan)
        from . import rod_authority, rod_local_hil
        authority = rod_local_hil if rod_local_hil.local(plan) else rod_authority
        if rod_authority.dynamic(plan):
            authority.require_decision(service, conn, plan, self.binding)
        if sanity_hil.from_plan(plan):
            sanity_hil.require_decision(service, conn, plan)
        run = document(conn, 'runs', 'run_id', run_id)
        permit = run.get('single_dispatch', {})
        require(permit.get('state') in ('ARMED', 'CLAIMED') and
                permit.get('owner_id') == service.store._session.owner_id == run['owner_id'] and
                permit.get('run_id') == run_id and permit.get('plan_digest') == plan['plan_digest'] and
                permit.get('grant_id') == run['grant_id'], 'DISPATCH_PAUSED', 'Exact current-owner one-shot permission required')
        if matches(plan):
            require(permit.get('kind') == PERMIT_KIND and permit.get('phase_attempt_id') == run['phase_attempt_id'],
                    'DISPATCH_PAUSED', 'Exact TEST_ONLY simulation permit required')
            accepted_receipt(conn, plan, run)
        require(now() < permit['start_not_after'], 'START_WINDOW_EXPIRED', 'No late or deferred launch')
        require(conn.execute('SELECT state FROM dispatch_gate WHERE id=1').fetchone()[0] == 'PAUSED',
                'DISPATCH_POLICY_MISMATCH', 'Single dispatch must remain globally PAUSED')

    def pending(self, service):
        if self.blocked or service.store._session.stopping:
            return None
        with service.store.read() as conn:
            if conn.execute('SELECT run_id FROM slot WHERE id=1').fetchone()[0] is not None:
                return None
            for row in conn.execute('SELECT body FROM runs WHERE plan_id=?', (self.binding['plan_id'],)):
                run = json.loads(row[0])
                permit = run.get('single_dispatch', {})
                if (run['execution'] == 'PLANNED' and run['queue_state'] == 'PENDING' and
                    permit.get('state') == 'ARMED' and permit.get('owner_id') == service.store._session.owner_id):
                    return run['run_id']
        return None

    def claim(self, service, conn, run):
        permit = run['single_dispatch']
        require(permit['state'] == 'ARMED', 'DISPATCH_CONSUMED', 'Single dispatch already consumed')
        claimed_at = now()
        timing = {} if permit.get('kind') == PERMIT_KIND else {'batch_observation_not_after': now()+300}
        return update_run(conn, run, 'PRODUCT_DISPATCH_CONSUMED',
                          single_dispatch={**permit, 'state': 'CLAIMED', 'claimed_at': claimed_at}, **timing)
