"""Compact, native process evidence for one queue attempt.

This is not a process trace: only identities observed by the runner are kept.
External passive-monitor JSONL files are never imported or relabelled here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .utils import now_iso, read_json, write_json


def evidence_reference(queue_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", queue_id):
        raise ValueError("Invalid queue_id for process evidence")
    return f"reports/process_evidence/{queue_id}.json"


def _strength(evidence: dict) -> dict[str, str]:
    launcher = evidence.get("launcher", {})
    launcher_strength = "VERIFIED" if launcher.get("identity_status") == "CONFIRMED" else (
        "UNVERIFIED" if isinstance(launcher.get("pid"), int) else "UNKNOWN")
    children = evidence.get("observed_children", [])
    verified = [child for child in children if child.get("identity_status") == "CONFIRMED"
                and child.get("relationship_status") == "VERIFIED"]
    lineage = "VERIFIED" if verified else ("UNVERIFIED" if children else "UNKNOWN")
    candidates = [child for child in children if child.get("role") == "solver_candidate"]
    solver = "VERIFIED" if any(child in verified for child in candidates) else (
        "UNVERIFIED" if candidates else "UNKNOWN")
    return {"launcher": launcher_strength, "lineage": lineage, "solver_candidate": solver}


def save_phase_evidence(runtime_dir: str | Path, queue_id: str, phase: str,
                        evidence: dict, *, return_code: int | None = None) -> str:
    if phase not in {"DATACHECK_RUNNING", "FULL_RUNNING"}:
        raise ValueError("Unsupported process evidence phase")
    reference = evidence_reference(queue_id)
    path = Path(runtime_dir) / reference
    record = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None
    if record is not None and (not isinstance(record, dict) or record.get("queue_id") != queue_id
                               or record.get("source") != "native_runner"
                               or not isinstance(record.get("phases"), dict)):
        raise ValueError("Existing process evidence identity does not match")
    if record is None:
        record = {"schema_version": "1.0", "source": "native_runner", "queue_id": queue_id,
                  "phases": {}}
    record["phases"][phase] = {
        "identity_strength": _strength(evidence),
        "process_identity": evidence,
        "command_exit": {"return_code": return_code, "observed_at": now_iso()}
        if return_code is not None else None,
    }
    record["updated_at"] = now_iso()
    write_json(path, record)
    return reference


def read_process_evidence(runtime_dir: str | Path, reference: str | None) -> dict | None:
    if not isinstance(reference, str) or not re.fullmatch(
            r"reports/process_evidence/[A-Za-z0-9_-]{1,128}\.json", reference):
        return None
    root = Path(runtime_dir).resolve()
    path = (root / reference).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    record = read_json(path, None)
    return record if isinstance(record, dict) and record.get("source") == "native_runner" else None
