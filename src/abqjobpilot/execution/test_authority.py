"""Trusted developer-only TEST_ONLY issuance; never imported by the thin client/RPC.

These helpers register exact records for the existing validators under the live
owner. They are not production human approval or an OS security boundary.
"""

import json
from pathlib import Path

from .authorization import check_grant, check_management_grant
from .models import DelegatedGrant, RESOURCES, canonical_json, digest, identifier, now, require, text
from .public_workflow import VALIDATE, validation_scope
from .store import document


def issue_delegated_fake(service, *, approval_key, plans, resource_limits, max_runs, expires_at):
    """Owner-local operator entry. No IPC operation or client credential can issue a Grant."""
    from .delegated_grant import check_plan_scope, check_registration, check_terms, issuer_scope, require_environment
    from .planning import check_plan

    service._context(service.context)
    text(approval_key)
    terms = {"plans": plans, "resource_limits": resource_limits, "max_runs": max_runs, "expires_at": expires_at}
    check_terms(terms)
    terms = json.loads(canonical_json(terms))
    scope = issuer_scope(service)
    grant_id = "grant_" + digest([scope["context_digest"], scope["authority_instance"], approval_key])[7:39]
    anchor = min(terms["plans"])
    with service.store.transaction("delegated_grant") as connection:
        require_environment(service, connection)
        row = connection.execute("SELECT plan_id,body FROM grants WHERE grant_id=?", (grant_id,)).fetchone()
        if row:
            grant = json.loads(row["body"])
            check_registration(service, grant_id, grant, row["plan_id"])
            require(canonical_json({key: grant[key] for key in terms}) == canonical_json(terms),
                    "IDEMPOTENCY_CONFLICT", "Approval key already names different Grant terms")
        else:
            grant = {**scope, **terms, "grant_id": grant_id, "issued_at": now(), "revoked_at": None}
            check_registration(service, grant_id, grant, anchor)
            row = connection.execute("SELECT body FROM configuration WHERE id=1").fetchone()
            require(row is not None, "PLAN_STALE", "Missing explicit configuration")
            current_config = json.loads(row[0])
            for plan_id, expected in terms["plans"].items():
                plan = document(connection, "plans", "plan_id", plan_id)
                require(plan["plan_digest"] == expected, "PLAN_STALE", "Reviewed Plan digest differs")
                check_plan_scope(service.context, plan)
                check_plan(service.context, plan, current_config)
            connection.execute("INSERT INTO grants VALUES(?,?,?)", (grant_id, anchor, canonical_json(grant)))
    return DelegatedGrant.from_dict(grant)


def revoke_delegated_fake(service, grant_id):
    """Revoke future acceptance without releasing any recorded consumption."""
    from .delegated_grant import check_registration, require_environment

    service._context(service.context)
    text(grant_id)
    with service.store.transaction("delegated_grant") as connection:
        require_environment(service, connection)
        row = connection.execute("SELECT plan_id,body FROM grants WHERE grant_id=?", (grant_id,)).fetchone()
        require(row is not None, "NOT_FOUND", "Delegated Grant not found")
        grant = json.loads(row["body"])
        check_registration(service, grant_id, grant, row["plan_id"])
        if grant["revoked_at"] is None:
            grant["revoked_at"] = now()
            connection.execute("UPDATE grants SET body=? WHERE grant_id=?", (canonical_json(grant), grant_id))
    return DelegatedGrant.from_dict(grant)


def issue_process_execution(service, plan_id, *, expires_at):
    service._context(service.context)
    with service.store.transaction("trusted_test_execution_grant") as c:
        return _issue_process_execution(service, c, plan_id, expires_at=expires_at)


def _issue_process_execution(service, c, plan_id, *, expires_at):
    """Same TEST_ONLY issuer, sharing the caller's atomic review transaction."""
    plan = document(c, "plans", "plan_id", plan_id)
    require(plan["backend_id"] == "python-process-fixture-v1" and service._process_backend is not None,
            "TEST_GRANT_ONLY", "Explicit fixed process configuration required")
    service._process_backend.config.verify(plan["process_fixture"])
    grant = {"grant_id": identifier("grant"), "issuer": "ProcessGrantFixture", "grant_kind": "TEST_ONLY",
             "authority_instance": service.store._session.authority_instance,
             "project_instance_id": service.context.project_instance_id, "plan_id": plan["plan_id"],
             "plan_digest": plan["plan_digest"], "job_id": plan["job_id"], "job_revision": plan["job_revision"],
             "allowed_action": "launch_fixed_python_fixture", "resource_limits": dict(RESOURCES),
             "output_scope": service.context.runtime_root, "expires_at": expires_at, "max_runs": 1}
    check_grant(service.context, plan, grant, service.store._session.authority_instance, None)
    c.execute("INSERT INTO grants VALUES(?,?,?)", (grant["grant_id"], plan_id, canonical_json(grant)))
    return grant["grant_id"]


