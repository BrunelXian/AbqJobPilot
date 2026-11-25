"""Read-only evidence projection for one independent native ODB extraction."""

from decimal import Decimal, DecimalException
import json
from pathlib import PureWindowsPath
import re
from types import SimpleNamespace

from . import hil_odb, odb_access, odb_history, odb_output_provenance, sanity_hil, standard_exit_policy as exits
from .job_process_observer import SOURCE
from .managed_process import POLICY as JOB_POLICY, check_completion
from .models import ExecutionError, digest, require
from .sanity_verdict import ATTEMPT_IDENTITY, _solver
from .store import open_existing_read_only

SCHEMA = "sanity-odb-extraction-verdict/1.0"
# One binary32 epsilon plus half of the last displayed DAT digit.
SINGLE_PRECISION_EPSILON = Decimal(2) ** -23
READ_ERRORS = (ExecutionError, OSError, ValueError, KeyError, TypeError, AttributeError)
NATIVE_INVALID_OUTPUT = hil_odb.NATIVE_ERRORS | {"ODB_OUTPUT_INVALID", "ODB_SIZE_INVALID", "INVALID_REQUEST"}


def _ledger(conn, service, plan, target, operation_id):
    key = plan["sanity"]["request_key"] + ".historical-odb"
    row = odb_history._lookup(conn, service, odb_history.EXTRACT, key)
    require(row is not None, "NOT_FOUND", "No original independent extraction Receipt")
    result = json.loads(row[1])
    require(result["operation_id"] == operation_id and result["operation_key"] == key
            and result["action"] == odb_history.EXTRACT
            and all(result[field] == value for field, value in target.items()),
            "EVIDENCE_IDENTITY_MISMATCH", "Extraction Receipt belongs to another operation or Attempt")
    grant_id = result["grant_id"]
    grant_row = conn.execute("SELECT body FROM management_grants WHERE grant_id=?", (grant_id,)).fetchone()
    approval_row = odb_history._lookup(conn, service, odb_history.ISSUE, key + "-review")
    consumption = conn.execute("SELECT operation_id FROM management_consumption WHERE grant_id=?",
                               (grant_id,)).fetchone()
    require(grant_row is not None and approval_row is not None and consumption is not None
            and consumption[0] == operation_id, "ODB_NOT_AUTHORIZED", "Original approval and consumption required")
    grant = json.loads(grant_row[0])
    approval = json.loads(approval_row[1])
    scope = grant["scope"]
    request = {**target, "grant_id": grant_id, "source_sha256": scope["source"]["artifact"]["sha256"],
               "script_version": scope["script_version"], "selector": scope["selector"]}
    human = {**target, **{field: grant[field] for field in odb_history.APPROVAL},
             "confirmation": "READ_ODB " + grant["approval_digest"]}
    require(grant["grant_id"] == grant_id and grant["kind"] == odb_history.SCHEMA
            and approval["grant"] == grant and approval["action"] == odb_history.ISSUE
            and approval["operation_key"] == key + "-review" and approval_row[0] == digest(human)
            and result["approval_digest"] == grant["approval_digest"] == odb_history.approval_digest(scope, grant)
            and row[0] == digest(request) and scope["max_reads"] == 1
            and scope["context_digest"] == service.context.context_digest
            and all(scope[field] == value for field, value in target.items())
            and scope["owner_id"] == result["owner_id"]
            and grant["approved_at"] <= result["recorded_at"] < grant["expires_at"],
            "ODB_NOT_AUTHORIZED", "Original independent approval or request binding differs")
    return result, scope


