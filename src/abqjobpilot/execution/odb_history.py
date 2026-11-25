"""Owner-only, single-use permission to observe an originally registered ODB."""

from contextlib import ExitStack
import json
from pathlib import Path
import stat
import time

from . import hil_odb, odb_access, odb_output_provenance, sanity_hil
from .job_process_observer import JobProcessObserver
from .managed_process import ManagedScope, check_completion
from .models import ExecutionError, bytes_digest, canonical_json, digest, fields, identifier, integer, now, require, text
from .paths import confined
from .sanity_model import hold_candidate
from .standard_process import check_host
from .store import document

DESCRIBE = "describe_historical_odb_v1"
ISSUE = "issue_historical_odb_read_v1"
EXTRACT = "extract_historical_odb_v1"
STATUS = "read_historical_odb_receipt_v1"
ACTIONS = (DESCRIBE, ISSUE, EXTRACT, STATUS)
SCHEMA = "historical-odb-observation-permit/1.0"
TARGET = ("project_id", "project_instance_id", "plan_id", "plan_digest",
          "run_id", "phase_attempt_id", "receipt_id")
READ = (*TARGET, "grant_id", "source_sha256", "script_version", "selector")
APPROVAL = ("subject", "approval_ref", "expires_at")
MAX_SECONDS = 600
PROCESS_EXIT_RECORDED = "EXTRACTOR_EXIT_RECORDED"


def _namespace(service, action):
    return canonical_json([service.context.project_instance_id, service.client_namespace, action])


def _lookup(conn, service, action, key):
    return conn.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?",
                        (_namespace(service, action), key)).fetchone()


def independent_review_exists(conn, service, plan):
    return _lookup(conn, service, ISSUE, plan["sanity"]["request_key"] + ".historical-odb-review") is not None


def _replay(row, fingerprint):
    if row is None:
        return None
    require(row[0] == fingerprint, "IDEMPOTENCY_CONFLICT", "Original ODB operation has different content")
    return {"replayed": True, "receipt": json.loads(row[1])}


