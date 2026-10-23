from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import sqlite3

import pytest

from abqjobpilot.execution import ExecutionError, ExecutionService, open_existing_read_only
from abqjobpilot.execution.fake_backend import FakeBackend
from abqjobpilot.execution.models import canonical_json, digest, now
from abqjobpilot.execution.reconciliation import ADOPT, RESUME
from abqjobpilot.execution.store import acquire_supervisor_store, document, update_run
from execution_helpers import guard_environment, harness, inventory
from reconciliation_helpers import FakeManagementFixture, adoption_scope, management_request


@pytest.fixture
def uncertain(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    h.original_receipt = receipt
    h.run_id = receipt["run_id"]
    h.artifact = Path(h.context.runtime_root) / "fake_runs" / h.run_id / "result.json"
    h.effects = []
    original = FakeBackend.emit
    def counted(backend, *args):
        h.effects.append(args[2]["run_id"])
        return original(backend, *args)
    monkeypatch.setattr(FakeBackend, "emit", counted)
    def fault(name):
        if name == "dispatch:after_artifact":
            raise OSError("test crash window")
    monkeypatch.setattr(h.store, "_checkpoint", fault)
    with pytest.raises(ExecutionError):
        h.service.execute_pending(h.context, h.run_id)
    monkeypatch.setattr(h.store, "_checkpoint", lambda name: None)
    h.store.pause_after_error()
    return h


def adoption(h, key="adopt-1", **grant_overrides):
    preview = h.service.preview_reconciliation(h.context, h.run_id)
    scope = adoption_scope(preview)
    grant = FakeManagementFixture(h.store).issue(ADOPT, scope, **grant_overrides)
    return management_request(h.context, h.store._session.owner_id, ADOPT, scope, grant, key)


def resume(h, key="resume-1", **grant_overrides):
    scope = {"expected_gate_version": h.store.gate()["version"]}
    grant = FakeManagementFixture(h.store).issue(RESUME, scope, **grant_overrides)
    return management_request(h.context, h.store._session.owner_id, RESUME, scope, grant, key)


def test_preview_is_readonly_deterministic_and_adoption_appends_bound_evidence(uncertain):
    h = uncertain
    before = inventory(h.root)
    p = h.service.preview_reconciliation(h.context, h.run_id)
    assert p == h.service.preview_reconciliation(h.context, h.run_id)
    assert p["candidate_action"] == ADOPT and p["evidence_fingerprint"]["expected_digest"]
    assert inventory(h.root) == before
    assert not (Path(h.context.runtime_root) / "reconciliation_evidence").exists()
    prior_events = h.store.events(h.context)
    original = h.artifact.read_bytes()
    request = adoption(h)
    answer = h.service.apply_reconciliation(h.context, request)
    assert answer["operation_status"] == "APPLIED" and not answer["replayed"]
    assert h.effects == [h.run_id] and h.artifact.read_bytes() == original
    assert h.store.query_receipt(h.context, "test-client", "request-1") == h.original_receipt
    run = h.store.query_run(h.context, h.run_id)
    assert run["run_id"] == h.run_id and run["attempt_no"] == 1
    assert run["backend_outcome_basis"] == "RECONCILED_FIXED_ARTIFACT"
    assert run["error"] is None
    assert run["solver_conclusion"] == "NOT_RUN" and run["reconciliation_requirement"] == "NONE"
    assert h.store.events(h.context)[:-1] == prior_events
    assert h.store.events(h.context)[-1]["type"] == "RECONCILIATION_APPLIED"
    record = h.store.reconciliations(h.context, h.run_id)[0]
    assert Path(record["snapshot"]["path"]).read_bytes() == original
    assert record["conclusion"] == "FIXED_FAKE_COMPLETION_INFERRED_NOW"
    assert h.store.validations(h.context, h.run_id)[0]["source"] == "explicit_reconciliation"
    assert h.store.gate()["state"] == "PAUSED"
    # Later source replacement cannot alter the content that was actually validated.
    h.artifact.write_text("changed after apply", encoding="utf-8")
    assert Path(record["snapshot"]["path"]).read_bytes() == original


@pytest.mark.parametrize("damage", ["missing", "malformed", "run_id", "plan_digest", "phase_attempt_id", "config_digest", "input_digests", "format", "oversize"])
def test_bad_artifact_cannot_be_adopted_or_recreated(uncertain, damage):
    h = uncertain
    if damage == "missing":
        h.artifact.unlink()
    elif damage in {"malformed", "oversize"}:
        h.artifact.write_text("not-json" if damage == "malformed" else "x" * 65537, encoding="utf-8")
    else:
        body = json.loads(h.artifact.read_text())
        body[damage] = ["wrong"] if damage == "input_digests" else "wrong"
        h.artifact.write_text(canonical_json(body), encoding="utf-8")
    p = h.service.preview_reconciliation(h.context, h.run_id)
    assert p["candidate_action"] is None and p["reasons"]
    request = adoption(h)
    before = inventory(h.root)
    with pytest.raises(ExecutionError) as exc:
        h.service.apply_reconciliation(h.context, request)
    assert exc.value.code == "EVIDENCE_INSUFFICIENT"
    assert inventory(h.root) == before and h.effects == [h.run_id]
    assert h.store.query_run(h.context, h.run_id)["reconciliation_requirement"] == "RECONCILIATION_REQUIRED"


@pytest.mark.parametrize("change", ["output_policy", "backend_id", "backend_version", "validation_policy", "canonicalization"])
def test_unsupported_plan_rejected_before_artifact_read(uncertain, monkeypatch, change):
    h = uncertain
    with h.store.transaction("test_fixture") as c:
        run = document(c, "runs", "run_id", h.run_id)
        plan = document(c, "plans", "plan_id", run["plan_id"])
        plan[change] = {"root": str(h.root.parent / "do-not-read")} if change == "output_policy" else "unsupported"
        plan["plan_digest"] = digest({k: v for k, v in plan.items() if k != "plan_digest"})
        c.execute("UPDATE plans SET body=? WHERE plan_id=?", (canonical_json(plan), plan["plan_id"]))
        run["plan_digest"] = plan["plan_digest"]
        c.execute("UPDATE runs SET body=? WHERE run_id=?", (canonical_json(run), h.run_id))
    original = Path.open
    def guard(path, *args, **kwargs):
        assert path != h.artifact, "Unsupported contract must be rejected before artifact IO"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guard)
    p = h.service.preview_reconciliation(h.context, h.run_id)
    assert p["candidate_action"] is None
    assert p["reasons"][0]["code"] in {"OUTPUT_SCOPE_VIOLATION", "UNSUPPORTED_EVIDENCE_POLICY"}


