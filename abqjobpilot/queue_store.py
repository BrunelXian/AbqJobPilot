"""JSON-backed queue storage.

The public functions here deliberately hide the persistence format so a later
SQLite implementation can keep the same GUI and command-console entry points.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import config
from .utils import ensure_runtime_dirs, now_iso, read_json, write_json


def init_storage() -> None:
    ensure_runtime_dirs()
    queue_path = Path(config.QUEUE_FILE)
    if not queue_path.exists():
        save_queue([])
    live_status_path = Path(config.LIVE_STATUS_FILE)
    if not live_status_path.exists():
        write_json(live_status_path, {"phase": "IDLE", "updated_at": now_iso()})


def load_queue() -> list[dict]:
    init_storage()
    data = read_json(config.QUEUE_FILE, [])
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data["jobs"]
    if isinstance(data, list):
        return data
    return []


def save_queue(jobs: list[dict]) -> None:
    ensure_runtime_dirs()
    write_json(config.QUEUE_FILE, jobs)


def _queue_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return f"q_{stamp}"


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).resolve())


def _bool_value(value: bool) -> bool:
    return bool(value)


def _build_job_record(
    inp_path: Path,
    cpus: int,
    gpus: int,
    batch_name: str | None,
    strategy_name: str | None,
    job_name: str | None,
    run_datacheck: bool,
    run_full: bool,
    notes: str,
) -> dict:
    work_dir = inp_path.parent
    resolved_job_name = job_name or inp_path.stem
    resolved_strategy = strategy_name or work_dir.name
    resolved_batch = batch_name or work_dir.parent.name
    odb_path = work_dir / f"{resolved_job_name}.odb"
    return {
        "queue_id": _queue_id(),
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
        "created_at": now_iso(),
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


def _validate_new_job(inp_path: Path, cpus: int, job_name: str | None, jobs: list[dict]) -> tuple[bool, str]:
    if not inp_path.exists():
        return False, f"ERROR: INP file does not exist:\n{inp_path}"
    if inp_path.suffix.lower() != ".inp":
        return False, f"ERROR: file is not an .inp file:\n{inp_path}"
    if not isinstance(cpus, int) or cpus <= 0:
        return False, "ERROR: cpus must be a positive integer"
    if not inp_path.parent.exists():
        return False, f"ERROR: work_dir does not exist:\n{inp_path.parent}"

    normalized_inp = _normalize_path(inp_path)
    resolved_job_name = job_name or inp_path.stem
    resolved_work_dir = _normalize_path(inp_path.parent)
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

    inp = Path(inp_path).expanduser()
    if not inp.is_absolute():
        inp = inp.resolve()
    else:
        inp = inp.resolve()

    jobs = load_queue()
    ok, message = _validate_new_job(inp, cpus, job_name, jobs)
    if not ok:
        return {"ok": False, "message": message}

    record = _build_job_record(
        inp,
        cpus,
        gpus,
        batch_name,
        strategy_name,
        job_name,
        run_datacheck,
        run_full,
        notes,
    )
    jobs.append(record)
    save_queue(jobs)
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
