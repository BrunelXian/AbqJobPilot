"""Recorded exit reconciliation: database evidence only, never process/artifact IO."""

import json

from .models import ExecutionError, canonical_json, digest, identifier, now, require, text
from .process_contract import BACKEND, ACTION, MEMBERSHIP_CONTRACT, EXIT_CONTRACT, REQUIRED_ROLES, SCENARIOS
from .store import document, gate_view, needs_reconciliation, update_run

RECONCILE_PROCESS = "reconcile_recorded_process_exits"
POLICY = "recorded-process-reconciliation-v1"
SCOPE_FIELDS = ("run_id", "expected_run_revision", "preview_digest", "plan_id", "plan_digest",
                "phase_attempt_id", "backend_id", "backend_version", "evidence_fingerprint")
BINDING = ("project_instance_id", "run_id", "plan_id", "plan_digest", "phase_attempt_id", "owner_id", "owner_epoch")
IDENTITY = ("role", "pid", "creation_time_100ns", "image_path", "identity_status", "observed_at",
            "execution_object_digest", "image_digest")


def _rows(connection, table, run_id, limit=64):
    # Table names are internal constants, never client supplied.
    rows = connection.execute("SELECT CASE WHEN length(CAST(body AS BLOB))<=16384 THEN body END FROM " + table + " WHERE run_id=? ORDER BY rowid LIMIT ?",
                              (run_id, limit + 1)).fetchall()
    require(len(rows) <= limit and all(r[0] is not None for r in rows)
            and sum(len(r[0].encode("utf-8")) for r in rows) <= 262144,
            "LIMIT_EXCEEDED", "Recorded process history exceeds reconciliation bound")
    require(all(len(r[0].encode("utf-8")) <= 16384 for r in rows), "LIMIT_EXCEEDED", "History record exceeds bound")
    return [json.loads(r[0]) for r in rows]


