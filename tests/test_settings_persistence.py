"""Settings persistence and GUI context isolation; temporary Projects only."""

import json
import tkinter as tk
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from abqjobpilot import config
from abqjobpilot.agent_session import AgentCommandSession
from abqjobpilot.api import AbqJobPilotClient
from abqjobpilot.gui_app import AbqJobPilotApp, BasicSettingsDialog
from abqjobpilot.project import ProjectManager
from abqjobpilot.queue_store import read_queue, save_queue
from abqjobpilot.settings_store import (
    DEFAULT_SETTINGS, inspect_settings_for_runtime, load_settings_for_runtime, save_settings,
)


@pytest.fixture
def projects(tmp_path, monkeypatch):
    runtime = tmp_path / "no_project"
    for name, value in {"RUNTIME_DIR_PATH": runtime, "RUNTIME_DIR": str(runtime),
                        "SETTINGS_FILE": str(runtime / "settings.json"),
                        "QUEUE_FILE": str(runtime / "queue.json"),
                        "LIVE_STATUS_FILE": str(runtime / "live_status.json")}.items():
        monkeypatch.setattr(config, name, value)
    monkeypatch.setattr("abqjobpilot.project.manager.get_app_state_dir", lambda: tmp_path / "app_state")
    manager = ProjectManager(tmp_path / "recent.json")
    a = manager.create_project(tmp_path / "A", "A")
    b = manager.create_project(tmp_path / "B", "B")
    return manager, a, b, runtime


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_missing_is_not_persisted_and_does_not_create_runtime(tmp_path):
    runtime = tmp_path / "absent"
    result = inspect_settings_for_runtime(runtime)
    assert result["status"] == "NOT_PERSISTED"
    assert not result["persisted"] and not result["exists"]
    assert result["settings"] is None
    assert result["effective_settings"] == DEFAULT_SETTINGS
    assert result["settings_file"] == str(runtime / "settings.json")
    assert load_settings_for_runtime(runtime) == DEFAULT_SETTINGS
    assert not runtime.exists()


@pytest.mark.parametrize("payload", ['{', '[]', '{"default_cpus":"14"}',
                                     '{"use_gpu":"false"}', '{"default_cpus":0}'])
def test_corrupt_or_invalid_settings_are_reported_without_rewrite(tmp_path, payload):
    path = tmp_path / "settings.json"
    path.write_text(payload, encoding="utf-8")
    before = snapshot(tmp_path)
    result = inspect_settings_for_runtime(tmp_path)
    assert result["status"] == "INVALID_SETTINGS"
    assert not result["persisted"] and result["exists"]
    assert result["effective_settings"] is None and result["errors"]
    assert snapshot(tmp_path) == before


def test_read_permission_failure_is_not_missing(tmp_path):
    with patch.object(Path, "read_text", side_effect=PermissionError("access denied")):
        result = inspect_settings_for_runtime(tmp_path)
    assert result["status"] == "SETTINGS_READ_FAILED"
    assert not result["persisted"] and result["exists"] is None


def test_no_project_explicit_save_ignores_mutable_global_file(projects, tmp_path, monkeypatch):
    runtime = projects[3]
    unrelated = tmp_path / "unrelated" / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_FILE", str(unrelated))
    saved = save_settings({"default_cpus": 7}, runtime_dir=runtime)
    result = inspect_settings_for_runtime(runtime)
    assert result["status"] == "PERSISTED" and result["persisted"]
    assert result["settings"] == saved == result["effective_settings"]
    assert result["settings"]["default_cpus"] == 7
    assert not unrelated.exists()
    assert not (runtime / "queue.json").exists()


def test_old_partial_file_reports_actual_values_separately(tmp_path):
    (tmp_path / "settings.json").write_text('{"default_cpus":3}', encoding="utf-8")
    result = inspect_settings_for_runtime(tmp_path)
    assert result["persisted"]
    assert result["settings"] == {"default_cpus": 3}
    assert result["effective_settings"]["run_full"] is True
    assert "run_full" in result["defaulted_fields"]


