"""Read-only review of one accepted Sanity HIL Attempt."""

import json
from collections import Counter
from pathlib import Path

from . import sanity_hil, standard_exit_policy as exits
from .job_process_observer import MAX_RECORD_BYTES, SOURCE
from .job_provenance import MAX_PROVENANCE_BYTES, POLICY as PROVENANCE_POLICY
from .managed_process import POLICY as JOB_POLICY, check_completion
from .models import ExecutionError, bytes_digest, require
from .paths import confined
from .sanity_model import MODEL_TITLE, file_bytes
from .standard_text import bound_terminal_text, displacement, terminal_outcome
from .store import document, open_existing_read_only

SCHEMA = "sanity-execution-verdict/1.0"
ATTEMPT_IDENTITY = ("project_instance_id", "run_id", "plan_digest", "phase_attempt_id", "owner_id")
READ_ERRORS = (ExecutionError, OSError, ValueError, KeyError, TypeError, AttributeError)


def _records(context, plan, receipt, run):
    """Read the bound Grant, consumption, and terminal records in one snapshot."""
    from .product_standard import scope

    with open_existing_read_only(context).read() as db:
        db.execute("BEGIN")
        current = document(db, "runs", "run_id", run["run_id"])
        require(current["revision"] == run["revision"], "STATE_CONFLICT", "Run changed during the review")
        grant = document(db, "grants", "grant_id", run["grant_id"])
        usage = db.execute("SELECT run_id FROM consumption WHERE grant_id=?", (run["grant_id"],)).fetchone()
        require(receipt["request_status"] == "ACCEPTED" and receipt["run_id"] == run["run_id"]
                and receipt["job_id"] == plan["job_id"] and receipt["idempotency_key"] == plan["sanity"]["request_key"]
                and usage is not None and usage[0] == run["run_id"]
                and grant["grant_id"] == run["grant_id"] and grant["max_runs"] == 1
                and grant["plan_id"] == plan["plan_id"] and grant["plan_digest"] == run["plan_digest"]
                and grant["project_id"] == context.project_id and grant["product_scope"] == scope(plan)
                and grant["project_instance_id"] == context.project_instance_id
                and grant["context_digest"] == context.context_digest and grant["approval_owner"] == run["owner_id"],
                "EVIDENCE_IDENTITY_MISMATCH", "Receipt, Grant or original consumption differs")
        rows = [db.execute("SELECT body FROM " + table + " WHERE run_id=? LIMIT 2", (run["run_id"],)).fetchall()
                for table in ("observations", "validations")]
        terminal = db.execute("SELECT body FROM events WHERE run_id=? "
                              "AND json_extract(body, '$.type')='STANDARD_RESULT_RECORDED' LIMIT 2",
                              (run["run_id"],)).fetchall()
    if any(len(records) != 1 for records in (*rows, terminal)):
        return None
    obs, val = (json.loads(records[0][0]) for records in rows)
    event = json.loads(terminal[0][0])
    require(all(record["run_id"] == run["run_id"] and record["phase_attempt_id"] == run["phase_attempt_id"]
                for record in (obs, val))
            and obs["kind"] == "STANDARD_TEXT" and val["evidence_refs"] == [obs["observation_id"]]
            and event["evidence_refs"] == [obs["observation_id"], val["validation_id"]]
            and val["scope"] == "current_run_measurement_only"
            and val["policy_id"] == plan["validation_policy"] and val["details"]["artifacts"] == obs["artifacts"],
            "EVIDENCE_IDENTITY_MISMATCH", "Observation or Validation differs from the original Attempt")
    return obs, val


def _solver(context, plan, run, obs, val):
    from ..sanity_admission import validate

    try:
        validate(context, plan, live=False)
        name = "." + plan["job_name"] + ".intent.json"
        path = confined(context.test_root, Path(plan["engineering"]) / name)
        intent = json.loads(file_bytes(path, 8192))
        require(intent == run["launch_intent"] and all(intent[k] == run[k] for k in ATTEMPT_IDENTITY)
                and intent["output_key"] == plan["output_key"],
                "EVIDENCE_IDENTITY_MISMATCH", "Original launch intent differs")
        raw = bound_terminal_text(context, plan, obs, intent, allow_partial=True)
        outcome = terminal_outcome(raw)
        if outcome == "FAILED":
            return outcome, "SOLVER_FAILURE_TEXT_VERIFIED"
        if outcome == "COMPLETED":
            measured = displacement(raw["dat"], plan["sanity"]["selector"], terminal=True, model_title=MODEL_TITLE)
            require(measured == val["details"]["measurement"]
                    and run["solver_conclusion"] == val["details"]["solver"] == "COMPLETED_TEXT_EVIDENCE",
                    "EVIDENCE_CHANGED", "Recomputed text outcome or measurement differs")
            return outcome, None
        return outcome, "SOLVER_TEXT_INCONCLUSIVE"
    except READ_ERRORS as exc:
        return "UNKNOWN", exc.code if isinstance(exc, ExecutionError) else "SOLVER_EVIDENCE_UNAVAILABLE"


