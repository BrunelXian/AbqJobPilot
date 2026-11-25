"""Policy for bounded, admission-only TEST_ONLY grants."""

from pathlib import Path

from .models import (DELEGATED_GRANT_CONTRACT, RESOURCES, canonical_json, fields,
                     integer, now, require, text)

KIND = "TEST_ONLY_DELEGATED"
ISSUER = "DelegatedFakeOperator"
MAX_PLANS = 32
MAX_RUNS = 128
MAX_LIFETIME_SECONDS = 86400
ADMISSION_RESOURCES = ("memory_bytes", "wall_seconds")


def input_root(context):
    return Path(context.root) / "inputs"


def environment_enabled(service, connection):
    from ..application_runtime import is_frozen_runtime

    enabled = connection.execute("SELECT value FROM meta WHERE key='delegated_grants'").fetchone()
    return (enabled is not None and enabled[0] == DELEGATED_GRANT_CONTRACT
            and not is_frozen_runtime() and service.product_control is None
            and service._standard_backend is None and service._process_backend is None)


def require_environment(service, connection):
    require(environment_enabled(service, connection),
            "TEST_SCOPE_REQUIRED", "Delegation requires an explicitly opted-in source Fake Project")


def plan_resources(value):
    fields(value, ADMISSION_RESOURCES)
    for amount in value.values():
        integer(amount, 1)
    return value


def check_plan_scope(context, plan):
    require(plan["backend_id"] == "fake-v1" and type(plan["backend_version"]) is int
            and plan["backend_version"] == 1 and plan["action"] == "emit_fixture_result"
            and plan["phases"] == ["FAKE"] and plan["validation_policy"] == "fake-result-v1"
            and "delegated_admission" in plan and "sanity" not in plan
            and "process_fixture" not in plan,
            "DELEGATED_SCOPE_MISMATCH", "Only an admission-only Fake Plan is eligible")
    require(plan["job_spec"]["project_id"] == context.project_id
            and plan["job_spec"]["project_instance_id"] == context.project_instance_id,
            "PROJECT_IDENTITY_MISMATCH", "Plan Job belongs to another Project")
    require(canonical_json(plan["resources"]) == canonical_json(RESOURCES)
            and canonical_json(plan["output_policy"]) == canonical_json({
                "root": context.runtime_root, "template": "fake_runs/{run_id}/result.json", "overwrite": False,
            }), "DELEGATED_SCOPE_MISMATCH", "Fixed Fake resources/output policy differs")
    return {**plan["resources"], **plan_resources(plan["delegated_admission"])}


def check_terms(terms):
    fields(terms, ("plans", "resource_limits", "max_runs", "expires_at"))
    plans = terms["plans"]
    require(type(plans) is dict and 0 < len(plans) <= MAX_PLANS,
            "INVALID_REQUEST", "Approve one to 32 exact Plan IDs and digests")
    for plan_id, plan_digest in plans.items():
        text(plan_id)
        text(plan_digest)
    limits = terms["resource_limits"]
    fields(limits, (*RESOURCES, *ADMISSION_RESOURCES))
    for amount in limits.values():
        integer(amount)
    integer(terms["max_runs"], 1)
    require(terms["max_runs"] <= MAX_RUNS, "RESOURCE_LIMIT", "Grant exceeds the Run budget ceiling")
    integer(terms["expires_at"])


def issuer_scope(service):
    context = service.context
    return {"contract_version": DELEGATED_GRANT_CONTRACT, "grant_kind": KIND, "issuer": ISSUER,
            "authority_instance": service.store._session.authority_instance,
            "project_id": context.project_id, "project_instance_id": context.project_instance_id,
            "context_digest": context.context_digest, "client_namespace": service.client_namespace,
            "backend_id": "fake-v1", "backend_version": 1, "allowed_action": "accept_fake_only",
            "input_scope": str(input_root(context)), "output_scope": context.runtime_root}


def check_registration(service, grant_id, grant, anchor_plan_id):
    scope = issuer_scope(service)
    keys = ("plans", "resource_limits", "max_runs", "expires_at")
    fields(grant, (*scope, *keys, "grant_id", "issued_at", "revoked_at"))
    require(grant["grant_id"] == grant_id
            and canonical_json({key: grant[key] for key in scope}) == canonical_json(scope),
            "DELEGATED_SCOPE_MISMATCH", "Grant belongs to another Project, authority or client")
    check_terms({key: grant[key] for key in keys})
    require(anchor_plan_id == min(grant["plans"]), "DELEGATED_SCOPE_MISMATCH", "Grant registration differs")
    integer(grant["issued_at"])
    require(0 < grant["expires_at"] - grant["issued_at"] <= MAX_LIFETIME_SECONDS,
            "INVALID_REQUEST", "Grant lifetime must be positive and at most 24 hours")
    if grant["revoked_at"] is not None:
        integer(grant["revoked_at"])


def validity(grant):
    current = now()
    if grant["revoked_at"] is not None:
        return "REVOKED"
    if current < grant["issued_at"]:
        return "NOT_YET_VALID"
    if current >= grant["expires_at"]:
        return "EXPIRED"
    return "VALID"


def check_admission(service, plan, grant, grant_id, anchor_plan_id):
    check_registration(service, grant_id, grant, anchor_plan_id)
    state = validity(grant)
    require(state == "VALID", f"GRANT_{state}", "Delegated Grant is " + state.lower().replace("_", " "))
    require(grant["plans"].get(plan["plan_id"]) == plan["plan_digest"],
            "DELEGATED_SCOPE_MISMATCH", "Plan ID/digest was outside the approved scope")
    resources = check_plan_scope(service.context, plan)
    require(all(amount <= grant["resource_limits"][name] for name, amount in resources.items()),
            "RESOURCE_LIMIT", "Plan exceeds a delegated resource limit")
