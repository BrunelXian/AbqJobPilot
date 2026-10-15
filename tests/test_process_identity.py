"""Run 005 process and recovery evidence, using Python fixture processes only."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from abqjobpilot import config
from abqjobpilot.process_identity import (capture_identity, inspect_pid, new_launch_evidence,
                                          refresh_launch_evidence, verify_identity, verify_launch_evidence)
from abqjobpilot.queue_store import build_queue_record, enqueue_record, read_queue, save_queue
from abqjobpilot.recovery_workflow import apply_approved_recovery, approve_local_plan, build_recovery_plan
from abqjobpilot.runner_core import _run_command
from abqjobpilot.utils import write_json


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows process identity tests")
CLEAR = lambda: {"state": "CLEAR", "matches": []}
EXITED = lambda _: {"state": "CONFIRMED_EXITED", "reason": "fixture exit"}


def _python_process(seconds: float):
    return subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({seconds})"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _recovery_fixture(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    work = tmp_path / "engineering"
    work.mkdir()
    inp = work / "job.inp"
    inp.write_text("*Heading\n", encoding="utf-8")
    row = build_queue_record(inp, 2, 0, None, None, None, True, True, "")
    row.update(status="FULL_RUNNING", phase="FULL_RUNNING", started_at="2026-01-01T00:00:00")
    save_queue([row], runtime_dir=runtime)
    write_json(runtime / "live_status.json", {
        "phase": "FULL_RUNNING", "queue_id": row["queue_id"], "started_at": row["started_at"],
        "return_code": 0, "process_identity": {"runtime_dir": str(runtime.resolve()),
                                               "queue_id": row["queue_id"], "phase": "FULL_RUNNING"},
    })
    return runtime, work, inp, row


def test_real_windows_pid_creation_time_and_executable(tmp_path):
    process = _python_process(0.8)
    try:
        identity = capture_identity(process.pid)
        assert identity["identity_status"] == "CONFIRMED"
        assert identity["creation_time_100ns"] > 0
        assert identity["executable_path"].lower().endswith("python.exe")
        assert verify_identity(identity)["state"] == "CONFIRMED_ACTIVE"
        process.wait(timeout=5)
        assert verify_identity(identity)["state"] == "CONFIRMED_EXITED"
    finally:
        process.wait(timeout=5)


def test_pid_reuse_unknown_pid_race_and_query_failure():
    record = {"pid": 1234, "creation_time_100ns": 100, "executable_path": r"C:\Python\python.exe",
              "identity_status": "CONFIRMED"}
    with patch("abqjobpilot.process_identity.inspect_pid", return_value={
            "state": "ACTIVE", "pid": 1234, "creation_time_100ns": 101,
            "executable_path": record["executable_path"]}):
        assert verify_identity(record)["state"] == "IDENTITY_MISMATCH"
    with patch("abqjobpilot.process_identity.inspect_pid", return_value={"state": "EXITED"}):
        assert verify_identity(record)["state"] == "CONFIRMED_EXITED"
    with patch("abqjobpilot.process_identity.inspect_pid", return_value={
            "state": "UNCONFIRMED", "reason": "access denied"}):
        assert verify_identity(record)["state"] == "UNCONFIRMED"
    assert inspect_pid(0)["state"] == "UNCONFIRMED"
    assert verify_identity({"pid": 1234})["state"] == "UNCONFIRMED"


def test_real_launcher_exits_while_python_child_remains_active(tmp_path):
    code = ("import subprocess,sys,time; "
            "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(3)'],"
            "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
            "print(child.pid,flush=True);time.sleep(1.2)")
    parent = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                              text=True, stderr=subprocess.DEVNULL)
    try:
        child_pid = int(parent.stdout.readline().strip())
        evidence = new_launch_evidence(runtime_dir=str(tmp_path), queue_id="q_fixture",
                                       phase="FULL_RUNNING", pid=parent.pid,
                                       command=[sys.executable, "fixture"],
                                       working_dir=str(tmp_path), job_name="fixture")
        deadline = time.monotonic() + 1
        while not evidence["observed_children"] and time.monotonic() < deadline:
            refresh_launch_evidence(evidence)
            time.sleep(0.02)
        assert any(item["pid"] == child_pid for item in evidence["observed_children"])
        parent.wait(timeout=5)
        evidence["launcher_exit_observed"] = True
        observed = verify_launch_evidence(evidence)
        assert observed["launcher"]["state"] == "CONFIRMED_EXITED"
        assert observed["state"] == "POSSIBLE_ORPHAN"
        # Even after the child exits, an unrecognized Python descendant is not
        # promoted to a confirmed Abaqus solver-exit verdict.
        deadline = time.monotonic() + 5
        while inspect_pid(child_pid)["state"] == "ACTIVE" and time.monotonic() < deadline:
            time.sleep(0.05)
        assert verify_launch_evidence(evidence)["state"] == "UNCONFIRMED"
    finally:
        parent.wait(timeout=5)


def test_launcher_exit_without_child_identity_remains_unconfirmed(tmp_path):
    process = _python_process(0.5)
    evidence = new_launch_evidence(runtime_dir=str(tmp_path), queue_id="q_fixture",
                                   phase="FULL_RUNNING", pid=process.pid,
                                   command=[sys.executable, "fixture"],
                                   working_dir=str(tmp_path), job_name="fixture")
    process.wait(timeout=5)
    evidence["launcher_exit_observed"] = True
    evidence["child_scan_status"] = "OK"
    assert verify_launch_evidence(evidence)["state"] == "UNCONFIRMED"
    assert verify_launch_evidence({"bad": "record"})["state"] == "UNCONFIRMED"


def test_mocked_solver_candidate_active_and_exited_classifications(tmp_path):
    launcher = {"pid": 1, "creation_time_100ns": 100, "executable_path": "cmd.exe",
                "identity_status": "CONFIRMED"}
    child = {"pid": 2, "creation_time_100ns": 101, "executable_path": "standard.exe",
             "identity_status": "CONFIRMED", "role": "solver_candidate"}
    evidence = {"runtime_dir": str(tmp_path), "queue_id": "q", "launcher": launcher,
                "observed_children": [child], "launcher_exit_observed": True,
                "child_scan_status": "OK"}
    def states(record):
        return {"state": "CONFIRMED_EXITED" if record["pid"] == 1 else "CONFIRMED_ACTIVE"}
    with patch("abqjobpilot.process_identity.verify_identity", side_effect=states):
        assert verify_launch_evidence(evidence)["state"] == "CONFIRMED_ACTIVE"
    with patch("abqjobpilot.process_identity.verify_identity", return_value={"state": "CONFIRMED_EXITED"}):
        assert verify_launch_evidence(evidence)["state"] == "CONFIRMED_EXITED"


def test_runner_helper_persists_launcher_identity_without_changing_command(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    inp = work / "fixture.inp"
    inp.write_text("*Heading\n", encoding="utf-8")
    job = build_queue_record(inp, 2, 0, None, None, None, True, True, "")
    job["started_at"] = "2026-01-01T00:00:00"
    command = [sys.executable, "-c", "import time;time.sleep(0.3)"]
    with patch.object(config, "RUNTIME_DIR", str(runtime)), \
         patch.object(config, "LIVE_STATUS_FILE", str(runtime / "live_status.json")), \
         patch.object(config, "POLL_INTERVAL_SECONDS", 0.02):
        assert _run_command(job, "FULL_RUNNING", command) == 0
    live = json.loads((runtime / "live_status.json").read_text(encoding="utf-8"))
    evidence = live["process_identity"]
    assert live["return_code"] == 0
    assert evidence["queue_id"] == job["queue_id"]
    assert evidence["launcher"]["identity_status"] == "CONFIRMED"
    assert evidence["launcher_exit_observed"] is True
    assert len(evidence["command_sha256"]) == 64
    assert "command" not in evidence
    assert command == [sys.executable, "-c", "import time;time.sleep(0.3)"]


@pytest.mark.parametrize("state", ["CONFIRMED_ACTIVE", "POSSIBLE_ORPHAN", "IDENTITY_MISMATCH", "UNCONFIRMED"])
def test_recovery_blocks_nonexited_identity_states(tmp_path, state):
    runtime, work, inp, row = _recovery_fixture(tmp_path)
    before = hashlib.sha256((runtime / "queue.json").read_bytes()).hexdigest()
    plan = build_recovery_plan(runtime, process_probe=CLEAR,
                               identity_probe=lambda _: {"state": state, "reason": "fixture"})
    assert not plan.can_apply
    assert any("exit" in reason.lower() or "lineage" in reason.lower() for reason in plan.unresolved)
    assert before == hashlib.sha256((runtime / "queue.json").read_bytes()).hexdigest()
    assert read_queue(runtime)[0]["status"] == "FULL_RUNNING"


def test_recovery_requires_matching_runtime_queue_and_phase(tmp_path):
    runtime, work, inp, row = _recovery_fixture(tmp_path)
    live_path = runtime / "live_status.json"
    live = json.loads(live_path.read_text(encoding="utf-8"))
    live["process_identity"]["runtime_dir"] = str(tmp_path / "other")
    write_json(live_path, live)
    plan = build_recovery_plan(runtime, process_probe=CLEAR, identity_probe=EXITED)
    assert not plan.can_apply


def test_odb_timestamp_is_observation_and_terminal_report_blocks(tmp_path):
    runtime, work, inp, row = _recovery_fixture(tmp_path)
    odb = work / "job.odb"
    odb.write_bytes(b"old fixture artifact")
    plan = build_recovery_plan(runtime, process_probe=CLEAR, identity_probe=EXITED)
    observed = next(item for item in plan.assessment["artifact_observations"]
                    if item["queue_id"] == row["queue_id"])
    assert observed["odb_exists"] and observed["odb_mtime_ns"] is not None
    assert all(item["to"] != "COMPLETED" for item in plan.transitions)
    reports = runtime / "reports"
    reports.mkdir()
    write_json(reports / f"{row['queue_id']}_job.json", {"queue_id": row["queue_id"],
                                                   "status": "COMPLETED_OK"})
    blocked = build_recovery_plan(runtime, process_probe=CLEAR, identity_probe=EXITED)
    assert blocked.assessment["report_terminal_evidence"]
    assert not blocked.can_apply


def test_process_state_change_after_approval_invalidates_plan(tmp_path):
    runtime, work, inp, row = _recovery_fixture(tmp_path)
    plan = build_recovery_plan(runtime, process_probe=CLEAR, identity_probe=EXITED)
    assert plan.can_apply
    with patch("tkinter.messagebox.askyesno", return_value=True):
        token = approve_local_plan(plan, Mock(winfo_exists=lambda: True))
    result = apply_approved_recovery(plan, token, process_probe=CLEAR,
                                     identity_probe=lambda _: {"state": "POSSIBLE_ORPHAN", "reason": "new child"})
    assert result["status"] == "STALE_PLAN"
    assert read_queue(runtime)[0]["status"] == "FULL_RUNNING"
    assert not (runtime / "recovery_audit").exists()


def test_approved_exit_still_only_marks_unknown_interrupted(tmp_path):
    runtime, work, inp, row = _recovery_fixture(tmp_path)
    plan = build_recovery_plan(runtime, process_probe=CLEAR, identity_probe=EXITED)
    with patch("tkinter.messagebox.askyesno", return_value=True):
        token = approve_local_plan(plan, Mock(winfo_exists=lambda: True))
    result = apply_approved_recovery(plan, token, process_probe=CLEAR, identity_probe=EXITED)
    assert result["status"] == "APPLIED"
    assert read_queue(runtime)[0]["status"] == "UNKNOWN_INTERRUPTED"
    assert inp.is_file()


def test_interrupted_output_identity_and_lock_block_reenqueue(tmp_path):
    runtime, work, inp, row = _recovery_fixture(tmp_path)
    row["status"] = "UNKNOWN_INTERRUPTED"
    save_queue([row], runtime_dir=runtime)
    write_json(runtime / "live_status.json", {"phase": "IDLE"})
    blocked = enqueue_record(str(inp), runtime_dir=runtime)
    assert blocked["code"] == "OUTPUT_CONFLICT_UNCONFIRMED"
    other = work / "other.inp"
    other.write_text("*Heading\n", encoding="utf-8")
    assert enqueue_record(str(other), runtime_dir=runtime)["ok"]
    (work / "locked.inp").write_text("*Heading\n", encoding="utf-8")
    (work / "locked.lck").write_text("fixture lock", encoding="utf-8")
    assert enqueue_record(str(work / "locked.inp"), runtime_dir=runtime)["code"] == "OUTPUT_CONFLICT_UNCONFIRMED"
    assert len(read_queue(runtime)) == 2


def test_live_process_identity_collision_and_runtime_isolation(tmp_path):
    runtime, work, inp, row = _recovery_fixture(tmp_path)
    save_queue([], runtime_dir=runtime)
    live = {"phase": "IDLE", "process_identity": {"runtime_dir": str(runtime),
            "queue_id": row["queue_id"], "phase": "FULL_RUNNING",
            "working_dir": str(work), "job_name": "job"}}
    write_json(runtime / "live_status.json", live)
    with patch("abqjobpilot.runtime_coordination.verify_launch_evidence",
               return_value={"state": "POSSIBLE_ORPHAN"}):
        assert enqueue_record(str(inp), runtime_dir=runtime)["code"] == "OUTPUT_CONFLICT_UNCONFIRMED"
        other = tmp_path / "other_runtime"
        other.mkdir()
        assert enqueue_record(str(inp), runtime_dir=other)["ok"]


def test_audit_preparation_failure_leaves_queue_untouched(tmp_path):
    runtime, work, inp, row = _recovery_fixture(tmp_path)
    plan = build_recovery_plan(runtime, process_probe=CLEAR, identity_probe=EXITED)
    with patch("tkinter.messagebox.askyesno", return_value=True):
        token = approve_local_plan(plan, Mock(winfo_exists=lambda: True))
    from abqjobpilot import recovery_workflow
    original_write = recovery_workflow.write_json
    def fail_audit(path, payload):
        if "recovery_audit" in str(path):
            raise OSError("fixture audit write failure")
        original_write(path, payload)
    with patch.object(recovery_workflow, "write_json", side_effect=fail_audit):
        result = apply_approved_recovery(plan, token, process_probe=CLEAR, identity_probe=EXITED)
    assert result["status"] == "REJECTED"
    assert read_queue(runtime)[0]["status"] == "FULL_RUNNING"