def inspect(service, connection, run_id):
    ctx, session = service.context, service.store._session
    run = document(connection, "runs", "run_id", run_id)
    gate = gate_view(connection)
    base = {"policy": POLICY, "project_id": ctx.project_id, "project_instance_id": ctx.project_instance_id,
            "context_digest": ctx.context_digest, "storage_generation": ctx.storage_generation,
            "run_id": run_id, "run_revision": run["revision"], "plan_id": run["plan_id"],
            "plan_digest": run["plan_digest"], "phase_attempt_id": run["phase_attempt_id"],
            "backend_id": run["backend_id"], "backend_version": 1, "owner_id": session.owner_id, "gate": gate,
            "candidate_action": None, "classification": None, "evidence_fingerprint": None,
            "member_fingerprint": None, "source_refs": [], "required_roles": list(REQUIRED_ROLES),
            "recorded_exits": [], "historical_validations": [], "artifact_validation": run["artifact_validation"],
            "reasons": [], "scope": "persisted_fixed_process_exit_facts_only_no_artifact_or_os_observation"}
    try:
        require(gate["state"] == "PAUSED" and gate["owner_id"] == session.owner_id and session.active_dispatches == 0,
                "OWNER_NOT_QUIESCENT", "Exclusive paused quiescent owner required")
        require(needs_reconciliation(run), "NOT_RECONCILABLE", "No unresolved execution uncertainty")
        plan = document(connection, "plans", "plan_id", run["plan_id"])
        require(plan["backend_id"] == run["backend_id"] == BACKEND and type(plan["backend_version"]) is int
                and plan["backend_version"] == 1 and plan["action"] == ACTION and plan["phases"] == ["PROCESS_FIXTURE"]
                and run["phase"] == "PROCESS_FIXTURE" and run["simulation"] is True,
                "UNSUPPORTED_EVIDENCE_POLICY", "Only the fixed process fixture version is supported")
        require(digest({k: v for k, v in plan.items() if k != "plan_digest"}) == plan["plan_digest"] == run["plan_digest"],
                "PLAN_STALE", "Original plan digest differs")
        require(run["project_instance_id"] == plan["project_instance_id"] == ctx.project_instance_id
                and run["project_id"] == ctx.project_id and plan["context_digest"] == ctx.context_digest
                and plan["job_id"] == run["job_id"] and plan["job_revision"] == run["job_revision"],
                "PROJECT_IDENTITY_MISMATCH", "Original identity binding differs")
        fixture = plan["process_fixture"]
        require(not fixture.get('managed_scope'),'UNSUPPORTED_EVIDENCE_POLICY',
                'Four recorded roles cannot reconcile an unresolved managed descendant scope')
        require(fixture.get("membership_contract") == MEMBERSHIP_CONTRACT
                and fixture.get("required_roles") == list(REQUIRED_ROLES) and fixture["max_process_members"] == 4
                and fixture["argument_policy"] == "isolated_python_fixture_v1" and fixture["scenario"] in SCENARIOS,
                "MEMBERSHIP_EVIDENCE_MISSING", "Historical plan does not establish the required fixed member set")
        events = _rows(connection, "events", run_id)
        require([e["run_sequence"] for e in events] == list(range(1, len(events) + 1))
                and all(e["run_id"] == run_id for e in events), "EVIDENCE_CONFLICT", "Attempt event history is incomplete")
        starts = [e for e in events if e["type"] == "START_INTENT"]
        accepts = [e for e in events if e["type"] == "REQUEST_ACCEPTED"]
        identities = [e for e in events if e["type"] == "PROCESS_IDENTITIES"]
        require(len(starts) == len(accepts) == len(identities) == 1
                and accepts[0]["run_sequence"] < starts[0]["run_sequence"] < identities[0]["run_sequence"],
                "MEMBERSHIP_EVIDENCE_MISSING", "Exactly one accepted, claimed and verified membership is required")
        receipt = connection.execute("SELECT body FROM receipts WHERE run_id=?", (run_id,)).fetchone()
        consumed = connection.execute("SELECT run_id FROM consumption WHERE grant_id=?", (run["grant_id"],)).fetchone()
        require(receipt is not None and consumed is not None and consumed[0] == run_id,
                "EVIDENCE_INSUFFICIENT", "Original acceptance and execution consumption are required")
        receipt = json.loads(receipt[0])
        require(receipt["run_id"] == run_id and receipt["job_id"] == run["job_id"], "EVIDENCE_CONFLICT", "Receipt mismatch")
        membership = identities[0]["payload"].get("process_membership")
        expected_binding = {k: run[k] for k in BINDING}
        require(membership is not None and all(membership.get(k) == v for k, v in expected_binding.items())
                and starts[0]["payload"]["owner_id"] == run["owner_id"]
                and starts[0]["payload"]["owner_epoch"] == run["owner_epoch"]
                and membership.get("contract") == MEMBERSHIP_CONTRACT
                and membership.get("required_roles") == list(REQUIRED_ROLES)
                and membership.get("backend_id") == BACKEND and membership.get("backend_version") == 1
                and membership.get("fixture_digest") == fixture["fixture_digest"]
                and membership.get("basis") == "FIXED_FIXTURE_ALL_ROLES_OS_VERIFIED_BEFORE_RELEASE"
                and run.get("process_membership") == membership,
                "MEMBERSHIP_EVIDENCE_MISSING", "No matching immutable verified membership basis")
        members = identities[0]["payload"]["process_records"]
        require(len(members) == 4 and {m["role"] for m in members} == set(REQUIRED_ROLES)
                and len({(m["pid"], m["creation_time_100ns"]) for m in members}) == 4
                and members == run["process_records"], "EVIDENCE_CONFLICT", "Required member identity mapping differs")
        for member in members:
            transport = member["role"].endswith("_transport")
            require(member["identity_status"] == "VERIFIED" and type(member["pid"]) is int and member["pid"] > 0
                    and type(member["creation_time_100ns"]) is int and member["creation_time_100ns"] > 0
                    and type(member["observed_at"]) is int
                    and member["image_path"] == fixture["interpreter" if transport else "image"]
                    and member["image_digest"] == fixture["interpreter_digest" if transport else "image_digest"]
                    and member["execution_object_digest"] == fixture["fixture_digest"],
                    "EVIDENCE_CONFLICT", "OS-verified member or execution identity is incomplete")
        exit_events = [e for e in events if e["type"] == "PROCESS_EXIT_OBSERVED"]
        require(len(exit_events) == 4, "EXIT_EVIDENCE_MISSING", "Every required member needs a persisted OS exit observation")
        previous = []
        for event in exit_events:
            observed = event["payload"]["process_exits"]
            require(len(observed) == len(previous) + 1 and observed[:-1] == previous
                    and event["run_sequence"] > identities[0]["run_sequence"], "EVIDENCE_CONFLICT", "Conflicting exit history")
            item = observed[-1]
            require(item["role"] not in {v["role"] for v in previous}
                    and all(item.get(k) == v for k, v in expected_binding.items())
                    and item.get("exit_contract") == EXIT_CONTRACT
                    and item["exit_source"] == "retained_windows_handle"
                    and type(item["exit_code"]) is int and 0 <= item["exit_code"] <= 0xffffffff
                    and type(item["exit_observed_at"]) is int
                    and item["observed_at"] <= item["exit_observed_at"] <= event["recorded_at"]
                    and any(all(item.get(k) == m.get(k) for k in IDENTITY) for m in members),
                    "EVIDENCE_CONFLICT", "Exit is not bound to the exact verified OS identity and attempt")
            previous = observed
        require(previous == run["process_exits"] and {e["role"] for e in previous} == set(REQUIRED_ROLES),
                "EVIDENCE_CONFLICT", "Current exit projection differs from immutable observations")
        validations = _rows(connection, "validations", run_id, 16)
        require(all(v["run_id"] == run_id and v["phase_attempt_id"] == run["phase_attempt_id"] for v in validations),
                "EVIDENCE_CONFLICT", "Historical validation belongs to another attempt")
        base["member_fingerprint"] = digest({"basis": membership, "members": members})
        base["evidence_fingerprint"] = digest({"run": run, "plan": plan, "events": events, "validations": validations,
                                                "receipt": receipt, "consumption": consumed[0]})
        base["source_refs"] = [accepts[0]["event_id"], starts[0]["event_id"], identities[0]["event_id"]] + [e["event_id"] for e in exit_events]
        base["recorded_exits"] = [{k: e[k] for k in ("role", "pid", "creation_time_100ns", "exit_code", "exit_observed_at", "exit_source")} for e in previous]
        base["historical_validations"] = [{k: v[k] for k in ("validation_id", "verdict", "recorded_at")} for v in validations]
        base["classification"] = "COMPLETED" if all(e["exit_code"] == 0 for e in previous) else "FAILED"
        base["candidate_action"] = RECONCILE_PROCESS
    except ExecutionError as exc:
        base["reasons"] = [{"code": exc.code, "message": str(exc)}]
    except (ValueError, KeyError, TypeError, IndexError):
        base["reasons"] = [{"code": "EVIDENCE_INSUFFICIENT", "message": "Required historical evidence was not recorded or is malformed"}]
    return {**base, "preview_digest": digest(base)}


