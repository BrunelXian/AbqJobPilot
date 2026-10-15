"""Metadata-only Run 004 recovery tests; all paths are temporary fixtures."""

import hashlib
import json
import multiprocessing
import sqlite3
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from abqjobpilot.database import ProjectHistoryRepository
from abqjobpilot.project import ProjectManager
from abqjobpilot.queue_store import build_queue_record, read_queue, save_queue
from abqjobpilot.recovery_workflow import (INTERRUPTED, apply_approved_recovery,
                                           approve_local_plan, build_recovery_plan)
from abqjobpilot.runtime_coordination import RunnerOwnership
from abqjobpilot.utils import write_json


CLEAR = lambda: {"state": "CLEAR", "matches": []}
UNKNOWN = lambda: {"state": "UNKNOWN", "reason": "test probe unavailable"}


@pytest.fixture(autouse=True)
def mocked_solver_exit_identity():
    # Run 004 unit fixtures simulate a verified lineage; Run 005 exercises the
    # actual Windows query and conservative missing-identity behavior separately.
    with patch("abqjobpilot.recovery_workflow.verify_launch_evidence",
               return_value={"state": "CONFIRMED_EXITED", "reason": "fixture-only observed exit"}):
        yield


def _fixture(tmp_path, *, running=True, live_exit=True, project=False):
    if project:
        formal = ProjectManager(recent_file=tmp_path / "recent.json").create_project(tmp_path / "project", "Test")
        runtime, db = formal.runtime_dir, formal.root / "project.db"
    else:
        runtime, db = tmp_path / "runtime", None
        runtime.mkdir()
    work = tmp_path / "engineering"
    work.mkdir()
    inp = work / "case.inp"
    inp.write_text("*Heading\n", encoding="utf-8")
    row = build_queue_record(inp, 2, 0, "batch", "strategy", None, True, True, "")
    if running:
        row.update(status="FULL_RUNNING", phase="FULL_RUNNING", started_at="2026-01-01T00:00:00")
    save_queue([row], runtime_dir=runtime)
    live = {"phase": "FULL_RUNNING" if running else "IDLE", "queue_id": row["queue_id"],
            "started_at": row.get("started_at"), "schema_version": "1.0",
            "process_identity": {"runtime_dir": str(runtime.resolve()), "queue_id": row["queue_id"],
                                 "phase": "FULL_RUNNING" if running else "IDLE"}}
    if live_exit:
        live["return_code"] = 0
    write_json(runtime / "live_status.json", live)
    return runtime, db, row, inp


def _plan(runtime, db=None, probe=CLEAR):
    return build_recovery_plan(runtime, project_db=db, process_probe=probe)


def _approve(plan):
    with patch("tkinter.messagebox.askyesno", return_value=True):
        return approve_local_plan(plan, Mock(winfo_exists=lambda: True))


def _hold_owner(runtime, ready, release):
    owner = RunnerOwnership(runtime)
    owner.acquire()
    ready.set()
    release.wait(10)
    owner.release()


def test_clean_idle_and_repeated_readonly_assessment(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path, running=False)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime.iterdir() if p.is_file()}
    first = _plan(runtime)
    second = _plan(runtime)
    assert first.assessment["status"] == "CLEAN"
    assert not first.can_apply and first.to_json() == second.to_json()
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime.iterdir() if p.is_file()}
    # The fixture's save_queue created this lock; assessment must not change it.
    assert (runtime / ".queue.lock").exists()


def test_exact_exit_evidence_produces_only_interrupted_and_idle(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path)
    plan = _plan(runtime)
    assert plan.can_apply
    assert plan.affected_queue_ids == (row["queue_id"],)
    assert [(item["target"], item["to"]) for item in plan.transitions] == [
        ("queue", INTERRUPTED), ("live_status", "IDLE")]
    assert all(item["reason"] and item["evidence"]["return_code"] == 0 for item in plan.transitions)
    assert json.loads(plan.to_json())["plan_id"] == plan.plan_id
    assert read_queue(runtime, strict=True)[0]["status"] == "FULL_RUNNING"