def source_status(conn, service, plan, args):
    """Assess original registration and path metadata. Never open or hash the ODB."""
    run, receipt = odb_access.accepted_run(conn, service, plan, args)
    observation, validation = odb_access.terminal_records(conn, run)
    if sanity_hil.independent_registration(plan):
        from .odb_registration import committed_source
        try:
            source = committed_source(conn, service, plan, run, receipt, observation, validation)
            info = confined(service.context.test_root, source["artifact"]["path"], exists=True).stat()
            require(stat.S_ISREG(info.st_mode) and all(source["artifact"].get(key) == value for key, value in (
                ("device", info.st_dev), ("inode", info.st_ino), ("mtime_ns", info.st_mtime_ns), ("size", info.st_size))),
                "SOURCE_MISMATCH", "File identity differs from its original ODB registration")
        except ExecutionError as exc:
            grade = exc.code if exc.code in {"ODB_REGISTRATION_UNKNOWN", "ODB_SOURCE_NOT_FOUND",
                                             "ODB_SOURCE_UNSTABLE", "ODB_NOT_AUTHORIZED", "ODB_SOURCE_UNTRUSTED"} else "SOURCE_MISMATCH"
            return grade, run, None
        except (OSError, KeyError, TypeError, AttributeError):
            return "SOURCE_MISMATCH", run, None
        return "TRUSTED_SOURCE", run, source
    location = Path(plan["engineering"]) / (plan["job_name"] + ".odb")
    has_record = "odb_source" in observation or run.get("odb_registration") == "BOUND_PENDING_CONTENT_VALIDATION"
    try:
        location = confined(service.context.test_root, location)
        info = location.stat()
    except FileNotFoundError:
        return ("SOURCE_MISMATCH" if has_record else "SOURCE_NOT_FOUND"), run, None
    except (ExecutionError, OSError):
        return "SOURCE_MISMATCH", run, None
    if not stat.S_ISREG(info.st_mode):
        return "SOURCE_MISMATCH", run, None
    if not has_record:
        return "HISTORICAL_SOURCE_UNVERIFIED", run, None
    try:
        source = odb_access.registered_identity(plan, run, receipt, observation, validation)
        decision_row = conn.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key='decision'",
                                    (sanity_hil.decision_namespace(service, plan),)).fetchone()
        require(decision_row is not None, "SOURCE_MISMATCH", "Original source registration approval is absent")
        decision = json.loads(decision_row[1])
        grant = document(conn, "grants", "grant_id", run["grant_id"])
        started_at = run["launch_intent"]["intent_at_ns"] // 1_000_000_000
        require(decision_row[0] == digest(decision) == grant["approval_source"]
                and decision["decision"] == "APPROVE_EXACT" and decision["allow_odb"] is True
                and decision["contract_version"] == sanity_hil.plan_version(plan)
                and decision["owner_id"] == run["owner_id"] and decision["plan_digest"] == plan["plan_digest"]
                and decision["plan_id"] == plan["plan_id"] and decision["project_id"] == run["project_id"]
                and decision["project_instance_id"] == run["project_instance_id"]
                and decision["scope_digest"] == sanity_hil.packet(plan)["scope_digest"]
                and decision["decided_at"] <= started_at < decision["expires_at"],
                "SOURCE_MISMATCH", "Original read authority does not support the recorded source")
        artifact = source["artifact"]
        metadata = {"device": info.st_dev, "inode": info.st_ino, "mtime_ns": info.st_mtime_ns, "size": info.st_size}
        require(all(artifact.get(field) == value for field, value in metadata.items()),
                "SOURCE_MISMATCH", "File identity differs from its original ODB registration")
        check_completion(run.get("managed_scope"), run)
        require(run["managed_completion"] == "COMMITTED_EMPTY_SCOPE"
                and run["solver_conclusion"] == "COMPLETED_TEXT_EVIDENCE",
                "SOURCE_MISMATCH", "Original managed terminal proof is inconsistent")
    except (ExecutionError, KeyError, TypeError, AttributeError):
        return "SOURCE_MISMATCH", run, None
    return "TRUSTED_SOURCE", run, source


def _bound_plan(conn, service, control, args, action, key):
    plan = document(conn, "plans", "plan_id", control.binding["plan_id"])
    control.check_plan(plan)
    require(sanity_hil.from_plan(plan), "CAPABILITY_UNAVAILABLE", "Exact Sanity HIL required")
    sanity_hil.validate_plan(plan)
    require(args["project_id"] == service.context.project_id
            and args["project_instance_id"] == service.context.project_instance_id,
            "PROJECT_IDENTITY_MISMATCH", "ODB request has another Project or Instance")
    require(args["plan_id"] == plan["plan_id"] and args["plan_digest"] == plan["plan_digest"],
            "ODB_SOURCE_UNTRUSTED", "ODB request has another Plan")
    expected = ".historical-odb-review" if action in (ISSUE, DESCRIBE) else ".historical-odb"
    require(key == plan["sanity"]["request_key"] + expected, "ODB_NOT_AUTHORIZED", "Exact ODB operation key required")
    return plan


def _scope(service, plan, args, source):
    return {"schema": SCHEMA, "purpose": "RESULT_OBSERVATION", **{key: args[key] for key in TARGET},
            "source_grade": "TRUSTED_SOURCE", "source": source,
            "script": plan["sanity"]["hil"]["odb"]["script"], "script_version": sanity_hil.ODB_VERSION,
            "selector": sanity_hil.ODB_SELECTOR, "max_reads": 1, "owner_id": service.store._session.owner_id,
            "context_digest": service.context.context_digest}


def approval_digest(scope, approval):
    return digest({"scope": scope, **{key: approval[key] for key in APPROVAL}})