def preview(service, context, run_id):
    from .reconciliation import _owner
    service._context(context)
    _owner(service)
    text(run_id)
    with service.store.read() as connection:
        connection.execute("BEGIN")
        return inspect(service, connection, run_id)


def apply_recorded(service, connection, request, operation_id, gate):
    current = inspect(service, connection, request["run_id"])
    require(current["run_revision"] == request["expected_run_revision"]
            and current["preview_digest"] == request["preview_digest"], "STALE_PREVIEW", "Recorded evidence, revision or owner changed")
    require(current["candidate_action"] == RECONCILE_PROCESS, "EVIDENCE_INSUFFICIENT", "No complete persisted exit candidate")
    require(all(request[k] == current[k] for k in SCOPE_FIELDS if k not in {"expected_run_revision", "preview_digest"}),
            "MANAGEMENT_SCOPE_MISMATCH", "Approved attempt or evidence scope differs")
    record = {"reconciliation_id": identifier("rec"), "operation_id": operation_id, "run_id": request["run_id"],
              "owner_id": service.store._session.owner_id, "recorded_at": now(), "action": RECONCILE_PROCESS,
              "source": "TEST_ONLY_RECORDED_OS_EXIT_RECONCILIATION", "policy": POLICY,
              "conclusion": "RECORDED_EXIT_SUCCESS" if current["classification"] == "COMPLETED" else "RECORDED_EXIT_FAILURE",
              "evidence_refs": current["source_refs"], "preview": current}
    connection.execute("INSERT INTO reconciliations VALUES(?,?,?)", (record["reconciliation_id"], request["run_id"], canonical_json(record)))
    refs = [record["reconciliation_id"], *current["source_refs"]]
    run = document(connection, "runs", "run_id", request["run_id"])
    updated = update_run(connection, run, "PROCESS_RECONCILIATION_APPLIED", evidence_refs=refs,
                         execution="FINISHED", reconciliation="NONE", backend_outcome=current["classification"],
                         backend_outcome_basis="RECONCILED_RECORDED_OS_EXITS", process_observation="EXIT_OBSERVED",
                         exit_verification="VERIFIED", solver_conclusion="NOT_RUN", reconciled_at=record["recorded_at"], error=None)
    connection.execute("UPDATE slot SET run_id=NULL WHERE id=1 AND run_id=?", (request["run_id"],))
    return refs, {"run_id": run["run_id"], "run_revision": updated["revision"], "gate": gate}
