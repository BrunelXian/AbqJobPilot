"""Sequential Abaqus queue runner."""

from __future__ import annotations

import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from . import config
from .parsers import classify_datacheck_attempt, classify_final_verdict, parse_sta_status
from .queue_store import load_queue, update_job
from .settings_store import load_settings
from .utils import now_iso, read_json, tail_text, write_json


def _effective_gpus(job: dict) -> int:
    try:
        return max(0, int(job.get("gpus") or 0))
    except (TypeError, ValueError):
        return 0


def _effective_cpus(job: dict) -> int:
    try:
        return max(1, int(job.get("cpus") or config.DEFAULT_CPUS))
    except (TypeError, ValueError):
        return config.DEFAULT_CPUS


def _abaqus_cmd_prefix() -> list[str]:
    settings = load_settings()
    abaqus_cmd = settings.get("abaqus_cmd") or config.ABAQUS_CMD
    # Windows batch files should be launched through cmd.exe, while still
    # avoiding shell=True and arbitrary shell command execution.
    if abaqus_cmd.lower().endswith((".bat", ".cmd")):
        return ["cmd.exe", "/c", abaqus_cmd]
    return [abaqus_cmd]


def _hidden_startupinfo() -> subprocess.STARTUPINFO | None:
    if not hasattr(subprocess, "STARTUPINFO"):
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    startupinfo.wShowWindow = 0
    return startupinfo


def _hidden_creationflags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _with_resources(job: dict, command: list[str], include_gpus: bool = True) -> list[str]:
    command.append(f"cpus={_effective_cpus(job)}")
    if include_gpus:
        gpus = _effective_gpus(job)
        if gpus > 0:
            command.append(f"gpus={gpus}")
    command.extend(["interactive", "ask_delete=OFF"])
    return command


def build_abaqus_datacheck_command(job: dict) -> list[str]:
    command = _abaqus_cmd_prefix()
    command.extend([f"job={job['job_name']}", f"input={job['inp_path']}", "datacheck"])
    return _with_resources(job, command, include_gpus=False)


def build_abaqus_full_run_command(job: dict) -> list[str]:
    command = _abaqus_cmd_prefix()
    command.extend([f"job={job['job_name']}", f"input={job['inp_path']}"])
    return _with_resources(job, command)


def _read_text(path: str | Path) -> str:
    target = Path(path)
    if not target.exists():
        return ""
    try:
        return target.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _duration_seconds(started_at: str | None) -> int | None:
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(started_at)
    except ValueError:
        return None
    return int((datetime.now() - start).total_seconds())


def _odb_size(job: dict) -> int | None:
    path = Path(job.get("odb_path", ""))
    if not path.exists():
        return None
    try:
        return path.stat().st_size
    except OSError:
        return None


def _write_live_status(job: dict | None = None, phase: str = "IDLE", extra: dict | None = None) -> None:
    payload = {
        "schema_version": config.SCHEMA_VERSION,
        "phase": phase,
        "updated_at": now_iso(),
    }
    if job:
        sta_status = parse_sta_status(_read_text(job.get("sta_path", "")))
        payload.update(
            {
                "queue_id": job.get("queue_id"),
                "current_job": job.get("job_name", ""),
                "strategy_name": job.get("strategy_name", ""),
                "batch_name": job.get("batch_name", ""),
                "step": sta_status.get("step", ""),
                "increment": sta_status.get("increment", ""),
                "analysis_time": sta_status.get("analysis_time", ""),
                "odb_size_bytes": _odb_size(job),
                "started_at": job.get("started_at", ""),
                "elapsed_time": str(_duration_seconds(job.get("started_at")) or ""),
                "sta_path": job.get("sta_path", ""),
                "log_path": job.get("log_path", ""),
            }
        )
    if extra:
        payload.update(extra)
    try:
        write_json(config.LIVE_STATUS_FILE, payload)
    except OSError:
        # Live status is best-effort telemetry. A transient Windows file lock
        # should not kill the Abaqus runner after the solver has completed.
        pass


