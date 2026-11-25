"""Inert BATs and isolated Native Settings. No vendor process is executed."""
import os
import subprocess
import tomllib
import pytest
from abqjobpilot import abaqus_environments as env
from abqjobpilot.execution.models import ExecutionError
from abqjobpilot.gui_settings import DEFAULTS, load_settings, save_settings
from abqjobpilot.product_project import create_project


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "preferences"))
    def forbidden(*args, **kwargs):
        pytest.fail("Environment management launched a program")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


def bat(root, year="2024"):
    commands = root / ("Abaqus" + year) / "Commands"
    commands.mkdir(parents=True)
    path = commands / ("abq" + year + ".bat")
    path.write_bytes(b"@rem INERT TEST ENTRY - DO NOT EXECUTE\r\n")
    return path


def test_none_and_one(tmp_path):
    assert env.discover(path_value="", drive_roots=[tmp_path], registry_locations=[]) == []
    entry = bat(tmp_path)
    result = env.discover(path_value="", drive_roots=[tmp_path], registry_locations=[])
    assert len(result) == 1 and result[0]["entry"] == str(entry)
    assert result[0]["solver"] == result[0]["abaqus_python"] == "NOT_RUN"
    assert result[0]["license"] == "NOT_CHECKED"


def test_multiple_alias_and_registry_deduplication(tmp_path):
    entries = [bat(tmp_path, y) for y in ("2023", "2024", "2025")]
    (entries[1].parent / "abaqus.bat").write_text('@call "%~dp0abq2024.bat" %*\n', encoding="ascii")
    found = env.discover(path_value=os.pathsep.join(str(p.parent) for p in entries),
                         drive_roots=[tmp_path], registry_locations=[entries[1].parent])
    assert sorted(x["version"] for x in found) == ["2023", "2024", "2025"]


def test_no_recursive_search(tmp_path):
    bat(tmp_path / "user-data/deep/archive")
    assert env.discover(path_value="", drive_roots=[tmp_path], registry_locations=[]) == []


def test_manual_default_and_shared_settings_roundtrip(tmp_path):
    entry = bat(tmp_path / "arbitrary location")
    save_settings({**DEFAULTS, "language": "ja-JP", "ui_scale": 1.25})
    manager = env.EnvironmentManager()
    item = manager.add(str(entry))
    assert item["configured"] and item["validation"] == "NOT_CHECKED"
    manager.set_default(item["id"])
    assert manager.validate(item["id"])["validation"] == "VALIDATED"
    assert env.EnvironmentManager().data == manager.data
    assert manager.path.name == "settings.toml"
    assert "abaqus_environments" in tomllib.loads(manager.path.read_text("utf-8"))
    save_settings({**load_settings(), "language": "de-DE"})
    assert env.EnvironmentManager().data == manager.data
    manager.validate(item["id"])
    assert load_settings()["language"] == "de-DE" and load_settings()["ui_scale"] == 1.25
    assert not (manager.path.parent / "abaqus-environments.json").exists()


def test_auto_discovery_preserves_default(tmp_path, monkeypatch):
    first, second = bat(tmp_path / "first"), bat(tmp_path / "second", "2025")
    manager = env.EnvironmentManager()
    item = manager.add(str(first)); manager.set_default(item["id"])
    monkeypatch.setattr(env, "discover", lambda: [env.inspect_entry(first), env.inspect_entry(second)])
    manager.auto_detect(); manager.auto_detect()
    assert manager.data["default_id"] == item["id"] and len(manager.data["environments"]) == 2
    assert not manager.data["environments"][1]["configured"]


@pytest.mark.parametrize("damage", ["missing", "bytes", "replacement"])
def test_material_drift_is_unavailable(tmp_path, damage):
    entry = bat(tmp_path)
    manager = env.EnvironmentManager()
    item = manager.add(str(entry)); manager.set_default(item["id"])
    frozen = manager.freeze()
    if damage == "missing":
        entry.unlink()
    elif damage == "bytes":
        entry.write_bytes(b"@rem changed vendor entry")
    else:
        replacement = entry.with_suffix(".new")
        replacement.write_bytes(entry.read_bytes()); replacement.replace(entry)
    assert manager.validate(item["id"])["validation"] == "UNAVAILABLE"
    with pytest.raises((ExecutionError, OSError)):
        env.verify_binding(frozen)
    with pytest.raises((ExecutionError, OSError)):
        manager.freeze()


