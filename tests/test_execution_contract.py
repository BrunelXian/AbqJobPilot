from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import threading

import pytest

from abqjobpilot.execution import ConfigSnapshot, ExecutionError, ExecutionService, ExperimentStore, create_experiment
from abqjobpilot.execution import authorization, planning
from abqjobpilot.execution.fake_backend import FakeBackend
from abqjobpilot.execution.models import canonical_json, digest, now
from execution_helpers import Harness, guard_environment, harness


def test_headless_submit_and_validation_run_persisted_before_effect(harness, monkeypatch):
    h = harness
    original = FakeBackend.emit
    observed = []
    def emit(backend, context, plan, run):
        # A separate read connection sees committed Run, receipt, claim and event before file effects.
        view = h.store.query_run(context, run["run_id"])
        assert view["execution"] == "START_INTENT"
        assert h.store.query_receipt(context, "test-client", "request-1")["run_id"] == run["run_id"]
        assert len(h.store.events(context)) == 2
        observed.append(run["run_id"])
        return original(backend, context, plan, run)
    monkeypatch.setattr(FakeBackend, "emit", emit)
    _, _, receipt = h.accept()
    result = h.service.execute_pending(h.context, receipt["run_id"])
    assert observed == [receipt["run_id"]]
    assert result["execution"] == "FINISHED"
    assert result["backend_outcome"] == "COMPLETED"
    assert result["artifact_validation"] == "VALID"
    assert result["solver_conclusion"] == "NOT_RUN"
    assert result["process_observation"] == result["exit_verification"] == "NOT_APPLICABLE"
    assert h.store.validations(h.context, result["run_id"])[0]["scope"] == "simulation"
    assert h.counts() == dict(runs=1, receipts=1, events=4, consumption=1, observations=1, validations=1)


def test_idempotent_submit_and_execution_replay(harness, monkeypatch):
    h = harness
    original, calls = FakeBackend.emit, []
    def emit(*args):
        calls.append(1)
        return original(*args)
    monkeypatch.setattr(FakeBackend, "emit", emit)
    _, request, receipt = h.accept()
    for _ in range(3):
        reply = h.service.submit(h.context, request)
        assert reply["replayed"] and reply["receipt"] == receipt
    first = h.service.execute_pending(h.context, receipt["run_id"])
    assert h.service.execute_pending(h.context, receipt["run_id"]) == first
    assert h.service.submit(h.context, request)["receipt"] == receipt
    assert len(calls) == 1 and h.counts()["consumption"] == 1


@pytest.mark.parametrize("field,value", [("plan_id", "other-plan"), ("plan_digest", "other-digest"),
                                         ("grant_id", "other-grant"), ("retry_of", "other-run")])
def test_same_key_different_content_conflict(harness, field, value):
    h = harness
    _, request, _ = h.accept()
    before = h.counts()
    with pytest.raises(ExecutionError) as failure:
        h.service.submit(h.context, {**request, field: value})
    assert failure.value.to_dict()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert h.counts() == before


def test_concurrent_submit_across_service_and_store_objects(harness):
    h = harness
    plan = h.plan()
    request = h.request(plan, h.grant(plan))
    services = [ExecutionService(h.context, ExperimentStore(h.context), client_namespace="test-client") for _ in range(8)]
    barrier = threading.Barrier(len(services))
    def submit(service):
        barrier.wait(timeout=5)
        return service.submit(h.context, request)
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(submit, services))
    assert len({item["receipt"]["run_id"] for item in replies}) == 1
    assert sum(not item["replayed"] for item in replies) == 1
    assert h.counts()["runs"] == h.counts()["events"] == h.counts()["consumption"] == 1


def test_atomic_execution_claim_and_store_single_slot(harness, monkeypatch):
    h = harness
    _, _, first = h.accept()
    _, _, second = h.accept(key="second", spec=h.spec(job_id="j_second"))
    other = ExecutionService(h.context, ExperimentStore(h.context), client_namespace="other-client")
    entered, release = threading.Event(), threading.Event()
    original, calls = FakeBackend.emit, []
    def held_emit(*args):
        calls.append(args[-1]["run_id"])
        entered.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(FakeBackend, "emit", held_emit)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(h.service.execute_pending, h.context, first["run_id"])
        try:
            assert entered.wait(5)
            duplicate = other.execute_pending(h.context, first["run_id"])
            assert duplicate["execution"] == "START_INTENT"
            with pytest.raises(ExecutionError, match="already has a claimed Run") as failure:
                other.execute_pending(h.context, second["run_id"])
            assert failure.value.code == "SLOT_BUSY"
            assert failure.value.to_dict()["request_status"] == "ACCEPTED"
            assert failure.value.run_id == second["run_id"]
            assert h.store.query_run(h.context, second["run_id"])["queue_state"] == "PENDING"
        finally:
            release.set()
        assert first_future.result()["execution"] == "FINISHED"
    assert other.execute_pending(h.context, second["run_id"])["execution"] == "FINISHED"
    assert calls == [first["run_id"], second["run_id"]]


