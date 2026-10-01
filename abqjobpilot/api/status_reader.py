"""Read-only status and output discovery helpers for the public API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from abqjobpilot import config
from abqjobpilot.queue_store import read_queue
from abqjobpilot.status_codes import normalize_status
from abqjobpilot.utils import read_json, tail_text


def read_queue_file(runtime_dir: str | Path | None = None) -> list[dict[str, Any]]:
    return read_queue(runtime_dir, strict=True)


def read_live_status_file(runtime_dir: str | Path | None = None) -> dict[str, Any]:
    path = Path(runtime_dir) / "live_status.json" if runtime_dir is not None else Path(config.LIVE_STATUS_FILE)
    data = read_json(path, {})
    return data if isinstance(data, dict) else {}


def read_report_jobs(runtime_dir: str | Path | None = None) -> list[dict[str, Any]]:
    reports_dir = Path(runtime_dir or config.RUNTIME_DIR) / "reports"
    if not reports_dir.exists():
        return []
    jobs: list[dict[str, Any]] = []
    for path in sorted(reports_dir.glob("*.json")):
        if path.name.lower() == "manifest.json":
            continue
        data = read_json(path, {})
        if isinstance(data, dict):
            data.setdefault("_report_path", str(path))
            jobs.append(data)
    return jobs


def find_job(job_id: str | None = None, inp_path: str | None = None,
             runtime_dir: str | Path | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    sources: list[str] = []
    normalized_inp = _normalize_optional_path(inp_path)

    queue_jobs = read_queue_file(runtime_dir)
    for job in queue_jobs if job_id else reversed(queue_jobs):
        if _matches(job, job_id, normalized_inp):
            sources.append(str(Path(runtime_dir) / "queue.json") if runtime_dir is not None else config.QUEUE_FILE)
            return job, sources

    for job in read_report_jobs(runtime_dir):
        if _matches(job, job_id, normalized_inp):
            report_path = job.get("_report_path")
            if report_path:
                sources.append(str(report_path))
            return job, sources

    live_status = read_live_status_file(runtime_dir)
    if live_status:
        if job_id and live_status.get("queue_id") == job_id:
            sources.append(str(Path(runtime_dir) / "live_status.json") if runtime_dir is not None else config.LIVE_STATUS_FILE)
            return _job_from_live_status(live_status), sources

    return None, sources


def expected_paths(job: dict[str, Any]) -> dict[str, str | None]:
    job_name = job.get("job_name") or job.get("current_job")
    work_dir = job.get("work_dir")
    inp_path = job.get("inp_path")
    if not work_dir and inp_path:
        work_dir = str(Path(str(inp_path)).parent)

    paths: dict[str, str | None] = {
        "work_dir": str(work_dir) if work_dir else None,
        "odb_path": job.get("odb_path"),
        "sta_path": job.get("sta_path"),
        "msg_path": job.get("msg_path"),
        "dat_path": job.get("dat_path"),
        "log_path": job.get("log_path"),
        "lck_path": None,
    }
    if work_dir and job_name:
        base = Path(str(work_dir)) / str(job_name)
        paths["odb_path"] = paths["odb_path"] or str(base.with_suffix(".odb"))
        paths["sta_path"] = paths["sta_path"] or str(base.with_suffix(".sta"))
        paths["msg_path"] = paths["msg_path"] or str(base.with_suffix(".msg"))
        paths["dat_path"] = paths["dat_path"] or str(base.with_suffix(".dat"))
        paths["log_path"] = paths["log_path"] or str(base.with_suffix(".log"))
        paths["lck_path"] = str(base.with_suffix(".lck"))
    return paths


def last_log_lines(log_path: str | None, line_count: int = 40) -> list[str]:
    if not log_path:
        return []
    return tail_text(log_path, line_count=line_count).splitlines()


def public_status_from_job(job: dict[str, Any] | None, lock_exists: bool, odb_exists: bool) -> str:
    if not job:
        return "LOCKED" if lock_exists else "UNKNOWN"
    return normalize_status(job.get("status") or job.get("phase"), lock_exists=lock_exists, odb_exists=odb_exists)


def _normalize_optional_path(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return str(Path(path).expanduser().resolve()).lower()
    except OSError:
        return str(path).lower()


def _matches(job: dict[str, Any], job_id: str | None, normalized_inp: str | None) -> bool:
    if job_id and job.get("queue_id") == job_id:
        return True
    if normalized_inp:
        job_inp = _normalize_optional_path(job.get("inp_path"))
        return job_inp == normalized_inp
    return False


def _job_from_live_status(live_status: dict[str, Any]) -> dict[str, Any]:
    job_name = live_status.get("current_job")
    log_path = live_status.get("log_path")
    work_dir = str(Path(log_path).parent) if log_path else None
    return {
        "queue_id": live_status.get("queue_id"),
        "status": live_status.get("phase"),
        "phase": live_status.get("phase"),
        "job_name": job_name,
        "work_dir": work_dir,
        "sta_path": live_status.get("sta_path"),
        "log_path": log_path,
    }