def _exclusive(conn, service, plan):
    sanity_hil._require_owner(service, conn)
    require(service.store._session.active_dispatches == 0
            and conn.execute("SELECT run_id FROM slot WHERE id=1").fetchone()[0] is None,
            "DISPATCH_PAUSED", "An idle Owner with a PAUSED Solver Gate is required")
    require(_lookup(conn, service, hil_odb.EXTRACT, plan["sanity"]["request_key"] + ".odb") is None,
            "ODB_READ_ALREADY_USED", "Original ODB operation has already been recorded")


def _insert_receipt(conn, service, action, key, fingerprint, receipt):
    conn.execute("INSERT INTO management_receipts VALUES(?,?,?,?,?)",
                 (_namespace(service, action), key, fingerprint, receipt["operation_id"], canonical_json(receipt)))


def _issue(conn, service, key, fingerprint, args, scope):
    checked = now()
    require(checked < args["expires_at"] <= checked + MAX_SECONDS,
            "ODB_APPROVAL_EXPIRED", "Use a current approval of at most 600 seconds")
    proof = approval_digest(scope, args)
    require(args["confirmation"] == "READ_ODB " + proof,
            "ODB_HUMAN_CONFIRMATION_REQUIRED", "Exact independent human confirmation required")
    grant = {"grant_id": identifier("odbgrant"), "kind": SCHEMA, "scope": scope,
             "approval_digest": proof, "approved_at": checked, **{key: args[key] for key in APPROVAL}}
    receipt = {"operation_id": identifier("op"), "action": ISSUE, "operation_key": key, "grant": grant}
    conn.execute("INSERT INTO management_grants VALUES(?,?)", (grant["grant_id"], canonical_json(grant)))
    _insert_receipt(conn, service, ISSUE, key, fingerprint, receipt)
    return {"replayed": False, "receipt": receipt}


def _consume(conn, service, plan, key, fingerprint, args, scope):
    row = conn.execute("SELECT body FROM management_grants WHERE grant_id=?", (args["grant_id"],)).fetchone()
    approved = _lookup(conn, service, ISSUE, plan["sanity"]["request_key"] + ".historical-odb-review")
    require(row is not None and approved is not None, "ODB_NOT_AUTHORIZED", "Independent ODB read permission required")
    grant = json.loads(row[0])
    require(grant.get("kind") == SCHEMA and grant["grant_id"] == args["grant_id"] and grant["scope"] == scope
            and json.loads(approved[1])["grant"] == grant
            and grant["approval_digest"] == approval_digest(scope, grant),
            "ODB_NOT_AUTHORIZED", "Grant differs from the original independent approval")
    require(grant["approved_at"] <= now() < grant["expires_at"], "ODB_APPROVAL_EXPIRED", "ODB read permission expired")
    require(args["source_sha256"] == scope["source"]["artifact"]["sha256"],
            "SOURCE_MISMATCH", "Requested SHA-256 differs from the original registration")
    require(conn.execute("SELECT 1 FROM management_consumption WHERE grant_id=?", (args["grant_id"],)).fetchone() is None,
            "ODB_READ_ALREADY_USED", "ODB read permission was consumed")
    receipt = {"operation_id": identifier("op"), "action": EXTRACT, "operation_key": key,
               "grant_id": grant["grant_id"], "approval_digest": grant["approval_digest"],
               "state": "OUTCOME_UNKNOWN", "native_hil_qualification": "UNVERIFIED",
               "recorded_at": now(), **scope}
    _insert_receipt(conn, service, EXTRACT, key, fingerprint, receipt)
    conn.execute("INSERT INTO management_consumption VALUES(?,?)", (grant["grant_id"], receipt["operation_id"]))
    return receipt, grant["expires_at"]


