"""Job-centric display projection over authenticated, read-only Run snapshots."""
from __future__ import annotations


TERMINAL = frozenset({"FINISHED", "COMPLETED", "FAILED", "CANCELLED", "REJECTED"})
QUEUE_VISIBLE = frozenset({"PLANNED", "QUEUED", "START_INTENT", "RUNNING", "VALIDATING", "PAUSED", "BLOCKED", "UNKNOWN"})


def project_jobs(runs: dict[str, dict]) -> dict[str, dict]:
    """Aggregate attempts by Job ID without treating conclusions as task states.

    The caller supplies actual ProjectView records. Missing legacy-only fields
    are not inferred and remain absent for the UI to render as unavailable.
    """
    grouped: dict[str, list[dict]] = {}
    for run in runs.values():
        job_id = run.get("job_id")
        if isinstance(job_id, str) and job_id:
            grouped.setdefault(job_id, []).append(run)
    result = {}
    for job_id, attempts in grouped.items():
        attempts.sort(key=lambda r: (
            r.get("attempt_no") if type(r.get("attempt_no")) is int else -1,
            str(r.get("created_at") or ""), str(r.get("run_id") or "")), reverse=True)
        latest = attempts[0]
        terminal = next((r for r in attempts if r.get("execution") in TERMINAL), None)
        status = str(latest.get("execution") or "UNKNOWN")
        result[job_id] = {
            "job_id": job_id,
            "job_name": latest.get("job_name") or job_id,
            "latest": latest,
            "terminal": terminal,
            "attempts": attempts,
            "queue_visible": status in QUEUE_VISIBLE and (terminal is None or latest is not terminal),
            "result_visible": terminal is not None or status in {"UNKNOWN", "BLOCKED", "PAUSED", "RECONCILIATION_REQUIRED"},
        }
    return result


def queue_row(index: int, job: dict, unavailable: str) -> tuple[str, tuple[str, ...]]:
    run = job["latest"]
    return job["job_id"], (
        str(index), str(run.get("execution") or "UNKNOWN"), str(job.get("job_name") or unavailable),
        unavailable, unavailable,
        str(run.get("planned_cpus")) if type(run.get("planned_cpus")) is int else unavailable,
        str(run.get("planned_gpus")) if type(run.get("planned_gpus")) is int else unavailable,
    )


def result_row(job: dict, unavailable: str) -> tuple[str, tuple[str, ...]]:
    run = job.get("terminal") or job["latest"]
    return job["job_id"], (
        str(run.get("execution") or "UNKNOWN"), str(job.get("job_name") or unavailable),
        unavailable, unavailable, unavailable, unavailable, unavailable,
    )
