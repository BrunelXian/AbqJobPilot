"""JSON-backed queue storage.

The public functions here deliberately hide the persistence format so a later
SQLite implementation can keep the same GUI and command-console entry points.
"""

from __future__ import annotations

import json
import threading
import uuid
from functools import wraps
from pathlib import Path

from . import config
from .utils import ensure_runtime_dirs, now_iso, read_json, write_json


_QUEUE_LOCK = threading.RLock()


def _queue_path(runtime_dir: str | Path | None = None) -> Path:
    return Path(runtime_dir) / "queue.json" if runtime_dir is not None else Path(config.QUEUE_FILE)


def _queue_write_locked(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        with _QUEUE_LOCK:
            return function(*args, **kwargs)
    return wrapper


def _jobs_from_payload(data) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data["jobs"]
    raise ValueError("queue.json must contain a list or an object with a jobs list")


def read_queue(runtime_dir: str | Path | None = None, *, strict: bool = False) -> list[dict]:
    """Read queue records without creating runtime files."""
    path = _queue_path(runtime_dir)
    if not path.exists():
        return []
    if strict:
        return _jobs_from_payload(json.loads(path.read_text(encoding="utf-8-sig")))
    return _jobs_from_payload(read_json(path, []))


def init_storage() -> None:
    with _QUEUE_LOCK:
        ensure_runtime_dirs()
        queue_path = Path(config.QUEUE_FILE)
        if not queue_path.exists():
            save_queue([])
        live_status_path = Path(config.LIVE_STATUS_FILE)
        if not live_status_path.exists():
            write_json(live_status_path, {"schema_version": config.SCHEMA_VERSION, "phase": "IDLE", "updated_at": now_iso()})


def load_queue() -> list[dict]:
    init_storage()
    return read_queue()


@_queue_write_locked
def save_queue(jobs: list[dict], runtime_dir: str | Path | None = None) -> None:
    path = _queue_path(runtime_dir)
    existing = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    if path.exists():
        _jobs_from_payload(existing)
    payload = dict(existing) if isinstance(existing, dict) else {}
    payload.update({"schema_version": config.SCHEMA_VERSION, "jobs": jobs})
    write_json(path, payload)


def _queue_id() -> str:
    return f"q_{uuid.uuid4().hex}"


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).resolve())


def _bool_value(value: bool) -> bool:
    return bool(value)


def build_queue_record(
    inp_path: Path,
    cpus: int,
    gpus: int,
    batch_name: str | None,
    strategy_name: str | None,
    job_name: str | None,
    run_datacheck: bool,
    run_full: bool,
    notes: str,
    working_dir: str | Path | None = None,
    queue_id: str | None = None,
    created_at: str | None = None,
) -> dict:
    work_dir = Path(working_dir).expanduser().resolve() if working_dir is not None else inp_path.parent
    resolved_job_name = job_name or inp_path.stem
    resolved_strategy = strategy_name or work_dir.name
    resolved_batch = batch_name or work_dir.parent.name
    odb_path = work_dir / f"{resolved_job_name}.odb"
    return {
        "schema_version": config.SCHEMA_VERSION,
        "queue_id": queue_id or _queue_id(),
        "status": "QUEUED",
        "batch_name": resolved_batch,
        "strategy_name": resolved_strategy,
        "job_name": resolved_job_name,
        "inp_path": str(inp_path),
        "work_dir": str(work_dir),
        "cpus": cpus,
        "gpus": gpus,
        "run_datacheck": _bool_value(run_datacheck),
        "run_full": _bool_value(run_full),
        "created_at": created_at or now_iso(),
        "started_at": None,
        "ended_at": None,
        "duration_sec": None,
        "phase": "QUEUED",
        "return_code": None,
        "final_verdict": None,
        "fatal_reason": None,
        "warning_count": None,
        "odb_path": str(odb_path),
        "odb_size_bytes": odb_path.stat().st_size if odb_path.exists() else None,
        "sta_path": str(work_dir / f"{resolved_job_name}.sta"),
        "msg_path": str(work_dir / f"{resolved_job_name}.msg"),
        "dat_path": str(work_dir / f"{resolved_job_name}.dat"),
        "log_path": str(work_dir / f"{resolved_job_name}.log"),
        "notes": notes or "",
    }


