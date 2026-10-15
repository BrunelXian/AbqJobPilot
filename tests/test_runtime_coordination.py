"""Run 003: real process overlap, ownership, and read-only recovery fixtures."""

import hashlib
import json
import multiprocessing
import sqlite3
import time
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from abqjobpilot.queue_store import (enqueue_record, move_queued_job, read_queue,
                                     remove_queued_jobs)
from abqjobpilot.recovery_assessment import assess_runtime
from abqjobpilot.project import ProjectManager, export_project_archive
from abqjobpilot.runtime_coordination import (CoordinationError, RunnerOwnership,
                                              queue_transaction, runner_ownership_state)
from abqjobpilot.utils import write_json


def _enqueue_worker(runtime, paths, event, results):
    event.wait(10)
    results.put([enqueue_record(str(path), runtime_dir=runtime) for path in paths])


def _hold_queue_lock(runtime, ready, release):
    with queue_transaction(runtime):
        ready.set()
        release.wait(10)


def _hold_runner(runtime, ready, release, start=None):
    if start is not None:
        start.wait(10)
    owner = RunnerOwnership(runtime)
    owner.acquire()
    ready.set()
    release.wait(10)
    owner.release()


def _gui_mutation_worker(runtime, action, queue_ids, start, results):
    from abqjobpilot import config
    from abqjobpilot.queue_store import move_queued_job, remove_queued_jobs
    config.use_runtime_dir(runtime)
    start.wait(10)
    if action == "reorder":
        results.put(move_queued_job(queue_ids[1], "top"))
    else:
        results.put(remove_queued_jobs([queue_ids[0]]))


def _fixture(tmp_path, count=4):
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True)
    paths = []
    for number in range(count):
        path = tmp_path / f"model_{number}.inp"
        path.write_text("*Heading\n", encoding="utf-8")
        paths.append(path)
    return runtime, paths


@pytest.mark.parametrize("processes,per_process", [(2, 1), (4, 8)])
def test_independent_enqueue_processes_do_not_lose_updates(tmp_path, processes, per_process):
    runtime, paths = _fixture(tmp_path, processes * per_process)
    ctx = multiprocessing.get_context("spawn")
    start = ctx.Event()
    results = ctx.Queue()
    workers = [ctx.Process(target=_enqueue_worker,
                           args=(str(runtime), paths[i * per_process:(i + 1) * per_process], start, results))
               for i in range(processes)]
    for worker in workers:
        worker.start()
    start.set()
    responses = [item for _ in workers for item in results.get(timeout=20)]
    for worker in workers:
        worker.join(20)
        assert worker.exitcode == 0
    assert all(item["ok"] for item in responses), responses
    queue = read_queue(runtime, strict=True)
    assert len(queue) == processes * per_process
    assert len({item["queue_id"] for item in queue}) == len(queue)


def test_lock_timeout_other_runtime_and_terminated_writer(tmp_path):
    runtime, paths = _fixture(tmp_path)
    other, _ = _fixture(tmp_path / "other")
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    holder = ctx.Process(target=_hold_queue_lock, args=(str(runtime), ready, release))
    holder.start()
    try:
        assert ready.wait(10)
        with pytest.raises(CoordinationError, match="timed out") as exc:
            with queue_transaction(runtime, timeout=0.05):
                pass
        assert exc.value.code == "QUEUE_LOCK_TIMEOUT"
        assert enqueue_record(str(paths[0]), runtime_dir=other)["ok"]
        assert read_queue(runtime) == []
        holder.terminate()  # fixture-only process, never a solver or QueueRunner
        holder.join(10)
        with queue_transaction(runtime, timeout=1):
            assert enqueue_record(str(paths[0]), runtime_dir=runtime)["ok"]
    finally:
        if holder.is_alive():
            release.set()
            holder.join(10)


def test_atomic_replace_failure_keeps_old_queue(tmp_path):
    runtime, paths = _fixture(tmp_path)
    assert enqueue_record(str(paths[0]), runtime_dir=runtime)["ok"]
    before = (runtime / "queue.json").read_bytes()
    with patch("abqjobpilot.utils.os.replace", side_effect=OSError("fixture replace failure")):
        result = enqueue_record(str(paths[1]), runtime_dir=runtime)
    assert not result["ok"]
    assert (runtime / "queue.json").read_bytes() == before
    assert len(read_queue(runtime, strict=True)) == 1


