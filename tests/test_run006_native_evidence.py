"""Native runner evidence and warning regression without launching Abaqus."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from abqjobpilot import config
from abqjobpilot.database import DatabaseFailure, ProjectHistoryRepository, sync_history_from_runtime
from abqjobpilot.gui_presentation import SUCCESS_TAG, status_presentation
from abqjobpilot.parsers import classify_datacheck_attempt, classify_final_verdict, parse_console_status
from abqjobpilot.process_identity import capture_identity, observe_descendants, verify_identity
from abqjobpilot.project import ProjectManager, export_project_archive, import_project_archive
from abqjobpilot.queue_store import build_queue_record, read_queue, save_queue
from abqjobpilot.run_evidence import read_process_evidence, save_phase_evidence
from abqjobpilot.runner_core import _write_report, run_next_job


class FakeProcess:
    def __init__(self, *args, **kwargs):
        self.pid = 31415
        self.returncode = None
        self.polls = 0

    def poll(self):
        self.polls += 1
        if self.polls < 3:
            return None
        self.returncode = 0
        return 0


@pytest.fixture
def fixture_project(tmp_path):
    project = ProjectManager(recent_file=tmp_path / "recent.json").create_project(
        tmp_path / "project", "Evidence fixture")
    work = tmp_path / "engineering"
    work.mkdir()
    inp = work / "fixture.inp"
    inp.write_text("*Heading\n", encoding="utf-8")
    row = build_queue_record(inp, 1, 0, "batch", "strategy", None, True, True, "")
    save_queue([row], runtime_dir=project.runtime_dir)
    return project, row, work


def _native_evidence(runtime_dir, queue_id, phase, pid, command, working_dir, job_name):
    return {"schema_version": "1.0", "runtime_dir": str(runtime_dir), "queue_id": queue_id,
            "phase": phase, "launcher": {"pid": pid, "creation_time_100ns": 100,
            "executable_path": "C:/Windows/System32/cmd.exe", "identity_status": "CONFIRMED"},
            "command_sha256": "a" * 64, "working_dir": working_dir, "job_name": job_name,
            "observed_children": [], "child_scan_status": "UNCONFIRMED",
            "launcher_exit_observed": False}


@pytest.mark.parametrize("failed", [False, True])
def test_two_phases_survive_terminal_status_and_reopen(fixture_project, failed):
    project, row, work = fixture_project
    def refresh(evidence):
        evidence["child_scan_status"] = "OK"
        evidence["observed_children"] = [{"pid": 400, "creation_time_100ns": 200,
            "executable_path": "C:/Abaqus/standard.exe", "identity_status": "CONFIRMED",
            "parent_pid": 31415, "observed_parent_creation_time_100ns": 100,
            "relationship_source": "windows_toolhelp32_snapshot", "relationship_status": "VERIFIED",
            "role": "solver_candidate"}]
        return evidence
    def read_text(path):
        suffix = Path(path).suffix.lower()
        if suffix == ".sta":
            return "THE ANALYSIS HAS COMPLETED SUCCESSFULLY"
        if suffix == ".msg":
            return ("Abaqus Error: failed analysis" if failed else
                    "0 WARNING MESSAGES DURING USER INPUT PROCESSING\n"
                    "0 WARNING MESSAGES DURING ANALYSIS\n0 ERROR MESSAGES")
        if suffix == ".log":
            return "Abaqus JOB fixture COMPLETED"
        return ""
    original_runtime = config.RUNTIME_DIR
    try:
        config.use_runtime_dir(project.runtime_dir)
        with patch("abqjobpilot.runner_core.subprocess.Popen", side_effect=FakeProcess) as popen, \
             patch("abqjobpilot.runner_core.new_launch_evidence", side_effect=_native_evidence), \
             patch("abqjobpilot.runner_core.refresh_launch_evidence", side_effect=refresh), \
             patch("abqjobpilot.runner_core.verify_identity", return_value={"state": "CONFIRMED_EXITED"}), \
             patch("abqjobpilot.runner_core._read_text", side_effect=read_text), \
             patch("abqjobpilot.runner_core.time.sleep"), \
             patch("abqjobpilot.runner_core.load_settings", return_value={"abaqus_cmd": "C:/fake.bat"}):
            result = run_next_job(row)
        assert popen.call_count == 2
        assert all(call.kwargs["cwd"] == str(work) for call in popen.call_args_list)
        queued = read_queue(project.runtime_dir)[0]
        expected = "FAILED_FATAL" if failed else "COMPLETED_OK"
        assert queued["status"] == expected
        assert queued["warning_count"] == 0
        assert status_presentation(queued["status"])[1] == ("failed" if failed else SUCCESS_TAG)
        assert result["job"]["status"] == expected
        reference = queued["process_evidence_path"]
        evidence = read_process_evidence(project.runtime_dir, reference)
        assert evidence["source"] == "native_runner"
        assert set(evidence["phases"]) == {"DATACHECK_RUNNING", "FULL_RUNNING"}
        for phase in evidence["phases"].values():
            assert phase["identity_strength"] == {
                "launcher": "VERIFIED", "lineage": "VERIFIED", "solver_candidate": "VERIFIED"}
            assert phase["process_identity"]["launcher"]["creation_time_100ns"] == 100
            assert phase["process_identity"]["observed_children"][0]["parent_pid"] == 31415
            assert phase["command_exit"]["return_code"] == 0
        report_files = [p for p in (project.runtime_dir / "reports").glob("*.json")
                        if p.name != "manifest.json"]
        assert len(report_files) == 1
        assert json.loads(report_files[0].read_text(encoding="utf-8"))["process_evidence_path"] == reference
        assert json.loads((project.runtime_dir / "live_status.json").read_text(encoding="utf-8"))[
            "process_evidence_path"] == reference
        assert (project.root / "project.db").is_file()
        assert sync_history_from_runtime(project.root)["created_runs"] == 0
        reopened = ProjectManager(recent_file=project.root.parent / "recent2.json").open_project(project.root)
        repository = ProjectHistoryRepository(reopened, read_only=True)
        job = repository.find_job_by_queue_id(row["queue_id"])
        run = repository.list_runs(job["job_id"])[0]
        assert run["status"] == ("FAILED" if failed else "COMPLETED")
        assert run["raw_status"] == expected
        assert repository.get_run_process_evidence(run["run_id"]) == evidence
    finally:
        config.use_runtime_dir(original_runtime)


def test_legacy_run_has_no_process_evidence(fixture_project):
    project, row, _ = fixture_project
    sync_history_from_runtime(project.root)
    repo = ProjectHistoryRepository(project, read_only=True)
    job = repo.find_job_by_queue_id(row["queue_id"])
    run = repo.list_runs(job["job_id"])[0]
    assert repo.get_run_process_evidence(run["run_id"]) is None


def test_native_evidence_archive_round_trip_and_old_format(fixture_project, tmp_path):
    project, row, _ = fixture_project
    evidence = _native_evidence(project.runtime_dir, row["queue_id"], "FULL_RUNNING", 91,
                                ["cmd.exe"], row["work_dir"], row["job_name"])
    reference = save_phase_evidence(project.runtime_dir, row["queue_id"], "FULL_RUNNING", evidence,
                                    return_code=0)
    row["process_evidence_path"] = reference
    save_queue([row], runtime_dir=project.runtime_dir)
    sync_history_from_runtime(project.root)
    archive = export_project_archive(project.root, tmp_path / "evidence.zip", mode="metadata")
    imported = import_project_archive(archive, tmp_path / "imported",
                                      recent_file=tmp_path / "import_recent.json")
    repo = ProjectHistoryRepository(imported, read_only=True)
    job = repo.find_job_by_queue_id(row["queue_id"])
    run = repo.list_runs(job["job_id"])[0]
    restored = repo.get_run_process_evidence(run["run_id"])
    assert restored["phases"]["FULL_RUNNING"]["process_identity"]["runtime_dir"] == str(imported.runtime_dir)
    assert restored["phases"]["FULL_RUNNING"]["command_exit"]["return_code"] == 0
    assert (tmp_path / "project" / "runtime" / reference).is_file()


def test_corrupt_evidence_cannot_be_silently_overwritten(fixture_project):
    project, row, _ = fixture_project
    evidence = _native_evidence(project.runtime_dir, row["queue_id"], "FULL_RUNNING", 91,
                                ["cmd.exe"], row["work_dir"], row["job_name"])
    reference = save_phase_evidence(project.runtime_dir, row["queue_id"], "FULL_RUNNING", evidence)
    path = project.runtime_dir / reference
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        save_phase_evidence(project.runtime_dir, row["queue_id"], "FULL_RUNNING", evidence)
    assert path.read_text(encoding="utf-8") == "{broken"


def test_project_history_projection_failure_is_visible_in_report(fixture_project):
    project, row, _ = fixture_project
    original_runtime = config.RUNTIME_DIR
    try:
        config.use_runtime_dir(project.runtime_dir)
        with patch("abqjobpilot.database.sync_history_from_runtime",
                   side_effect=DatabaseFailure("DATABASE_WRITE_FAILED", "fixture failure")):
            _write_report({**row, "status": "COMPLETED_OK"})
        reports = [path for path in (project.runtime_dir / "reports").glob("*.json")
                   if path.name != "manifest.json"]
        assert len(reports) == 1
        assert "fixture failure" in json.loads(reports[0].read_text(encoding="utf-8"))[
            "history_projection_error"]
        assert read_queue(project.runtime_dir)[0]["status"] == "QUEUED"
    finally:
        config.use_runtime_dir(original_runtime)


def test_transient_evidence_write_failure_remains_visible_at_terminal(fixture_project):
    project, row, _ = fixture_project
    original_runtime = config.RUNTIME_DIR
    writes = 0

    def save_with_initial_failure(*args, **kwargs):
        nonlocal writes
        writes += 1
        if writes == 1:
            raise OSError("fixture evidence write failed")
        return save_phase_evidence(*args, **kwargs)

    try:
        config.use_runtime_dir(project.runtime_dir)
        with patch("abqjobpilot.runner_core.subprocess.Popen", side_effect=FakeProcess), \
             patch("abqjobpilot.runner_core.new_launch_evidence", side_effect=_native_evidence), \
             patch("abqjobpilot.runner_core.refresh_launch_evidence", side_effect=lambda evidence: evidence), \
             patch("abqjobpilot.runner_core.verify_identity", return_value={"state": "CONFIRMED_EXITED"}), \
             patch("abqjobpilot.runner_core._read_text", side_effect=lambda path: (
                 "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" if Path(path).suffix == ".sta"
                 else "Abaqus JOB fixture COMPLETED" if Path(path).suffix == ".log" else "")), \
             patch("abqjobpilot.runner_core.time.sleep"), \
             patch("abqjobpilot.runner_core.load_settings", return_value={"abaqus_cmd": "C:/fake.bat"}), \
             patch("abqjobpilot.runner_core.save_phase_evidence", side_effect=save_with_initial_failure):
            run_next_job(row)
        queued = read_queue(project.runtime_dir)[0]
        assert queued["status"] == "COMPLETED_OK"
        assert "fixture evidence write failed" in queued["process_evidence_error"]
        assert read_process_evidence(project.runtime_dir, queued["process_evidence_path"])
        report = next(path for path in (project.runtime_dir / "reports").glob("*.json")
                      if path.name != "manifest.json")
        assert "fixture evidence write failed" in json.loads(report.read_text(encoding="utf-8"))[
            "process_evidence_error"]
    finally:
        config.use_runtime_dir(original_runtime)


def test_datacheck_failure_persists_phase_evidence(fixture_project):
    project, row, _ = fixture_project
    original_runtime = config.RUNTIME_DIR
    try:
        config.use_runtime_dir(project.runtime_dir)
        with patch("abqjobpilot.runner_core.subprocess.Popen", side_effect=FakeProcess) as popen, \
             patch("abqjobpilot.runner_core.new_launch_evidence", side_effect=_native_evidence), \
             patch("abqjobpilot.runner_core.refresh_launch_evidence", side_effect=lambda evidence: evidence), \
             patch("abqjobpilot.runner_core.verify_identity", return_value={"state": "UNCONFIRMED"}), \
             patch("abqjobpilot.runner_core._read_text", return_value="Abaqus Error: invalid input"), \
             patch("abqjobpilot.runner_core.time.sleep"), \
             patch("abqjobpilot.runner_core.load_settings", return_value={"abaqus_cmd": "C:/fake.bat"}):
            outcome = run_next_job(row)
        assert not outcome["ok"]
        assert popen.call_count == 1
        queued = read_queue(project.runtime_dir)[0]
        evidence = read_process_evidence(project.runtime_dir, queued["process_evidence_path"])
        assert set(evidence["phases"]) == {"DATACHECK_RUNNING"}
        assert evidence["phases"]["DATACHECK_RUNNING"]["identity_strength"]["solver_candidate"] == "UNKNOWN"
        assert evidence["phases"]["DATACHECK_RUNNING"]["command_exit"]["return_code"] == 0
        repo = ProjectHistoryRepository(project, read_only=True)
        job = repo.find_job_by_queue_id(row["queue_id"])
        run = repo.list_runs(job["job_id"])[0]
        assert repo.get_run_process_evidence(run["run_id"]) == evidence
    finally:
        config.use_runtime_dir(original_runtime)


def test_pid_reuse_and_query_failure_do_not_verify_lineage():
    launcher = {"pid": 10, "creation_time_100ns": 100, "executable_path": "cmd.exe",
                "identity_status": "CONFIRMED"}
    with patch("abqjobpilot.process_identity.inspect_pid", return_value={
            "state": "ACTIVE", "pid": 10, "creation_time_100ns": 101,
            "executable_path": "cmd.exe"}):
        assert verify_identity(launcher)["state"] == "IDENTITY_MISMATCH"
        assert observe_descendants(launcher)["state"] == "UNCONFIRMED"
    with patch("abqjobpilot.process_identity.inspect_pid", return_value={
            "state": "UNCONFIRMED", "reason": "access denied"}):
        assert verify_identity(launcher)["state"] == "UNCONFIRMED"
        assert observe_descendants(launcher)["state"] == "UNCONFIRMED"
    with patch("abqjobpilot.process_identity.inspect_pid", side_effect=OSError("query denied")):
        assert capture_identity(10)["identity_status"] == "UNCONFIRMED"
        assert verify_identity(launcher)["state"] == "UNCONFIRMED"


def test_warning_summary_zero_nonzero_and_deduplication():
    msg = ("0 WARNING MESSAGES DURING USER INPUT PROCESSING\n"
           "0 WARNING MESSAGES DURING ANALYSIS\n0 ERROR MESSAGES")
    success = classify_final_verdict(sta_text="THE ANALYSIS HAS COMPLETED SUCCESSFULLY",
                                     msg_text=msg, return_code=0)
    assert success == {"status": "COMPLETED_OK", "final_verdict": "SUCCESS",
                       "fatal_reason": "", "warning_count": 0}
    assert parse_console_status(msg)["warning_count"] == 0
    assert classify_datacheck_attempt("START DATACHECK_RUNNING\n" + msg)["warning_count"] == 0
    warning = "***WARNING: contact note"
    with_warnings = classify_final_verdict(
        sta_text="THE ANALYSIS HAS COMPLETED SUCCESSFULLY",
        msg_text="1 WARNING MESSAGES DURING ANALYSIS\n" + warning,
        log_text="START FULL_RUNNING\n" + warning + "\nEND FULL_RUNNING", return_code=0)
    assert with_warnings["status"] == "COMPLETED_WITH_WARNINGS"
    assert with_warnings["warning_count"] == 1
    repeated = classify_final_verdict(sta_text="THE ANALYSIS HAS COMPLETED SUCCESSFULLY",
                                      msg_text=warning + "\n" + warning, log_text=warning)
    assert repeated["warning_count"] == 2
    assert status_presentation(with_warnings["status"])[1] == SUCCESS_TAG
    assert classify_final_verdict(msg_text="Abaqus Error: failed\n" + msg)["status"] == "FAILED_FATAL"
    assert classify_datacheck_attempt("Abaqus JOB fixture COMPLETED\nAbaqus Error: failed", 0)[
        "status"] == "DATACHECK_FAILED"
    assert classify_datacheck_attempt("Abaqus JOB fixture COMPLETED", 8)["status"] == "DATACHECK_FAILED"
