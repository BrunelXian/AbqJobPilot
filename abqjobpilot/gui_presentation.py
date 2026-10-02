"""Pure GUI presentation rules; persisted status and warnings stay untouched."""

from __future__ import annotations

from pathlib import Path

from .status_codes import normalize_status


SUCCESS_TAG = "success"
SUCCESS_FOREGROUND = "#166534"
SUCCESS_BACKGROUND = "#f0fdf4"


def status_presentation(raw_status: str | None, language: str = "en") -> tuple[str, str]:
    raw = str(raw_status or "").upper()
    canonical = normalize_status(raw)
    translated = language == "zh"
    if raw == "COMPLETED_WITH_WARNINGS":
        return ("完成 · 有警告" if translated else "Completed · warnings", SUCCESS_TAG)
    if canonical == "COMPLETED":
        return ("完成" if translated else "Completed", SUCCESS_TAG)
    if canonical == "FAILED" or raw == "UNKNOWN_INTERRUPTED":
        return ("失败" if translated else "Failed", "failed")
    if canonical == "RUNNING":
        return ("运行中" if translated else "Running", "running")
    if raw == "DATACHECK_OK":
        return ("预检通过" if translated else "Datacheck OK", "queued")
    if canonical == "QUEUED":
        return ("待执行" if translated else "Queued", "queued")
    if canonical == "CANCELLED":
        return ("已取消" if translated else "Cancelled", "skipped")
    if canonical == "SKIPPED":
        return ("已跳过" if translated else "Skipped", "skipped")
    return (raw or ("未知" if translated else "Unknown"), "queued")


def filter_jobs(jobs: list[dict], search: str = "", status_filter: str = "all",
                batch: str | None = None) -> list[dict]:
    query = search.strip().casefold()
    visible = []
    for job in jobs:
        if batch and str(job.get("batch_name") or "") != batch:
            continue
        raw = str(job.get("status") or "").upper()
        canonical = normalize_status(raw)
        if status_filter == "warnings" and raw != "COMPLETED_WITH_WARNINGS":
            continue
        if status_filter == "completed" and canonical != "COMPLETED":
            continue
        if status_filter == "failed" and canonical != "FAILED":
            continue
        if status_filter == "queued" and canonical != "QUEUED":
            continue
        if status_filter == "running" and canonical != "RUNNING":
            continue
        if query and not any(query in str(job.get(field) or "").casefold() for field in (
                "job_name", "batch_name", "strategy_name", "inp_path")):
            continue
        visible.append(job)
    return visible


def read_log_tail(path: str | Path | None, *, max_bytes: int = 65536,
                  max_lines: int = 80) -> str:
    """Read only the end of a possibly large solver log."""
    if not path or max_bytes <= 0 or max_lines <= 0:
        return ""
    try:
        with Path(path).open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            start = max(0, size - max_bytes)
            stream.seek(start)
            data = stream.read(max_bytes)
    except OSError:
        return ""
    text = data.decode("utf-8", errors="replace")
    if start:
        text = text.partition("\n")[2]
    return "\n".join(text.splitlines()[-max_lines:])