@pytest.mark.parametrize("change", ["artifact", "revision", "gate", "owner"])
def test_preview_change_invalidates_submission(uncertain, change):
    h = uncertain
    request = adoption(h)
    if change == "artifact":
        h.artifact.write_text("changed", encoding="utf-8")
    elif change == "revision":
        with h.store.transaction("fixture") as c:
            update_run(c, document(c, "runs", "run_id", h.run_id), "FIXTURE_REVISION", fixture=True)
    elif change == "gate":
        with h.store.transaction("fixture") as c:
            c.execute("UPDATE dispatch_gate SET version=version+1")
    else:
        authority = h.store._session.authority_instance
        h.store.close()
        h.store = acquire_supervisor_store(h.context, authority)
        h.service = ExecutionService(h.context, h.store, client_namespace="test-client")
    before = inventory(h.root)
    try:
        with pytest.raises(ExecutionError) as exc:
            h.service.apply_reconciliation(h.context, request)
        assert exc.value.code in {"STALE_PREVIEW", "STALE_OWNER"}
        assert inventory(h.root) == before
    finally:
        if change == "owner":
            h.store.close()


@pytest.mark.parametrize("override", [{"expires_at": 0}, {"owner_id": "wrong"}, {"project_instance_id": "wrong"},
    {"action": RESUME}, {"grant_kind": "TEST_ONLY"}, {"scope": {}}, {"max_uses": 2}, {"authority_instance": "wrong"}])