def _refresh_job_paths(job: dict) -> dict:
    job = job.copy()
    job_name = job.get("job_name", "")
    work_dir = Path(job.get("work_dir", ""))
    job.setdefault("sta_path", str(work_dir / f"{job_name}.sta"))
    job.setdefault("msg_path", str(work_dir / f"{job_name}.msg"))
    job.setdefault("dat_path", str(work_dir / f"{job_name}.dat"))
    job.setdefault("log_path", str(work_dir / f"{job_name}.log"))
    job.setdefault("odb_path", str(work_dir / f"{job_name}.odb"))
    return job


def _write_report(job: dict) -> None:
    reports_dir = Path(config.RUNTIME_DIR) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in job.get("job_name", "job"))
    report_path = reports_dir / f"{job.get('queue_id', 'unknown')}_{safe_name}.json"
    write_json(report_path, {**job, "schema_version": config.SCHEMA_VERSION})
    manifest_path = reports_dir / "manifest.json"
    manifest = read_json(manifest_path, [])
    if not isinstance(manifest, list):
        manifest = []
    manifest = [item for item in manifest if item.get("queue_id") != job.get("queue_id")]
    manifest.append(
        {
            "schema_version": config.SCHEMA_VERSION,
            "queue_id": job.get("queue_id"),
            "job_name": job.get("job_name"),
            "status": job.get("status"),
            "ended_at": job.get("ended_at"),
            "report_path": str(report_path),
        }
    )
    write_json(manifest_path, manifest)


