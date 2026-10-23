"""Run008 public adapters, reusing real R7 exit evidence instead of synthetic success."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

from abqjobpilot.execution import ExecutionError
from abqjobpilot.execution.models import now
from abqjobpilot.execution.public_workflow import VALIDATE
from abqjobpilot.execution.test_authority import issue_process_execution, issue_validation
from execution_helpers import harness, inventory
from test_process_contract import process_plan
from test_process_fixture import factory
from test_recorded_exit_reconciliation import local, permission, apply


@pytest.fixture
def guard_environment(monkeypatch):
    import execution_helpers
    execution_helpers.guard_environment.__wrapped__(monkeypatch)


def finish(h):
    apply(h, permission(h))
    return issue_validation(h.service, h.rid, expires_at=now() + 120)


def test_plan_inspection_readonly_and_public_projection(harness, monkeypatch):
    h = harness; plan = process_plan(h).to_dict()
    before = inventory(h.root)
    def trap(*a, **kw): raise AssertionError("inspection must not prepare, approve or write")
    monkeypatch.setattr(h.store, "transaction", trap)
    result = h.service.inspect_plan(h.context, plan["plan_id"], plan["plan_digest"])
    assert result["plan_digest"] == plan["plan_digest"] and result["required_roles"] == plan["process_fixture"]["required_roles"]
    assert str(h.root) not in json.dumps(result) and "interpreter" not in result
    assert "not_current_input_or_permission_preflight" in result["inspection_basis"]
    assert inventory(h.root) == before
    with pytest.raises(ExecutionError) as exc: h.service.inspect_plan(h.context, plan["plan_id"], "wrong")
    assert exc.value.code == "PLAN_STALE"


def test_trusted_process_issuance_exact_and_no_self_approval(harness):
    h = harness; plan = process_plan(h)
    grant = issue_process_execution(h.service, plan.to_dict()["plan_id"], expires_at=now() + 120)
    request = h.request(plan, grant)
    assert h.service.submit(h.context, request)["receipt"]["run_id"]
    assert h.service.submit(h.context, request)["replayed"]
    with pytest.raises(ExecutionError): issue_process_execution(h.service, h.plan().to_dict()["plan_id"], expires_at=now() + 120)
    with pytest.raises(ExecutionError): h.service.submit(h.context, {**request, "approved": True})
    assert h.counts()["consumption"] == 1


def test_explicit_validation_replay_concurrent_and_separate_state(local, monkeypatch):
    h = local; request = finish(h)
    before = h.local_store.query_run(h.context, h.rid)
    gate = h.local_store.gate()
    receipt = h.local_store.query_receipt(h.context, "stable-test-client", "key-0")
    from abqjobpilot.execution.process_backend import ProcessBackend
    monkeypatch.setattr(ProcessBackend, "execute", lambda *a: pytest.fail("validation cannot execute"))
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: h.service.validate_run(h.context, request), range(2)))
    assert sorted(r["replayed"] for r in results) == [False, True]
    assert results[0]["receipt"] == results[1]["receipt"]
    after = h.local_store.query_run(h.context, h.rid)
    assert after["revision"] == before["revision"] + 1 and after["artifact_validation"] == "VALID"
    for key in ("phase_attempt_id", "process_records", "process_exits", "solver_conclusion", "backend_outcome", "execution"):
        assert before[key] == after[key]
    assert gate == h.local_store.gate() and gate["state"] == "PAUSED"
    assert receipt == h.local_store.query_receipt(h.context, "stable-test-client", "key-0")
    assert len(h.local_store.validations(h.context, h.rid)) == 1
    with pytest.raises(ExecutionError) as exc: h.service.validate_run(h.context, {**request, "plan_digest": "wrong"})
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"


@pytest.mark.parametrize("damage,code", [("missing", "MANAGEMENT_GRANT_REQUIRED"), ("execution", "MANAGEMENT_GRANT_REQUIRED"),
    ("owner", "STALE_OWNER"), ("scope", "MANAGEMENT_SCOPE_MISMATCH"), ("approved", "INVALID_REQUEST")])
def test_validation_refusal_before_artifact_read(local, monkeypatch, damage, code):
    h = local; request = finish(h)
    if damage == "missing": request["management_grant_id"] = "missing"
    if damage == "execution": request["management_grant_id"] = h.requests[0]["grant_id"]
    if damage == "owner": request["owner_id"] = "wrong"
    if damage == "scope": request["expected_run_revision"] += 1
    if damage == "approved": request["approved"] = True
    from abqjobpilot.execution import public_workflow
    monkeypatch.setattr(public_workflow, "validate_process_artifact", lambda *a: pytest.fail("unauthorized artifact read"))
    before = inventory(Path(h.context.root))
    with pytest.raises(ExecutionError) as exc: h.service.validate_run(h.context, request)
    assert exc.value.code == code
    assert inventory(Path(h.context.root)) == before


def test_validation_pending_and_uncertain_are_ineligible(local):
    h = local
    for rid in (h.rid, h.pending):
        with pytest.raises(ExecutionError) as exc: issue_validation(h.service, rid, expires_at=now() + 120)
        assert exc.value.code == "VALIDATION_PRECONDITION_FAILED"


@pytest.mark.parametrize("fault", ["management:before_commit", "management:after_commit"])
def test_validation_transaction_and_lost_response(local, fault):
    h = local; request = finish(h)
    before = h.local_store.query_run(h.context, h.rid)
    def fail(stage):
        if stage == fault: raise OSError("private-failure-canary")
    h.local_store._checkpoint = fail
    with pytest.raises(ExecutionError) as exc: h.service.validate_run(h.context, request)
    assert "private-failure-canary" not in str(exc.value)
    h.local_store._checkpoint = lambda stage: None
    recorded = h.local_store.query_run(h.context, h.rid)
    assert recorded["revision"] == before["revision"] + (fault == "management:after_commit")
    result = h.service.validate_run(h.context, request)
    assert result["replayed"] == (fault == "management:after_commit")
    assert len(h.local_store.validations(h.context, h.rid)) == 1


def test_explicit_validation_invalid_does_not_rewrite_process_success(local):
    h = local; request = finish(h)
    (h.run_root(h.rid) / "result.json").write_text("invalid", encoding="utf-8")
    assert h.service.validate_run(h.context, request)["receipt"]["projection_at_commit"]["verdict"] == "FAIL"
    run = h.local_store.query_run(h.context, h.rid)
    assert run["backend_outcome"] == "COMPLETED" and run["exit_verification"] == "VERIFIED"
    assert run["artifact_validation"] == "INVALID" and run["solver_conclusion"] == "NOT_RUN"
    assert h.local_store.gate()["state"] == "PAUSED"


def test_new_ipc_operations_keep_auth_binding_and_strict_fields(factory):
    from abqjobpilot.execution.client import FakeClient
    h = factory("normal")
    h.owner(); client = h.client(); request = h.requests[0]
    assert client.inspect_plan(request["plan_id"], request["plan_digest"])["scope"] == "TEST_ONLY"
    assert {"inspect_plan", "validate_run"} <= set(client.health()["operations"])
    for operation, args in [("inspect_plan", {"plan_id": request["plan_id"], "expected_digest": request["plan_digest"]}),
                            ("validate_run", {"request": {}})]:
        with pytest.raises(ExecutionError) as exc: FakeClient(client.endpoint, "incorrect").call(operation, args)
        assert exc.value.code == "AUTHENTICATION_FAILED"
        wrong = {**client.endpoint, "project_instance_id": "pi_wrong"}
        with pytest.raises(ExecutionError) as exc: FakeClient(wrong, h.credential).call(operation, args)
        assert exc.value.code == "ENDPOINT_IDENTITY_MISMATCH"
        with pytest.raises(ExecutionError) as exc: client.call(operation, {**args, "approved": True})
        assert exc.value.code == "INVALID_REQUEST"
    with pytest.raises(ExecutionError) as exc: client.call("approve", {"approved": True})
    assert exc.value.code == "UNKNOWN_OPERATION"
    assert client.events() == []


def test_expired_and_stale_validation_permission_fail_before_read(local, monkeypatch):
    from abqjobpilot.execution import public_workflow, authorization
    h = local; request = finish(h)
    monkeypatch.setattr(public_workflow, "validate_process_artifact", lambda *a: pytest.fail("unauthorized read"))
    with monkeypatch.context() as patch:
        patch.setattr(authorization, "now", lambda: now() + 200)
        with pytest.raises(ExecutionError) as exc: h.service.validate_run(h.context, request)
        assert exc.value.code == "MANAGEMENT_GRANT_EXPIRED"
    from abqjobpilot.execution.store import document, update_run
    with h.local_store.transaction("test_revision_change") as c:
        update_run(c, document(c, "runs", "run_id", h.rid), "TEST_REVISION_CHANGE")
    with pytest.raises(ExecutionError) as exc: h.service.validate_run(h.context, request)
    assert exc.value.code == "STALE_PREVIEW"
