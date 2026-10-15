"""Project-bound Agent Command execution through the public automation API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .api import AbqJobPilotClient, JobRequest
from .api.project_surface import SurfaceFailure
from .command_parser import CommandParseError, extract_agent_commands, parse_agent_command
from .project.models import ProjectInfo
from .settings_store import load_settings_for_runtime
from .utils import read_json


class AgentCommandSession:
    def __init__(self, *, recent_file: str | None = None, project: str | None = None,
                 runner_active: Callable[[], bool] | None = None,
                 confirm_folder: Callable[[dict], bool] | None = None):
        self.api = AbqJobPilotClient(recent_file=recent_file)
        self.target: ProjectInfo | None = None
        self.runner_active = runner_active or (lambda: False)
        self.confirm_folder = confirm_folder
        if project:
            self.use_project(project)

    def _result(self, status: str, message: str, *, data: dict | None = None,
                queue_changed: bool = False, target_changed: bool = False) -> dict:
        return {"status": status, "message": message, "data": data or {},
                "queue_changed": queue_changed, "target_changed": target_changed}

    def use_project(self, selector: str) -> dict:
        try:
            path = Path(selector).expanduser()
            info = self.api.projects.resolve(project=str(path) if path.is_dir() else None,
                                             project_name=None if path.is_dir() else selector)
        except SurfaceFailure as exc:
            self.target = None
            return self._result(exc.code, str(exc), target_changed=True)
        except (OSError, ValueError) as exc:
            self.target = None
            return self._result("PROJECT_SELECTION_FAILED", str(exc), target_changed=True)
        self.target = info
        return self._result("PROJECT_SELECTED", f"Target Project: {info.name} ({info.project_id})",
                            data={"project_id": info.project_id, "path": str(info.root)}, target_changed=True)

    def _target_for(self, parsed: dict) -> tuple[ProjectInfo | None, dict | None]:
        explicit = parsed.get("project")
        if explicit:
            try:
                path = Path(explicit).expanduser()
                info = self.api.projects.resolve(project=str(path) if path.is_dir() else None,
                                                 project_name=None if path.is_dir() else explicit)
                return info, None
            except SurfaceFailure as exc:
                self.target = None
                return None, self._result(exc.code, str(exc), target_changed=True)
            except (OSError, ValueError) as exc:
                self.target = None
                return None, self._result("PROJECT_SELECTION_FAILED", str(exc), target_changed=True)
        if self.target is None:
            return None, self._result("PROJECT_REQUIRED", "No target Project selected; use project use first.")
        try:
            info = self.api.projects.resolve(project=str(self.target.root))
        except SurfaceFailure as exc:
            self.target = None
            return None, self._result(exc.code, str(exc), target_changed=True)
        except (OSError, ValueError) as exc:
            self.target = None
            return None, self._result("PROJECT_SELECTION_FAILED", str(exc), target_changed=True)
        if info.project_id != self.target.project_id:
            self.target = None
            return None, self._result("PROJECT_SELECTION_FAILED", "Project identity changed on disk.",
                                      target_changed=True)
        return info, None

    def _admission(self, info: ProjectInfo) -> dict | None:
        if self.runner_active():
            return self._result("RUNNER_ACTIVE", "Runner is active; enqueue may execute immediately.")
        live = read_json(info.runtime_dir / "live_status.json", None)
        if not isinstance(live, dict) or live.get("phase") != "IDLE":
            return self._result("RUNNER_STATE_UNCONFIRMED", "Runtime is not confirmed idle; enqueue rejected.")
        listing = self.api.for_project(project=str(info.root)).list_jobs()
        if listing.get("errors"):
            return self._result("INVALID_STATUS_DATA", "; ".join(listing["errors"]))
        if any(job.get("status") == "RUNNING" for job in listing["jobs"]):
            return self._result("RUNNER_STATE_UNCONFIRMED", "Queue contains an unconfirmed RUNNING record.")
        return None

    def _resources(self, info: ProjectInfo, parsed: dict) -> tuple[int, int, dict]:
        settings = load_settings_for_runtime(info.runtime_dir)
        cpus = parsed.get("cpus") if parsed.get("cpus") is not None else settings["default_cpus"]
        gpus = parsed.get("gpus") if parsed.get("gpus") is not None else (
            settings["default_gpus"] if settings["use_gpu"] else 0)
        return cpus, gpus, settings

    def execute(self, command_text: str) -> dict:
        try:
            parsed = parse_agent_command(command_text)
        except CommandParseError as exc:
            if command_text.strip().startswith("project"):
                self.target = None
            return self._result("INVALID_COMMAND", str(exc), target_changed=command_text.strip().startswith("project"))
        command = parsed["command"]
        if command == "project":
            action = parsed["project_action"]
            if action == "list":
                data = self.api.list_projects().to_dict()
                return self._result(data["status"], json.dumps(data["projects"], ensure_ascii=False, indent=2), data=data)
            if action == "create":
                data = self.api.create_project(parsed["name"]).to_dict()
                return self._result(data["status"], json.dumps(data, ensure_ascii=False, indent=2),
                                    data=data, target_changed=data["status"] == "PROJECT_CREATED")
            if action == "use":
                return self.use_project(parsed["project"])
            info, error = self._target_for(parsed)
            if error:
                return error
            data = self.api.show_project(project=str(info.root)).to_dict()
            return self._result(data["status"], json.dumps(data, ensure_ascii=False, indent=2), data=data)
        if command in {"help", "clear"}:
            return self._result(command.upper(), "")
        info, error = self._target_for(parsed)
        if error:
            return error
        client = self.api.for_project(project=str(info.root))
        if command == "list":
            data = client.list_jobs()
            content = data if data.get("errors") else data.get("jobs", [])
            return self._result(data["status"], json.dumps(content, ensure_ascii=False, indent=2), data=data)
        if command in {"status", "outputs"}:
            result = (client.status(job_id=parsed["job_id"]) if command == "status" else
                      client.locate_outputs(job_id=parsed["job_id"]))
            data = result.to_dict()
            return self._result(data.get("status", "OK"), json.dumps(data, ensure_ascii=False, indent=2), data=data)

        admission = self._admission(info)
        if admission:
            return admission
        cpus, gpus, settings = self._resources(info, parsed)
        if command == "enqueue":
            request = JobRequest(inp_path=parsed["inp"], job_name=parsed.get("job_name"),
                                 cpus=cpus, gpus=gpus, batch=parsed.get("batch_name"),
                                 strategy=parsed.get("strategy_name"), submission_mode="enqueue_only",
                                 run_datacheck=settings["run_datacheck"] if parsed.get("datacheck") is None else parsed["datacheck"],
                                 run_full=settings["run_full"] if parsed.get("full_run") is None else parsed["full_run"],
                                 metadata={"notes": parsed.get("notes", "")})
            preflight = client.preflight(request)
            if preflight.status != "PREVIEW_READY":
                return self._result(preflight.status, "; ".join(preflight.errors))
            admission = self._admission(info)
            if admission:
                return admission
            data = client.enqueue(request, dry_run=False).to_dict()
            return self._result(data["status"], json.dumps(data, ensure_ascii=False, indent=2),
                                data=data, queue_changed=data["status"] == "ENQUEUED")
        if command == "enqueue-folder":
            folder = Path(parsed["folder"]).expanduser().resolve()
            pattern = parsed["pattern"]
            if not folder.is_dir() or not pattern or "/" in pattern or "\\" in pattern or "**" in pattern:
                return self._result("INVALID_REQUEST", "Folder or non-recursive pattern is invalid.")
            files = sorted(path for path in folder.glob(pattern) if path.is_file() and path.suffix.lower() == ".inp")
            if not files or any(not path.resolve().is_relative_to(folder) for path in files):
                return self._result("INVALID_REQUEST", "No safe matching INP files within the selected folder.")
            preview = client.enqueue_folder(str(folder), pattern, cpus=cpus, gpus=gpus,
                                            batch=parsed.get("batch_name"), strategy=parsed.get("strategy_name"),
                                            dry_run=True)
            if preview["status"] != "DRY_RUN_READY":
                return self._result(preview["status"], json.dumps(preview, ensure_ascii=False), data=preview)
            requests = []
            for path in files:
                checked = client.preflight(JobRequest(
                    inp_path=str(path), cpus=cpus, gpus=gpus,
                    batch=parsed.get("batch_name"), strategy=parsed.get("strategy_name")))
                requests.append({"inp_path": checked.inp_path, "job_name": checked.job_name,
                                 "working_dir": checked.working_dir, "cpus": checked.cpus,
                                 "gpus": gpus, "batch": checked.batch, "strategy": checked.strategy,
                                 "expected_odb_path": checked.expected_odb_path})
            summary = {"project_id": info.project_id, "project": info.name,
                       "project_path": str(info.root), "count": len(files),
                       "inputs": [str(path.resolve()) for path in files],
                       "requests": requests, "previews": preview["results"]}
            if self.confirm_folder is None or not self.confirm_folder(summary):
                return self._result("CONFIRMATION_REQUIRED", "Folder preview was not approved.", data=summary)
            admission = self._admission(info)
            if admission:
                return admission
            data = client.enqueue_folder(str(folder), pattern, cpus=cpus, gpus=gpus,
                                         batch=parsed.get("batch_name"), strategy=parsed.get("strategy_name"),
                                         dry_run=False)
            changed = any(item.get("status") == "ENQUEUED" for item in data["results"])
            return self._result(data["status"], json.dumps(data, ensure_ascii=False, indent=2),
                                data={**data, "preview": summary}, queue_changed=changed)
        return self._result("INVALID_COMMAND", f"Unsupported command: {command}")

    def execute_lines(self, text: str) -> list[dict]:
        return [self.execute(line) for line in extract_agent_commands(text)]
