import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import patch

from abqjobpilot import config
from abqjobpilot import __version__
from abqjobpilot.app_metadata import STABLE_GITHUB_URL, github_url_from_remote
from abqjobpilot.api import AbqJobPilotClient
from abqjobpilot.command_console import AGENT_UI_STRINGS, AI_INSTRUCTION, CLI_EXAMPLES
from abqjobpilot.command_parser import COMMAND_EXAMPLES, SUPPORTED_COMMANDS, parse_agent_command
from abqjobpilot.gui_app import AbqJobPilotApp
from abqjobpilot.gui_presentation import (SUCCESS_BACKGROUND, SUCCESS_FOREGROUND,
                                           filter_jobs, read_log_tail, status_presentation)
from abqjobpilot.gui_table_state import queue_display_jobs, result_display_jobs, row_iid
from abqjobpilot.project import ProjectManager
from abqjobpilot.queue_store import build_queue_record, read_queue, save_queue
from abqjobpilot.utils import write_json


class PresentationTests(unittest.TestCase):
    def test_verified_github_remote_normalization(self):
        url = "https://github.com/BrunelXian/AbqJobPilot"
        self.assertEqual(STABLE_GITHUB_URL, url)
        self.assertEqual(github_url_from_remote(url + ".git"), url)
        self.assertEqual(github_url_from_remote("git@github.com:BrunelXian/AbqJobPilot.git"), url)
        self.assertIsNone(github_url_from_remote("https://example.com/BrunelXian/AbqJobPilot.git"))
        self.assertIsNone(github_url_from_remote("git@github.com:../AbqJobPilot.git"))

    def test_app_version_and_agent_reference_are_canonical(self):
        self.assertEqual(__version__, "0.2.0")
        self.assertEqual(tuple(COMMAND_EXAMPLES), SUPPORTED_COMMANDS)
        for name, example in COMMAND_EXAMPLES.items():
            self.assertEqual(parse_agent_command(example)["command"], name)
            self.assertIn(example, AI_INSTRUCTION)
        self.assertIn("capabilities --json", CLI_EXAMPLES)
        self.assertNotIn("solver-start", CLI_EXAMPLES)
        self.assertNotIn('"0.2.0"', (Path(__file__).parents[1] / "abqjobpilot" / "gui_app.py").read_text(encoding="utf-8"))
        self.assertNotIn('"0.2.0"', (Path(__file__).parents[1] / "abqjobpilot" / "api" / "client.py").read_text(encoding="utf-8"))

    def test_success_with_warnings_uses_exact_same_tag_and_keeps_identity(self):
        complete = status_presentation("COMPLETED_OK")
        warned = status_presentation("COMPLETED_WITH_WARNINGS")
        self.assertEqual(complete[1], warned[1])
        self.assertEqual(complete[1], "success")
        self.assertNotEqual(complete[0], warned[0])
        self.assertIn("warnings", warned[0])
        self.assertEqual(status_presentation("COMPLETED", "zh")[1], "success")
        self.assertEqual(status_presentation("COMPLETED_WITH_WARNINGS", "zh")[1], "success")
        self.assertEqual([item["status"] for item in result_display_jobs([
            {"status": "COMPLETED", "queue_id": "canonical"},
            {"status": "COMPLETED_WITH_WARNINGS", "queue_id": "warned"},
        ])], ["COMPLETED", "COMPLETED_WITH_WARNINGS"])
        self.assertEqual([item["status"] for item in queue_display_jobs([
            {"status": "RUNNING", "queue_id": "active"},
        ])], ["RUNNING"])
        for raw in ("FAILED_FATAL", "FULL_RUNNING", "UNKNOWN_INTERRUPTED", "UNKNOWN"):
            self.assertNotEqual(status_presentation(raw)[1], "success")

    def test_filter_preserves_order_and_does_not_modify_records(self):
        jobs = [
            {"queue_id": "one", "status": "QUEUED", "job_name": "A", "batch_name": "batch", "inp_path": "A.inp"},
            {"queue_id": "two", "status": "QUEUED", "job_name": "B", "batch_name": "batch", "inp_path": "B.inp"},
            {"queue_id": "three", "status": "COMPLETED_WITH_WARNINGS", "job_name": "C",
             "batch_name": "other", "warning_count": 1593},
            {"queue_id": "four", "status": "FAILED_FATAL", "job_name": "D",
             "batch_name": "other", "warning_count": 9999},
        ]
        before = json.dumps(jobs)
        self.assertEqual([item["queue_id"] for item in filter_jobs(jobs, batch="batch")], ["one", "two"])
        self.assertEqual([item["queue_id"] for item in filter_jobs(jobs, "b.inp")], ["two"])
        self.assertEqual([item["queue_id"] for item in filter_jobs(jobs, status_filter="warnings")], ["three"])
        self.assertEqual([item["queue_id"] for item in filter_jobs(jobs, status_filter="failed")], ["four"])
        self.assertEqual(json.dumps(jobs), before)

    def test_log_tail_is_bounded_and_chronological(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.msg"
            path.write_text("\n".join(f"line {number:04d}" for number in range(5000)), encoding="utf-8")
            tail = read_log_tail(path, max_bytes=128, max_lines=5)
            self.assertEqual(tail.splitlines(), [f"line {number:04d}" for number in range(4995, 5000)])
            self.assertEqual(read_log_tail(path.with_suffix(".missing")), "")


class TaskWorkspaceGuiTests(unittest.TestCase):
    def test_g2_3_log_access_running_highlight_and_about(self):
        app = self.app
        self.assertEqual(app.title(), "AbqJobPilot")
        self.assertEqual(__version__, "0.2.0")
        help_menu = app.nametowidget(app.menu_bar.entrycget(5, "menu"))
        self.assertEqual(help_menu.entrycget(0, "label"), "About AbqJobPilot")
        help_menu.invoke(0)
        self.assertEqual(app.about_window.title(), "About AbqJobPilot")
        self.assertIn(f"Version {__version__}", app.about_version_label.cget("text"))
        self.assertEqual(app.about_repo_label.cget("text"), STABLE_GITHUB_URL)
        with patch("abqjobpilot.gui_app.webbrowser.open", return_value=True) as browser:
            app.about_open_button.invoke()
            browser.assert_called_once_with(STABLE_GITHUB_URL)
        app.about_copy_button.invoke()
        self.assertEqual(app.clipboard_get(), STABLE_GITHUB_URL)
        app.about_window.destroy()
        app.toggle_language()
        help_menu = app.nametowidget(app.menu_bar.entrycget(5, "menu"))
        self.assertEqual(help_menu.entrycget(0, "label"), "关于 AbqJobPilot")
        help_menu.invoke(0)
        self.assertEqual(app.about_window.title(), "关于 AbqJobPilot")
        self.assertIn(f"版本 {__version__}", app.about_version_label.cget("text"))
        self.assertEqual(app.about_open_button.cget("text"), "打开 GitHub")
        self.assertEqual(app.about_copy_button.cget("text"), "复制链接")
        self.assertEqual(app._menu_label("view_logs"), "查看日志")
        self.assertEqual(app.view_running_button.cget("text"), "查看运行任务")
        app.about_window.destroy()
        app.toggle_language()

        pending = build_queue_record(self.inp_a, 12, 0, "batch", "strategy", "C_pending", True, True, "")
        save_queue([self.a, pending, self.b], runtime_dir=self.runtime)
        (self.external / "B07.msg").write_text("B HISTORICAL MSG\n", encoding="utf-8")
        (self.external / "B07.dat").write_text("B HISTORICAL DAT\n", encoding="utf-8")
        app.refresh_all()
        app.update_idletasks()
        home_before = (app.live_origin_vars["solver"].get(), app.live_origin_vars["console"].get())
        with patch.object(app.runner, "start", side_effect=AssertionError("runner must not start")), \
             patch.object(app, "_post_menu") as post:
            queue_iid = row_iid(pending)
            app.queue_tree.see(queue_iid)
            app.update_idletasks()
            queue_y = app.queue_tree.bbox(queue_iid)[1] + 2
            app._show_queue_menu(SimpleNamespace(y=queue_y))
            queue_menu = post.call_args.args[0]
            queue_labels = [queue_menu.entrycget(i, "label") for i in range(queue_menu.index("end") + 1)
                            if queue_menu.type(i) == "command"]
            self.assertEqual(queue_labels[:2], ["View Details", "View Logs"])
            queue_menu.invoke(1)
            self.assertEqual(app.detail_notebook.select(), str(app.logs_tab))
            self.assertEqual(app.inspection_key[1], pending["queue_id"])
            for source in ("STA", "MSG", "DAT", "LOG"):
                app.log_source_var.set(source)
                app._refresh_log(force=True)
                self.assertIn("Not yet created", app.log_path_var.get())
                self.assertIn("has not been created", app.log_text.get("1.0", "end-1c"))

            result_iid = row_iid(self.b, results=True)
            app.results_tree.see(result_iid)
            app.update_idletasks()
            result_y = app.results_tree.bbox(result_iid)[1] + 2
            app._show_results_menu(SimpleNamespace(y=result_y))
            result_menu = post.call_args.args[0]
            result_labels = [result_menu.entrycget(i, "label") for i in range(result_menu.index("end") + 1)
                             if result_menu.type(i) == "command"]
            self.assertEqual(result_labels[:2], ["View Details", "View Logs"])
            result_menu.invoke(1)
            self.assertEqual(app.inspection_key[1], self.b["queue_id"])
            for source, marker in (("STA", "B HISTORICAL STA"), ("MSG", "B HISTORICAL MSG"),
                                   ("DAT", "B HISTORICAL DAT"), ("LOG", "B log 199")):
                app.log_source_var.set(source)
                app._refresh_log(force=True)
                self.assertIn("Available", app.log_path_var.get())
                self.assertIn(marker, app.log_text.get("1.0", "end-1c"))
                self.assertIn("may have overwritten", app.log_text.get("1.0", "end-1c"))
            self.assertEqual(home_before, (app.live_origin_vars["solver"].get(),
                                           app.live_origin_vars["console"].get()))

        with patch.object(app.runner, "is_running", return_value=True):
            app.refresh_all()
        self.assertEqual(str(app.view_running_button.cget("state")), "normal")
        self.assertEqual(app.view_running_button.cget("style"), "RunningAction.TButton")
        style = ttk.Style(app)
        self.assertEqual(style.lookup("RunningAction.TButton", "background"), "#2563eb")
        self.assertEqual(style.lookup("RunningAction.TButton", "foreground"), "#ffffff")
        app.refresh_all()
        self.assertIn("Status unconfirmed", app.running_summary_var.get())
        self.assertEqual(str(app.view_running_button.cget("state")), "disabled")
        self.assertEqual(app.view_running_button.cget("style"), "TButton")
        jobs = read_queue(self.runtime)
        jobs[0]["status"] = "QUEUED"
        save_queue(jobs, runtime_dir=self.runtime)
        write_json(self.runtime / "live_status.json", {"phase": "IDLE"})
        app.refresh_all()
        self.assertIn("IDLE", app.running_summary_var.get())
        self.assertEqual(str(app.view_running_button.cget("state")), "disabled")
        self.assertEqual(app.view_running_button.cget("style"), "TButton")
        self.assertTrue(self.inp_a.is_file())
        self.assertTrue((self.external / "B07.log").is_file())

    def test_workspace_gui_end_to_end(self):
        self._check_layout_languages_and_no_solver_actions()
        self._check_tabs_success_style_context_and_refresh()
        self._check_operational_dashboard_and_safe_toolbar()
        self._check_agent_menu_and_console()
        self._check_filter_reorder_follow_and_project_switch()
        self._check_requeue_and_delete_record_do_not_start_solver_or_delete_files()
        self._check_queue_scroll_selection_after_insert()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / "default_runtime"
        self.external = self.root / "external"
        self.external.mkdir()
        self.manager = ProjectManager(recent_file=self.root / "recent.json")
        self.inp_a = self.external / "A01.inp"
        self.inp_b = self.external / "B07.inp"
        self.inp_a.write_text("*Heading\n", encoding="utf-8")
        self.inp_b.write_text("*Heading\n", encoding="utf-8")
        self.a = build_queue_record(self.inp_a, 12, 0, "batch", "strategy", "A01", True, True, "")
        self.a.update(status="FULL_RUNNING", phase="FULL_RUNNING")
        self.b = build_queue_record(self.inp_b, 14, 0, "batch", "strategy", "B07", True, True, "")
        self.b.update(status="COMPLETED_WITH_WARNINGS", phase="COMPLETED_WITH_WARNINGS",
                      ended_at="2026-02-01T12:00:00", warning_count=1593)
        (self.external / "A01.log").write_text("A RUNNING\n", encoding="utf-8")
        (self.external / "A01.sta").write_text("A STA RUNNING\n", encoding="utf-8")
        (self.external / "A01.msg").write_text("A MSG RUNNING\n", encoding="utf-8")
        (self.external / "B07.log").write_text("\n".join(f"B log {n}" for n in range(200)), encoding="utf-8")
        (self.external / "B07.sta").write_text("B HISTORICAL STA\n", encoding="utf-8")
        save_queue([self.a, self.b], runtime_dir=self.runtime)
        write_json(self.runtime / "live_status.json", {
            "phase": "FULL_RUNNING", "queue_id": self.a["queue_id"], "current_job": "A01",
            "log_path": str(self.external / "A01.log"),
        })
        patches = (patch.object(config, "RUNTIME_DIR_PATH", self.runtime),
                   patch.object(config, "RUNTIME_DIR", str(self.runtime)),
                   patch.object(config, "QUEUE_FILE", str(self.runtime / "queue.json")),
                   patch.object(config, "LIVE_STATUS_FILE", str(self.runtime / "live_status.json")),
                   patch.object(config, "SETTINGS_FILE", str(self.runtime / "settings.json")),
                   patch("abqjobpilot.gui_app.ProjectManager", return_value=self.manager),
                   patch.object(AbqJobPilotApp, "_read_gpu_text", return_value="--"))
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        try:
            self.app = AbqJobPilotApp()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.addCleanup(self.app.destroy)
        self.app.geometry("1280x800")
        self.app.update_idletasks()

    def _check_tabs_success_style_context_and_refresh(self):
        app = self.app
        self.assertEqual(app.title(), "AbqJobPilot")
        style = ttk.Style(app)
        self.assertEqual(app.results_tree.tag_configure("success")["foreground"], SUCCESS_FOREGROUND)
        self.assertEqual(app.results_tree.tag_configure("success")["background"], SUCCESS_BACKGROUND)
        self.assertEqual(style.lookup("Treeview", "foreground", ("selected",)), "#ffffff")
        self.assertEqual(app.results_tree.item(row_iid(self.b, results=True), "tags"), ("success",))
        self.assertIn("Status unconfirmed", app.running_summary_var.get())
        self.assertEqual(str(app.view_running_button.cget("state")), "disabled")
        self.assertEqual(read_queue(self.runtime)[1]["warning_count"], 1593)
        self.assertEqual(read_queue(self.runtime)[1]["status"], "COMPLETED_WITH_WARNINGS")
        with patch.object(app.runner, "is_running", return_value=True):
            app.refresh_all()
            app.update_idletasks()
            selected = row_iid(self.b, results=True)
            app.results_tree.selection_set(selected)
            app._on_table_select(app.results_tree, app.queue_tree)
            app.open_task_details(self.b["queue_id"])
            self.assertIn("COMPLETED_WITH_WARNINGS", app.overview_text.get("1.0", "end-1c"))
            self.assertIn("1593", app.overview_text.get("1.0", "end-1c"))
            app.detail_notebook.select(app.logs_tab)
            app.log_source_var.set("Console")
            app._refresh_inspection()
            self.assertIn("A01", app.running_summary_var.get())
            self.assertIn("B07", app.inspection_title_var.get())
            self.assertIn("B log 199", app.log_text.get("1.0", "end-1c"))
            self.assertNotIn("A RUNNING", app.log_text.get("1.0", "end-1c"))
            self.assertIn("A STA RUNNING", app.live_log_texts["solver"].get("1.0", "end-1c"))
            self.assertIn("A RUNNING", app.live_log_texts["console"].get("1.0", "end-1c"))
            self.assertNotIn("B log", app.live_log_texts["console"].get("1.0", "end-1c"))
            for _ in range(3):
                app.refresh_all()
            self.assertEqual(app.results_tree.selection(), (selected,))
            self.assertEqual(app.detail_notebook.select(), str(app.logs_tab))
            self.assertEqual(app.log_source_var.get(), "Console")
            self.assertIn("B07", app.inspection_title_var.get())
            app.update_idletasks()
            bbox = app.results_tree.bbox(selected)
            with patch.object(app, "_post_menu") as post_menu:
                app._show_results_menu(SimpleNamespace(y=bbox[1] + 2, x_root=0, y_root=0))
            menu = post_menu.call_args.args[0]
            menu_labels = [menu.entrycget(index, "label") for index in range(menu.index("end") + 1)
                           if menu.type(index) == "command"]
            self.assertIn("Requeue", menu_labels)
            self.assertIn("Delete Result Record", menu_labels)
            self.assertIn("View Details", menu_labels)
            app._open_details_at_event(app.results_tree, SimpleNamespace(y=bbox[1] + 2))
            self.assertIn("B07", app.inspection_title_var.get())
            app.view_running_job()
            self.assertIn("A01", app.inspection_title_var.get())
            newer_result = build_queue_record(self.inp_a, 12, 0, "batch", "strategy", "A03", True, True, "")
            newer_result.update(status="COMPLETED_OK", ended_at="2026-04-01T12:00:00")
            save_queue(read_queue(self.runtime) + [newer_result], runtime_dir=self.runtime)
            app.refresh_all()
            app.update()
            self.assertIn("A01", app.inspection_title_var.get())
            self.assertEqual(app.results_tree.selection(), (selected,))
            save_queue([self.a, self.b], runtime_dir=self.runtime)
            app.refresh_all()
            app.update_idletasks()
            queue_bbox = app.queue_tree.bbox(row_iid(self.a))
            with patch.object(app, "_post_menu") as post_queue:
                app._show_queue_menu(SimpleNamespace(y=queue_bbox[1] + 2, x_root=0, y_root=0))
            queue_menu = post_queue.call_args.args[0]
            queue_labels = [queue_menu.entrycget(index, "label") for index in range(queue_menu.index("end") + 1)
                            if queue_menu.type(index) == "command"]
            self.assertIn("Run Preflight", queue_labels)
            self.assertIn("View Details", queue_labels)
            app.results_tree.selection_set(selected)
            app._on_table_select(app.results_tree, app.queue_tree)
        self.assertTrue(app.queue_tree.winfo_ismapped())
        self.assertTrue(app.results_tree.winfo_ismapped())
        app.results_tree.selection_remove(selected)
        self.assertEqual(app.results_tree.item(selected, "tags"), ("success",))
        app.results_tree.selection_set(selected)

    def _check_operational_dashboard_and_safe_toolbar(self):
        app = self.app
        self.assertEqual(app.live_source_var.get(), "STA")
        self.assertTrue(app.toolbar_buttons["agent_command"].winfo_ismapped())
        with patch("abqjobpilot.gui_app.AgentCommandConsole") as console:
            app.toolbar_buttons["agent_command"].invoke()
            console.assert_called_once()
        app._agent_console = None
        with patch.object(app.runner, "is_running", return_value=True):
            app.refresh_all()
            app.results_tree.selection_set(row_iid(self.b, results=True))
            app._on_table_select(app.results_tree, app.queue_tree)
            app.live_source_var.set("MSG")
            app._refresh_live_logs()
            self.assertIn("A MSG RUNNING", app.live_log_texts["solver"].get("1.0", "end-1c"))
            self.assertIn("B07", app.inspection_title_var.get())
            app.live_source_var.set("STA")
            app._refresh_live_logs()
            app.live_follow_vars["console"].set(False)
            (self.external / "A01.log").write_text("\n".join(f"A line {n}" for n in range(200)), encoding="utf-8")
            app.refresh_all()
            app.live_log_texts["console"].yview_moveto(0)
            (self.external / "A01.log").write_text("\n".join(f"A line {n}" for n in range(220)), encoding="utf-8")
            app.refresh_all()
            self.assertLess(app.live_log_texts["console"].yview()[0], 0.1)
        app.refresh_all()
        self.assertIn("No active job", app.live_origin_vars["console"].get())
        self.assertNotIn("A RUNNING", app.live_log_texts["console"].get("1.0", "end-1c"))
        self.assertIn("Local machine", app.resource_line_var.get())
        self.assertTrue(app.resource_button.winfo_ismapped())
        jobs = read_queue(self.runtime)
        jobs[0].update(status="QUEUED", phase="QUEUED")
        save_queue(jobs, runtime_dir=self.runtime)
        with patch.object(app.runner, "start", return_value={"ok": False, "message": "fake"}) as start, \
             patch.object(app.runner, "request_stop_after_current", return_value={"message": "fake"}) as stop, \
             patch("abqjobpilot.gui_app.messagebox.askyesno", return_value=True), \
             patch("abqjobpilot.gui_app.messagebox.showwarning"), \
             patch("abqjobpilot.gui_app.messagebox.showinfo"):
            app.toolbar_button_labels["start_queue"].event_generate("<Button-1>")
            app.toolbar_buttons["stop_after_current"].invoke()
            start.assert_called_once()
            stop.assert_called_once()
        self.assertEqual(app.queue_tree.get_children()[0], row_iid(self.a))

    def _check_agent_menu_and_console(self):
        app = self.app
        self.assertEqual(app.title(), "AbqJobPilot")
        labels = [app.menu_bar.entrycget(index, "label") for index in range(app.menu_bar.index("end") + 1)]
        self.assertEqual(labels, ["Project", "Task", "View", "Tools", "Agent", "Help"])
        self.assertEqual(app.agent_menu.entrycget(0, "label"), "Agent Command Console")
        app.toolbar_buttons["agent_command"].invoke()
        console = app._agent_console
        self.assertIsNotNone(console)
        app.agent_menu.invoke(0)
        self.assertIs(app._agent_console, console)
        self.assertEqual(console.title(), "Agent Command Console")
        self.assertEqual(console.instruction_frame.cget("text"), "AI Instruction")
        self.assertEqual(console.commands_frame.cget("text"), "Commands")
        self.assertEqual(console.output_frame.cget("text"), "Output")
        self.assertFalse(console.reference_body.winfo_ismapped())
        console.reference_toggle.invoke()
        app.update_idletasks()
        self.assertTrue(console.reference_body.winfo_ismapped())
        console.copy_ai_prompt()
        self.assertEqual(console.clipboard_get(), AI_INSTRUCTION)
        with patch("abqjobpilot.gui_app.messagebox.showinfo") as show:
            app.agent_menu.invoke(3)
            self.assertEqual(json.loads(show.call_args.args[1]),
                             AbqJobPilotClient(runtime_dir=config.RUNTIME_DIR).capabilities())
        with patch.object(app, "_open_job_text") as open_text:
            app.agent_menu.invoke(5)
            self.assertEqual(Path(open_text.call_args.args[0]).name, "ABQJOBPILOT_PUBLIC_API.md")
        app.agent_menu.invoke(2)
        self.assertEqual(app.clipboard_get(), CLI_EXAMPLES)
        app.agent_menu.invoke(1)
        self.assertEqual(app.clipboard_get(), AI_INSTRUCTION)
        app.toggle_language()
        self.assertEqual(app.menu_bar.entrycget(4, "label"), "智能体")
        self.assertEqual(app.toolbar_buttons["agent_command"].cget("text"), "智能体命令")
        self.assertEqual(console.title(), "智能体命令控制台")
        for key, button in console.buttons.items():
            self.assertEqual(button.cget("text"), AGENT_UI_STRINGS["zh"][key])
        self.assertIn("enqueue --inp", console.reference_body.cget("text"))
        self.assertNotIn("代理", console.title())
        console.input_text.insert("1.0", "help")
        console.run_commands()
        self.assertIn("支持的命令：", console.output.get("1.0", "end-1c"))
        self.assertIn("enqueue-folder", console.output.get("1.0", "end-1c"))
        with patch.object(console, "clipboard_get", side_effect=tk.TclError("empty")), \
             patch.object(console, "run_commands") as run:
            console.paste_and_run()
            run.assert_not_called()
        console.destroy()
        app._agent_console = None
        app.toggle_language()

    def _check_requeue_and_delete_record_do_not_start_solver_or_delete_files(self):
        app = self.app
        jobs = read_queue(self.runtime)
        jobs[0].update(status="QUEUED", phase="QUEUED")
        save_queue(jobs, runtime_dir=self.runtime)
        write_json(self.runtime / "live_status.json", {"phase": "IDLE", "current_job": "old A01"})
        app.search_var.set("")
        app.refresh_all()
        self.assertIn("idle", app.running_summary_var.get().lower())
        self.assertNotIn("old A01", app.running_summary_var.get())
        with patch.object(app.runner, "start", side_effect=AssertionError("solver must not start")), \
             patch("abqjobpilot.gui_app.messagebox.showinfo"):
            app._results_context_action("requeue", self.b["queue_id"])
        queued = read_queue(self.runtime)
        self.assertEqual(len(queued), 4)
        self.assertEqual(queued[-1]["status"], "QUEUED")
        self.assertEqual(queued[-1]["inp_path"], str(self.inp_b))
        with patch("abqjobpilot.gui_app.messagebox.askyesno", return_value=True), \
             patch("abqjobpilot.gui_app.messagebox.showinfo"):
            app.clear_selected_result(self.b["queue_id"])
        self.assertTrue(self.inp_b.is_file())
        self.assertTrue((self.external / "B07.log").is_file())
        self.assertNotIn(self.b["queue_id"], [item["queue_id"] for item in read_queue(self.runtime)])

    def _check_queue_scroll_selection_after_insert(self):
        app = self.app
        jobs = read_queue(self.runtime)
        extra = [build_queue_record(self.inp_a, 12, 0, "batch", "strategy", f"Q_{index:03d}",
                                    True, True, "") for index in range(60)]
        save_queue(jobs + extra, runtime_dir=self.runtime)
        app.refresh_all()
        app.update_idletasks()
        selected = row_iid(extra[30])
        app.queue_tree.selection_set(selected)
        app._on_table_select(app.queue_tree, app.results_tree)
        app.queue_tree.yview_moveto(0.5)
        before = app.queue_tree.yview()[0]
        newer = build_queue_record(self.inp_a, 12, 0, "batch", "strategy", "Q_new", True, True, "")
        save_queue([newer] + jobs + extra, runtime_dir=self.runtime)
        app.refresh_all()
        self.assertEqual(app.queue_tree.selection(), (selected,))
        self.assertLess(abs(app.queue_tree.yview()[0] - before), 0.1)
        self.assertEqual(app.queue_tree.item(app.queue_tree.get_children()[0], "values")[0], "1")

    def _check_filter_reorder_follow_and_project_switch(self):
        app = self.app
        selected = row_iid(self.b, results=True)
        app.results_tree.selection_set(selected)
        app._on_table_select(app.results_tree, app.queue_tree)
        app.open_task_details(self.b["queue_id"])
        app.detail_notebook.select(app.logs_tab)
        app.log_source_var.set("Console")
        app._refresh_inspection()
        app.log_follow_var.set(False)
        app.log_text.yview_moveto(0)
        (self.external / "B07.log").write_text("\n".join(f"B log {n}" for n in range(210)), encoding="utf-8")
        app.refresh_all()
        self.assertLess(app.log_text.yview()[0], 0.1)
        newer = build_queue_record(self.inp_a, 12, 0, "batch", "strategy", "A02", True, True, "")
        newer.update(status="COMPLETED_OK", ended_at="2026-03-01T12:00:00")
        save_queue([self.a, self.b, newer], runtime_dir=self.runtime)
        app.refresh_all()
        self.assertEqual(app.results_tree.get_children()[0], row_iid(newer, results=True))
        self.assertEqual(app.results_tree.selection(), (selected,))
        app.search_var.set("A02")
        self.assertEqual(app.results_tree.get_children(), (row_iid(newer, results=True),))
        self.assertIn("hidden", app.filtered_hint_var.get())
        self.assertIn("B07", app.inspection_title_var.get())
        app._populate_detail_more_menu()
        labels = [app.detail_more_menu.entrycget(index, "label") for index in range(app.detail_more_menu.index("end") + 1)]
        delete_index = labels.index("Delete Result Record")
        self.assertEqual(app.detail_more_menu.entrycget(delete_index, "state"), "disabled")
        project = self.manager.create_project(self.root / "other_project", "Other")
        app.open_project(project.root)
        self.assertIsNone(app.inspection_key)
        self.assertNotIn("B07", app.log_text.get("1.0", "end-1c"))
        self.assertIn("No active job", app.live_origin_vars["console"].get())
        self.assertEqual(len(app.results_tree.get_children()), 0)
        app.close_project()
        self.assertIsNone(self.manager.current)

    def _check_layout_languages_and_no_solver_actions(self):
        app = self.app
        for width, height in ((1280, 800), (1440, 900)):
            app.geometry(f"{width}x{height}")
            app.update_idletasks()
            self.assertGreater(app.queue_tree.winfo_width(), 400)
            self.assertGreater(app.results_tree.winfo_width(), 500)
            self.assertLess(abs(app.queue_frame.winfo_width() - app.results_frame.winfo_width()), 24)
            self.assertGreater(app.live_log_texts["solver"].winfo_width(), 400)
            self.assertGreater(app.live_log_texts["console"].winfo_width(), 400)
            self.assertTrue(app.status_light.winfo_ismapped())
            self.assertTrue(app.resource_button.winfo_ismapped())
            self.assertLess(app.toolbar_button_labels["start_queue"].winfo_rootx() +
                            app.toolbar_button_labels["start_queue"].winfo_width(),
                            app.winfo_rootx() + app.winfo_width())
        original_table_sash = app.table_pane.sashpos(0)
        app.table_pane.sashpos(0, original_table_sash + 30)
        app.update_idletasks()
        self.assertGreater(app.table_pane.sashpos(0), original_table_sash)
        app.table_pane.event_generate("<ButtonRelease-1>", x=app.table_pane.sashpos(0), y=20)
        user_fraction = app._table_split_fraction
        app.geometry("1280x800")
        app.update_idletasks()
        self.assertLess(abs(app.table_pane.sashpos(0) / app.table_pane.winfo_width() - user_fraction), 0.02)
        original_log_sash = app.live_log_pane.sashpos(0)
        app.live_log_pane.sashpos(0, original_log_sash + 30)
        app.update_idletasks()
        self.assertGreater(app.live_log_pane.sashpos(0), original_log_sash)
        with patch.object(app.runner, "is_running", return_value=True):
            write_json(self.runtime / "live_status.json", {
                "phase": "FULL_RUNNING", "queue_id": self.a["queue_id"],
                "current_job": "A_very_long_engineering_job_name_" * 4,
                "step": "49", "increment": "38", "elapsed_time": "751",
            })
            app.geometry("1280x800")
            app.refresh_all()
            app.update_idletasks()
            self.assertLessEqual(app.resource_button.winfo_rootx() + app.resource_button.winfo_width(),
                                 app.winfo_rootx() + app.winfo_width())
            self.assertLessEqual(app.running_summary_label.winfo_rootx() + app.running_summary_label.winfo_width(),
                                 app.resource_button.winfo_rootx())
            self.assertIn("Step 49", app.running_summary_var.get())
        write_json(self.runtime / "live_status.json", {
            "phase": "FULL_RUNNING", "queue_id": self.a["queue_id"], "current_job": "A01",
            "log_path": str(self.external / "A01.log"),
        })
        app.refresh_all()
        app.open_task_details(self.b["queue_id"])
        self.assertFalse(app._details_collapsed)
        app._toggle_details()
        self.assertTrue(app._details_collapsed)
        app.toggle_language()
        self.assertIn("队列", app.queue_count_var.get())
        self.assertEqual(app.results_tree.item(row_iid(self.b, results=True), "tags"), ("success",))
        self.assertIn("文件引用", app.detail_notebook.tab(app.files_tab, "text"))
        app.toggle_language()
        app._render_history_rows([
            {"run_id": "r_done", "attempt_no": 2, "status": "COMPLETED", "raw_status": "COMPLETED_OK"},
            {"run_id": "r_warn", "attempt_no": 1, "status": "COMPLETED", "raw_status": "COMPLETED_WITH_WARNINGS"},
        ])
        self.assertEqual(app.history_tree.item("r_done", "tags"), ("success",))
        self.assertEqual(app.history_tree.item("r_warn", "tags"), ("success",))
        self.assertNotEqual(app.history_tree.item("r_done", "values")[1],
                            app.history_tree.item("r_warn", "values")[1])
        with patch.object(app.runner, "start", side_effect=AssertionError("solver start must not run")):
            app.search_var.set("B07")
            app.refresh_all()
        self.assertEqual(len(read_queue(self.runtime)), 2)
        app.search_var.set("")


if __name__ == "__main__":
    unittest.main()
