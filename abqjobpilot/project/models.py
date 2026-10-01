"""Small, GUI-free Project contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectInfo:
    project_id: str
    name: str
    root_dir: str
    created_at: str
    updated_at: str
    description: str | None = None
    schema_version: str = "1.0"

    @property
    def root(self) -> Path:
        return Path(self.root_dir)

    @property
    def project_file(self) -> Path:
        return self.root / "project.json"

    @property
    def runtime_dir(self) -> Path:
        return self.root / "runtime"

    @property
    def models_dir(self) -> Path:
        return self.root / "models"

    @property
    def results_dir(self) -> Path:
        return self.root / "results"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"
