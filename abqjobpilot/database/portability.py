"""Rebase only project-owned indexed paths in an archive DB snapshot."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path, PurePosixPath

from .connection import DatabaseFailure, inspect_schema_version, open_connection
from .repository import _logical_key


PREFIX = "project://"
PATH_COLUMNS = {"jobs": ("inp_path",), "runs": ("working_dir", "expected_odb_path"),
                "artifacts": ("path",)}
IDENTITIES = {"jobs": "job_id", "runs": "run_id", "artifacts": "artifact_id"}


def _relative_marker(value: str | None, root: Path) -> str | None:
    if not value:
        return value
    path = Path(value)
    path = (path if path.is_absolute() else root / path).resolve()
    try:
        return PREFIX + path.relative_to(root).as_posix()
    except ValueError:
        return value


def _restored_path(value: str | None, root: Path) -> str | None:
    if not value or not value.startswith(PREFIX):
        return value
    relative = value[len(PREFIX):]
    parts = PurePosixPath(relative)
    if not relative or "\\" in relative or parts.is_absolute() or ".." in parts.parts:
        raise DatabaseFailure("DATABASE_MIGRATION_FAILED", f"Unsafe archived database path: {value}")
    target = root.joinpath(*parts.parts).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise DatabaseFailure("DATABASE_MIGRATION_FAILED", f"Archived database path escapes Project: {value}") from exc
    return str(target)


def _rewrite_paths(connection: sqlite3.Connection, root: Path, converter) -> None:
    for table, columns in PATH_COLUMNS.items():
        identity = IDENTITIES[table]
        rows = connection.execute(f"SELECT {identity}, {', '.join(columns)} FROM {table}").fetchall()
        for row in rows:
            values = [converter(row[column], root) for column in columns]
            clauses = ", ".join(f"{column} = ?" for column in columns)
            connection.execute(f"UPDATE {table} SET {clauses} WHERE {identity} = ?", (*values, row[identity]))


def portabilize_database_snapshot(path: str | Path, project_root: str | Path) -> None:
    if inspect_schema_version(path) == 0:
        return
    root = Path(project_root).resolve()
    with closing(open_connection(path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            _rewrite_paths(connection, root, _relative_marker)
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def restore_database_snapshot(path: str | Path, destination_root: str | Path,
                              project_id: str) -> None:
    if inspect_schema_version(path) == 0:
        return
    root = Path(destination_root).resolve()
    with closing(open_connection(path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            _rewrite_paths(connection, root, _restored_path)
            rows = connection.execute("SELECT job_id, job_name, inp_path, logical_key FROM jobs").fetchall()
            for row in rows:
                fallback = connection.execute(
                    "SELECT queue_id, working_dir FROM runs WHERE job_id = ? ORDER BY attempt_no LIMIT 1",
                    (row["job_id"],),
                ).fetchone()
                key, _basis = _logical_key(row["job_name"], row["inp_path"],
                                            fallback["working_dir"] if fallback else None,
                                            fallback["queue_id"] if fallback else None)
                connection.execute("UPDATE jobs SET project_id = ?, logical_key = ? WHERE job_id = ?",
                                   (project_id, key, row["job_id"]))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