def _launch(service, plan, run, receipt, expires_at):
    """Return the original native process evidence to the Owner transaction."""
    config = service._standard_backend.config
    config.verify()
    require(check_host(config)["eligible"], "HOST_UNVERIFIED", "Exact Owner launch environment required")
    output = confined(service.context.test_root,
                      Path(service.context.runtime_root) / "standard_runs" / run["run_id"] / receipt["operation_id"])
    output.mkdir()
    for name in ("home/AppData/Roaming", "home/AppData/Local", "tmp"):
        (output / name).mkdir(parents=True)
    call = hil_odb.call_data(plan, output, receipt["source"], expires_at)
    extract_run = {**run, "owner_id": receipt["owner_id"],
                   "owner_epoch": run["owner_epoch"] + (run["owner_id"] != receipt["owner_id"])}
    with ExitStack() as resources, ExitStack() as observing:
        script = Path(receipt["script"]["path"])
        pinned, info = hil_odb._pin(resources, script, 16384)
        require({"path": str(script), "size": info.st_size, "digest": bytes_digest(pinned.read(16385))}
                == receipt["script"], "PLAN_STALE", "Fixed extractor script changed")
        scope = ManagedScope(extract_run)
        resources.callback(scope.close)
        observer = JobProcessObserver(scope)
        observing.callback(observer.close)
        discard = resources.enter_context(open("NUL", "wb"))
        deadline = time.monotonic() + min(sanity_hil.ODB_SECONDS, expires_at - now())
        require(time.monotonic() < deadline and now() < call["start_not_after"],
                "ODB_APPROVAL_EXPIRED", "No time left for the original read operation")
        child = scope.create_standard(call, discard, discard)
        resources.callback(child.close)
        observer.bind_root(child)
        while time.monotonic() < deadline:
            view = observer.sample()
            require(observer.in_scope(scope), "ODB_OUTCOME_UNKNOWN", "Incomplete managed membership")
            completion = scope.query()
            if completion["state"] == "EMPTY_CONFIRMED":
                break
            time.sleep(0.05)
        else:
            raise ExecutionError("ODB_OUTCOME_UNKNOWN", "No confirmed extractor process exit")
        check_completion(completion, extract_run)
        view = observer.sample(completion)
        require(view["membership_evidence"]["complete"] and view["all_observed_exited"] and observer.in_scope(scope),
                "ODB_OUTCOME_UNKNOWN", "No complete extractor exit evidence")
        process = {"scope": completion, "membership_evidence": view["membership_evidence"],
                   "exits": view["process_exits"]}
        require(process["exits"], "ODB_OUTCOME_UNKNOWN", "No retained extractor exit records")
        return {"state": PROCESS_EXIT_RECORDED, "process": process}


def _observe_output(pins, service, plan, receipt, process):
    diagnostic = any(item["exit_code"] != 0 for item in process["exits"])
    outcome = {"state": "FAILED" if diagnostic else "NATIVE_OUTPUT_RECORDED", "process": process}
    if diagnostic:
        outcome["error_code"] = "ODB_EXTRACTION_FAILED"
    try:
        artifact, proof = odb_output_provenance.observe(pins, service.context, plan, {**receipt, **outcome},
                                                        diagnostic=diagnostic)
    except (ExecutionError, OSError) as exc:
        reason = getattr(exc, "code", "ODB_OUTPUT_INVALID")
        return {**outcome, "state": "FAILED", "error_code": outcome.get("error_code", reason),
                "output_observation_error": reason}
    outcome["output_provenance"] = proof
    if not diagnostic:
        outcome["artifact"] = artifact
    return outcome


