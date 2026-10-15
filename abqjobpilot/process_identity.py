"""Best-effort Windows process identity, separate from solver completion status.

No process is launched or terminated here. An Abaqus batch launcher can spawn
other processes, so an exited launcher alone is never solver-exit evidence.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path

from .utils import now_iso


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
TH32CS_SNAPPROCESS = 0x00000002
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102
MAX_PATH = 260
SOLVER_NAMES = {"standard.exe", "explicit.exe", "pre.exe", "package.exe"}


class _FILETIME(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                ("module_id", wintypes.DWORD), ("threads", wintypes.DWORD),
                ("parent_pid", wintypes.DWORD), ("priority", wintypes.LONG),
                ("flags", wintypes.DWORD), ("exe", wintypes.WCHAR * MAX_PATH)]


def _kernel32():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    api.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FILETIME),
                                    ctypes.POINTER(_FILETIME), ctypes.POINTER(_FILETIME),
                                    ctypes.POINTER(_FILETIME)]
    api.GetProcessTimes.restype = wintypes.BOOL
    api.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                               wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    api.QueryFullProcessImageNameW.restype = wintypes.BOOL
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    api.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    api.Process32FirstW.restype = wintypes.BOOL
    api.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    api.Process32NextW.restype = wintypes.BOOL
    return api


def inspect_pid(pid: int) -> dict:
    """Read PID, creation FILETIME, executable path and liveness; fail closed."""
    if sys.platform != "win32" or not isinstance(pid, int) or pid <= 0:
        return {"state": "UNCONFIRMED", "reason": "unsupported platform or PID"}
    api = _kernel32()
    handle = api.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        return {"state": "EXITED" if error in {87, 1168} else "UNCONFIRMED",
                "reason": "process absent" if error in {87, 1168} else f"OpenProcess error {error}"}
    try:
        created, exited, kernel, user = (_FILETIME() for _ in range(4))
        if not api.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                   ctypes.byref(kernel), ctypes.byref(user)):
            return {"state": "UNCONFIRMED", "reason": f"GetProcessTimes error {ctypes.get_last_error()}"}
        created_ticks = (created.high << 32) | created.low
        wait = api.WaitForSingleObject(handle, 0)
        if wait == WAIT_OBJECT_0:
            return {"state": "EXITED", "pid": pid, "creation_time_100ns": created_ticks}
        if wait != WAIT_TIMEOUT:
            return {"state": "UNCONFIRMED", "reason": f"WaitForSingleObject result {wait}"}
        size = wintypes.DWORD(32768)
        image = ctypes.create_unicode_buffer(size.value)
        if not api.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
            return {"state": "UNCONFIRMED", "reason": f"QueryFullProcessImageName error {ctypes.get_last_error()}"}
        return {"state": "ACTIVE", "pid": pid,
                "creation_time_100ns": created_ticks,
                "executable_path": image.value}
    finally:
        api.CloseHandle(handle)


def capture_identity(pid: int) -> dict:
    observed = inspect_pid(pid)
    if observed.get("state") != "ACTIVE":
        return {"pid": pid, "identity_status": "UNCONFIRMED", "reason": observed.get("reason", observed["state"])}
    return {"pid": pid, "creation_time_100ns": observed["creation_time_100ns"],
            "executable_path": observed["executable_path"], "identity_status": "CONFIRMED"}


def verify_identity(record: dict) -> dict:
    if (not isinstance(record, dict) or record.get("identity_status") != "CONFIRMED"
            or not isinstance(record.get("pid"), int) or not isinstance(record.get("creation_time_100ns"), int)
            or not isinstance(record.get("executable_path"), str) or not record["executable_path"]):
        return {"state": "UNCONFIRMED", "reason": "incomplete process identity"}
    observed = inspect_pid(record["pid"])
    if observed["state"] == "EXITED":
        if (observed.get("creation_time_100ns") is not None
                and observed["creation_time_100ns"] != record["creation_time_100ns"]):
            return {"state": "IDENTITY_MISMATCH", "pid": record["pid"],
                    "reason": "PID was reused before the observed process exited"}
        return {"state": "CONFIRMED_EXITED", "pid": record["pid"]}
    if observed["state"] != "ACTIVE":
        return {"state": "UNCONFIRMED", "reason": observed.get("reason", "process query failed")}
    if (observed["creation_time_100ns"] != record["creation_time_100ns"]
            or os.path.normcase(observed["executable_path"]) != os.path.normcase(record["executable_path"])):
        return {"state": "IDENTITY_MISMATCH", "pid": record["pid"],
                "reason": "PID was reused or executable identity changed"}
    return {"state": "CONFIRMED_ACTIVE", "pid": record["pid"]}


def _process_snapshot() -> list[dict] | None:
    if sys.platform != "win32":
        return None
    api = _kernel32()
    handle = api.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not handle or handle == ctypes.c_void_p(-1).value:
        return None
    try:
        entry = _PROCESSENTRY32W()
        entry.size = ctypes.sizeof(entry)
        if not api.Process32FirstW(handle, ctypes.byref(entry)):
            return None
        rows = []
        while True:
            rows.append({"pid": int(entry.pid), "parent_pid": int(entry.parent_pid),
                         "exe": str(entry.exe)})
            if not api.Process32NextW(handle, ctypes.byref(entry)):
                break
        return rows
    finally:
        api.CloseHandle(handle)


def observe_descendants(launcher: dict) -> dict:
    """Capture observed descendants; names indicate candidates, not proof."""
    if verify_identity(launcher)["state"] != "CONFIRMED_ACTIVE":
        return {"state": "UNCONFIRMED", "children": []}
    rows = _process_snapshot()
    if rows is None:
        return {"state": "UNCONFIRMED", "children": []}
    parents = {launcher["pid"]}
    known_identities = {launcher["pid"]: launcher}
    descendants = []
    pending = list(rows)
    while pending:
        found = [row for row in pending if row["parent_pid"] in parents and row["pid"] not in parents]
        if not found:
            break
        for row in found:
            pending.remove(row)
            parents.add(row["pid"])
            identity = capture_identity(row["pid"])
            parent = known_identities.get(row["parent_pid"], {})
            identity["parent_pid"] = row["parent_pid"]
            identity["observed_parent_creation_time_100ns"] = parent.get("creation_time_100ns")
            if (identity["identity_status"] == "CONFIRMED"
                    and Path(identity["executable_path"]).name.casefold() != row["exe"].casefold()):
                identity = {"pid": row["pid"], "parent_pid": row["parent_pid"],
                            "observed_parent_creation_time_100ns": parent.get("creation_time_100ns"),
                            "identity_status": "UNCONFIRMED",
                            "reason": "process image changed after the descendant snapshot"}
            identity["role"] = "solver_candidate" if (
                row["exe"].lower() in SOLVER_NAMES or row["exe"].lower().startswith("abq")) else "descendant"
            descendants.append(identity)
            known_identities[row["pid"]] = identity
    launcher_still_active = verify_identity(launcher)["state"] == "CONFIRMED_ACTIVE"
    return {"state": "OK" if launcher_still_active and all(
        child["identity_status"] == "CONFIRMED"
        and isinstance(child.get("observed_parent_creation_time_100ns"), int)
        for child in descendants) else "UNCONFIRMED",
            "children": descendants}


def new_launch_evidence(*, runtime_dir: str, queue_id: str, phase: str, pid: int,
                        command: list[str], working_dir: str, job_name: str) -> dict:
    return {"schema_version": "1.0", "runtime_dir": str(Path(runtime_dir).resolve()),
            "queue_id": queue_id, "phase": phase, "launcher": capture_identity(pid),
            "command_sha256": hashlib.sha256(json.dumps(command, ensure_ascii=False).encode("utf-8")).hexdigest(),
            "working_dir": str(Path(working_dir).resolve()), "job_name": job_name,
            "launched_at": now_iso(), "last_verified_at": now_iso(),
            "observed_children": [], "child_scan_status": "UNCONFIRMED",
            "launcher_exit_observed": False}


def refresh_launch_evidence(evidence: dict) -> dict:
    scan = observe_descendants(evidence["launcher"])
    existing = {(item.get("pid"), item.get("creation_time_100ns")): item
                for item in evidence.get("observed_children", [])}
    for child in scan["children"]:
        existing[(child.get("pid"), child.get("creation_time_100ns"))] = child
    evidence["observed_children"] = list(existing.values())
    evidence["child_scan_status"] = scan["state"]
    evidence["last_verified_at"] = now_iso()
    return evidence


def verify_launch_evidence(evidence: dict | None) -> dict:
    """Describe tracked identities, not an Abaqus analysis success verdict."""
    if (not isinstance(evidence, dict) or not isinstance(evidence.get("launcher"), dict)
            or not isinstance(evidence.get("queue_id"), str)
            or not isinstance(evidence.get("runtime_dir"), str)
            or not isinstance(evidence.get("observed_children"), list)):
        return {"state": "UNCONFIRMED", "reason": "missing or invalid process evidence"}
    launcher = verify_identity(evidence["launcher"])
    children = []
    for child in evidence["observed_children"]:
        if not isinstance(child, dict):
            return {"state": "UNCONFIRMED", "reason": "invalid child identity"}
        if (child.get("role") == "solver_candidate" and
                not isinstance(child.get("executable_path"), str)):
            return {"state": "UNCONFIRMED", "reason": "solver candidate has no executable identity"}
        if child.get("role") == "solver_candidate":
            name = Path(child["executable_path"]).name.lower()
            if name not in SOLVER_NAMES and not name.startswith("abq"):
                return {"state": "UNCONFIRMED", "reason": "solver-candidate executable is not recognized"}
        children.append({"role": child.get("role"), **verify_identity(child)})
    if launcher["state"] == "IDENTITY_MISMATCH" or any(item["state"] == "IDENTITY_MISMATCH" for item in children):
        state, reason = "IDENTITY_MISMATCH", "tracked PID identity changed"
    elif any(item["state"] == "CONFIRMED_ACTIVE" and item["role"] == "solver_candidate" for item in children):
        state, reason = "CONFIRMED_ACTIVE", "observed solver-candidate child remains active"
    elif any(item["state"] == "CONFIRMED_ACTIVE" for item in children):
        state, reason = "POSSIBLE_ORPHAN", "observed descendant remains active"
    elif launcher["state"] == "CONFIRMED_ACTIVE":
        state, reason = "CONFIRMED_ACTIVE", "launcher remains active; solver state is separate"
    elif launcher["state"] == "UNCONFIRMED" or any(item["state"] == "UNCONFIRMED" for item in children):
        state, reason = "UNCONFIRMED", "tracked identity cannot be verified"
    elif (launcher["state"] == "CONFIRMED_EXITED" and evidence.get("launcher_exit_observed") is True
          and evidence.get("child_scan_status") == "OK"
          and any(item["role"] == "solver_candidate" for item in children)
          and all(item["state"] == "CONFIRMED_EXITED" for item in children)):
        state, reason = "CONFIRMED_EXITED", "tracked launcher and observed solver candidate exited"
    else:
        state, reason = "UNCONFIRMED", "launcher exit does not establish solver-child termination"
    return {"state": state, "reason": reason, "launcher": launcher, "children": children}
