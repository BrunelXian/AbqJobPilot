"""Lightweight public data models for abqjobpilot integrations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from abqjobpilot import config
from .errors import error_detail


@dataclass
class JsonModel:
    """Small JSON helper base class without third-party dependencies."""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema_version"] = config.SCHEMA_VERSION
        if "errors" in data:
            data["error_details"] = self.error_details
        return data

    @property
    def error_details(self) -> list[dict[str, str]]:
        return [error_detail(message) for message in getattr(self, "errors", [])]

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class JobRequest(JsonModel):
    inp_path: str
    job_name: str | None = None
    cpus: int = config.DEFAULT_CPUS
    gpus: int = config.DEFAULT_GPUS
    batch: str | None = None
    strategy: str | None = None
    working_dir: str | None = None
    submission_mode: str = "preview_only"
    allow_solver_submit: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobPreflightResult(JsonModel):
    status: str
    job_id: str | None
    inp_path: str
    inp_exists: bool
    job_name: str | None
    cpus: int
    batch: str | None
    strategy: str | None
    working_dir: str | None
    expected_odb_path: str | None
    command_preview: str | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class JobSubmitResult(JsonModel):
    status: str
    job_id: str | None
    queue_file: str | None
    command_preview: str | None
    expected_odb_path: str | None = None
    queue_only: bool = False
    queue_file_mutated: bool = False
    solver_started: bool = False
    runner_started: bool = False
    gui_required: bool = False
    allowed_mutations: list[str] = field(default_factory=list)
    forbidden_mutations_detected: bool = False
    runtime_snapshot_before: dict[str, Any] | None = None
    runtime_snapshot_after: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class JobStatusResult(JsonModel):
    status: str
    job_id: str | None
    inp_path: str | None
    working_dir: str | None
    expected_odb_path: str | None
    odb_exists: bool
    lock_exists: bool
    status_sources: list[str] = field(default_factory=list)
    last_log_lines: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class JobOutputResult(JsonModel):
    job_id: str | None
    working_dir: str | None
    expected_odb_path: str | None
    odb_exists: bool
    lock_exists: bool
    log_paths: list[str] = field(default_factory=list)
    sta_path: str | None = None
    msg_path: str | None = None
    dat_path: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
