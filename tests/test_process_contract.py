"""Negative pre-launch gates retain the original effective subprocess trap."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from abqjobpilot.execution import ExecutionError, ExecutionService
from abqjobpilot.execution.models import canonical_json, now
from abqjobpilot.execution.process_backend import ProcessFixtureConfig
from execution_helpers import guard_environment, harness, inventory


def process_plan(h, scenario="normal"):
    h.service = ExecutionService(h.context, h.store, client_namespace="test-client", process_config=ProcessFixtureConfig.current())
    return h.service.prepare(h.context, h.spec(), h.config, expires_at=now() + 300, process_scenario=scenario)


@pytest.mark.parametrize("changes,code", [({}, "TEST_GRANT_ONLY"),
    ({"issuer": "ProcessGrantFixture"}, "GRANT_SCOPE_MISMATCH"),
    ({"issuer": "ProcessGrantFixture", "allowed_action": "launch_fixed_python_fixture", "expires_at": 0}, "GRANT_EXPIRED"),
    ({"issuer": "ProcessGrantFixture", "allowed_action": "launch_fixed_python_fixture", "plan_digest": "wrong"}, "GRANT_SCOPE_MISMATCH"),
    ({"issuer": "ProcessGrantFixture", "allowed_action": "launch_fixed_python_fixture", "resource_limits": {"slots": 5}}, "GRANT_SCOPE_MISMATCH")])
def test_process_requires_exact_dedicated_test_grant_before_any_launch(harness, changes, code):
    h = harness
    plan = process_plan(h)
    request = h.request(plan, h.grant(plan, **changes))
    with pytest.raises(ExecutionError) as error:
        h.service.submit(h.context, request)
    assert error.value.code == code
    assert h.counts()["runs"] == 0
    assert not (Path(h.context.runtime_root) / "process_runs").exists()


@pytest.mark.parametrize("field,value", [("fixture_digest", "sha256:wrong"), ("image_digest", "sha256:wrong"),
    ("interpreter_digest", "sha256:wrong"), ("interpreter", "C:\\forbidden.exe"),
    ("max_seconds", 1000)])
def test_execution_object_identity_and_budget_rejected(harness, field, value):
    h = harness
    config = replace(ProcessFixtureConfig.current(), **{field: value})
    h.service = ExecutionService(h.context, h.store, process_config=config)
    with pytest.raises(ExecutionError) as error:
        h.service.prepare(h.context, h.spec(), h.config, expires_at=now() + 300, process_scenario="normal")
    assert error.value.code in {"PLAN_STALE", "RESOURCE_LIMIT"}
    assert h.counts()["runs"] == 0


@pytest.mark.parametrize("scenario", ["shell", "normal --command evil", {"command": "evil"}, 1])
def test_scenario_is_a_strict_enum_not_a_command(harness, scenario):
    with pytest.raises(ExecutionError):
        process_plan(harness, scenario)


@pytest.mark.parametrize("field", ["command", "environment", "working_directory", "backend", "approved"])
def test_client_cannot_supply_process_controls(harness, field):
    h = harness
    plan = process_plan(h)
    grant = h.grant(plan, issuer="ProcessGrantFixture", allowed_action="launch_fixed_python_fixture")
    request = h.request(plan, grant, **{field: "forbidden"})
    with pytest.raises(ExecutionError) as error:
        h.service.submit(h.context, request)
    assert error.value.code == "INVALID_REQUEST"
    assert h.counts()["runs"] == 0


@pytest.mark.parametrize("change", ["fixture", "input", "grant", "backend_configuration"])
def test_accepted_process_plan_is_rechecked_at_dispatch_without_start(harness, monkeypatch, change):
    h = harness
    plan = process_plan(h)
    grant = h.grant(plan, issuer="ProcessGrantFixture", allowed_action="launch_fixed_python_fixture")
    receipt = h.service.submit(h.context, h.request(plan, grant))["receipt"]
    if change == "fixture":
        original = Path.read_bytes
        monkeypatch.setattr(Path, "read_bytes", lambda p: b"changed" if p.name == "process_fixture.py" else original(p))
    elif change == "input":
        h.input.write_text("changed")
    elif change == "backend_configuration":
        h.service._process_backend.config = replace(h.service._process_backend.config, max_seconds=39)
    else:
        with h.store.transaction("test_expire") as connection:
            data = json.loads(connection.execute("SELECT body FROM grants WHERE grant_id=?", (grant,)).fetchone()[0])
            data["expires_at"] = 0
            connection.execute("UPDATE grants SET body=? WHERE grant_id=?", (canonical_json(data), grant))
    with pytest.raises(ExecutionError) as error:
        h.service.execute_pending(h.context, receipt["run_id"])
    assert error.value.code in {"PLAN_STALE", "GRANT_EXPIRED"}
    run = h.store.query_run(h.context, receipt["run_id"])
    assert run["execution"] == "BLOCKED" and run["process_records"] == []
    assert h.counts()["consumption"] == 1
    assert not (Path(h.context.runtime_root) / "process_runs").exists()


@pytest.mark.parametrize("change", ["grant_expired", "input_changed"])
def test_delayed_start_rechecks_permission_and_input_before_os_creation(harness, change):
    h = harness
    plan = process_plan(h)
    grant = h.grant(plan, issuer="ProcessGrantFixture", allowed_action="launch_fixed_python_fixture")
    rid = h.service.submit(h.context, h.request(plan, grant))["receipt"]["run_id"]
    def checkpoint(stage):
        if stage != "process:before_create":
            return
        if change == "input_changed":
            h.input.write_text("changed after claim")
        else:
            with h.store.transaction("fixture_expire_after_claim") as connection:
                value = json.loads(connection.execute("SELECT body FROM grants WHERE grant_id=?", (grant,)).fetchone()[0])
                value["expires_at"] = 0
                connection.execute("UPDATE grants SET body=? WHERE grant_id=?", (canonical_json(value), grant))
    h.store._checkpoint = checkpoint
    with pytest.raises(ExecutionError):
        h.service.execute_pending(h.context, rid)
    run = h.store.query_run(h.context, rid)
    assert run["process_failure_code"] == ("GRANT_EXPIRED" if change == "grant_expired" else "PLAN_STALE")
    assert run["process_records"] == [] and run["process_observation"] == "UNKNOWN"
    assert run["reconciliation_requirement"] == "RECONCILIATION_REQUIRED" and h.counts()["consumption"] == 1
    assert not list(Path(h.context.runtime_root).rglob("launcher.json"))


def test_no_process_configuration_cannot_dispatch_process_plan(harness):
    h = harness
    plan = process_plan(h)
    grant = h.grant(plan, issuer="ProcessGrantFixture", allowed_action="launch_fixed_python_fixture")
    old_service = ExecutionService(h.context, h.store)
    with pytest.raises(ExecutionError) as error:
        old_service.submit(h.context, h.request(plan, grant))
    assert error.value.code == "TEST_GRANT_ONLY"


def test_invalid_trusted_backend_configuration_does_not_leak_owner_lock(harness):
    h = harness
    authority = h.store._session.authority_instance
    h.store.close()
    from abqjobpilot.execution.supervisor import FakeSupervisor
    from abqjobpilot.execution.store import acquire_supervisor_store
    bootstrap = {"authority_instance": authority, "credential": "x" * 32, "client_namespace": "test-client"}
    with pytest.raises(ExecutionError) as error:
        FakeSupervisor(h.context, bootstrap, process_config=object())
    assert error.value.code == "INVALID_REQUEST"
    successor = acquire_supervisor_store(h.context, authority)
    assert successor.gate()["state"] == "PAUSED"
    successor.close()


def test_dedicated_process_grant_cannot_expand_original_fake(harness):
    h = harness
    plan = h.plan()
    grant = h.grant(plan, issuer="ProcessGrantFixture", allowed_action="launch_fixed_python_fixture")
    with pytest.raises(ExecutionError) as error:
        h.service.submit(h.context, h.request(plan, grant))
    assert error.value.code == "TEST_GRANT_ONLY"


def test_opt_in_process_capability_does_not_change_fake_no_launch_path(harness):
    h = harness
    h.service = ExecutionService(h.context, h.store, process_config=ProcessFixtureConfig.current())
    _, _, receipt = h.accept()
    result = h.service.execute_pending(h.context, receipt["run_id"])
    assert result["process_observation"] == result["exit_verification"] == "NOT_APPLICABLE"
    assert result["backend_id"] == "fake-v1" and result["artifact_validation"] == "VALID"


def test_missing_historical_exit_records_are_not_filled_from_projection(harness):
    h = harness
    plan = process_plan(h)
    grant = h.grant(plan, issuer="ProcessGrantFixture", allowed_action="launch_fixed_python_fixture")
    rid = h.service.submit(h.context, h.request(plan, grant))["receipt"]["run_id"]
    # Deliberately incomplete historical fixture, never claimed as real process evidence.
    with h.store.transaction("fixture_incomplete_history") as connection:
        run = json.loads(connection.execute("SELECT body FROM runs WHERE run_id=?", (rid,)).fetchone()[0])
        run.update(execution="FINISHED", backend_outcome="COMPLETED", exit_verification="VERIFIED")
        connection.execute("UPDATE runs SET body=? WHERE run_id=?", (canonical_json(run), rid))
    before = inventory(h.root)
    report = h.store.diagnose(h.context, rid)
    assert inventory(h.root) == before
    codes = [d["reason_code"] for d in report["body"]["diagnostics"]]
    assert "PROCESS_EXIT_NOT_ESTABLISHED" in codes
    assert "TEST_PROCESS_COMPLETED" not in codes and "FAKE_COMPLETED" not in codes


@pytest.mark.parametrize("corruption", ["boolean_version", "duplicate_key", "wrong_instance", "wrong_phase"])
def test_process_validator_rejects_lookalike_content_without_process_authority(harness, corruption):
    h = harness
    plan = process_plan(h)
    grant = h.grant(plan, issuer="ProcessGrantFixture", allowed_action="launch_fixed_python_fixture")
    rid = h.service.submit(h.context, h.request(plan, grant))["receipt"]["run_id"]
    run = h.store.query_run(h.context, rid)
    from abqjobpilot.execution.process_contract import directory, expected_result
    from abqjobpilot.execution.process_validation import validate_process_artifact
    root = directory(h.context, run)
    root.mkdir(parents=True)
    data = expected_result(h.context, plan.to_dict(), run)
    if corruption == "boolean_version": data["backend_version"] = True
    if corruption == "wrong_instance": data["project_instance_id"] = "wrong"
    if corruption == "wrong_phase": data["phase_attempt_id"] = "wrong"
    content = canonical_json(data)
    if corruption == "duplicate_key": content = '{"simulation":true,' + content[1:]
    (root / "result.json").write_text(content, encoding="utf-8")
    _, validation = validate_process_artifact(h.context, plan.to_dict(), run)
    assert validation["verdict"] == "FAIL"
    assert h.store.query_run(h.context, rid)["execution"] == "PLANNED"
