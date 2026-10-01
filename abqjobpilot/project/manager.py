"""Project creation/opening and application-level recent history."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from abqjobpilot import config
from abqjobpilot.utils import now_iso, write_json

from .models import ProjectInfo


PROJECT_SCHEMA_VERSION = "1.0"
RECENT_LIMIT = 10


def default_recent_file() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    return base / "abqjobpilot" / "recent_projects.json"


def load_project_info(root_dir: str | Path) -> ProjectInfo:
    root = Path(root_dir).expanduser().resolve()
    path = root / "project.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Invalid project manifest: {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("application") != "abqjobpilot" or data.get("schema_version") != PROJECT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported project manifest: {path}")
    for key in ("project_id", "name", "created_at", "updated_at"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"Missing or invalid project field: {key}")
    try:
        uuid.UUID(data["project_id"])
    except ValueError as exc:
        raise ValueError("project_id must be a UUID") from exc
    if data.get("description") is not None and not isinstance(data["description"], str):
        raise ValueError("description must be a string or null")
    if not (root / "runtime").is_dir():
        raise ValueError(f"Project runtime directory is missing: {root / 'runtime'}")
    if not (root / "runtime" / "queue.json").is_file():
        raise ValueError(f"Project queue file is missing: {root / 'runtime' / 'queue.json'}")
    from abqjobpilot.queue_store import read_queue
    if not all(isinstance(item, dict) for item in read_queue(root / "runtime", strict=True)):
        raise ValueError("Project queue must contain job objects")
    return ProjectInfo(
        project_id=data["project_id"], name=data["name"], root_dir=str(root),
        created_at=data["created_at"], updated_at=data["updated_at"],
        description=data.get("description"), schema_version=data["schema_version"],
    )


class ProjectManager:
    def __init__(self, recent_file: str | Path | None = None):
        self.recent_file = Path(recent_file) if recent_file is not None else default_recent_file()
        self.current: ProjectInfo | None = None

    def validate_project(self, root_dir: str | Path) -> ProjectInfo:
        return load_project_info(root_dir)

    def create_project(self, root_dir: str | Path, name: str, description: str | None = None) -> ProjectInfo:
        root = Path(root_dir).expanduser().resolve()
        if not name or not name.strip():
            raise ValueError("Project name is required")
        if root.exists():
            raise FileExistsError(f"Project destination already exists: {root}")
        root.mkdir(parents=True, exist_ok=False)
        for relative in ("runtime/reports",):
            (root / relative).mkdir(parents=True, exist_ok=False)
        timestamp = now_iso()
        data = {
            "schema_version": PROJECT_SCHEMA_VERSION,
            "project_id": str(uuid.uuid4()),
            "name": name.strip(),
            "description": description,
            "created_at": timestamp,
            "updated_at": timestamp,
            "application": "abqjobpilot",
        }
        write_json(root / "project.json", data)
        write_json(root / "runtime" / "queue.json", {"schema_version": config.SCHEMA_VERSION, "jobs": []})
        write_json(root / "runtime" / "live_status.json", {
            "schema_version": config.SCHEMA_VERSION, "phase": "IDLE", "updated_at": timestamp,
        })
        return load_project_info(root)

    def open_project(self, root_dir: str | Path) -> ProjectInfo:
        project = self.validate_project(root_dir)
        self.current = project
        self._remember(project)
        return project

    def close_project(self) -> None:
        self.current = None

    def recent_projects(self, include_missing: bool = False) -> list[dict]:
        try:
            data = json.loads(self.recent_file.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return []
        entries = data.get("recent_projects", []) if isinstance(data, dict) else []
        if not isinstance(entries, list):
            return []
        valid = [item for item in entries if isinstance(item, dict) and isinstance(item.get("path"), str)]
        if not include_missing:
            valid = [item for item in valid if (Path(item["path"]) / "project.json").is_file()]
        return valid[:RECENT_LIMIT]

    def _remember(self, project: ProjectInfo) -> None:
        canonical = os.path.normcase(str(project.root.resolve()))
        existing = self.recent_projects(include_missing=True)
        entries = [item for item in existing if os.path.normcase(str(Path(item["path"]).resolve())) != canonical
                   and item.get("project_id") != project.project_id]
        entries.insert(0, {
            "project_id": project.project_id,
            "name": project.name,
            "path": project.root_dir,
            "last_opened_at": now_iso(),
        })
        write_json(self.recent_file, {"schema_version": PROJECT_SCHEMA_VERSION,
                                      "recent_projects": entries[:RECENT_LIMIT]})