def test_gui_compatible_reorder_and_remove_preserve_current_queue(tmp_path, monkeypatch):
    runtime, paths = _fixture(tmp_path, 3)
    from abqjobpilot import config
    monkeypatch.setattr(config, "RUNTIME_DIR", str(runtime))
    monkeypatch.setattr(config, "QUEUE_FILE", str(runtime / "queue.json"))
    monkeypatch.setattr(config, "LIVE_STATUS_FILE", str(runtime / "live_status.json"))
    rows = [enqueue_record(str(path), runtime_dir=runtime) for path in paths]
    assert all(row["ok"] for row in rows)
    assert move_queued_job(rows[2]["queue_id"], "top")["ok"]
    assert [job["queue_id"] for job in read_queue(runtime)] == [
        rows[2]["queue_id"], rows[0]["queue_id"], rows[1]["queue_id"]]
    assert remove_queued_jobs([rows[0]["queue_id"]])["ok"]
    assert {job["queue_id"] for job in read_queue(runtime)} == {
        rows[1]["queue_id"], rows[2]["queue_id"]}


@pytest.mark.parametrize("action", ["reorder", "remove"])
def test_independent_gui_mutation_and_enqueue_do_not_lose_updates(tmp_path, action):
    runtime, paths = _fixture(tmp_path, 3)
    first = enqueue_record(str(paths[0]), runtime_dir=runtime)
    second = enqueue_record(str(paths[1]), runtime_dir=runtime)
    assert first["ok"] and second["ok"]
    ctx = multiprocessing.get_context("spawn")
    start, results = ctx.Event(), ctx.Queue()
    gui = ctx.Process(target=_gui_mutation_worker,
                      args=(str(runtime), action, [first["queue_id"], second["queue_id"]], start, results))
    enqueue = ctx.Process(target=_enqueue_worker, args=(str(runtime), [paths[2]], start, results))
    gui.start()
    enqueue.start()
    start.set()
    a, b = results.get(timeout=20), results.get(timeout=20)
    gui.join(20)
    enqueue.join(20)
    assert gui.exitcode == enqueue.exitcode == 0
    assert all(item["ok"] for item in (a, b) if isinstance(item, dict))
    assert all(item["ok"] for batch in (a, b) if isinstance(batch, list) for item in batch)
    queue_ids = {job["queue_id"] for job in read_queue(runtime, strict=True)}
    if action == "remove":
        assert first["queue_id"] not in queue_ids
    else:
        assert first["queue_id"] in queue_ids
    assert second["queue_id"] in queue_ids
    assert len(queue_ids) == (2 if action == "remove" else 3)