def test_management_grant_exact_scope_and_expiry_required(uncertain, override):
    h = uncertain
    request = adoption(h, **override)
    before = inventory(h.root)
    with pytest.raises(ExecutionError) as exc:
        h.service.apply_reconciliation(h.context, request)
    assert exc.value.code in {"MANAGEMENT_SCOPE_MISMATCH", "MANAGEMENT_GRANT_EXPIRED"}
    assert inventory(h.root) == before


@pytest.mark.parametrize("extra", [{"approved": True}, {"role": "admin"}, {"target_state": "FINISHED"}])
def test_self_attested_management_fields_rejected(uncertain, extra):
    h = uncertain
    request = {**adoption(h), **extra}
    before = inventory(h.root)
    with pytest.raises(ExecutionError) as exc:
        h.service.apply_reconciliation(h.context, request)
    assert exc.value.code == "INVALID_REQUEST" and inventory(h.root) == before


@pytest.mark.parametrize("grant", ["missing", "execution_grant"])
def test_execution_grant_cannot_replace_management_permission(uncertain, grant):
    h = uncertain
    request = adoption(h)
    request["management_grant_id"] = "missing" if grant == "missing" else h.store.query_run(h.context, h.run_id)["grant_id"]
    with pytest.raises(ExecutionError) as exc:
        h.service.apply_reconciliation(h.context, request)
    assert exc.value.code == "MANAGEMENT_GRANT_REQUIRED"


def test_concurrent_apply_idempotency_conflict_and_consumption(uncertain):
    h = uncertain
    request = adoption(h)
    with ThreadPoolExecutor(max_workers=6) as pool:
        answers = list(pool.map(lambda _: h.service.apply_reconciliation(h.context, request), range(6)))
    assert sum(not r["replayed"] for r in answers) == 1
    assert all(r["receipt"] == answers[0]["receipt"] for r in answers)
    before = inventory(h.root)
    assert h.service.apply_reconciliation(h.context, request)["replayed"]
    with pytest.raises(ExecutionError) as exc:
        h.service.apply_reconciliation(h.context, {**request, "expected_run_revision": 999})
    assert exc.value.code == "IDEMPOTENCY_CONFLICT" and inventory(h.root) == before
    with h.store.read() as c:
        assert c.execute("SELECT COUNT(*) FROM management_consumption").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM consumption").fetchone()[0] == 1
    assert len(h.store.reconciliations(h.context, h.run_id)) == 1


@pytest.mark.parametrize("stage", ["reconciliation:before_snapshot", "reconciliation:after_snapshot", "management:before_commit", "management:after_commit"])
def test_snapshot_and_commit_failures_preserve_truth_and_receipt(uncertain, monkeypatch, stage):
    h = uncertain
    request = adoption(h)
    prior = h.store.events(h.context)
    def fault(name):
        if name == stage:
            raise OSError("explicit fault")
    monkeypatch.setattr(h.store, "_checkpoint", fault)
    with pytest.raises(ExecutionError) as exc:
        h.service.apply_reconciliation(h.context, request)
    monkeypatch.setattr(h.store, "_checkpoint", lambda name: None)
    assert h.effects == [h.run_id]
    if stage == "management:after_commit":
        assert exc.value.code == "ACCEPTANCE_UNKNOWN"
        receipt = h.store.management_receipt("test-client", ADOPT, "adopt-1")
        assert h.service.apply_reconciliation(h.context, request)["receipt"] == receipt
    else:
        assert h.store.events(h.context) == prior and h.store.reconciliations(h.context, h.run_id) == []
        with pytest.raises(ExecutionError):
            h.store.management_receipt("test-client", ADOPT, "adopt-1")
        orphans = list((Path(h.context.runtime_root) / "reconciliation_evidence").glob("*.json"))
        assert len(orphans) == (0 if stage == "reconciliation:before_snapshot" else 1)
        before = inventory(h.root)
        h.service.preview_reconciliation(h.context, h.run_id)
        assert inventory(h.root) == before
    assert h.store.gate()["state"] == "PAUSED"