def _run_command(job: dict, phase: str, command: list[str]) -> int:
    job = _refresh_job_paths(job)
    log_path = Path(job["log_path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", errors="ignore") as log_file:
        log_file.write(f"\n[{now_iso()}] START {phase}\n")
        log_file.write(f"Command: {subprocess.list2cmdline(command)}\n\n")
        log_file.flush()
        process = subprocess.Popen(
            command,
            cwd=job["work_dir"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            startupinfo=_hidden_startupinfo(),
            creationflags=_hidden_creationflags(),
        )
        while process.poll() is None:
            _write_live_status(job, phase)
            time.sleep(config.POLL_INTERVAL_SECONDS)
        return_code = process.returncode
        log_file.write(f"\n[{now_iso()}] END {phase} return_code={return_code}\n")
        log_file.flush()
    _write_live_status(job, phase, {"return_code": return_code})
    return return_code


def run_next_job(job: dict) -> dict:
    """Run one job synchronously.

    This function is intentionally explicit: calling it will submit Abaqus.
    GUI code runs it only after the user presses Start Queue and confirms.
    """

    job = _refresh_job_paths(job)
    queue_id = job["queue_id"]
    started_at = job.get("started_at") or now_iso()
    update_job(
        queue_id,
        {
            "started_at": started_at,
            "phase": "STARTED",
            "status": "QUEUED",
            "return_code": None,
            "fatal_reason": None,
            "final_verdict": None,
        },
    )
    refreshed = next((item for item in load_queue() if item.get("queue_id") == queue_id), None)
    if refreshed:
        job.update(refreshed)

    datacheck_already_ok = job.get("status") == "DATACHECK_OK"

    if job.get("run_datacheck", True) and not datacheck_already_ok:
        update_job(queue_id, {"status": "DATACHECK_RUNNING", "phase": "DATACHECK_RUNNING"})
        job.update({"status": "DATACHECK_RUNNING", "phase": "DATACHECK_RUNNING"})
        return_code = _run_command(job, "DATACHECK_RUNNING", build_abaqus_datacheck_command(job))
        log_text = _read_text(job.get("log_path", ""))
        verdict = classify_datacheck_attempt(log_text, return_code)
        if verdict["status"] != "DATACHECK_PASS":
            updates = {
                "status": verdict["status"],
                "phase": verdict["status"],
                "ended_at": now_iso(),
                "duration_sec": _duration_seconds(started_at),
                "return_code": return_code,
                "final_verdict": verdict.get("final_verdict", "FAILED"),
                "fatal_reason": verdict.get("fatal_reason") or f"datacheck return code {return_code}",
                "warning_count": verdict.get("warning_count"),
                "odb_size_bytes": _odb_size(job),
            }
            final_job = update_job(queue_id, updates) or job
            _write_live_status(final_job, verdict["status"])
            _write_report(final_job)
            return {"ok": False, "message": "datacheck failed", "job": final_job}
        update_job(
            queue_id,
            {
                "status": "DATACHECK_OK",
                "phase": "DATACHECK_PASS",
                "return_code": return_code,
                "final_verdict": verdict.get("final_verdict"),
                "fatal_reason": "",
                "warning_count": verdict.get("warning_count"),
            },
        )
        job.update({"status": "DATACHECK_OK", "phase": "DATACHECK_PASS", "return_code": return_code})

    if job.get("run_full", True):
        update_job(queue_id, {"status": "FULL_RUNNING", "phase": "FULL_RUNNING"})
        job.update({"status": "FULL_RUNNING", "phase": "FULL_RUNNING"})
        return_code = _run_command(job, "FULL_RUNNING", build_abaqus_full_run_command(job))
        sta_text = _read_text(job.get("sta_path", ""))
        msg_text = _read_text(job.get("msg_path", ""))
        dat_text = _read_text(job.get("dat_path", ""))
        log_text = _read_text(job.get("log_path", ""))
        verdict = classify_final_verdict(sta_text, msg_text, dat_text, log_text, return_code)
        updates = {
            "status": verdict["status"],
            "phase": verdict["status"],
            "ended_at": now_iso(),
            "duration_sec": _duration_seconds(started_at),
            "return_code": return_code,
            "final_verdict": verdict.get("final_verdict"),
            "fatal_reason": verdict.get("fatal_reason"),
            "warning_count": verdict.get("warning_count"),
            "odb_size_bytes": _odb_size(job),
        }
        final_job = update_job(queue_id, updates) or job
        _write_live_status(final_job, verdict["status"])
        _write_report(final_job)
        return {"ok": verdict.get("final_verdict") == "SUCCESS", "message": verdict["status"], "job": final_job}

    updates = {
        "status": "COMPLETED_OK",
        "phase": "DATACHECK_OK",
        "ended_at": now_iso(),
        "duration_sec": _duration_seconds(started_at),
        "final_verdict": "DATACHECK_ONLY",
        "odb_size_bytes": _odb_size(job),
    }
    final_job = update_job(queue_id, updates) or job
    _write_report(final_job)
    return {"ok": True, "message": "datacheck only complete", "job": final_job}


class QueueRunner:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_after_current = False

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> dict:
        with self._lock:
            if self.is_running():
                return {"ok": False, "message": "Queue runner is already running."}
            self._stop_after_current = False
            self._thread = threading.Thread(target=self._run_loop, name="abqjobpilot-runner", daemon=True)
            self._thread.start()
        return {"ok": True, "message": "Queue runner started."}

    def request_stop_after_current(self) -> dict:
        self._stop_after_current = True
        return {"ok": True, "message": "Runner will stop after the current job finishes."}

    def _next_queued_job(self) -> dict | None:
        for job in load_queue():
            if job.get("status") in {"QUEUED", "DATACHECK_OK"}:
                return job
        return None

    def _run_loop(self) -> None:
        _write_live_status(phase="RUNNER_ACTIVE")
        try:
            while True:
                if self._stop_after_current:
                    break
                job = self._next_queued_job()
                if not job:
                    break
                run_next_job(job)
        finally:
            status = read_json(config.LIVE_STATUS_FILE, {})
            if not isinstance(status, dict):
                status = {}
            status.update({"schema_version": config.SCHEMA_VERSION, "phase": "IDLE", "updated_at": now_iso()})
            try:
                write_json(config.LIVE_STATUS_FILE, status)
            except OSError:
                pass
            self._stop_after_current = False
