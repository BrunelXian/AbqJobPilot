"""Versioned public offline rod Plan registration in the existing AF store.

Creates real ExecutionPlan records, not real execution authorization. No schema
migration, default backend selection, launch, Grant issuance or Owner startup.
The product lifecycle has not qualified this backend; all execution is refused.
"""
from pathlib import Path

from .models import ExecutionPlan, canonical_json, digest, require
from .rod_profile import RodPlanPreview, revalidate_materialization
from .store import document

BACKEND = "abaqus-standard-rod-preview-v1"
SCHEMA = "registered-rod-offline-plan-v1"
ACTION = "execute_axial_rod_cload_once"


def register_plan(service, preview, candidate, *, expected_digest, at_time, phase="A", product_request=None):
    """Register exactly one A prerequisite Plan in an explicitly idle PAUSED store.

    B registration is blocked until a qualified real A evidence handoff exists.
    Retries of the same preview reuse its deterministic ID; conflicting content
    or any prior different Plan, Grant or Run is refused. No lifecycle bypass.
    """
    context = service.context
    service._context(context)
    require(phase == "A", "REAL_A_EVIDENCE_REQUIRED", "B requires a separately qualified actual A result")
    raw = revalidate_materialization(preview, candidate, test_root=context.test_root,
                                     expected_digest=expected_digest, project_id=context.project_id,
                                     project_instance_id=context.project_instance_id, at_time=at_time)
    suffix = digest({"instance": context.project_instance_id, "preview": expected_digest}).split(":")[1][:32]
    job_id, plan_id = "rod_job_" + suffix, "rod_plan_" + suffix
    data = {"plan_id": plan_id, "job_id": job_id, "job_revision": 1,
            "job_spec": {"job_id": job_id, "revision": 1},
            "project_instance_id": context.project_instance_id, "context_digest": context.context_digest,
            "backend_id": BACKEND, "backend_version": 1, "action": ACTION,
            "phases": ["STANDARD_ANALYSIS"], "resources": raw["resources"],
            "input_manifest": [{"path": raw["input_path"], "size": len(candidate.input_bytes),
                                "digest": raw["candidate"]["input_digest"]}],
            "engineering": str(Path(raw["input_path"]).parent), "scratch": raw["scratch"],
            "output_key": digest({"output": raw["output_path"].casefold()}),
            "output_policy": {"overwrite": False, "root": raw["output_path"]},
            "validation_policy": "axial-rod-bound-dat-v1", "expires_at": raw["expires_at"],
            "plan_schema": SCHEMA, "profile": raw["profile"], "rod_preview": raw,
            "registration_scope": "OFFLINE_ONLY", "execution_authorized": False,
            "live_dispatch": "PRODUCT_LIFECYCLE_AND_AUTHORITY_UNQUALIFIED"}
    if product_request is not None:
        require(type(product_request) is dict, "INVALID_REQUEST", "Exact product request required")
        data["product_request"] = product_request
    data["plan_digest"] = digest(data)
    with service.store.transaction("register_rod_offline_plan") as conn:
        prior = conn.execute("SELECT body FROM plans WHERE plan_id=?", (plan_id,)).fetchone()
        if prior:
            require(prior[0] == canonical_json(data), "IDEMPOTENCY_CONFLICT", "Registered Plan content differs")
            return ExecutionPlan.from_dict(data)
        require(conn.execute("SELECT state FROM dispatch_gate WHERE id=1").fetchone()[0] == "PAUSED"
                and conn.execute("SELECT run_id FROM slot WHERE id=1").fetchone()[0] is None,
                "DISPATCH_POLICY_MISMATCH", "Explicit idle PAUSED Project required")
        require(all(conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
                    for table in ("jobs", "plans", "grants", "runs", "receipts", "consumption")),
                "LIFECYCLE_PROVISIONING_CLOSED", "One new execution Project per prerequisite Plan")
        conn.execute("INSERT INTO jobs VALUES(?,?,?)", (job_id, 1, canonical_json(data["job_spec"])))
        conn.execute("INSERT INTO plans VALUES(?,?,?,?)", (plan_id, job_id, 1, canonical_json(data)))
    service.store._checkpoint("register_rod_offline_plan:after_commit")
    return ExecutionPlan.from_dict(data)


def inspect_registered(service, plan_id, expected_digest):
    """Existing public inspect_plan dispatch uses this bounded read-only projection."""
    with service.store.read() as conn:
        plan = document(conn, "plans", "plan_id", plan_id)
    original = dict(plan)
    claimed = original.pop("plan_digest", None)
    require(claimed == expected_digest == digest(original), "PLAN_STALE", "Stored exact Plan digest differs")
    context = service.context
    require(plan["backend_id"] == BACKEND and plan["plan_schema"] == SCHEMA
            and plan["project_instance_id"] == context.project_instance_id
            and plan["context_digest"] == context.context_digest,
            "PROJECT_IDENTITY_MISMATCH", "Registered Plan context or profile differs")
    require(plan["registration_scope"] == "OFFLINE_ONLY" and plan["execution_authorized"] is False,
            "PLAN_STALE", "Offline scope cannot be promoted")
    return {key: plan[key] for key in (
        "plan_id", "plan_digest", "job_id", "job_revision", "project_instance_id",
        "backend_id", "backend_version", "plan_schema", "profile", "resources",
        "validation_policy", "expires_at", "registration_scope", "execution_authorized", "live_dispatch")}


def revalidate_registered(service, plan_id, expected_digest, candidate, *, at_time):
    inspect_registered(service, plan_id, expected_digest)
    with service.store.read() as conn:
        plan = document(conn, "plans", "plan_id", plan_id)
    raw = plan["rod_preview"]
    revalidate_materialization(RodPlanPreview(canonical_json(raw)), candidate,
                               test_root=service.context.test_root,
                               expected_digest=raw["plan_digest"], project_id=service.context.project_id,
                               project_instance_id=service.context.project_instance_id, at_time=at_time)
    require(plan["input_manifest"] == [{"path": raw["input_path"], "size": len(candidate.input_bytes),
                                       "digest": candidate.to_dict()["input_digest"]}],
            "PLAN_STALE", "Registered input manifest differs")
    return ExecutionPlan.from_dict(plan)


def refuse_unqualified_execution():
    require(False, "ROD_EXECUTION_UNQUALIFIED", "Registered offline Plan has no qualified real authority or lifecycle")


def validate_registered_dat(service, plan_id, expected_digest, candidate, data, binding,
                            expected_binding, *, at_time):
    """Offline verifier uses only tolerances from the exact persisted reviewed Plan.

    Unlike the low-level parser, this API has no caller-controlled tolerance
    argument. Source binding remains an explicit isolated substitute; it is not a
    live artifact acquisition interface or a scientific Goal decision.
    """
    from .rod_dat import parse_bound_dat
    plan = revalidate_registered(service, plan_id, expected_digest, candidate,
                                 at_time=at_time).to_dict()
    require(type(expected_binding) is dict
            and expected_binding.get("plan_digest") == expected_digest
            and expected_binding.get("project_id") == service.context.project_id
            and expected_binding.get("project_instance_id") == service.context.project_instance_id
            and expected_binding.get("input_digest") == plan["input_manifest"][0]["digest"],
            "DAT_SOURCE_MISMATCH", "Expected evidence must name the registered Plan")
    result = parse_bound_dat(data, candidate, binding, expected_binding,
                             plan["rod_preview"]["tolerances"])
    return {**result, "registered_plan_id": plan_id, "registered_plan_digest": expected_digest,
            "verification_policy_digest": digest(plan["rod_preview"]["tolerances"])}
