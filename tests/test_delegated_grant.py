from pathlib import Path

import pytest

from abqjobpilot import application_runtime
from abqjobpilot.execution import ConfigSnapshot, ExecutionError, ExecutionService, ExperimentStore, create_experiment
from abqjobpilot.execution import delegated_grant
from abqjobpilot.execution.models import DELEGATED_GRANT_CONTRACT, RESOURCES, now
from abqjobpilot.execution.test_authority import issue_delegated_fake, revoke_delegated_fake
from execution_helpers import Harness, guard_environment, harness

ADMISSION = {"memory_bytes": 16 * 1024 * 1024, "wall_seconds": 3}


def make_harness(root, *, odb_fixture_test_only=False):
    context = create_experiment(root, root / "project", delegated_test_only=True,
                                odb_fixture_test_only=odb_fixture_test_only)
    store = ExperimentStore(context)
    source = Path(context.root) / "inputs" / "fixture.txt"
    source.parent.mkdir()
    source.write_text("bounded Fake input", encoding="utf-8")
    (root / "recent-fixture.json").write_text('{"unchanged":true}', encoding="utf-8")
    service = ExecutionService(context, store, client_namespace="delegated-test-client")
    config = ConfigSnapshot.from_dict({"config_revision": 1, "values": {"label": "delegated test"}})
    return Harness(root, context, store, service, source, config)


@pytest.fixture
def delegated(tmp_path, guard_environment):
    root = tmp_path / "delegated"
    root.mkdir()
    h = make_harness(root)
    try:
        yield h
    finally:
        h.store.close()


def prepare(h, *, job_id="fixture-job", resources=ADMISSION, **spec):
    return h.service.prepare(h.context, h.spec(job_id=job_id, **spec), h.config,
                             expires_at=now() + 3600, delegated_resources=resources)


def approve(h, *plans, **overrides):
    terms = {"approval_key": "review-1",
             "plans": {p.to_dict()["plan_id"]: p.to_dict()["plan_digest"] for p in plans},
             "max_runs": 2, "expires_at": now() + 600, "resource_limits": {**RESOURCES, **ADMISSION}}
    terms.update(overrides)
    return issue_delegated_fake(h.service, **terms).to_dict()


def test_operator_approval_binds_source_project_and_terms(delegated):
    h = delegated
    plan = prepare(h)
    grant = approve(h, plan)
    assert grant["contract_version"] == DELEGATED_GRANT_CONTRACT
    assert grant["grant_kind"] == "TEST_ONLY_DELEGATED" and grant["issuer"] == "DelegatedFakeOperator"
    assert grant["project_id"] == h.context.project_id
    assert grant["project_instance_id"] == h.context.project_instance_id
    assert grant["context_digest"] == h.context.context_digest
    assert grant["input_scope"] == str(h.input.parent) and grant["output_scope"] == h.context.runtime_root
    assert grant["backend_id"] == "fake-v1" and grant["allowed_action"] == "accept_fake_only"
    assert approve(h, plan, expires_at=grant["expires_at"]) == grant
    with pytest.raises(ExecutionError) as error:
        approve(h, plan, max_runs=3, expires_at=grant["expires_at"])
    assert error.value.code == "IDEMPOTENCY_CONFLICT"


@pytest.mark.parametrize("limits", [{"max_runs": True}, {"max_runs": 0}, {"max_runs": 129},
                                    {"expires_at": 0}, {"resource_limits": {**RESOURCES, **ADMISSION, "wall_seconds": True}}])
def test_malformed_or_unbounded_terms_are_rejected(delegated, limits):
    with pytest.raises(ExecutionError):
        approve(delegated, prepare(delegated), **limits)
    with delegated.store.read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM grants").fetchone()[0] == 0


@pytest.mark.parametrize("why,code", [
    ("expires", "GRANT_EXPIRED"), ("clock_rollback", "GRANT_NOT_YET_VALID"),
    ("revoked", "GRANT_REVOKED"), ("input_drift", "PLAN_STALE"),
    ("unlisted_plan", "DELEGATED_SCOPE_MISMATCH"), ("plan_digest", "GRANT_SCOPE_MISMATCH"),
    ("project_id", "PROJECT_IDENTITY_MISMATCH"), ("project_instance_id", "PROJECT_IDENTITY_MISMATCH"),
    ("client_namespace", "DELEGATED_SCOPE_MISMATCH"), ("retry_of", "INVALID_RETRY"),
])
def test_admission_rechecks_current_preconditions_and_preserves_existing_acceptance(delegated, monkeypatch, why, code):
    h = delegated
    plan = prepare(h)
    grant = approve(h, plan)
    grant_id = grant["grant_id"]
    original = h.request(plan, grant_id)
    receipt = h.service.submit(h.context, original)["receipt"]
    request = h.request(plan, grant_id, "new")
    service = h.service
    if why == "expires":
        monkeypatch.setattr(delegated_grant, "now", lambda: grant["expires_at"])
    elif why == "clock_rollback":
        monkeypatch.setattr(delegated_grant, "now", lambda: grant["issued_at"] - 1)
    elif why == "revoked":
        revoked = revoke_delegated_fake(service, grant_id)
        assert revoke_delegated_fake(service, grant_id) == revoked
        assert approve(h, plan, expires_at=grant["expires_at"]) == revoked.to_dict()
    elif why == "input_drift":
        h.input.write_text("changed model", encoding="utf-8")
    elif why == "unlisted_plan":
        request = h.request(prepare(h), grant_id, "new")
    elif why == "client_namespace":
        service = ExecutionService(h.context, h.store, client_namespace="other-client")
    else:
        request[why] = "different"
    with pytest.raises(ExecutionError) as error:
        service.submit(h.context, request)
    assert error.value.code == code
    assert h.service.submit(h.context, original)["receipt"] == receipt
    assert h.store.delegated_budget(h.context, grant_id)["consumed"] == 1


