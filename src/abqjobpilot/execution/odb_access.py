"""Metadata-only preflight for the existing Owner-native ODB operation."""

import json
from pathlib import Path
import re

from . import hil_odb, sanity_hil
from .models import ExecutionError, canonical_json, digest, fields, require, text
from .store import document

PREVIEW = "preview_hil_odb_access_v1"
SCHEMA = "sanity-odb-access-preview/1.0"


def accepted_run(conn, service, plan, args):
    run = document(conn, "runs", "run_id", args["run_id"])
    require(run["phase_attempt_id"] == args["phase_attempt_id"] and run["execution"] == "FINISHED"
            and run["reconciliation"] == "NONE", "ODB_SOURCE_UNTRUSTED", "Original terminal Attempt required")
    receipt = hil_odb._accepted(conn, service, plan, run)
    require(receipt["request_id"] == args["receipt_id"],
            "ODB_SOURCE_UNTRUSTED", "Original accepting Receipt differs")
    return run, receipt


def terminal_records(conn, run):
    events = conn.execute("SELECT body FROM events WHERE run_id=? "
                          "AND json_extract(body,'$.type')='STANDARD_RESULT_RECORDED' LIMIT 2",
                          (run["run_id"],)).fetchall()
    require(len(events) == 1, "ODB_SOURCE_UNTRUSTED", "Unique native terminal event required")
    refs = json.loads(events[0][0]).get("evidence_refs", [])
    require(len(refs) == 2, "ODB_SOURCE_UNTRUSTED", "Original Observation and Validation are required")
    row = conn.execute("SELECT observations.body,validations.body FROM observations JOIN validations USING(run_id) "
                       "WHERE run_id=? AND observation_id=? AND validation_id=?",
                       (run["run_id"], *refs)).fetchone()
    require(row is not None, "ODB_SOURCE_UNTRUSTED", "Original terminal evidence is missing")
    observation, validation = map(json.loads, row)
    require(observation.get("kind") == "STANDARD_TEXT"
            and observation.get("phase_attempt_id") == validation.get("phase_attempt_id") == run["phase_attempt_id"]
            and observation.get("observation_id") == refs[0] and validation.get("validation_id") == refs[1]
            and validation.get("evidence_refs") == [refs[0]],
            "ODB_SOURCE_UNTRUSTED", "Original terminal records differ from their Attempt")
    return observation, validation


def registered_identity(plan, run, receipt, observation, validation):
    source = observation.get("odb_source", {})
    artifact = source.get("artifact", {})
    sha256 = artifact.get("sha256")
    expected_path = Path(plan["engineering"]) / (plan["job_name"] + ".odb")
    require(run["backend_outcome"] == "COMPLETED"
            and run.get("odb_registration") == "BOUND_PENDING_CONTENT_VALIDATION"
            and validation.get("verdict") == "PASS"
            and validation.get("details", {}).get("observed_exit_success") is True
            and source.get("kind") == "CURRENT_ATTEMPT_ODB"
            and source.get("contract_version") == sanity_hil.plan_version(plan)
            and all(source.get(key) == run[key] for key in (
                "project_id", "project_instance_id", "plan_id", "plan_digest", "run_id", "phase_attempt_id", "grant_id"))
            and source.get("receipt_id") == receipt["request_id"]
            and source.get("input_sha256") == plan["input_manifest"][0]["digest"]
            and source.get("launch_intent_digest") == digest(run["launch_intent"])
            and artifact.get("path") == str(expected_path)
            and type(artifact.get("size")) is int and 0 < artifact["size"] <= sanity_hil.ODB_MAX_BYTES
            and isinstance(sha256, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", sha256),
            "ODB_SOURCE_UNTRUSTED", "Recorded ODB identity differs from its original provenance")
    return {**source, "observation_id": observation["observation_id"], "validation_id": validation["validation_id"]}


def _registered_source(conn, service, plan, args, decision):
    run, receipt = accepted_run(conn, service, plan, args)
    require(run["owner_id"] == decision["owner_id"], "ODB_SOURCE_UNTRUSTED", "Original Owner differs")
    grant = document(conn, "grants", "grant_id", run["grant_id"])
    require(grant["approval_source"] == digest(decision),
            "ODB_NOT_AUTHORIZED", "ODB scope is outside the original decision and Grant")
    source = registered_identity(plan, run, receipt, *terminal_records(conn, run))
    if "source_sha256" in args:
        require(args["source_sha256"] == source["artifact"]["sha256"],
                "ODB_SOURCE_UNTRUSTED", "Requested SHA-256 differs from the registered source")
    return source


def invoke(service, control, request):
    """Preserve the native receipt/replay path and screen new requests before ODB I/O."""
    action = request["action"]
    if action == hil_odb.STATUS:
        return hil_odb.invoke(service, control, request)
    if action == hil_odb.EXTRACT:
        try:
            return hil_odb.invoke(service, control, {**request, "action": hil_odb.STATUS})
        except ExecutionError as exc:
            if exc.code != "NOT_FOUND":
                raise

    args = request["arguments"]
    fields(args, hil_odb.REQUEST, ("source_sha256",) if action == PREVIEW else ())
    for key in ("run_id", "phase_attempt_id", "receipt_id"):
        text(args[key])
    require(args["script_version"] == sanity_hil.ODB_VERSION and args["selector"] == sanity_hil.ODB_SELECTOR,
            "ODB_FIELD_NOT_ALLOWED", "Only the fixed T3D2 final TIP U2 selection is supported")
    if "source_sha256" in args:
        require(isinstance(args["source_sha256"], str) and re.fullmatch(r"sha256:[0-9a-f]{64}", args["source_sha256"]),
                "INVALID_REQUEST", "A canonical registered SHA-256 is required")
    require(request["owner_id"] == service.store._session.owner_id,
            "ENDPOINT_IDENTITY_MISMATCH", "Current Owner required")
    with service.store.read() as conn:
        conn.execute("BEGIN")
        plan = document(conn, "plans", "plan_id", control.binding["plan_id"])
        control.check_plan(plan)
        decision = sanity_hil.require_decision(service, conn, plan, allow_odb=True)
        require(request["operation_key"] == plan["sanity"]["request_key"] + ".odb",
                "ODB_NOT_AUTHORIZED", "Only the exact one-read operation key is supported")
        source = _registered_source(conn, service, plan, args, decision)
        if action == PREVIEW:
            namespace = canonical_json([service.context.project_instance_id, service.client_namespace, hil_odb.EXTRACT])
            recorded = conn.execute("SELECT body FROM management_receipts WHERE namespace=? AND key=?",
                                    (namespace, request["operation_key"])).fetchone()
            return {"schema": SCHEMA, "status": "REGISTERED_METADATA_MATCHED",
                    "source": source, "file_bytes_checked": False, "execution_authorized_by_preview": False,
                    "recorded_attempt_state": json.loads(recorded[0])["state"] if recorded else None,
                    "script": plan["sanity"]["hil"]["odb"]["script"],
                    "script_version": sanity_hil.ODB_VERSION, "selector": args["selector"]}
    # The native path repeats authorization and checks the pinned file against the
    # original Observation inside the existing durable intent/dispatch boundary.
    return hil_odb.invoke(service, control, request)