def _recorded_exit_classes(archive, details, derived):
    """Retain witnessed Owner classifications only from a consistent pinned archive."""
    recorded = archive.get("exit_semantics")
    if recorded is None:
        return derived["members"]
    require(recorded["policy"] == exits.POLICY and exits.summary(recorded) == details.get("exit_semantics")
            and recorded["unverified_critical_roles"] == derived["unverified_critical_roles"],
            "EXIT_ASSESSMENT_INCONSISTENT", "Stored exit assessment differs from Run evidence")
    baseline = {entry["role"]: entry for entry in derived["members"]}
    codes = {entry["role"]: entry["exit_code"] for entry in archive["process_exits"]}
    capture = archive.get("process_provenance", {})
    provenance = {entry["role"]: entry for entry in capture.get("members", [])}
    members = recorded["members"]
    require(len(members) == len(baseline) and {entry["role"] for entry in members} == baseline.keys()
            and dict(Counter(entry["classification"] for entry in members)) == recorded["counts"],
            "EXIT_ASSESSMENT_INCONSISTENT", "Stored exit assessment has different membership")
    for entry in members:
        role = entry["role"]
        if entry == baseline[role]:
            continue
        source = provenance.get(role, {})
        require(capture.get("policy") == PROVENANCE_POLICY
                and baseline[role]["classification"] == exits.UNKNOWN and codes[role] != 0
                and entry["classification"] in (exits.AUXILIARY_EXPECTED_NONZERO, exits.AUXILIARY_UNEXPECTED_NONZERO)
                and source.get("command_status") == "HANDLE_OBSERVED" and source.get("command_line")
                and source.get("parent_status") == "VERIFIED_JOB_LIFETIME"
                and source.get("parent", {}).get("role") == entry.get("caller_role")
                and all(entry.get(k) for k in ("operation", "caller_role", "output_digest", "independent_digest")),
                "EXIT_ASSESSMENT_INCONSISTENT", "Archived auxiliary classification has no bound witness")
    return members


