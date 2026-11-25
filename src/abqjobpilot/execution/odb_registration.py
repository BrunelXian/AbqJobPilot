"""Owner terminal worker registration for one newly authorized Sanity ODB."""

from contextlib import ExitStack
import json
import os
from pathlib import Path

from . import hil_odb, odb_access, sanity_hil
from .models import ExecutionError, canonical_json, digest, identifier, now, require
from .paths import confined
from .sanity_model import hold_candidate
from .sanity_verdict import read_verdict
from .store import document

ACTION = "register_native_odb_source_v1"
SCHEMA = "sanity-odb-source-registration/1.0"
IDENTITY = ("project_id", "project_instance_id", "plan_id", "plan_digest",
            "run_id", "phase_attempt_id", "grant_id", "owner_id")
FILE_FIELDS = ("device", "inode", "size", "mtime_ns")


def _namespace(service):
    return canonical_json([service.context.project_instance_id, service.client_namespace, ACTION])


def _key(plan):
    return plan["sanity"]["request_key"] + ".odb-source"


def _binding(run, receipt, observation, validation):
    return {**{key: run[key] for key in IDENTITY}, "receipt_id": receipt["request_id"],
            "launch_intent_digest": digest(run["launch_intent"]), "run_revision": run["revision"],
            "scope_id": run.get("managed_scope", {}).get("scope_id"),
            "observation_id": observation["observation_id"], "validation_id": validation["validation_id"]}


def _lookup(conn, service, plan, bound):
    row = conn.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?",
                       (_namespace(service), _key(plan))).fetchone()
    if row is None:
        return None
    receipt = json.loads(row[1])
    require(receipt["binding"] == bound and row[0] == digest(bound)
            and receipt["schema"] == SCHEMA and receipt["action"] == ACTION
            and receipt["operation_key"] == _key(plan),
            "IDEMPOTENCY_CONFLICT", "ODB registration already names different terminal evidence")
    return receipt


def _decision(conn, service, plan, run, *, committed=False):
    from .product_standard import scope

    row = conn.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key='decision'",
                       (sanity_hil.decision_namespace(service, plan),)).fetchone()
    require(row is not None, "ODB_NOT_AUTHORIZED", "Original registration choice absent")
    choice = json.loads(row[1])
    grant = document(conn, "grants", "grant_id", run["grant_id"])
    started_at = run["launch_intent"]["intent_at_ns"] // 1_000_000_000
    # A committed registration authenticates the originally consumed Plan, not
    # the code bytes installed today. The live writer still checks the packet.
    scope_digest = digest(scope(plan)) if committed else sanity_hil.packet(plan)["scope_digest"]
    require(choice.get(sanity_hil.REGISTRATION_CHOICE) is True and choice["allow_odb"] is False
            and choice["decision"] == "APPROVE_EXACT"
            and row[0] == digest(choice) == grant["approval_source"]
            and choice["contract_version"] == sanity_hil.plan_version(plan)
            and all(choice[key] == run[key] for key in ("plan_id", "plan_digest", "project_id",
                                                      "project_instance_id", "owner_id"))
            and choice["input_sha256"] == plan["input_manifest"][0]["digest"]
            and choice["scope_digest"] == scope_digest
            and choice["decided_at"] <= started_at < choice["expires_at"] <= plan["expires_at"],
            "ODB_NOT_AUTHORIZED", "Original Solver approval did not authorize this registration")
    return row[0]


def _targets(conn, service, plan, run, attempt_id):
    require(run["phase_attempt_id"] == attempt_id, "ODB_SOURCE_UNTRUSTED", "Only the terminal worker's Attempt can register")
    receipt = hil_odb._accepted(conn, service, plan, run)
    observation, validation = odb_access.terminal_records(conn, run)
    return receipt, observation, validation


def _no_lock(context, plan):
    lock = confined(context.test_root, Path(plan["engineering"]) / (plan["job_name"] + ".lck"))
    try:
        lock.lstat()
    except FileNotFoundError:
        return
    raise ExecutionError("ODB_SOURCE_UNSTABLE", "Abaqus output lock is still present")


def _file_identity(stat):
    return dict(zip(FILE_FIELDS, (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)))


def _fingerprint(pins, service, plan, run):
    context = service.context
    _no_lock(context, plan)
    pins.enter_context(hold_candidate(plan))
    try:
        path, stream = hil_odb._source_pin(pins, context, plan, run)
    except ExecutionError as exc:
        if exc.code in ("INPUT_READ_FAILED", "INPUT_UNSTABLE"):
            raise ExecutionError("ODB_SOURCE_UNSTABLE", "Cannot retain stable read-only ODB identity") from exc
        raise
    before = _file_identity(os.fstat(stream.fileno()))
    artifact = hil_odb._fingerprint(path, stream, sanity_hil.ODB_MAX_BYTES)
    _no_lock(context, plan)
    require(before == _file_identity(path.stat()) == {key: artifact[key] for key in FILE_FIELDS},
            "ODB_SOURCE_UNSTABLE", "ODB identity changed during registration")
    return artifact


