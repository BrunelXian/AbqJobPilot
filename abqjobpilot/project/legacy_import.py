"""Read-only legacy runtime inspection and metadata-only import."""

from __future__ import annotations

import json
from pathlib import Path

from abqjobpilot import config
from abqjobpilot.queue_store import read_queue
from abqjobpilot.utils import now_iso, write_json

from .manager import ProjectManager
from .models import ProjectInfo


def import_legacy_runtime(source_runtime_dir: str | Path, destination_project_root: str | Path,
                          project_name: str, *, recent_file: str | Path | None = None) -> ProjectInfo:
    source = Path(source_runtime_dir).expanduser().resolve()
    destination = Path(destination_project_root).expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Legacy runtime directory does not exist: {source}")
    if destination.exists():
        raise FileExistsError(f"Project destination already exists: {destination}")

    queue_file = source / "queue.json"
    if not queue_file.is_file():
        raise ValueError(f"Legacy queue.json is missing: {queue_file}")
    raw_queue = json.loads(queue_file.read_text(encoding="utf-8-sig"))
    jobs = read_queue(source, strict=True)
    if not all(isinstance(item, dict) for item in jobs):
        raise ValueError("Legacy queue must contain job objects")
    source_schema = raw_queue.get("schema_version") if isinstance(raw_queue, dict) else None
    live_file = source / "live_status.json"
    live = json.loads(live_file.read_text(encoding="utf-8-sig")) if live_file.is_file() else None
    if live is not None and not isinstance(live, dict):
        raise ValueError("Legacy live status must be a JSON object")
    report_data = {}
    reports_dir = source / "reports"
    if reports_dir.is_dir():
        for path in reports_dir.glob("*.json"):
            if path.is_file():
                report_data[path.name] = json.loads(path.read_text(encoding="utf-8-sig"))

    manager = ProjectManager(recent_file=recent_file)
    project = manager._create_project(destination, project_name)
    write_json(project.runtime_dir / "queue.json", {"schema_version": config.SCHEMA_VERSION, "jobs": jobs})
    if live is not None:
        write_json(project.runtime_dir / "live_status.json", live)
    for name, data in report_data.items():
        write_json(project.runtime_dir / "reports" / name, data)
    manifest = json.loads(project.project_file.read_text(encoding="utf-8-sig"))
    manifest["import_provenance"] = {
        "imported": True,
        "source_type": "legacy_abqjobpilot_runtime",
        "source_path": str(source),
        "imported_at": now_iso(),
        "source_schema_version": source_schema,
    }
    write_json(project.project_file, manifest)
    from abqjobpilot.database.reconciliation import sync_history_from_runtime
    sync_history_from_runtime(destination)
    return manager.register_project(destination)