def _process(plan, run, result):
    process = result.get("process")
    if not process or result["state"] not in ("FAILED", "NATIVE_OUTPUT_RECORDED"):
        return "UNKNOWN", None, [], "EXTRACTION_PROCESS_EVIDENCE_UNAVAILABLE"
    expected = {**run, "owner_id": result["owner_id"],
                "owner_epoch": run["owner_epoch"] + (run["owner_id"] != result["owner_id"])}
    try:
        accounting = process["scope"]
        if (accounting.get("policy") == JOB_POLICY
                and accounting.get("source") == "QueryInformationJobObject.BasicAccounting"
                and accounting.get("creation_confirmed") is True
                and all(accounting.get(k) == expected[k] for k in (*ATTEMPT_IDENTITY, "owner_epoch"))
                and (accounting.get("breakaway_allowed") is True or accounting.get("kill_on_job_close") is False
                     or (type(accounting.get("limit_terminated_processes")) is int
                         and accounting["limit_terminated_processes"] > 0))):
            return "FAILED", None, [], "JOB_POLICY_VIOLATION"
        check_completion(accounting, expected)
        membership = process["membership_evidence"]
        records = process["exits"]
        require(membership["source"] == SOURCE and membership["scope_id"] == accounting["scope_id"]
                and membership["job_total_processes"] == accounting["total_processes"]
                and membership["unresolved_hint_pids"] == 0
                and len({(item["pid"], item["creation_time_100ns"]) for item in records}) == len(records)
                and all(type(item["pid"]) is int and item["pid"] > 0
                        and type(item["creation_time_100ns"]) is int and item["creation_time_100ns"] > 0
                        for item in records), exits.MEMBERSHIP_UNCERTAIN, "Extract Job accounting differs")
        materials = {PureWindowsPath(item["path"]): item for item in plan["runtime_binding"]["materials"]}
        critical = {"wrapper": plan["runtime_binding"]["cmd"]}
        for role, filename in (("launcher", "SMALauncher.exe"), ("program", "SMAPython.exe")):
            image = sanity_hil.INSTALL / "code/bin" / filename
            if PureWindowsPath(image) in materials:
                critical[role] = str(image)
        # This Receipt stores the handle-bound member identity on each exit row.
        view = {"process_records": records, "process_exits": records, "membership_evidence": membership,
                "all_observed_exited": True, "observation_unknowns": []}
        assessment = exits.assess(view, critical)
        require(assessment["reason"] != exits.MEMBERSHIP_UNCERTAIN,
                exits.MEMBERSHIP_UNCERTAIN, "Extract Job member identities or exits are incomplete")
    except READ_ERRORS as exc:
        return "UNKNOWN", None, [], exc.code if isinstance(exc, ExecutionError) else exits.MEMBERSHIP_UNCERTAIN
    critical_members = {entry["role"]: entry.get("critical_role") for entry in assessment["members"]}
    program = [item["exit_code"] for item in records if critical_members[item["role"]] == "program"]
    program_exit = program[0] if len(program) == 1 else None
    unresolved = [role for role in ("launcher", "program") if role not in critical]
    reason = assessment["reason"]
    if (unresolved or assessment["unverified_critical_roles"]) and reason != exits.CRITICAL_FAILURE:
        reason = "CRITICAL_EXIT_UNVERIFIED"
    return "VERIFIED", program_exit, records, reason


def _compare(context, plan, run, observation, validation, artifact):
    outcome, _ = _solver(context, plan, run, observation, validation)
    if outcome != "COMPLETED":
        return {"state": "INSUFFICIENT"}
    try:
        row = artifact["data"]["measurement"]
        dat = validation["details"]["measurement"]
        value, reference = Decimal(row["value_mm"]), Decimal(dat["raw_value"])
        difference = value - reference
        rounding = Decimal(1).scaleb(reference.as_tuple().exponent) / 2
        tolerance = abs(reference) * SINGLE_PRECISION_EPSILON + rounding
        matches = row["increment"] == dat["increment"] and abs(difference) <= tolerance
    except (DecimalException, KeyError, TypeError, ValueError):
        return {"state": "INSUFFICIENT"}
    return {"state": "AGREED" if matches else "MISMATCH", "dat_reference_mm": str(reference),
            "difference_mm": str(difference), "absolute_tolerance_mm": str(tolerance)}