@pytest.mark.parametrize("change", ["no_exit", "unknown_probe", "lock", "odb", "malformed_live", "identity"])
def test_uncertainty_blocks_metadata_correction(tmp_path, change):
    runtime, db, row, inp = _fixture(tmp_path, live_exit=change != "no_exit")
    if change == "lock":
        (inp.parent / "case.lck").write_text("locked", encoding="utf-8")
    elif change == "odb":
        (inp.parent / "case.odb").write_text("not proof", encoding="utf-8")
        (inp.parent / "case.lck").write_text("locked", encoding="utf-8")
    elif change == "malformed_live":
        (runtime / "live_status.json").write_text("{bad", encoding="utf-8")
    elif change == "identity":
        write_json(runtime / "live_status.json", {"phase": "FULL_RUNNING", "queue_id": "other",
                                                  "return_code": 0, "started_at": row["started_at"]})
    plan = _plan(runtime, probe=UNKNOWN if change == "unknown_probe" else CLEAR)
    assert not plan.can_apply if change != "odb" else plan.can_apply is False
    assert _approve(plan) is None


def test_odb_without_lock_never_proves_completion(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path, live_exit=False)
    (inp.parent / "case.odb").write_text("old", encoding="utf-8")
    plan = _plan(runtime)
    assert not plan.can_apply
    assert not plan.transitions


def test_active_runner_blocks_plan(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path)
    # Existing stale RUNNING guard prevents a real owner acquisition; lock only
    # the fixture's owner file to simulate a separately owning process.
    actual = _plan(runtime).assessment
    with patch("abqjobpilot.recovery_workflow.assess_runtime") as assess:
        actual["owner"] = {"state": "ACTIVE", "metadata": {"token": "fixture"}}
        assess.return_value = actual
        assert not _plan(runtime).can_apply


def test_real_other_process_owner_blocks_apply(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path, running=False)
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    process = context.Process(target=_hold_owner, args=(str(runtime), ready, release))
    process.start()
    try:
        assert ready.wait(10)
        jobs = read_queue(runtime, strict=True)
        jobs[0].update(status="FULL_RUNNING", phase="FULL_RUNNING", started_at="2026-01-01T00:00:00")
        save_queue(jobs, runtime_dir=runtime)
        write_json(runtime / "live_status.json", {"phase": "FULL_RUNNING", "queue_id": row["queue_id"],
                                                  "started_at": jobs[0]["started_at"], "return_code": 0})
        plan = _plan(runtime)
        assert plan.assessment["owner"]["state"] == "ACTIVE"
        assert not plan.can_apply
    finally:
        release.set()
        process.join(15)
    assert process.exitcode == 0


def test_imported_historical_running_without_live_exit_is_not_repaired(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path, live_exit=False)
    plan = _plan(runtime)
    assert not plan.can_apply and plan.assessment["status"] == "STALE_RUNNING"


def test_approval_rejection_binding_and_single_use(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path)
    plan = _plan(runtime)
    with patch("tkinter.messagebox.askyesno", return_value=False):
        assert approve_local_plan(plan, Mock(winfo_exists=lambda: True)) is None
    assert apply_approved_recovery(plan, "not-a-token", process_probe=CLEAR)["status"] == "REJECTED"
    token = _approve(plan)
    (tmp_path / "other").mkdir()
    other, _, _, _ = _fixture(tmp_path / "other")
    other_plan = _plan(other)
    assert apply_approved_recovery(other_plan, token, process_probe=CLEAR)["status"] == "REJECTED"
    assert apply_approved_recovery(plan, token, process_probe=CLEAR)["status"] == "REJECTED"


def test_changed_queue_or_probe_invalidates_approved_plan(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path)
    plan = _plan(runtime)
    token = _approve(plan)
    jobs = read_queue(runtime, strict=True)
    jobs[0]["notes"] = "changed"
    save_queue(jobs, runtime_dir=runtime)
    assert apply_approved_recovery(plan, token, process_probe=CLEAR)["status"] == "STALE_PLAN"
    plan = _plan(runtime)
    token = _approve(plan)
    assert apply_approved_recovery(plan, token, process_probe=UNKNOWN)["status"] == "STALE_PLAN"
    assert read_queue(runtime)[0]["status"] == "FULL_RUNNING"