def test_other_opted_in_project_cannot_use_grant(delegated):
    h = delegated
    grant = approve(h, prepare(h))
    root = h.root / "other"
    root.mkdir()
    other = make_harness(root)
    try:
        request = other.request(prepare(other), grant["grant_id"])
        with pytest.raises(ExecutionError) as error:
            other.service.submit(other.context, request)
        assert error.value.code == "GRANT_REQUIRED" and other.counts()["runs"] == 0
    finally:
        other.store.close()


@pytest.mark.parametrize("resource", ["simulated_cpus", "memory_bytes", "wall_seconds", "max_output_bytes"])
def test_each_resource_ceiling_is_checked_on_admission(delegated, resource):
    h = delegated
    plan = prepare(h)
    limits = {**RESOURCES, **ADMISSION}
    limits[resource] -= 1
    grant = approve(h, plan, resource_limits=limits)
    with pytest.raises(ExecutionError) as error:
        h.service.submit(h.context, h.request(plan, grant["grant_id"]))
    assert error.value.code == "RESOURCE_LIMIT"
    assert h.store.delegated_budget(h.context, grant["grant_id"])["consumed"] == 0


@pytest.mark.parametrize("kind,code", [("outside", "OUTPUT_SCOPE_VIOLATION"),
                                       ("hardlink", "OUTPUT_SCOPE_VIOLATION"), ("model", "INVALID_REQUEST")])
def test_delegated_input_boundaries(delegated, kind, code):
    h = delegated
    outside = h.root / "outside.txt"
    outside.write_text("fixture", encoding="utf-8")
    target = outside
    if kind == "hardlink":
        target = h.input.parent / "linked.txt"
        target.hardlink_to(outside)
    elif kind == "model":
        target = h.input.with_suffix(".inp")
        target.write_text("placeholder", encoding="utf-8")
    with pytest.raises(ExecutionError) as error:
        prepare(h, input_refs=[str(target)])
    assert error.value.code == code and h.counts()["runs"] == 0


def test_existing_or_frozen_projects_cannot_enable_delegation(harness, delegated, monkeypatch):
    with pytest.raises(ExecutionError) as error:
        prepare(harness)
    assert error.value.code == "TEST_SCOPE_REQUIRED"
    plan = prepare(delegated)
    grant = approve(delegated, plan)
    monkeypatch.setattr(application_runtime, "is_frozen_runtime", lambda: True)
    with pytest.raises(ExecutionError) as error:
        approve(delegated, plan, approval_key="frozen")
    assert error.value.code == "TEST_SCOPE_REQUIRED"
    with pytest.raises(ExecutionError) as error:
        delegated.service.submit(delegated.context, delegated.request(plan, grant["grant_id"]))
    assert error.value.code == "TEST_SCOPE_REQUIRED"


def test_exact_grant_and_delegated_admission_cannot_cross(delegated):
    h = delegated
    exact_plan, delegated_plan = h.plan(), prepare(h, job_id="delegated")
    grant = approve(h, delegated_plan)
    with pytest.raises(ExecutionError) as error:
        h.service.submit(h.context, h.request(exact_plan, grant["grant_id"]))
    assert error.value.code == "DELEGATED_SCOPE_MISMATCH"
    with pytest.raises(ExecutionError) as error:
        h.service.submit(h.context, h.request(delegated_plan, h.grant(delegated_plan)))
    assert error.value.code == "GRANT_REQUIRED"
    request = h.request(exact_plan, h.grant(exact_plan))
    run_id = h.service.submit(h.context, request)["receipt"]["run_id"]
    run = h.service.execute_pending(h.context, run_id)
    assert run["execution"] == "FINISHED" and run["solver_conclusion"] == "NOT_RUN"
    assert h.counts()["consumption"] == 1
    assert h.store.delegated_budget(h.context, grant["grant_id"])["consumed"] == 0
