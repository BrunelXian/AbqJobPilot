"""Pure read-only tool adapter over the public AbqJobPilot API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from abqjobpilot import config
from abqjobpilot.api import AbqJobPilotClient, JobRequest
from abqjobpilot.status_codes import normalize_status


MAX_LIST_ITEMS = 100


class ReadOnlyTools:
    def __init__(self, project_path: str):
        base = AbqJobPilotClient()
        self.project = base.projects.resolve(project=project_path)
        self.client = base.for_project(project=str(self.project.root))

    def _reply(self, status: str, data: dict[str, Any] | None = None,
               errors: list[str] | None = None, warnings: list[str] | None = None,
               error_details: list[dict[str, str]] | None = None) -> dict[str, Any]:
        return {
            "schema_version": config.SCHEMA_VERSION,
            "status": status,
            "project_id": self.project.project_id,
            "data": data or {},
            "errors": errors or [],
            "warnings": warnings or [],
            "error_details": error_details or [],
        }

    def _error(self, code: str, message: str) -> dict[str, Any]:
        return self._reply(code, errors=[message], error_details=[{"code": code, "message": message}])

    def _safe(self, action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return action()
        except (OSError, ValueError, TypeError) as exc:
            return self._error("INVALID_REQUEST", str(exc))

    def preflight(self, inp_path: str, job_name: str | None = None,
                  cpus: int = config.DEFAULT_CPUS, gpus: int = config.DEFAULT_GPUS,
                  working_dir: str | None = None, batch: str | None = None,
                  strategy: str | None = None) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            request = JobRequest(inp_path=inp_path, job_name=job_name, cpus=cpus, gpus=gpus,
                                 working_dir=working_dir, batch=batch, strategy=strategy)
            result = self.client.preflight(request).to_dict()
            data = {key: result.get(key) for key in (
                "inp_path", "inp_exists", "job_name", "cpus", "batch", "strategy",
                "working_dir", "expected_odb_path", "command_preview")}
            data["gpus"] = gpus
            return self._reply(result["status"], data, result["errors"], result["warnings"],
                               result["error_details"])
        return self._safe(action)

    def list_jobs(self, scope: str = "queue", status: str | None = None,
                  batch: str | None = None, strategy: str | None = None,
                  limit: int = 50) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            if scope not in {"queue", "history"}:
                return self._error("INVALID_REQUEST", "scope must be queue or history")
            if type(limit) is not int or limit <= 0:
                return self._error("INVALID_REQUEST", "limit must be a positive integer")
            bounded = min(limit, MAX_LIST_ITEMS)
            warnings = [f"limit capped at {MAX_LIST_ITEMS}"] if limit > MAX_LIST_ITEMS else []
            if scope == "history":
                result = self.client.list_project_jobs(project=str(self.project.root), status=status,
                                                       batch=batch, strategy=strategy, limit=bounded).to_dict()
                if result["errors"]:
                    return self._reply(result["status"], {"scope": scope, "jobs": []}, result["errors"],
                                       result.get("warnings", []), result.get("error_details", []))
                jobs = [{key: item.get(key) for key in (
                    "job_id", "job_name", "inp_path", "batch", "strategy", "latest_status",
                    "run_count", "latest_run_id", "updated_at")} for item in result["jobs"]]
            else:
                result = self.client.list_jobs()
                if result["errors"]:
                    return self._reply(result["status"], {"scope": scope, "jobs": []}, result["errors"],
                                       warnings, result.get("error_details", []))
                jobs = []
                for item in result["jobs"]:
                    if status and item["status"] != normalize_status(status):
                        continue
                    if batch and item.get("batch_name") != batch:
                        continue
                    if strategy and item.get("strategy_name") != strategy:
                        continue
                    jobs.append({"queue_id": item.get("queue_id"), "job_name": item.get("job_name"),
                                 "status": item.get("status"), "raw_status": item.get("raw_status"),
                                 "batch": item.get("batch_name"), "strategy": item.get("strategy_name"),
                                 "created_at": item.get("created_at"), "started_at": item.get("started_at"),
                                 "ended_at": item.get("ended_at")})
                    if len(jobs) >= bounded:
                        break
            return self._reply("OK", {"scope": scope, "jobs": jobs, "limit": bounded}, warnings=warnings)
        return self._safe(action)

    def job_status(self, scope: str, identifier: str) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            if scope not in {"queue", "history"} or not identifier:
                return self._error("INVALID_REQUEST", "Provide scope=queue|history and an identifier")
            if scope == "history":
                result = self.client.show_job(identifier, project=str(self.project.root)).to_dict()
                if result["errors"]:
                    return self._reply(result["status"], {"scope": scope, "identifier": identifier},
                                       result["errors"], result.get("warnings", []), result.get("error_details", []))
                run = result.get("latest_run")
                observed = run.get("status") if run else "UNKNOWN"
                data = {"scope": scope, "job_id": identifier,
                        "job_name": result["job"].get("job_name"),
                        "latest_run": {key: run.get(key) for key in (
                            "run_id", "queue_id", "attempt_no", "status", "raw_status",
                            "started_at", "completed_at", "error_code") } if run else None,
                        "observed_status": observed, "active_execution_confirmed": False}
                warnings = list(result.get("warnings", []))
                errors = []
                details = []
            else:
                result = self.client.status(job_id=identifier).to_dict()
                observed = result["status"]
                data = {"scope": scope, "queue_id": identifier, "observed_status": observed,
                        "inp_path": result.get("inp_path"), "working_dir": result.get("working_dir"),
                        "expected_odb_path": result.get("expected_odb_path"),
                        "odb_exists": result.get("odb_exists"), "lock_exists": result.get("lock_exists"),
                        "status_sources": result.get("status_sources"),
                        "last_log_lines": result.get("last_log_lines"),
                        "active_execution_confirmed": False}
                warnings = list(result["warnings"])
                errors = result["errors"]
                details = result["error_details"]
            if observed == "RUNNING":
                warnings.append("Stored RUNNING state does not confirm a live executor process.")
                return self._reply("STATUS_UNCONFIRMED", data, errors, warnings, details)
            return self._reply(observed, data, errors, warnings, details)
        return self._safe(action)

    def locate_outputs(self, queue_id: str | None = None,
                       inp_path: str | None = None) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            if bool(queue_id) == bool(inp_path):
                return self._error("INVALID_REQUEST", "Provide exactly one of queue_id or inp_path")
            result = self.client.locate_outputs(job_id=queue_id, inp_path=inp_path).to_dict()
            log_path = next((path for path in result["log_paths"] if path.lower().endswith(".log")), None)
            paths = {"ODB": result.get("expected_odb_path"), "STA": result.get("sta_path"),
                     "MSG": result.get("msg_path"), "DAT": result.get("dat_path"),
                     "LOG": log_path, "LCK": result.get("lck_path")}
            artifacts = {kind: {"path": path, "path_source": "recorded_or_expected" if path else "unavailable",
                                "exists": Path(path).is_file() if path else False}
                         for kind, path in paths.items()}
            source_keys = {"ODB": "odb_path", "STA": "sta_path", "MSG": "msg_path",
                           "DAT": "dat_path", "LOG": "log_path", "LCK": "lck_path"}
            for kind, entry in artifacts.items():
                entry["path_source"] = result.get("path_sources", {}).get(source_keys[kind], "unavailable")
            data = {"queue_id": queue_id, "inp_path": inp_path,
                    "working_dir": result.get("working_dir"), "artifacts": artifacts,
                    "odb_validity_verified": False}
            return self._reply("OK" if not result["errors"] else "OUTPUT_LOOKUP_INCOMPLETE", data,
                               result["errors"], result["warnings"], result["error_details"])
        return self._safe(action)

    def prepare_enqueue(self, inp_path: str, job_name: str | None = None,
                        cpus: int = config.DEFAULT_CPUS, gpus: int = config.DEFAULT_GPUS,
                        working_dir: str | None = None, batch: str | None = None,
                        strategy: str | None = None) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            request = JobRequest(inp_path=inp_path, job_name=job_name, cpus=cpus, gpus=gpus,
                                 working_dir=working_dir, batch=batch, strategy=strategy)
            preflight = self.client.preflight(request).to_dict()
            preview = self.client.enqueue(request, dry_run=True).to_dict()
            data = {key: preflight.get(key) for key in (
                "inp_path", "inp_exists", "job_name", "cpus", "batch", "strategy",
                "working_dir", "expected_odb_path")}
            data.update({"gpus": gpus, "command_preview": preview.get("command_preview"),
                         "queue_mutated": preview["queue_file_mutated"],
                         "solver_started": preview["solver_started"],
                         "runner_started": preview["runner_started"]})
            return self._reply(preview["status"], data, preview["errors"], preview["warnings"],
                               preview["error_details"])
        return self._safe(action)