def test_runner_ownership_is_cross_process_and_stale_metadata_is_not_owner(tmp_path):
    runtime, paths = _fixture(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    holder = ctx.Process(target=_hold_runner, args=(str(runtime), ready, release))
    holder.start()
    try:
        assert ready.wait(10)
        assert runner_ownership_state(runtime)["state"] == "ACTIVE"
        with pytest.raises(CoordinationError) as exc:
            RunnerOwnership(runtime).acquire()
        assert exc.value.code == "RUNNER_OWNERSHIP_CONFLICT"
        rejected = enqueue_record(str(paths[0]), runtime_dir=runtime)
        assert rejected["code"] == "RUNNER_ACTIVE"
        assert read_queue(runtime) == []
    finally:
        release.set()
        holder.join(10)
    assert holder.exitcode == 0
    assert runner_ownership_state(runtime)["state"] == "ABSENT"
    (runtime / "runner_owner.json").write_text('{"pid": 99999}', encoding="utf-8")
    assert runner_ownership_state(runtime)["state"] == "STALE"
    owner = RunnerOwnership(runtime)
    owner.acquire()
    assert owner.verify()
    owner.release()


def test_ambiguous_locked_ownership_fails_closed(tmp_path):
    runtime, paths = _fixture(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    holder = ctx.Process(target=_hold_runner, args=(str(runtime), ready, release))
    holder.start()
    try:
        assert ready.wait(10)
        (runtime / "runner_owner.json").write_text("{bad", encoding="utf-8")
        assert runner_ownership_state(runtime)["state"] == "UNCONFIRMED"
        result = enqueue_record(str(paths[0]), runtime_dir=runtime)
        assert result["code"] == "RUNNER_OWNERSHIP_UNCONFIRMED"
    finally:
        release.set()
        holder.join(10)
    assert holder.exitcode == 0


def test_public_api_surfaces_runner_active_error_code(tmp_path):
    from abqjobpilot.api import AbqJobPilotClient, JobRequest
    runtime, paths = _fixture(tmp_path)
    owner = RunnerOwnership(runtime)
    owner.acquire()
    try:
        result = AbqJobPilotClient(runtime_dir=str(runtime)).enqueue(
            JobRequest(inp_path=str(paths[0]), submission_mode="enqueue_only"), dry_run=False).to_dict()
        assert result["job_id"] is None
        assert result["error_details"][0]["code"] == "RUNNER_ACTIVE"
        assert not (runtime / "queue.json").exists()
    finally:
        owner.release()


def test_orphaned_running_state_requires_read_only_recovery(tmp_path):
    runtime, paths = _fixture(tmp_path)
    write_json(runtime / "queue.json", {"jobs": [
        {"queue_id": "old", "status": "FULL_RUNNING", "job_name": "old"}]})
    before = (runtime / "queue.json").read_bytes()
    rejected = enqueue_record(str(paths[0]), runtime_dir=runtime)
    assert rejected["code"] == "RECOVERY_REQUIRED"
    with pytest.raises(CoordinationError) as exc:
        RunnerOwnership(runtime).acquire()
    assert exc.value.code == "RECOVERY_REQUIRED"
    assert (runtime / "queue.json").read_bytes() == before
    assert assess_runtime(runtime)["status"] == "STALE_RUNNING"


def test_separate_runtimes_have_independent_runner_ownership(tmp_path):
    a, _ = _fixture(tmp_path / "a")
    b, _ = _fixture(tmp_path / "b")
    first, second = RunnerOwnership(a), RunnerOwnership(b)
    try:
        first.acquire()
        second.acquire()
        assert first.verify() and second.verify()
    finally:
        second.release()
        first.release()


def test_runner_start_and_enqueue_share_admission_boundary(tmp_path):
    runtime, paths = _fixture(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    start, ready, release, results = ctx.Event(), ctx.Event(), ctx.Event(), ctx.Queue()
    # Both processes are released together. Either enqueue commits before the
    # owner is acquired, or it is rejected; it cannot commit after ownership.
    owner = ctx.Process(target=_hold_runner, args=(str(runtime), ready, release, start))
    writer = ctx.Process(target=_enqueue_worker, args=(str(runtime), [paths[0]], start, results))
    owner.start()
    writer.start()
    start.set()
    assert ready.wait(10)
    response = results.get(timeout=20)[0]
    try:
        assert response["ok"] or response["code"] == "RUNNER_ACTIVE"
        assert runner_ownership_state(runtime)["state"] == "ACTIVE"
        assert not enqueue_record(str(paths[1]), runtime_dir=runtime)["ok"]
    finally:
        release.set()
        owner.join(20)
        writer.join(20)
    assert owner.exitcode == writer.exitcode == 0


def test_runner_start_uses_ownership_without_solver(tmp_path, monkeypatch):
    from abqjobpilot import config
    from abqjobpilot.runner_core import QueueRunner
    runtime, _ = _fixture(tmp_path)
    monkeypatch.setattr(config, "RUNTIME_DIR", str(runtime))
    done = multiprocessing.get_context("spawn").Event()

    def fake_loop(self):
        done.wait(2)
        self._ownership.release()
        self._ownership = None

    monkeypatch.setattr(QueueRunner, "_run_loop", fake_loop)
    first, second = QueueRunner(), QueueRunner()
    assert first.start()["ok"]
    assert second.start()["code"] == "RUNNER_OWNERSHIP_CONFLICT"
    done.set()
    first._thread.join(5)
    assert second.start()["ok"]
    second._thread.join(5)


def test_recovery_assessment_is_read_only_and_does_not_infer_success(tmp_path):
    runtime, paths = _fixture(tmp_path)
    queue_file = runtime / "queue.json"
    live_file = runtime / "live_status.json"
    write_json(queue_file, {"jobs": []})
    write_json(live_file, {"phase": "IDLE"})
    assert assess_runtime(runtime)["status"] == "CLEAN"
    job = {"queue_id": "q1", "status": "FULL_RUNNING", "job_name": "model_0",
           "work_dir": str(tmp_path), "odb_path": str(tmp_path / "model_0.odb")}
    write_json(queue_file, {"jobs": [job]})
    write_json(live_file, {"phase": "FULL_RUNNING"})
    (tmp_path / "model_0.lck").write_text("stale", encoding="utf-8")
    (tmp_path / "model_0.odb").write_bytes(b"not validated")
    before = {path: hashlib.sha256(path.read_bytes()).digest() for path in
              (queue_file, live_file, tmp_path / "model_0.lck", tmp_path / "model_0.odb")}
    first = assess_runtime(runtime)
    second = assess_runtime(runtime)
    assert first == second
    assert first["status"] == "STALE_RUNNING"
    assert first["solver_process"] == "UNKNOWN"
    assert first["lock_files"] and first["odb_files"]
    assert before == {path: hashlib.sha256(path.read_bytes()).digest() for path in before}
    assert not (runtime / ".queue.lock").exists()


def test_recovery_reports_malformed_status_and_history_disagreement(tmp_path):
    runtime, _ = _fixture(tmp_path)
    write_json(runtime / "queue.json", {"jobs": [{"queue_id": "q1", "status": "FAILED_FATAL"}]})
    (runtime / "live_status.json").write_text("{bad", encoding="utf-8")
    assert assess_runtime(runtime)["status"] == "UNCONFIRMED"
    write_json(runtime / "live_status.json", {})
    assert assess_runtime(runtime)["status"] == "UNCONFIRMED"
    write_json(runtime / "live_status.json", {"phase": "IDLE"})
    db = tmp_path / "project.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE runs (queue_id TEXT, status TEXT, attempt_no INTEGER)")
        connection.execute("INSERT INTO runs VALUES ('q1', 'COMPLETED', 1)")
    result = assess_runtime(runtime, project_db=db)
    assert result["status"] == "RECOVERY_REQUIRED"
    assert result["history_disagreements"][0]["queue_id"] == "q1"


def test_recovery_reports_active_owner_and_missing_output_without_writes(tmp_path):
    runtime, paths = _fixture(tmp_path)
    write_json(runtime / "queue.json", {"jobs": []})
    owner = RunnerOwnership(runtime)
    owner.acquire()
    try:
        assert assess_runtime(runtime)["status"] == "ACTIVE_RUNNER"
    finally:
        owner.release()
    job = {"queue_id": "q1", "status": "COMPLETED_OK", "job_name": "model_0",
           "work_dir": str(tmp_path), "odb_path": str(tmp_path / "missing.odb")}
    write_json(runtime / "queue.json", {"jobs": [job]})
    assert assess_runtime(runtime)["status"] == "RECOVERY_REQUIRED"
    assert not paths[0].with_suffix(".odb").exists()


@pytest.mark.parametrize("mode", ["metadata", "full"])
def test_portable_archive_excludes_local_coordination_artifacts(tmp_path, mode):
    manager = ProjectManager(recent_file=tmp_path / "app" / "recent.json")
    project = manager.create_project(tmp_path / "study", "Study")
    with queue_transaction(project.runtime_dir):
        pass
    owner = RunnerOwnership(project.runtime_dir)
    owner.acquire()
    try:
        archive_path = tmp_path / f"{mode}.abqjobpilot-project.zip"
        export_project_archive(project.root, archive_path, mode=mode)
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
        assert "project/runtime/queue.json" in names
        assert "project/runtime/.queue.lock" not in names
        assert "project/runtime/.runner.lock" not in names
        assert "project/runtime/runner_owner.json" not in names
    finally:
        owner.release()