def _validate_new_job(inp_path: Path, cpus: int, job_name: str | None, jobs: list[dict], working_dir: Path | None = None) -> tuple[bool, str]:
    if not inp_path.exists():
        return False, f"ERROR: INP file does not exist:\n{inp_path}"
    if inp_path.suffix.lower() != ".inp":
        return False, f"ERROR: file is not an .inp file:\n{inp_path}"
    if not isinstance(cpus, int) or cpus <= 0:
        return False, "ERROR: cpus must be a positive integer"
    work_dir = working_dir or inp_path.parent
    if not work_dir.is_dir():
        return False, f"ERROR: work_dir does not exist:\n{work_dir}"

    normalized_inp = _normalize_path(inp_path)
    resolved_job_name = job_name or inp_path.stem
    resolved_work_dir = _normalize_path(work_dir)
    for existing in jobs:
        if existing.get("status") not in config.ACTIVE_STATUSES:
            continue
        existing_inp = _normalize_path(existing.get("inp_path", ""))
        existing_work_dir = _normalize_path(existing.get("work_dir", ""))
        if existing_inp.lower() == normalized_inp.lower():
            return (
                False,
                "ERROR: job already exists in queue:\n"
                f"Job: {existing.get('job_name', resolved_job_name)}\n"
                f"INP: {existing.get('inp_path', inp_path)}",
            )
        if (
            str(existing.get("job_name", "")).lower() == resolved_job_name.lower()
            and existing_work_dir.lower() == resolved_work_dir.lower()
        ):
            return (
                False,
                "ERROR: job already exists in queue:\n"
                f"Job: {resolved_job_name}\n"
                f"INP: {existing.get('inp_path', inp_path)}",
            )
    return True, ""


@_queue_write_locked
def add_inp_job_to_queue(
    inp_path: str,
    cpus: int = config.DEFAULT_CPUS,
    gpus: int = config.DEFAULT_GPUS,
    batch_name: str | None = None,
    strategy_name: str | None = None,
    job_name: str | None = None,
    run_datacheck: bool = config.DEFAULT_RUN_DATACHECK,
    run_full: bool = config.DEFAULT_RUN_FULL,
    notes: str = "",
) -> dict:
    return enqueue_record(
        inp_path, cpus=cpus, gpus=gpus, batch_name=batch_name, strategy_name=strategy_name,
        job_name=job_name, run_datacheck=run_datacheck, run_full=run_full, notes=notes,
    )


@_queue_write_locked
def enqueue_record(
    inp_path: str,
    cpus: int = config.DEFAULT_CPUS,
    gpus: int = config.DEFAULT_GPUS,
    batch_name: str | None = None,
    strategy_name: str | None = None,
    job_name: str | None = None,
    run_datacheck: bool = config.DEFAULT_RUN_DATACHECK,
    run_full: bool = config.DEFAULT_RUN_FULL,
    notes: str = "",
    working_dir: str | None = None,
    runtime_dir: str | Path | None = None,
) -> dict:
    try:
        cpus = int(cpus)
    except (TypeError, ValueError):
        return {"ok": False, "message": "ERROR: cpus must be a positive integer"}
    try:
        gpus = int(gpus)
    except (TypeError, ValueError):
        return {"ok": False, "message": "ERROR: gpus must be a non-negative integer"}
    if gpus < 0:
        return {"ok": False, "message": "ERROR: gpus must be a non-negative integer"}

    inp = Path(inp_path).expanduser().resolve()
    work_dir = Path(working_dir).expanduser().resolve() if working_dir else inp.parent
    try:
        jobs = read_queue(runtime_dir, strict=True)
    except (OSError, ValueError) as exc:
        return {"ok": False, "message": f"ERROR: invalid queue data or queue read failed: {exc}"}
    ok, message = _validate_new_job(inp, cpus, job_name, jobs, work_dir)
    if not ok:
        return {"ok": False, "message": message}

    record = build_queue_record(
        inp,
        cpus,
        gpus,
        batch_name,
        strategy_name,
        job_name,
        run_datacheck,
        run_full,
        notes,
        working_dir=work_dir,
    )
    jobs.append(record)
    try:
        save_queue(jobs, runtime_dir=runtime_dir)
    except (OSError, ValueError) as exc:
        return {"ok": False, "message": f"ERROR: queue write failed: {exc}"}
    return {
        "ok": True,
        "message": "added job to queue",
        "queue_id": record["queue_id"],
        "job_name": record["job_name"],
        "strategy_name": record["strategy_name"],
        "batch_name": record["batch_name"],
        "inp_path": record["inp_path"],
        "work_dir": record["work_dir"],
        "cpus": record["cpus"],
        "gpus": record["gpus"],
        "queue_position": len(jobs),
        "job": record,
    }


