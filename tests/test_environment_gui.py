"""Current Native Settings dialog only; isolated data and no process launch."""
import tkinter as tk
from unittest.mock import patch

import pytest

from test_native_workspace import desktop, LANGUAGES, catalog
from abqjobpilot import abaqus_environments as env
from abqjobpilot.product_project import create_project
from test_abaqus_environments import bat


@pytest.fixture(autouse=True)
def hidden(monkeypatch):
    original = tk.Tk.__init__
    def initialize(root, *args, **kwargs):
        original(root, *args, **kwargs)
        root.withdraw()
    monkeypatch.setattr(tk.Tk, "__init__", initialize)


def ready(w):
    if w.environment_thread:
        w.environment_thread.join(5)
    assert not w.environment_busy
    w.show_environments()
    return w.environment_dialog


def test_no_installation_and_native_settings_controls(desktop, tmp_path):
    app, w = desktop
    dialog = ready(w)
    app.update_idletasks()
    assert dialog.tree.get_children() == ()
    assert w.reader is None and w.project is None
    assert w.environment_manager.path.name == "settings.toml"
    assert [b.cget("text") for b in dialog.buttons] == ["Auto Detect", "Add Manually", "Edit", "Remove", "Set Default", "Validate"]
    assert app.desktop_shell_settings["appearance"] == "light"
    with patch("tkinter.filedialog.askopenfilename", return_value=""):
        before = w.environment_manager.path.read_bytes()
        dialog.add()
    assert w.environment_manager.path.read_bytes() == before
    for locale in LANGUAGES:
        assert catalog(locale).keys() == catalog("en").keys()
    dialog.close()


def test_saved_default_reopens_and_project_override(desktop, tmp_path):
    app, w = desktop
    dialog = ready(w)
    first, second = bat(tmp_path / "first"), bat(tmp_path / "second", "2025")
    with patch("tkinter.filedialog.askopenfilename", return_value=str(first)):
        dialog.add()
    a, = dialog.tree.get_children()
    dialog.tree.selection_set(a)
    dialog.set_default(); dialog.validate()
    assert "VALIDATED" in dialog.tree.item(a, "values")[3]
    dialog.close(); w.show_environments(); dialog = w.environment_dialog
    assert w.environment_manager.data["default_id"] == a
    with patch("tkinter.filedialog.askopenfilename", return_value=str(second)):
        dialog.add()
    b = next(i for i in dialog.tree.get_children() if i != a)
    project = tmp_path / "project"
    create_project(project, "GUI Environment")
    w.project = str(project)
    dialog.tree.selection_set(b); dialog.use_project()
    assert env.EnvironmentManager().project_choice(project) == b
    assert env.EnvironmentManager().data["default_id"] == a
    dialog.use_global()
    assert env.EnvironmentManager().project_choice(project) is None
    second.unlink()
    dialog.tree.selection_set(b); dialog.validate()
    assert "UNAVAILABLE" in dialog.tree.item(b, "values")[3]
    assert dialog.tree.item(b, "values")[5]
    with patch("tkinter.messagebox.askyesno", return_value=True):
        dialog.remove()
    assert b not in dialog.tree.get_children()
    assert w.reader is None and w.lifecycle_threads == []
    w.project = None
    dialog.close()


def test_first_use_detects_once_and_manual_rescan(desktop, monkeypatch, tmp_path):
    app, w = desktop
    dialog = ready(w)
    entry = bat(tmp_path)
    calls = []
    def found():
        calls.append("static")
        return [env.inspect_entry(entry)]
    monkeypatch.setattr(env, "discover", found)
    w.detect_environments()
    w.environment_thread.join(5)
    dialog.refresh(schedule=False)
    assert calls == ["static"]
    identifier, = dialog.tree.get_children()
    assert "FOUND" in dialog.tree.item(identifier, "values")[3]
    dialog.tree.selection_set(identifier); dialog.set_default()
    w.detect_environments(); w.environment_thread.join(5)
    dialog.refresh(schedule=False)
    assert w.environment_manager.data["default_id"] == identifier
    assert calls == ["static", "static"]
