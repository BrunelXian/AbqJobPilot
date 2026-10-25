"""Explicit Fake-only reconciliation, using the existing service/store/validator."""

import json
import os
from pathlib import Path

from .authorization import check_grant, check_management_grant
from .models import (CANONICAL, RESOURCES, ExecutionError, bytes_digest, canonical_json, digest, fields,
                     fixed_fake_content, identifier, integer, now, require, text)
from .paths import confined, result_path
from .store import document, gate_view, needs_reconciliation, update_run
from .validation import validate_artifact
from .process_reconciliation import RECONCILE_PROCESS, SCOPE_FIELDS, apply_recorded
from .public_workflow import VALIDATE, VALIDATION_SCOPE, validate_recorded

MANAGEMENT_CONTRACT = "af-management-v1"
ADOPT = "adopt_verified_fake_artifact"
RESUME = "resume_dispatch"


def _owner(service):
    service._context(service.context)
    require(service.context.schema_version == 3, "UNSUPPORTED_FORMAT", "Management requires new format 3")
    service.store._session.lease.check()
    require(not service.store._session.closed, "OWNER_UNCONFIRMED", "Owner session closed")


def _inspect(service, connection, run_id):
    ctx, session = service.context, service.store._session
    run = document(connection, "runs", "run_id", run_id)
    gate = gate_view(connection)
    base = {"policy": "fake-reconciliation-v1", "project_id": ctx.project_id,
            "project_instance_id": ctx.project_instance_id, "context_digest": ctx.context_digest,
            "run_id": run_id, "run_revision": run["revision"], "plan_id": run["plan_id"],
            "plan_digest": run["plan_digest"], "owner_id": session.owner_id, "gate": gate,
            "candidate_action": None, "reasons": [], "evidence_fingerprint": None}
    captured = observation = validation = None
    try:
        require(gate["state"] == "PAUSED" and gate["owner_id"] == session.owner_id
                and session.active_dispatches == 0, "OWNER_NOT_QUIESCENT", "Reconciliation requires the exclusive paused owner")
        require(needs_reconciliation(run), "NOT_RECONCILABLE", "Run has no unresolved execution uncertainty")
        plan = document(connection, "plans", "plan_id", run["plan_id"])
        unsigned = {k: v for k, v in plan.items() if k != "plan_digest"}
        require(digest(unsigned) == plan["plan_digest"] == run["plan_digest"], "PLAN_STALE", "Historical plan digest mismatch")
        require(plan["context_digest"] == ctx.context_digest and plan["project_instance_id"] == ctx.project_instance_id
                and run["project_id"] == ctx.project_id and run["project_instance_id"] == ctx.project_instance_id
                and plan["job_id"] == run["job_id"] and plan["job_revision"] == run["job_revision"],
                "PROJECT_IDENTITY_MISMATCH", "Historical Project/Run/Job binding mismatch")
        require(plan["backend_id"] == run["backend_id"] == "fake-v1" and type(plan["backend_version"]) is int and plan["backend_version"] == 1
                and plan["action"] == "emit_fixture_result" and plan["phases"] == ["FAKE"]
                and run["phase"] == "FAKE" and run["simulation"] is True
                and plan["validation_policy"] == "fake-result-v1" and canonical_json(plan["resources"]) == canonical_json(RESOURCES)
                and plan["canonicalization"] == CANONICAL,
                "UNSUPPORTED_EVIDENCE_POLICY", "Only the original fixed Fake contract can be reconciled")
        require(canonical_json(plan["output_policy"]) == canonical_json({"root": ctx.runtime_root, "template": "fake_runs/{run_id}/result.json", "overwrite": False}),
                "OUTPUT_SCOPE_VIOLATION", "Historical output policy is outside the fixed Fake scope")
        config = plan["config_snapshot"]
        require(digest({k: v for k, v in config.items() if k != "digest"}) == config["digest"],
                "EVIDENCE_INSUFFICIENT", "Historical configuration digest mismatch")
        require(type(plan["input_manifest"]) is list and 0 < len(plan["input_manifest"]) <= 8,
                "EVIDENCE_INSUFFICIENT", "Missing historical input manifest")
        require([item["path"] for item in plan["input_manifest"]] == plan["job_spec"]["input_refs"],
                "EVIDENCE_INSUFFICIENT", "Historical input references do not match original Job")
        for item in plan["input_manifest"]:
            fields(item, ("path", "size", "digest"))
            integer(item["size"])
            require(item["size"] <= 65536 and type(item["digest"]) is str and item["digest"].startswith("sha256:")
                    and len(item["digest"]) == 71 and all(c in "0123456789abcdef" for c in item["digest"][7:]),
                    "EVIDENCE_INSUFFICIENT", "Historical input digest/size is invalid")
        events = [json.loads(r[0]) for r in connection.execute("SELECT body FROM events WHERE run_id=? ORDER BY sequence", (run_id,))]
        starts = [e for e in events if e["type"] == "START_INTENT"]
        accepts = [e for e in events if e["type"] == "REQUEST_ACCEPTED"]
        require(len(starts) == len(accepts) == 1 and starts[0]["run_sequence"] > accepts[0]["run_sequence"],
                "EVIDENCE_INSUFFICIENT", "Exactly one accepted and claimed attempt must be recorded")
        row = connection.execute("SELECT body FROM receipts WHERE run_id=?", (run_id,)).fetchone()
        require(row is not None, "EVIDENCE_INSUFFICIENT", "Original submission receipt is missing")
        receipt = json.loads(row[0])
        require(receipt["run_id"] == run_id and receipt["job_id"] == run["job_id"], "EVIDENCE_INSUFFICIENT", "Receipt binding mismatch")
        grant_row = connection.execute("SELECT body FROM grants WHERE grant_id=?", (run["grant_id"],)).fetchone()
        consumption = connection.execute("SELECT run_id FROM consumption WHERE grant_id=?", (run["grant_id"],)).fetchone()
        require(grant_row is not None and consumption is not None and consumption[0] == run_id,
                "EVIDENCE_INSUFFICIENT", "Original execution authorization/consumption is missing")
        grant = json.loads(grant_row[0])
        historical_time = starts[0]["recorded_at"]
        integer(historical_time)
        require(receipt["accepted_at"] <= historical_time, "EVIDENCE_INSUFFICIENT", "Claim predates the accepted request")
        check_grant(ctx, plan, grant, session.authority_instance, run_id, run_id, at_time=historical_time)
        require(plan["expires_at"] > historical_time, "EVIDENCE_INSUFFICIENT", "Plan was not valid at the recorded claim")
        expected = fixed_fake_content(plan, run)
        require(len(expected) <= RESOURCES["max_output_bytes"], "EVIDENCE_INSUFFICIENT", "Fixed content exceeds original resource bound")
        path = result_path(ctx, run_id)  # Check policy/backend/format BEFORE opening any candidate artifact.
        with path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            require(info.st_nlink == 1, "OUTPUT_SCOPE_VIOLATION", "Shared hard-link artifacts are not supported")
            content = stream.read(RESOURCES["max_output_bytes"] + 1)
            after = os.fstat(stream.fileno())
        require((info.st_size, info.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                "EVIDENCE_CHANGED", "Artifact changed during capture")
        emission = {"path": str(path), "size": len(expected), "digest": bytes_digest(expected)}
        observation, validation = validate_artifact(ctx, plan, run, emission, captured=(content, info))
        fingerprint = {"path": str(path), "device": info.st_dev, "inode": info.st_ino,
                       "size": info.st_size, "mtime_ns": info.st_mtime_ns, "digest": bytes_digest(content),
                       "expected_digest": emission["digest"], "plan": digest(plan), "run": digest(run),
                       "events": digest(events), "receipt": digest(receipt), "execution_grant": digest(grant)}
        base["evidence_fingerprint"] = fingerprint
        require(validation["verdict"] == "PASS" and content == expected, "EVIDENCE_INVALID",
                "Original fixed bytes/independent validation failed: " + ", ".join(validation["reasons"]))
        base["candidate_action"] = ADOPT
        base["basis"] = "Complete deterministic fake-v1 output plus original accepted/claimed Plan and grant history; inferred now, not a past observed completion"
        captured = content
    except ExecutionError as exc:
        base["reasons"] = [{"code": exc.code, "message": str(exc)}]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        base["reasons"] = [{"code": "EVIDENCE_INSUFFICIENT", "message": "Historical evidence cannot be verified: " + type(exc).__name__}]
    return {**base, "preview_digest": digest(base)}, captured, observation, validation


def preview(service, context, run_id):
    service._context(context)
    _owner(service)
    text(run_id)
    with service.store.read() as connection:
        return _inspect(service, connection, run_id)[0]


def _request(service, request, action):
    require(action in {ADOPT, RESUME, RECONCILE_PROCESS, VALIDATE}, "INVALID_REQUEST", "Unsupported management action")
    common = ("contract_version", "operation", "project_id", "project_instance_id", "owner_id",
              "management_grant_id", "idempotency_key")
    scope_names = ("run_id", "expected_run_revision", "preview_digest") if action == ADOPT else ("expected_gate_version",)
    if action == RECONCILE_PROCESS:
        scope_names = SCOPE_FIELDS
    if action == VALIDATE:
        scope_names = VALIDATION_SCOPE
    fields(request, common + scope_names)
    require(request["contract_version"] == MANAGEMENT_CONTRACT and request["operation"] == action,
            "INVALID_REQUEST", "Unsupported management contract/action")
    ctx = service.context
    require(request["project_id"] == ctx.project_id and request["project_instance_id"] == ctx.project_instance_id,
            "PROJECT_IDENTITY_MISMATCH", "Management request targets another Project")
    for key in ("owner_id", "management_grant_id", "idempotency_key"):
        text(request[key])
    if action == VALIDATE:
        integer(request["expected_run_revision"], 1)
        for key in ("run_id", "plan_id", "plan_digest"):
            text(request[key])
    elif action in {ADOPT, RECONCILE_PROCESS}:
        integer(request["expected_run_revision"], 1)
        text(request["run_id"])
        text(request["preview_digest"])
        if action == RECONCILE_PROCESS:
            for key in ("plan_id", "plan_digest", "phase_attempt_id", "backend_id", "evidence_fingerprint"):
                text(request[key])
            integer(request["backend_version"], 1)
    else:
        integer(request["expected_gate_version"], 1)
    namespace = canonical_json([ctx.project_instance_id, service.client_namespace, action])
    summary = digest({k: v for k, v in request.items() if k != "idempotency_key"})
    return namespace, summary, {k: request[k] for k in scope_names}


def _prior(connection, namespace, key, summary):
    row = connection.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?", (namespace, key)).fetchone()
    if row:
        require(row[0] == summary, "IDEMPOTENCY_CONFLICT", "Same management key has different content")
        return json.loads(row[1])
    return None


def _authorize(service, connection, request, action, scope):
    session = service.store._session
    require(request["owner_id"] == session.owner_id, "STALE_OWNER", "A new owner requires a new preview and permission")
    row = connection.execute("SELECT body FROM management_grants WHERE grant_id=?", (request["management_grant_id"],)).fetchone()
    used = connection.execute("SELECT 1 FROM management_consumption WHERE grant_id=?", (request["management_grant_id"],)).fetchone()
    check_management_grant(service.context, json.loads(row[0]) if row else None,
                           session.authority_instance, session.owner_id, action, scope, used)


def _snapshot(service, operation_id, content):
    root = confined(service.context.test_root, Path(service.context.runtime_root) / "reconciliation_evidence")
    root.mkdir(exist_ok=True)
    path = confined(service.context.test_root, root / (operation_id + ".json"))
    service.store._checkpoint("reconciliation:before_snapshot")
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    service.store._checkpoint("reconciliation:after_snapshot")
    return {"path": str(path), "digest": bytes_digest(content), "size": len(content), "operation_id": operation_id}


def manage(service, context, request, action):
    service._context(context)
    _owner(service)
    namespace, summary, scope = _request(service, request, action)
    replayed = False
    with service.store.transaction("management") as connection:
        receipt = _prior(connection, namespace, request["idempotency_key"], summary)
        if receipt:
            replayed = True  # Before revision, owner, expiry or consumption checks; no side effect.
        else:
            _authorize(service, connection, request, action, scope)
            session = service.store._session
            gate = gate_view(connection)
            require((gate["state"] == "PAUSED" or action == VALIDATE) and gate["owner_id"] == session.owner_id
                    and session.active_dispatches == 0, "GATE_PRECONDITION_FAILED", "Current owner must be paused and quiescent")
            operation_id = identifier("op")
            refs = []
            if action == VALIDATE:
                refs, projection = validate_recorded(service, connection, request, operation_id, gate)
            elif action == RECONCILE_PROCESS:
                refs, projection = apply_recorded(service, connection, request, operation_id, gate)
            elif action == ADOPT:
                current, captured, observation, validation = _inspect(service, connection, request["run_id"])
                require(current["run_revision"] == request["expected_run_revision"]
                        and current["preview_digest"] == request["preview_digest"],
                        "STALE_PREVIEW", "Evidence, owner, gate or Run changed; preview again")
                require(current["candidate_action"] == ADOPT, "EVIDENCE_INSUFFICIENT", "No verified adoption candidate")
                snapshot = _snapshot(service, operation_id, captured)
                observation.update(provenance="reconciliation_capture", snapshot=snapshot)
                validation.update(source="explicit_reconciliation", snapshot=snapshot)
                record = {"reconciliation_id": identifier("rec"), "operation_id": operation_id,
                          "run_id": request["run_id"], "owner_id": session.owner_id, "recorded_at": now(),
                          "source": "TEST_ONLY_EXPLICIT_RECONCILIATION", "action": ADOPT, "preview": current,
                          "snapshot": snapshot, "observation_id": observation["observation_id"],
                          "validation_id": validation["validation_id"], "conclusion": "FIXED_FAKE_COMPLETION_INFERRED_NOW"}
                connection.execute("INSERT INTO observations VALUES(?,?,?)", (observation["observation_id"], request["run_id"], canonical_json(observation)))
                connection.execute("INSERT INTO validations VALUES(?,?,?)", (validation["validation_id"], request["run_id"], canonical_json(validation)))
                connection.execute("INSERT INTO reconciliations VALUES(?,?,?)", (record["reconciliation_id"], request["run_id"], canonical_json(record)))
                refs = [record["reconciliation_id"], observation["observation_id"], validation["validation_id"]]
                run = document(connection, "runs", "run_id", request["run_id"])
                updated = update_run(connection, run, "RECONCILIATION_APPLIED", evidence_refs=refs,
                                     execution="FINISHED", reconciliation="NONE", backend_outcome="COMPLETED",
                                     backend_outcome_basis="RECONCILED_FIXED_ARTIFACT", artifact_validation="VALID",
                                     solver_conclusion="NOT_RUN", validation_scope="simulation", reconciled_at=record["recorded_at"], error=None)
                connection.execute("UPDATE slot SET run_id=NULL WHERE id=1 AND run_id=?", (request["run_id"],))
                projection = {"run_id": run["run_id"], "run_revision": updated["revision"], "gate": gate}
            else:
                require(gate["version"] == request["expected_gate_version"], "GATE_PRECONDITION_FAILED", "Gate version changed")
                runs = [json.loads(r[0]) for r in connection.execute("SELECT body FROM runs")]
                require(not any(needs_reconciliation(r) for r in runs)
                        and connection.execute("SELECT run_id FROM slot WHERE id=1").fetchone()[0] is None,
                        "RECONCILIATION_REQUIRED", "Unresolved execution or occupied slot blocks resumption")
                connection.execute("UPDATE dispatch_gate SET state='OPEN',version=version+1 WHERE id=1")
                gate = gate_view(connection)
                event = {"event_id": identifier("control"), "operation_id": operation_id, "type": "DISPATCH_RESUMED",
                         "owner_id": session.owner_id, "gate": gate, "recorded_at": now()}
                connection.execute("INSERT INTO control_events(body) VALUES(?)", (canonical_json(event),))
                refs = [event["event_id"]]
                projection = {"gate": gate}
            receipt = {"operation_id": operation_id, "operation": action, "operation_status": "APPLIED",
                       "namespace": namespace, "idempotency_key": request["idempotency_key"], "request_digest": summary,
                       "applied_at": now(), "owner_id": session.owner_id, "projection_at_commit": projection, "evidence_refs": refs}
            connection.execute("INSERT INTO management_receipts VALUES(?,?,?,?,?)",
                               (namespace, request["idempotency_key"], summary, operation_id, canonical_json(receipt)))
            connection.execute("INSERT INTO management_consumption VALUES(?,?)", (request["management_grant_id"], operation_id))
    try:
        service.store._checkpoint("management:after_commit")
    except OSError as exc:
        raise ExecutionError("ACCEPTANCE_UNKNOWN", "Management commit response lost; query original operation key", stage="MANAGEMENT") from exc
    return {"operation_status": "APPLIED", "replayed": replayed, "receipt": receipt}