def test_resume_separate_from_adoption_pending_revalidated_and_replay_no_reopen(uncertain):
    h = uncertain
    # The explicit paused gate prevents new submissions; pre-existing pending is
    # created in the separate test below. Resume itself changes only the gate.
    denied = resume(h, "denied")
    with pytest.raises(ExecutionError) as exc:
        h.service.resume_dispatch(h.context, denied)
    assert exc.value.code == "RECONCILIATION_REQUIRED"
    h.service.apply_reconciliation(h.context, adoption(h))
    assert h.store.gate()["state"] == "PAUSED"
    request = resume(h)
    answer = h.service.resume_dispatch(h.context, request)
    assert h.store.gate()["state"] == "OPEN" and h.effects == [h.run_id]
    assert h.service.resume_dispatch(h.context, request)["receipt"] == answer["receipt"]
    authority = h.store._session.authority_instance
    h.store.close()
    store = acquire_supervisor_store(h.context, authority)
    try:
        service = ExecutionService(h.context, store, client_namespace="test-client")
        before = inventory(h.root)
        assert service.resume_dispatch(h.context, request)["receipt"] == answer["receipt"]
        assert store.gate()["state"] == "PAUSED" and inventory(h.root) == before
    finally:
        store.close()


@pytest.mark.parametrize("change", ["input", "configuration", "grant_expired", "plan_expired", "authority"])
def test_pending_does_not_revive_stale_plan_or_grant_after_resume(harness, change):
    h = harness
    _, _, receipt = h.accept()
    h.store.pause_after_error()
    if change == "input":
        h.input.write_text("changed", encoding="utf-8")
    else:
        with h.store.transaction("fixture") as c:
            if change == "configuration":
                c.execute("UPDATE configuration SET body='{}'")
            elif change in {"grant_expired", "authority"}:
                grant = json.loads(c.execute("SELECT body FROM grants").fetchone()[0])
                grant["expires_at" if change == "grant_expired" else "authority_instance"] = 0 if change == "grant_expired" else "wrong"
                c.execute("UPDATE grants SET body=?", (canonical_json(grant),))
            else:
                plan = json.loads(c.execute("SELECT body FROM plans").fetchone()[0])
                plan["expires_at"] = 0
                plan["plan_digest"] = digest({k: v for k, v in plan.items() if k != "plan_digest"})
                c.execute("UPDATE plans SET body=?", (canonical_json(plan),))
    with h.store.read() as c:
        original_consumption = [tuple(r) for r in c.execute("SELECT * FROM consumption")]
    h.service.resume_dispatch(h.context, resume(h))
    with pytest.raises(ExecutionError):
        h.service.execute_pending(h.context, receipt["run_id"])
    assert h.store.query_run(h.context, receipt["run_id"])["queue_state"] == "BLOCKED"
    assert not list(Path(h.context.runtime_root).rglob("result.json"))
    with h.store.read() as c:
        assert [tuple(r) for r in c.execute("SELECT * FROM consumption")] == original_consumption


def test_historical_plan_is_used_without_reading_new_input_or_configuration(uncertain, monkeypatch):
    h = uncertain
    h.input.unlink()
    with h.store.transaction("fixture") as c:
        c.execute("UPDATE configuration SET body='{}'")
    original = Path.open
    def guard(path, *args, **kwargs):
        assert path != h.input
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guard)
    assert h.service.preview_reconciliation(h.context, h.run_id)["candidate_action"] == ADOPT
    h.service.apply_reconciliation(h.context, adoption(h))
    assert h.effects == [h.run_id]


