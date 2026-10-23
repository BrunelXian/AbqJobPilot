from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import threading
import time

import pytest

from abqjobpilot.execution import ExecutionError
from abqjobpilot.execution import diagnostics as diagnostic_rules
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.models import canonical_json, digest, identifier
from abqjobpilot.execution.store import ReadOnlyStore, append_event, document, update_run
from abqjobpilot.execution.fake_backend import FakeBackend
from execution_helpers import guard_environment, harness, inventory
from test_fake_reconciliation import uncertain, adoption, resume


def codes(report):
    return {d["reason_code"] for d in report["body"]["diagnostics"]}


def read(h, run_id=None):
    return h.store.diagnose(h.context, run_id or h.run_id)


def test_pending_completed_and_historical_validation_are_distinct(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    h.run_id = receipt["run_id"]
    pending = read(h)
    assert {"REQUEST_ACCEPTED", "WAITING_DISPATCH", "NO_RECORDED_ERROR"} <= codes(pending)
    assert "FAKE_COMPLETED" not in codes(pending)
    h.service.execute_pending(h.context, h.run_id)
    artifact = Path(h.context.runtime_root) / "fake_runs" / h.run_id / "result.json"
    artifact.unlink()  # The report must still describe the historical PASS only.
    complete = read(h)
    assert {"FAKE_COMPLETED", "HISTORICAL_VALIDATION_PASSED"} <= codes(complete)
    assert complete["body"]["facts"]["observations"][0]["exists"] is True
    assert "CURRENT_ARTIFACT_CONTENT_NOT_READ" in complete["body"]["unknowns"]
    assert complete["body"]["facts"]["run"]["solver_conclusion"] == "NOT_RUN"
    assert complete["body"]["facts"]["run"]["process_observation"] == "NOT_APPLICABLE"
    assert complete["body"]["facts"]["run"]["exit_verification"] == "NOT_APPLICABLE"
    assert not complete["body"]["disclosure"]["artifacts_revalidated_now"]
    for item in complete["body"]["diagnostics"]:
        assert item["recorded_facts"] and item["inference"] and item["unknowns"] and item["source_refs"]
        assert item["next_step"]["preconditions"]
        assert "confidence" not in item


def test_uncertain_insufficient_then_reconciled_paused_then_resumed(uncertain):
    h = uncertain
    before = read(h)
    assert {"EXECUTION_UNCERTAIN", "EVIDENCE_INSUFFICIENT", "DISPATCH_PAUSED"} <= codes(before)
    assert not before["body"]["facts"]["validations"]
    h.service.apply_reconciliation(h.context, adoption(h))
    adopted = read(h)
    assert {"EXPLICITLY_RECONCILED", "DISPATCH_PAUSED", "HISTORICAL_VALIDATION_PASSED"} <= codes(adopted)
    assert "EXECUTION_UNCERTAIN" not in codes(adopted)
    h.service.resume_dispatch(h.context, resume(h))
    reopened = read(h)
    assert "DISPATCH_PAUSED" not in codes(reopened)
    assert adopted["body"]["facts"]["run"] == reopened["body"]["facts"]["run"]
    assert h.effects == [h.run_id]


def test_actual_validator_failure_is_reported_without_rerunning_it(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    h.run_id = receipt["run_id"]
    original = FakeBackend.emit
    def damaged(backend, *args):
        emission = original(backend, *args)
        Path(emission["path"]).write_text("not json", encoding="utf-8")
        return emission
    monkeypatch.setattr(FakeBackend, "emit", damaged)
    h.service.execute_pending(h.context, h.run_id)
    report = read(h)
    assert {"FAKE_COMPLETED", "HISTORICAL_VALIDATION_FAILED"} <= codes(report)
    assert "HISTORICAL_VALIDATION_PASSED" not in codes(report)
    assert report["body"]["facts"]["run"]["artifact_validation"] == "INVALID"
    assert report["body"]["facts"]["validations"][0]["verdict"] == "FAIL"


def test_snapshot_real_read_write_interleaving_and_transaction_released(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    run_id = receipt["run_id"]
    read_started, write_staged, reader_released = threading.Event(), threading.Event(), threading.Event()
    writer_finished = threading.Event()
    def checkpoint(stage):
        if stage == "diagnostic:after_run":
            read_started.set()
            assert write_staged.wait(2)
        elif stage == "diagnostic:after_close":
            reader_released.set()
            assert writer_finished.wait(2)  # Commit must succeed before projection.
    monkeypatch.setattr(h.store, "_diagnostic_checkpoint", checkpoint)
    def writer():
        assert read_started.wait(2)
        with h.store.transaction("test_atomic_writer") as connection:
            run = document(connection, "runs", "run_id", run_id)
            update_run(connection, run, "DISPATCH_BLOCKED", execution="BLOCKED", queue_state="BLOCKED")
            connection.execute("UPDATE dispatch_gate SET state='PAUSED',version=version+1")
            write_staged.set()
        writer_finished.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        writing = pool.submit(writer)
        before = h.store.diagnose(h.context, run_id)
        writing.result(timeout=3)
    assert reader_released.is_set()
    assert before["body"]["view"]["run_revision"] == 1
    assert before["body"]["coverage"]["events"] == 1
    assert before["body"]["facts"]["dispatch_gate"]["state"] == "OPEN"
    monkeypatch.setattr(h.store, "_diagnostic_checkpoint", lambda stage: None)
    after = h.store.diagnose(h.context, run_id)
    assert after["body"]["view"]["run_revision"] == 2
    assert after["body"]["coverage"]["events"] == 2
    assert after["body"]["facts"]["dispatch_gate"]["state"] == "PAUSED"


def test_readonly_all_business_records_and_effect_traps(uncertain, monkeypatch):
    h = uncertain
    baseline = inventory(h.root)
    def forbidden(*args, **kwargs):
        raise AssertionError("Diagnostic must not execute, validate, reconcile, resume or write")
    monkeypatch.setattr(FakeBackend, "emit", forbidden)
    import abqjobpilot.execution.validation as validator
    import abqjobpilot.execution.reconciliation as reconciliation
    monkeypatch.setattr(validator, "validate_artifact", forbidden)
    monkeypatch.setattr(reconciliation, "preview", forbidden)
    monkeypatch.setattr(reconciliation, "manage", forbidden)
    monkeypatch.setattr(h.store, "transaction", forbidden)
    monkeypatch.setattr(h.store._session.lease, "check", forbidden)
    raw_open = Path.open
    def no_artifacts(path, *args, **kwargs):
        assert not path.is_relative_to(Path(h.context.runtime_root))
        return raw_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", no_artifacts)
    for _ in range(3): read(h)
    monkeypatch.setattr(Path, "open", raw_open)  # The independent inventory audit itself reads files.
    assert inventory(h.root) == baseline


@pytest.mark.parametrize("damage", ["missing", "corrupt", "future", "journal", "wal", "shm", "busy"])
def test_honest_read_failures_no_repair_or_path_disclosure(harness, damage):
    h = harness
    _, _, receipt = h.accept()
    path = Path(h.context.execution_store)
    lock = None
    if damage == "missing": path.unlink()
    elif damage == "corrupt": path.write_bytes(b"broken")
    elif damage == "future":
        with h.store.transaction("fixture") as c: c.execute("UPDATE meta SET value='999' WHERE key='schema'")
    elif damage in {"journal", "wal", "shm"}: path.with_name(path.name + "-" + damage).write_bytes(b"requires maintenance")
    else:
        lock = sqlite3.connect(path)
        lock.execute("BEGIN EXCLUSIVE")
    before = inventory(h.root)
    started = time.monotonic()
    try:
        with pytest.raises(ExecutionError) as error:
            h.store.diagnose(h.context, receipt["run_id"])
        assert error.value.code == {"missing": "NOT_FOUND", "future": "UNSUPPORTED_FORMAT",
                                   "journal": "STORE_REQUIRES_MAINTENANCE", "wal": "STORE_REQUIRES_MAINTENANCE",
                                   "shm": "STORE_REQUIRES_MAINTENANCE"}.get(damage, "STORE_UNAVAILABLE")
        assert str(h.root) not in canonical_json(error.value.to_dict())
        assert time.monotonic() - started < 1.5
        assert inventory(h.root) == before
    finally:
        if lock: lock.close()


def test_schema_two_reports_missing_gate_without_migration(harness):
    h = harness
    _, _, receipt = h.accept()
    manifest = Path(h.context.root) / "experiment.json"
    body = json.loads(manifest.read_text())
    body["schema_version"] = 2
    ctx = replace(h.context, schema_version=2, manifest_digest=digest(body))
    with h.store.transaction("fixture") as c:
        c.execute("UPDATE meta SET value='2' WHERE key='schema'")
        c.execute("UPDATE meta SET value=? WHERE key='context_digest'", (ctx.context_digest,))
        c.execute("DROP TABLE dispatch_gate")
        c.execute("DROP TABLE reconciliations")
    manifest.write_text(canonical_json(body), encoding="utf-8")
    before = inventory(h.root)
    report = ReadOnlyStore(ctx).diagnose(ctx, receipt["run_id"])
    assert report["body"]["facts"]["dispatch_gate"] is None
    assert "GATE_NOT_RECORDED" in report["body"]["unknowns"]
    assert inventory(h.root) == before


def test_global_event_gaps_are_not_run_history_gaps(harness):
    h = harness
    _, _, a = h.accept()
    h.accept(key="other", spec=h.spec(job_id="other"))
    h.service.execute_pending(h.context, a["run_id"])
    report = h.store.diagnose(h.context, a["run_id"])
    assert report["body"]["view"]["project_event_sequences"] == [1, 3, 4, 5]
    assert report["body"]["view"]["run_event_sequences"] == [1, 2, 3, 4]
    assert "RUN_EVENT_SEQUENCE_GAP" not in report["body"]["unknowns"]


def test_whitelist_secret_injection_and_export(harness, tmp_path):
    h = harness
    _, request, receipt = h.accept()
    run_id = receipt["run_id"]
    h.service.execute_pending(h.context, run_id)
    secret = "R5_SECRET_token_grant_command_username_external_bytes"
    with h.store.transaction("inject_test_secrets") as c:
        for table in ("runs", "receipts", "events", "observations", "validations", "plans"):
            for row in c.execute("SELECT rowid,body FROM " + table).fetchall():
                data = json.loads(row[1])
                data.update(credential=secret, grant_id=secret, environment=secret, command=secret,
                            path="C:/Users/" + secret, error={"message": secret, "code": secret, "stage": secret})
                if table == "events": data["payload"].update(secret=secret, error=secret)
                if table == "validations": data["reasons"] = [secret]
                c.execute("UPDATE " + table + " SET body=? WHERE rowid=?", (canonical_json(data), row[0]))
    report = h.store.diagnose(h.context, run_id)
    content = diagnostic_rules.report_bytes(report)
    assert secret.encode() not in content and str(h.root).encode() not in content
    assert request["grant_id"].encode() not in content and b"grant_id" not in content
    assert report["body"]["facts"]["run"]["error"]["code"] is None
    exports = tmp_path / "exports"
    exports.mkdir()
    FakeClient.export_diagnostic(report, export_root=exports, target=exports / "report.json")
    assert (exports / "report.json").read_bytes() == content


@pytest.mark.parametrize("limit", ["events", "record_bytes", "raw_bytes", "field_chars", "serialized", "deadline"])
def test_limits_explicit_no_truncation(harness, monkeypatch, limit):
    h = harness
    _, _, receipt = h.accept()
    run_id = receipt["run_id"]
    if limit in {"record_bytes", "field_chars"}:
        with h.store.transaction("large_fixture") as c:
            run = document(c, "runs", "run_id", run_id)
            run["omitted_payload"] = "x" * (16385 if limit == "record_bytes" else 1025)
            c.execute("UPDATE runs SET body=? WHERE run_id=?", (canonical_json(run), run_id))
    if limit == "events":
        with h.store.transaction("large_fixture") as c:
            for _ in range(64): append_event(c, run_id, "START_INTENT")
    if limit == "raw_bytes":
        with h.store.transaction("large_fixture") as c:
            for _ in range(27): append_event(c, run_id, "START_INTENT", {"omitted": ["x" * 1000] * 10})
    if limit == "serialized": monkeypatch.setattr(diagnostic_rules, "MAX_REPORT_BYTES", 100)
    if limit == "deadline":
        import abqjobpilot.execution.store as storage
        ticks = iter([0, 1])
        monkeypatch.setattr(storage.time, "monotonic", lambda: next(ticks, 1))
    before = inventory(h.root)
    with pytest.raises(ExecutionError) as error:
        h.store.diagnose(h.context, run_id)
    assert error.value.code == ("STORE_UNAVAILABLE" if limit == "deadline" else "LIMIT_EXCEEDED")
    assert inventory(h.root) == before


def test_missing_history_and_unrecognized_error_not_success(harness):
    h = harness
    _, _, receipt = h.accept()
    with h.store.transaction("missing_history") as c:
        c.execute("DELETE FROM receipts")
        c.execute("DELETE FROM events")
    report = h.store.diagnose(h.context, receipt["run_id"])
    assert {"ORIGINAL_RECEIPT_NOT_RECORDED", "RUN_EVENT_SEQUENCE_GAP"} <= set(report["body"]["unknowns"])
    assert "REQUEST_ACCEPTED" not in codes(report)
    assert "NO_RECORDED_ERROR" in codes(report) and "FAKE_COMPLETED" not in codes(report)


def test_export_original_view_offline_without_store_network_or_owner(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    report = h.store.diagnose(h.context, receipt["run_id"])
    h.service.execute_pending(h.context, receipt["run_id"])
    baseline = inventory(Path(h.context.root))
    h.store.close()
    def forbidden(*args, **kwargs): raise AssertionError("Export must not query")
    monkeypatch.setattr(FakeClient, "call", forbidden)
    monkeypatch.setattr(ReadOnlyStore, "diagnose", forbidden)
    exports = h.root / "exports"
    exports.mkdir()
    result = FakeClient.export_diagnostic(report, export_root=exports, target=exports / "original.json")
    offline = json.loads((exports / "original.json").read_text(encoding="utf-8"))
    assert offline == report and result["content_digest"] == digest(offline["body"])
    assert offline["body"]["facts"]["run"]["execution"] == "PLANNED"
    assert offline["body"]["disclosure"]["executable_authorization"] is False
    assert offline["body"]["disclosure"]["artifact_bytes_included"] is False
    assert inventory(Path(h.context.root)) == baseline


@pytest.mark.parametrize("problem", ["escape", "parent", "existing", "junction", "write", "publish_race", "injected_report", "changed_digest"])
def test_export_path_and_failure_boundaries(harness, monkeypatch, problem):
    h = harness
    _, _, receipt = h.accept()
    report = h.store.diagnose(h.context, receipt["run_id"])
    exports = h.root / "exports"
    exports.mkdir()
    target = exports / "audit.json"
    baseline = inventory(Path(h.context.root))
    if problem == "escape": target = h.root / "escape.json"
    if problem == "parent": target = exports / ".." / "escape.json"
    if problem == "existing": target.write_bytes(b"preserve")
    if problem == "junction":
        from test_execution_isolation import _junction
        other = h.root / "other_exports"
        other.mkdir()
        exports = h.root / "link_exports"
        _junction(exports, other)
        target = exports / "audit.json"
    if problem == "write":
        import abqjobpilot.execution.audit_export as export
        monkeypatch.setattr(export.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("SECRET_write_error")))
    if problem == "publish_race":
        rename = Path.rename
        def conflict(path, dest):
            dest.write_bytes(b"preserve")
            return rename(path, dest)
        monkeypatch.setattr(Path, "rename", conflict)
    if problem == "injected_report":
        report["body"]["facts"]["run"]["credential"] = "SECRET_export"
        report["content_digest"] = digest(report["body"])
    if problem == "changed_digest": report["content_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ExecutionError) as error:
        FakeClient.export_diagnostic(report, export_root=exports, target=target)
    assert "SECRET" not in str(error.value) and str(h.root) not in str(error.value)
    assert inventory(Path(h.context.root)) == baseline
    if problem in {"existing", "publish_race"}: assert target.read_bytes() == b"preserve"
    elif problem not in {"parent", "escape"}: assert not target.exists()
    assert not list(exports.glob("*.partial"))


def test_audit_cannot_be_submitted_as_execution_or_management_request(harness):
    h = harness
    _, _, receipt = h.accept()
    report = h.store.diagnose(h.context, receipt["run_id"])
    before = inventory(h.root)
    for method in (h.service.submit, h.service.apply_reconciliation, h.service.resume_dispatch):
        with pytest.raises(ExecutionError) as error: method(h.context, report)
        assert error.value.code == "INVALID_REQUEST"
    assert inventory(h.root) == before


@pytest.mark.parametrize("table,cap,prefix", [("observations", 16, "obs"), ("validations", 16, "val"), ("reconciliations", 8, "rec")])
def test_each_evidence_collection_has_hard_record_limit(harness, table, cap, prefix):
    h = harness
    _, _, receipt = h.accept()
    with h.store.transaction("large_fixture") as c:
        for _ in range(cap + 1):
            c.execute("INSERT INTO " + table + " VALUES(?,?,?)", (identifier(prefix), receipt["run_id"], "{}"))
    baseline = inventory(h.root)
    with pytest.raises(ExecutionError) as error: h.store.diagnose(h.context, receipt["run_id"])
    assert error.value.code == "LIMIT_EXCEEDED"
    assert inventory(h.root) == baseline


def test_reconciliation_private_fields_and_storage_error_are_not_echoed(uncertain, monkeypatch):
    h = uncertain
    h.service.apply_reconciliation(h.context, adoption(h))
    secret = "R5_SECRET_reconciliation_and_store_error"
    with h.store.transaction("inject_test_secret") as c:
        row = c.execute("SELECT reconciliation_id,body FROM reconciliations").fetchone()
        value = json.loads(row[1])
        value["preview"]["evidence_fingerprint"]["path"] = "C:/Users/" + secret
        value["snapshot"]["path"] = secret
        value["management_grant_id"] = secret
        c.execute("UPDATE reconciliations SET body=? WHERE reconciliation_id=?", (canonical_json(value), row[0]))
    assert secret not in canonical_json(read(h))
    import abqjobpilot.execution.store as storage
    monkeypatch.setattr(storage, "_connection", lambda *a, **k: (_ for _ in ()).throw(OSError(secret)))
    with pytest.raises(ExecutionError) as error: read(h)
    assert error.value.code == "STORE_UNAVAILABLE" and secret not in canonical_json(error.value.to_dict())


def test_report_rule_computation_is_deterministic_for_same_snapshot(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    import abqjobpilot.execution.store as storage
    monkeypatch.setattr(storage, "now", lambda: 123456)
    one = h.store.diagnose(h.context, receipt["run_id"])
    two = h.store.diagnose(h.context, receipt["run_id"])
    assert one == two
    assert one["body"]["view"]["read_at"] == 123456
    assert one["body"]["facts"]["receipt"]["accepted_at"] != 123456


@pytest.mark.parametrize("table,key", [("runs", "run_id"), ("runs", "project_instance_id"), ("plans", "plan_id"),
                                       ("events", "run_id"), ("observations", "run_id")])
def test_inconsistent_persisted_bindings_are_not_misreported(harness, table, key):
    h = harness
    _, _, receipt = h.accept()
    h.service.execute_pending(h.context, receipt["run_id"])
    with h.store.transaction("corrupted_binding") as c:
        row = c.execute("SELECT rowid,body FROM " + table + " LIMIT 1").fetchone()
        value = json.loads(row[1])
        value[key] = "R5_SECRET_inconsistent_identity"
        c.execute("UPDATE " + table + " SET body=? WHERE rowid=?", (canonical_json(value), row[0]))
    baseline = inventory(h.root)
    with pytest.raises(ExecutionError) as error: h.store.diagnose(h.context, receipt["run_id"])
    assert error.value.code == "STORE_UNAVAILABLE" and "R5_SECRET" not in str(error.value)
    assert inventory(h.root) == baseline


def test_actual_blocked_error_code_is_preserved_without_free_message(harness, monkeypatch):
    h = harness
    plan, _, receipt = h.accept()
    import abqjobpilot.execution.planning as planning
    monkeypatch.setattr(planning, "now", lambda: plan.to_dict()["expires_at"])
    with pytest.raises(ExecutionError): h.service.execute_pending(h.context, receipt["run_id"])
    report = h.store.diagnose(h.context, receipt["run_id"])
    assert "DISPATCH_BLOCKED" in codes(report)
    assert report["body"]["facts"]["run"]["error"]["code"] == "PLAN_EXPIRED"
    assert "message" not in report["body"]["facts"]["run"]["error"]


def test_export_cleanup_failure_leaves_identifiable_partial_and_no_success(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    report = h.store.diagnose(h.context, receipt["run_id"])
    exports = h.root / "exports"
    exports.mkdir()
    import abqjobpilot.execution.audit_export as export
    monkeypatch.setattr(export.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("test disk failure")))
    monkeypatch.setattr(Path, "unlink", lambda *a, **k: (_ for _ in ()).throw(PermissionError("test cleanup failure")))
    baseline = inventory(Path(h.context.root))
    with pytest.raises(ExecutionError) as error:
        FakeClient.export_diagnostic(report, export_root=exports, target=exports / "not-published.json")
    assert error.value.code == "EXPORT_FAILED"
    assert not (exports / "not-published.json").exists()
    assert len(list(exports.glob("audit_*.partial"))) == 1
    assert inventory(Path(h.context.root)) == baseline


@pytest.mark.parametrize("part", ["manifest", "metadata_count", "metadata_field", "gate"])
def test_diagnostic_connection_metadata_and_manifest_are_bounded(harness, part):
    h = harness
    _, _, receipt = h.accept()
    if part == "manifest":
        (Path(h.context.root) / "experiment.json").write_bytes(b" " * 16385)
    else:
        with h.store.transaction("large_connection_fixture") as c:
            if part == "metadata_count":
                c.executemany("INSERT INTO meta VALUES(?,?)", [("test_extra_" + str(i), "value") for i in range(17)])
            elif part == "metadata_field":
                c.execute("INSERT INTO meta VALUES('test_extra',?)", ("x" * 1025,))
            else:
                c.execute("UPDATE dispatch_gate SET owner_id=?", ("x" * 257,))
    baseline = inventory(h.root)
    with pytest.raises(ExecutionError) as error: h.store.diagnose(h.context, receipt["run_id"])
    assert error.value.code == "LIMIT_EXCEEDED"
    assert inventory(h.root) == baseline
