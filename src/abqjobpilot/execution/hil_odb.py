"""Owner-only ODB provenance and one separately approved native extraction."""

from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import time

from . import sanity_hil
from .managed_process import ManagedScope, check_completion
from .models import ExecutionError, bytes_digest, canonical_json, digest, fields, identifier, now, require, text
from .paths import confined
from .sanity_model import hold_candidate
from .standard_backend import process_environment
from .standard_process import Observer, check_host
from .store import document

EXTRACT = "extract_hil_odb_v1"
STATUS = "read_hil_odb_receipt_v1"
REQUEST = ("run_id", "phase_attempt_id", "receipt_id", "script_version", "selector")
MAX_RESULT = 4096
NATIVE_ERRORS = {"ODB_FIELD_MISSING", "ODB_FINAL_FRAME_MISSING", "ODB_COMPONENT_MISSING",
                 "ODB_REGION_AMBIGUOUS", "ODB_NODE_MISMATCH", "ODB_NONFINITE"}


def _pin(pins, path, maximum):
    from ..abaqus_preview.inputs import _open_pinned

    stream = pins.enter_context(_open_pinned(path))
    info = os.fstat(stream.fileno())
    require(0 < info.st_size <= maximum, "ODB_SIZE_INVALID", "Artifact exceeds the approved byte range")
    return stream, info


def _fingerprint(path, stream, maximum):
    stream.seek(0)
    hasher = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        require(size <= maximum, "ODB_SIZE_INVALID", "Artifact exceeded the approved byte range")
        hasher.update(chunk)
    info = os.fstat(stream.fileno())
    require(info.st_size == size, "ODB_SOURCE_UNTRUSTED", "Artifact size changed")
    return {"path": str(path), "size": size, "device": info.st_dev, "inode": info.st_ino,
            "mtime_ns": info.st_mtime_ns, "sha256": "sha256:" + hasher.hexdigest()}


def _source_pin(pins, context, plan, run):
    root = Path(plan["engineering"])
    path = confined(context.test_root, root / (plan["job_name"] + ".odb"))
    intent_path = confined(context.test_root, root / ("." + plan["job_name"] + ".intent.json"), exists=True)
    intent_file, _ = _pin(pins, intent_path, 8192)
    try:
        intent = json.load(intent_file)
    except (ValueError, UnicodeError) as exc:
        raise ExecutionError('ODB_SOURCE_UNTRUSTED', 'Invalid original launch intent') from exc
    require(intent == run.get("launch_intent")
            and all(intent.get(key) == run[key] for key in (
                "run_id", "phase_attempt_id", "plan_digest", "owner_id", "project_instance_id"))
            and intent.get("state") == "START_INTENT" and intent.get("output_key") == plan["output_key"],
            "ODB_SOURCE_UNTRUSTED", "Original bound launch intent required")
    require(path.is_file(), "ODB_SOURCE_NOT_FOUND", "No ODB was produced for the exact attempt")
    stream, _ = _pin(pins, path, sanity_hil.ODB_MAX_BYTES)
    require(min(path.stat().st_ctime_ns, path.stat().st_mtime_ns) >= intent["intent_at_ns"],
            "ODB_SOURCE_UNTRUSTED", "ODB predates the attempt")
    return path, stream


def _accepted(conn, service, plan, run):
    namespace = canonical_json([service.context.project_instance_id, service.client_namespace, "submit"])
    row = conn.execute(
        "SELECT receipts.body,grants.body FROM receipts JOIN consumption USING(run_id) "
        "JOIN grants ON consumption.grant_id=grants.grant_id "
        "WHERE receipts.namespace=? AND receipts.run_id=? AND consumption.grant_id=?",
        (namespace, run["run_id"], run["grant_id"])).fetchone()
    require(row is not None, "ODB_SOURCE_UNTRUSTED", "Original accepted Receipt and Grant consumption required")
    receipt, grant = map(json.loads, row)
    from .product_standard import scope

    require(receipt["request_status"] == "ACCEPTED" and receipt["job_id"] == run["job_id"] == plan["job_id"]
            and receipt["idempotency_key"] == plan["sanity"]["request_key"]
            and grant["grant_kind"] == sanity_hil.GRANT_KIND and grant["max_runs"] == 1
            and grant["product_scope"] == scope(plan) and grant["approval_owner"] == run["owner_id"]
            and run["project_id"] == service.context.project_id == plan["sanity"]["project_id"]
            and run["project_instance_id"] == service.context.project_instance_id == plan["project_instance_id"]
            and all(run[key] == plan[key] for key in ("plan_id", "plan_digest", "backend_id"))
            and run["attempt_no"] == 1 and run["simulation"] is False
            and run["launch_state"] == "PROCESS_OBJECT_RETURNED",
            "ODB_SOURCE_UNTRUSTED", "Receipt, Plan, exhausted Grant or native Attempt differs")
    return receipt


