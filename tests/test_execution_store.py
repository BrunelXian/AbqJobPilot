from dataclasses import replace
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from abqjobpilot.execution import ExecutionError, ExperimentStore, open_existing_read_only
from abqjobpilot.execution.fake_backend import FakeBackend
from abqjobpilot.execution.models import bytes_digest, canonical_json
from abqjobpilot.execution.paths import result_path
from abqjobpilot.execution import store as store_module
from execution_helpers import guard_environment, harness, inventory


def test_reopen_readonly_retains_receipt_run_events_validation_without_writes(harness):
    h = harness
    _, _, receipt = h.accept()
    run = h.service.execute_pending(h.context, receipt["run_id"])
    events = h.store.events(h.context)
    validations = h.store.validations(h.context, run["run_id"])
    h.store.close()
    before = inventory(h.root)
    reader = open_existing_read_only(h.context)
    for _ in range(3):
        assert reader.query_receipt(h.context, "test-client", "request-1") == receipt
        assert reader.query_run(h.context, run["run_id"]) == run
        assert reader.events(h.context) == events
        assert reader.validations(h.context, run["run_id"]) == validations
        assert len(reader.observations(h.context, run["run_id"])) == 1
    assert inventory(h.root) == before
    with pytest.raises(ExecutionError) as failure:
        ExperimentStore(h.context)
    assert failure.value.code == "OWNER_UNCONFIRMED"


@pytest.mark.parametrize("fault", ["missing", "corrupt", "future_schema", "wal", "shm", "journal"])
def test_query_failures_never_initialize_migrate_or_repair(harness, fault):
    h = harness
    path = Path(h.context.execution_store)
    h.store.close()
    if fault == "missing":
        path.unlink()
    elif fault == "corrupt":
        path.write_bytes(b"not a database")
    elif fault == "future_schema":
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE meta SET value='999' WHERE key='schema'")
    else:
        path.with_name(path.name + "-" + fault).write_bytes(b"do not recover")
    before = inventory(h.root)
    with pytest.raises(ExecutionError):
        open_existing_read_only(h.context)
    assert inventory(h.root) == before


def test_readonly_connection_enforces_query_only_and_foreign_keys(harness):
    h = harness
    reader = open_existing_read_only(h.context)
    with reader.read() as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM meta")
    with h.store.transaction("constraint_check") as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO consumption VALUES('unknown-grant','unknown-run')")


def test_accept_transaction_failure_rolls_back_all_acceptance_records(harness, monkeypatch):
    h = harness
    plan = h.plan()
    request = h.request(plan, h.grant(plan))
    def fail(name):
        if name == "accept:before_commit":
            raise OSError("injected acceptance failure")
    monkeypatch.setattr(h.store, "_checkpoint", fail)
    with pytest.raises(ExecutionError):
        h.service.submit(h.context, request)
    assert h.counts() == dict(runs=0, receipts=0, events=0, consumption=0, observations=0, validations=0)
    assert not list(h.root.rglob("result.json"))
    monkeypatch.setattr(h.store, "_checkpoint", lambda name: None)
    receipt = h.service.submit(h.context, request)["receipt"]
    assert h.store.query_run(h.context, receipt["run_id"])["attempt_no"] == 1


def test_lost_acceptance_response_replays_committed_receipt(harness, monkeypatch):
    h = harness
    plan = h.plan()
    request = h.request(plan, h.grant(plan))
    def fail(name):
        if name == "accept:after_commit":
            raise OSError("response lost")
    monkeypatch.setattr(h.store, "_checkpoint", fail)
    with pytest.raises(ExecutionError) as failure:
        h.service.submit(h.context, request)
    assert failure.value.code == "ACCEPTANCE_UNKNOWN"
    original = h.store.query_receipt(h.context, "test-client", "request-1")
    monkeypatch.setattr(h.store, "_checkpoint", lambda name: None)
    assert h.service.submit(h.context, request)["receipt"] == original
    assert not list(h.root.rglob("result.json"))


