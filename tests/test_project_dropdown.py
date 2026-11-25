"""Project navigation in hidden Native Tk windows and isolated product Projects."""

import hashlib
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

import pytest

from test_native_workspace import desktop
from abqjobpilot.product_project import create_project
from abqjobpilot.ui_resources import LANGUAGES


@pytest.fixture(autouse=True)
def hidden_window(monkeypatch):
    original = tk.Tk.__init__

    def initialize(root, *args, **kwargs):
        original(root, *args, **kwargs)
        root.withdraw()

    monkeypatch.setattr(tk.Tk, "__init__", initialize)


def settled(app, workspace):
    limit = time.monotonic() + 8
    while workspace.lifecycle_busy and time.monotonic() < limit:
        app.update()
        time.sleep(0.02)
    app.update()
    assert not workspace.lifecycle_busy


def inventory(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def labels(menu):
    return [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
            if menu.type(i) != "separator"]


def test_project_selector_menu_and_empty_state(desktop):
    app, w = desktop
    assert w.project_label.get() == "Select Project"
    assert app.desktop_shell_settings["appearance"] == "light"
    for menu in (w.project_menu, w.project_bar_menu):
        assert labels(menu) == ["New Project", "Open Project", "Close Project",
                               "Open Management Project Folder", "Recent Projects",
                               "Export Project", "Import Project", "Project Settings"]
        assert menu.type(4) == "cascade"
        assert menu.entrycget(4, "menu") == str(menu.recent_projects)
        assert menu.recent_projects.entrycget(0, "label") == w.t("noRecent")
        assert menu.entrycget(2, "state") == "disabled"
        assert menu.entrycget(6, "state") == menu.entrycget(7, "state") == "disabled"
        assert menu.entrycget(8, "state") == "normal"
    assert w.reader is None and not w.lifecycle_threads


def test_recent_switch_close_and_native_records_unchanged(desktop, tmp_path):
    app, w = desktop
    first, second = tmp_path / "folder-a", tmp_path / "folder-b"
    create_project(first, "Project Alpha")
    create_project(second, "A long project name " + "x" * 55)
    before = {str(p): inventory(p) for p in (first, second)}
    w.open_path(str(first))
    assert w.project_label.get() == "Project Alpha"
    settled(app, w)
    first_reader = w.reader
    w.preferences.save(recent=[str(second), str(first)])
    # The native postcommand refreshes the cascade without opening another window.
    app.tk.call(w.project_menu.cget("postcommand"))
    submenu = w.project_menu.recent_projects
    assert submenu.entrycget(0, "label") == f"A long project name {'x' * 55} ({second})"
    assert submenu.entrycget(1, "label") == f"Project Alpha ({first})"
    assert w.preferences.data["recent"] == [str(second), str(first)]
    submenu.invoke(0)
    assert w.project == str(second)
    assert w.project_label.get() == "A long project name " + "x" * 55
    assert first_reader.stop.is_set()
    settled(app, w)
    w._menus()
    assert w.project_menu.entrycget(2, "state") == "normal"
    with patch("os.startfile") as launch:
        w.project_menu.invoke(3)
        launch.assert_called_once_with(str(second))
    with patch("tkinter.messagebox.showinfo") as info:
        w.project_menu.invoke(8)
        assert info.call_count == 1
        assert str(second) in info.call_args.args[1]
    reader = w.reader
    w.run_items = {"r_fixture": {"run_id": "r_fixture", "job_id": "job_fixture", "execution": "RUNNING"}}
    w.selected_run_id = "r_fixture"
    w.close_project()
    assert reader.stop.is_set() and w.reader is None and w.project is None
    assert w.project_label.get() == "Select Project" and w.product_name is None
    assert w.selected_run_id is None and w.run_items == {}
    assert w.queue_tree.get_children() == w.results_tree.get_children() == ()
    assert w.preferences.data["recent"] == [str(second), str(first)]
    assert {str(p): inventory(p) for p in (first, second)} == before
    assert w.classic_pane is None


def test_missing_recent_path_preserves_selection_and_history(desktop, tmp_path):
    app, w = desktop
    project, missing = tmp_path / "valid", tmp_path / "does-not-exist"
    create_project(project, "Current Project")
    w.open_path(str(project));settled(app, w)
    current_reader = w.reader
    w.preferences.save(recent=[str(missing), str(project)])
    w._menus()
    assert w.project_menu.recent_projects.entrycget(0, "label") == f"does-not-exist ({missing})"
    with patch("tkinter.messagebox.showerror") as error:
        w.project_menu.recent_projects.invoke(0)
        assert error.call_count == 1 and str(missing) in error.call_args.args[1]
    assert not missing.exists()
    assert w.project == str(project) and w.reader is current_reader
    assert w.project_label.get() == "Current Project"
    assert w.preferences.data["recent"] == [str(missing), str(project)]


def test_switch_close_refused_during_lifecycle_operation(desktop, tmp_path):
    app, w = desktop
    w.project = str(tmp_path / "selected")
    w.product_name = "Selected"
    w.project_label.set("Selected")
    w.lifecycle_busy = True
    w._menus()
    for index in (0, 1, 2):
        assert w.project_menu.entrycget(index, "state") == "disabled"
    w.open_path(str(tmp_path / "other"))
    w.close_project()
    assert w.project == str(tmp_path / "selected")
    assert w.project_label.get() == "Selected"
    assert w.lifecycle_threads == [] and w.reader is None
    w.lifecycle_busy = False


def test_native_recent_cascade_posts_in_light_mode(desktop, tmp_path):
    app, w = desktop
    w.preferences.save(recent=[str(tmp_path / "Recent A")])
    assert app.desktop_shell_settings["appearance"] == "light"
    # Run the native posting hooks without entering Windows' modal menu tracking loop.
    app.tk.call(w.project_menu.cget("postcommand"))
    submenu = w.project_menu.recent_projects
    app.tk.call(submenu.cget("postcommand"))
    assert w.project_menu.type(4) == "cascade"
    assert w.project_menu.entrycget(4, "menu") == str(submenu)
    assert submenu.entrycget(0, "label") == f"Recent A ({tmp_path / 'Recent A'})"


@pytest.mark.parametrize("locale", list(LANGUAGES))
def test_project_menus_follow_language_and_keep_settings(desktop, locale):
    app, w = desktop
    w.change_language(locale)
    app.update()
    assert w.project_label.get() == w.t("noProject")
    for menu in (w.project_menu, w.project_bar_menu):
        assert labels(menu)[-1] == w.t("projectSettings")
        assert labels(menu)[2] == w.t("closeProject")
        assert labels(menu)[4] == w.t("recent")
    assert w.reader is None and not w.lifecycle_threads
