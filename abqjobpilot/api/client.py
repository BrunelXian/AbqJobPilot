"""Safe public client for AbqPilot and other non-GUI integrations."""

from __future__ import annotations

from typing import Any
from pathlib import Path

from abqjobpilot import __version__, config
from abqjobpilot.queue_store import enqueue_record, read_queue
from abqjobpilot.status_codes import normalize_status
from .errors import error_detail

from .models import (
    JobOutputResult,
    JobPreflightResult,
    JobRequest,
    JobStatusResult,
    JobSubmitResult,
)
from .status_reader import (
    expected_paths,
    find_job,
    last_log_lines,
    public_status_from_job,
)


class AbqJobPilotClient:
    """GUI-free public integration client.

    The client defaults to preview and dry-run behavior. It does not start the
    background runner and does not call Abaqus.
    """

    def __init__(self, runtime_dir: str | None = None) -> None:
        self.runtime_dir = str(Path(runtime_dir or config.RUNTIME_DIR).expanduser().resolve())

    def capabilities(self) -> dict[str, Any]:
        return {
            "schema_version": config.SCHEMA_VERSION,
            "application": "abqjobpilot",
            "application_version": __version__,
            "automation_surface": "1.0",
            "capabilities": {
                "preflight": True, "enqueue": True, "enqueue_folder": True,
                "list": True, "status": True, "locate_outputs": True,
                "solver_start": False,
            },
        }

    def list_jobs(self) -> dict[str, Any]:
        try:
            jobs = read_queue(self.runtime_dir, strict=True)
        except (OSError, ValueError) as exc:
            message = f"Invalid status data: {exc}"
            return {"schema_version": config.SCHEMA_VERSION, "status": "INVALID_STATUS_DATA",
                    "jobs": [], "errors": [message], "error_details": [error_detail(message)]}
        entries = []
        for job in jobs:
            entry = dict(job)
            entry["raw_status"] = job.get("status")
            entry["status"] = normalize_status(job.get("status") or job.get("phase"))
            entries.append(entry)
        return {"schema_version": config.SCHEMA_VERSION, "status": "OK", "jobs": entries,
                "errors": [], "error_details": []}

    def enqueue_folder(self, folder: str, pattern: str = "*.inp", *, cpus: int = config.DEFAULT_CPUS,
                       gpus: int = config.DEFAULT_GPUS, batch: str | None = None,
                       strategy: str | None = None, dry_run: bool = True) -> dict[str, Any]:
        target = Path(folder).expanduser().resolve()
        if not target.is_dir() or not pattern or "/" in pattern or "\\" in pattern or "**" in pattern:
            message = f"Invalid folder or non-recursive pattern: {target} ({pattern})"
            return {"schema_version": config.SCHEMA_VERSION, "status": "INVALID_REQUEST", "results": [],
                    "errors": [message], "error_details": [error_detail(message)]}
        files = sorted(path for path in target.glob(pattern) if path.is_file() and path.suffix.lower() == ".inp")
        if not files:
            message = f"No INP files matched: {target} ({pattern})"
            return {"schema_version": config.SCHEMA_VERSION, "status": "INVALID_REQUEST", "results": [],
                    "errors": [message], "error_details": [error_detail(message)]}
        results = []
        for inp in files:
            request = JobRequest(inp_path=str(inp), cpus=cpus, gpus=gpus, batch=batch, strategy=strategy,
                                 submission_mode="preview_only" if dry_run else "enqueue_only")
            results.append(self.enqueue(request, dry_run=dry_run).to_dict())
        errors = [detail for result in results for detail in result.get("error_details", [])]
        return {"schema_version": config.SCHEMA_VERSION,
                "status": "DRY_RUN_READY" if dry_run and not errors else "ENQUEUED" if not errors else "PARTIAL",
                "results": results, "errors": [item["message"] for item in errors], "error_details": errors}

    def preflight(self, request: JobRequest) -> JobPreflightResult:
        resolved = _resolve_request(request)
        errors = list(resolved["errors"])
        warnings = list(resolved["warnings"])
        status = "PREVIEW_READY"

        if request.submission_mode not in {"preview_only", "enqueue_only", "submit"}:
            errors.append(f"Invalid submission_mode: {request.submission_mode}")
        if request.submission_mode == "submit" and not request.allow_solver_submit:
            status = "UNSAFE_REQUEST"
            errors.append("submit mode requires allow_solver_submit=True")

        if errors and status != "UNSAFE_REQUEST":
            status = "INVALID_REQUEST"

        return JobPreflightResult(
            status=status,
            job_id=None,
            inp_path=resolved["inp_path"],
            inp_exists=resolved["inp_exists"],
            job_name=resolved["job_name"],
            cpus=resolved["cpus"],
            batch=resolved["batch"],
            strategy=resolved["strategy"],
            working_dir=resolved["working_dir"],
            expected_odb_path=resolved["expected_odb_path"],
            command_preview=resolved["command_preview"] if status != "INVALID_REQUEST" else None,
            errors=errors,
            warnings=warnings,
        )

    def enqueue(self, request: JobRequest, dry_run: bool = True) -> JobSubmitResult:
        preflight = self.preflight(request)
        if not dry_run and (request.allow_solver_submit or request.submission_mode == "submit"):
            return JobSubmitResult(
                status="REJECTED_UNSAFE_DIRECT_SUBMIT",
                job_id=None,
                queue_file=str(_queue_file(self.runtime_dir)),
                command_preview=preflight.command_preview,
                expected_odb_path=preflight.expected_odb_path,
                errors=["REJECTED_UNSAFE_DIRECT_SUBMIT: public API does not submit Abaqus jobs."],
                warnings=preflight.warnings,
            )

        if preflight.status != "PREVIEW_READY":
            return JobSubmitResult(
                status="REJECTED",
                job_id=None,
                queue_file=str(_queue_file(self.runtime_dir)),
                command_preview=preflight.command_preview,
                expected_odb_path=preflight.expected_odb_path,
                errors=preflight.errors,
                warnings=preflight.warnings,
            )

        if dry_run:
            before = snapshot_runtime(self.runtime_dir)
            after = snapshot_runtime(self.runtime_dir)
            return JobSubmitResult(
                status="DRY_RUN_READY",
                job_id=None,
                queue_file=str(_queue_file(self.runtime_dir)),
                command_preview=preflight.command_preview,
                expected_odb_path=preflight.expected_odb_path,
                queue_only=True,
                queue_file_mutated=False,
                solver_started=False,
                runner_started=False,
                gui_required=False,
                allowed_mutations=["runtime/queue.json"],
                forbidden_mutations_detected=False,
                runtime_snapshot_before=before,
                runtime_snapshot_after=after,
                warnings=["Dry-run only; queue.json was not modified."],
            )

        return enqueue_job_queue_only(
            JobRequest(
                inp_path=preflight.inp_path,
                job_name=preflight.job_name,
                cpus=preflight.cpus,
                gpus=max(0, int(request.gpus or 0)),
                batch=preflight.batch,
                strategy=preflight.strategy,
                working_dir=preflight.working_dir,
                submission_mode=request.submission_mode,
                allow_solver_submit=request.allow_solver_submit,
                metadata=request.metadata,
            ),
            runtime_dir=self.runtime_dir,
            command_preview=preflight.command_preview,
            expected_odb_path=preflight.expected_odb_path,
            warnings=preflight.warnings,
        )

    def status(self, job_id: str | None = None, inp_path: str | None = None) -> JobStatusResult:
        try:
            job, sources = find_job(job_id=job_id, inp_path=inp_path, runtime_dir=self.runtime_dir)
        except (OSError, ValueError) as exc:
            job, sources = None, []
            read_error = f"Invalid status data: {exc}"
        else:
            read_error = None
        paths = expected_paths(job or _job_stub_from_inp(inp_path))
        odb_exists = _exists(paths.get("odb_path"))
        lock_exists = _exists(paths.get("lck_path"))
        status = public_status_from_job(job, lock_exists=lock_exists, odb_exists=odb_exists)
        errors: list[str] = []
        if not job and not lock_exists:
            errors.append("Job was not found in queue, live status, or reports.")
        if read_error:
            errors.insert(0, read_error)
        if not Path(self.runtime_dir).is_dir():
            errors.insert(0, f"Runtime directory does not exist: {self.runtime_dir}")
        warnings: list[str] = []
        if status == "ODB_MISSING":
            warnings.append("Job is completed but expected ODB file was not found.")
            errors.append(f"Expected output file not found: {paths.get('odb_path')}")
        if lock_exists:
            warnings.append("Abaqus lock file exists.")

        return JobStatusResult(
            status=status,
            job_id=(job or {}).get("queue_id") or job_id,
            inp_path=(job or {}).get("inp_path") or inp_path,
            working_dir=paths.get("work_dir"),
            expected_odb_path=paths.get("odb_path"),
            odb_exists=odb_exists,
            lock_exists=lock_exists,
            status_sources=sources,
            last_log_lines=last_log_lines(paths.get("log_path")),
            errors=errors,
            warnings=warnings,
        )

    def locate_outputs(self, job_id: str | None = None, inp_path: str | None = None) -> JobOutputResult:
        try:
            job, _sources = find_job(job_id=job_id, inp_path=inp_path, runtime_dir=self.runtime_dir)
        except (OSError, ValueError) as exc:
            job = None
            read_error = f"Invalid status data: {exc}"
        else:
            read_error = None
        paths = expected_paths(job or _job_stub_from_inp(inp_path))
        errors: list[str] = []
        if not job and job_id:
            errors.append("Job was not found in queue, live status, or reports.")
        elif not job and not inp_path:
            errors.append("Provide job_id or inp_path.")
        elif not job and inp_path:
            errors.append("Job was not found in queue, live status, or reports; paths were inferred from inp_path.")
        if read_error:
            errors.insert(0, read_error)
        if not Path(self.runtime_dir).is_dir():
            errors.insert(0, f"Runtime directory does not exist: {self.runtime_dir}")

        log_paths = [str(path) for path in (paths.get("log_path"), paths.get("sta_path"), paths.get("msg_path"), paths.get("dat_path")) if path]
        lock_exists = _exists(paths.get("lck_path"))
        warnings = ["Abaqus lock file exists."] if lock_exists else []
        if job and normalize_status(job.get("status") or job.get("phase")) == "COMPLETED" and not _exists(paths.get("odb_path")):
            errors.append(f"Expected output file not found: {paths.get('odb_path')}")
        return JobOutputResult(
            job_id=(job or {}).get("queue_id") or job_id,
            working_dir=paths.get("work_dir"),
            expected_odb_path=paths.get("odb_path"),
            odb_exists=_exists(paths.get("odb_path")),
            lock_exists=lock_exists,
            log_paths=log_paths,
            sta_path=paths.get("sta_path"),
            msg_path=paths.get("msg_path"),
            dat_path=paths.get("dat_path"),
            errors=errors,
            warnings=warnings,
        )