def register(pins, conn, service, plan, run):
    """Called only in the existing native successful terminal transaction."""
    intent_time = run.get("launch_intent", {}).get("intent_at_ns")
    if sanity_hil.external(plan):
        require(type(intent_time) is int, "ODB_SOURCE_UNTRUSTED", "Original launch time required")
    pins.enter_context(hold_candidate(plan))
    decision = sanity_hil.require_activation(plan, service=service, connection=conn,
                                             authorized_at=None if intent_time is None else intent_time // 1_000_000_000)
    if sanity_hil.plan_version(plan) == sanity_hil.HIL_003_VERSION:
        require(decision["allow_odb"] is True, "ODB_NOT_AUTHORIZED", "NO_ODB prevents source registration")
    return _source(pins, conn, service, plan, run)[0]


def _source(pins, conn, service, plan, run):
    receipt = _accepted(conn, service, plan, run)
    path, stream = _source_pin(pins, service.context, plan, run)
    artifact = _fingerprint(path, stream, sanity_hil.ODB_MAX_BYTES)
    return {"contract_version": sanity_hil.plan_version(plan), "kind": "CURRENT_ATTEMPT_ODB",
            **{key: run[key] for key in ("project_id", "project_instance_id", "plan_id", "plan_digest",
                                        "run_id", "phase_attempt_id", "grant_id")},
            "receipt_id": receipt["request_id"], "input_sha256": plan["input_manifest"][0]["digest"],
            "launch_intent_digest": digest(run["launch_intent"]), "artifact": artifact}, stream


def _bound_source(pins, conn, service, plan, args, decision):
    from ..sanity_admission import validate

    run = document(conn, "runs", "run_id", args["run_id"])
    require(run["phase_attempt_id"] == args["phase_attempt_id"]
            and run["owner_id"] == decision["owner_id"]
            and run["execution"] == "FINISHED" and run["backend_outcome"] == "COMPLETED"
            and run["reconciliation"] == "NONE" and run["managed_completion"] == "COMMITTED_EMPTY_SCOPE"
            and run["solver_conclusion"] == "COMPLETED_TEXT_EVIDENCE"
            and run.get("odb_registration") == "BOUND_PENDING_CONTENT_VALIDATION",
            "ODB_SOURCE_UNTRUSTED", "Expected the approved native terminal Run and Attempt")
    check_completion(run["managed_scope"], run)
    pins.enter_context(hold_candidate(plan))
    validate(service.context, plan, live=False)
    source, pinned = _source(pins, conn, service, plan, run)
    require(source["receipt_id"] == args["receipt_id"], "ODB_SOURCE_UNTRUSTED", "Accepting Receipt differs")
    rows = conn.execute("SELECT body FROM events WHERE run_id=? "
                        "AND json_extract(body,'$.type')='STANDARD_RESULT_RECORDED' LIMIT 2",
                        (run["run_id"],)).fetchall()
    require(len(rows) == 1, "ODB_SOURCE_UNTRUSTED", "Exact terminal event is missing")
    refs = json.loads(rows[0][0])["evidence_refs"]
    require(len(refs) == 2, "ODB_SOURCE_UNTRUSTED", "Exact terminal Observation and Validation required")
    observation_id, validation_id = refs
    obs_row = conn.execute("SELECT body FROM observations WHERE observation_id=?", (observation_id,)).fetchone()
    val_row = conn.execute("SELECT body FROM validations WHERE validation_id=?", (validation_id,)).fetchone()
    require(obs_row is not None and val_row is not None, "ODB_SOURCE_UNTRUSTED", "Terminal evidence is missing")
    obs, val = json.loads(obs_row[0]), json.loads(val_row[0])
    require(all(item["run_id"] == run["run_id"] and item["phase_attempt_id"] == run["phase_attempt_id"]
                for item in (obs, val))
            and obs["kind"] == "STANDARD_TEXT" and obs.get("odb_source") == source
            and val["verdict"] == "PASS" and val["evidence_refs"] == [observation_id]
            and val["details"]["observed_exit_success"] is True,
            "ODB_SOURCE_UNTRUSTED", "ODB identity or original completion evidence changed")
    grant = document(conn, "grants", "grant_id", run["grant_id"])
    require(grant["approval_source"] == digest(decision),
            "ODB_NOT_AUTHORIZED", "Extraction must refer to the original decision and Grant")
    return run, {**source, "observation_id": observation_id, "validation_id": validation_id}, pinned


def call_data(plan, output, source, expires_at):
    binding = plan["sanity"]["hil"]
    runtime = plan["runtime_binding"]
    cmd, entry = runtime["cmd"], runtime["entry"]
    script = binding["odb"]["script"]["path"]
    result = output / "u2.json"
    values = (cmd, entry, script, source["artifact"]["path"], str(result))
    require(all(not any(character in value for character in '"%!&|<>^\r\n') for value in values),
            "OUTPUT_SCOPE_VIOLATION", "Non-literal command path rejected")
    line = f'"{cmd}" /d /s /c ""{entry}" python "{script}" "{values[3]}" "{result}""'
    return {"application": cmd, "command_line": line, "cwd": str(output),
            "environment": {**process_environment(output), **binding["environment"]},
            "start_not_after": min(now() + 30, expires_at)}


def _read_result(path):
    with ExitStack() as pins:
        stream, _ = _pin(pins, path, MAX_RESULT)
        output = stream.read(MAX_RESULT + 1)
    try:
        data = json.loads(output)
        if type(data) is dict and set(data) == {"error"} and data["error"] in NATIVE_ERRORS:
            raise ExecutionError(data["error"], "Approved ODB selector could not be resolved")
        fields(data, ("measurement",))
        row = data["measurement"]
        fields(row, ("node", "increment", "step_time", "value_mm"))
        require(type(row["node"]) is int and row["node"] == 2
                and type(row["increment"]) is int and row["increment"] > 0
                and type(row["step_time"]) is str and type(row["value_mm"]) is str
                and len(row["step_time"]) <= 32 and len(row["value_mm"]) <= 32
                and math.isclose(float(row["step_time"]), 1, rel_tol=0.0, abs_tol=1e-9)
                and math.isfinite(float(row["value_mm"])),
                "ODB_OUTPUT_INVALID", "Unexpected native measurement")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ExecutionError("ODB_OUTPUT_INVALID", "Malformed native script output") from exc
    return {"format": "JSON", "size": len(output), "sha256": bytes_digest(output), "data": data}


def _run_script(service, plan, run, source, operation_id, expires_at):
    with service.store.read() as conn:
        sanity_hil.require_decision(service, conn, plan, allow_odb=True)
    config = service._standard_backend.config
    config.verify()
    require(check_host(config)["eligible"], "HOST_UNVERIFIED", "Exact Owner launch environment required")
    root = Path(service.context.runtime_root) / "standard_runs" / run["run_id"] / operation_id
    output = confined(service.context.test_root, root)
    output.mkdir(exist_ok=False)
    for name in ("home/AppData/Roaming", "home/AppData/Local", "tmp"):
        (output / name).mkdir(parents=True, exist_ok=True)
    call = call_data(plan, output, source, expires_at)
    script = Path(plan["sanity"]["hil"]["odb"]["script"]["path"])
    scope = ManagedScope(run)  # Sanity already uses non-breakaway kill-on-close.
    child = observer = None
    try:
        # Keep diagnostics bounded by discarding stdout/stderr. The script's
        # structured result is the only reportable data channel.
        with ExitStack() as pins, open("NUL", "wb") as discard:
            pinned, info = _pin(pins, script, 16384)
            identity = {"path": str(script), "size": info.st_size,
                        "digest": bytes_digest(pinned.read(16385))}
            require(identity == plan["sanity"]["hil"]["odb"]["script"],
                    "PLAN_STALE", "Fixed extractor script changed")
            deadline = time.monotonic() + min(sanity_hil.ODB_SECONDS, max(0, expires_at - now()))
            require(time.monotonic() < deadline, "HIL_APPROVAL_EXPIRED", "No time left for extraction")
            child = scope.create_standard(call, discard, discard)
            observer = Observer(child)
            while time.monotonic() < deadline:
                view = observer.sample()
                require(observer.in_scope(scope), "ODB_OUTCOME_UNKNOWN", "Incomplete managed membership")
                completion = scope.query()
                if completion["state"] == "EMPTY_CONFIRMED":
                    break
                time.sleep(0.05)
            else:
                raise ExecutionError("ODB_OUTCOME_UNKNOWN", "Extraction timeout without proved exit")
            check_completion(completion, run)
            view = observer.sample()
            require(view["all_observed_exited"] and not view["observation_unknowns"] and observer.in_scope(scope),
                    "ODB_OUTCOME_UNKNOWN", "Unknown extractor process exit")
            process = {"scope": completion, "exits": view["process_exits"]}
            if not view["process_exits"] or any(item["exit_code"] != 0 for item in view["process_exits"]):
                return {"state": "FAILED", "error_code": "ODB_EXTRACTION_FAILED", "process": process}
            try:
                artifact = _read_result(output / "u2.json")
            except (ExecutionError, OSError) as exc:
                code = exc.code if isinstance(exc, ExecutionError) else "ODB_OUTPUT_INVALID"
                return {"state": "FAILED", "error_code": code, "process": process}
            return {"state": "NATIVE_OUTPUT_RECORDED", "artifact": artifact, "process": process}
    finally:
        if observer is not None:
            observer.close()
        if child is not None:
            child.close()
        scope.close()


def invoke(service, control, request):
    args = request["arguments"]
    fields(args, REQUEST)
    for key in ("run_id", "phase_attempt_id", "receipt_id"):
        text(args[key])
    require(args["script_version"] == sanity_hil.ODB_VERSION and args["selector"] == sanity_hil.ODB_SELECTOR,
            "ODB_FIELD_NOT_ALLOWED", "Only the fixed T3D2 final TIP U2 selection is supported")
    store = service.store
    session = store._session
    namespace = canonical_json([service.context.project_instance_id, service.client_namespace, EXTRACT])
    key = request["operation_key"]
    fingerprint = digest(args)

    with store.read() as conn:
        prior = conn.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?",
                             (namespace, key)).fetchone()
    if prior:
        require(prior[0] == fingerprint, "IDEMPOTENCY_CONFLICT", "Extraction key already has different scope")
        return {"replayed": True, "receipt": json.loads(prior[1])}
    require(request["action"] == EXTRACT, "NOT_FOUND", "No original extraction request was recorded")
    require(request["owner_id"] == session.owner_id, "ENDPOINT_IDENTITY_MISMATCH", "Current Owner required")
    with ExitStack() as pins:
        with session.lock:
            with store.transaction("management") as conn:
                plan = document(conn, "plans", "plan_id", control.binding["plan_id"])
                control.check_plan(plan)
                decision = sanity_hil.require_decision(service, conn, plan, allow_odb=True)
                require(key == plan["sanity"]["request_key"] + ".odb",
                        "ODB_NOT_AUTHORIZED", "Only the exact one-read operation key is supported")
                # Check again under the write lock, before authorizing any process.
                prior = conn.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?",
                                     (namespace, key)).fetchone()
                if prior:
                    require(prior[0] == fingerprint, "IDEMPOTENCY_CONFLICT", "Extraction key already has different scope")
                    return {"replayed": True, "receipt": json.loads(prior[1])}
                require(conn.execute("SELECT run_id FROM slot").fetchone()[0] is None
                        and session.active_dispatches == 0, "DISPATCH_PAUSED", "Run must complete before ODB extraction")
                try:
                    run, source, pinned = _bound_source(pins, conn, service, plan, args, decision)
                except OSError as exc:
                    raise ExecutionError("ODB_SOURCE_UNTRUSTED", "Cannot retain a stable source file") from exc
                receipt = {"operation_id": identifier("op"), "action": EXTRACT, "operation_key": key,
                           "state": "OUTCOME_UNKNOWN", "recorded_at": now(), "owner_id": session.owner_id,
                           "source": source, "script": plan["sanity"]["hil"]["odb"]["script"],
                           "script_version": sanity_hil.ODB_VERSION, "selector": args["selector"],
                           "native_hil_qualification": "UNVERIFIED"}
                conn.execute("INSERT INTO management_receipts VALUES(?,?,?,?,?)",
                             (namespace, key, fingerprint, receipt["operation_id"], canonical_json(receipt)))
            session.active_dispatches += 1
        try:
            store._checkpoint("hil_odb:after_intent")
            try:
                outcome = _run_script(service, plan, run, source, receipt["operation_id"], decision["expires_at"])
                path = confined(service.context.test_root, source["artifact"]["path"], exists=True)
                require(_fingerprint(path, pinned, sanity_hil.ODB_MAX_BYTES) == source["artifact"],
                        "ODB_SOURCE_UNTRUSTED", "ODB changed during extraction")
            except (ExecutionError, OSError) as exc:
                raise ExecutionError("ODB_OUTCOME_UNKNOWN", "Consult the original extraction intent") from exc
            receipt.update(outcome)
            with store.transaction("management") as conn:
                conn.execute("UPDATE management_receipts SET body=? WHERE namespace=? AND key=?",
                             (canonical_json(receipt), namespace, key))
            return {"replayed": False, "receipt": receipt}
        finally:
            with session.lock:
                session.active_dispatches -= 1