@pytest.mark.parametrize("missing", ["claim", "accept", "consumption", "historical_inputs"])
def test_missing_historical_evidence_never_infers_completion(uncertain, missing):
    h = uncertain
    with h.store.transaction("fixture") as c:
        if missing in {"claim", "accept"}:
            kind = "START_INTENT" if missing == "claim" else "REQUEST_ACCEPTED"
            for row in c.execute("SELECT sequence,body FROM events").fetchall():
                if json.loads(row[1])["type"] == kind:
                    c.execute("DELETE FROM events WHERE sequence=?", (row[0],))
        elif missing == "consumption":
            c.execute("DELETE FROM consumption")
        else:
            run = document(c, "runs", "run_id", h.run_id)
            plan = document(c, "plans", "plan_id", run["plan_id"])
            plan["input_manifest"] = []
            plan["plan_digest"] = digest({k: v for k, v in plan.items() if k != "plan_digest"})
            c.execute("UPDATE plans SET body=?", (canonical_json(plan),))
            run["plan_digest"] = plan["plan_digest"]
            c.execute("UPDATE runs SET body=?", (canonical_json(run),))
    before = inventory(h.root)
    p = h.service.preview_reconciliation(h.context, h.run_id)
    assert p["candidate_action"] is None and p["reasons"][0]["code"] == "EVIDENCE_INSUFFICIENT"
    assert inventory(h.root) == before and h.effects == [h.run_id]


def test_concurrent_distinct_keys_cannot_adopt_same_revision_twice(uncertain):
    h = uncertain
    requests = [adoption(h, key="adopt-" + str(i)) for i in range(2)]
    def attempt(request):
        try:
            return h.service.apply_reconciliation(h.context, request)
        except ExecutionError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        answers = list(pool.map(attempt, requests))
    assert sum(type(a) is dict for a in answers) == 1 and "STALE_PREVIEW" in answers
    assert len(h.store.reconciliations(h.context, h.run_id)) == 1
    assert len(list((Path(h.context.runtime_root) / "reconciliation_evidence").glob("*.json"))) == 1


@pytest.mark.parametrize("condition", ["missing", "expired", "wrong_action", "wrong_gate", "wrong_owner", "approved"])
def test_resume_requires_distinct_exact_management_permission(uncertain, condition):
    h = uncertain
    h.service.apply_reconciliation(h.context, adoption(h))
    if condition == "expired":
        request = resume(h, expires_at=0)
    elif condition == "wrong_action":
        request = resume(h, action=ADOPT)
    else:
        request = resume(h)
        if condition == "missing":
            request["management_grant_id"] = "missing"
        elif condition == "wrong_owner":
            request["owner_id"] = "other"
        elif condition == "wrong_gate":
            with h.store.transaction("fixture") as c:
                c.execute("UPDATE dispatch_gate SET version=version+1")
        else:
            request["approved"] = True
    before = inventory(h.root)
    with pytest.raises(ExecutionError):
        h.service.resume_dispatch(h.context, request)
    assert h.store.gate()["state"] == "PAUSED" and inventory(h.root) == before


def test_resume_atomic_idempotency_conflict_and_receipt_is_not_gate_view(uncertain):
    h = uncertain
    h.service.apply_reconciliation(h.context, adoption(h))
    request = resume(h)
    with ThreadPoolExecutor(max_workers=5) as pool:
        replies = list(pool.map(lambda _: h.service.resume_dispatch(h.context, request), range(5)))
    assert sum(not r["replayed"] for r in replies) == 1
    assert all(r["receipt"] == replies[0]["receipt"] for r in replies)
    with pytest.raises(ExecutionError) as exc:
        h.service.resume_dispatch(h.context, {**request, "expected_gate_version": 999})
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
    with h.store.read() as c:
        assert c.execute("SELECT COUNT(*) FROM control_events").fetchone()[0] == 1