def _process(context, plan, run, details):
    scope = run.get("managed_scope") or {}
    if (scope == details.get("managed_scope") and scope.get("policy") == JOB_POLICY
            and scope.get("source") == "QueryInformationJobObject.BasicAccounting"
            and scope.get("creation_confirmed") is True
            and all(scope.get(k) == run[k] for k in (*ATTEMPT_IDENTITY, "owner_epoch"))
            and (scope.get("breakaway_allowed") is True or scope.get("kill_on_job_close") is False
                 or (type(scope.get("limit_terminated_processes")) is int and scope["limit_terminated_processes"] > 0))):
        return "FAILED", "JOB_POLICY_VIOLATION", False

    try:
        membership = run["membership_evidence"]
        require(membership is not None and membership == details.get("membership_evidence"),
                exits.MEMBERSHIP_UNCERTAIN, "Original Run has no matching pinned membership evidence")
        name = "process-membership.json"
        path = confined(context.test_root, Path(context.runtime_root) / "standard_runs" / run["run_id"] / name)
        raw = file_bytes(path, MAX_RECORD_BYTES + MAX_PROVENANCE_BYTES + exits.MAX_EVIDENCE_BYTES + 4096)
        archive = json.loads(raw)
        require(membership["artifact"] == {"logical_ref": "run-output:" + name,
                                          "digest": bytes_digest(raw), "size": len(raw)}
                and archive["membership_evidence"] == {k: v for k, v in membership.items() if k != "artifact"}
                and all(archive[k] == run[k] for k in ATTEMPT_IDENTITY),
                "PROCESS_EVIDENCE_CHANGED", "Original process archive differs from its Run")
        derived = exits.assess(archive, sanity_hil.critical_images(plan))
        critical_failed = bool(derived["counts"].get(exits.CRITICAL_FAILURE))
    except READ_ERRORS as exc:
        return "UNKNOWN", exc.code if isinstance(exc, ExecutionError) else exits.MEMBERSHIP_UNCERTAIN, False

    try:
        check_completion(scope, run)
        require(run["managed_completion"] == "COMMITTED_EMPTY_SCOPE" and details["managed_scope"] == scope
                and membership["source"] == SOURCE and membership["scope_id"] == scope["scope_id"]
                and membership["job_total_processes"] == scope["total_processes"]
                and derived["reason"] != exits.MEMBERSHIP_UNCERTAIN,
                exits.MEMBERSHIP_UNCERTAIN, "Job accounting and member evidence do not close")
    except READ_ERRORS as exc:
        return "UNKNOWN", exc.code if isinstance(exc, ExecutionError) else exits.MEMBERSHIP_UNCERTAIN, critical_failed

    try:
        members = _recorded_exit_classes(archive, details, derived)
        codes = {entry["role"]: entry["exit_code"] for entry in archive["process_exits"]}
        unexpected = any(entry["classification"] == exits.AUXILIARY_UNEXPECTED_NONZERO for entry in members)
        unknown_nonzero = any(entry["classification"] == exits.UNKNOWN and codes[entry["role"]] != 0 for entry in members)
        reason = next((code for present, code in (
            (critical_failed, exits.CRITICAL_FAILURE),
            (unexpected, exits.AUXILIARY_UNEXPECTED_NONZERO),
            (unknown_nonzero or derived["unverified_critical_roles"], exits.UNKNOWN),
        ) if present), None)
        if "exit_semantics" in archive:
            stored = archive["exit_semantics"]
            require(stored["reason"] == reason and stored["accepted"] is (reason is None),
                    "EXIT_ASSESSMENT_INCONSISTENT", "Archived exit conclusion differs from the member results")
    except READ_ERRORS:
        return "VERIFIED", exits.CRITICAL_FAILURE if critical_failed else "EXIT_ASSESSMENT_INCONSISTENT", critical_failed

    if derived["unverified_critical_roles"] and reason == exits.UNKNOWN:
        return "VERIFIED", "CRITICAL_EXIT_UNVERIFIED", False
    return "VERIFIED", reason, critical_failed or unexpected


def read_verdict(context, plan, receipt, run):
    require(sanity_hil.from_plan(plan) and plan["sanity"]["mode"] == "REAL" and run["simulation"] is False,
            "CAPABILITY_UNAVAILABLE", "The verdict view requires a REAL Sanity HIL Attempt")
    report = {
        "schema": SCHEMA, "read_only": True,
        "project_id": context.project_id, "project_instance_id": context.project_instance_id,
        "plan_id": plan["plan_id"], "plan_digest": plan["plan_digest"],
        "run_id": run["run_id"], "attempt_id": run["phase_attempt_id"], "receipt_id": receipt["request_id"],
        "solver_outcome": "UNKNOWN", "process_containment": "UNKNOWN", "execution_qualification": "INSUFFICIENT",
        "reasons": ["TERMINAL_EVIDENCE_UNAVAILABLE"],
        "recorded": {k: run.get(k) for k in ("execution", "backend_outcome", "result_reason", "solver_conclusion")},
    }
    if run["launch_state"] != "PROCESS_OBJECT_RETURNED" or run.get("execution_phase") != "EVIDENCE_RECORDED":
        return report
    records = _records(context, plan, receipt, run)
    if records is None:
        return report
    obs, val = records
    solver, solver_reason = _solver(context, plan, run, obs, val)
    containment, process_reason, failed_exit = _process(context, plan, run, val["details"])
    qualification = "INSUFFICIENT"
    reasons = [reason for reason in (solver_reason, process_reason) if reason]
    ready = (solver == "COMPLETED" and containment == "VERIFIED" and val["verdict"] == "PASS"
             and run["execution"] == "FINISHED" and run["reconciliation"] == "NONE")
    if solver == "FAILED" or containment == "FAILED" or failed_exit:
        qualification = "FAILED"
    elif ready and process_reason == exits.UNKNOWN:
        qualification = "REVIEW_REQUIRED"
    elif ready and process_reason is None and run["backend_outcome"] == "COMPLETED" and val["details"].get("observed_exit_success") is True:
        qualification = "VERIFIED"
    elif not reasons:
        reasons = ["NATIVE_QUALIFICATION_UNMET"]
    report["recorded"].update(validation_id=val["validation_id"], validation_verdict=val["verdict"],
                              validation_scope=val["scope"], observation_id=obs["observation_id"])
    return {**report, "solver_outcome": solver, "process_containment": containment,
            "execution_qualification": qualification, "reasons": reasons}