def _data(context, plan, run, observation, validation, result, scope, grade, source):
    fixed = plan["sanity"]["hil"]["odb"]
    if any(result.get(field) != expected or scope.get(field) != expected for field, expected in (
            ("selector", sanity_hil.ODB_SELECTOR), ("script", fixed["script"]),
            ("script_version", sanity_hil.ODB_VERSION))):
        return "FAILED", "EXTRACTION_SELECTOR_OR_SCRIPT_MISMATCH", None, None
    if result.get("error_code") == "SOURCE_MISMATCH" or grade == "SOURCE_MISMATCH":
        return "FAILED", "SOURCE_MISMATCH", None, None
    if grade != "TRUSTED_SOURCE":
        return "INSUFFICIENT", grade, None, None
    if result["source"] != source or scope["source"] != source:
        return "FAILED", "SOURCE_MISMATCH", None, None
    if result["state"] not in ("FAILED", "NATIVE_OUTPUT_RECORDED") or not result.get("process"):
        return "INSUFFICIENT", "OUTPUT_NOT_COMMITTED", None, None
    if (error := result.get("output_observation_error")) is not None:
        state = "INSUFFICIENT" if error in ("INPUT_NOT_FOUND", "INPUT_READ_FAILED") else "FAILED"
        return state, error, None, None
    has_proof = "output_provenance" in result
    try:
        if has_proof:
            artifact = odb_output_provenance.verify(context, plan, result)
        else:
            artifact = hil_odb._read_result(odb_output_provenance.output_path(context, result))
    except READ_ERRORS as exc:
        code = exc.code if isinstance(exc, ExecutionError) else "ODB_OUTPUT_INVALID"
        if isinstance(exc, FileNotFoundError) or code == "INPUT_NOT_FOUND":
            return "INSUFFICIENT", "EXTRACTION_OUTPUT_MISSING", None, None
        if code == "INPUT_READ_FAILED":
            return "INSUFFICIENT", "EXTRACTION_OUTPUT_UNAVAILABLE", None, None
        return "FAILED", "ODB_OUTPUT_INVALID" if code == "INVALID_REQUEST" else code, None, None
    original = result.get("artifact")
    if original is not None and original != artifact:
        return "FAILED", "OUTPUT_DIGEST_MISMATCH", None, None
    comparison = _compare(context, plan, run, observation, validation, artifact)
    if comparison["state"] == "MISMATCH":
        return "FAILED", "DAT_COMPARISON_MISMATCH", artifact, comparison
    if not has_proof and (original is None or result["state"] != "NATIVE_OUTPUT_RECORDED"):
        return "INSUFFICIENT", "OUTPUT_NOT_BOUND_BY_OWNER", artifact, comparison
    if comparison["state"] != "AGREED":
        return "INSUFFICIENT", "DAT_COMPARISON_UNAVAILABLE", artifact, comparison
    return "VERIFIED", None, artifact, comparison


def read_verdict(context, plan, receipt, run, operation_id):
    """Project recorded evidence without an Owner, an executable, or ODB byte access."""
    require(sanity_hil.from_plan(plan) and plan["sanity"]["mode"] == "REAL" and run["simulation"] is False,
            "CAPABILITY_UNAVAILABLE", "A native Sanity Attempt is required")
    require(isinstance(operation_id, str) and re.fullmatch(r"op_[0-9a-f]{32}", operation_id),
            "INVALID_REQUEST", "A canonical extraction operation ID is required")
    target = {field: (receipt["request_id"] if field == "receipt_id" else run[field])
              for field in odb_history.TARGET}
    service = SimpleNamespace(context=context, client_namespace="product-client")
    with open_existing_read_only(context).read() as conn:
        conn.execute("BEGIN")
        result, scope = _ledger(conn, service, plan, target, operation_id)
        grade, _, source = odb_history.source_status(conn, service, plan, target)
        observation, validation = odb_access.terminal_records(conn, run)

    containment, program_exit, members, process_reason = _process(plan, run, result)
    integrity, data_reason, artifact, comparison = _data(
        context, plan, run, observation, validation, result, scope, grade, source)
    program = "UNKNOWN"
    if program_exit is not None and (program_exit != 0 or result.get("error_code") in NATIVE_INVALID_OUTPUT):
        program = "FAILED"
    elif program_exit == 0 and (artifact is not None
                                or (result["state"] == "NATIVE_OUTPUT_RECORDED" and result.get("artifact"))):
        program = "COMPLETED"

    qualification = "INSUFFICIENT"
    if program == "FAILED" or containment == "FAILED" or process_reason == exits.CRITICAL_FAILURE or integrity == "FAILED":
        qualification = "FAILED"
    elif program == "COMPLETED" and containment == "VERIFIED":
        if process_reason == exits.UNKNOWN and comparison and comparison["state"] == "AGREED":
            qualification = "REVIEW_REQUIRED"
        elif process_reason is None and integrity == "VERIFIED":
            qualification = "VERIFIED"

    return {"schema": SCHEMA, "read_only": True, **target, "operation_id": operation_id,
            "grant_id": result["grant_id"], "extraction_program_outcome": program,
            "program_exit_code": program_exit, "process_containment": containment,
            "extraction_qualification": qualification, "result_data_integrity": integrity,
            "reasons": [reason for reason in (process_reason, data_reason) if reason],
            "verified_exit_count": len(members),
            "nonzero_exit_count": sum(item["exit_code"] != 0 for item in members),
            "approved_selector": scope["selector"], "approved_script": scope["script"],
            "approved_source_sha256": scope["source"]["artifact"]["sha256"],
            "source_grade": grade, "source_bytes_checked": False, "output_observation": artifact,
            "output_provenance_grade": result.get("output_provenance", {}).get("grade") if artifact else None,
            "numeric_comparison": comparison,
            "recorded": {field: result.get(field) for field in ("state", "error_code", "native_hil_qualification")}}