def test_query_and_management_refuse_maintenance_without_repair(uncertain):
    h = uncertain
    request = adoption(h)
    Path(h.context.execution_store + "-journal").write_bytes(b"test sidecar")
    before = inventory(h.root)
    for operation in (lambda: h.service.preview_reconciliation(h.context, h.run_id),
                      lambda: h.service.apply_reconciliation(h.context, request), h.store.gate):
        with pytest.raises(ExecutionError) as exc:
            operation()
        assert exc.value.code == "STORE_REQUIRES_MAINTENANCE"
    assert inventory(h.root) == before


def test_real_junction_artifact_is_refused_before_read(uncertain, monkeypatch):
    from test_execution_isolation import _junction
    h = uncertain
    target = h.root / "target"
    target.mkdir()
    (target / "result.json").write_bytes(h.artifact.read_bytes())
    h.artifact.unlink()
    h.artifact.parent.rmdir()
    _junction(h.artifact.parent, target)
    original = Path.open
    def guarded(path, *args, **kwargs):
        assert path not in {h.artifact, target / "result.json"}
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    p = h.service.preview_reconciliation(h.context, h.run_id)
    assert p["reasons"][0]["code"] == "OUTPUT_SCOPE_VIOLATION" and p["candidate_action"] is None


def test_format_two_readonly_compatible_but_management_rejected(harness):
    h = harness
    _, _, receipt = h.accept()
    h.store.close()
    path = Path(h.context.root) / "experiment.json"
    manifest = json.loads(path.read_text())
    manifest["schema_version"] = 2
    path.write_text(canonical_json(manifest), encoding="utf-8")
    old_context = replace(h.context, schema_version=2, manifest_digest=digest(manifest))
    with sqlite3.connect(h.context.execution_store) as c:
        c.execute("UPDATE meta SET value='2' WHERE key='schema'")
        c.execute("UPDATE meta SET value=? WHERE key='context_digest'", (old_context.context_digest,))
        for table in ("management_consumption", "management_receipts", "management_grants", "reconciliations", "control_events", "dispatch_gate"):
            c.execute("DROP TABLE " + table)
    before = inventory(h.root)
    assert open_existing_read_only(old_context).query_receipt(old_context, "test-client", "request-1") == receipt
    with pytest.raises(ExecutionError) as error:
        acquire_supervisor_store(old_context, "unused")
    assert error.value.code == "UNSUPPORTED_FORMAT" and inventory(h.root) == before


def test_hardlinked_artifact_is_not_accepted(uncertain):
    h = uncertain
    (h.root / "shared.json").hardlink_to(h.artifact)
    before = inventory(h.root)
    p = h.service.preview_reconciliation(h.context, h.run_id)
    assert p["candidate_action"] is None and p["reasons"][0]["code"] == "OUTPUT_SCOPE_VIOLATION"
    assert inventory(h.root) == before


def test_management_commit_ack_unknown_is_resolved_by_original_key(uncertain, monkeypatch):
    import abqjobpilot.execution.store as stores
    h = uncertain
    request = adoption(h)
    original = stores._connection
    class UnknownCommit:
        def __init__(self, connection):
            self.connection = connection
        def __getattr__(self, name):
            return getattr(self.connection, name)
        def commit(self):
            self.connection.commit()
            raise sqlite3.OperationalError("acknowledgement lost after commit")
    def connection(context, *, read_only):
        inner = original(context, read_only=read_only)
        return inner if read_only else UnknownCommit(inner)
    monkeypatch.setattr(stores, "_connection", connection)
    with pytest.raises(ExecutionError) as error:
        h.service.apply_reconciliation(h.context, request)
    assert error.value.code == "ACCEPTANCE_UNKNOWN"
    monkeypatch.setattr(stores, "_connection", original)
    receipt = h.store.management_receipt("test-client", ADOPT, "adopt-1")
    assert h.service.apply_reconciliation(h.context, request)["receipt"] == receipt
    assert h.effects == [h.run_id] and len(h.store.reconciliations(h.context, h.run_id)) == 1
