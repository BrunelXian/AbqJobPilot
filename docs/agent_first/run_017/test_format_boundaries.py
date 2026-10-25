"""Run017: real format rejection, with no schema conversion or default Project lookup."""
from dataclasses import replace
from pathlib import Path
import hashlib
import pytest

from abqjobpilot.execution.models import ExecutionError
from abqjobpilot.execution.store import create_experiment, ExperimentStore, open_existing_read_only
from abqjobpilot.project.manager import ProjectManager


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def test_legacy_reader_rejects_experimental_project_without_writes(tmp_path):
    context = create_experiment(tmp_path, tmp_path / 'af')
    ExperimentStore(context).close()
    before = snapshot(tmp_path)
    manager = ProjectManager(recent_file=tmp_path / 'recent.json')
    with pytest.raises((ValueError, FileNotFoundError)):
        manager.validate_project(context.root)
    assert snapshot(tmp_path) == before
    assert not (Path(context.root) / 'project.db').exists()


def test_experimental_reader_rejects_legacy_project_without_writes(tmp_path):
    manager = ProjectManager(recent_file=tmp_path / 'recent.json')
    legacy = manager.create_project(tmp_path / 'legacy', 'legacy')
    context = create_experiment(tmp_path, tmp_path / 'af')
    ExperimentStore(context).close()
    stat = legacy.root.stat()
    wrong = replace(context, root=str(legacy.root), runtime_root=str(legacy.runtime_dir),
                    execution_store=str(legacy.root / 'execution.sqlite3'),
                    root_device=stat.st_dev, root_inode=stat.st_ino)
    before = snapshot(tmp_path)
    with pytest.raises(ExecutionError):
        open_existing_read_only(wrong)
    assert snapshot(tmp_path) == before
    assert not (legacy.root / 'execution.sqlite3').exists()