def test_approved_apply_is_metadata_only_audited_and_idempotent(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path)
    original = inp.read_bytes()
    plan = _plan(runtime)
    token = _approve(plan)
    result = apply_approved_recovery(plan, token, process_probe=CLEAR)
    assert result["status"] == "APPLIED"
    assert read_queue(runtime)[0]["status"] == INTERRUPTED
    assert json.loads((runtime / "live_status.json").read_text(encoding="utf-8"))["phase"] == "IDLE"
    audit = json.loads(Path(result["audit_path"]).read_text(encoding="utf-8"))
    assert audit["approval_source"] == "local_gui_confirmation"
    assert audit["affected_queue_ids"] == [row["queue_id"]]
    assert audit["outcome"] == "APPLIED"
    assert inp.read_bytes() == original
    assert apply_approved_recovery(plan, token, process_probe=CLEAR)["status"] == "REJECTED"
    assert not _plan(runtime).can_apply


def test_partial_live_write_can_be_replanned_without_second_queue_change(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path)
    plan = _plan(runtime)
    import abqjobpilot.recovery_workflow as workflow
    original_write = workflow.write_json

    def fail_live(path, data):
        if Path(path).name == "live_status.json":
            raise OSError("fixture write failure")
        original_write(path, data)

    with patch.object(workflow, "write_json", side_effect=fail_live):
        result = apply_approved_recovery(plan, _approve(plan), process_probe=CLEAR)
    assert result["status"] == "PARTIAL_OR_FAILED"
    assert read_queue(runtime)[0]["status"] == INTERRUPTED
    assert _plan(runtime).can_apply
    assert apply_approved_recovery(_plan(runtime), _approve(_plan(runtime)), process_probe=CLEAR)["status"] == "APPLIED"


def test_existing_project_history_is_narrow_and_preserves_terminal_evidence(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path, project=True)
    repo = ProjectHistoryRepository(runtime.parent)
    repo.sync_records([row])
    plan = _plan(runtime, db)
    assert plan.can_apply
    assert apply_approved_recovery(plan, _approve(plan), process_probe=CLEAR)["status"] == "APPLIED"
    job = repo.find_job_by_queue_id(row["queue_id"])
    runs = repo.list_runs(job["job_id"])
    assert len(runs) == 1 and runs[0]["queue_id"] == row["queue_id"]
    assert runs[0]["status"] == "UNKNOWN"
    assert not _plan(runtime, db).can_apply
    assert len(repo.list_runs(job["job_id"])) == 1


def test_terminal_sqlite_disagreement_blocks_weaker_recovery(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path, project=True)
    repo = ProjectHistoryRepository(runtime.parent)
    completed = {**row, "status": "COMPLETED_OK", "phase": "COMPLETED_OK"}
    repo.sync_records([completed], provenance="legacy_import")
    job = repo.find_job_by_queue_id(row["queue_id"])
    before = repo.list_runs(job["job_id"])
    plan = _plan(runtime, db)
    assert plan.assessment["history_disagreements"]
    assert not plan.can_apply
    assert repo.list_runs(job["job_id"]) == before


def test_failed_sqlite_projection_has_approved_history_only_retry(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path, project=True)
    repo = ProjectHistoryRepository(runtime.parent)
    repo.sync_records([row])
    plan = _plan(runtime, db)
    with patch.object(ProjectHistoryRepository, "sync_records", side_effect=OSError("fixture DB failure")):
        partial = apply_approved_recovery(plan, _approve(plan), process_probe=CLEAR)
    assert partial["status"] == "PARTIAL_OR_FAILED"
    assert read_queue(runtime)[0]["status"] == INTERRUPTED
    assert json.loads((runtime / "live_status.json").read_text(encoding="utf-8"))["phase"] == "IDLE"
    retry = _plan(runtime, db)
    assert retry.can_apply
    assert [(item["target"], item["to"]) for item in retry.transitions] == [("history", "UNKNOWN")]
    assert apply_approved_recovery(retry, _approve(retry), process_probe=CLEAR)["status"] == "APPLIED"
    job = repo.find_job_by_queue_id(row["queue_id"])
    runs = repo.list_runs(job["job_id"])
    assert len(runs) == 1 and runs[0]["status"] == "UNKNOWN"


