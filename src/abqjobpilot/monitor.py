"""Monitoring placeholders for future Abaqus execution."""

from __future__ import annotations

from pathlib import Path

from .utils import tail_text


def read_sta_tail(job: dict, line_count: int = 80) -> str:
    return tail_text(job.get("sta_path", ""), line_count=line_count)


def read_console_tail(job: dict, line_count: int = 80) -> str:
    log_path = job.get("log_path", "")
    if not log_path:
        return ""
    return tail_text(Path(log_path), line_count=line_count)
