"""Explicit delegated Fake execution, including the independent stdio/Owner boundary."""

import asyncio
from contextlib import contextmanager
import json
from pathlib import Path

import pytest

from abqjobpilot.execution import ExecutionError, open_existing_read_only
from abqjobpilot.execution.delegated_grant import EXECUTE, check_plan_scope
from abqjobpilot.execution.models import bytes_digest, now
from abqjobpilot.execution.test_authority import revoke_delegated_fake
import execution_helpers
from test_agent_first_mcp import arguments, call, stdio
from test_delegated_grant import ADMISSION, approve, make_harness, prepare
from test_delegated_owner import DelegatedOwnerHarness
from test_service_attachment import connection


@pytest.fixture
def delegated(tmp_path, monkeypatch):
    execution_helpers.guard_environment.__wrapped__(monkeypatch)
    h = make_harness(tmp_path)
    try:
        yield h
    finally:
        h.store.close()


@contextmanager
def denied(code):
    with pytest.raises(ExecutionError) as error:
        yield
    assert error.value.code == code


def executable_plan(h):
    return h.service.prepare(h.context, h.spec(job_id="bridge"), h.config, expires_at=now() + 3600,
                             delegated_resources=ADMISSION, delegated_execution=EXECUTE)


def provision(h, _):
    plan = executable_plan(h)
    grant = approve(h, plan, approval_key="approve-bridge", max_runs=1, allowed_action=EXECUTE)
    return h.request(plan, grant["grant_id"], "bridge-first")


def test_operator_and_plan_must_agree(delegated):
    h = delegated
    admission = prepare(h)
    with denied("DELEGATED_SCOPE_MISMATCH"):
        approve(h, admission, allowed_action=EXECUTE)
    executable = executable_plan(h)
    with denied("DELEGATED_SCOPE_MISMATCH"):
        approve(h, executable)
    prior = approve(h, admission)
    with denied("IDEMPOTENCY_CONFLICT"):
        approve(h, admission, allowed_action=EXECUTE, expires_at=prior["expires_at"])
    for backend in ("abaqus-standard-t3d2-sanity-v1", "python-process-fixture-v1"):
        with denied("DELEGATED_SCOPE_MISMATCH"):
            check_plan_scope(h.context, {**executable.to_dict(), "backend_id": backend}, EXECUTE)
    request = h.request(admission, prior["grant_id"])
    run_id = h.service.submit(h.context, request)["receipt"]["run_id"]
    # The authorization check independently denies dispatch of the original Run.
    with h.store.read() as conn, denied("DELEGATED_DISPATCH_UNAVAILABLE"):
        h.service._check(conn, h.context, admission.to_dict(), prior["grant_id"], run_id)


@pytest.mark.parametrize("damage,code", [("input", "PLAN_STALE"), ("revoke", "GRANT_REVOKED")])
def test_claim_rechecks_original_authority(delegated, damage, code):
    h = delegated
    request = provision(h, None)
    receipt = h.service.submit(h.context, request)["receipt"]
    if damage == "input":
        h.input.write_text("changed fixture", encoding="utf-8")
    else:
        revoke_delegated_fake(h.service, request["grant_id"])
    with denied(code):
        h.service.execute_pending(h.context, receipt["run_id"])
    assert h.store.query_run(h.context, receipt["run_id"])["execution"] == "BLOCKED"
    assert h.store.delegated_budget(h.context, request["grant_id"])["consumed"] == 1
    assert not list(Path(h.context.runtime_root).rglob("result.json"))


def test_another_runs_artifact_cannot_be_published_as_verified(delegated, monkeypatch):
    h = delegated
    plan = executable_plan(h)
    grant_id = approve(h, plan, allowed_action=EXECUTE)["grant_id"]

    def submit(key):
        return h.service.submit(h.context, h.request(plan, grant_id, key))["receipt"]["run_id"]

    first = submit("first")
    h.service.execute_pending(h.context, first)
    second = submit("second")
    outputs = Path(h.context.runtime_root) / "fake_runs"

    def substitute(name):
        if name == "dispatch:after_artifact":
            (outputs / second / "result.json").write_bytes((outputs / first / "result.json").read_bytes())

    monkeypatch.setattr(h.store, "_checkpoint", substitute)
    run = h.service.execute_pending(h.context, second)
    assert run["backend_outcome"] == "COMPLETED" and run["artifact_validation"] == "INVALID"
    evidence = run["fake_result_evidence"]
    assert evidence["run_id"] == second and evidence["verdict"] == "FAIL" and evidence["result"] is None
    validation, = h.store.validations(h.context, second)
    assert {"run", "phase", "digest"} <= set(validation["reasons"])


def test_revocation_after_claim_prevents_emission(delegated, monkeypatch):
    h = delegated
    request = provision(h, None)
    run_id = h.service.submit(h.context, request)["receipt"]["run_id"]

    def revoke_before_emit(name):
        if name == "dispatch:after_claim":
            revoke_delegated_fake(h.service, request["grant_id"])

    monkeypatch.setattr(h.store, "_checkpoint", revoke_before_emit)
    with denied("EVIDENCE_WRITE_FAILED"):
        h.service.execute_pending(h.context, run_id)
    run = h.store.query_run(h.context, run_id)
    assert run["reconciliation_requirement"] == "RECONCILIATION_REQUIRED"
    assert "fake_result_evidence" not in run
    assert h.store.delegated_budget(h.context, request["grant_id"])["consumed"] == 1
    assert not list(Path(h.context.runtime_root).rglob("result.json"))