def _resolve_request(request: JobRequest) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        cpus = int(request.cpus)
    except (TypeError, ValueError):
        cpus = config.DEFAULT_CPUS
        errors.append("cpus must be a positive integer")
    if cpus <= 0:
        errors.append("cpus must be a positive integer")

    try:
        gpus = int(request.gpus)
    except (TypeError, ValueError):
        gpus = config.DEFAULT_GPUS
        errors.append("gpus must be a non-negative integer")
    if gpus < 0:
        errors.append("gpus must be a non-negative integer")

    inp = Path(request.inp_path).expanduser()
    try:
        inp = inp.resolve()
    except OSError:
        pass
    inp_exists = inp.exists()
    if not inp_exists:
        errors.append(f"INP file does not exist: {inp}")
    if inp.suffix.lower() != ".inp":
        errors.append(f"File is not an .inp file: {inp}")

    working_dir = Path(request.working_dir).expanduser() if request.working_dir else inp.parent
    try:
        working_dir = working_dir.resolve()
    except OSError:
        pass
    if not working_dir.exists():
        errors.append(f"working_dir does not exist: {working_dir}")

    job_name = request.job_name or inp.stem
    batch = request.batch or (working_dir.parent.name if working_dir.parent else None)
    strategy = request.strategy or working_dir.name
    expected_odb_path = str(working_dir / f"{job_name}.odb") if job_name and working_dir else None
    command_preview = _command_preview(str(inp), job_name, cpus, gpus)

    if gpus > 0:
        warnings.append("Datacheck preview omits gpus because Abaqus datacheck does not accept gpus.")

    return {
        "inp_path": str(inp),
        "inp_exists": inp_exists,
        "job_name": job_name,
        "cpus": cpus,
        "gpus": gpus,
        "batch": batch,
        "strategy": strategy,
        "working_dir": str(working_dir),
        "expected_odb_path": expected_odb_path,
        "command_preview": command_preview,
        "errors": errors,
        "warnings": warnings,
    }