def test_simultaneous_claim_same_run_only_one_effect(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    other = ExecutionService(h.context, ExperimentStore(h.context))
    barrier, calls, original = threading.Barrier(2), [], FakeBackend.emit
    def emit(*args):
        calls.append(1)
        return original(*args)
    monkeypatch.setattr(FakeBackend, "emit", emit)
    def execute(service):
        barrier.wait(timeout=5)
        return service.execute_pending(h.context, receipt["run_id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(execute, [h.service, other]))
    assert len(calls) == 1
    assert [e["type"] for e in h.store.events(h.context)].count("START_INTENT") == 1


@pytest.mark.parametrize("field,value", [("project_id", "wrong"), ("project_instance_id", "wrong"),
                                         ("root", "wrong"), ("manifest_digest", "wrong")])
def test_wrong_context_rejected(harness, field, value):
    h = harness
    plan = h.plan()
    with pytest.raises(ExecutionError) as failure:
        h.service.submit(replace(h.context, **{field: value}), h.request(plan, h.grant(plan)))
    assert failure.value.code == "PROJECT_IDENTITY_MISMATCH"
    assert h.counts()["runs"] == 0


@pytest.mark.parametrize("when", ["before_submit", "before_dispatch"])
@pytest.mark.parametrize("change", ["input", "config_revision", "config_values"])
def test_changed_input_or_configuration_invalidates_plan(harness, when, change):
    h = harness
    plan = h.plan()
    request = h.request(plan, h.grant(plan))
    receipt = h.service.submit(h.context, request)["receipt"] if when == "before_dispatch" else None
    if change == "input":
        h.input.write_text("FIXTURE INPUT", encoding="utf-8")  # Same byte size.
    else:
        h.service.configure(h.context, ConfigSnapshot.from_dict({"config_revision": 2 if change == "config_revision" else 1,
                                                                "values": {"label": "changed" if change == "config_values" else "simulation 测试"}}))
    with pytest.raises(ExecutionError) as failure:
        if receipt:
            h.service.execute_pending(h.context, receipt["run_id"])
        else:
            h.service.submit(h.context, request)
    assert failure.value.code == "PLAN_STALE"
    if receipt:
        assert failure.value.to_dict()["request_status"] == "ACCEPTED"
        assert h.store.query_run(h.context, receipt["run_id"])["execution"] == "BLOCKED"
        assert h.service.submit(h.context, request)["receipt"] == receipt
    else:
        assert h.counts()["runs"] == 0
    assert not list(h.root.rglob("result.json"))


@pytest.mark.parametrize("override,code", [({"expires_at": 0}, "GRANT_EXPIRED"),
    ({"project_instance_id": "other"}, "GRANT_SCOPE_MISMATCH"), ({"plan_digest": "other"}, "GRANT_SCOPE_MISMATCH"),
    ({"job_id": "other"}, "GRANT_SCOPE_MISMATCH"), ({"job_revision": 2}, "GRANT_SCOPE_MISMATCH"),
    ({"output_scope": "outside"}, "GRANT_SCOPE_MISMATCH"), ({"max_runs": 2}, "GRANT_SCOPE_MISMATCH"),
    ({"authority_instance": "forged"}, "GRANT_SCOPE_MISMATCH"), ({"grant_kind": "REAL"}, "TEST_GRANT_ONLY")])
def test_grant_conditions_reject(harness, override, code):
    h = harness
    plan = h.plan()
    with pytest.raises(ExecutionError) as failure:
        h.service.submit(h.context, h.request(plan, h.grant(plan, **override)))
    assert failure.value.code == code and h.counts()["runs"] == 0


@pytest.mark.parametrize("grant_id", [None, "", "unknown"])
def test_missing_or_unregistered_grant(harness, grant_id):
    h = harness
    with pytest.raises(ExecutionError) as failure:
        h.service.submit(h.context, h.request(h.plan(), grant_id))
    assert failure.value.code == "GRANT_REQUIRED"


@pytest.mark.parametrize("extra", [{"approved": True}, {"allow_solver_submit": True}, {"backend_id": "abaqus"},
                                   {"executable": "ignored.bat"}, {"output_dir": "elsewhere"}])
def test_self_approval_and_execution_options_rejected(harness, extra):
    h = harness
    plan = h.plan()
    with pytest.raises(ExecutionError) as failure:
        h.service.submit(h.context, {**h.request(plan, h.grant(plan)), **extra})
    assert failure.value.code == "INVALID_REQUEST" and h.counts()["runs"] == 0


@pytest.mark.parametrize("field,value", [("simulated_cpus", 2), ("simulated_gpus", 1), ("slots", 2)])
def test_resource_budget_rejected(harness, field, value):
    h = harness
    resources = h.spec().to_dict()["resources"]
    resources[field] = value
    with pytest.raises(ExecutionError) as failure:
        h.plan(h.spec(resources=resources))
    assert failure.value.code == "RESOURCE_LIMIT"


@pytest.mark.parametrize("change", ["new_job", "new_revision", "new_plan", "consumed"])
def test_new_work_cannot_reuse_old_plan_or_grant(harness, change):
    h = harness
    old_plan = h.plan()
    grant = h.grant(old_plan)
    request = h.request(old_plan, grant)
    if change == "new_job":
        request["job_id"] = "new-job"
    elif change == "new_revision":
        request["job_revision"] = 2
    elif change == "new_plan":
        request = h.request(h.plan(), grant)
    else:
        h.service.submit(h.context, request)
        request["idempotency_key"] = "new-key"
    with pytest.raises(ExecutionError) as failure:
        h.service.submit(h.context, request)
    assert failure.value.code in {"GRANT_SCOPE_MISMATCH", "GRANT_CONSUMED"}


def test_replay_survives_expired_grant_and_changed_input(harness):
    h = harness
    _, request, receipt = h.accept()
    with h.store.transaction("fixture_expire") as connection:
        row = connection.execute("SELECT body FROM grants WHERE grant_id=?", (request["grant_id"],)).fetchone()
        grant = json.loads(row[0])
        grant["expires_at"] = 0
        connection.execute("UPDATE grants SET body=? WHERE grant_id=?", (canonical_json(grant), request["grant_id"]))
    h.input.write_text("changed", encoding="utf-8")
    assert h.service.submit(h.context, request)["receipt"] == receipt
    assert h.counts()["events"] == 1


def test_true_retry_creates_new_run_and_preserves_old_evidence(harness):
    h = harness
    _, _, first = h.accept()
    h.service.execute_pending(h.context, first["run_id"])
    old_validation = h.store.validations(h.context, first["run_id"])
    _, _, second = h.accept(key="retry", retry_of=first["run_id"])
    result = h.service.execute_pending(h.context, second["run_id"])
    assert result["run_id"] != first["run_id"] and result["attempt_no"] == 2
    assert result["retry_of"] == first["run_id"]
    assert h.store.validations(h.context, first["run_id"]) == old_validation


@pytest.mark.parametrize("reason", ["missing", "pending", "other_job", "other_project"])
def test_invalid_retry_rejected(harness, reason):
    h = harness
    _, _, first = h.accept()
    if reason == "other_job":
        h.service.execute_pending(h.context, first["run_id"])
    retry_of = first["run_id"] if reason in {"pending", "other_job"} else "r_not_in_this_project"
    with pytest.raises(ExecutionError) as failure:
        h.accept(key="retry", spec=h.spec(job_id="other" if reason == "other_job" else "j_fixture"), retry_of=retry_of)
    assert failure.value.code in {"INVALID_RETRY", "NOT_FOUND"}


def test_canonical_values_and_event_pagination(harness):
    assert digest({"b": "测试", "a": [1, True]}) == digest({"a": [1, True], "b": "测试"})
    assert digest({"a": True}) != digest({"a": 1})
    assert digest([1, 2]) != digest([2, 1])
    for value in (1.2, float("nan"), float("inf"), {1: "bad"}):
        with pytest.raises(ExecutionError):
            canonical_json(value)
    h = harness
    _, request, receipt = h.accept()
    h.service.execute_pending(h.context, receipt["run_id"])
    first = h.store.events(h.context, limit=2)
    second = h.store.events(h.context, after_sequence=first[-1]["project_sequence"], limit=2)
    events = first + second
    assert [e["project_sequence"] for e in events] == [1, 2, 3, 4]
    assert [e["run_sequence"] for e in events] == [1, 2, 3, 4]
    assert len({e["event_id"] for e in events}) == 4
    assert receipt["accepted_sequence"] == 1
    with pytest.raises(ExecutionError):
        h.service.submit(h.context, {**request, "job_revision": True})


def test_plan_is_detached_from_mutable_inputs_and_expiry_checked(harness):
    h = harness
    value = h.spec().to_dict()
    spec = h.spec(metadata=value["metadata"])
    value["metadata"]["label"] = "changed"
    plan = h.plan(spec)
    assert plan.to_dict()["job_spec"]["metadata"]["label"] == "测试"
    data = plan.to_dict()
    data["backend_id"] = "abaqus"
    assert plan.to_dict()["backend_id"] == "fake-v1"
    with pytest.raises(ExecutionError) as failure:
        h.plan(expires_at=now() - 1)
    assert failure.value.code == "PLAN_EXPIRED"


@pytest.mark.parametrize("when", ["before_submit", "before_dispatch"])
def test_plan_expiry_after_prepare_blocks_execution(harness, monkeypatch, when):
    h = harness
    plan = h.plan()
    request = h.request(plan, h.grant(plan))
    receipt = h.service.submit(h.context, request)["receipt"] if when == "before_dispatch" else None
    monkeypatch.setattr(planning, "now", lambda: plan.to_dict()["expires_at"] + 1)
    with pytest.raises(ExecutionError) as failure:
        if receipt:
            h.service.execute_pending(h.context, receipt["run_id"])
        else:
            h.service.submit(h.context, request)
    assert failure.value.code == "PLAN_EXPIRED"
    assert not list(h.root.rglob("result.json"))


def test_grant_expiry_after_accept_blocks_dispatch_but_keeps_receipt(harness, monkeypatch):
    h = harness
    _, request, receipt = h.accept()
    monkeypatch.setattr(authorization, "now", lambda: now() + 4000)
    with pytest.raises(ExecutionError) as failure:
        h.service.execute_pending(h.context, receipt["run_id"])
    assert failure.value.code == "GRANT_EXPIRED" and failure.value.run_id == receipt["run_id"]
    assert h.service.submit(h.context, request)["receipt"] == receipt
    assert not list(h.root.rglob("result.json"))


def test_real_other_project_retry_and_request_scope_rejected(harness):
    h = harness
    context = create_experiment(h.root, h.root / "second-project")
    store = ExperimentStore(context)
    try:
        other = Harness(h.root, context, store, ExecutionService(context, store), h.input, h.config)
        _, _, old = other.accept()
        other.service.execute_pending(context, old["run_id"])
        with pytest.raises(ExecutionError) as failure:
            h.accept(retry_of=old["run_id"])
        assert failure.value.code == "NOT_FOUND"
        plan = h.plan()
        with pytest.raises(ExecutionError) as mismatch:
            h.service.submit(h.context, h.request(plan, h.grant(plan), project_id=context.project_id))
        assert mismatch.value.code == "PROJECT_IDENTITY_MISMATCH"
    finally:
        store.close()


def test_single_slot_scope_is_per_experiment_store(harness, monkeypatch):
    h = harness
    context = create_experiment(h.root, h.root / "second-project")
    store = ExperimentStore(context)
    other = Harness(h.root, context, store, ExecutionService(context, store), h.input, h.config)
    _, _, first = h.accept()
    _, _, second = other.accept()
    barrier, original = threading.Barrier(2), FakeBackend.emit
    def concurrent_emit(*args):
        # Distinct stores have independent slots; no host-wide scheduling claim.
        barrier.wait(timeout=5)
        return original(*args)
    monkeypatch.setattr(FakeBackend, "emit", concurrent_emit)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(h.service.execute_pending, h.context, first["run_id"])
            b = pool.submit(other.service.execute_pending, context, second["run_id"])
            assert a.result()["execution"] == b.result()["execution"] == "FINISHED"
    finally:
        store.close()