def test_save_verifies_real_data_not_default_fallback(tmp_path):
    with patch("abqjobpilot.settings_store.write_json"):
        with pytest.raises(OSError, match="verification failed"):
            save_settings(DEFAULT_SETTINGS, runtime_dir=tmp_path)
    save_settings({"default_cpus": 2}, runtime_dir=tmp_path)
    with patch("abqjobpilot.settings_store.write_json"):
        with pytest.raises(OSError, match="verification failed"):
            save_settings({"default_cpus": 14}, runtime_dir=tmp_path)


def test_wrong_write_destination_and_readback_path_are_rejected(tmp_path):
    intended = tmp_path / "intended"
    wrong = tmp_path / "wrong.json"
    with patch("abqjobpilot.settings_store.write_json",
               side_effect=lambda path, data: wrong.write_text(json.dumps(data), encoding="utf-8")):
        with pytest.raises(OSError, match="verification failed"):
            save_settings(DEFAULT_SETTINGS, runtime_dir=intended)
    assert not (intended / "settings.json").exists()
    with patch("abqjobpilot.settings_store.inspect_settings_for_runtime", return_value={
            "settings_file": str(wrong), "persisted": True, "settings": DEFAULT_SETTINGS,
            "status": "PERSISTED", "errors": []}):
        with pytest.raises(OSError, match="verification failed"):
            save_settings(DEFAULT_SETTINGS, runtime_dir=intended)


def test_public_project_query_is_read_only_and_requires_selector(projects, tmp_path):
    manager, a, b, _ = projects
    client = AbqJobPilotClient(recent_file=str(manager.recent_file))
    before = snapshot(tmp_path)
    result = client.get_project_settings(project_id=a.project_id).to_dict()
    assert result["project_id"] == a.project_id and result["status"] == "NOT_PERSISTED"
    assert result["settings_file"] == str(a.runtime_dir / "settings.json")
    assert result["settings"] is None and not result["persisted"]
    assert client.get_project_settings().status == "INVALID_PROJECT_SELECTOR"
    assert snapshot(tmp_path) == before
    save_settings({"default_cpus": 4}, runtime_dir=a.runtime_dir)
    save_settings({"default_cpus": 8}, runtime_dir=b.runtime_dir)
    before = snapshot(tmp_path)
    for project, cpus in ((a, 4), (b, 8), (a, 4)):
        result = json.loads(client.get_project_settings(project=str(project.root)).to_json())
        assert result["persisted"] and result["settings"]["default_cpus"] == cpus
        assert result["project_id"] == project.project_id and result["schema_version"] == "1.0"
    assert snapshot(tmp_path) == before
    (a.runtime_dir / "settings.json").write_text("broken", encoding="utf-8")
    result = client.get_project_settings(project=str(a.root)).to_dict()
    assert result["status"] == "INVALID_SETTINGS" and not result["persisted"]
    assert result["error_details"][0]["code"] == "INVALID_SETTINGS"


def fake_dialog(runtime, tmp_path, **kwargs):
    values = {"abaqus_cmd": DEFAULT_SETTINGS["abaqus_cmd"], "cpus": 14, "use_gpu": False,
              "gpus": 0, "datacheck": True, "full_run": True, "auto_shutdown": False,
              "auto_shutdown_minutes": 5, "apply_queued": False, "projects_root": str(tmp_path / "projects")}
    dialog = SimpleNamespace(runtime_dir=Path(runtime), settings_file=Path(runtime) / "settings.json",
                             project_id=None, validate_context=None, on_saved=Mock(), destroy=Mock(),
                             _projects_root=tmp_path / "projects", winfo_exists=Mock(return_value=False))
    for name, value in values.items():
        setattr(dialog, name + "_var", SimpleNamespace(get=lambda value=value: value))
    for name, value in kwargs.items():
        setattr(dialog, name, value)
    return dialog


