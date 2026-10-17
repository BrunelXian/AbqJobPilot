"""Read-only observations for a runtime after a possible abnormal exit."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .runtime_coordination import runner_ownership_state, runtime_path
from .process_identity import verify_launch_evidence
from .status_codes import normalize_status


RUNNING_STATUSES = {"RUNNING", "DATACHECK_RUNNING", "FULL_RUNNING"}


def _json_file(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def assess_runtime(runtime_dir: str | Path, *, project_db: str | Path | None = None) -> dict:
    """Inspect state; never create a lock, repair a record, or infer solver success."""
    runtime = runtime_path(runtime_dir)
    errors: list[str] = []
    try:
        payload = _json_file(runtime / "queue.json")
        jobs = payload if isinstance(payload, list) else payload.get("jobs", []) if isinstance(payload, dict) else []
        if not isinstance(jobs, list) or any(not isinstance(job, dict) for job in jobs):
            raise ValueError("queue jobs must be a list of objects")
    except (OSError, ValueError) as exc:
        jobs = []
        errors.append(f"Invalid queue.json: {exc}")
    try:
        live = _json_file(runtime / "live_status.json")
        if live is not None and not isinstance(live, dict):
            raise ValueError("live status must be an object")
        if live is not None and not isinstance(live.get("phase"), str):
            raise ValueError("live status phase is missing")
    except (OSError, ValueError) as exc:
        live = None
        errors.append(f"Invalid live_status.json: {exc}")
    owner = runner_ownership_state(runtime)
    process_evidence = verify_launch_evidence(live.get("process_identity") if live else None)
    running = [str(job.get("queue_id")) for job in jobs if job.get("status") in RUNNING_STATUSES]
    lock_files = []
    odb_files = []
    missing_outputs = []
    artifact_observations = []
    for job in jobs:
        work = job.get("work_dir")
        name = job.get("job_name")
        if not work or not name:
            continue
        lock = Path(work) / f"{name}.lck"
        odb = Path(job.get("odb_path") or Path(work) / f"{name}.odb")
        observation = {"queue_id": job.get("queue_id"), "lck_path": str(lock), "odb_path": str(odb),
                       "lck_exists": False, "odb_exists": False, "odb_mtime_ns": None}
        if lock.is_file():
            lock_files.append(str(lock))
            observation["lck_exists"] = True
        if odb.is_file():
            odb_files.append(str(odb))
            observation["odb_exists"] = True
            try:
                observation["odb_mtime_ns"] = odb.stat().st_mtime_ns
            except OSError:
                pass
        elif job.get("status") in {"COMPLETED_OK", "COMPLETED_WITH_WARNINGS"}:
            missing_outputs.append(str(odb))
        artifact_observations.append(observation)
    reports = runtime / "reports"
    report_count = len(list(reports.glob("*.json"))) if reports.is_dir() else 0
    report_terminal_evidence = []
    if reports.is_dir():
        for path in reports.glob("*.json"):
            if not any(path.name.startswith(f"{queue_id}_") for queue_id in running):
                continue
            try:
                report = _json_file(path)
                if isinstance(report, dict) and report.get("queue_id") in running:
                    if normalize_status(report.get("status")) in {"COMPLETED", "FAILED", "CANCELLED"}:
                        report_terminal_evidence.append({"queue_id": report["queue_id"],
                                                         "status": report.get("status"), "path": str(path)})
            except (OSError, ValueError) as exc:
                errors.append(f"Matching report could not be read: {path}: {exc}")
    db_disagreements = []
    if project_db is not None and Path(project_db).is_file():
        try:
            with closing(sqlite3.connect(f"{Path(project_db).resolve().as_uri()}?mode=ro", uri=True)) as connection:
                for job in jobs:
                    queue_id = job.get("queue_id")
                    if not queue_id:
                        continue
                    row = connection.execute(
                        "SELECT status FROM runs WHERE queue_id = ? ORDER BY attempt_no DESC LIMIT 1", (queue_id,)
                    ).fetchone()
                    if row and normalize_status(row[0]) != normalize_status(job.get("status")):
                        db_disagreements.append({"queue_id": queue_id, "queue_status": job.get("status"),
                                                 "history_status": row[0]})
        except (OSError, sqlite3.Error) as exc:
            errors.append(f"History database could not be read: {exc}")
    if errors or owner["state"] == "UNCONFIRMED":
        status = "UNCONFIRMED"
    elif owner["state"] == "ACTIVE":
        status = "ACTIVE_RUNNER"
    elif db_disagreements or missing_outputs or report_terminal_evidence:
        status = "RECOVERY_REQUIRED"
    elif running or (live and live.get("phase") in RUNNING_STATUSES | {"RUNNER_ACTIVE"}):
        status = "STALE_RUNNING"
    else:
        status = "CLEAN"
    return {"status": status, "runtime_dir": str(runtime), "owner": owner,
            "running_queue_ids": running, "live_phase": live.get("phase") if live else None,
            "lock_files": lock_files, "odb_files": odb_files, "missing_outputs": missing_outputs,
            "artifact_observations": artifact_observations,
            "solver_process": "UNKNOWN", "process_evidence": process_evidence,
            "report_count": report_count,
            "report_terminal_evidence": report_terminal_evidence,
            "history_disagreements": db_disagreements, "errors": errors}