@_queue_write_locked
def add_folder_to_queue(
    folder: str,
    pattern: str = "*.inp",
    cpus: int = config.DEFAULT_CPUS,
    gpus: int = config.DEFAULT_GPUS,
    batch_name: str | None = None,
    strategy_name: str | None = None,
) -> dict:
    target = Path(folder).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        return {"ok": False, "message": f"ERROR: folder does not exist:\n{target}", "added": []}
    inp_files = sorted(path for path in target.glob(pattern) if path.is_file())
    if not inp_files:
        return {"ok": False, "message": f"ERROR: no INP files matched {pattern} in:\n{target}", "added": []}

    added: list[dict] = []
    errors: list[str] = []
    for inp in inp_files:
        result = add_inp_job_to_queue(
            str(inp),
            cpus=cpus,
            gpus=gpus,
            batch_name=batch_name,
            strategy_name=strategy_name,
        )
        if result.get("ok"):
            added.append(result)
        else:
            errors.append(result.get("message", "ERROR: failed to add job"))
    return {
        "ok": bool(added) and not errors,
        "message": f"added {len(added)} job(s) to queue" if added else "ERROR: no jobs were added",
        "added": added,
        "errors": errors,
    }


def queued_jobs() -> list[dict]:
    return [job for job in load_queue() if job.get("status") in config.ACTIVE_STATUSES]


def result_jobs() -> list[dict]:
    return [job for job in load_queue() if job.get("status") in config.RESULT_STATUSES]


@_queue_write_locked
def update_job(queue_id: str, updates: dict) -> dict | None:
    jobs = load_queue()
    updated_job = None
    for job in jobs:
        if job.get("queue_id") == queue_id:
            job.update(updates)
            updated_job = job
            break
    if updated_job is not None:
        save_queue(jobs)
    return updated_job


def mark_job_skipped(queue_id: str) -> dict:
    job = update_job(
        queue_id,
        {
            "status": "SKIPPED",
            "phase": "SKIPPED",
            "ended_at": now_iso(),
            "final_verdict": "SKIPPED",
            "fatal_reason": "Skipped by user",
        },
    )
    if not job:
        return {"ok": False, "message": "ERROR: selected job not found"}
    return {"ok": True, "message": f"Skipped job: {job.get('job_name', queue_id)}", "job": job}


@_queue_write_locked
def remove_result_job(queue_id: str) -> dict:
    jobs = load_queue()
    removed_job = None
    remaining: list[dict] = []
    for job in jobs:
        if job.get("queue_id") == queue_id:
            removed_job = job
        else:
            remaining.append(job)

    if not removed_job:
        return {"ok": False, "message": "ERROR: selected result was not found"}
    if removed_job.get("status") not in config.RESULT_STATUSES:
        return {"ok": False, "message": "ERROR: only completed, failed, skipped, or cancelled results can be cleared"}

    save_queue(remaining)
    return {
        "ok": True,
        "message": f"Cleared result record: {removed_job.get('job_name', queue_id)}",
        "job": removed_job,
    }