def _command_preview(inp_path: str, job_name: str, cpus: int, gpus: int) -> str:
    prefix = _abaqus_cmd_prefix_preview()
    datacheck = prefix + [f"job={job_name}", f"input={inp_path}", "datacheck", f"cpus={cpus}", "interactive", "ask_delete=OFF"]
    full = prefix + [f"job={job_name}", f"input={inp_path}", f"cpus={cpus}"]
    if gpus > 0:
        full.append(f"gpus={gpus}")
    full.extend(["interactive", "ask_delete=OFF"])
    return "DATACHECK: " + _cmdline(datacheck) + "\nFULL_RUN: " + _cmdline(full)


def _abaqus_cmd_prefix_preview() -> list[str]:
    abaqus_cmd = config.ABAQUS_CMD
    if abaqus_cmd.lower().endswith((".bat", ".cmd")):
        return ["cmd.exe", "/c", abaqus_cmd]
    return [abaqus_cmd]


def _exists(path: str | None) -> bool:
    return bool(path) and Path(path).exists()


def enqueue_job_queue_only(
    request: JobRequest,
    runtime_dir: str | None = None,
    command_preview: str | None = None,
    expected_odb_path: str | None = None,
    warnings: list[str] | None = None,
) -> JobSubmitResult:
    """Append a queue record without importing GUI, runner, or Abaqus launchers."""

    queue_file = _queue_file(runtime_dir)
    before = snapshot_runtime(runtime_dir)
    base_warnings = list(warnings or [])

    if request.allow_solver_submit or request.submission_mode not in {"preview_only", "enqueue_only"}:
        return JobSubmitResult(
            status="REJECTED_UNSAFE_DIRECT_SUBMIT",
            job_id=None,
            queue_file=str(queue_file),
            command_preview=command_preview,
            expected_odb_path=expected_odb_path,
            runtime_snapshot_before=before,
            runtime_snapshot_after=snapshot_runtime(runtime_dir),
            errors=["REJECTED_UNSAFE_DIRECT_SUBMIT: enqueue-only API requires allow_solver_submit=False and submission_mode preview_only or enqueue_only."],
            warnings=base_warnings,
        )

    result = enqueue_record(
        inp_path=request.inp_path,
        cpus=request.cpus,
        gpus=request.gpus,
        batch_name=request.batch,
        strategy_name=request.strategy,
        job_name=request.job_name,
        working_dir=request.working_dir,
        notes=str(request.metadata.get("notes", "")) if isinstance(request.metadata, dict) else "",
        runtime_dir=runtime_dir,
    )
    if not result.get("ok"):
        return _failed_queue_only_result("FAILED", queue_file, command_preview, expected_odb_path,
                                         before, runtime_dir, [result.get("message", "Queue write failed")], base_warnings)

    after = snapshot_runtime(runtime_dir)
    comparison = compare_runtime_snapshots(before, after)
    if comparison["forbidden_mutations_detected"]:
        return JobSubmitResult(
            status="FAILED_FORBIDDEN_RUNTIME_MUTATION",
            job_id=result["queue_id"],
            queue_file=str(queue_file),
            command_preview=command_preview,
            expected_odb_path=expected_odb_path,
            queue_only=True,
            queue_file_mutated=bool(comparison["queue_file_mutated"]),
            solver_started=False,
            runner_started=False,
            gui_required=False,
            allowed_mutations=["runtime/queue.json"],
            forbidden_mutations_detected=True,
            runtime_snapshot_before=before,
            runtime_snapshot_after=after,
            errors=list(comparison["errors"]),
            warnings=base_warnings,
        )

    return JobSubmitResult(
        status="ENQUEUED",
        job_id=result["queue_id"],
        queue_file=str(queue_file),
        command_preview=command_preview,
        expected_odb_path=expected_odb_path,
        queue_only=True,
        queue_file_mutated=bool(comparison["queue_file_mutated"]),
        solver_started=False,
        runner_started=False,
        gui_required=False,
        allowed_mutations=["runtime/queue.json"],
        forbidden_mutations_detected=False,
        runtime_snapshot_before=before,
        runtime_snapshot_after=after,
        warnings=base_warnings,
    )


