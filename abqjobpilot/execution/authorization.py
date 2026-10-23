"""Verification only. Test grant issuance lives in the test harness."""

from .models import RESOURCES, canonical_json, fields, integer, now, require


def check_grant(context, plan, grant, authority_instance, consumed_by, run_id=None, *, at_time=None):
    require(grant is not None, "GRANT_REQUIRED", "No registered grant")
    fields(grant, ("grant_id", "issuer", "authority_instance", "grant_kind", "project_instance_id",
                   "plan_id", "plan_digest", "job_id", "job_revision", "allowed_action",
                   "resource_limits", "output_scope", "expires_at", "max_runs"))
    process = plan["backend_id"] == "python-process-fixture-v1"
    require(grant["grant_kind"] == "TEST_ONLY" and grant["issuer"] == ("ProcessGrantFixture" if process else "FakeGrantFixture"),
            "TEST_GRANT_ONLY", "Only fixture-issued TEST_ONLY grants accepted")
    require(grant["authority_instance"] == authority_instance, "GRANT_SCOPE_MISMATCH", "Wrong fixture authority")
    expected = {"project_instance_id": context.project_instance_id, "plan_id": plan["plan_id"],
                "plan_digest": plan["plan_digest"], "job_id": plan["job_id"],
                "job_revision": plan["job_revision"], "allowed_action": "launch_fixed_python_fixture" if process else "emit_fixture_result",
                "resource_limits": RESOURCES, "output_scope": context.runtime_root, "max_runs": 1}
    require(all(type(grant[key]) is type(value) and grant[key] == value for key, value in expected.items()),
            "GRANT_SCOPE_MISMATCH", "Grant does not bind this exact plan, Project and budget")
    for amount in grant["resource_limits"].values():
        integer(amount)
    integer(grant["expires_at"])
    require(grant["expires_at"] > (now() if at_time is None else at_time), "GRANT_EXPIRED", "Grant expired before execution")
    require(consumed_by is None or (run_id is not None and consumed_by == run_id),
            "GRANT_CONSUMED", "Grant already belongs to another Run")


def check_management_grant(context, grant, authority, owner_id, action, scope, consumed):
    require(grant is not None, "MANAGEMENT_GRANT_REQUIRED", "A registered test management grant is required")
    fields(grant, ("grant_id", "issuer", "authority_instance", "grant_kind", "project_instance_id",
                   "context_digest", "owner_id", "action", "scope", "expires_at", "max_uses"))
    expected = {"issuer": "FakeManagementFixture", "authority_instance": authority,
                "grant_kind": "TEST_ONLY_MANAGEMENT", "project_instance_id": context.project_instance_id,
                "context_digest": context.context_digest, "owner_id": owner_id,
                "action": action, "scope": scope, "max_uses": 1}
    require(all(type(grant[k]) is type(v) and grant[k] == v for k, v in expected.items()),
            "MANAGEMENT_SCOPE_MISMATCH", "Management grant does not authorize these exact preconditions")
    require(canonical_json(grant["scope"]) == canonical_json(scope), "MANAGEMENT_SCOPE_MISMATCH", "Management scope types must match exactly")
    integer(grant["expires_at"])
    require(grant["expires_at"] > now(), "MANAGEMENT_GRANT_EXPIRED", "Test management permission expired")
    require(not consumed, "MANAGEMENT_GRANT_CONSUMED", "Test management permission was consumed")
