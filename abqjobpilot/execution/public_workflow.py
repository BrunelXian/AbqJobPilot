"""Small TEST_ONLY public plan inspection and explicit artifact validation adapters."""

from .models import canonical_json, digest, require, text
from .process_contract import BACKEND, REQUIRED_ROLES
from .process_validation import validate_process_artifact
from .store import document, needs_reconciliation, update_run

VALIDATE = "validate_process_artifact"
VALIDATION_SCOPE = ("run_id", "expected_run_revision", "plan_id", "plan_digest")


def inspect_plan(service, context, plan_id, expected_digest):
    service._context(context)
    text(plan_id); text(expected_digest)
    with service.store.read() as connection:
        plan = document(connection, "plans", "plan_id", plan_id)
    require(digest({k: v for k, v in plan.items() if k != "plan_digest"}) == plan["plan_digest"] == expected_digest,
            "PLAN_STALE", "Fixed plan identity differs from operator handoff")
    require(plan["context_digest"] == context.context_digest and plan["project_instance_id"] == context.project_instance_id,
            "PROJECT_IDENTITY_MISMATCH", "Plan belongs to another experiment")
    require(plan["backend_id"] == BACKEND and plan["backend_version"] == 1,
            "UNSUPPORTED_EVIDENCE_POLICY", "Public inspection supports the fixed TEST_ONLY process plan")
    fixture = plan["process_fixture"]
    return {"inspection_version": "test-plan-inspection-v1", "scope": "TEST_ONLY",
            "project_instance_id": context.project_instance_id, "context_digest": context.context_digest,
            **{k: plan[k] for k in ("plan_id", "plan_digest", "job_id", "job_revision", "backend_id", "backend_version",
                                   "action", "phases", "resources", "validation_policy", "expires_at")},
            "scenario": fixture["scenario"], "membership_contract": fixture["membership_contract"],
            **({'managed_scope':fixture['managed_scope'],'required_roles_meaning':'KEY_ROLES_NOT_DESCENDANT_COMPLETENESS'} if fixture.get('managed_scope') else {}),
            "required_roles": fixture["required_roles"], "fixture_digest": fixture["fixture_digest"],
            "interpreter_digest": fixture["interpreter_digest"], "image_digest": fixture["image_digest"],
            "input_dependencies": [{"ref": "input:" + str(i), "digest": v["digest"], "size": v["size"]}
                                   for i, v in enumerate(plan["input_manifest"])],
            "output_reference": "run:process_fixture/result.json", "overwrite": False,
            "configuration_digest": plan["config_snapshot"]["digest"],
            "inspection_basis": "stored_fixed_plan_digest_only_not_current_input_or_permission_preflight"}


def validation_scope(connection, run_id):
    run = document(connection, "runs", "run_id", run_id)
    return {"run_id": run_id, "expected_run_revision": run["revision"],
            "plan_id": run["plan_id"], "plan_digest": run["plan_digest"]}


def validate_recorded(service, connection, request, operation_id, gate):
    run = document(connection, "runs", "run_id", request["run_id"])
    require(validation_scope(connection, run["run_id"]) == {k: request[k] for k in VALIDATION_SCOPE},
            "STALE_PREVIEW", "Run or plan changed before explicit validation")
    require(run["backend_id"] == BACKEND and run["execution"] == "FINISHED"
            and not needs_reconciliation(run) and run["exit_verification"] == "VERIFIED",
            "VALIDATION_PRECONDITION_FAILED", "Only a finished, exit-verified fixed process Run may be revalidated")
    roles = set(REQUIRED_ROLES)
    require(len(run["process_records"]) == len(run["process_exits"]) == 4
            and {v["role"] for v in run["process_records"]} == {v["role"] for v in run["process_exits"]} == roles
            and all(v["exit_source"] == "retained_windows_handle" and type(v["exit_code"]) is int
                    and any(all(v[k] == p[k] for k in ("role", "pid", "creation_time_100ns"))
                            for p in run["process_records"]) for v in run["process_exits"]),
            "VALIDATION_PRECONDITION_FAILED", "Required recorded process exit evidence is incomplete")
    plan = document(connection, "plans", "plan_id", run["plan_id"])
    require(plan["backend_id"] == BACKEND and type(plan["backend_version"]) is int and plan["backend_version"] == 1
            and plan["context_digest"] == service.context.context_digest
            and plan["validation_policy"] == "process-fixture-result-v1"
            and digest({k: v for k, v in plan.items() if k != "plan_digest"}) == run["plan_digest"],
            "PLAN_STALE", "Original fixed validation policy or plan differs")
    observation, validation = validate_process_artifact(service.context, plan, run)
    validation.update(source="explicit_client_validation", operation_id=operation_id)
    connection.execute("INSERT INTO observations VALUES(?,?,?)", (observation["observation_id"], run["run_id"], canonical_json(observation)))
    connection.execute("INSERT INTO validations VALUES(?,?,?)", (validation["validation_id"], run["run_id"], canonical_json(validation)))
    refs = [observation["observation_id"], validation["validation_id"]]
    updated = update_run(connection, run, "VALIDATION_RECORDED", evidence_refs=refs,
                         artifact_validation={"PASS": "VALID", "FAIL": "INVALID", "UNKNOWN": "UNKNOWN"}[validation["verdict"]],
                         validation_scope="simulation")
    return refs, {"run_id": run["run_id"], "run_revision": updated["revision"], "validation_id": validation["validation_id"],
                  "verdict": validation["verdict"], "gate": gate}
