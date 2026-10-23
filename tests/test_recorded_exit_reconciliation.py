"""Run007: positive exit facts always originate in a real Windows owner path."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import sqlite3

import pytest

from abqjobpilot.execution import ExecutionError, ExecutionService
from abqjobpilot.execution.models import canonical_json, now
from abqjobpilot.execution.process_reconciliation import RECONCILE_PROCESS as ACTION, SCOPE_FIELDS
from abqjobpilot.execution.reconciliation import ADOPT, RESUME
from abqjobpilot.execution.store import acquire_supervisor_store, document, update_run
from execution_helpers import inventory
from reconciliation_helpers import FakeManagementFixture, management_request
from supervisor_helpers import read_json, wait_until
from test_process_fixture import factory, assert_once
from test_reconciliation_supervisor import permit


def scope(preview):
    return {key: preview["run_revision"] if key == "expected_run_revision" else preview[key] for key in SCOPE_FIELDS}


def exited(h, stage="process:after_exit"):
    owner = h.owner(barriers=["process:after_identity", stage])
    receipt = h.client().submit(h.requests[0])["receipt"]
    rid = receipt["run_id"]
    owner.reached("process:after_identity")
    h.capture(rid)
    owner.release("process:after_identity")
    owner.reached(stage)
    recorded = h.client().run(rid)
    assert len(recorded["process_exits"]) == 4
    assert all(ref.exit_evidence() is not None for ref in h.references.values())
    if len(h.requests) > 1:
        h.pending = h.client().submit(h.requests[1])["receipt"]["run_id"]
    owner.terminate()
    return rid, receipt, recorded


@pytest.fixture
def local(factory):
    h = factory("normal", None)
    rid, receipt, recorded = exited(h)
    bootstrap = read_json(h.bootstrap)
    store = acquire_supervisor_store(h.context, bootstrap["authority_instance"])
    service = ExecutionService(h.context, store, client_namespace="stable-test-client")
    h.local_store, h.service, h.rid = store, service, rid
    yield h
    store.close()


def preview(h):
    return h.service.preview_process_reconciliation(h.context, h.rid)


def permission(h, value=None, key="finish", **overrides):
    value = preview(h) if value is None else value
    grant = FakeManagementFixture(h.local_store).issue(ACTION, scope(value), **overrides)
    return management_request(h.context, value["owner_id"], ACTION, scope(value), grant, key)


def apply(h, request):
    return h.service.apply_process_reconciliation(h.context, request)


def mutate(h, function):
    # Negative corruption/fault fixtures write only through the current exclusive owner.
    with h.local_store.transaction("negative_fixture") as connection:
        function(connection)


@pytest.mark.parametrize("scenario,outcome", [("normal", "COMPLETED"), ("nonzero", "FAILED"), ("invalid_result", "COMPLETED")])
def test_real_exit_commit_owner_crash_reconcile_and_separate_resume(factory, scenario, outcome):
    h = factory(scenario, None)
    owner = h.owner(barriers=["process:after_identity", "process:after_exit"])
    receipt = h.client().submit(h.requests[0])["receipt"]
    rid = receipt["run_id"]
    owner.reached("process:after_identity"); h.capture(rid)
    pending = h.client().submit(h.requests[1])["receipt"]["run_id"]
    owner.release("process:after_identity"); owner.reached("process:after_exit")
    before = h.client().run(rid)
    owner.terminate()
    fresh = h.owner(management_control=True)
    client = h.client()
    before_inventory = inventory(Path(h.context.root))
    p = client.preview_process_reconciliation(rid)
    assert p == client.preview_process_reconciliation(rid)
    assert inventory(Path(h.context.root)) == before_inventory
    assert p["candidate_action"] == ACTION and p["classification"] == outcome
    assert p["artifact_validation"] == "NOT_RUN" and p["historical_validations"] == []
    exports = h.root / "exports"; exports.mkdir()
    client.export_diagnostic(client.diagnose(rid), export_root=exports, target=exports / "before.json")
    denied = management_request(h.context, p["owner_id"], ACTION, scope(p), h.requests[0]["grant_id"], "execution-is-not-management")
    with pytest.raises(ExecutionError) as exc: client.apply_process_reconciliation(denied)
    assert exc.value.code == "MANAGEMENT_GRANT_REQUIRED"
    with pytest.raises(ExecutionError): client.call("preview_process_reconciliation", {"run_id": rid, "members_complete": True})
    request = permit(h, fresh, ACTION, scope(p), "recorded-exits")
    applied = client.apply_process_reconciliation(request)
    run = assert_once(h, rid)
    assert run["execution"] == "FINISHED" and run["backend_outcome"] == outcome
    assert run["artifact_validation"] == "NOT_RUN" and run["solver_conclusion"] == "NOT_RUN"
    assert run["phase_attempt_id"] == before["phase_attempt_id"] and run["process_exits"] == before["process_exits"]
    assert client.receipt("key-0") == receipt and client.dispatch_gate()["state"] == "PAUSED"
    assert client.run(pending)["execution"] == "PLANNED"
    report = client.diagnose(rid)
    assert "RECORDED_EXITS_RECONCILED" in [d["reason_code"] for d in report["body"]["diagnostics"]]
    assert report["body"]["facts"]["validations"] == []
    client.export_diagnostic(report, export_root=exports, target=exports / "after.json")
    resume = permit(h, fresh, RESUME, {"expected_gate_version": client.dispatch_gate()["version"]}, "resume")
    client.resume_dispatch(resume); h.finished(pending)
    assert_once(h, rid)
    (h.root / "reconciliation-evidence.json").write_text(canonical_json({"old_owner": owner.identity,
        "new_owner": fresh.identity, "persisted_before_crash": before, "preview": p, "receipt": applied,
        "persisted_after": run, "pending": pending}), encoding="utf-8")


def test_preview_readonly_no_probe_artifact_validator_or_observer(local, monkeypatch):
    h = local
    from abqjobpilot.execution import process_handles, process_validation, process_backend
    def trap(*args, **kwargs): raise AssertionError("Read-only evidence operation triggered a side effect")
    before = inventory(Path(h.context.root))
    with monkeypatch.context() as patch:
        patch.setattr(process_handles.ProcessReference, "__init__", trap)
        patch.setattr(process_validation, "validate_process_artifact", trap)
        patch.setattr(process_backend.ProcessBackend, "execute", trap)
        patch.setattr(threading.Thread, "start", trap)
        patch.setattr(h.local_store, "transaction", trap)
        original = Path.open
        def guarded(path, *args, **kwargs):
            assert "process_runs" not in path.parts
            return original(path, *args, **kwargs)
        patch.setattr(Path, "open", guarded)
        assert preview(h)["candidate_action"] == ACTION
    assert inventory(Path(h.context.root)) == before


@pytest.mark.parametrize("damage", ["worker_identity", "worker_exit", "membership", "pid_only", "different_attempt",
                                    "conflicting_exit", "extra_start", "projection", "legacy_contract"])
def test_incomplete_or_conflicting_required_set_rejected(local, damage):
    h = local
    def corrupt(c):
        run = document(c, "runs", "run_id", h.rid)
        if damage == "worker_identity": run["process_records"] = run["process_records"][:-1]
        if damage == "worker_exit":
            c.execute("DELETE FROM events WHERE event_id=(SELECT event_id FROM events WHERE run_id=? AND body LIKE '%PROCESS_EXIT_OBSERVED%' ORDER BY sequence DESC LIMIT 1)", (h.rid,))
        if damage == "membership": run.pop("process_membership")
        if damage == "pid_only": run["process_records"][0].pop("creation_time_100ns")
        if damage == "different_attempt": run["phase_attempt_id"] = "phase_wrong"
        if damage == "conflicting_exit":
            row = c.execute("SELECT event_id,body FROM events WHERE run_id=? AND body LIKE '%PROCESS_EXIT_OBSERVED%' ORDER BY sequence DESC LIMIT 1", (h.rid,)).fetchone()
            event = json.loads(row[1]); event["payload"]["process_exits"][0]["exit_code"] = 99
            c.execute("UPDATE events SET body=? WHERE event_id=?", (canonical_json(event), row[0]))
        if damage == "extra_start":
            from abqjobpilot.execution.store import append_event
            append_event(c, h.rid, "START_INTENT", {})
        if damage == "projection": run["process_exits"][0]["creation_time_100ns"] += 1
        if damage == "legacy_contract":
            run["process_membership"]["contract"] = "unrecorded"
        c.execute("UPDATE runs SET body=? WHERE run_id=?", (canonical_json(run), h.rid))
    mutate(h, corrupt)
    p = preview(h)
    assert p["candidate_action"] is None and p["reasons"]
    assert h.local_store.query_run(h.context, h.rid)["reconciliation_requirement"] == "RECONCILIATION_REQUIRED"
    assert h.local_store.gate()["state"] == "PAUSED"


@pytest.mark.parametrize("stage", ["process:after_identity", "process:after_handoff", "process:before_exit_record"])
def test_result_self_report_controller_exits_are_not_service_evidence(factory, stage):
    h = factory("result_wait" if stage != "process:before_exit_record" else "normal")
    owner = h.owner(barriers=["process:after_identity", stage])
    rid = h.client().submit(h.requests[0])["receipt"]["run_id"]
    owner.reached("process:after_identity"); h.capture(rid)
    if stage != "process:after_identity":
        owner.release("process:after_identity"); owner.reached(stage)
    if stage == "process:after_handoff": wait_until(lambda: (h.run_root(rid) / "result.json").exists())
    if stage == "process:before_exit_record": wait_until(lambda: all(r.exit_evidence() for r in h.references.values()))
    owner.terminate(); h.owner()
    assert h.client().preview_process_reconciliation(rid)["candidate_action"] is None
    assert h.client().run(rid)["reconciliation_requirement"] == "RECONCILIATION_REQUIRED"


@pytest.mark.parametrize("override", [{"action": ADOPT}, {"expires_at": 1}, {"owner_id": "owner_wrong"},
    {"grant_kind": "TEST_ONLY"}, {"max_uses": 2}, {"project_instance_id": "pi_wrong"}, {"scope": {}}])
def test_exact_management_authority_required(local, override):
    h = local; request = permission(h, **override)
    before = inventory(Path(h.context.root))
    with pytest.raises(ExecutionError): apply(h, request)
    assert inventory(Path(h.context.root)) == before


@pytest.mark.parametrize("field", ["target_state", "exit_code", "members_complete", "approved"])
def test_caller_cannot_supply_execution_facts(local, field):
    h = local; request = permission(h); request[field] = True
    with pytest.raises(ExecutionError) as exc: apply(h, request)
    assert exc.value.code == "INVALID_REQUEST"


@pytest.mark.parametrize("field", ["backend_id", "backend_version", "run_id", "plan_id", "phase_attempt_id", "evidence_fingerprint"])
def test_wrong_exact_scope_cannot_reinterpret_approved_operation(local, field):
    h = local; p = preview(h); p[field] = 2 if field == "backend_version" else "wrong"
    request = permission(h, p)
    with pytest.raises(ExecutionError): apply(h, request)
    assert h.local_store.reconciliations(h.context, h.rid) == []


@pytest.mark.parametrize("change", ["revision", "evidence", "owner"])
def test_changed_preview_preconditions_refused(local, change):
    h = local; request = permission(h)
    if change == "owner": request["owner_id"] = "owner_wrong"
    else:
        def change_record(c):
            run = document(c, "runs", "run_id", h.rid)
            if change == "revision": update_run(c, run, "RECONCILIATION_REQUIRED", reconciliation="RECONCILIATION_REQUIRED")
            else:
                run["process_exits"][0]["exit_code"] = 88
                c.execute("UPDATE runs SET body=? WHERE run_id=?", (canonical_json(run), h.rid))
        mutate(h, change_record)
    with pytest.raises(ExecutionError) as exc: apply(h, request)
    assert exc.value.code in {"STALE_PREVIEW", "STALE_OWNER"}


def test_concurrent_apply_conflict_replay_and_consumption(local):
    h = local; request = permission(h)
    old = h.local_store.query_run(h.context, h.rid)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: apply(h, request), range(4)))
    assert sum(not r["replayed"] for r in results) == 1
    assert all(r["receipt"] == results[0]["receipt"] for r in results)
    assert h.local_store.query_run(h.context, h.rid)["revision"] == old["revision"] + 1
    assert len(h.local_store.reconciliations(h.context, h.rid)) == 1
    with h.local_store.read() as c:
        assert c.execute("SELECT count(*) FROM consumption").fetchone()[0] == 2  # Original and accepted pending Run, unchanged.
        assert c.execute("SELECT count(*) FROM management_consumption").fetchone()[0] == 1
    with pytest.raises(ExecutionError) as exc: apply(h, {**request, "phase_attempt_id": "phase_other"})
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
    assert h.local_store.gate()["state"] == "PAUSED"


@pytest.mark.parametrize("stage", ["management:before_commit", "management:after_commit"])
def test_atomic_management_failure_and_unknown_commit(local, stage):
    h = local; request = permission(h); before = h.local_store.events(h.context)
    def fail(point):
        if point == stage: raise OSError("injected commit boundary")
    h.local_store._checkpoint = fail
    with pytest.raises(ExecutionError) as exc: apply(h, request)
    h.local_store._checkpoint = lambda _: None
    if stage.endswith("before_commit"):
        assert h.local_store.events(h.context) == before
        assert h.local_store.reconciliations(h.context, h.rid) == []
        assert preview(h)["candidate_action"] == ACTION
    else:
        assert exc.value.code == "ACCEPTANCE_UNKNOWN"
        original = h.local_store.management_receipt("stable-test-client", ACTION, "finish")
        assert apply(h, request)["receipt"] == original
    assert h.local_store.gate()["state"] == "PAUSED"


def test_lost_management_response_and_new_owner_replay(factory):
    h = factory("normal")
    rid, original, _ = exited(h)
    owner = h.owner(management_control=True, barriers=["management:before_response"])
    p = h.client().preview_process_reconciliation(rid)
    request = permit(h, owner, ACTION, scope(p), "lost-reply")
    child = h.spawn("client", operation="apply_process_reconciliation", arguments={"request": request})
    owner.reached("management:before_response")
    receipt = h.client().management_receipt(ACTION, "lost-reply")
    child.terminate(); owner.release("management:before_response")
    assert h.client().apply_process_reconciliation(request)["receipt"] == receipt
    owner.terminate(); h.owner()
    client = h.client(); before = inventory(Path(h.context.root))
    assert client.apply_process_reconciliation(request)["receipt"] == receipt
    assert inventory(Path(h.context.root)) == before
    assert client.receipt("key-0") == original and client.dispatch_gate()["state"] == "PAUSED"
    assert len(client.reconciliations(rid)) == 1
    with pytest.raises(ExecutionError) as exc:
        client.apply_process_reconciliation({**request, "idempotency_key": "new-not-authorized"})
    assert exc.value.code == "STALE_OWNER"
    assert_once(h, rid)


def test_apply_never_probes_or_validates_and_expired_execution_grant_is_history(local, monkeypatch):
    h = local
    from abqjobpilot.execution import authorization
    later = now() + 7201
    request = permission(h, expires_at=later + 3600)
    monkeypatch.setattr(authorization, "now", lambda: later)
    from abqjobpilot.execution import process_handles, process_validation, process_backend, reconciliation
    def trap(*args, **kwargs): raise AssertionError("Recorded exit reconciliation must have no external observation")
    with monkeypatch.context() as patch:
        patch.setattr(process_handles.ProcessReference, "__init__", trap)
        patch.setattr(process_validation, "validate_process_artifact", trap)
        patch.setattr(process_backend.ProcessBackend, "execute", trap)
        patch.setattr(reconciliation, "_snapshot", trap)
        patch.setattr(threading.Thread, "start", trap)
        original_open = Path.open
        def guarded(path, *args, **kwargs):
            assert "process_runs" not in path.parts
            return original_open(path, *args, **kwargs)
        patch.setattr(Path, "open", guarded)
        apply(h, request)
    assert h.local_store.validations(h.context, h.rid) == []


@pytest.mark.parametrize("verdict,status", [("PASS", "VALID"), ("FAIL", "INVALID"), ("UNKNOWN", "UNKNOWN")])
def test_existing_independent_validation_preserved_without_revalidation(local, monkeypatch, verdict, status):
    h = local
    # Negative/history-preservation fixture only: genuine OS exit qualification was
    # already produced by exited(). No fixture inserts identities or exit facts.
    artifact = h.run_root(h.rid) / "result.json"
    if verdict == "FAIL": artifact.write_text("invalid fixture artifact", encoding="utf-8")
    if verdict == "UNKNOWN": artifact.unlink()
    from abqjobpilot.execution import process_validation
    with h.local_store.read() as c:
        run = document(c, "runs", "run_id", h.rid); plan = document(c, "plans", "plan_id", run["plan_id"])
    observation, validation = process_validation.validate_process_artifact(h.context, plan, run)
    assert validation["verdict"] == verdict
    def history(c):
        c.execute("INSERT INTO observations VALUES(?,?,?)", (observation["observation_id"], h.rid, canonical_json(observation)))
        c.execute("INSERT INTO validations VALUES(?,?,?)", (validation["validation_id"], h.rid, canonical_json(validation)))
        update_run(c, document(c, "runs", "run_id", h.rid), "VALIDATION_RECORDED", artifact_validation=status,
                   evidence_refs=[validation["validation_id"], observation["observation_id"]])
    mutate(h, history)  # Explicit test-only history setup through the held owner, not a product validation API.
    def trap(*args, **kwargs): raise AssertionError("Must preserve historical validation")
    monkeypatch.setattr(process_validation, "validate_process_artifact", trap)
    p = preview(h)
    assert p["historical_validations"] == [{k: validation[k] for k in ("validation_id", "verdict", "recorded_at")}]
    apply(h, permission(h, p))
    assert h.local_store.validations(h.context, h.rid) == [validation]
    assert h.local_store.query_run(h.context, h.rid)["artifact_validation"] == status
    exports = h.root / "exports"; exports.mkdir()
    from abqjobpilot.execution.client import FakeClient
    FakeClient.export_diagnostic(h.local_store.diagnose(h.context, h.rid), export_root=exports, target=exports / (status + ".json"))


def test_preview_consistent_read_transaction_and_serialized_owner_writer(local, monkeypatch):
    h = local
    from abqjobpilot.execution import process_reconciliation as module
    read_started, writer_started, writer_entered = threading.Event(), threading.Event(), threading.Event()
    real_document = module.document
    def read_document(c, table, key, value):
        result = real_document(c, table, key, value)
        if table == "runs":
            assert c.in_transaction and c.execute("PRAGMA query_only").fetchone()[0] == 1
            read_started.set(); assert writer_started.wait(3)
            assert not writer_entered.is_set()
        return result
    monkeypatch.setattr(module, "document", read_document)
    def write():
        assert read_started.wait(3); writer_started.set()
        with h.local_store.transaction("concurrent_owner") as c:
            writer_entered.set()
            run = document(c, "runs", "run_id", h.rid)
            update_run(c, run, "RECONCILIATION_REQUIRED", reconciliation="RECONCILIATION_REQUIRED")
            c.execute("UPDATE dispatch_gate SET version=version+1")
    old = h.local_store.query_run(h.context, h.rid)
    gate = h.local_store.gate()
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(write); p = preview(h); task.result(timeout=3)
    monkeypatch.setattr(module, "document", real_document)
    after = preview(h)
    assert p["candidate_action"] == ACTION and p["run_revision"] == old["revision"] and p["gate"] == gate
    assert after["run_revision"] == p["run_revision"] + 1 and after["gate"]["version"] == gate["version"] + 1
    assert after["preview_digest"] != p["preview_digest"]


def test_unknown_sql_commit_queries_original_key(local, monkeypatch):
    h = local; request = permission(h)
    import abqjobpilot.execution.store as stores
    original = stores._connection
    class UnknownCommit:
        def __init__(self, inner): self.inner = inner
        def __getattr__(self, key): return getattr(self.inner, key)
        def commit(self):
            self.inner.commit()
            raise sqlite3.OperationalError("commit acknowledgement lost")
    def connection(context, *, read_only, **kwargs):
        inner = original(context, read_only=read_only, **kwargs)
        return inner if read_only else UnknownCommit(inner)
    monkeypatch.setattr(stores, "_connection", connection)
    with pytest.raises(ExecutionError) as exc: apply(h, request)
    assert exc.value.code == "ACCEPTANCE_UNKNOWN"
    monkeypatch.setattr(stores, "_connection", original)
    receipt = h.local_store.management_receipt("stable-test-client", ACTION, "finish")
    assert apply(h, request)["receipt"] == receipt
    assert len(h.local_store.reconciliations(h.context, h.rid)) == 1


def test_other_unresolved_run_still_blocks_resume(local):
    h = local
    # Negative corruption fixture models another unresolved accepted Run. It does
    # not create a reconciliation candidate or allow that Run to execute.
    def occupied(c):
        other = document(c, "runs", "run_id", h.pending)
        update_run(c, other, "RECONCILIATION_REQUIRED", reconciliation="RECONCILIATION_REQUIRED")
    mutate(h, occupied)
    apply(h, permission(h))
    gate = h.local_store.gate()
    s = {"expected_gate_version": gate["version"]}
    grant = FakeManagementFixture(h.local_store).issue(RESUME, s)
    req = management_request(h.context, gate["owner_id"], RESUME, s, grant, "blocked-resume")
    with pytest.raises(ExecutionError) as exc: h.service.resume_dispatch(h.context, req)
    assert exc.value.code == "RECONCILIATION_REQUIRED" and h.local_store.gate()["state"] == "PAUSED"


@pytest.mark.parametrize("kind", ["events", "oversize", "journal"])
def test_preview_bound_and_maintenance_no_repair(local, kind):
    h = local
    if kind == "journal":
        path = Path(h.context.execution_store + "-journal"); path.write_bytes(b"explicit maintenance fixture")
        before = inventory(Path(h.context.root))
        with pytest.raises(ExecutionError) as exc: preview(h)
        assert exc.value.code == "STORE_REQUIRES_MAINTENANCE"
        assert inventory(Path(h.context.root)) == before
        path.unlink()  # Only this test's sidecar; no product repair.
    else:
        def corrupt(c):
            from abqjobpilot.execution.store import append_event
            for _ in range(65 if kind == "events" else 1):
                append_event(c, h.rid, "TEST_OVERSIZE", {"value": "x" * (17000 if kind == "oversize" else 1)})
        mutate(h, corrupt)
        p = preview(h)
        assert p["candidate_action"] is None and p["reasons"][0]["code"] == "LIMIT_EXCEEDED"
