import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from abqjobpilot import config
from abqjobpilot.gui_app import AbqJobPilotApp
from abqjobpilot.project import ProjectManager
from abqjobpilot.queue_store import build_queue_record, save_queue


class ProjectGuiTests(unittest.TestCase):
    def test_export_defaults_to_metadata_and_explains_external_references(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manager = ProjectManager(recent_file=root / "recent.json")
            project = manager.create_project(root / "Project", "Project")
            manager.current = project
            default = root / "default_runtime"
            with patch.object(config, "RUNTIME_DIR_PATH", default), \
                 patch.object(config, "RUNTIME_DIR", str(default)), \
                 patch.object(config, "QUEUE_FILE", str(default / "queue.json")), \
                 patch.object(config, "LIVE_STATUS_FILE", str(default / "live_status.json")), \
                 patch.object(config, "SETTINGS_FILE", str(default / "settings.json")), \
                 patch("abqjobpilot.gui_app.ProjectManager", return_value=manager), \
                 patch.object(AbqJobPilotApp, "_read_gpu_text", return_value="--"):
                try:
                    app = AbqJobPilotApp()
                except tk.TclError as exc:
                    self.skipTest(f"Tk display unavailable: {exc}")
                try:
                    with patch("abqjobpilot.gui_app.messagebox.askyesnocancel", return_value=False) as choice, \
                         patch("abqjobpilot.gui_app.filedialog.asksaveasfilename",
                               return_value=str(root / "metadata.zip")), \
                         patch("abqjobpilot.gui_app.export_project_archive") as exporter, \
                         patch("abqjobpilot.gui_app.messagebox.showinfo"):
                        app.export_project_dialog()
                    self.assertEqual(choice.call_args.kwargs["default"], "no")
                    self.assertIn("outside the Project are never copied", choice.call_args.args[1])
                    exporter.assert_called_once_with(project.root, str(root / "metadata.zip"), mode="metadata")
                finally:
                    app.destroy()

    def test_project_switch_reloads_queue_and_results_without_runner(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manager = ProjectManager(recent_file=root / "recent.json")
            a = manager.create_project(root / "A", "A")
            b = manager.create_project(root / "B", "B")
            inp_a = a.models_dir / "Job_A.inp"
            inp_b = b.models_dir / "Job_B.inp"
            a.models_dir.mkdir()
            b.models_dir.mkdir()
            inp_a.write_text("*Heading\n", encoding="utf-8")
            inp_b.write_text("*Heading\n", encoding="utf-8")
            queued = build_queue_record(inp_a, 2, 0, "A", "A", None, True, True, "")
            completed = build_queue_record(inp_b, 2, 0, "B", "B", None, True, True, "")
            completed["status"] = "COMPLETED_OK"
            completed["phase"] = "COMPLETED_OK"
            save_queue([queued], runtime_dir=a.runtime_dir)
            save_queue([completed], runtime_dir=b.runtime_dir)
            default = root / "default_runtime"
            with patch.object(config, "RUNTIME_DIR_PATH", default), \
                 patch.object(config, "RUNTIME_DIR", str(default)), \
                 patch.object(config, "QUEUE_FILE", str(default / "queue.json")), \
                 patch.object(config, "LIVE_STATUS_FILE", str(default / "live_status.json")), \
                 patch.object(config, "SETTINGS_FILE", str(default / "settings.json")), \
                 patch("abqjobpilot.gui_app.ProjectManager", return_value=manager), \
                 patch.object(AbqJobPilotApp, "_read_gpu_text", return_value="--"):
                try:
                    app = AbqJobPilotApp()
                except tk.TclError as exc:
                    self.skipTest(f"Tk display unavailable: {exc}")
                try:
                    self.assertEqual(len(app.queue_tree.get_children()), 0)
                    app.open_project(a.root)
                    self.assertIn("A", app.project_name_var.get())
                    self.assertEqual(len(app.queue_tree.get_children()), 1)
                    self.assertEqual(len(app.results_tree.get_children()), 0)
                    app.open_project(b.root)
                    self.assertEqual(len(app.queue_tree.get_children()), 0)
                    self.assertEqual(len(app.results_tree.get_children()), 1)
                    existing_windows = set(app.winfo_children())
                    app._show_run_history(completed)
                    history_windows = [child for child in app.winfo_children()
                                       if isinstance(child, tk.Toplevel) and child not in existing_windows]
                    self.assertEqual(len(history_windows), 1)
                    self.assertIn("Run History", history_windows[0].title())
                    history_windows[0].destroy()
                    with patch.object(app.runner, "is_running", return_value=True), \
                         patch("abqjobpilot.gui_app.messagebox.showwarning"):
                        app.open_project(a.root)
                    self.assertEqual(manager.current.project_id, b.project_id)
                    app.close_project()
                    self.assertIsNone(manager.current)
                    self.assertEqual(len(app.results_tree.get_children()), 0)
                    self.assertEqual(config.RUNTIME_DIR, str(default))
                    self.assertTrue(callable(app._show_queue_menu))
                    self.assertTrue(callable(app._show_results_menu))
                finally:
                    app.destroy()


if __name__ == "__main__":
    unittest.main()
