"""Conservative, locally approved metadata recovery for one interrupted run.

This module is intentionally absent from the public API and MCP surface.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .queue_store import read_queue, save_queue
from .process_identity import verify_launch_evidence
from .recovery_assessment import RUNNING_STATUSES, assess_runtime
from .runtime_coordination import queue_transaction, runtime_path
from .utils import now_iso, write_json


LIVE_RUNNING = RUNNING_STATUSES | {"RUNNER_ACTIVE"}
INTERRUPTED = "UNKNOWN_INTERRUPTED"
_APPROVALS: dict[str, tuple[str, float]] = {}


def probe_solver_processes() -> dict:
    """Fail closed if Windows process enumeration is unavailable or ambiguous."""
    if sys.platform != "win32":
        return {"state": "UNKNOWN", "reason": "Windows tasklist is unavailable"}
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                                text=True, timeout=5, creationflags=flags, shell=False)
        if result.returncode:
            return {"state": "UNKNOWN", "reason": "tasklist failed"}
        rows = list(csv.reader(io.StringIO(result.stdout)))
        if not rows or any(len(row) < 2 for row in rows):
            return {"state": "UNKNOWN", "reason": "tasklist output was not usable"}
        names = [row[0].strip().lower() for row in rows]
        matches = [name for name in names if name.startswith("abq") or name in
                   {"standard.exe", "explicit.exe", "pre.exe", "package.exe"}]
        return {"state": "PRESENT" if matches else "CLEAR", "matches": matches}
    except (OSError, subprocess.TimeoutExpired, csv.Error, UnicodeError):
        return {"state": "UNKNOWN", "reason": "process enumeration failed"}


def _read_live(runtime: Path) -> dict | None:
    path = runtime / "live_status.json"
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("live_status.json must be an object")
    return value


def _file_signature(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False}
    stat = path.stat()
    # Only queue/live metadata is hashed; solver artifacts are never read.
    if path.name in {"queue.json", "live_status.json", "runner_owner.json"}:
        return {"exists": True, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {"exists": True, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _fingerprint(runtime: Path, db: Path | None, assessment: dict) -> str:
    paths = [runtime / "queue.json", runtime / "live_status.json", runtime / "runner_owner.json",
             runtime / ".runner.lock"]
    if db is not None:
        paths.append(db)
        paths.append(db.with_name(db.name + "-wal"))
    live = _read_live(runtime)
    operation_id = live.get("recovery_operation_id") if live else None
    if isinstance(operation_id, str) and len(operation_id) == 32 and all(c in "0123456789abcdef" for c in operation_id):
        paths.append(runtime / "recovery_audit" / f"{operation_id}.json")
    for job in read_queue(runtime, strict=True):
        if job.get("status") in RUNNING_STATUSES | {INTERRUPTED}:
            work = job.get("work_dir")
            name = job.get("job_name")
            if work and name:
                paths.extend((Path(work) / f"{name}.lck", Path(job.get("odb_path") or Path(work) / f"{name}.odb")))
    data = {"files": [(str(path), _file_signature(path)) for path in paths],
            "owner": assessment["owner"]}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RecoveryPlan:
    runtime_dir: str
    project_db: str | None
    assessment: dict
    fingerprint: str
    process_fingerprint: str
    affected_queue_ids: tuple[str, ...]
    transitions: tuple[dict, ...]
    warnings: tuple[str, ...]
    unresolved: tuple[str, ...]
    can_apply: bool
    plan_id: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


def build_recovery_plan(runtime_dir: str | Path, *, project_db: str | Path | None = None,
                        process_probe: Callable[[], dict] = probe_solver_processes,
                        identity_probe: Callable[[dict | None], dict] | None = None) -> RecoveryPlan:
    """Inspect without writing, opening SQLite for write, or opening solver files."""
    runtime = runtime_path(runtime_dir)
    db = Path(project_db).expanduser().resolve() if project_db is not None else None
    assessment = assess_runtime(runtime, project_db=db)
    warnings: list[str] = []
    unresolved: list[str] = list(assessment["errors"])
    transitions: list[dict] = []
    affected: list[str] = []
    try:
        jobs = read_queue(runtime, strict=True)
        live = _read_live(runtime)
        fingerprint = _fingerprint(runtime, db, assessment)
    except (OSError, ValueError, TypeError) as exc:
        jobs, live, fingerprint = [], None, ""
        unresolved.append(f"Runtime metadata cannot be read: {exc}")
    probe = process_probe()
    identity_record = live.get("process_identity") if isinstance(live, dict) else None
    identity = (identity_probe or verify_launch_evidence)(identity_record)
    process_fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
    assessment = {**assessment, "solver_process": probe, "process_evidence": identity}
    if assessment["owner"]["state"] not in {"ABSENT", "STALE"}:
        unresolved.append("Runner ownership is active or unconfirmed")
    if probe.get("state") != "CLEAR":
        unresolved.append("Solver process absence is not established")
    if identity_record is not None and (not isinstance(identity_record, dict)
                                        or identity_record.get("runtime_dir") != str(runtime)):
        unresolved.append("Process identity belongs to another runtime or is malformed")
    if identity["state"] != "CONFIRMED_EXITED" and (assessment["running_queue_ids"] or
                                                       (live and live.get("phase") in LIVE_RUNNING)):
        unresolved.append(f"Tracked launcher/solver exit is not established: {identity['state']}")
    if assessment["lock_files"]:
        unresolved.append("A solver .lck file exists; never remove it automatically")
    if assessment.get("report_terminal_evidence"):
        unresolved.append("A matching terminal report exists; preserve it and investigate before correction")
    if db is not None and db.is_file():
        try:
            from .database.connection import inspect_schema_version
            from .database.migrations import SCHEMA_VERSION
            if inspect_schema_version(db) != SCHEMA_VERSION:
                unresolved.append("Project database needs a separate schema migration before recovery")
        except Exception as exc:
            unresolved.append(f"Project database schema cannot be safely verified: {exc}")
    conflicting_history = [item for item in assessment["history_disagreements"]
                           if not (item["queue_status"] == INTERRUPTED
                                   and item["history_status"] in RUNNING_STATUSES)]
    if conflicting_history:
        unresolved.append("SQLite history disagrees with queue metadata; investigate before correction")
    if len([job for job in jobs if job.get("status") in RUNNING_STATUSES]) > 1:
        unresolved.append("Multiple running queue records require manual investigation")
    if live and live.get("phase") in LIVE_RUNNING:
        queue_id = live.get("queue_id")
        if not isinstance(identity_record, dict) or (identity_record.get("queue_id") != queue_id
                                                     or identity_record.get("phase") != live.get("phase")):
            unresolved.append("Process identity does not match the current queue ID and phase")
        match = [job for job in jobs if job.get("queue_id") == queue_id]
        if (len(match) == 1 and match[0].get("status") in RUNNING_STATUSES | {INTERRUPTED}
                and (live.get("phase") == match[0].get("status") or match[0].get("status") == INTERRUPTED)
                and isinstance(live.get("return_code"), int) and not isinstance(live.get("return_code"), bool)
                and live.get("started_at") and live.get("started_at") == match[0].get("started_at")
                and queue_id and len([job for job in jobs if job.get("status") in RUNNING_STATUSES]) <= 1):
            affected.append(queue_id)
            evidence = {"queue_id": queue_id, "phase": live["phase"],
                        "started_at": live["started_at"], "return_code": live["return_code"],
                        "owner_state": assessment["owner"]["state"], "solver_probe": probe["state"]}
            if match[0]["status"] in RUNNING_STATUSES:
                transitions.append({"target": "queue", "queue_id": queue_id, "from": match[0]["status"],
                                    "to": INTERRUPTED, "reason": "Matching runner telemetry recorded command exit, but queue classification was interrupted; outcome remains unknown", "evidence": evidence})
            transitions.append({"target": "live_status", "queue_id": queue_id, "from": live["phase"],
                                "to": "IDLE", "reason": "Clear stale live observation after command exit and owner/process recheck", "evidence": evidence})
            warnings.append("Process listing is a point-in-time check; confirm no detached Abaqus process before approval")
        else:
            unresolved.append("No exact queue/live identity, start time, phase and command-exit evidence match")
    elif any(job.get("status") in RUNNING_STATUSES for job in jobs):
        unresolved.append("Running queue record has no matching command-exit telemetry")
    elif (live and live.get("phase") == "IDLE" and db and db.is_file()
          and len(assessment["history_disagreements"]) == 1):
        disagreement = assessment["history_disagreements"][0]
        queue_id = disagreement["queue_id"]
        operation_id = live.get("recovery_operation_id")
        matching = [job for job in jobs if job.get("queue_id") == queue_id and job.get("status") == INTERRUPTED]
        if (isinstance(operation_id, str) and len(operation_id) == 32
                and all(c in "0123456789abcdef" for c in operation_id)
                and disagreement["history_status"] in RUNNING_STATUSES and len(matching) == 1
                and isinstance(identity_record, dict) and identity_record.get("queue_id") == queue_id):
            try:
                audit = json.loads((runtime / "recovery_audit" / f"{operation_id}.json").read_text(encoding="utf-8"))
                if (audit.get("runtime_dir") == str(runtime)
                        and audit.get("approval_source") == "local_gui_confirmation"
                        and audit.get("outcome") == "PARTIAL_OR_FAILED"
                        and audit.get("affected_queue_ids") == [queue_id]
                        and {item.get("target") for item in audit.get("transitions", [])} >= {"queue", "live_status"}):
                    affected.append(queue_id)
                    transitions.append({"target": "history", "queue_id": queue_id,
                                        "from": disagreement["history_status"], "to": "UNKNOWN",
                                        "reason": "Retry only the historical projection of a previously approved partial correction",
                                        "evidence": {"prior_operation_id": operation_id, "queue_status": INTERRUPTED}})
                else:
                    unresolved.append("Prior approved recovery audit does not support history-only retry")
            except (OSError, ValueError, TypeError, AttributeError):
                unresolved.append("Prior recovery audit is unavailable or invalid")
    if not transitions and assessment["status"] != "CLEAN":
        unresolved.append("No supported metadata-only transition; manual investigation is required")
    if transitions and identity["state"] != "CONFIRMED_EXITED":
        unresolved.append("Process lineage is not confirmed exited; metadata correction remains blocked")
    can_apply = bool(transitions and not unresolved and fingerprint)
    identity = {"runtime": str(runtime), "database": str(db) if db else None,
                "fingerprint": fingerprint, "process_fingerprint": process_fingerprint,
                "transitions": transitions, "unresolved": unresolved}
    plan_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    return RecoveryPlan(str(runtime), str(db) if db else None, assessment, fingerprint, process_fingerprint,
                        tuple(affected), tuple(transitions), tuple(warnings), tuple(unresolved), can_apply, plan_id)


def approve_local_plan(plan: RecoveryPlan, parent, *, language: str = "en") -> str | None:
    """Issue a one-use token only after a live local Tk confirmation dialog."""
    from tkinter import messagebox

    if not plan.can_apply or parent is None or not parent.winfo_exists():
        return None
    if language == "zh":
        prompt = (f"Runtime：{plan.runtime_dir}\nQueue ID：{', '.join(plan.affected_queue_ids)}\n\n"
                  "仅修正 AbqJobPilot 元数据；不会重启或终止 Abaqus，不会删除工程文件或日志，也不会将未知结果标记为完成。"
                  "请确认没有仍在运行的独立求解器进程。")
        title = "确认运行时元数据修正"
    else:
        prompt = (f"Runtime: {plan.runtime_dir}\nQueue IDs: {', '.join(plan.affected_queue_ids)}\n\n"
                  "Update AbqJobPilot metadata only? This will not restart/terminate Abaqus, delete engineering files "
                  "or logs, or mark an uncertain analysis completed. Confirm no detached solver is running.")
        title = "Confirm Runtime Metadata Correction"
    if not messagebox.askyesno(title, prompt, parent=parent):
        return None
    token = uuid.uuid4().hex
    _APPROVALS[token] = (plan.plan_id, time.monotonic() + 60)
    return token


def apply_approved_recovery(plan: RecoveryPlan, approval_token: str,
                            *, process_probe: Callable[[], dict] = probe_solver_processes,
                            identity_probe: Callable[[dict | None], dict] | None = None) -> dict:
    """Internal, single-use GUI action; not a public API or CLI command."""
    approval = _APPROVALS.pop(approval_token, None)
    if not approval or approval[0] != plan.plan_id or approval[1] < time.monotonic() or not plan.can_apply:
        return {"status": "REJECTED", "error": "Missing, expired or mismatched local approval"}
    runtime = Path(plan.runtime_dir)
    audit_path = runtime / "recovery_audit" / f"{uuid.uuid4().hex}.json"
    result = {"status": "REJECTED", "audit_path": None, "assessment": None}
    try:
        with queue_transaction(runtime):
            current = build_recovery_plan(runtime, project_db=plan.project_db, process_probe=process_probe,
                                          identity_probe=identity_probe)
            if (not current.can_apply or current.plan_id != plan.plan_id
                    or current.fingerprint != plan.fingerprint
                    or current.process_fingerprint != plan.process_fingerprint):
                return {"status": "STALE_PLAN", "error": "Runtime, runner, solver or artifact state changed; refresh assessment"}
            jobs = read_queue(runtime, strict=True)
            live = _read_live(runtime)
            audit = {"operation_id": audit_path.stem, "runtime_dir": plan.runtime_dir,
                     "timestamp": now_iso(), "affected_queue_ids": list(plan.affected_queue_ids),
                     "transitions": list(plan.transitions), "assessment_fingerprint": plan.fingerprint,
                     "process_fingerprint": plan.process_fingerprint,
                     "approval_source": "local_gui_confirmation", "outcome": "PREPARED", "warnings": [], "errors": []}
            write_json(audit_path, audit)
            result["audit_path"] = str(audit_path)
            try:
                for transition in plan.transitions:
                    if transition["target"] == "queue":
                        row = next(job for job in jobs if job.get("queue_id") == transition["queue_id"])
                        row["status"] = INTERRUPTED
                        row["phase"] = INTERRUPTED
                if any(item["target"] == "queue" for item in plan.transitions):
                    save_queue(jobs, runtime_dir=runtime)
                if any(item["target"] == "live_status" for item in plan.transitions):
                    idle = {"schema_version": live.get("schema_version", "1.0"), "phase": "IDLE",
                            "updated_at": now_iso(), "recovery_operation_id": audit_path.stem}
                    if isinstance(live.get("process_identity"), dict):
                        idle["process_identity"] = live["process_identity"]
                    write_json(runtime / "live_status.json", idle)
                if plan.project_db and Path(plan.project_db).is_file():
                    from .database import ProjectHistoryRepository
                    project_root = runtime.parent
                    if (project_root / "project.json").is_file() and (project_root / "project.db").resolve() == Path(plan.project_db).resolve():
                        rows = [job for job in jobs if job.get("queue_id") in plan.affected_queue_ids]
                        ProjectHistoryRepository(project_root).sync_records(rows, provenance="runtime_recovery")
                audit["outcome"] = "APPLIED"
                result["status"] = "APPLIED"
            except Exception as exc:
                audit["outcome"] = "PARTIAL_OR_FAILED"
                audit["errors"].append(f"{type(exc).__name__}: {exc}")
                result.update(status="PARTIAL_OR_FAILED", error=str(exc))
            finally:
                try:
                    write_json(audit_path, audit)
                except OSError as exc:
                    result.update(status="PARTIAL_OR_FAILED", error=f"Audit finalization failed: {exc}")
    except Exception as exc:
        return {"status": "REJECTED", "error": f"Coordination or audit preparation failed: {exc}"}
    result["assessment"] = assess_runtime(runtime, project_db=plan.project_db)
    return result
