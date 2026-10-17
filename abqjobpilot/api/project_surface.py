"""Project-scoped automation operations; no GUI or solver imports."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from abqjobpilot import config
from abqjobpilot.database import ProjectHistoryRepository
from abqjobpilot.database.connection import DatabaseFailure
from abqjobpilot.project.archive import export_project_archive, import_project_archive
from abqjobpilot.project.manager import (ProjectManager, default_projects_root,
                                         ensure_default_projects_root)
from abqjobpilot.project.models import ProjectInfo
from abqjobpilot.queue_store import read_queue
from abqjobpilot.status_codes import normalize_status


@dataclass
class AutomationResult:
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error_details: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": config.SCHEMA_VERSION, "status": self.status,
                **self.data, "errors": self.errors, "warnings": self.warnings,
                "error_details": self.error_details}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class SurfaceFailure(Exception):
    def __init__(self, code: str, message: str, **details: Any):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def safe_project_folder(name: str) -> str:
    folder = name.strip()
    if (not folder or folder in {".", ".."} or folder.endswith((".", " "))
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', folder)
            or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", folder)):
        raise SurfaceFailure("INVALID_PROJECT_SELECTOR", "Project name is not a safe folder name")
    return folder


def _summary(project: ProjectInfo) -> dict[str, Any]:
    return {"project_id": project.project_id, "name": project.name,
            "description": project.description, "path": str(project.root),
            "schema_version": project.schema_version, "created_at": project.created_at,
            "updated_at": project.updated_at, "runtime_dir": str(project.runtime_dir),
            "database_exists": (project.root / "project.db").is_file()}


class ProjectAutomationSurface:
    def __init__(self, recent_file: str | Path | None = None):
        self.manager = ProjectManager(recent_file=recent_file)

    def _guard(self, action: Callable[[], AutomationResult]) -> AutomationResult:
        try:
            return action()
        except SurfaceFailure as exc:
            return AutomationResult(exc.code, exc.details, [exc.message],
                                    error_details=[{"code": exc.code, "message": exc.message}])
        except DatabaseFailure as exc:
            return AutomationResult(exc.code, errors=[exc.message], error_details=[exc.to_dict()])
        except FileExistsError as exc:
            code = "PROJECT_ALREADY_EXISTS"
            return AutomationResult(code, errors=[str(exc)], error_details=[{"code": code, "message": str(exc)}])
        except FileNotFoundError as exc:
            code = "PROJECT_NOT_FOUND"
            return AutomationResult(code, errors=[str(exc)], error_details=[{"code": code, "message": str(exc)}])
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            code = "PROJECT_INVALID"
            return AutomationResult(code, errors=[str(exc)], error_details=[{"code": code, "message": str(exc)}])

    def resolve(self, *, project: str | None = None, project_id: str | None = None,
                project_name: str | None = None) -> ProjectInfo:
        if project:
            path = Path(project).expanduser()
            if not path.is_dir():
                raise SurfaceFailure("PROJECT_NOT_FOUND", f"Project path not found: {path}")
            return self.manager.validate_project(path)
        if not project_id and not project_name:
            raise SurfaceFailure("INVALID_PROJECT_SELECTOR", "Provide --project, --project-id, or --project-name")
        entries = self.manager.recent_projects(include_missing=True)
        matches = [entry for entry in entries if (entry.get("project_id") == project_id if project_id else
                                                    entry.get("name") == project_name)]
        if len(matches) > 1:
            raise SurfaceFailure("AMBIGUOUS_PROJECT", "Project name matches multiple registrations",
                                 matches=[{"project_id": item.get("project_id"), "path": item.get("path")} for item in matches])
        if not matches:
            raise SurfaceFailure("PROJECT_NOT_FOUND", "Project is not registered")
        path = Path(matches[0]["path"])
        if not path.is_dir():
            raise SurfaceFailure("PROJECT_NOT_FOUND", f"Registered Project path is missing: {path}")
        info = self.manager.validate_project(path)
        if project_id and info.project_id != project_id:
            raise SurfaceFailure("PROJECT_INVALID", "Registered Project identity does not match manifest")
        return info

    def list_projects(self) -> AutomationResult:
        def action() -> AutomationResult:
            projects = []
            for entry in self.manager.recent_projects(include_missing=True):
                path = Path(entry["path"])
                projects.append({"project_id": entry.get("project_id"), "name": entry.get("name"),
                                 "path": str(path), "exists": (path / "project.json").is_file(),
                                 "schema_version": None, "last_opened_at": entry.get("last_opened_at")})
                if projects[-1]["exists"]:
                    try:
                        projects[-1]["schema_version"] = self.manager.validate_project(path).schema_version
                    except (OSError, ValueError):
                        pass
            return AutomationResult("OK", {"projects": projects})
        return self._guard(action)

    def create_project(self, name: str, *, path: str | None = None,
                       description: str | None = None) -> AutomationResult:
        def action() -> AutomationResult:
            if not isinstance(name, str) or not name.strip():
                raise SurfaceFailure("INVALID_PROJECT_SELECTOR", "Project name is required")
            destination = Path(path).expanduser() if path else ensure_default_projects_root() / safe_project_folder(name)
            info = self.manager.create_project(destination, name, description)
            return AutomationResult("PROJECT_CREATED", {"project": _summary(info)})
        return self._guard(action)

    def show_project(self, **selector: str | None) -> AutomationResult:
        def action() -> AutomationResult:
            info = self.resolve(**selector)
            summary = _summary(info)
            summary.update(self._history_counts(info))
            records = read_queue(info.runtime_dir, strict=True)
            summary["queue"] = {"queued": sum(normalize_status(item.get("status")) == "QUEUED" for item in records),
                                "running": sum(normalize_status(item.get("status")) == "RUNNING" for item in records),
                                "total_records": len(records)}
            return AutomationResult("OK", {"project": summary})
        return self._guard(action)

    def _history_counts(self, info: ProjectInfo) -> dict[str, int | None]:
        if not (info.root / "project.db").is_file():
            return {"job_count": None, "run_count": None, "artifact_reference_count": None}
        repository = ProjectHistoryRepository(info, read_only=True)
        jobs = repository.list_jobs()
        runs = [run for job in jobs for run in repository.list_runs(job["job_id"])]
        artifacts = sum(len(repository.list_artifacts(run["run_id"])) for run in runs)
        return {"job_count": len(jobs), "run_count": len(runs), "artifact_reference_count": artifacts}

    def update_project(self, *, name: str | None = None, description: str | None = None,
                       update_description: bool = False, **selector: str | None) -> AutomationResult:
        def action() -> AutomationResult:
            info = self.resolve(**selector)
            updated = self.manager.update_project(info.root, name=name, description=description,
                                                  update_description=update_description)
            return AutomationResult("PROJECT_UPDATED", {"project": _summary(updated)})
        return self._guard(action)

    def register_project(self, path: str) -> AutomationResult:
        return self._guard(lambda: AutomationResult("PROJECT_REGISTERED", {
            "project": _summary(self.manager.register_project(path))}))

    def unregister_project(self, **selector: str | None) -> AutomationResult:
        def action() -> AutomationResult:
            try:
                info = self.resolve(**selector)
            except SurfaceFailure as exc:
                if exc.code == "PROJECT_NOT_FOUND" and selector.get("project_id"):
                    raise SurfaceFailure("PROJECT_NOT_REGISTERED", "Project is not registered") from exc
                raise
            if not self.manager.unregister_project(info.project_id):
                raise SurfaceFailure("PROJECT_NOT_REGISTERED", "Project is not registered")
            return AutomationResult("PROJECT_UNREGISTERED", {"project_id": info.project_id,
                                                           "path": str(info.root)})
        return self._guard(action)

    def export_project(self, output: str, *, mode: str = "metadata", **selector: str | None) -> AutomationResult:
        def action() -> AutomationResult:
            info = self.resolve(**selector)
            if mode not in {"metadata", "project-owned"}:
                raise SurfaceFailure("INVALID_REQUEST", "Export mode must be metadata or project-owned")
            archive = export_project_archive(info.root, output, mode="full" if mode == "project-owned" else mode)
            return AutomationResult("PROJECT_EXPORTED", {"project_id": info.project_id,
                                                         "archive": str(archive), "mode": mode})
        return self._guard(action)

    def import_project_archive(self, archive: str, *, destination: str | None = None) -> AutomationResult:
        def action() -> AutomationResult:
            target = destination
            if target is None:
                with zipfile.ZipFile(archive) as source:
                    manifest = json.loads(source.read("project/project.json"))
                target = str(ensure_default_projects_root() / safe_project_folder(manifest["name"]))
            info = import_project_archive(archive, target, recent_file=self.manager.recent_file)
            return AutomationResult("PROJECT_IMPORTED", {"project": _summary(info)})
        return self._guard(action)

    def list_project_jobs(self, *, status: str | None = None, batch: str | None = None,
                          strategy: str | None = None, limit: int | None = None,
                          **selector: str | None) -> AutomationResult:
        def action() -> AutomationResult:
            info = self.resolve(**selector)
            if limit is not None and limit <= 0:
                raise SurfaceFailure("INVALID_REQUEST", "limit must be positive")
            if not (info.root / "project.db").is_file():
                return AutomationResult("OK", {"project_id": info.project_id, "jobs": []})
            repository = ProjectHistoryRepository(info, read_only=True)
            jobs = []
            for job in repository.list_jobs():
                runs = repository.list_runs(job["job_id"])
                latest = runs[0] if runs else None
                entry = {"job_id": job["job_id"], "job_name": job["job_name"], "inp_path": job["inp_path"],
                         "batch": job["batch"], "strategy": job["strategy"],
                         "latest_status": latest["status"] if latest else None,
                         "run_count": len(runs), "latest_run_id": latest["run_id"] if latest else None,
                         "updated_at": job["updated_at"]}
                if status and entry["latest_status"] != normalize_status(status):
                    continue
                if batch and entry["batch"] != batch:
                    continue
                if strategy and entry["strategy"] != strategy:
                    continue
                jobs.append(entry)
                if limit is not None and len(jobs) >= limit:
                    break
            return AutomationResult("OK", {"project_id": info.project_id, "jobs": jobs})
        return self._guard(action)

    def show_job(self, job_id: str, **selector: str | None) -> AutomationResult:
        def action() -> AutomationResult:
            info = self.resolve(**selector)
            if not (info.root / "project.db").is_file():
                raise SurfaceFailure("JOB_NOT_FOUND", f"Job not found: {job_id}")
            repository = ProjectHistoryRepository(info, read_only=True)
            job = next((item for item in repository.list_jobs() if item["job_id"] == job_id), None)
            if job is None:
                raise SurfaceFailure("JOB_NOT_FOUND", f"Job not found: {job_id}")
            runs = repository.list_runs(job_id)
            return AutomationResult("OK", {"project_id": info.project_id, "job": job,
                                           "latest_run": runs[0] if runs else None, "runs": runs,
                                           "artifacts": [{"run_id": run["run_id"], "items": repository.list_artifacts(run["run_id"])}
                                                         for run in runs]})
        return self._guard(action)