def test_readonly_plan_never_initializes_missing_project_database(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path, project=True)
    assert not db.exists()
    _plan(runtime, db)
    assert not db.exists()


def test_recovery_refuses_database_schema_migration(tmp_path):
    runtime, db, row, inp = _fixture(tmp_path, project=True)
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO schema_meta VALUES('schema_version', '0')")
    before = db.read_bytes()
    plan = _plan(runtime, db)
    assert not plan.can_apply
    assert any("database" in item.lower() for item in plan.unresolved)
    assert db.read_bytes() == before


def test_gui_recovery_entry_and_readonly_dialog(tmp_path):
    from abqjobpilot import config
    from abqjobpilot.gui_app import AbqJobPilotApp
    from abqjobpilot.recovery_dialog import RecoveryDialog

    runtime, db, row, inp = _fixture(tmp_path, running=False)
    with patch.object(config, "RUNTIME_DIR_PATH", runtime), \
         patch.object(config, "RUNTIME_DIR", str(runtime)), \
         patch.object(config, "QUEUE_FILE", str(runtime / "queue.json")), \
         patch.object(config, "LIVE_STATUS_FILE", str(runtime / "live_status.json")), \
         patch.object(config, "SETTINGS_FILE", str(runtime / "settings.json")), \
         patch.object(AbqJobPilotApp, "_read_gpu_text", return_value="--"):
        try:
            app = AbqJobPilotApp()
        except tk.TclError as exc:
            pytest.skip(f"Tk display unavailable: {exc}")
        try:
            with patch("abqjobpilot.recovery_dialog.build_recovery_plan", return_value=_plan(runtime)):
                app.open_runtime_recovery()
                dialogs = [child for child in app.winfo_children() if isinstance(child, RecoveryDialog)]
                assert len(dialogs) == 1
                assert str(dialogs[0].apply_button.cget("state")) == "disabled"
                dialogs[0].destroy()
        finally:
            app.destroy()


def test_gui_apply_requires_tk_confirmation_and_uses_reviewed_plan(tmp_path):
    from abqjobpilot import config
    from abqjobpilot.gui_app import AbqJobPilotApp
    from abqjobpilot.recovery_dialog import RecoveryDialog

    runtime, db, row, inp = _fixture(tmp_path)
    plan = _plan(runtime)
    with patch.object(config, "RUNTIME_DIR_PATH", runtime), \
         patch.object(config, "RUNTIME_DIR", str(runtime)), \
         patch.object(config, "QUEUE_FILE", str(runtime / "queue.json")), \
         patch.object(config, "LIVE_STATUS_FILE", str(runtime / "live_status.json")), \
         patch.object(config, "SETTINGS_FILE", str(runtime / "settings.json")), \
         patch.object(AbqJobPilotApp, "_read_gpu_text", return_value="--"):
        try:
            app = AbqJobPilotApp()
        except tk.TclError as exc:
            pytest.skip(f"Tk display unavailable: {exc}")
        try:
            with patch("abqjobpilot.recovery_dialog.build_recovery_plan", return_value=plan), \
                 patch("tkinter.messagebox.askyesno", return_value=True) as confirm, \
                 patch("abqjobpilot.recovery_dialog.apply_approved_recovery",
                       return_value={"status": "APPLIED"}) as apply, \
                 patch("abqjobpilot.recovery_dialog.messagebox.showinfo"):
                app.open_runtime_recovery()
                dialog = next(child for child in app.winfo_children() if isinstance(child, RecoveryDialog))
                assert str(dialog.apply_button.cget("state")) == "normal"
                dialog.apply()
                assert row["queue_id"] in confirm.call_args.args[1]
                assert apply.call_args.args[0] is plan
                assert read_queue(runtime)[0]["status"] == "FULL_RUNNING"  # mocked apply never writes
                dialog.destroy()
        finally:
            app.destroy()
