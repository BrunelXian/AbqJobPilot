"""Pure ordering and identity helpers for the queue and results tables."""

from __future__ import annotations

from datetime import datetime

from . import config


def queue_display_jobs(jobs: list[dict]) -> list[dict]:
    # The runner scans the persisted list from top to bottom.
    return [job for job in jobs if job.get("status") in config.ACTIVE_STATUSES or job.get("status") == "RUNNING"]


def result_display_jobs(jobs: list[dict]) -> list[dict]:
    results = [job for job in jobs if job.get("status") in config.RESULT_STATUSES or
               job.get("status") in {"COMPLETED", "FAILED"}]
    return sorted(results, key=_result_time, reverse=True)


def _result_time(job: dict) -> float:
    for field in ("ended_at", "completed_at", "updated_at", "created_at", "started_at"):
        value = job.get(field)
        if not value:
            continue
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
    return float("-inf")


def row_iid(job: dict, results: bool = False) -> str:
    job_id = str(job["queue_id"])
    return f"result_{job_id}" if results else job_id


def selected_job_id(selected_iid: str | None, results: bool = False) -> str | None:
    if not selected_iid:
        return None
    return selected_iid.removeprefix("result_") if results else selected_iid


def restore_iid(job_id: str | None, visible_jobs: list[dict], results: bool = False) -> str | None:
    if job_id and any(str(job.get("queue_id")) == job_id for job in visible_jobs):
        return f"result_{job_id}" if results else job_id
    return None


def restore_iids(selected_iids: tuple[str, ...], visible_jobs: list[dict],
                 results: bool = False) -> tuple[str, ...]:
    visible = {row_iid(job, results=results) for job in visible_jobs}
    return tuple(iid for iid in selected_iids if iid in visible)