def test_project_override_and_frozen_binding(tmp_path):
    first, second = bat(tmp_path / "first"), bat(tmp_path / "second", "2025")
    project = tmp_path / "project"; create_project(project, "Environment Test")
    manager = env.EnvironmentManager()
    a, b = manager.add(str(first)), manager.add(str(second))
    manager.set_default(a["id"])
    assert manager.freeze(project).to_dict()["selection"] == "GLOBAL_DEFAULT"
    manager.select_for_project(project, b["id"])
    assert env.EnvironmentManager().project_choice(project) == b["id"]
    frozen = manager.freeze(project); before = frozen.to_dict()
    manager.set_default(b["id"])
    assert env.verify_binding(frozen) == before and frozen.to_dict() == before
    assert before["snapshot"]["entry"] == str(second) and before["selection"] == "PROJECT"
    assert before["real_plan_adapter"] == "UNAVAILABLE" and before["execution_authorized"] is False
    manager.select_for_project(project, None)
    assert manager.freeze(project).to_dict()["selection"] == "GLOBAL_DEFAULT"


def test_edit_and_remove_do_not_rewrite_frozen_selection(tmp_path):
    first, second = bat(tmp_path / "first"), bat(tmp_path / "second", "2025")
    manager = env.EnvironmentManager()
    a = manager.add(str(first)); manager.set_default(a["id"])
    frozen = manager.freeze()
    manager.add(str(second), replace_id=a["id"])
    assert env.EnvironmentManager().data["default_id"] == a["id"]
    assert manager.freeze().to_dict()["snapshot"]["entry"] == str(second)
    assert env.verify_binding(frozen)["snapshot"]["entry"] == str(first)
    project = tmp_path / "project"; create_project(project, "Override")
    manager.select_for_project(project, a["id"]); manager.remove(a["id"])
    with pytest.raises(ExecutionError) as exc:
        manager.freeze(project)
    assert exc.value.code == "ENVIRONMENT_UNAVAILABLE"


def test_direct_launcher_dependency_is_pinned(tmp_path):
    entry = bat(tmp_path)
    launcher = tmp_path / "SMALauncher.exe"; launcher.write_bytes(b"INERT MATERIAL")
    entry.write_text(f'@echo off\n"{launcher}" %*\n', encoding="utf-8")
    manager = env.EnvironmentManager()
    item = manager.add(str(entry)); manager.set_default(item["id"])
    assert len(item["snapshot"]["materials"]) == 2
    frozen = manager.freeze()
    launcher.write_bytes(b"REPLACED MATERIAL")
    with pytest.raises(ExecutionError):
        env.verify_binding(frozen)


def test_invalid_hardlink_and_cross_project_refused(tmp_path):
    invalid = tmp_path / "random.bat"; invalid.write_bytes(b"echo unrelated")
    manager = env.EnvironmentManager()
    with pytest.raises(ExecutionError):
        manager.add(str(invalid))
    entry = bat(tmp_path)
    item = manager.add(str(entry))
    linked = entry.parent / "abq2025.bat"; os.link(entry, linked)
    with pytest.raises(ExecutionError):
        manager.add(str(linked))
    linked.unlink()
    a, b = tmp_path / "project-a", tmp_path / "project-b"
    create_project(a, "A"); create_project(b, "B")
    manager.select_for_project(a, item["id"])
    (b / "abaqus-environment.json").write_bytes((a / "abaqus-environment.json").read_bytes())
    with pytest.raises(ExecutionError) as exc:
        manager.project_choice(b)
    assert exc.value.code == "PROJECT_IDENTITY_MISMATCH"


def test_failed_atomic_save_reports_unsaved_and_preserves_disk(tmp_path, monkeypatch):
    entry = bat(tmp_path)
    manager = env.EnvironmentManager()
    item = manager.add(str(entry))
    before = manager.path.read_bytes()
    def failed(*args, **kwargs):
        raise OSError("Isolated disk failure")
    monkeypatch.setattr(env, "save_environment_settings", failed)
    with pytest.raises(OSError):
        manager.set_default(item["id"])
    assert manager.unsaved and manager.path.read_bytes() == before
    with pytest.raises(ExecutionError) as exc:
        manager.freeze()
    assert exc.value.code == "UNSAVED_SETTINGS"
    assert env.EnvironmentManager().data["default_id"] is None
