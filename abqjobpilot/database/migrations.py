"""Explicit, transactional schema migrations."""

from __future__ import annotations

import sqlite3

from .schema import SCHEMA_V1


SCHEMA_VERSION = 1


class DatabaseFailure(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def get_schema_version(connection: sqlite3.Connection) -> int:
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )}
    if "schema_meta" not in tables:
        if tables:
            raise DatabaseFailure("DATABASE_MIGRATION_FAILED", "Unversioned database contains unknown user tables")
        return 0
    row = connection.execute("SELECT value FROM schema_meta WHERE key = ?", ("schema_version",)).fetchone()
    if row is None:
        raise DatabaseFailure("DATABASE_MIGRATION_FAILED", "schema_meta has no schema_version")
    try:
        return int(row[0])
    except (TypeError, ValueError) as exc:
        raise DatabaseFailure("DATABASE_MIGRATION_FAILED", "Invalid database schema_version") from exc


def set_schema_version(connection: sqlite3.Connection, version: int) -> None:
    connection.execute(
        "INSERT INTO schema_meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("schema_version", str(version)),
    )


def initialize_database(connection: sqlite3.Connection) -> int:
    try:
        version = get_schema_version(connection)
        if version > SCHEMA_VERSION:
            raise DatabaseFailure("UNSUPPORTED_DATABASE_SCHEMA", f"Database schema {version} is newer than supported {SCHEMA_VERSION}")
        if version < 0:
            raise DatabaseFailure("DATABASE_MIGRATION_FAILED", f"Invalid database schema {version}")
        if version == SCHEMA_VERSION:
            return version
        if version != 0:
            raise DatabaseFailure("DATABASE_MIGRATION_FAILED", f"No migration from database schema {version}")
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in SCHEMA_V1:
                connection.execute(statement)
            set_schema_version(connection, SCHEMA_VERSION)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return SCHEMA_VERSION
    except DatabaseFailure:
        raise
    except sqlite3.Error as exc:
        raise DatabaseFailure("DATABASE_MIGRATION_FAILED", f"Database migration failed: {exc}") from exc