@pytest.fixture
def messages():
    with patch("abqjobpilot.gui_app.messagebox.showerror") as error, \
         patch("abqjobpilot.gui_app.messagebox.showinfo") as info:
        yield error, info


def test_gui_save_does_not_modify_queue_without_opt_in(projects, tmp_path, messages):
    _, a, b, _ = projects
    for project in (a, b):
        save_queue([{"queue_id": project.name, "status": "QUEUED", "cpus": 2}], project.runtime_dir)
    before = [snapshot(project.root) for project in (a, b)]
    dialog = fake_dialog(a.runtime_dir, tmp_path, project_id=a.project_id)
    with patch("abqjobpilot.gui_app.apply_resources_to_queued_jobs") as apply:
        BasicSettingsDialog.save(dialog)
    apply.assert_not_called()
    messages[0].assert_not_called()
    dialog.destroy.assert_called_once()
    assert str(a.runtime_dir / "settings.json") in messages[1].call_args.args[1]
    after = snapshot(a.root)
    del after["runtime/settings.json" if "runtime/settings.json" in after else "runtime\\settings.json"]
    assert after == before[0] and snapshot(b.root) == before[1]


@pytest.mark.parametrize("failure", [PermissionError("denied"), OSError("disk failure")])
def test_gui_write_failure_is_visible_and_keeps_dialog_open(projects, tmp_path, messages, failure):
    a = projects[1]
    dialog = fake_dialog(a.runtime_dir, tmp_path)
    with patch("abqjobpilot.settings_store.write_json", side_effect=failure), \
         patch("abqjobpilot.gui_app.apply_resources_to_queued_jobs") as apply:
        BasicSettingsDialog.save(dialog)
    assert str(dialog.settings_file) in messages[0].call_args.args[1]
    assert str(failure) in messages[0].call_args.args[1]
    messages[1].assert_not_called()
    dialog.destroy.assert_not_called()
    dialog.on_saved.assert_not_called()
    apply.assert_not_called()


def test_explicit_queue_update_stays_in_bound_runtime(projects, tmp_path, messages):
    _, a, b, _ = projects
    records = [{"queue_id": "queued", "status": "QUEUED", "cpus": 2},
               {"queue_id": "done", "status": "COMPLETED_OK", "cpus": 3}]
    for project in (a, b):
        save_queue(records, project.runtime_dir)
    config.use_runtime_dir(b.runtime_dir)
    before_b = snapshot(b.root)
    dialog = fake_dialog(a.runtime_dir, tmp_path, apply_queued_var=SimpleNamespace(get=lambda: True))
    BasicSettingsDialog.save(dialog)
    assert read_queue(a.runtime_dir)[0]["cpus"] == 14
    assert read_queue(a.runtime_dir)[1] == records[1]
    assert snapshot(b.root) == before_b
    messages[0].assert_not_called()


def test_partial_followup_failure_does_not_report_complete_success(projects, tmp_path, messages):
    dialog = fake_dialog(projects[1].runtime_dir, tmp_path,
                         apply_queued_var=SimpleNamespace(get=lambda: True))
    with patch("abqjobpilot.gui_app.apply_resources_to_queued_jobs", return_value={"ok": False, "message": "QUEUE_LOCK_TIMEOUT"}):
        BasicSettingsDialog.save(dialog)
    assert "saved and verified" in messages[0].call_args.args[1]
    assert "QUEUE_LOCK_TIMEOUT" in messages[0].call_args.args[1]
    assert inspect_settings_for_runtime(dialog.runtime_dir)["persisted"]
    messages[1].assert_not_called()
    dialog.destroy.assert_not_called()


def captured_gui_dialog(projects, tmp_path):
    manager, a, _b, _runtime = projects
    manager.current = a
    config.use_runtime_dir(a.runtime_dir)
    app = SimpleNamespace(project_manager=manager, _project_context_revision=0,
                          _settings_dialog=None, refresh_all=Mock())
    app._settings_binding = MethodType(AbqJobPilotApp._settings_binding, app)
    def create(master, **kwargs):
        runtime = kwargs.pop("runtime_dir")
        return fake_dialog(runtime, tmp_path, **kwargs)
    with patch("abqjobpilot.gui_app.BasicSettingsDialog", side_effect=create):
        AbqJobPilotApp.open_settings(app)
    return app, app._settings_dialog