def snapshot_runtime(runtime_dir: str | None = None) -> dict[str, Any]:
    runtime = _runtime_dir(runtime_dir)
    return {
        "runtime_dir": str(runtime),
        "queue.json": _snapshot_path(_queue_file(runtime_dir)),
        "live_status.json": _snapshot_path(_live_status_file(runtime_dir)),
        "reports": _snapshot_path(runtime / "reports"),
    }


def compare_runtime_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    queue_changed = before.get("queue.json") != after.get("queue.json")
    forbidden: list[str] = []
    for key in ("live_status.json", "reports"):
        if before.get(key) != after.get(key):
            forbidden.append(key)
    return {
        "queue_file_mutated": queue_changed,
        "forbidden_mutations_detected": bool(forbidden),
        "forbidden_mutations": forbidden,
        "errors": [f"Forbidden runtime mutation detected: {item}" for item in forbidden],
    }


def _runtime_dir(runtime_dir: str | None = None) -> Path:
    return Path(runtime_dir or config.RUNTIME_DIR)


def _queue_file(runtime_dir: str | None = None) -> Path:
    if runtime_dir is None:
        return Path(config.QUEUE_FILE)
    return Path(runtime_dir) / "queue.json"


def _live_status_file(runtime_dir: str | None = None) -> Path:
    if runtime_dir is None:
        return Path(config.LIVE_STATUS_FILE)
    return Path(runtime_dir) / "live_status.json"


