"""Public lifecycle status normalization over persisted legacy status values."""

from __future__ import annotations


PUBLIC_STATUSES = frozenset({
    "QUEUED", "DATACHECK", "RUNNING", "COMPLETED", "FAILED",
    "CANCELLED", "SKIPPED", "LOCKED", "ODB_MISSING", "UNKNOWN",
})


def normalize_status(value: str | None, *, lock_exists: bool = False, odb_exists: bool | None = None) -> str:
    raw = str(value or "").upper()
    if lock_exists and raw not in {"COMPLETED_OK", "COMPLETED_WITH_WARNINGS", "COMPLETED"}:
        return "LOCKED"
    if raw in {"QUEUED", "DATACHECK_OK"}:
        return "QUEUED"
    if raw in {"DATACHECK_RUNNING", "FULL_RUNNING", "RUNNER_ACTIVE", "STARTED", "RUNNING"}:
        return "RUNNING"
    if raw in {"COMPLETED_OK", "COMPLETED_WITH_WARNINGS", "COMPLETED"}:
        return "ODB_MISSING" if odb_exists is False else "COMPLETED"
    if raw in {"CANCELLED", "SKIPPED"}:
        return raw
    if raw.startswith(("FAILED", "DATACHECK_FAILED")):
        return "FAILED"
    if raw in PUBLIC_STATUSES:
        return raw
    return "UNKNOWN"