@pytest.fixture
def bridge(tmp_path):
    h = DelegatedOwnerHarness(tmp_path, provision=provision)
    try:
        yield h
    finally:
        (h.root / "private" / "connection.json").unlink(missing_ok=True)
        h.close()


def test_same_run_stdio_submit_dispatch_result_and_reconnect(bridge):
    h = bridge
    owner = h.owner(barriers=["dispatch:after_claim"])
    connection(h)
    request = arguments(h.provisioned)
    grant_args = {"grant_id": request["grant_id"]}

    async def exercise():
        async with stdio(h, explicit_connection=True) as client:
            environment = await call(client, "abq_check_environment")
            assert environment["capabilities"]["delegated_fake_execution"] == "TEST_ONLY"
            assert environment["supervisor"]["execution_scope"] == "TEST_ONLY"
            before = (await call(client, "abq_get_grant_status", grant_args))["grant"]
            assert before["allowed_action"] == EXECUTE and before["remaining"] == 1
            first = await call(client, "abq_submit_job", request)
            assert first["request_status"] == "ACCEPTED" and not first["replayed"]
            receipt = first["receipt"]
            run_args = {"run_id": receipt["run_id"]}
            owner.reached("dispatch:after_claim")
            claimed = (await call(client, "abq_get_run_status", run_args))["run"]
            assert claimed["execution"] == "START_INTENT" and claimed["queue_state"] == "DISPATCHED"
            assert "fake_result_evidence" not in claimed
            during = await call(client, "abq_submit_job", request)
            assert during["replayed"] and during["receipt"] == receipt
        owner.release("dispatch:after_claim")
        async with stdio(h, explicit_connection=True) as client:
            async with asyncio.timeout(10):
                while True:
                    run = (await call(client, "abq_get_run_status", run_args))["run"]
                    if run["execution"] == "FINISHED":
                        break
                    await asyncio.sleep(0.05)
            assert run["simulation"] is True and run["solver_conclusion"] == "NOT_RUN"
            assert run["backend_outcome"] == "COMPLETED" and run["artifact_validation"] == "VALID"
            assert run["phase_attempt_id"] == claimed["phase_attempt_id"]
            assert all(run[k] == request[k] for k in request if k != "idempotency_key")
            assert run["admission_only"] is False and run["delegated_execution"] == EXECUTE
            evidence = run["fake_result_evidence"]
            assert evidence["run_id"] == run["run_id"] and evidence["phase_attempt_id"] == run["phase_attempt_id"]
            assert evidence["verdict"] == "PASS" and evidence["backend_id"] == "fake-v1"
            reader = open_existing_read_only(h.context)
            obs, = reader.observations(h.context, run["run_id"])
            val, = reader.validations(h.context, run["run_id"])
            assert obs["observation_id"] == evidence["observation_id"] and val["validation_id"] == evidence["validation_id"]
            assert val["evidence_refs"] == [obs["observation_id"]]
            content = (Path(h.context.runtime_root) / "fake_runs" / run["run_id"] / "result.json").read_bytes()
            assert evidence["digest"] == bytes_digest(content) and evidence["size"] == len(content)
            assert evidence["result"] == json.loads(content) == obs["verified_result"]
            assert evidence["result"]["run_id"] == run["run_id"]
            assert evidence["result"]["phase_attempt_id"] == run["phase_attempt_id"]
            assert evidence["result"]["plan_digest"] == request["plan_digest"]
            assert (await call(client, "abq_get_receipt", {"idempotency_key": request["idempotency_key"]}))["receipt"] == receipt
            replay = await call(client, "abq_submit_job", request)
            assert replay["replayed"] and replay["receipt"] == receipt
            await call(client, "abq_submit_job", {**request, "job_revision": 2}, error="IDEMPOTENCY_CONFLICT")
            await call(client, "abq_submit_job", {**request, "idempotency_key": "bridge-second"}, error="GRANT_BUDGET_EXHAUSTED")
            after = (await call(client, "abq_get_grant_status", grant_args))["grant"]
            assert after["consumed"] == 1 and after["remaining"] == 0
            events = [e["type"] for e in h.client().events() if e["run_id"] == run["run_id"]]
            assert events == ["REQUEST_ACCEPTED", "START_INTENT", "FAKE_COMPLETED", "VALIDATION_RECORDED"]
            (h.root / "bridge-proof.json").write_text(json.dumps({
                "receipt": receipt, "claim": claimed, "terminal": run, "grant": after, "events": events,
            }, indent=2), encoding="utf-8")

    asyncio.run(exercise())


def test_owner_killed_after_claim_preserves_unknown_and_budget(bridge):
    h = bridge
    owner = h.owner(barriers=["dispatch:after_claim"])
    client = h.client()
    receipt = client.submit_delegated(h.provisioned)["receipt"]
    owner.reached("dispatch:after_claim")
    owner.terminate()
    h.owner()
    restarted = h.client()
    assert not restarted.health()["dispatch_enabled"]
    assert restarted.submit_delegated(h.provisioned)["receipt"] == receipt
    run = restarted.run(receipt["run_id"])
    assert run["execution"] == "START_INTENT" and run["reconciliation_requirement"] == "RECONCILIATION_REQUIRED"
    assert "fake_result_evidence" not in run and run["backend_outcome"] != "COMPLETED"
    assert restarted.delegated_grant_status(h.provisioned["grant_id"])["remaining"] == 0
    assert not open_existing_read_only(h.context).validations(h.context, run["run_id"])
    assert [e["type"] for e in restarted.events()] == ["REQUEST_ACCEPTED", "START_INTENT"]
    assert not list(Path(h.context.runtime_root).rglob("result.json"))