def issue_validation(service, run_id, *, expires_at):
    service._context(service.context)
    with service.store.transaction("trusted_test_validation_grant") as c:
        scope = validation_scope(c, run_id)
        run = document(c, "runs", "run_id", run_id)
        require(run["backend_id"] == "python-process-fixture-v1" and run["execution"] == "FINISHED"
                and run["reconciliation"] == "NONE" and run["exit_verification"] == "VERIFIED",
                "VALIDATION_PRECONDITION_FAILED", "Operator must review a finished exit-verified test Run")
        grant = {"grant_id": identifier("mg"), "issuer": "FakeManagementFixture", "grant_kind": "TEST_ONLY_MANAGEMENT",
                 "authority_instance": service.store._session.authority_instance,
                 "project_instance_id": service.context.project_instance_id, "context_digest": service.context.context_digest,
                 "owner_id": service.store._session.owner_id, "action": VALIDATE, "scope": scope,
                 "expires_at": expires_at, "max_uses": 1}
        check_management_grant(service.context, grant, service.store._session.authority_instance,
                               service.store._session.owner_id, VALIDATE, scope, False)
        c.execute("INSERT INTO management_grants VALUES(?,?)", (grant["grant_id"], canonical_json(grant)))
    return {"contract_version": "af-management-v1", "operation": VALIDATE,
            "project_id": service.context.project_id, "project_instance_id": service.context.project_instance_id,
            "owner_id": service.store._session.owner_id, "management_grant_id": grant["grant_id"],
            "idempotency_key": identifier("validation-request"), **scope}


def resume_fixed_test_dispatch(service):
    """Owner-local, one-use TEST_ONLY resume for the isolated qualification build."""
    return _resume_fixed_process_dispatch(service, 'normal')


def resume_fixed_result_wait_dispatch(service):
    """Owner-local one-use TEST_ONLY resume for the fixed R6 result_wait scenario."""
    return _resume_fixed_process_dispatch(service, 'result_wait')


def _resume_fixed_process_dispatch(service, expected_scenario):
    from ..application_runtime import executable_role, is_test_only_build
    from .models import now
    from .store import gate_view
    require(is_test_only_build() and executable_role() == 'owner', 'CAPABILITY_UNAVAILABLE',
            'TEST_ONLY management issuance is unavailable in this runtime')
    from ..qualification import require_owner_project
    require_owner_project(service, expected_scenario)
    service._context(service.context)
    require(service.product_control is None, 'DISPATCH_POLICY_MISMATCH',
            'Product-controlled dispatch cannot use the test management path')
    session = service.store._session
    with service.store.transaction('trusted_test_resume_grant') as c:
        plans = [json.loads(row[0]) for row in c.execute('SELECT body FROM plans')]
        grants = [json.loads(row[0]) for row in c.execute('SELECT body FROM grants')]
        require(len(plans) == len(grants) == 1
                and c.execute('SELECT COUNT(*) FROM runs').fetchone()[0] == 0
                and c.execute('SELECT COUNT(*) FROM management_grants').fetchone()[0] == 0,
                'TEST_AUTHORITY_SCOPE', 'Resume requires one fixed TEST_ONLY Plan/Grant and no Run or prior management authority')
        plan, execution_grant = plans[0], grants[0]
        process = plan['backend_id'] == 'python-process-fixture-v1'
        require(plan['backend_id'] in {'fake-v1', 'python-process-fixture-v1'}
                and execution_grant.get('grant_kind') == 'TEST_ONLY'
                and execution_grant.get('issuer') == ('ProcessGrantFixture' if process else 'FakeGrantFixture'),
                'TEST_AUTHORITY_SCOPE', 'REAL or unknown Plan/Grant blocks TEST_ONLY resume')
        if process:
            require(service._process_backend is not None, 'TEST_AUTHORITY_SCOPE',
                    'Frozen TEST_ONLY ProcessFixture backend is not provisioned')
            config = service._process_backend.config
            config.verify(plan['process_fixture'])
            fixture = plan['process_fixture']
            expected_scope = config.binding(expected_scenario)['managed_scope']
            require(config.managed_scope is True and fixture['scenario'] == expected_scenario
                    and fixture['managed_scope'] == expected_scope
                    and fixture['max_seconds'] == 40 and fixture['max_process_members'] == 32,
                    'TEST_AUTHORITY_SCOPE', 'Only the fixed managed ProcessFixture contract is eligible')
            require(fixture['scenario'] == expected_scenario,
                    'TEST_AUTHORITY_SCOPE', 'TEST_ONLY scenario does not match this fixed resume entry')
        else:
            require(plan['action'] == 'emit_fixture_result' and plan['phases'] == ['FAKE'],
                    'TEST_AUTHORITY_SCOPE', 'Only the fixed Fake plan is eligible')
        check_grant(service.context, plan, execution_grant, session.authority_instance, None)
        gate = gate_view(c)
        require(gate['state'] == 'PAUSED' and gate['owner_id'] == session.owner_id
                and session.active_dispatches == 0,
                'GATE_PRECONDITION_FAILED', 'Current Owner must be paused and quiescent')
        from .reconciliation import RESUME
        scope = {'expected_gate_version': gate['version']}
        grant = {'grant_id': identifier('mg'), 'issuer': 'FakeManagementFixture',
                 'grant_kind': 'TEST_ONLY_MANAGEMENT', 'authority_instance': session.authority_instance,
                 'project_instance_id': service.context.project_instance_id,
                 'context_digest': service.context.context_digest, 'owner_id': session.owner_id,
                 'action': RESUME, 'scope': scope, 'expires_at': now() + 120, 'max_uses': 1}
        check_management_grant(service.context, grant, session.authority_instance, session.owner_id,
                               RESUME, scope, False)
        c.execute('INSERT INTO management_grants VALUES(?,?)', (grant['grant_id'], canonical_json(grant)))
    request = {'contract_version': 'af-management-v1', 'operation': 'resume_dispatch',
               'project_id': service.context.project_id,
               'project_instance_id': service.context.project_instance_id,
               'owner_id': session.owner_id, 'management_grant_id': grant['grant_id'],
               'idempotency_key': identifier('test-resume'), **scope}
    result = service.resume_dispatch(service.context, request)
    return {'management_grant_id': grant['grant_id'], 'request': request, 'result': result}


