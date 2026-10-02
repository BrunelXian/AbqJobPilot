"""Small parameterized repository for Project/Job/Run/artifact metadata."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from abqjobpilot.status_codes import normalize_status
from abqjobpilot.project.manager import load_project_info
from abqjobpilot.project.models import ProjectInfo

from .connection import DatabaseFailure, open_connection, inspect_schema_version
from .migrations import SCHEMA_VERSION, initialize_database


ARTIFACT_FIELDS = {"INP": "inp_path", "ODB": "odb_path", "STA": "sta_path",
                   "MSG": "msg_path", "DAT": "dat_path", "LOG": "log_path"}
TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED", "SKIPPED", "ODB_MISSING"})


def _as_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def _logical_key(job_name: str | None, inp_path: str | None, work_dir: str | None,
                 queue_id: str | None) -> tuple[str, str]:
    if inp_path:
        basis = "inp_path"
        location = os.path.normcase(str(Path(inp_path).expanduser().resolve()))
    elif work_dir and job_name:
        basis = "work_dir"
        location = os.path.normcase(str(Path(work_dir).expanduser().resolve()))
    elif queue_id:
        basis = "queue_id_fallback"
        location = queue_id
    else:
        raise DatabaseFailure("DATABASE_WRITE_FAILED", "Job needs inp_path or work_dir/job_name or queue_id")
    serialized = json.dumps([basis, location, (job_name or "").casefold()], ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest(), basis


class ProjectHistoryRepository:
    def __init__(self, project: ProjectInfo | str | Path, *, read_only: bool = False):
        self.project = project if isinstance(project, ProjectInfo) else load_project_info(project)
        self.db_path = self.project.root / "project.db"
        self.read_only = read_only

    @contextmanager
    def _connection(self, write: bool = False):
        if self.read_only and write:
            raise DatabaseFailure("DATABASE_WRITE_FAILED", "Read-only history cannot be modified")
        if self.read_only and inspect_schema_version(self.db_path) != SCHEMA_VERSION:
            raise DatabaseFailure("DATABASE_READ_FAILED", "Project database has not been initialized")
        connection = open_connection(self.db_path, read_only=self.read_only)
        try:
            if not self.read_only:
                initialize_database(connection)
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except DatabaseFailure:
            if write:
                connection.rollback()
            raise
        except sqlite3.Error as exc:
            if write:
                connection.rollback()
            code = "DATABASE_WRITE_FAILED" if write else "DATABASE_READ_FAILED"
            raise DatabaseFailure(code, f"Project database operation failed: {exc}") from exc
        except Exception:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> int:
        with self._connection() as connection:
            return int(connection.execute("SELECT value FROM schema_meta WHERE key = ?",
                                          ("schema_version",)).fetchone()[0])

    def _get_or_create_job(self, connection: sqlite3.Connection, *, job_name: str | None,
                           inp_path: str | None, queue_id: str | None = None,
                           work_dir: str | None = None, batch: str | None = None,
                           strategy: str | None = None, created_at: str | None = None,
                           updated_at: str | None = None, metadata: dict | None = None) -> dict:
        key, basis = _logical_key(job_name, inp_path, work_dir, queue_id)
        row = connection.execute("SELECT * FROM jobs WHERE project_id = ? AND logical_key = ?",
                                 (self.project.project_id, key)).fetchone()
        if row:
            return dict(row)
        job_id = "j_" + uuid.uuid4().hex
        content = dict(metadata or {})
        content.setdefault("identity_basis", basis)
        connection.execute(
            "INSERT INTO jobs(job_id, project_id, logical_key, job_name, inp_path, batch, strategy, "
            "created_at, updated_at, metadata_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, self.project.project_id, key, job_name, inp_path, batch, strategy,
             created_at, updated_at, json.dumps(content, ensure_ascii=False)),
        )
        return dict(connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone())

    def get_or_create_job(self, *, job_name: str | None, inp_path: str | None,
                          queue_id: str | None = None, work_dir: str | None = None,
                          batch: str | None = None, strategy: str | None = None,
                          created_at: str | None = None, updated_at: str | None = None,
                          metadata: dict | None = None) -> dict:
        with self._connection(write=True) as connection:
            return self._get_or_create_job(connection, job_name=job_name, inp_path=inp_path,
                                           queue_id=queue_id, work_dir=work_dir, batch=batch,
                                           strategy=strategy, created_at=created_at,
                                           updated_at=updated_at, metadata=metadata)

    def _create_run(self, connection: sqlite3.Connection, job_id: str, *, queue_id: str | None = None,
                    status: str = "QUEUED", raw_status: str | None = None,
                    cpus: int | None = None, gpus: int | None = None,
                    working_dir: str | None = None, expected_odb_path: str | None = None,
                    created_at: str | None = None, started_at: str | None = None,
                    completed_at: str | None = None, exit_reason: str | None = None,
                    error_code: str | None = None, metadata: dict | None = None) -> dict:
        if queue_id:
            existing = connection.execute("SELECT * FROM runs WHERE queue_id = ?", (queue_id,)).fetchone()
            if existing:
                if existing["job_id"] != job_id:
                    raise DatabaseFailure("DATABASE_WRITE_FAILED", "queue_id already belongs to another logical Job")
                return dict(existing)
        job = connection.execute("SELECT job_id FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if job is None:
            raise DatabaseFailure("JOB_NOT_FOUND", f"Logical Job was not found: {job_id}")
        attempt = connection.execute("SELECT COALESCE(MAX(attempt_no), 0) + 1 FROM runs WHERE job_id = ?",
                                     (job_id,)).fetchone()[0]
        run_id = "r_" + uuid.uuid4().hex
        connection.execute(
            "INSERT INTO runs(run_id, job_id, attempt_no, queue_id, status, raw_status, cpus, gpus, "
            "working_dir, expected_odb_path, created_at, started_at, completed_at, exit_reason, error_code, metadata_json) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, job_id, attempt, queue_id, normalize_status(status), raw_status, cpus, gpus,
             working_dir, expected_odb_path, created_at, started_at, completed_at, exit_reason,
             error_code, json.dumps(metadata or {}, ensure_ascii=False)),
        )
        return dict(connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone())

    def create_run(self, job_id: str, **kwargs) -> dict:
        with self._connection(write=True) as connection:
            return self._create_run(connection, job_id, **kwargs)

    def update_run_status(self, run_id: str, status: str, *, raw_status: str | None = None,
                          started_at: str | None = None, completed_at: str | None = None,
                          exit_reason: str | None = None, error_code: str | None = None) -> dict:
        with self._connection(write=True) as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise DatabaseFailure("RUN_NOT_FOUND", f"Run was not found: {run_id}")
            normalized = normalize_status(status)
            if row["status"] in TERMINAL_STATUSES and row["status"] != normalized:
                return dict(row)
            connection.execute(
                "UPDATE runs SET status = ?, raw_status = COALESCE(?, raw_status), "
                "started_at = COALESCE(?, started_at), completed_at = COALESCE(?, completed_at), "
                "exit_reason = COALESCE(?, exit_reason), error_code = COALESCE(?, error_code) "
                "WHERE run_id = ?",
                (normalized, raw_status, started_at, completed_at, exit_reason, error_code, run_id),
            )
            return dict(connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone())

    def complete_run(self, run_id: str, status: str, *, completed_at: str | None = None,
                     exit_reason: str | None = None, error_code: str | None = None) -> dict:
        normalized = normalize_status(status)
        if normalized not in TERMINAL_STATUSES:
            raise ValueError("complete_run requires a terminal status")
        return self.update_run_status(run_id, normalized, completed_at=completed_at,
                                      exit_reason=exit_reason, error_code=error_code)

    def _add_or_update_artifact(self, connection: sqlite3.Connection, run_id: str, kind: str,
                                path: str, *, exists_flag: bool, size_bytes: int | None = None,
                                mtime_ns: int | None = None, metadata: dict | None = None) -> dict:
        kind = kind.upper()
        if kind not in ARTIFACT_FIELDS or not path:
            raise ValueError("Unsupported artifact kind or empty path")
        artifact_id = "a_" + uuid.uuid4().hex
        connection.execute(
            "INSERT INTO artifacts(artifact_id, run_id, kind, path, exists_flag, size_bytes, mtime_ns, metadata_json) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(run_id, kind, path) DO UPDATE SET "
            "exists_flag = excluded.exists_flag, size_bytes = excluded.size_bytes, "
            "mtime_ns = excluded.mtime_ns, metadata_json = excluded.metadata_json",
            (artifact_id, run_id, kind, path, int(bool(exists_flag)), size_bytes, mtime_ns,
             json.dumps(metadata or {}, ensure_ascii=False)),
        )
        return dict(connection.execute("SELECT * FROM artifacts WHERE run_id = ? AND kind = ? AND path = ?",
                                       (run_id, kind, path)).fetchone())

    def add_or_update_artifact(self, run_id: str, kind: str, path: str, **kwargs) -> dict:
        with self._connection(write=True) as connection:
            return self._add_or_update_artifact(connection, run_id, kind, path, **kwargs)

    def list_jobs(self) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT jobs.*, (SELECT status FROM runs WHERE runs.job_id = jobs.job_id "
                "ORDER BY attempt_no DESC LIMIT 1) AS latest_status FROM jobs "
                "WHERE project_id = ? ORDER BY COALESCE(updated_at, created_at, '') DESC, job_name",
                (self.project.project_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_runs(self, job_id: str) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM runs WHERE job_id = ? ORDER BY attempt_no DESC", (job_id,)).fetchall()
            return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict | None:
        with self._connection() as connection:
            return _as_dict(connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone())

    def find_job_by_queue_id(self, queue_id: str) -> dict | None:
        with self._connection() as connection:
            return _as_dict(connection.execute(
                "SELECT jobs.* FROM jobs JOIN runs ON runs.job_id = jobs.job_id WHERE runs.queue_id = ?",
                (queue_id,),
            ).fetchone())

    def latest_completed_run(self, job_id: str) -> dict | None:
        with self._connection() as connection:
            return _as_dict(connection.execute(
                "SELECT * FROM runs WHERE job_id = ? AND status = ? ORDER BY attempt_no DESC LIMIT 1",
                (job_id, "COMPLETED"),
            ).fetchone())

    def list_artifacts(self, run_id: str) -> list[dict]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY kind, path", (run_id,),
            ).fetchall()]

    def sync_records(self, records: list[dict], *, provenance: str = "runtime_json") -> dict[str, int]:
        """Project runtime is authoritative; this only inserts/updates its historical projection."""
        counts = {"seen": 0, "created_runs": 0, "skipped_missing_queue_id": 0}
        with self._connection(write=True) as connection:
            for record in records:
                if not isinstance(record, dict):
                    continue
                queue_id = record.get("queue_id")
                if not isinstance(queue_id, str) or not queue_id:
                    counts["skipped_missing_queue_id"] += 1
                    continue
                counts["seen"] += 1
                job = self._get_or_create_job(
                    connection, job_name=record.get("job_name"), inp_path=record.get("inp_path"),
                    work_dir=record.get("work_dir"), queue_id=queue_id,
                    batch=record.get("batch_name"), strategy=record.get("strategy_name"),
                    created_at=record.get("created_at"), updated_at=record.get("ended_at"),
                    metadata={"source": provenance},
                )
                existing = connection.execute("SELECT * FROM runs WHERE queue_id = ?", (queue_id,)).fetchone()
                raw_status = record.get("status") or record.get("phase")
                canonical = normalize_status(raw_status)
                if existing is None:
                    run = self._create_run(
                        connection, job["job_id"], queue_id=queue_id, status=canonical, raw_status=raw_status,
                        cpus=record.get("cpus"), gpus=record.get("gpus"),
                        working_dir=record.get("work_dir"), expected_odb_path=record.get("odb_path"),
                        created_at=record.get("created_at"), started_at=record.get("started_at"),
                        completed_at=record.get("ended_at"), exit_reason=record.get("fatal_reason"),
                        metadata={"source": provenance},
                    )
                    counts["created_runs"] += 1
                else:
                    if existing["job_id"] != job["job_id"]:
                        raise DatabaseFailure("DATABASE_WRITE_FAILED", "queue_id maps to conflicting logical Jobs")
                    run = dict(existing)
                    if existing["status"] not in TERMINAL_STATUSES or existing["status"] == canonical:
                        connection.execute(
                            "UPDATE runs SET status = ?, raw_status = ?, "
                            "started_at = COALESCE(?, started_at), completed_at = COALESCE(?, completed_at), "
                            "exit_reason = COALESCE(?, exit_reason) WHERE run_id = ?",
                            (canonical, raw_status, record.get("started_at"), record.get("ended_at"),
                             record.get("fatal_reason"), run["run_id"]),
                        )
                for kind, field in ARTIFACT_FIELDS.items():
                    path = record.get(field)
                    if not isinstance(path, str) or not path:
                        continue
                    try:
                        stat_result = Path(path).stat()
                        exists_flag = Path(path).is_file()
                    except OSError:
                        stat_result = None
                        exists_flag = False
                    self._add_or_update_artifact(
                        connection, run["run_id"], kind, path, exists_flag=exists_flag,
                        size_bytes=stat_result.st_size if stat_result and exists_flag else None,
                        mtime_ns=stat_result.st_mtime_ns if stat_result and exists_flag else None,
                    )
        return counts