@_queue_write_locked
def remove_queued_job(queue_id: str) -> dict:
    jobs = load_queue()
    if any(job.get("status") in {"DATACHECK_RUNNING", "FULL_RUNNING"} for job in jobs):
        return {"ok": False, "message": "ERROR: cannot change the queue while a job is running"}
    job = next((item for item in jobs if item.get("queue_id") == queue_id), None)
    if not job or job.get("status") != "QUEUED":
        return {"ok": False, "message": "ERROR: only a QUEUED job can be removed"}
    save_queue([item for item in jobs if item.get("queue_id") != queue_id])
    return {"ok": True, "message": f"Removed queue record: {job.get('job_name', queue_id)}", "job": job}


@_queue_write_locked
def move_queued_job(queue_id: str, direction: str) -> dict:
    if direction not in {"top", "up", "down"}:
        return {"ok": False, "message": "ERROR: invalid move direction"}
    jobs = load_queue()
    if any(job.get("status") in {"DATACHECK_RUNNING", "FULL_RUNNING"} for job in jobs):
        return {"ok": False, "message": "ERROR: cannot reorder while a job is running"}
    active_positions = [index for index, job in enumerate(jobs) if job.get("status") in config.ACTIVE_STATUSES]
    active_index = next((index for index, position in enumerate(active_positions) if jobs[position].get("queue_id") == queue_id), None)
    if active_index is None or jobs[active_positions[active_index]].get("status") != "QUEUED":
        return {"ok": False, "message": "ERROR: only a QUEUED job can be moved"}
    target_index = 0 if direction == "top" else active_index + (-1 if direction == "up" else 1)
    if target_index < 0 or target_index >= len(active_positions) or target_index == active_index:
        return {"ok": True, "message": "Job is already at that position"}
    if direction == "top":
        selected_position = active_positions[active_index]
        selected = jobs[selected_position]
        for index in range(active_index, 0, -1):
            jobs[active_positions[index]] = jobs[active_positions[index - 1]]
        jobs[active_positions[0]] = selected
    else:
        first, second = active_positions[active_index], active_positions[target_index]
        jobs[first], jobs[second] = jobs[second], jobs[first]
    save_queue(jobs)
    return {"ok": True, "message": "Queue order updated"}


@_queue_write_locked
def requeue_result_job(queue_id: str) -> dict:
    job = next((item for item in load_queue() if item.get("queue_id") == queue_id), None)
    if not job or job.get("status") not in config.RESULT_STATUSES:
        return {"ok": False, "message": "ERROR: selected result was not found"}
    return add_inp_job_to_queue(
        str(job.get("inp_path") or ""),
        cpus=job.get("cpus", config.DEFAULT_CPUS),
        gpus=job.get("gpus", config.DEFAULT_GPUS),
        batch_name=job.get("batch_name"),
        strategy_name=job.get("strategy_name"),
        job_name=job.get("job_name"),
        run_datacheck=job.get("run_datacheck", config.DEFAULT_RUN_DATACHECK),
        run_full=job.get("run_full", config.DEFAULT_RUN_FULL),
        notes=job.get("notes", ""),
    )


@_queue_write_locked
def apply_resources_to_queued_jobs(
    cpus: int,
    gpus: int,
    run_datacheck: bool,
    run_full: bool,
) -> dict:
    jobs = load_queue()
    updated = 0
    for job in jobs:
        if job.get("status") == "QUEUED":
            job["cpus"] = int(cpus)
            job["gpus"] = int(gpus)
            job["run_datacheck"] = bool(run_datacheck)
            job["run_full"] = bool(run_full)
            updated += 1
    if updated:
        save_queue(jobs)
    return {"ok": True, "message": f"Updated {updated} queued job(s).", "updated": updated}
