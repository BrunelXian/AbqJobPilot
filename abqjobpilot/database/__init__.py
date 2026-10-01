"""Per-project historical metadata; runtime JSON remains authoritative."""

from .connection import DatabaseFailure, backup_database, inspect_schema_version
from .migrations import SCHEMA_VERSION, initialize_database
from .repository import ProjectHistoryRepository
from .reconciliation import sync_history_from_runtime

__all__ = ["DatabaseFailure", "ProjectHistoryRepository", "SCHEMA_VERSION",
           "initialize_database", "inspect_schema_version", "backup_database",
           "sync_history_from_runtime"]