def issue_fixed_process_fixture(service):
    """Owner-signed single normal managed ProcessFixture Plan and TEST_ONLY Grant."""
    return _issue_fixed_process_fixture(service, 'normal')


def issue_fixed_result_wait_fixture(service):
    """Owner-signed single fixed result_wait managed ProcessFixture Plan and Grant."""
    return _issue_fixed_process_fixture(service, 'result_wait')


def _issue_fixed_process_fixture(service, scenario):
    from ..application_runtime import executable_role, is_test_only_build
    from .models import ConfigSnapshot, JobSpec, RESOURCES, identifier, now, require
    require(is_test_only_build() and executable_role() == 'owner'
            and service._process_backend is not None,
            'CAPABILITY_UNAVAILABLE', 'Frozen TEST_ONLY ProcessFixture provisioning is unavailable')
    from ..qualification import require_owner_project
    require_owner_project(service, scenario)
    service._context(service.context)
    config = service._process_backend.config
    require(scenario in {'normal', 'result_wait'}, 'TEST_AUTHORITY_SCOPE',
            'Only fixed normal or result_wait TEST_ONLY scenarios are supported')
    binding = config.binding(scenario)
    config.verify(binding)
    expected_scope = config.binding(scenario)['managed_scope']
    require(binding['scenario'] == scenario and binding['max_seconds'] == 40
            and config.managed_scope is True and binding['managed_scope'] == expected_scope
            and binding['max_process_members'] == 32,
            'TEST_AUTHORITY_SCOPE', 'Only the fixed managed TEST_ONLY ProcessFixture contract is eligible')
    with service.store.read() as c:
        require(c.execute('SELECT COUNT(*) FROM plans').fetchone()[0] == 0
                and c.execute('SELECT COUNT(*) FROM grants').fetchone()[0] == 0
                and c.execute('SELECT COUNT(*) FROM runs').fetchone()[0] == 0,
                'TEST_AUTHORITY_SCOPE', 'Fixture project must be empty before its single test Plan')
    input_path = Path(service.context.root) / f'ap_d01c_p2b_r6_{scenario}_input.txt'
    with input_path.open('x', encoding='utf-8') as stream:
        stream.write(f'AP-D01C-P2B-R6 fixed {scenario} ProcessFixture input\n')
    snapshot = ConfigSnapshot.from_dict({'config_revision': 1,
                                         'values': {'label': f'ap-d01c-p2b-r6-fixed-{scenario}'}})
    service.configure(service.context, snapshot)
    spec = JobSpec.from_dict({'job_id': identifier('job'), 'revision': 1,
                              'project_id': service.context.project_id,
                              'project_instance_id': service.context.project_instance_id,
                              'input_refs': [str(input_path)], 'resources': dict(RESOURCES),
                              'metadata': {'purpose': f'AP-D01C-P2B-R6 fixed {scenario} TEST_ONLY fixture'}})
    plan = service.prepare(service.context, spec, snapshot, expires_at=now() + 3600,
                           process_scenario=scenario)
    with service.store.transaction('trusted_test_process_grant') as c:
        grant_id = _issue_process_execution(service, c, plan.to_dict()['plan_id'], expires_at=now() + 3600)
    return {'plan': plan.to_dict(), 'grant_id': grant_id}