def register_finished(service, run_id, attempt_id):
    """Runs only in the original Owner dispatch, immediately after native terminal commit."""
    store = service.store
    with store.transaction("management") as conn:
        run = document(conn, "runs", "run_id", run_id)
        plan = document(conn, "plans", "plan_id", run["plan_id"])
        require(sanity_hil.independent_registration(plan), "CAPABILITY_UNAVAILABLE", "New registration contract required")
        if run["execution"] != "FINISHED":
            return None
        receipt, observation, validation = _targets(conn, service, plan, run, attempt_id)
        binding = _binding(run, receipt, observation, validation)
        prior = _lookup(conn, service, plan, binding)
        if prior is not None:
            return prior
        sanity_hil._require_owner(service, conn)
        require(run["owner_id"] == store._session.owner_id and store._session.active_dispatches == 1,
                "OWNER_UNCONFIRMED", "Original active Owner dispatch required")
        intent = {"schema": SCHEMA, "action": ACTION, "operation_key": _key(plan), "operation_id": identifier("op"),
                  "state": "OUTCOME_UNKNOWN", "recorded_at": now(), "binding": binding}
        try:
            intent["decision_digest"] = _decision(conn, service, plan, run)
            verdict = read_verdict(service.context, plan, receipt, run)
            intent["terminal_evidence"] = {key: verdict[key] for key in (
                "solver_outcome", "process_containment", "execution_qualification")}
            require(verdict["solver_outcome"] == "COMPLETED" and verdict["process_containment"] == "VERIFIED"
                    and verdict["execution_qualification"] in ("VERIFIED", "REVIEW_REQUIRED"),
                    "ODB_SOURCE_UNTRUSTED", "Bound Solver completion and verified closure are required")
        except (ExecutionError, KeyError, TypeError) as exc:
            intent.update(state="REJECTED", reason=getattr(exc, "code", "ODB_SOURCE_UNTRUSTED"))
        conn.execute("INSERT INTO management_receipts VALUES(?,?,?,?,?)",
                     (_namespace(service), _key(plan), digest(binding), intent["operation_id"], canonical_json(intent)))
    if intent["state"] == "REJECTED":
        return intent
    store._checkpoint("odb_registration:after_intent")
    with ExitStack() as pins:
        try:
            artifact = _fingerprint(pins, service, plan, run)
            source = {**binding, "contract_version": sanity_hil.plan_version(plan), "kind": "CURRENT_ATTEMPT_ODB",
                      "input_sha256": plan["input_manifest"][0]["digest"], "artifact": artifact,
                      "registration_id": intent["operation_id"], "observed_at": now(),
                      "terminal_evidence": intent["terminal_evidence"],
                      "observation_basis": "MANAGED_TERMINAL_AND_STABLE_READ_HANDLE"}
            finished = {**intent, "state": "REGISTERED", "source": source, "source_digest": digest(source)}
        except (ExecutionError, OSError, ValueError) as exc:
            finished = {**intent, "state": "REJECTED", "reason": getattr(exc, "code", "ODB_SOURCE_UNSTABLE")}
        with store.transaction("management") as conn:
            current = document(conn, "runs", "run_id", run_id)
            require(current["revision"] == binding["run_revision"] and _lookup(conn, service, plan, binding) == intent,
                    "STATE_CONFLICT", "Original ODB registration intent or Run changed")
            conn.execute("UPDATE management_receipts SET body=? WHERE namespace=? AND key=?",
                         (canonical_json(finished), _namespace(service), _key(plan)))
    return finished


def committed_source(conn, service, plan, run, receipt, observation, validation):
    """Resolve evidence from the original terminal transaction path without ODB I/O."""
    binding = _binding(run, receipt, observation, validation)
    registration = _lookup(conn, service, plan, binding)
    require(registration is not None, "ODB_REGISTRATION_UNKNOWN", "No original Owner registration receipt")
    require(registration["state"] != "OUTCOME_UNKNOWN", "ODB_REGISTRATION_UNKNOWN", "Registration outcome unknown")
    require(registration["state"] == "REGISTERED", registration.get("reason", "ODB_SOURCE_UNTRUSTED"),
            "Original Owner did not register this ODB")
    source = registration["source"]
    require(registration["source_digest"] == digest(source)
            and registration["decision_digest"] == _decision(conn, service, plan, run, committed=True)
            and all(source[key] == value for key, value in binding.items())
            and source["registration_id"] == registration["operation_id"]
            and source["terminal_evidence"] == registration["terminal_evidence"]
            and source["kind"] == "CURRENT_ATTEMPT_ODB"
            and source["contract_version"] == sanity_hil.plan_version(plan)
            and source["artifact"]["path"] == str(Path(plan["engineering"]) / (plan["job_name"] + ".odb")),
            "SOURCE_MISMATCH", "Committed ODB registration no longer matches the original Attempt")
    return source