def _snapshot_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    if path.is_dir():
        files = [item for item in path.rglob("*") if item.is_file()]
        latest_mtime = max((item.stat().st_mtime_ns for item in files), default=path.stat().st_mtime_ns)
        return {
            "path": str(path),
            "exists": True,
            "is_dir": True,
            "file_count": len(files),
            "total_size": sum(item.stat().st_size for item in files),
            "mtime_ns": latest_mtime,
        }
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "is_dir": False,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _failed_queue_only_result(
    status: str,
    queue_file: Path,
    command_preview: str | None,
    expected_odb_path: str | None,
    before: dict[str, Any],
    runtime_dir: str | None,
    errors: list[str],
    warnings: list[str],
) -> JobSubmitResult:
    return JobSubmitResult(
        status=status,
        job_id=None,
        queue_file=str(queue_file),
        command_preview=command_preview,
        expected_odb_path=expected_odb_path,
        runtime_snapshot_before=before,
        runtime_snapshot_after=snapshot_runtime(runtime_dir),
        errors=errors,
        warnings=warnings,
    )


def _cmdline(parts: list[str]) -> str:
    return " ".join(_quote_arg(part) for part in parts)


def _quote_arg(value: str) -> str:
    text = str(value)
    if not text or any(ch.isspace() for ch in text) or '"' in text:
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _job_stub_from_inp(inp_path: str | None) -> dict:
    if not inp_path:
        return {}
    inp = Path(inp_path).expanduser()
    try:
        inp = inp.resolve()
    except OSError:
        pass
    return {
        "inp_path": str(inp),
        "job_name": inp.stem,
        "work_dir": str(inp.parent),
    }
