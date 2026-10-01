"""SQLite connection, schema inspection, and online-safe backup."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .migrations import SCHEMA_VERSION, DatabaseFailure, get_schema_version, initialize_database


def open_connection(path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    target = Path(path).expanduser().resolve()
    if read_only and not target.is_file():
        raise DatabaseFailure("DATABASE_OPEN_FAILED", f"Database does not exist: {target}")
    connection = None
    try:
        connection = sqlite3.connect(f"{target.as_uri()}?mode=ro" if read_only else str(target),
                                     uri=read_only, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
    except sqlite3.Error as exc:
        if connection is not None:
            connection.close()
        raise DatabaseFailure("DATABASE_OPEN_FAILED", f"Could not open database {target}: {exc}") from exc


def inspect_schema_version(path: str | Path) -> int:
    with closing(open_connection(path, read_only=True)) as connection:
        try:
            version = get_schema_version(connection)
        except sqlite3.Error as exc:
            raise DatabaseFailure("DATABASE_READ_FAILED", f"Could not read database schema: {exc}") from exc
        if version > SCHEMA_VERSION:
            raise DatabaseFailure("UNSUPPORTED_DATABASE_SCHEMA", f"Database schema {version} is newer than supported {SCHEMA_VERSION}")
        if version < 0:
            raise DatabaseFailure("DATABASE_MIGRATION_FAILED", f"Invalid database schema {version}")
        return version


def backup_database(source_path: str | Path, destination_path: str | Path) -> Path:
    source = Path(source_path).expanduser().resolve()
    destination = Path(destination_path).expanduser().resolve()
    if not destination.parent.is_dir():
        raise DatabaseFailure("DATABASE_OPEN_FAILED", f"Backup parent directory does not exist: {destination.parent}")
    if not source.is_file():
        raise DatabaseFailure("DATABASE_OPEN_FAILED", f"Source database does not exist: {source}")
    inspect_schema_version(source)
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with closing(open_connection(source, read_only=True)) as origin, closing(open_connection(destination)) as backup:
            origin.backup(backup)
        return destination
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def ensure_project_database(path: str | Path) -> int:
    with closing(open_connection(path)) as connection:
        return initialize_database(connection)


__all__ = ["DatabaseFailure", "open_connection", "inspect_schema_version", "backup_database",
           "ensure_project_database", "initialize_database"]