@pytest.mark.parametrize("change", ["project_b", "roundtrip", "global_runtime", "global_file", "manifest_id"])
def test_changed_context_cannot_write_to_any_project(projects, tmp_path, messages, change):
    manager, a, b, _ = projects
    app, dialog = captured_gui_dialog(projects, tmp_path)
    if change in {"project_b", "roundtrip"}:
        manager.current = b if change == "project_b" else a
        config.use_runtime_dir(manager.current.runtime_dir)
        app._project_context_revision += 2
    elif change == "global_runtime":
        config.use_runtime_dir(b.runtime_dir)
    elif change == "global_file":
        config.SETTINGS_FILE = str(b.runtime_dir / "settings.json")
    else:
        data = json.loads(a.project_file.read_text(encoding="utf-8"))
        data["project_id"] = b.project_id
        a.project_file.write_text(json.dumps(data), encoding="utf-8")
    before = snapshot(tmp_path)
    BasicSettingsDialog.save(dialog)
    assert snapshot(tmp_path) == before
    messages[0].assert_called_once()
    messages[1].assert_not_called()
    dialog.destroy.assert_not_called()


def test_agent_target_does_not_change_gui_settings_binding(projects, tmp_path, messages):
    manager, a, b, _ = projects
    _app, dialog = captured_gui_dialog(projects, tmp_path)
    agent = AgentCommandSession(recent_file=str(manager.recent_file), project=str(a.root))
    assert agent.use_project(str(b.root))["status"] == "PROJECT_SELECTED"
    assert agent.target.project_id == b.project_id and manager.current.project_id == a.project_id
    before_b = snapshot(b.root)
    BasicSettingsDialog.save(dialog)
    assert inspect_settings_for_runtime(a.runtime_dir)["persisted"]
    assert snapshot(b.root) == before_b
    assert Path(config.RUNTIME_DIR) == a.runtime_dir
    messages[0].assert_not_called()


def test_real_gui_no_project_and_a_b_a_persistence(projects, messages):
    manager, a, b, runtime = projects
    with patch("abqjobpilot.gui_app.ProjectManager", return_value=manager), \
         patch.object(AbqJobPilotApp, "_read_gpu_text", return_value="--"), \
         patch("abqjobpilot.gui_app.QueueRunner.start", side_effect=AssertionError("No runner")):
        try:
            app = AbqJobPilotApp()
        except tk.TclError as exc:
            pytest.skip(f"Tk display unavailable: {exc}")
        try:
            app.update_idletasks()
            app.open_settings()
            dialog = app._settings_dialog
            assert dialog.runtime_dir == runtime and dialog.project_id is None
            assert not dialog.apply_queued_var.get() and dialog.gpus_var.get() == 0
            dialog.save()
            assert inspect_settings_for_runtime(runtime)["persisted"]
            for project, cpus in ((a, 4), (b, 8), (a, 4)):
                app.open_project(project.root)
                app.open_settings()
                dialog = app._settings_dialog
                assert dialog.runtime_dir == project.runtime_dir and dialog.project_id == project.project_id
                if inspect_settings_for_runtime(project.runtime_dir)["persisted"]:
                    assert dialog.cpus_var.get() == cpus
                with patch("abqjobpilot.gui_app.messagebox.showwarning") as warning:
                    assert not app._can_switch_project()
                    warning.assert_called_once()
                dialog.cpus_var.set(cpus)
                before = (project.runtime_dir / "queue.json").read_bytes()
                dialog.save()
                assert (project.runtime_dir / "queue.json").read_bytes() == before
                assert inspect_settings_for_runtime(project.runtime_dir)["settings"]["default_cpus"] == cpus
            messages[0].assert_not_called()
        finally:
            app.destroy()
