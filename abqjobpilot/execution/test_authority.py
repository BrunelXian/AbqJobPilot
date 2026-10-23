"""Trusted developer-only TEST_ONLY issuance; never imported by the thin client/RPC.

These helpers register exact records for the existing validators under the live
owner. They are not production human approval or an OS security boundary.
"""

from .authorization import check_grant, check_management_grant
from .models import RESOURCES, canonical_json, identifier, now, require
from .public_workflow import VALIDATE, validation_scope
from .store import document


def issue_process_execution(service, plan_id, *, expires_at):
    service._context(service.context)
    with service.store.transaction("trusted_test_execution_grant") as c:
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
