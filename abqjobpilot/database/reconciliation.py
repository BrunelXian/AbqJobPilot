"""Idempotent, one-way projection from Project runtime JSON to SQLite."""

from __future__ import annotations

import json
from pathlib import Path

from abqjobpilot.project.manager import load_project_info
from abqjobpilot.queue_store import read_queue
from abqjobpilot.status_codes import normalize_status

from .repository import ProjectHistoryRepository, TERMINAL_STATUSES


def sync_history_from_runtime(project_root: str | Path) -> dict[str, int]:
    project = load_project_info(project_root)
    records_by_id: dict[str, dict] = {}
    records_without_id: list[dict] = []
    for record in read_queue(project.runtime_dir, strict=True):
        if isinstance(record, dict):
            if record.get("queue_id"):
                records_by_id[record["queue_id"]] = record
            else:
                records_without_id.append(record)
    reports = project.runtime_dir / "reports"
    if reports.is_dir():
        for path in sorted(reports.glob("*.json")):
            if path.name.lower() == "manifest.json":
                continue
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                continue
            if not data.get("queue_id"):
                records_without_id.append(data)
                continue
            existing = records_by_id.get(data["queue_id"])
            if existing is None or (normalize_status(existing.get("status")) not in TERMINAL_STATUSES
                                    and normalize_status(data.get("status")) in TERMINAL_STATUSES):
                records_by_id[data["queue_id"]] = data
    repository = ProjectHistoryRepository(project)
    return repository.sync_records(list(records_by_id.values()) + records_without_id)
