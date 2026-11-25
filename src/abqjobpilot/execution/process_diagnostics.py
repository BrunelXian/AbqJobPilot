"""Bounded, non-authoritative diagnostics for fixed ProcessFixture failures."""

import json
import os
import re
import sqlite3

from .models import ExecutionError, now


DIAGNOSTIC_FORMAT = "process-fixture-failure-diagnostic-v1"
DIAGNOSTIC_NAME = "failure-diagnostic.json"
MAX_DIAGNOSTIC_BYTES = 4096

# Stage names and categories are source-controlled. Never put exception text,
# paths, command lines, credentials, or tokens in this sidecar.
STAGE_CATEGORY = {
    "fixture_config_verify": "identity",
    "run_directory_resolve": "filesystem",
    "run_directory_create": "filesystem",
    "fixture_manifest_write": "filesystem",
    "pre_create_checkpoint": "test_orchestration",
    "execution_checkpoint": "test_orchestration",
    "start_authorization": "authorization",
    "fixture_environment_prepare": "environment",
    "fixture_role_entry": "identity",
    "fixture_role_launch": "windows_process",
    "managed_scope_create": "windows_native",
    "managed_scope_record_prepared": "store_event",
    "managed_root_create": "windows_native",
    "managed_root_query": "windows_native",
    "managed_root_record": "store_event",
    "direct_process_identity_open": "windows_native",
    "direct_process_identity_validate": "identity",
    "post_create_checkpoint": "test_orchestration",
    "role_handshake_wait": "filesystem",
    "role_handshake_read": "filesystem",
    "role_handshake_parse": "filesystem",
    "role_handshake_binding": "identity",
    "role_process_identity_open": "windows_native",
    "role_image_validate": "identity",
    "role_parent_validate": "identity",
    "role_exit_probe": "windows_native",
    "process_identities_record": "store_event",
    "process_identity_checkpoint": "test_orchestration",
    "owner_binding_write": "filesystem",
    "owner_handoff_checkpoint": "test_orchestration",
    "process_exit_observe": "windows_native",
    "process_exit_record": "store_event",
    "managed_scope_query": "windows_native",
    "managed_scope_observation_record": "store_event",
    "process_completion_record": "store_event",
    "process_handle_close": "windows_native",
    "managed_scope_close": "windows_native",
}

_SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SAFE_EXECUTION_CODES = frozenset({
    "HOST_UNCONFIRMED", "INVALID_REQUEST", "RESOURCE_LIMIT", "PLAN_STALE",
    "MANAGED_SCOPE_UNAVAILABLE", "MANAGED_SCOPE_UNKNOWN", "MANAGED_SCOPE_POLICY_CHANGED",
    "PROCESS_IDENTITY_UNKNOWN", "PROCESS_IDENTITY_MISMATCH", "PROCESS_EXIT_UNKNOWN",
    "START_WINDOW_EXPIRED", "START_ALREADY_ATTEMPTED", "START_NOT_AUTHORIZED",
    "START_NOT_ACCEPTED", "PROCESS_IO_FAILURE", "EVIDENCE_WRITE_FAILED",
    "STORE_UNAVAILABLE", "ACCEPTANCE_UNKNOWN", "STATE_CONFLICT",
})
_SAFE_EXCEPTION_CLASSES = frozenset({
    "ExecutionError", "OSError", "PermissionError", "FileNotFoundError",
    "TimeoutError", "ValueError", "TypeError", "JSONDecodeError",
    "OperationalError", "IntegrityError", "DatabaseError", "RuntimeError",
})
_SAFE_NATIVE_OPERATION = frozenset({
    "OpenProcess", "GetProcessTimes", "QueryFullProcessImageNameW",
    "WaitForSingleObject", "GetExitCodeProcess",
})


def failure_record(run, stage, exc):
    """Build a bounded record containing only fixed fields and safe scalars."""
    if stage not in STAGE_CATEGORY:
        raise ValueError("unknown diagnostic stage")
    if isinstance(exc, ExecutionError):
        error_code = exc.code if isinstance(exc.code, str) and exc.code in _SAFE_EXECUTION_CODES else "EXECUTION_ERROR"
    elif isinstance(exc, OSError):
        error_code = "OS_ERROR"
    elif isinstance(exc, sqlite3.Error):
        error_code = "SQLITE_ERROR"
    else:
        error_code = "UNEXPECTED_ERROR"
    category = STAGE_CATEGORY[stage]
    if isinstance(exc, ExecutionError) and exc.code == "PROCESS_IDENTITY_MISMATCH":
        category = "identity"
    record = {
        "format": DIAGNOSTIC_FORMAT,
        "project_instance_id": run["project_instance_id"],
        "run_id": run["run_id"],
        "plan_id": run["plan_id"],
        "plan_digest": run["plan_digest"],
        "phase_attempt_id": run["phase_attempt_id"],
        "owner_id": run["owner_id"],
        "owner_epoch": run["owner_epoch"],
        "recorded_at": now(),
        "stage": stage,
        "category": category,
        "exception_class": (type(exc).__name__ if type(exc).__name__ in _SAFE_EXCEPTION_CLASSES
                            else "OTHER_EXCEPTION"),
        "error_code": error_code,
    }
    for key in ("errno", "winerror"):
        value = getattr(exc, key, None)
        if type(value) is int and 0 <= value <= 0xFFFFFFFF:
            record[key] = value
    native_operation = getattr(exc, "native_operation", None)
    if native_operation in _SAFE_NATIVE_OPERATION:
        record["native_operation"] = native_operation
    if isinstance(exc, sqlite3.Error):
        sqlite_code = getattr(exc, "sqlite_errorcode", None)
        sqlite_name = getattr(exc, "sqlite_errorname", None)
        if type(sqlite_code) is int and 0 <= sqlite_code <= 0xFFFFFFFF:
            record["sqlite_errorcode"] = sqlite_code
        if isinstance(sqlite_name, str) and _SAFE_CODE.fullmatch(sqlite_name):
            record["sqlite_errorname"] = sqlite_name
    cause = exc.__cause__
    if cause is not None and cause is not exc and isinstance(cause, (OSError, sqlite3.Error)):
        record['cause'] = {'exception_class': type(cause).__name__ if type(cause).__name__ in _SAFE_EXCEPTION_CLASSES else 'OTHER_EXCEPTION'}
        for key in ('errno', 'winerror', 'sqlite_errorcode'):
            value = getattr(cause, key, None)
            if type(value) is int and 0 <= value <= 0xFFFFFFFF:
                record['cause'][key] = value
    payload = (json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
    if len(payload) > MAX_DIAGNOSTIC_BYTES:
        raise ValueError("diagnostic exceeds bound")
    return record


def write_failure_record(path, record):
    """Create one diagnostic sidecar without replacing an existing file."""
    payload = (json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
    if len(payload) > MAX_DIAGNOSTIC_BYTES:
        raise ValueError("diagnostic exceeds bound")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def try_write_failure_record(path, run, stage, exc):
    """Best effort only: diagnostics must never change the execution outcome."""
    try:
        write_failure_record(path, failure_record(run, stage, exc))
        return True
    except Exception:
        return False