def test_claim_transaction_failure_has_no_effect_or_partial_claim(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    def fail(name):
        if name == "claim:before_commit":
            raise OSError("claim failed before commit")
    monkeypatch.setattr(h.store, "_checkpoint", fail)
    with pytest.raises(ExecutionError):
        h.service.execute_pending(h.context, receipt["run_id"])
    assert h.store.query_run(h.context, receipt["run_id"])["queue_state"] == "PENDING"
    assert h.counts()["events"] == 1 and not list(h.root.rglob("result.json"))
    with h.store.read() as connection:
        assert connection.execute("SELECT run_id FROM slot").fetchone()[0] is None


@pytest.mark.parametrize("fault", ["after_claim", "file_write", "observe", "terminal", "terminal_and_uncertain"])
def test_post_claim_failures_preserve_uncertainty_and_never_repeat_effect(harness, monkeypatch, fault):
    h = harness
    _, request, receipt = h.accept()
    run_id = receipt["run_id"]
    original, calls = FakeBackend.emit, []
    def emit(*args):
        calls.append(1)
        result = original(*args)
        if fault == "file_write":
            raise OSError("file exists but writer outcome unavailable")
        return result
    monkeypatch.setattr(FakeBackend, "emit", emit)
    def fail(name):
        points = {"after_claim": {"dispatch:after_claim"}, "file_write": set(),
                  "observe": {"observe:before_commit"}, "terminal": {"terminal:before_commit"},
                  "terminal_and_uncertain": {"terminal:before_commit", "uncertain:before_commit"}}
        if name in points[fault]:
            raise OSError("injected " + name)
    monkeypatch.setattr(h.store, "_checkpoint", fail)
    with pytest.raises(ExecutionError) as failure:
        h.service.execute_pending(h.context, run_id)
    assert failure.value.reconcile
    monkeypatch.setattr(h.store, "_checkpoint", lambda name: None)
    run = h.service.execute_pending(h.context, run_id)
    assert run["reconciliation_requirement"] == "RECONCILIATION_REQUIRED"
    assert run["artifact_validation"] != "VALID"
    assert len(calls) == (0 if fault == "after_claim" else 1)
    assert result_path(h.context, run_id).exists() is (fault != "after_claim")
    assert h.counts()["validations"] == h.counts()["observations"] == 0
    assert h.service.submit(h.context, request)["receipt"] == receipt
    _, _, second = h.accept(key="another", spec=h.spec(job_id="j_another"))
    with pytest.raises(ExecutionError) as busy:
        h.service.execute_pending(h.context, second["run_id"])
    assert busy.value.code == "SLOT_BUSY"
    h.store.close()
    before = inventory(h.root)
    reader = open_existing_read_only(h.context)
    assert reader.query_run(h.context, run_id)["reconciliation_requirement"] == "RECONCILIATION_REQUIRED"
    assert inventory(h.root) == before


@pytest.mark.parametrize("tamper", ["missing", "malformed", "run_id", "phase_attempt_id", "plan_digest", "old_success", "digest"])
def test_fake_completion_and_artifact_validation_are_separate(harness, monkeypatch, tamper):
    h = harness
    original = FakeBackend.emit
    def emit(*args):
        evidence = original(*args)
        path = Path(evidence["path"])
        if tamper == "missing":
            path.unlink()
        elif tamper in {"malformed", "old_success"}:
            path.write_text("THE ANALYSIS HAS COMPLETED SUCCESSFULLY", encoding="utf-8")
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            if tamper == "digest":
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                data[tamper] = "old_attempt"
                path.write_text(canonical_json(data), encoding="utf-8")
                # Even a matching file digest cannot replace Run/phase/plan binding checks.
                content = path.read_bytes()
                evidence.update(digest=bytes_digest(content), size=len(content))
        return evidence
    monkeypatch.setattr(FakeBackend, "emit", emit)
    _, _, receipt = h.accept()
    run = h.service.execute_pending(h.context, receipt["run_id"])
    assert run["backend_outcome"] == "COMPLETED" and run["execution"] == "FINISHED"
    assert run["artifact_validation"] in {"INVALID", "UNKNOWN"}
    assert run["solver_conclusion"] == "NOT_RUN"
    assert h.store.validations(h.context, run["run_id"])[0]["verdict"] in {"FAIL", "UNKNOWN"}


def test_existing_old_output_is_not_overwritten_or_adopted(harness):
    h = harness
    _, _, receipt = h.accept()
    path = result_path(h.context, receipt["run_id"])
    path.parent.mkdir(parents=True)
    path.write_text("old successful result", encoding="utf-8")
    with pytest.raises(ExecutionError):
        h.service.execute_pending(h.context, receipt["run_id"])
    assert path.read_text(encoding="utf-8") == "old successful result"
    assert h.store.query_run(h.context, receipt["run_id"])["reconciliation_requirement"] == "RECONCILIATION_REQUIRED"


def test_copied_project_does_not_inherit_execution_permission(harness):
    h = harness
    h.accept()
    copy_root = h.root / "copy"
    shutil.copytree(h.context.root, copy_root)
    copied = replace(h.context, root=str(copy_root), runtime_root=str(copy_root / "runtime"),
                     execution_store=str(copy_root / "execution.sqlite3"))
    before = inventory(copy_root)
    with pytest.raises(ExecutionError) as failure:
        ExperimentStore(copied)
    assert failure.value.code == "OWNER_UNCONFIRMED"
    assert inventory(copy_root) == before


@pytest.mark.parametrize("value", [[], {"format_id": "future", "schema_version": 1}])
def test_malformed_manifest_is_structured_error_without_repair(harness, value):
    h = harness
    (Path(h.context.root) / "experiment.json").write_text(json.dumps(value), encoding="utf-8")
    before = inventory(h.root)
    with pytest.raises(ExecutionError) as failure:
        open_existing_read_only(h.context)
    assert failure.value.code == "UNSUPPORTED_FORMAT"
    assert inventory(h.root) == before


def test_response_failure_after_terminal_commit_does_not_repeat(harness, monkeypatch):
    h = harness
    _, request, receipt = h.accept()
    original, calls = FakeBackend.emit, []
    def emit(*args):
        calls.append(1)
        return original(*args)
    monkeypatch.setattr(FakeBackend, "emit", emit)
    with monkeypatch.context() as local:
        def lost(*args):
            raise ExecutionError("STORE_UNAVAILABLE", "response read failed")
        local.setattr(h.store, "query_run", lost)
        with pytest.raises(ExecutionError) as failure:
            h.service.execute_pending(h.context, receipt["run_id"])
        assert failure.value.to_dict()["request_status"] == "ACCEPTED"
    assert h.service.submit(h.context, request)["receipt"] == receipt
    assert h.service.execute_pending(h.context, receipt["run_id"])["execution"] == "FINISHED"
    assert len(calls) == 1


def test_retry_of_uncertain_run_is_rejected(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    def failed(*args):
        raise OSError("uncertain emission")
    monkeypatch.setattr(FakeBackend, "emit", failed)
    with pytest.raises(ExecutionError):
        h.service.execute_pending(h.context, receipt["run_id"])
    with pytest.raises(ExecutionError) as failure:
        h.accept(key="retry", retry_of=receipt["run_id"])
    assert failure.value.code == "INVALID_RETRY"


def test_commit_acknowledgement_failure_queries_existing_acceptance(harness, monkeypatch):
    h = harness
    plan = h.plan()
    request = h.request(plan, h.grant(plan))
    original = store_module._connection
    class LostCommitAcknowledgement:
        def __init__(self, connection):
            self.connection = connection
        def __getattr__(self, name):
            return getattr(self.connection, name)
        def commit(self):
            self.connection.commit()
            raise sqlite3.OperationalError("commit succeeded but acknowledgement lost")
    with monkeypatch.context() as local:
        def connect(context, *, read_only):
            connection = original(context, read_only=read_only)
            return connection if read_only else LostCommitAcknowledgement(connection)
        local.setattr(store_module, "_connection", connect)
        with pytest.raises(ExecutionError) as failure:
            h.service.submit(h.context, request)
        assert failure.value.code == "ACCEPTANCE_UNKNOWN"
    original_receipt = h.store.query_receipt(h.context, "test-client", "request-1")
    assert h.service.submit(h.context, request)["receipt"] == original_receipt
    assert h.counts()["runs"] == h.counts()["consumption"] == 1