def _finish(service, plan, run, receipt, expires_at, key):
    store = service.store
    try:
        store._checkpoint("historical_odb:after_intent")
        with ExitStack() as pins:
            try:
                require(now() < expires_at, "ODB_APPROVAL_EXPIRED", "Approved read window closed")
                pins.enter_context(hold_candidate(plan))
                path, stream = hil_odb._source_pin(pins, service.context, plan, run)
                original = receipt["source"]["artifact"]
                require(hil_odb._fingerprint(path, stream, sanity_hil.ODB_MAX_BYTES) == original,
                        "SOURCE_MISMATCH", "Actual ODB differs from the original registration")
            except (ExecutionError, OSError) as exc:
                outcome = {"state": "FAILED", "error_code": getattr(exc, "code", "SOURCE_MISMATCH")}
            else:
                odb_output_provenance.check_selector(plan, receipt)
                outcome = _launch(service, plan, run, receipt, expires_at)
                require(hil_odb._fingerprint(path, stream, sanity_hil.ODB_MAX_BYTES) == original,
                        "SOURCE_MISMATCH", "Source changed after extraction start")
                if outcome["state"] == PROCESS_EXIT_RECORDED:
                    outcome = _observe_output(pins, service, plan, receipt, outcome["process"])
            with store.transaction("management") as conn:
                current = _lookup(conn, service, EXTRACT, key)
                require(current is not None and json.loads(current[1]) == receipt,
                        "STATE_CONFLICT", "Original extraction intent changed")
                if "output_provenance" in outcome:
                    odb_output_provenance.check_path_identity(service.context, receipt, outcome["output_provenance"])
                receipt = {**receipt, **outcome}
                conn.execute("UPDATE management_receipts SET body=? WHERE namespace=? AND key=?",
                             (canonical_json(receipt), _namespace(service, EXTRACT), key))
        return {"replayed": False, "receipt": receipt}
    except (ExecutionError, OSError) as exc:
        raise ExecutionError("ODB_OUTCOME_UNKNOWN", "Consult the original historical ODB receipt") from exc
    finally:
        with store._session.lock:
            store._session.active_dispatches -= 1


def invoke(service, control, request):
    action, args, key = (request[k] for k in ("action", "arguments", "operation_key"))
    expected = TARGET if action == DESCRIBE else (*TARGET, *APPROVAL, "confirmation") if action == ISSUE else READ
    fields(args, expected)
    for name in TARGET:
        text(args[name])
    if action == ISSUE:
        integer(args["expires_at"])
        for name in ("subject", "approval_ref", "confirmation"):
            text(args[name])
        require(len(args["subject"]) <= 128 and len(args["approval_ref"]) <= 256,
                "LIMIT_EXCEEDED", "Bounded independent human approval reference required")
    if action in (EXTRACT, STATUS):
        text(args["grant_id"])
        text(args["source_sha256"])
        require(args["script_version"] == sanity_hil.ODB_VERSION and args["selector"] == sanity_hil.ODB_SELECTOR,
                "ODB_FIELD_NOT_ALLOWED", "Only the fixed T3D2 final TIP U2 selector is supported")
    store = service.store
    if action == DESCRIBE:
        with store.read() as conn:
            conn.execute("BEGIN")
            plan = _bound_plan(conn, service, control, args, action, key)
            grade, _, source = source_status(conn, service, plan, args)
        return {"schema": SCHEMA, "source_grade": grade, "file_bytes_checked": False,
                "scope": _scope(service, plan, args, source) if source is not None else None}
    ledger_action = ISSUE if action == ISSUE else EXTRACT
    fingerprint = digest(args)
    with store.read() as conn:
        prior = _replay(_lookup(conn, service, ledger_action, key), fingerprint)
    if prior:
        return prior
    require(action != STATUS, "NOT_FOUND", "No original historical ODB receipt")
    require(request["owner_id"] == store._session.owner_id, "ENDPOINT_IDENTITY_MISMATCH", "Current Owner required")
    with store._session.lock:
        with store.transaction("management") as conn:
            prior = _replay(_lookup(conn, service, ledger_action, key), fingerprint)
            if prior:
                return prior
            plan = _bound_plan(conn, service, control, args, action, key)
            _exclusive(conn, service, plan)
            grade, run, source = source_status(conn, service, plan, args)
            require(grade == "TRUSTED_SOURCE", grade, "Original registered ODB evidence required")
            scope = _scope(service, plan, args, source)
            if action == ISSUE:
                return _issue(conn, service, key, fingerprint, args, scope)
            receipt, expires_at = _consume(conn, service, plan, key, fingerprint, args, scope)
        store._session.active_dispatches += 1
    return _finish(service, plan, run, receipt, expires_at, key)
