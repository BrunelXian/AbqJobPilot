"""Human-only narrow local terminal entry. Never called by GD/MCP or on import.

Run only after separate real-execution approval. Same-user DPAPI custody is not
hostile-agent isolation. No Owner start; explicit dispatch arms only the original AF single-use worker.
"""
import json
import secrets
import sys

from .execution.models import canonical_json, digest, now, require
from .execution.rod_local_hil import FORMAT, local, qualified
from .execution.product_standard import scope
from .execution.store import open_existing_read_only, acquire_initial_preparation_store, document
from .local_credentials import private_value
from .product_standard import StandardOperator
from .service_lifecycle import ServiceLifecycleManager, write_new


def main():
    # No stdin piping, choice argument, automatic yes or fallback channel.
    require(sys.stdin.isatty() and sys.stdout.isatty() and len(sys.argv) == 6,
            'HUMAN_TERMINAL_REQUIRED', 'Usage: module provision|review|dispatch PROJECT PLAN_ID PLAN_DIGEST RESEARCH_ROOT')
    mode, project, plan_id, plan_digest, research_root = sys.argv[1:]
    require(mode in ('provision', 'review', 'dispatch'), 'INVALID_REQUEST', 'Only exact local preparation/review')
    manager = ServiceLifecycleManager(project)
    base = manager._profile()
    with open_existing_read_only(manager.context).read() as conn:
        plan = document(conn, 'plans', 'plan_id', plan_id)
    require(local(plan) and plan['plan_digest'] == plan_digest, 'PLAN_STALE', 'Exact frozen local Plan required')
    from .execution.standard_contract import StandardConfig
    from types import SimpleNamespace
    from .execution.rod_trusted import check_plan
    config = StandardConfig(canonical_json(plan['runtime_binding']))
    reader = SimpleNamespace(context=manager.context, store=open_existing_read_only(manager.context),
                             _standard_backend=SimpleNamespace(config=config))
    check_plan(reader, plan)
    from aegiscae.research.project import open_existing_readonly
    from aegiscae.research.rod_local_project import LocalRodProject, code_digest
    research = LocalRodProject(open_existing_readonly(research_root))
    view = research.inspect()
    phase = plan['rod_contract']['phase']
    attempt = view['attempts'].get(phase)
    expected_states = {'provision': ('HELD',), 'review': ('HELD',), 'dispatch': ('ACCEPTED',)}
    require(view['research_project_id'] == plan['rod_contract']['research_project_id']
            and view['contract_digest'] == plan['rod_contract']['contract_digest']
            and view['policy']['runtime'] == plan['rod_contract']['local_contract']['runtime']
            and code_digest() == view['policy']['runtime']['gd']
            and attempt is not None and attempt['status'] in expected_states[mode]
            and attempt['binding']['project_instance_id'] == manager.context.project_instance_id
            and attempt['binding']['plan_id'] == plan_id and attempt['binding']['plan_digest'] == plan_digest
            and view['candidates'][phase]['candidate_id'] == plan['rod_contract']['candidate_id'],
            'RESEARCH_BUDGET_UNQUALIFIED', 'Exact frozen research hold/intent/charge required')
    packet = scope(plan)
    stamp = now()
    expiry = min(stamp + 300, plan['expires_at'])
    nonce = plan['rod_contract']['request_nonce']
    require(stamp < expiry, 'HIL_APPROVAL_EXPIRED', 'Plan already expired')
    dispatch = None
    if mode == 'dispatch':
        with reader.store.read() as conn:
            rows = conn.execute('SELECT body FROM runs WHERE plan_id=?', (plan_id,)).fetchall()
            require(len(rows) == 1, 'DISPATCH_SCOPE_CONFLICT', 'One original accepted Run required')
            run = json.loads(rows[0][0])
            require(run['execution'] == 'PLANNED' and run['queue_state'] == 'PENDING'
                    and run.get('launch_state') == 'NOT_CALLED' and not run.get('single_dispatch'),
                    'STALE_DISPATCH', 'Never rearm a submitted or unknown attempt')
            grant = document(conn, 'grants', 'grant_id', run['grant_id'])
            dispatch = {'run_id': run['run_id'], 'revision': run['revision'],
                        'gate_version': conn.execute('SELECT version FROM dispatch_gate WHERE id=1').fetchone()[0],
                        'start_not_after': min(now()+20, grant['expires_at'])}
        print(json.dumps({'exact_run': run['run_id'], 'grant_id': grant['grant_id'],
                          'dispatch': dispatch, 'extra_calls': 0}))
    # This contains public Plan scope, never private lifecycle/operator credentials.
    print(json.dumps({'mode': mode, 'scope': packet, 'trust': 'TRUSTED_LOCAL_HIL',
                      'not_before': stamp, 'expires_at': expiry, 'plan_expires_at': plan['expires_at'],
                      'nonce': nonce, 'budget': view['budget'], 'research_revision': view['project_revision'],
                      'same_user_tamper_resistance': False}, indent=2))
    confirmation = input('Type APPROVE ' + plan_digest + ' or DENY: ').strip()
    require(confirmation in ('APPROVE ' + plan_digest, 'DENY'), 'HIL_NOT_CONFIRMED', 'Stop without side effects')
    approve = confirmation.startswith('APPROVE ')
    require(now() < expiry and research.inspect() == view, 'HIL_APPROVAL_EXPIRED', 'Window or research state changed during confirmation')
    if mode == 'provision':
        require(approve, 'HIL_DENIED', 'No provisioning after denial')
        require('standard_extension' not in base and base['process_config'] is None,
                'LIFECYCLE_PROVISIONING_CLOSED', 'No replacement or migration')
        store = acquire_initial_preparation_store(manager.context, base['authority_instance'])
        try:
            with store.read() as conn:
                require(conn.execute('SELECT COUNT(*) FROM plans').fetchone()[0] == 1
                        and all(conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] == 0
                                for t in ('runs', 'grants', 'receipts', 'consumption')),
                        'LIFECYCLE_PROVISIONING_CLOSED', 'Fresh single Plan only')
            token = secrets.token_hex(32)
            binding = {'plan_id': plan_id, 'plan_digest': plan_digest, 'operator_digest': digest(token),
                       'local_policy_digest': digest(plan['rod_contract']['local_contract'])}
            qualified(reader, plan, binding)
            write_new(manager._path('standard-operator.json'), private_value(manager.context,
                {'format': FORMAT, 'context_digest': manager.context.context_digest, 'operator_token': token}))
            write_new(manager._path('standard-profile.json'), private_value(manager.context,
                {'format': FORMAT, 'context_digest': manager.context.context_digest,
                 'base_profile_digest': digest(base), 'standard_config': config.value(), 'binding': binding}))
        finally:
            store.close()
        print('PROVISIONED_NO_GRANT')
        return
    operator = StandardOperator(project)
    if mode == 'dispatch':
        require(approve, 'HIL_DENIED', 'No dispatch after denial')
        result = operator.request('dispatch_once', dispatch, operation_key='dispatch_' + run['run_id'],
                                  owner_id=run['owner_id'])
        print(json.dumps({'status': 'EXACT_DISPATCH_ARMED', 'operation_id': result['receipt']['operation_id']}))
        return
    decision = operator.request('review_a', {'plan_id': plan_id, 'plan_digest': plan_digest,
        'scope_digest': digest(packet), 'decision': 'APPROVE_EXACT' if approve else 'DENY_TERMINAL',
        'nonce': nonce, 'not_before': stamp, 'expires_at': expiry}, operation_key='review_' + nonce)
    if not approve:
        print('DENY_TERMINAL')
        return
    result = operator.request('authorize', {'plan_id': plan_id, 'plan_digest': plan_digest,
        'expires_at': expiry, 'subject': 'HUMAN_LOCAL_CONSOLE', 'source': decision['receipt']['decision_digest']},
        operation_key='authorize_' + nonce)
    print(json.dumps({'status': 'EXACT_GRANT_RECORDED', 'grant_id': result['receipt']['grant_id']}))


if __name__ == '__main__':
    # Unknown after any write is retained; no retries or cleanup.
    try:
        main()
    except Exception:
        print('LOCAL_HIL_STOPPED_UNKNOWN_NO_RETRY', file=sys.stderr)
        raise SystemExit(1) from None
