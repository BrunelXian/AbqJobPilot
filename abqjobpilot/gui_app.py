"""Main Tkinter GUI for abqjobpilot."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import logging
import subprocess
import tkinter as tk
import time
import webbrowser
import zipfile
from pathlib import Path
from types import SimpleNamespace
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

from . import __version__, config
from .app_metadata import STABLE_GITHUB_URL
from .command_console import AI_INSTRUCTION, CLI_EXAMPLES, AgentCommandConsole
from .gui_presentation import (SUCCESS_BACKGROUND, SUCCESS_FOREGROUND, filter_jobs,
                               read_log_tail, status_presentation)
from .gui_table_state import queue_display_jobs, result_display_jobs, restore_iids, row_iid, selected_job_id
from .queue_store import (
    add_folder_to_queue,
    add_inp_job_to_queue,
    apply_resources_to_queued_jobs,
    init_storage,
    load_queue,
    mark_job_skipped,
    move_queued_job,
    remove_queued_job,
    remove_queued_jobs,
    remove_result_job,
    remove_result_jobs,
    requeue_result_job,
)
from .api import AbqJobPilotClient, JobRequest
from .api.status_reader import expected_paths
from .project import ProjectInfo, ProjectManager, export_project_archive, import_legacy_runtime, import_project_archive
from .project.manager import ensure_default_projects_root
from .database import DatabaseFailure, ProjectHistoryRepository, sync_history_from_runtime
from .status_codes import normalize_status
from .runner_core import QueueRunner
from .settings_store import load_settings, save_settings
from .utils import format_bytes, now_iso, open_folder, read_json, tail_text, write_json


QUEUE_COLUMNS = ("index", "status", "batch", "strategy", "job", "cpus", "gpus", "created", "inp")
RESULT_COLUMNS = ("status", "batch", "strategy", "job", "started", "ended", "duration", "odb", "warnings", "fatal")
STA_HEADER = "STEP  INC  ATT  CUT  EQUIL  ITER  TOTAL_TIME  STEP_TIME  TIME_INC"

COLORS = {
    "bg": "#f4f7fb",
    "panel": "#ffffff",
    "panel_border": "#d9e2ef",
    "text": "#172033",
    "muted": "#64748b",
    "accent": "#2563eb",
    "accent_dark": "#1d4ed8",
    "accent_soft": "#dbeafe",
    "success": "#16a34a",
    "warning": "#d97706",
    "danger": "#dc2626",
    "table_head": "#eaf0f8",
    "table_alt": "#f8fafc",
}

MENU_LABELS = {
    "open_inp": ("Open INP", "打开 INP"),
    "open_inp_folder": ("Open INP Folder", "打开 INP 文件夹"),
    "copy_inp": ("Copy INP Path", "复制 INP 路径"),
    "copy_name": ("Copy Job Name", "复制 Job 名称"),
    "refresh": ("Refresh", "刷新"),
    "preflight": ("Run Preflight", "运行预检"),
    "output_folder": ("Locate Expected Output Folder", "打开预期输出文件夹"),
    "top": ("Move to Top", "移到队首"),
    "up": ("Move Up", "上移"),
    "down": ("Move Down", "下移"),
    "remove": ("Remove from Queue", "从队列移除"),
    "work_folder": ("Open Working Folder", "打开工作文件夹"),
    "odb_folder": ("Open ODB Folder", "打开 ODB 文件夹"),
    "sta": ("Open STA", "打开 STA"),
    "msg": ("Open MSG", "打开 MSG"),
    "dat": ("Open DAT", "打开 DAT"),
    "log": ("Open LOG", "打开 LOG"),
    "copy_id": ("Copy Job ID", "复制 Job ID"),
    "copy_odb": ("Copy ODB Path", "复制 ODB 路径"),
    "refresh_status": ("Refresh Status", "刷新状态"),
    "locate_outputs": ("Locate Outputs", "定位输出文件"),
    "requeue": ("Requeue", "重新入队"),
    "delete_result": ("Delete Result Record", "删除结果记录"),
    "failure_summary": ("Show Failure Summary", "查看失败摘要"),
    "run_history": ("View Run History", "查看运行历史"),
    "view_details": ("View Details", "查看详情"),
    "view_logs": ("View Logs", "查看日志"),
    "select_all": ("Select All", "全选"),
    "clear_selection": ("Clear Selection", "取消选择"),
    "remove_selected": ("Remove Selected Queue Records", "移除选中队列记录"),
    "delete_selected": ("Delete Selected Result Records", "删除选中结果记录"),
}


class BasicSettingsDialog(tk.Toplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.title("Basic Settings")
        self.geometry("580x390")
        self.resizable(False, False)
        self.on_saved = on_saved
        settings = load_settings()

        self.abaqus_cmd_var = tk.StringVar(value=settings["abaqus_cmd"])
        self.cpus_var = tk.IntVar(value=settings["default_cpus"])
        self.use_gpu_var = tk.BooleanVar(value=settings["use_gpu"])
        self.gpus_var = tk.IntVar(value=settings["default_gpus"] if settings["default_gpus"] else 1)
        self.datacheck_var = tk.BooleanVar(value=settings["run_datacheck"])
        self.full_run_var = tk.BooleanVar(value=settings["run_full"])
        self.auto_shutdown_var = tk.BooleanVar(value=settings["auto_shutdown_enabled"])
        self.auto_shutdown_minutes_var = tk.IntVar(value=settings["auto_shutdown_idle_minutes"])
        self.apply_queued_var = tk.BooleanVar(value=True)

        self.columnconfigure(1, weight=1)
        self._build_widgets()
        self.transient(master)
        self.grab_set()

    def _build_widgets(self) -> None:
        pad = {"padx": 10, "pady": 6}
        ttk.Label(self, text="Abaqus command").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(self, textvariable=self.abaqus_cmd_var).grid(row=0, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(self, text="Default CPUs").grid(row=1, column=0, sticky="w", **pad)
        ttk.Spinbox(self, from_=1, to=128, textvariable=self.cpus_var, width=8).grid(row=1, column=1, sticky="w", **pad)
        preset_frame = ttk.Frame(self)
        preset_frame.grid(row=1, column=2, sticky="w", **pad)
        ttk.Button(preset_frame, text="12", width=4, command=lambda: self.cpus_var.set(12)).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(preset_frame, text="14", width=4, command=lambda: self.cpus_var.set(14)).grid(row=0, column=1)

        ttk.Checkbutton(self, text="Use GPU", variable=self.use_gpu_var).grid(row=2, column=0, sticky="w", **pad)
        ttk.Label(self, text="GPUs").grid(row=2, column=1, sticky="w", **pad)
        ttk.Spinbox(self, from_=0, to=8, textvariable=self.gpus_var, width=8).grid(row=2, column=2, sticky="w", **pad)

        ttk.Checkbutton(self, text="Run datacheck first", variable=self.datacheck_var).grid(row=3, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(self, text="Run full analysis", variable=self.full_run_var).grid(row=4, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(
            self,
            text="Auto shutdown after queue is done and system is idle",
            variable=self.auto_shutdown_var,
        ).grid(row=5, column=0, columnspan=3, sticky="w", **pad)
        ttk.Label(self, text="Idle minutes before shutdown").grid(row=6, column=0, sticky="w", **pad)
        ttk.Spinbox(self, from_=1, to=240, textvariable=self.auto_shutdown_minutes_var, width=8).grid(row=6, column=1, sticky="w", **pad)
        ttk.Label(self, text="Default: 5 minutes. Windows shows a 60-second shutdown warning.").grid(
            row=7, column=0, columnspan=3, sticky="w", **pad
        )
        ttk.Checkbutton(
            self,
            text="Apply these values to existing QUEUED jobs",
            variable=self.apply_queued_var,
        ).grid(row=8, column=0, columnspan=3, sticky="w", **pad)

        button_frame = ttk.Frame(self)
        button_frame.grid(row=9, column=0, columnspan=3, sticky="e", padx=10, pady=(18, 10))
        ttk.Button(button_frame, text="Save", command=self.save).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(button_frame, text="Cancel", command=self.destroy).grid(row=0, column=1)

    def save(self) -> None:
        try:
            settings = save_settings(
                {
                    "abaqus_cmd": self.abaqus_cmd_var.get().strip() or config.ABAQUS_CMD,
                    "default_cpus": int(self.cpus_var.get()),
                    "use_gpu": bool(self.use_gpu_var.get()),
                    "default_gpus": int(self.gpus_var.get()) if self.use_gpu_var.get() else 0,
                    "run_datacheck": bool(self.datacheck_var.get()),
                    "run_full": bool(self.full_run_var.get()),
                    "auto_shutdown_enabled": bool(self.auto_shutdown_var.get()),
                    "auto_shutdown_idle_minutes": int(self.auto_shutdown_minutes_var.get()),
                }
            )
        except (TypeError, ValueError) as exc:
            messagebox.showerror("Settings", f"Invalid settings: {exc}")
            return
        if self.apply_queued_var.get():
            apply_resources_to_queued_jobs(
                settings["default_cpus"],
                settings["default_gpus"] if settings["use_gpu"] else 0,
                settings["run_datacheck"],
                settings["run_full"],
            )
        if self.on_saved:
            self.on_saved(settings)
        self.destroy()


class AbqJobPilotApp(tk.Tk):
    def __init__(self):
        super().__init__()
        init_storage()
        self.title("AbqJobPilot")
        self._apply_icon()
        self._set_initial_geometry()
        self.configure(background=COLORS["bg"])
        self.job_by_id: dict[str, dict] = {}
        self._rendered_rows: dict[str, list[tuple]] = {}
        self._restoring_table_selection = False
        self._selection_restore_after_id: str | None = None
        self._table_split_fraction = 0.5
        self._table_split_width = 0
        self._table_split_pending = False
        self._all_jobs: list[dict] = []
        self._last_selected_tree: ttk.Treeview | None = None
        self.inspection_key: tuple[str, str] | None = None
        self.runner_context: dict = {}
        self._verified_running = False
        self._live_status: dict = {}
        self._rendered_inspection: tuple | None = None
        self._rendered_log: tuple | None = None
        self._details_collapsed = True
        self.search_var = tk.StringVar()
        self.queue_search_var = tk.StringVar()
        self.filter_status_code = "all"
        self.filter_batch: str | None = None
        self.log_source_var = tk.StringVar(value="STA")
        self.log_follow_var = tk.BooleanVar(value=True)
        self.live_source_var = tk.StringVar(value="STA")
        self.live_follow_vars = {"solver": tk.BooleanVar(value=True), "console": tk.BooleanVar(value=True)}
        self._live_log_signatures: dict[str, tuple] = {}
        self.running_summary_var = tk.StringVar()
        self.queue_count_var = tk.StringVar()
        self.results_count_var = tk.StringVar()
        self.live_origin_vars = {"solver": tk.StringVar(), "console": tk.StringVar()}
        self.inspection_title_var = tk.StringVar()
        self.filtered_hint_var = tk.StringVar()
        self.log_path_var = tk.StringVar()
        self.resource_line_var = tk.StringVar()
        self.runner = QueueRunner()
        self.project_manager = ProjectManager()
        self.project_name_var = tk.StringVar()
        self.project_controls: dict[str, ttk.Button] = {}
        self._agent_console: AgentCommandConsole | None = None
        self._history_signature: tuple | None = None
        self.lang = "en"
        self.toolbar_buttons: dict[str, ttk.Button] = {}
        self.toolbar_button_labels: dict[str, tk.Label] = {}
        self.frames: dict[str, ttk.LabelFrame] = {}
        self.status_label_widgets: dict[str, ttk.Label] = {}
        self.status_vars: dict[str, tk.StringVar] = {}
        self.cpu_percent_var = tk.StringVar(value="--%")
        self.memory_percent_var = tk.StringVar(value="--")
        self.gpu_percent_var = tk.StringVar(value="--")
        self._last_cpu_times: tuple[int, int, int] | None = None
        self._runner_was_running = False
        self._queue_completed_monotonic: float | None = None
        self._shutdown_requested = False

        self._configure_styles()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self._build_widgets()
        self.refresh_all()
        self._poll_after_id = self.after(config.POLL_INTERVAL_SECONDS * 1000, self._poll_refresh)

    def destroy(self) -> None:
        for key in ("_poll_after_id", "_selection_restore_after_id"):
            callback_id = getattr(self, key, None)
            if not callback_id:
                continue
            try:
                self.after_cancel(callback_id)
            except tk.TclError:
                pass
            setattr(self, key, None)
        super().destroy()

    def _apply_icon(self) -> None:
        icon_path = Path(config.APP_ICON_FILE)
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except tk.TclError:
                pass

    def _set_initial_geometry(self) -> None:
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(1760, max(1024, int(screen_width * 0.92)), screen_width)
        height = min(980, max(700, int(screen_height * 0.88)), screen_height)
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(1024, 640)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.option_add("*Font", "{Segoe UI} 10")
        self.option_add("*TCombobox*Listbox.font", "{Segoe UI} 10")

        style.configure(".", font=("Segoe UI", 10), background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["panel"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
        style.configure("ResourceValue.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI Semibold", 11))
        style.configure("TLabelframe", background=COLORS["panel"], bordercolor=COLORS["panel_border"], relief="solid")
        style.configure("TLabelframe.Label", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI Semibold", 10))

        style.configure("TButton", padding=(12, 6), background="#ffffff", foreground=COLORS["text"], bordercolor="#cbd5e1")
        style.map(
            "TButton",
            background=[("active", "#f1f5f9"), ("pressed", "#e2e8f0")],
            bordercolor=[("active", COLORS["accent"])],
        )
        style.configure("RunningAction.TButton", padding=(12, 6), background=COLORS["accent"],
                        foreground="#ffffff", bordercolor=COLORS["accent_dark"])
        style.map("RunningAction.TButton",
                  background=[("active", COLORS["accent_dark"]), ("pressed", COLORS["accent_dark"])],
                  foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])
        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground=COLORS["text"], rowheight=28, bordercolor=COLORS["panel_border"])
        style.configure("Treeview.Heading", background=COLORS["table_head"], foreground=COLORS["text"], font=("Segoe UI Semibold", 10), padding=(6, 6))
        style.map("Treeview", background=[("selected", COLORS["accent"])], foreground=[("selected", "#ffffff")])
        style.configure("Workspace.TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("Workspace.TNotebook.Tab", padding=(16, 8))
        style.configure("Vertical.TScrollbar", background="#e2e8f0", troughcolor="#f8fafc", bordercolor="#e2e8f0")
        style.configure("Horizontal.TScrollbar", background="#e2e8f0", troughcolor="#f8fafc", bordercolor="#e2e8f0")

    def _build_widgets(self) -> None:
        self._build_toolbar()
        self._build_status_area(self)

        self.workspace_pane = ttk.PanedWindow(self, orient="vertical")
        self.workspace_pane.grid(row=2, column=0, sticky="nsew", padx=12, pady=(2, 0))
        table_workspace = ttk.Frame(self.workspace_pane)
        table_workspace.rowconfigure(0, weight=1)
        table_workspace.columnconfigure(0, weight=1)
        self.workspace_pane.add(table_workspace, weight=3)
        self.table_pane = ttk.PanedWindow(table_workspace, orient="horizontal")
        self.table_pane.grid(row=0, column=0, sticky="nsew")
        self.table_pane.bind("<Configure>", self._on_table_pane_resize)
        self.table_pane.bind("<ButtonRelease-1>", self._remember_table_split, add="+")
        self._build_queue_area(self.table_pane)
        self._build_results_area(self.table_pane)
        self._build_live_logs(self.workspace_pane)

        self.detail_window = tk.Toplevel(self)
        self.detail_window.withdraw()
        self.detail_window.title("Task Details")
        self.detail_window.geometry("1050x650")
        self.detail_window.rowconfigure(0, weight=1)
        self.detail_window.columnconfigure(0, weight=1)
        self.detail_window.protocol("WM_DELETE_WINDOW", self._hide_details)
        self._build_details_area(self.detail_window)
        self._build_footer()
        self.bind("<F5>", lambda _event: self.refresh_all())
        self.search_var.trace_add("write", lambda *_args: self._on_search_change())
        self.queue_search_var.trace_add("write", lambda *_args: self._on_search_change())
        self._clear_inspection_view()

    def _on_table_pane_resize(self, event) -> None:
        if event.width == self._table_split_width:
            return
        self._table_split_width = event.width
        if not self._table_split_pending:
            self._table_split_pending = True
            self.after_idle(self._apply_table_split)

    def _apply_table_split(self) -> None:
        self._table_split_pending = False
        width = self.table_pane.winfo_width()
        if width > 100:
            self.table_pane.sashpos(0, round(width * self._table_split_fraction))

    def _remember_table_split(self, event) -> None:
        width = self.table_pane.winfo_width()
        if width > 100 and abs(event.x - self.table_pane.sashpos(0)) <= 12:
            self._table_split_fraction = self.table_pane.sashpos(0) / width

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self, padding=(12, 9, 12, 5))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(5, weight=1)
        self.project_dropdown_menu = tk.Menu(self, tearoff=False)
        self.project_dropdown = ttk.Menubutton(toolbar, textvariable=self.project_name_var,
                                               menu=self.project_dropdown_menu, width=28)
        self.project_dropdown.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.add_menu = tk.Menu(self, tearoff=False)
        self.add_button = ttk.Menubutton(toolbar, menu=self.add_menu)
        self.add_button.grid(row=0, column=1, sticky="w", padx=(0, 18))
        self._make_button(toolbar, "agent_command", self.open_agent_console, 2)
        self._make_primary_button(toolbar, "start_queue", self.start_queue, 3)
        self._make_button(toolbar, "stop_after_current", self.stop_after_current, 4)
        self._build_menus()
        self._update_project_label()

    def _fill_project_menu(self, menu: tk.Menu) -> None:
        menu.delete(0, "end")
        labels = self._texts()["project_menu"]
        for key, action in (("new", self.new_project), ("open", self.open_project_dialog),
                            ("close", self.close_project), ("folder", self.open_project_folder)):
            menu.add_command(label=labels[key], command=action)
        menu.add_separator()
        recent = tk.Menu(menu, tearoff=False, postcommand=lambda: self._populate_recent_menu(recent))
        # Seed native cascades before posting; an empty submenu may not post on Windows.
        self._populate_recent_menu(recent)
        menu.add_cascade(label=labels["recent"], menu=recent)
        menu.add_separator()
        for key, action in (("export", self.export_project_dialog), ("import", self.import_project_dialog),
                            ("legacy", self.import_legacy_dialog)):
            menu.add_command(label=labels[key], command=action)

    def _build_menus(self) -> None:
        labels = self._texts()["menus"]
        menu_bar = tk.Menu(self, tearoff=False)
        project_menu = tk.Menu(menu_bar, tearoff=False)
        self._fill_project_menu(project_menu)
        self._fill_project_menu(self.project_dropdown_menu)
        menu_bar.add_cascade(label=labels["project"], menu=project_menu)

        self.add_menu.delete(0, "end")
        self.add_menu.add_command(label=labels["add_inp"], command=self.add_inp)
        self.add_menu.add_command(label=labels["add_folder"], command=self.add_folder)
        task_menu = tk.Menu(menu_bar, tearoff=False)
        task_menu.add_command(label=labels["add_inp"], command=self.add_inp)
        task_menu.add_command(label=labels["add_folder"], command=self.add_folder)
        task_menu.add_separator()
        task_menu.add_command(label=labels["view_details"], command=self.open_selected_details)
        task_menu.add_command(label=labels["skip"], command=self.skip_selected)
        task_menu.add_command(label=labels["requeue"], command=lambda: self._selected_result_action("requeue"))
        task_menu.add_command(label=labels["delete_result"], command=self.clear_selected_result)
        menu_bar.add_cascade(label=labels["task"], menu=task_menu)

        view_menu = tk.Menu(menu_bar, tearoff=False)
        view_menu.add_command(label=labels["queue"], command=lambda: self.queue_tree.focus_set())
        view_menu.add_command(label=labels["results"], command=lambda: self.results_tree.focus_set())
        view_menu.add_command(label=labels["refresh"], command=self.refresh_all, accelerator="F5")
        menu_bar.add_cascade(label=labels["view"], menu=view_menu)

        tools_menu = tk.Menu(menu_bar, tearoff=False)
        tools_menu.add_command(label=labels["settings"], command=self.open_settings)
        tools_menu.add_command(label=labels["language"], command=self.toggle_language)
        tools_menu.add_command(label=labels["task_manager"], command=self.open_task_manager_performance)
        menu_bar.add_cascade(label=labels["tools"], menu=tools_menu)

        agent_menu = tk.Menu(menu_bar, tearoff=False)
        agent_labels = self._texts()["agent_menu"]
        agent_menu.add_command(label=agent_labels["console"], command=self.open_agent_console)
        agent_menu.add_command(label=agent_labels["instruction"], command=lambda: self._copy_text(AI_INSTRUCTION))
        agent_menu.add_command(label=agent_labels["examples"], command=lambda: self._copy_text(CLI_EXAMPLES))
        agent_menu.add_command(label=agent_labels["capabilities"], command=self.show_agent_capabilities)
        agent_menu.add_separator()
        agent_menu.add_command(label=agent_labels["docs"], command=self.open_automation_docs)
        agent_menu.add_command(label=agent_labels["about"], command=self.show_automation_about)
        menu_bar.add_cascade(label=labels["agent_top"], menu=agent_menu)
        self.agent_menu = agent_menu

        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label=labels["about_app"], command=self.show_help)
        help_menu.add_command(label=labels["exit"], command=self.destroy)
        menu_bar.add_cascade(label=labels["help"], menu=help_menu)
        self.configure(menu=menu_bar)
        self.menu_bar = menu_bar
        self.add_button.configure(text=labels["add_task"])

    def _update_project_label(self) -> None:
        project = self.project_manager.current
        prefix = "项目" if self.lang == "zh" else "Project"
        name = project.name if project else ("无项目（默认运行目录）" if self.lang == "zh" else "No Project (default runtime)")
        self.project_name_var.set(f"{prefix}: {name}")

    def _can_switch_project(self) -> bool:
        if self.runner.is_running():
            messagebox.showwarning("Project", "A queue job is running. Switch projects after the runner stops.")
            return False
        if self._agent_console is not None and self._agent_console.winfo_exists():
            messagebox.showwarning("Project", "Close Agent Command Console before switching projects.")
            return False
        return True

    def _activate_project(self, project: ProjectInfo | None) -> None:
        self._hide_details()
        config.use_runtime_dir(project.runtime_dir if project else None)
        self.project_manager.current = project
        self._runner_was_running = False
        self._queue_completed_monotonic = None
        self._shutdown_requested = False
        self.job_by_id.clear()
        self._all_jobs.clear()
        self.inspection_key = None
        self._last_selected_tree = None
        self.runner_context = {}
        self._verified_running = False
        self._rendered_inspection = None
        self._rendered_log = None
        self._live_log_signatures.clear()
        self._rendered_rows.clear()
        self._history_signature = None
        self.queue_tree.delete(*self.queue_tree.get_children())
        self.results_tree.delete(*self.results_tree.get_children())
        self._clear_inspection_view()
        for side, widget in self.live_log_texts.items():
            self.live_origin_vars[side].set("")
            self._set_text(widget, "", follow=False)
        self._update_project_label()
        self.refresh_all()

    def open_project(self, root_dir: str | Path) -> None:
        if not self._can_switch_project():
            return
        project = self.project_manager.open_project(root_dir)
        self._activate_project(project)

    def close_project(self) -> None:
        if self.project_manager.current is None or not self._can_switch_project():
            return
        self._activate_project(None)

    def _new_project_destination(self, title: str) -> tuple[Path, str] | None:
        parent = filedialog.askdirectory(parent=self, title=title,
                                         initialdir=str(ensure_default_projects_root()))
        if not parent:
            return None
        name = simpledialog.askstring("Project", "New project folder and name:", parent=self)
        if not name:
            return None
        name = name.strip()
        if not name or name in {".", ".."} or Path(name).name != name or any(char in name for char in '<>:"/\\|?*'):
            raise ValueError("Enter a single valid folder name")
        return Path(parent) / name, name

    def new_project(self) -> None:
        if not self._can_switch_project():
            return
        try:
            destination = self._new_project_destination("Select a parent folder for the new Project")
            if destination is None:
                return
            root, name = destination
            self.project_manager.create_project(root, name)
            self.open_project(root)
        except (OSError, ValueError) as exc:
            messagebox.showerror("New Project", str(exc))

    def open_project_dialog(self) -> None:
        if not self._can_switch_project():
            return
        root = filedialog.askdirectory(parent=self, title="Select a Project folder containing project.json")
        if root:
            try:
                self.open_project(root)
            except (OSError, ValueError) as exc:
                messagebox.showerror("Open Project", str(exc))

    def _populate_recent_menu(self, menu: tk.Menu) -> None:
        menu.delete(0, "end")
        entries = self.project_manager.recent_projects()
        if not entries:
            menu.add_command(label="No recent projects" if self.lang == "en" else "没有最近项目", state="disabled")
        for item in entries:
            menu.add_command(
                label=f"{item.get('name', '')}  ({item['path']})",
                command=lambda path=item["path"]: self._open_recent(path),
            )

    def _open_recent(self, path: str) -> None:
        try:
            self.open_project(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Recent Project", str(exc))

    def open_project_folder(self) -> None:
        project = self.project_manager.current
        if project:
            open_folder(project.root)

    def export_project_dialog(self) -> None:
        project = self.project_manager.current
        if project is None:
            messagebox.showwarning("Export Project", "Open a Project first.")
            return
        choice = messagebox.askyesnocancel(
            "Export Project",
            "Metadata Archive is the default and contains Project metadata/history only.\n\n"
            "Include every file physically inside this Project? This may include large ODB files. "
            "Files referenced outside the Project are never copied.\n\n"
            "Yes: Archive with Project-Owned Files     No: Metadata Archive     Cancel: Stop",
            default="no",
        )
        if choice is None:
            return
        mode = "full" if choice else "metadata"
        destination = filedialog.asksaveasfilename(
            parent=self, title="Export Project", defaultextension=".abqjobpilot-project.zip",
            initialfile=f"{project.name}.abqjobpilot-project.zip",
            filetypes=[("AbqJobPilot Project", "*.zip")],
        )
        if destination:
            try:
                export_project_archive(project.root, destination, mode=mode)
                label = "Archive with Project-Owned Files" if mode == "full" else "Metadata Archive"
                messagebox.showinfo("Export Project", f"{label} saved:\n{destination}")
            except (OSError, ValueError, DatabaseFailure) as exc:
                messagebox.showerror("Export Project", str(exc))

    def import_project_dialog(self) -> None:
        if not self._can_switch_project():
            return
        archive = filedialog.askopenfilename(parent=self, title="Import Project Archive",
                                             filetypes=[("AbqJobPilot Project", "*.zip")])
        if not archive:
            return
        try:
            destination = self._new_project_destination("Select a parent folder for the imported Project")
            if destination is None:
                return
            project = import_project_archive(archive, destination[0],
                                             recent_file=self.project_manager.recent_file)
            self.open_project(project.root)
        except (OSError, ValueError, DatabaseFailure, zipfile.BadZipFile) as exc:
            messagebox.showerror("Import Project", str(exc))

    def import_legacy_dialog(self) -> None:
        if not self._can_switch_project():
            return
        source = filedialog.askdirectory(parent=self, title="Select a legacy runtime folder")
        if not source:
            return
        try:
            destination = self._new_project_destination("Select a parent folder for the imported Project")
            if destination is None:
                return
            project = import_legacy_runtime(source, destination[0], destination[1],
                                            recent_file=self.project_manager.recent_file)
            self.open_project(project.root)
        except (OSError, ValueError, DatabaseFailure) as exc:
            messagebox.showerror("Import Legacy Runtime", str(exc))

    def _make_button(self, parent: ttk.Frame, key: str, command, column: int) -> None:
        button = ttk.Button(parent, command=command)
        button.grid(row=0, column=column, padx=(0, 6))
        self.toolbar_buttons[key] = button

    def _make_primary_button(self, parent: ttk.Frame, key: str, command, column: int) -> None:
        frame = tk.Frame(parent, bd=2, relief="solid", background=COLORS["accent_dark"])
        frame.grid(row=0, column=column, padx=(0, 8), ipadx=1, ipady=1)
        label = tk.Label(
            frame,
            text="",
            padx=14,
            pady=5,
            background=COLORS["accent_soft"],
            foreground=COLORS["accent_dark"],
            cursor="hand2",
            font=("TkDefaultFont", 10, "bold"),
        )
        label.pack(fill="both", expand=True)
        label.bind("<Button-1>", lambda _event: command())
        label.bind("<Enter>", lambda _event: label.configure(background="#bfdbfe"))
        label.bind("<Leave>", lambda _event: label.configure(background=COLORS["accent_soft"]))
        self.toolbar_button_labels[key] = label

    def _build_status_area(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, padding=(14, 8, 14, 8))
        frame.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)
        self.status_light = tk.Canvas(frame, width=18, height=18, highlightthickness=0, background=COLORS["bg"])
        self.status_light.grid(row=0, column=0, padx=(0, 8))
        self.status_light_id = self.status_light.create_oval(3, 3, 15, 15, fill=COLORS["muted"], outline="")
        self.running_summary_label = ttk.Label(frame, textvariable=self.running_summary_var, wraplength=640)
        self.running_summary_label.grid(row=0, column=1, sticky="w")
        self.view_running_button = ttk.Button(frame, command=self.view_running_job)
        self.view_running_button.grid(row=0, column=2, sticky="e")
        self.resource_button = ttk.Button(frame, textvariable=self.resource_line_var,
                                          command=self.open_task_manager_performance)
        self.resource_button.grid(row=0, column=3, sticky="e", padx=(12, 0))

    def _build_table_controls(self, parent: ttk.Frame) -> None:
        controls = ttk.Frame(parent, padding=(0, 0, 0, 5))
        controls.grid(row=1, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)
        self.search_label = ttk.Label(controls)
        self.search_label.grid(row=0, column=0, padx=(0, 4))
        self.search_entry = ttk.Entry(controls, textvariable=self.search_var, width=18)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.status_filter = ttk.Combobox(controls, state="readonly", width=13)
        self.status_filter.grid(row=0, column=2, padx=4)
        self.status_filter.bind("<<ComboboxSelected>>", self._on_status_filter)
        self.batch_filter = ttk.Combobox(controls, state="readonly", width=14)
        self.batch_filter.grid(row=0, column=3, padx=4)
        self.batch_filter.bind("<<ComboboxSelected>>", self._on_batch_filter)
        self.refresh_button = ttk.Button(controls, command=self.refresh_all)
        self.refresh_button.grid(row=0, column=4, padx=(4, 0))

    def _build_queue_area(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, padding=2)
        self.queue_frame = frame
        parent.add(frame, weight=1)
        frame.rowconfigure(2, weight=1)
        frame.columnconfigure(0, weight=1)
        self.queue_heading = ttk.Label(frame, textvariable=self.queue_count_var)
        self.queue_heading.grid(row=0, column=0, sticky="w", pady=(0, 4))
        queue_controls = ttk.Frame(frame)
        queue_controls.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        queue_controls.columnconfigure(0, weight=1)
        self.queue_search_entry = ttk.Entry(queue_controls, textvariable=self.queue_search_var)
        self.queue_search_entry.grid(row=0, column=0, sticky="ew")
        self.queue_refresh_button = ttk.Button(queue_controls, command=self.refresh_all)
        self.queue_refresh_button.grid(row=0, column=1, padx=(5, 0))
        self.queue_more_button = ttk.Button(queue_controls, command=lambda: self._show_selected_context(self.queue_tree))
        self.queue_more_button.grid(row=0, column=2, padx=(5, 0))
        self.queue_tree = ttk.Treeview(frame, columns=QUEUE_COLUMNS, show="headings", selectmode="extended")
        widths = {"index": 50, "status": 105, "batch": 90, "strategy": 90, "job": 180,
                  "cpus": 50, "gpus": 50, "created": 150, "inp": 360}
        self._configure_tree(self.queue_tree, {column: column for column in QUEUE_COLUMNS}, widths)
        self.queue_tree.configure(displaycolumns=("index", "status", "job", "batch", "strategy", "cpus", "gpus"))
        self._configure_status_tags(self.queue_tree)
        self.queue_tree.grid(row=2, column=0, sticky="nsew")
        self._attach_scrollbars(frame, self.queue_tree, row=2)
        self.queue_tree.bind("<Button-3>", self._show_queue_menu)
        self.queue_tree.bind("<Control-a>", lambda _event: self._select_all_visible(self.queue_tree))
        self.queue_tree.bind("<Double-1>", lambda event: self._open_details_at_event(self.queue_tree, event))
        self.queue_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_table_select(self.queue_tree, self.results_tree))

    def _build_results_area(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, padding=2)
        self.results_frame = frame
        parent.add(frame, weight=1)
        frame.rowconfigure(2, weight=1)
        frame.columnconfigure(0, weight=1)
        self.results_heading = ttk.Label(frame, textvariable=self.results_count_var)
        self.results_heading.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self._build_table_controls(frame)
        self.results_tree = ttk.Treeview(frame, columns=RESULT_COLUMNS, show="headings", selectmode="extended")
        widths = {"status": 130, "batch": 90, "strategy": 90, "job": 190, "started": 150,
                  "ended": 145, "duration": 70, "odb": 90, "warnings": 70, "fatal": 360}
        self._configure_tree(self.results_tree, {column: column for column in RESULT_COLUMNS}, widths)
        self.results_tree.configure(displaycolumns=("status", "job", "batch", "strategy", "ended", "duration", "warnings"))
        self._configure_status_tags(self.results_tree)
        self.results_tree.grid(row=2, column=0, sticky="nsew")
        self._attach_scrollbars(frame, self.results_tree, row=2)
        self.results_tree.bind("<Button-3>", self._show_results_menu)
        self.results_tree.bind("<Control-a>", lambda _event: self._select_all_visible(self.results_tree))
        self.results_tree.bind("<Double-1>", lambda event: self._open_details_at_event(self.results_tree, event))
        self.results_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_table_select(self.results_tree, self.queue_tree))
        self.results_more_button = ttk.Button(frame, command=lambda: self._show_selected_context(self.results_tree))
        self.results_more_button.grid(row=0, column=0, sticky="e")

    def _build_details_area(self, parent: tk.Toplevel) -> None:
        section = ttk.Frame(parent)
        section.rowconfigure(1, weight=1)
        section.columnconfigure(0, weight=1)
        self.detail_section = section
        section.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        header = ttk.Frame(section, padding=(2, 4))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, textvariable=self.inspection_title_var).grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.filtered_hint_var, foreground=COLORS["muted"]).grid(row=0, column=1, padx=8)
        self.detail_folder_button = ttk.Button(header, command=self.open_selected_work_folder)
        self.detail_folder_button.grid(row=0, column=2, padx=4)
        self.detail_more_menu = tk.Menu(self, tearoff=False, postcommand=self._populate_detail_more_menu)
        self.detail_more_button = ttk.Menubutton(header, menu=self.detail_more_menu)
        self.detail_more_button.grid(row=0, column=3, padx=4)
        self.detail_collapse_button = ttk.Button(header, command=self._toggle_details)
        self.detail_collapse_button.grid(row=0, column=4, padx=4)

        self.detail_notebook = ttk.Notebook(section, style="Workspace.TNotebook")
        self.detail_notebook.grid(row=1, column=0, sticky="nsew")
        self.overview_tab = ttk.Frame(self.detail_notebook)
        self.files_tab = ttk.Frame(self.detail_notebook)
        self.logs_tab = ttk.Frame(self.detail_notebook)
        self.history_tab = ttk.Frame(self.detail_notebook)
        for tab in (self.overview_tab, self.files_tab, self.logs_tab, self.history_tab):
            self.detail_notebook.add(tab)
        self._build_overview_tab()
        self._build_files_tab()
        self._build_logs_tab()
        self._build_history_tab()
        self.detail_notebook.bind("<<NotebookTabChanged>>", lambda _event: self._refresh_inspection())

    def _build_overview_tab(self) -> None:
        self.overview_tab.rowconfigure(0, weight=1)
        self.overview_tab.columnconfigure(0, weight=1)
        self.overview_text = scrolledtext.ScrolledText(self.overview_tab, height=6, wrap="word",
                                                      font=("Segoe UI", 10), relief="flat", state="disabled")
        self.overview_text.grid(row=0, column=0, sticky="nsew")

    def _build_files_tab(self) -> None:
        self.files_tab.rowconfigure(0, weight=1)
        self.files_tab.columnconfigure(0, weight=1)
        self.files_tree = ttk.Treeview(self.files_tab, columns=("kind", "state", "path"), show="headings")
        for column, width in (("kind", 80), ("state", 190), ("path", 700)):
            self.files_tree.heading(column, text=column.title())
            self.files_tree.column(column, width=width, minwidth=60, stretch=column == "path")
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        file_scroll = ttk.Scrollbar(self.files_tab, orient="vertical", command=self.files_tree.yview)
        file_scroll.grid(row=0, column=1, sticky="ns")
        self.files_tree.configure(yscrollcommand=file_scroll.set)
        actions = ttk.Frame(self.files_tab)
        actions.grid(row=1, column=0, sticky="w", pady=4)
        self.file_copy_button = ttk.Button(actions, command=lambda: self._file_reference_action("copy"))
        self.file_copy_button.pack(side="left", padx=4)
        self.file_folder_button = ttk.Button(actions, command=lambda: self._file_reference_action("folder"))
        self.file_folder_button.pack(side="left", padx=4)
        self.file_open_button = ttk.Button(actions, command=lambda: self._file_reference_action("open"))
        self.file_open_button.pack(side="left", padx=4)

    def _build_logs_tab(self) -> None:
        self.logs_tab.rowconfigure(1, weight=1)
        self.logs_tab.columnconfigure(0, weight=1)
        controls = ttk.Frame(self.logs_tab)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)
        self.log_source = ttk.Combobox(controls, textvariable=self.log_source_var,
                                       values=("STA", "MSG", "DAT", "LOG", "Console"), state="readonly", width=10)
        self.log_source.grid(row=0, column=0, padx=(2, 8))
        self.log_source.bind("<<ComboboxSelected>>", lambda _event: self._refresh_log(force=True))
        self.log_origin_label = ttk.Label(controls, textvariable=self.log_path_var)
        self.log_origin_label.grid(row=0, column=1, sticky="ew")
        self.follow_checkbox = ttk.Checkbutton(controls, variable=self.log_follow_var)
        self.follow_checkbox.grid(row=0, column=2, padx=4)
        self.log_copy_button = ttk.Button(controls, command=self.copy_console_for_ai)
        self.log_copy_button.grid(row=0, column=3, padx=4)
        self.log_text = scrolledtext.ScrolledText(self.logs_tab, height=8, wrap="none", font=("Consolas", 10),
                                                 background="#fbfdff", foreground=COLORS["text"], state="disabled")
        self.log_text.grid(row=1, column=0, sticky="nsew")
        for event_name in ("<MouseWheel>", "<Button-4>", "<Button-5>", "<Prior>", "<Up>"):
            self.log_text.bind(event_name, self._pause_log_follow, add="+")
        self.log_text.vbar.bind("<ButtonPress-1>", self._pause_log_follow, add="+")

    def _build_history_tab(self) -> None:
        self.history_tab.rowconfigure(0, weight=1)
        self.history_tab.columnconfigure(0, weight=1)
        columns = ("attempt", "status", "started", "completed", "cpus", "gpus", "working_dir", "odb")
        self.history_tree = ttk.Treeview(self.history_tab, columns=columns, show="headings")
        for column, width in (("attempt", 70), ("status", 160), ("started", 160), ("completed", 160),
                              ("cpus", 60), ("gpus", 60), ("working_dir", 250), ("odb", 250)):
            self.history_tree.heading(column, text=column.replace("_", " ").title())
            self.history_tree.column(column, width=width, minwidth=55)
        self._configure_status_tags(self.history_tree)
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self.history_tab, orient="vertical", command=self.history_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        self.history_empty_var = tk.StringVar()
        ttk.Label(self.history_tab, textvariable=self.history_empty_var).grid(row=1, column=0, sticky="w")

    def _build_live_logs(self, parent: ttk.PanedWindow) -> None:
        section = ttk.Frame(parent)
        section.rowconfigure(0, weight=1)
        section.columnconfigure(0, weight=1)
        parent.add(section, weight=2)
        self.live_log_pane = ttk.PanedWindow(section, orient="horizontal")
        self.live_log_pane.grid(row=0, column=0, sticky="nsew")
        self.live_log_texts = {}
        for side in ("solver", "console"):
            pane = ttk.Frame(self.live_log_pane, padding=2)
            pane.rowconfigure(1, weight=1)
            pane.columnconfigure(0, weight=1)
            self.live_log_pane.add(pane, weight=1)
            controls = ttk.Frame(pane)
            controls.grid(row=0, column=0, sticky="ew", pady=(0, 4))
            controls.columnconfigure(1, weight=1)
            if side == "solver":
                selector = ttk.Combobox(controls, textvariable=self.live_source_var,
                                        values=("STA", "MSG", "DAT", "LOG"), state="readonly", width=6)
                selector.grid(row=0, column=0, padx=(0, 6))
                selector.bind("<<ComboboxSelected>>", lambda _event: self._refresh_live_logs())
                self.live_source_selector = selector
            else:
                self.console_heading = ttk.Label(controls)
                self.console_heading.grid(row=0, column=0, padx=(0, 6))
            ttk.Label(controls, textvariable=self.live_origin_vars[side]).grid(row=0, column=1, sticky="w")
            follow = ttk.Checkbutton(controls, variable=self.live_follow_vars[side])
            follow.grid(row=0, column=2, padx=4)
            setattr(self, f"live_{side}_follow", follow)
            widget = scrolledtext.ScrolledText(pane, height=8, wrap="none", font=("Consolas", 10),
                                               background="#fbfdff", foreground=COLORS["text"], state="disabled")
            widget.grid(row=1, column=0, sticky="nsew")
            for event_name in ("<MouseWheel>", "<Button-4>", "<Button-5>", "<Prior>", "<Up>"):
                widget.bind(event_name, lambda _event, key=side: self.live_follow_vars[key].set(False), add="+")
            widget.vbar.bind("<ButtonPress-1>",
                             lambda _event, key=side: self.live_follow_vars[key].set(False), add="+")
            self.live_log_texts[side] = widget

    def _build_footer(self) -> None:
        footer = ttk.Frame(self, padding=(12, 4))
        footer.grid(row=3, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.footer_mode_var = tk.StringVar()
        ttk.Label(footer, textvariable=self.footer_mode_var, foreground=COLORS["muted"]).grid(row=0, column=0, sticky="w")

    def _configure_tree(self, tree: ttk.Treeview, headings: dict[str, str], widths: dict[str, int]) -> None:
        for column, label in headings.items():
            tree.heading(column, text=label)
            tree.column(column, width=widths.get(column, 120), minwidth=50, anchor="w")

    def _configure_status_tags(self, tree: ttk.Treeview) -> None:
        tree.tag_configure("queued", background="#ffffff", foreground=COLORS["text"])
        tree.tag_configure("running", background="#eff6ff", foreground=COLORS["accent_dark"])
        tree.tag_configure("success", background=SUCCESS_BACKGROUND, foreground=SUCCESS_FOREGROUND)
        tree.tag_configure("failed", background="#fef2f2", foreground="#991b1b")
        tree.tag_configure("skipped", background="#f8fafc", foreground=COLORS["muted"])

    def _status_tag(self, status: str) -> str:
        return status_presentation(status, self.lang)[1]

    def _attach_scrollbars(self, parent: ttk.Frame, tree: ttk.Treeview, row: int = 0) -> None:
        y_scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.grid(row=row, column=1, sticky="ns")
        x_scroll.grid(row=row + 1, column=0, sticky="ew")

    def refresh_all(self) -> None:
        self._sync_project_history_if_changed()
        jobs = load_queue()
        self._all_jobs = jobs
        self.job_by_id = {job["queue_id"]: job for job in jobs if job.get("queue_id")}
        self._refresh_status()
        self._refresh_live_logs()
        self._refresh_tables_from_cache()
        if self.inspection_key and (self.inspection_key[0] != config.RUNTIME_DIR or
                                    self.inspection_key[1] not in self.job_by_id):
            self.inspection_key = None
            self._clear_inspection_view()
        self._refresh_inspection()
        self._refresh_resource_usage()
        self._apply_language()

    def _sync_project_history_if_changed(self) -> None:
        project = self.project_manager.current
        if project is None:
            return
        queue_file = project.runtime_dir / "queue.json"
        reports = project.runtime_dir / "reports"
        try:
            queue_stat = queue_file.stat()
            report_stat = reports.stat() if reports.exists() else None
            signature = (queue_stat.st_mtime_ns, queue_stat.st_size,
                         report_stat.st_mtime_ns if report_stat else None)
        except OSError as exc:
            logging.warning("Project history source unavailable: %s", exc)
            return
        if signature == self._history_signature:
            return
        try:
            sync_history_from_runtime(project.root)
        except (OSError, ValueError, DatabaseFailure) as exc:
            logging.warning("Project history synchronization failed; runtime JSON remains active: %s", exc)
        else:
            self._history_signature = signature

    def _poll_refresh(self) -> None:
        self.refresh_all()
        self._check_auto_shutdown_after_queue()
        self._poll_after_id = self.after(config.POLL_INTERVAL_SECONDS * 1000, self._poll_refresh)

    def _refresh_status(self) -> None:
        data = read_json(config.LIVE_STATUS_FILE, {})
        self._live_status = data if isinstance(data, dict) else {}
        phase = str(self._live_status.get("phase") or "IDLE")
        running = self.runner.is_running()
        persisted_running = any(job.get("status") in {"DATACHECK_RUNNING", "FULL_RUNNING"}
                                for job in self._all_jobs)
        if running:
            observed_phase = phase in {"DATACHECK_RUNNING", "FULL_RUNNING", "STARTED"}
            self.runner_context = dict(self._live_status) if observed_phase else {}
            name = self.runner_context.get("current_job") or "..."
            if observed_phase:
                parts = [("运行中" if self.lang == "zh" else "RUNNING"), str(name), phase]
                for label, field in (("Step", "step"), ("Inc", "increment")):
                    value = self.runner_context.get(field)
                    if value not in (None, ""):
                        parts.append(f"{label} {value}")
                elapsed = self.runner_context.get("elapsed_time")
                if elapsed not in (None, ""):
                    try:
                        seconds = int(float(elapsed))
                        parts.append(f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}")
                    except (TypeError, ValueError):
                        pass
                summary = " · ".join(parts)
            else:
                summary = "执行器已启动 · 等待任务状态" if self.lang == "zh" else "Runner active · awaiting task status"
            light = "running"
        elif phase in {"DATACHECK_RUNNING", "FULL_RUNNING", "RUNNER_ACTIVE"} or persisted_running:
            self.runner_context = dict(self._live_status)
            prefix = "状态未确认 · 上次观察到的任务：" if self.lang == "zh" else "Status unconfirmed · last observed run: "
            summary = prefix + str(self._live_status.get("current_job") or "--")
            light = "uncertain"
        else:
            self.runner_context = {}
            summary = "空闲" if self.lang == "zh" else "IDLE"
            light = "idle"
        pending = sum(job.get("status") in {"QUEUED", "DATACHECK_OK"} for job in self._all_jobs)
        summary += f" · 待执行 {pending} 项" if self.lang == "zh" else f" · {pending} pending"
        self.running_summary_var.set(summary)
        self._verified_running = light == "running"
        self._update_status_light(light)
        can_view_running = bool(light == "running" and self.runner_context.get("queue_id"))
        self.view_running_button.configure(state="normal" if can_view_running else "disabled",
                                           style="RunningAction.TButton" if can_view_running else "TButton")

    def _refresh_live_logs(self) -> None:
        queue_id = self.runner_context.get("queue_id") if self._verified_running else None
        job = self.job_by_id.get(queue_id) if queue_id else None
        for side, widget in self.live_log_texts.items():
            source = self.live_source_var.get() if side == "solver" else "Console"
            field = {"STA": "sta_path", "MSG": "msg_path", "DAT": "dat_path",
                     "LOG": "log_path", "Console": "log_path"}[source]
            path = (job.get(field) if job else None) or self.runner_context.get(field)
            if not queue_id:
                path = None
            if not path:
                origin = ("无当前任务" if self.lang == "zh" else "No active job") if not queue_id else (
                    "未记录路径" if self.lang == "zh" else "Path not recorded")
                content = ""
            else:
                name = self.runner_context.get("current_job") or (job.get("job_name") if job else queue_id)
                origin = f"{name} · {path}"
                content = read_log_tail(path, max_bytes=65536, max_lines=80)
                if source == "STA" and content:
                    content = self._sta_table_text(content)
                if not Path(path).is_file():
                    content = "记录路径处文件缺失。" if self.lang == "zh" else "File missing at recorded path."
            self.live_origin_vars[side].set(origin)
            signature = (config.RUNTIME_DIR, queue_id, source, path, content, self.lang)
            if signature != self._live_log_signatures.get(side):
                self._set_text(widget, content, follow=self.live_follow_vars[side].get())
                self._live_log_signatures[side] = signature

    def _refresh_tables_from_cache(self) -> None:
        if not hasattr(self, "queue_tree"):
            return
        self._update_batch_choices()
        self._refresh_queue(self._all_jobs)
        self._refresh_results(self._all_jobs)
        self._refresh_table_counts()

    def _refresh_queue(self, jobs: list[dict]) -> None:
        active = queue_display_jobs(jobs)
        visible = filter_jobs(active, self.queue_search_var.get())
        visible_ids = {job.get("queue_id") for job in visible}
        rows = []
        for index, job in enumerate(active, start=1):
            if job.get("queue_id") not in visible_ids:
                continue
            rows.append((
                row_iid(job),
                (
                    index,
                    status_presentation(job.get("status"), self.lang)[0],
                    job.get("batch_name", ""),
                    job.get("strategy_name", ""),
                    job.get("job_name", ""),
                    job.get("cpus", ""),
                    job.get("gpus", 0),
                    job.get("created_at", ""),
                    job.get("inp_path", ""),
                ),
                self._status_tag(job.get("status", "")),
            ))
        self._render_tree(self.queue_tree, "queue", rows, visible)

    def _refresh_results(self, jobs: list[dict]) -> None:
        results = result_display_jobs(jobs)
        visible = filter_jobs(results, self.search_var.get(), self.filter_status_code, self.filter_batch)
        rows = []
        for job in visible:
            rows.append((
                row_iid(job, results=True),
                (
                    status_presentation(job.get("status"), self.lang)[0],
                    job.get("batch_name", ""),
                    job.get("strategy_name", ""),
                    job.get("job_name", ""),
                    job.get("started_at", ""),
                    job.get("ended_at", ""),
                    job.get("duration_sec", ""),
                    format_bytes(job.get("odb_size_bytes")),
                    job.get("warning_count", ""),
                    job.get("fatal_reason", ""),
                ),
                self._status_tag(job.get("status", "")),
            ))
        self._render_tree(self.results_tree, "results", rows, visible)

    def _render_tree(self, tree: ttk.Treeview, key: str, rows: list[tuple], jobs: list[dict]) -> None:
        if rows == self._rendered_rows.get(key):
            return
        current = tree.selection()
        focused = tree.focus()
        y_start = tree.yview()[0]
        x_start = tree.xview()[0]
        self._restoring_table_selection = True
        tree.delete(*tree.get_children())
        for iid, values, tag in rows:
            tree.insert("", "end", iid=iid, values=values, tags=(tag,))
        selected_iids = restore_iids(current, jobs, results=key == "results")
        if selected_iids:
            tree.selection_set(selected_iids)
            tree.focus(focused if focused in selected_iids else selected_iids[0])
        if self._selection_restore_after_id is None:
            self._selection_restore_after_id = self.after_idle(self._finish_table_selection_restore)
        tree.yview_moveto(y_start)
        tree.xview_moveto(x_start)
        self._rendered_rows[key] = rows
        self._refresh_table_counts()

    def _finish_table_selection_restore(self) -> None:
        self._selection_restore_after_id = None
        self._restoring_table_selection = False

    def _on_table_select(self, selected_tree: ttk.Treeview, other_tree: ttk.Treeview) -> None:
        if self._restoring_table_selection:
            return
        self._refresh_table_counts()
        selection = selected_tree.selection()
        if not selection:
            return
        queue_id = selected_job_id(selection[0], results=selected_tree is self.results_tree)
        if queue_id and queue_id in self.job_by_id:
            self._last_selected_tree = selected_tree
            self.inspection_key = (config.RUNTIME_DIR, queue_id)
            self._rendered_inspection = None
            self._refresh_inspection()

    def _update_batch_choices(self) -> None:
        all_label = "全部批次" if self.lang == "zh" else "All batches"
        values = [all_label] + sorted({str(job.get("batch_name")) for job in self._all_jobs
                                       if job.get("batch_name")})
        if tuple(self.batch_filter.cget("values")) != tuple(values):
            self.batch_filter.configure(values=values)
        self.batch_filter.set(self.filter_batch if self.filter_batch in values else all_label)
        if self.filter_batch not in values:
            self.filter_batch = None

    def _on_batch_filter(self, _event=None) -> None:
        value = self.batch_filter.get()
        self.filter_batch = value if value in {str(job.get("batch_name")) for job in self._all_jobs} else None
        self._refresh_tables_from_cache()
        self._refresh_inspection()

    def _status_filter_labels(self) -> list[str]:
        return (["全部状态", "待执行", "运行中", "完成", "有警告", "失败"] if self.lang == "zh" else
                ["All statuses", "Queued", "Running", "Completed", "With warnings", "Failed"])

    def _on_status_filter(self, _event=None) -> None:
        codes = ("all", "queued", "running", "completed", "warnings", "failed")
        index = self.status_filter.current()
        self.filter_status_code = codes[index] if 0 <= index < len(codes) else "all"
        self._refresh_tables_from_cache()
        self._refresh_inspection()

    def _on_search_change(self) -> None:
        self._refresh_tables_from_cache()
        self._refresh_inspection()

    def _refresh_table_counts(self) -> None:
        if not hasattr(self, "queue_tree"):
            return
        queued = len(queue_display_jobs(self._all_jobs))
        results = len(result_display_jobs(self._all_jobs))
        shown_queue = len(self.queue_tree.get_children())
        shown_results = len(self.results_tree.get_children())
        self.queue_count_var.set((f"队列 {shown_queue}/{queued} · 筛选不改变执行顺序" if self.lang == "zh" else
                                  f"Queue {shown_queue}/{queued} · execution order unchanged") +
                                 ((f" · 已选 {len(self.queue_tree.selection())} 项" if self.lang == "zh" else
                                   f" · {len(self.queue_tree.selection())} selected") if self.queue_tree.selection() else ""))
        self.results_count_var.set((f"结果 {shown_results}/{results} · 最新在前" if self.lang == "zh" else
                                    f"Results {shown_results}/{results} · newest first") +
                                   ((f" · 已选 {len(self.results_tree.selection())} 项" if self.lang == "zh" else
                                     f" · {len(self.results_tree.selection())} selected") if self.results_tree.selection() else ""))

    def _inspection_job(self) -> dict | None:
        if not self.inspection_key or self.inspection_key[0] != config.RUNTIME_DIR:
            return None
        return self.job_by_id.get(self.inspection_key[1])

    def _inspection_visible(self, job: dict) -> bool:
        if job.get("status") in config.ACTIVE_STATUSES or job.get("status") == "RUNNING":
            return self.queue_tree.exists(row_iid(job))
        return self.results_tree.exists(row_iid(job, results=True))

    def _clear_inspection_view(self) -> None:
        self.inspection_title_var.set("No task selected" if self.lang == "en" else "未选择任务")
        self.filtered_hint_var.set("")
        self.log_path_var.set("")
        self._rendered_log = None
        self._inspection_history_runs = []
        for name in ("overview_text", "log_text"):
            if hasattr(self, name):
                self._set_text(getattr(self, name), "", follow=False)
        for name in ("files_tree", "history_tree"):
            if hasattr(self, name):
                tree = getattr(self, name)
                tree.delete(*tree.get_children())
        if hasattr(self, "history_empty_var"):
            self.history_empty_var.set("")

    def _refresh_inspection(self) -> None:
        if not hasattr(self, "detail_notebook"):
            return
        job = self._inspection_job()
        if not job:
            if self._rendered_inspection is not None:
                self._rendered_inspection = None
                self._clear_inspection_view()
            return
        signature = (self.inspection_key, self.lang, tuple(sorted((key, str(value)) for key, value in job.items())))
        if signature != self._rendered_inspection:
            self._rendered_inspection = signature
            self.inspection_title_var.set(("当前查看：" if self.lang == "zh" else "Inspecting: ") +
                                          str(job.get("job_name") or job.get("queue_id")))
            self._inspection_history_runs = self._history_for_job(job)
            self._render_overview(job)
            self._render_file_references(job)
            self._render_history_rows(self._inspection_history_runs)
            self._rendered_log = None
        self.filtered_hint_var.set("" if self._inspection_visible(job) else
                                   ("当前查看项不在筛选结果中" if self.lang == "zh" else "Inspected task is hidden by filters"))
        if self.detail_notebook.select() == str(self.logs_tab) and not self._details_collapsed:
            self._refresh_log()

    def _history_for_job(self, job: dict) -> list[dict]:
        project = self.project_manager.current
        if project is None:
            return []
        try:
            repository = ProjectHistoryRepository(project)
            logical = repository.find_job_by_queue_id(job["queue_id"])
            return repository.list_runs(logical["job_id"]) if logical else []
        except (OSError, ValueError, DatabaseFailure) as exc:
            logging.warning("Run history unavailable: %s", exc)
            return []

    def _render_overview(self, job: dict) -> None:
        label, _tag = status_presentation(job.get("status"), self.lang)
        run = next((item for item in self._inspection_history_runs
                    if item.get("queue_id") == job.get("queue_id")), None)
        labels = ({"status": "状态", "raw": "原始状态", "warnings": "警告", "batch": "批次", "strategy": "策略",
                   "created": "创建", "started": "开始", "ended": "结束", "duration": "耗时（秒）",
                   "attempt": "尝试", "failure": "失败原因", "notes": "备注", "analysis": "分析时间"}
                  if self.lang == "zh" else
                  {"status": "Status", "raw": "Raw status", "warnings": "Warnings", "batch": "Batch", "strategy": "Strategy",
                   "created": "Created", "started": "Started", "ended": "Ended", "duration": "Duration (s)",
                   "attempt": "Attempt", "failure": "Failure", "notes": "Notes", "analysis": "Analysis time"})
        lines = [f"{labels['status']}: {label}", f"{labels['raw']}: {job.get('status') or '--'}",
                 f"{labels['warnings']}: {job.get('warning_count') if job.get('warning_count') is not None else '--'}",
                 f"{labels['batch']}: {job.get('batch_name') or '--'}     {labels['strategy']}: {job.get('strategy_name') or '--'}",
                 f"CPU: {job.get('cpus') if job.get('cpus') is not None else '--'}     GPU: {job.get('gpus') if job.get('gpus') is not None else '--'}",
                 f"{labels['created']}: {job.get('created_at') or '--'}     {labels['started']}: {job.get('started_at') or '--'}",
                 f"{labels['ended']}: {job.get('ended_at') or '--'}     {labels['duration']}: {job.get('duration_sec') if job.get('duration_sec') is not None else '--'}",
                 f"Queue ID: {job.get('queue_id') or '--'}"]
        if run:
            lines.append(f"{labels['attempt']}: {run['attempt_no']}     Run ID: {run['run_id']}")
        if job.get("fatal_reason"):
            lines.append(f"{labels['failure']}: {job['fatal_reason']}")
        if job.get("notes"):
            lines.append(f"{labels['notes']}: {job['notes']}")
        if job.get("step") is not None:
            lines.append(f"Step: {job['step']}     Increment: {job.get('increment') or '--'}")
        if job.get("analysis_time") is not None:
            lines.append(f"{labels['analysis']}: {job['analysis_time']}")
        self._set_text(self.overview_text, "\n".join(lines), follow=False)

    def _render_file_references(self, job: dict) -> None:
        self.files_tree.delete(*self.files_tree.get_children())
        for kind, field in (("INP", "inp_path"), ("ODB", "odb_path"), ("STA", "sta_path"),
                            ("MSG", "msg_path"), ("DAT", "dat_path"), ("LOG", "log_path")):
            path = job.get(field)
            exists = bool(path and Path(path).is_file())
            state = (("存在（未验证有效性）" if exists else "文件缺失") if self.lang == "zh" else
                     ("Exists (not validated)" if exists else "Missing")) if path else (
                         "未记录" if self.lang == "zh" else "Not recorded")
            self.files_tree.insert("", "end", iid=kind, values=(kind, state, path or ""))

    def _render_history_rows(self, runs: list[dict]) -> None:
        self.history_tree.delete(*self.history_tree.get_children())
        for run in runs:
            raw = run.get("raw_status") or run.get("status")
            label, tag = status_presentation(raw, self.lang)
            self.history_tree.insert("", "end", iid=run["run_id"], tags=(tag,), values=(
                run["attempt_no"], label, run.get("started_at") or "", run.get("completed_at") or "",
                run.get("cpus") if run.get("cpus") is not None else "",
                run.get("gpus") if run.get("gpus") is not None else "",
                run.get("working_dir") or "", run.get("expected_odb_path") or ""))
        self.history_empty_var.set("" if runs else
                                   ("暂无已记录的运行尝试" if self.lang == "zh" else "No recorded attempts"))

    def _file_reference_action(self, action: str) -> None:
        selected = self.files_tree.selection()
        if not selected:
            return
        kind, _state, path = self.files_tree.item(selected[0], "values")
        if not path:
            return
        if action == "copy":
            self._copy_text(path)
        elif action == "folder":
            self._open_job_folder(str(Path(path).parent))
        elif action == "open" and kind in {"INP", "STA", "MSG", "DAT", "LOG"}:
            self._open_job_text(path)

    def _pause_log_follow(self, _event=None) -> None:
        self.log_follow_var.set(False)

    def _refresh_log(self, *, force: bool = False) -> None:
        job = self._inspection_job()
        if not job:
            self.log_path_var.set("")
            return
        source = self.log_source_var.get()
        field = {"STA": "sta_path", "MSG": "msg_path", "DAT": "dat_path",
                 "LOG": "log_path", "Console": "log_path"}[source]
        path = job.get(field) or expected_paths(job).get(field)
        run = next((item for item in self._inspection_history_runs
                    if item.get("queue_id") == job.get("queue_id")), None)
        attempt = f" · Attempt {run['attempt_no']}" if run else ""
        available = bool(path and Path(path).is_file())
        not_started = job.get("status") == "QUEUED" and not job.get("started_at")
        state = (("可查看" if self.lang == "zh" else "Available") if available else
                 ("路径未知" if self.lang == "zh" else "Path unknown") if not path else
                 ("尚未生成" if self.lang == "zh" else "Not yet created") if not_started else
                 ("文件缺失" if self.lang == "zh" else "Missing"))
        self.log_path_var.set(f"{job.get('job_name') or '--'}{attempt} · {source}: {state} · "
                              f"{path or ('未记录路径' if self.lang == 'zh' else 'Path not recorded')}")
        content = read_log_tail(path, max_bytes=65536, max_lines=80) if available else ""
        if source == "STA" and content:
            content = self._sta_table_text(content)
        if not path:
            content = "此日志来源未记录路径。" if self.lang == "zh" else "No path recorded for this log source."
        elif not available:
            content = (("任务尚未运行，日志尚未生成。" if self.lang == "zh" else
                        "This task has not run; the log has not been created yet.") if not_started else
                       ("记录路径处文件缺失。" if self.lang == "zh" else "File missing at recorded path."))
        else:
            note = ("记录路径的当前文件内容；历史尝试的同名文件可能已被覆盖。\n\n" if self.lang == "zh" else
                    "Current contents at recorded path; historical attempts may have overwritten this file.\n\n")
            content = note + content
        signature = (self.inspection_key, source, path, content)
        if force or signature != self._rendered_log:
            self._set_text(self.log_text, content, follow=self.log_follow_var.get())
            self._rendered_log = signature

    def _toggle_details(self) -> None:
        if self._details_collapsed:
            self._show_details()
        else:
            self._hide_details()
        self._apply_language()

    def _show_details(self) -> None:
        if not self._inspection_job():
            return
        self._details_collapsed = False
        self.detail_window.deiconify()
        self.detail_window.lift()
        self._refresh_inspection()

    def _hide_details(self) -> None:
        if hasattr(self, "detail_window") and self.detail_window.winfo_exists():
            self.detail_window.withdraw()
        self._details_collapsed = True

    def open_task_details(self, job_id: str | None, initial_tab: str | None = None) -> None:
        if not job_id or job_id not in self.job_by_id:
            return
        self.inspection_key = (config.RUNTIME_DIR, job_id)
        self._rendered_inspection = None
        if initial_tab == "logs":
            self.detail_notebook.select(self.logs_tab)
        self._show_details()

    def open_selected_details(self) -> None:
        job = self._selected_job()
        if job:
            self.open_task_details(job.get("queue_id"))

    def _open_details_at_event(self, tree: ttk.Treeview, event) -> None:
        iid = tree.identify_row(event.y)
        if iid:
            self.open_task_details(selected_job_id(iid, results=tree is self.results_tree))

    def _show_selected_context(self, tree: ttk.Treeview) -> None:
        selection = tree.selection()
        if selection:
            tree.see(selection[0])
            tree.update_idletasks()
            bbox = tree.bbox(selection[0])
        else:
            bbox = None
        event = SimpleNamespace(y=bbox[1] + 2 if bbox else -1,
                                x_root=tree.winfo_rootx() + 30,
                                y_root=tree.winfo_rooty() + (bbox[1] + 20 if bbox else 20))
        if tree is self.queue_tree:
            self._show_queue_menu(event)
        else:
            self._show_results_menu(event)

    def _selected_visible_ids(self, tree: ttk.Treeview) -> tuple[str, ...]:
        visible = set(tree.get_children())
        results = tree is self.results_tree
        return tuple(selected_job_id(iid, results=results) for iid in tree.selection() if iid in visible)

    def _select_all_visible(self, tree: ttk.Treeview) -> str:
        tree.selection_set(tree.get_children())
        self._last_selected_tree = tree
        tree.focus_set()
        self._refresh_table_counts()
        return "break"

    def _clear_table_selection(self, tree: ttk.Treeview) -> None:
        tree.selection_remove(tree.selection())
        self._last_selected_tree = tree
        self._refresh_table_counts()

    def _append_selection_menu(self, menu: tk.Menu, tree: ttk.Treeview) -> None:
        menu.add_separator()
        self._menu_item(menu, "select_all", lambda: self._select_all_visible(tree), bool(tree.get_children()))
        self._menu_item(menu, "clear_selection", lambda: self._clear_table_selection(tree), bool(tree.selection()))
        selected = self._selected_visible_ids(tree)
        if len(selected) > 1:
            key = "delete_selected" if tree is self.results_tree else "remove_selected"
            action = self._delete_selected_results if tree is self.results_tree else self._remove_selected_queue
            self._menu_item(menu, key, action)

    def _remove_selected_queue(self) -> None:
        ids = self._selected_visible_ids(self.queue_tree)
        jobs = load_queue()
        selected = [job for job in jobs if job.get("queue_id") in ids]
        title = "移除队列记录" if self.lang == "zh" else "Remove Queue Records"
        if (not ids or len(selected) != len(ids) or any(job.get("status") != "QUEUED" for job in selected) or
                not self._queue_mutations_allowed(queue_display_jobs(jobs))):
            messagebox.showwarning(title, "只能在没有运行中任务时移除选中的待执行记录。" if self.lang == "zh" else
                                   "Only selected QUEUED records can be removed while no job is running.")
            return
        prompt = (f"移除选中的 {len(ids)} 条队列记录？\n\n不会删除工程文件。" if self.lang == "zh" else
                  f"Remove {len(ids)} selected queue records?\n\nEngineering files will not be deleted.")
        if not messagebox.askyesno(title, prompt):
            return
        result = remove_queued_jobs(ids)
        self.refresh_all()
        if not result["ok"]:
            messagebox.showerror(title, result["message"])

    def _delete_selected_results(self) -> None:
        ids = self._selected_visible_ids(self.results_tree)
        jobs = load_queue()
        selected = [job for job in jobs if job.get("queue_id") in ids]
        title = "删除结果记录" if self.lang == "zh" else "Delete Result Records"
        if (not ids or len(selected) != len(ids) or
                any(job.get("status") not in config.RESULT_STATUSES for job in selected) or
                not self._queue_mutations_allowed(queue_display_jobs(jobs))):
            messagebox.showwarning(title, "无法批量删除选中的结果记录。" if self.lang == "zh" else
                                   "Selected result records cannot be deleted now.")
            return
        prompt = (f"删除选中的 {len(ids)} 条结果列表记录？\n\n不会删除工程文件或数据库运行历史。" if self.lang == "zh" else
                  f"Delete {len(ids)} selected result records?\n\n"
                  "Engineering files and database run history will not be deleted.")
        if not messagebox.askyesno(title, prompt):
            return
        result = remove_result_jobs(ids)
        self.refresh_all()
        if not result["ok"]:
            messagebox.showerror(title, result["message"])

    def view_running_job(self) -> None:
        queue_id = self.runner_context.get("queue_id")
        self.open_task_details(queue_id)

    def _populate_detail_more_menu(self) -> None:
        menu = self.detail_more_menu
        menu.delete(0, "end")
        job = self._inspection_job()
        if not job:
            menu.add_command(label="No task selected" if self.lang == "en" else "未选择任务", state="disabled")
            return
        queue_id = job["queue_id"]
        visible = self._inspection_visible(job)
        if job.get("status") in config.ACTIVE_STATUSES or job.get("status") == "RUNNING":
            for key in ("open_inp", "copy_inp", "preflight", "top", "up", "down", "remove"):
                menu.add_command(label=self._menu_label(key),
                                 command=lambda action=key: self._queue_context_action(action, queue_id),
                                 state="normal" if key not in {"top", "up", "down", "remove"} or
                                 (visible and job.get("status") == "QUEUED" and
                                  self._queue_mutations_allowed(queue_display_jobs(load_queue())))
                                 else "disabled")
            menu.add_command(label=self._texts()["menus"]["skip"], command=lambda: self.skip_selected(queue_id),
                             state="normal" if visible and job.get("status") == "QUEUED" else "disabled")
        else:
            for key in ("copy_id", "copy_name", "copy_inp", "copy_odb", "locate_outputs",
                        "failure_summary", "run_history", "requeue", "delete_result"):
                enabled = (key != "run_history" or self.project_manager.current is not None)
                enabled = enabled and (key != "failure_summary" or normalize_status(job.get("status")) == "FAILED")
                enabled = enabled and (key not in {"requeue", "delete_result"} or
                                       (visible and job.get("status") in config.RESULT_STATUSES and
                                        self._queue_mutations_allowed(queue_display_jobs(load_queue()))))
                callback = (lambda: self.clear_selected_result(queue_id)) if key == "delete_result" else (
                    lambda action=key: self._results_context_action(action, queue_id))
                menu.add_command(label=self._menu_label(key), command=callback,
                                 state="normal" if enabled else "disabled")

    def _selected_result_action(self, action: str) -> None:
        if len(self._selected_visible_ids(self.results_tree)) != 1:
            messagebox.showwarning("Results", "Select exactly one result for this action.")
            return
        job = self._selected_job(self.results_tree)
        if job and job.get("status") in config.RESULT_STATUSES and self.results_tree.exists(row_iid(job, results=True)):
            self._results_context_action(action, job["queue_id"])
        else:
            messagebox.showwarning("Results", "Select a result first.")

    def _menu_label(self, key: str) -> str:
        return MENU_LABELS[key][1 if self.lang == "zh" else 0]

    def _menu_item(self, menu: tk.Menu, key: str, callback, enabled: bool = True) -> None:
        menu.add_command(label=self._menu_label(key), command=callback, state="normal" if enabled else "disabled")

    def _show_queue_menu(self, event) -> None:
        iid = self.queue_tree.identify_row(event.y)
        if iid and iid not in self.queue_tree.selection():
            self.queue_tree.selection_set(iid)
        self._last_selected_tree = self.queue_tree
        job_id = selected_job_id(iid)
        job = self.job_by_id.get(job_id) if job_id else None
        active = queue_display_jobs(load_queue())
        index = next((index for index, item in enumerate(active) if item.get("queue_id") == job_id), -1)
        single = len(self._selected_visible_ids(self.queue_tree)) == 1
        editable = bool(single and job and job.get("status") == "QUEUED" and self._queue_mutations_allowed(active))
        menu = tk.Menu(self, tearoff=False)
        self._menu_item(menu, "view_details", lambda: self.open_task_details(job_id), bool(job))
        self._menu_item(menu, "view_logs", lambda: self.open_task_details(job_id, initial_tab="logs"), bool(job))
        for key in ("open_inp", "open_inp_folder", "copy_inp", "copy_name"):
            self._menu_item(menu, key, lambda action=key: self._queue_context_action(action, job_id), bool(job))
        menu.add_separator()
        self._menu_item(menu, "refresh", self.refresh_all)
        self._menu_item(menu, "preflight", lambda: self._queue_context_action("preflight", job_id), bool(job))
        self._menu_item(menu, "output_folder", lambda: self._queue_context_action("output_folder", job_id), bool(job))
        menu.add_separator()
        for key, enabled in (("top", index > 0), ("up", index > 0), ("down", 0 <= index < len(active) - 1)):
            self._menu_item(menu, key, lambda action=key: self._queue_context_action(action, job_id), editable and enabled)
        self._menu_item(menu, "remove", lambda: self._queue_context_action("remove", job_id), editable)
        self._append_selection_menu(menu, self.queue_tree)
        self._post_menu(menu, event)

    def _show_results_menu(self, event) -> None:
        iid = self.results_tree.identify_row(event.y)
        if iid and iid not in self.results_tree.selection():
            self.results_tree.selection_set(iid)
        self._last_selected_tree = self.results_tree
        job_id = selected_job_id(iid, results=True)
        job = self.job_by_id.get(job_id) if job_id else None
        mutable = bool(len(self._selected_visible_ids(self.results_tree)) == 1 and
                       job and job.get("status") in config.RESULT_STATUSES and
                       self._queue_mutations_allowed(queue_display_jobs(load_queue())))
        menu = tk.Menu(self, tearoff=False)
        self._menu_item(menu, "view_details", lambda: self.open_task_details(job_id), bool(job))
        self._menu_item(menu, "view_logs", lambda: self.open_task_details(job_id, initial_tab="logs"), bool(job))
        for key, field in (("work_folder", "work_dir"), ("odb_folder", "odb_path"),
                           ("sta", "sta_path"), ("msg", "msg_path"), ("dat", "dat_path"), ("log", "log_path")):
            path = job.get(field) if job else None
            target = Path(path).parent if path and key == "odb_folder" else Path(path) if path else None
            self._menu_item(menu, key, lambda action=key: self._results_context_action(action, job_id), bool(target and target.exists()))
        menu.add_separator()
        for key, field in (("copy_id", "queue_id"), ("copy_name", "job_name"),
                           ("copy_inp", "inp_path"), ("copy_odb", "odb_path")):
            self._menu_item(menu, key, lambda action=key: self._results_context_action(action, job_id), bool(job and job.get(field)))
        menu.add_separator()
        self._menu_item(menu, "refresh_status", lambda: self._results_context_action("refresh_status", job_id), bool(job))
        self._menu_item(menu, "locate_outputs", lambda: self._results_context_action("locate_outputs", job_id), bool(job))
        self._menu_item(menu, "failure_summary", lambda: self._results_context_action("failure_summary", job_id),
                        bool(job and (str(job.get("status", "")).startswith(("FAILED", "DATACHECK_FAILED")))))
        self._menu_item(menu, "run_history", lambda: self._results_context_action("run_history", job_id),
                        bool(job and self.project_manager.current))
        menu.add_separator()
        self._menu_item(menu, "requeue", lambda: self._results_context_action("requeue", job_id), mutable)
        self._menu_item(menu, "delete_result", lambda: self.clear_selected_result(job_id), mutable)
        self._append_selection_menu(menu, self.results_tree)
        self._post_menu(menu, event)

    def _post_menu(self, menu: tk.Menu, event) -> None:
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _queue_mutations_allowed(self, active: list[dict]) -> bool:
        return not self.runner.is_running() and not any(
            normalize_status(job.get("status")) == "RUNNING" for job in active
        )

    def _current_job(self, job_id: str | None) -> dict | None:
        if not job_id:
            return None
        return next((job for job in load_queue() if job.get("queue_id") == job_id), None)

    def _copy_text(self, value: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(str(value))

    def _open_job_folder(self, folder: str | None) -> None:
        if not folder or not Path(folder).is_dir():
            messagebox.showerror("Open Folder", f"Folder does not exist:\n{folder or ''}")
            return
        open_folder(folder)

    def _open_job_text(self, path: str | None) -> None:
        if not path or not Path(path).is_file():
            messagebox.showerror("Open File", f"File does not exist:\n{path or ''}")
            return
        try:
            subprocess.Popen(["notepad.exe", str(path)])
        except OSError as exc:
            messagebox.showerror("Open File", str(exc))

    def _queue_context_action(self, action: str, job_id: str | None) -> None:
        job = self._current_job(job_id)
        if not job:
            messagebox.showwarning("Queue", "Selected job is no longer in the queue.")
            self.refresh_all()
            return
        if action == "open_inp":
            self._open_job_text(job.get("inp_path"))
        elif action == "open_inp_folder":
            self._open_job_folder(str(Path(job["inp_path"]).parent))
        elif action in {"copy_inp", "copy_name"}:
            self._copy_text(job.get("inp_path" if action == "copy_inp" else "job_name", ""))
        elif action == "output_folder":
            odb_path = job.get("odb_path")
            self._open_job_folder(str(Path(odb_path).parent) if odb_path else job.get("work_dir"))
        elif action == "preflight":
            request = JobRequest(
                inp_path=job["inp_path"], job_name=job.get("job_name"), cpus=job.get("cpus", 14),
                gpus=job.get("gpus", 0), batch=job.get("batch_name"), strategy=job.get("strategy_name"),
                working_dir=job.get("work_dir"),
            )
            result = AbqJobPilotClient(runtime_dir=config.RUNTIME_DIR).preflight(request)
            details = "\n".join(filter(None, (
                result.status,
                f"INP: {result.inp_path}",
                f"CPUs: {result.cpus}",
                f"Expected ODB: {result.expected_odb_path}",
                *result.warnings,
                *result.errors,
            )))
            messagebox.showinfo("Preflight", details)
        elif action in {"top", "up", "down", "remove"}:
            if not self._queue_mutations_allowed(queue_display_jobs(load_queue())):
                messagebox.showwarning("Queue", "Queue changes are disabled while a job is running.")
                return
            if action == "remove":
                if not messagebox.askyesno("Remove from Queue", "Remove this queue record only?\n\n"
                                           "INP and Abaqus output files will remain untouched.\n\n"
                                           f"Job: {job.get('job_name', '')}"):
                    return
                result = remove_queued_job(job["queue_id"])
            else:
                result = move_queued_job(job["queue_id"], action)
            self.refresh_all()
            if not result.get("ok"):
                messagebox.showerror("Queue", result["message"])

    def _results_context_action(self, action: str, job_id: str | None) -> None:
        job = self._current_job(job_id)
        if not job or not result_display_jobs([job]):
            messagebox.showwarning("Results", "Selected result is no longer available.")
            self.refresh_all()
            return
        if action == "work_folder":
            self._open_job_folder(job.get("work_dir"))
        elif action == "odb_folder":
            self._open_job_folder(str(Path(job["odb_path"]).parent) if job.get("odb_path") else None)
        elif action in {"sta", "msg", "dat", "log"}:
            self._open_job_text(job.get(f"{action}_path"))
        elif action in {"copy_id", "copy_name", "copy_inp", "copy_odb"}:
            field = {"copy_id": "queue_id", "copy_name": "job_name", "copy_inp": "inp_path", "copy_odb": "odb_path"}[action]
            self._copy_text(job.get(field, ""))
        elif action == "refresh_status":
            status = AbqJobPilotClient(runtime_dir=config.RUNTIME_DIR).status(job_id=job_id)
            details = "\n".join(filter(None, (status.status, f"ODB exists: {status.odb_exists}",
                                               f"Lock exists: {status.lock_exists}", *status.warnings, *status.errors)))
            messagebox.showinfo("Job Status", details)
            self.refresh_all()
        elif action == "locate_outputs":
            outputs = AbqJobPilotClient(runtime_dir=config.RUNTIME_DIR).locate_outputs(job_id=job_id)
            details = "\n".join(filter(None, (f"Work dir: {outputs.working_dir}",
                                               f"ODB: {outputs.expected_odb_path}",
                                               f"ODB exists: {outputs.odb_exists}",
                                               *outputs.log_paths, *outputs.warnings, *outputs.errors)))
            messagebox.showinfo("Outputs", details)
        elif action == "failure_summary":
            self._show_failure_summary(job)
        elif action == "run_history":
            self._show_run_history(job)
        elif action == "requeue":
            if not self._queue_mutations_allowed(queue_display_jobs(load_queue())):
                messagebox.showwarning("Requeue", "Requeue is disabled while a job is running.")
                return
            result = requeue_result_job(job_id)
            self.refresh_all()
            if result.get("ok"):
                messagebox.showinfo("Requeue", f"Queued {result['job_name']}. A runner already active in another "
                                    "process may pick it up; otherwise use Start Queue.")
            else:
                messagebox.showerror("Requeue", result.get("message", "Requeue failed."))

    def _show_failure_summary(self, job: dict) -> None:
        window = tk.Toplevel(self)
        window.title(f"Failure Summary - {job.get('job_name', '')}")
        window.geometry("920x580")
        text_widget = scrolledtext.ScrolledText(window, wrap="none", font=("Consolas", 10))
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        lines = [f"Job: {job.get('job_name', '')}", f"Status: {job.get('status', '')}",
                 f"Reason: {job.get('fatal_reason') or '(none)'}"]
        for suffix in ("sta", "msg", "dat"):
            path = job.get(f"{suffix}_path")
            content = tail_text(path, 30) if path else ""
            lines.extend(("", f"{suffix.upper()} tail: {path or '(not recorded)'}", content or "(missing or empty)"))
        text_widget.insert("1.0", "\n".join(lines))
        text_widget.configure(state="disabled")

    def _show_run_history(self, job: dict) -> None:
        project = self.project_manager.current
        if project is None:
            messagebox.showinfo("Run History", "Open a Project to view durable Run history.")
            return
        try:
            sync_history_from_runtime(project.root)
            repository = ProjectHistoryRepository(project)
            logical = repository.find_job_by_queue_id(job["queue_id"])
            runs = repository.list_runs(logical["job_id"]) if logical else []
        except (OSError, ValueError, DatabaseFailure) as exc:
            messagebox.showerror("Run History", str(exc))
            return
        if not runs:
            messagebox.showinfo("Run History", "No indexed attempts for this Job.")
            return
        window = tk.Toplevel(self)
        window.title(f"Run History - {job.get('job_name', '')}")
        window.geometry("1100x430")
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        columns = ("attempt", "status", "started", "completed", "cpus", "gpus", "working_dir", "odb")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        for column, width in (("attempt", 75), ("status", 125), ("started", 150), ("completed", 150),
                              ("cpus", 55), ("gpus", 55), ("working_dir", 240), ("odb", 260)):
            tree.heading(column, text=column.replace("_", " ").title())
            tree.column(column, width=width, minwidth=width)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        self._configure_status_tags(tree)
        for run in runs:
            label, tag = status_presentation(run.get("raw_status") or run.get("status"), self.lang)
            tree.insert("", "end", tags=(tag,), values=(run["attempt_no"], label, run["started_at"] or "",
                                             run["completed_at"] or "", run["cpus"] if run["cpus"] is not None else "",
                                             run["gpus"] if run["gpus"] is not None else "",
                                             run["working_dir"] or "", run["expected_odb_path"] or ""))

    def _sta_table_text(self, text: str) -> str:
        if not text:
            return STA_HEADER + "\n" + "-" * len(STA_HEADER)
        return STA_HEADER + "\n" + "-" * len(STA_HEADER) + "\n" + text

    def _set_text(self, widget: scrolledtext.ScrolledText, text: str, *, follow: bool = True) -> None:
        if widget.get("1.0", "end-1c") == text:
            return
        previous_position = widget.yview()[0]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        if follow:
            widget.see("end")
        else:
            widget.yview_moveto(previous_position)
        widget.configure(state="disabled")

    def _refresh_resource_usage(self) -> None:
        percent = self._read_cpu_percent()
        if percent is None:
            self.cpu_percent_var.set("--%")
        else:
            percent = max(0, min(100, int(percent)))
            self.cpu_percent_var.set(f"{percent}%")
        self.memory_percent_var.set(self._read_memory_text())
        self.gpu_percent_var.set(self._read_gpu_text())
        prefix = "本机" if self.lang == "zh" else "Local machine"
        self.resource_line_var.set(f"{prefix}: CPU {self.cpu_percent_var.get()} · "
                                   f"{self._texts()['resources']['memory']} {self.memory_percent_var.get()} · "
                                   f"GPU {self.gpu_percent_var.get()}")

    def _read_cpu_percent(self) -> int | None:
        current = self._get_system_cpu_times()
        if current is None:
            return None
        previous = self._last_cpu_times
        self._last_cpu_times = current
        if previous is None:
            return None
        idle_delta = current[0] - previous[0]
        kernel_delta = current[1] - previous[1]
        user_delta = current[2] - previous[2]
        total_delta = kernel_delta + user_delta
        if total_delta <= 0:
            return None
        busy = max(0, total_delta - idle_delta)
        return round((busy / total_delta) * 100)

    def _get_system_cpu_times(self) -> tuple[int, int, int] | None:
        class FileTime(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

        idle = FileTime()
        kernel = FileTime()
        user = FileTime()
        try:
            ok = ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        except AttributeError:
            return None
        if not ok:
            return None
        return (
            (idle.dwHighDateTime << 32) + idle.dwLowDateTime,
            (kernel.dwHighDateTime << 32) + kernel.dwLowDateTime,
            (user.dwHighDateTime << 32) + user.dwLowDateTime,
        )

    def _read_memory_text(self) -> str:
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        try:
            ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        except AttributeError:
            return "--"
        if not ok:
            return "--"
        used_gb = (status.ullTotalPhys - status.ullAvailPhys) / (1024 ** 3)
        total_gb = status.ullTotalPhys / (1024 ** 3)
        return f"{status.dwMemoryLoad}%  {used_gb:.1f}/{total_gb:.1f} GB"

    def _read_gpu_text(self) -> str:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=1.5,
                creationflags=flags,
            )
        except (OSError, subprocess.SubprocessError):
            return "--"
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return "--"
        try:
            util, mem_used, mem_total = [part.strip() for part in lines[0].split(",")[:3]]
        except ValueError:
            return "--"
        return f"{util}%  {mem_used}/{mem_total} MB"

    def _system_idle_seconds(self) -> float | None:
        class LastInputInfo(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        info = LastInputInfo()
        info.cbSize = ctypes.sizeof(LastInputInfo)
        try:
            ok = ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
            tick_count = ctypes.windll.kernel32.GetTickCount()
        except AttributeError:
            return None
        if not ok:
            return None
        elapsed_ms = (int(tick_count) - int(info.dwTime)) & 0xFFFFFFFF
        return max(0.0, elapsed_ms / 1000.0)

    def _check_auto_shutdown_after_queue(self) -> None:
        running = self.runner.is_running()
        if running:
            self._runner_was_running = True
            self._queue_completed_monotonic = None
            self._shutdown_requested = False
            return

        if not self._runner_was_running:
            return

        settings = load_settings()
        if not settings.get("auto_shutdown_enabled"):
            self._queue_completed_monotonic = None
            self._runner_was_running = False
            self._shutdown_requested = False
            return

        if self._queue_completed_monotonic is None:
            self._queue_completed_monotonic = time.monotonic()
            return

        idle_minutes = max(1, int(settings.get("auto_shutdown_idle_minutes") or 5))
        required_seconds = idle_minutes * 60
        elapsed_after_queue = time.monotonic() - self._queue_completed_monotonic
        idle_seconds = self._system_idle_seconds()
        if idle_seconds is None:
            return
        if elapsed_after_queue >= required_seconds and idle_seconds >= required_seconds and not self._shutdown_requested:
            self._request_windows_shutdown(idle_minutes)

    def _request_windows_shutdown(self, idle_minutes: int) -> None:
        self._shutdown_requested = True
        message = (
            "abqjobpilot queue finished and the system has been idle. "
            "Shutdown will begin in 60 seconds. Run 'shutdown /a' to abort."
        )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(
                ["shutdown", "/s", "/t", "60", "/c", message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
        except OSError:
            self._shutdown_requested = False
            return
        try:
            status = read_json(config.LIVE_STATUS_FILE, {})
            if not isinstance(status, dict):
                status = {}
            status.update(
                {
                    "schema_version": config.SCHEMA_VERSION,
                    "phase": "AUTO_SHUTDOWN_REQUESTED",
                    "auto_shutdown_idle_minutes": idle_minutes,
                    "updated_at": now_iso(),
                }
            )
            write_json(config.LIVE_STATUS_FILE, status)
        except OSError:
            pass

    def add_inp(self) -> None:
        path = filedialog.askopenfilename(title="Select Abaqus INP", filetypes=[("Abaqus input", "*.inp"), ("All files", "*.*")])
        if not path:
            return
        settings = load_settings()
        result = add_inp_job_to_queue(
            path,
            cpus=settings["default_cpus"],
            gpus=settings["default_gpus"] if settings["use_gpu"] else 0,
            run_datacheck=settings["run_datacheck"],
            run_full=settings["run_full"],
        )
        self.refresh_all()
        if result.get("ok"):
            messagebox.showinfo("Add INP", f"Added job: {result['job_name']}")
        else:
            messagebox.showerror("Add INP", result.get("message", "Failed to add INP"))

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder containing INP files")
        if not folder:
            return
        settings = load_settings()
        result = add_folder_to_queue(
            folder,
            cpus=settings["default_cpus"],
            gpus=settings["default_gpus"] if settings["use_gpu"] else 0,
        )
        self.refresh_all()
        if result.get("added"):
            messagebox.showinfo("Add Folder", f"Added {len(result['added'])} job(s).")
        else:
            messagebox.showerror("Add Folder", result.get("message", "No jobs added"))

    def open_settings(self) -> None:
        BasicSettingsDialog(self, on_saved=lambda _settings: self.refresh_all())

    def open_agent_console(self) -> None:
        if self._agent_console is not None and self._agent_console.winfo_exists():
            self._agent_console.lift()
            return
        self._agent_console = AgentCommandConsole(self, on_queue_changed=self.refresh_all, language=self.lang)

    def show_agent_capabilities(self) -> None:
        capabilities = AbqJobPilotClient(runtime_dir=config.RUNTIME_DIR).capabilities()
        title = "接口能力" if self.lang == "zh" else "Capabilities"
        messagebox.showinfo(title, json.dumps(capabilities, ensure_ascii=False, indent=2))

    def open_automation_docs(self) -> None:
        path = config.APP_ROOT_PATH / "docs" / "ABQJOBPILOT_PUBLIC_API.md"
        if path.is_file():
            self._open_job_text(str(path))
        else:
            self._copy_text(str(path))
            messagebox.showwarning("Documentation", f"Documentation not found. Path copied:\n{path}")

    def show_automation_about(self) -> None:
        title = "关于自动化接口" if self.lang == "zh" else "About Automation Interface"
        message = ("AbqJobPilot 提供轻量自动化接口，用于任务预检、入队、状态查询和输出定位。\n"
                   "它不是 AI Runtime；公开自动化接口不提供求解器启动。" if self.lang == "zh" else
                   "AbqJobPilot provides a thin automation interface for job preparation, queueing, "
                   "status inspection, and output discovery.\nIt is not an AI Runtime. "
                   "The public automation surface does not expose solver start.")
        messagebox.showinfo(title, message)

    def toggle_language(self) -> None:
        self.lang = "zh" if self.lang == "en" else "en"
        self._rendered_inspection = None
        self._rendered_rows.clear()
        self._refresh_status()
        self._refresh_live_logs()
        self._refresh_tables_from_cache()
        self._apply_language()
        self._refresh_inspection()
        if self._agent_console is not None and self._agent_console.winfo_exists():
            self._agent_console.set_language(self.lang)

    def show_help(self) -> None:
        if getattr(self, "about_window", None) is not None and self.about_window.winfo_exists():
            self.about_window.lift()
            return
        words = self._texts()["about"]
        window = tk.Toplevel(self)
        self.about_window = window
        window.title(words["title"])
        window.resizable(False, False)
        window.transient(self)
        body = ttk.Frame(window, padding=20)
        body.grid(row=0, column=0, sticky="nsew")
        ttk.Label(body, text="AbqJobPilot", font=("Segoe UI Semibold", 16)).grid(row=0, column=0, sticky="w")
        self.about_version_label = ttk.Label(body, text=f"{words['version']} {__version__} · {words['build']}")
        self.about_version_label.grid(row=1, column=0, sticky="w", pady=(4, 12))
        self.about_description_label = ttk.Label(body, text=words["description"], wraplength=530, justify="left")
        self.about_description_label.grid(row=2, column=0, sticky="w", pady=(0, 12))
        self.about_ownership_label = ttk.Label(body, text=words["ownership"], wraplength=530, justify="left")
        self.about_ownership_label.grid(row=3, column=0, sticky="w", pady=(0, 16))
        ttk.Label(body, text=words["source"]).grid(row=4, column=0, sticky="w")
        self.about_repo_label = ttk.Label(body, text=STABLE_GITHUB_URL or words["unavailable"],
                                          foreground=COLORS["accent"] if STABLE_GITHUB_URL else COLORS["muted"])
        self.about_repo_label.grid(row=5, column=0, sticky="w", pady=(3, 12))
        actions = ttk.Frame(body)
        actions.grid(row=6, column=0, sticky="e")
        self.about_open_button = ttk.Button(actions, text=words["open"],
                                            command=lambda: webbrowser.open(STABLE_GITHUB_URL)
                                            if STABLE_GITHUB_URL else None)
        self.about_open_button.grid(row=0, column=0, padx=(0, 8))
        self.about_copy_button = ttk.Button(actions, text=words["copy"],
                                            command=lambda: self._copy_text(STABLE_GITHUB_URL)
                                            if STABLE_GITHUB_URL else None)
        self.about_copy_button.grid(row=0, column=1)
        if not STABLE_GITHUB_URL:
            self.about_open_button.configure(state="disabled")
            self.about_copy_button.configure(state="disabled")

    def open_task_manager_performance(self) -> None:
        try:
            subprocess.Popen(["taskmgr.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.after(900, self._try_switch_task_manager_to_performance)
        except OSError:
            messagebox.showerror("Task Manager", "Unable to open taskmgr.exe")

    def _try_switch_task_manager_to_performance(self) -> None:
        hwnd = self._find_window_by_title(("Task Manager", "任务管理器"))
        if not hwnd:
            return
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            self.after(200, self._send_ctrl_tab)
        except OSError:
            return

    def _find_window_by_title(self, title_parts: tuple[str, ...]) -> int:
        user32 = ctypes.windll.user32
        matches: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_proc(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
            if any(part in title for part in title_parts):
                matches.append(hwnd)
                return False
            return True

        user32.EnumWindows(enum_proc, 0)
        return matches[0] if matches else 0

    def _send_ctrl_tab(self) -> None:
        user32 = ctypes.windll.user32
        key_event = user32.keybd_event
        vk_control = 0x11
        vk_tab = 0x09
        key_up = 0x0002
        key_event(vk_control, 0, 0, 0)
        key_event(vk_tab, 0, 0, 0)
        key_event(vk_tab, 0, key_up, 0)
        key_event(vk_control, 0, key_up, 0)

    def start_queue(self) -> None:
        queued_count = sum(1 for job in load_queue() if job.get("status") in {"QUEUED", "DATACHECK_OK"})
        if queued_count == 0:
            messagebox.showinfo("Start Queue", "No QUEUED or DATACHECK_OK jobs to run.")
            return
        if not messagebox.askyesno(
            "Start Queue",
            f"This starts the entire executable queue ({queued_count} job(s)), not only visible or "
            "selected rows. Continue?",
        ):
            return
        result = self.runner.start()
        if result.get("ok"):
            self._runner_was_running = True
            self._queue_completed_monotonic = None
            self._shutdown_requested = False
        self.refresh_all()
        if not result.get("ok"):
            messagebox.showwarning("Start Queue", result.get("message", "Runner did not start."))

    def stop_after_current(self) -> None:
        result = self.runner.request_stop_after_current()
        messagebox.showinfo("Stop After Current Job", result["message"])

    def skip_selected(self, job_id: str | None = None) -> None:
        if job_id:
            job = self._current_job(job_id)
        elif self._last_selected_tree is self.queue_tree:
            if len(self._selected_visible_ids(self.queue_tree)) != 1:
                messagebox.showwarning("Skip Selected", "Select exactly one queued job.")
                return
            job = self._selected_job(self.queue_tree)
        else:
            job = None
        if not job:
            messagebox.showwarning("Skip Selected", "Select a queued job first.")
            return
        if job.get("status") != "QUEUED":
            messagebox.showwarning("Skip Selected", "Only QUEUED jobs can be skipped.")
            return
        result = mark_job_skipped(job["queue_id"])
        self.refresh_all()
        if result.get("ok"):
            messagebox.showinfo("Skip Selected", result["message"])
        else:
            messagebox.showerror("Skip Selected", result.get("message", "Failed to skip job."))

    def clear_selected_result(self, job_id: str | None = None) -> None:
        if job_id is None and self._last_selected_tree is self.results_tree and len(self._selected_visible_ids(self.results_tree)) > 1:
            self._delete_selected_results()
            return
        if job_id:
            job = self._current_job(job_id)
        elif self._last_selected_tree is self.results_tree:
            job = self._selected_job(self.results_tree)
        else:
            job = None
        title = "Clear Selected Result" if self.lang == "en" else "清除选中结果"
        if not job:
            messagebox.showwarning(title, "Select a result row first." if self.lang == "en" else "请先选中结果表中的一行。")
            return
        if job.get("status") not in config.RESULT_STATUSES:
            messagebox.showwarning(
                title,
                "Only completed, failed, skipped, or cancelled result rows can be cleared."
                if self.lang == "en"
                else "只能清除已完成、失败、跳过或取消的结果记录。",
            )
            return
        if not self._queue_mutations_allowed(queue_display_jobs(load_queue())):
            messagebox.showwarning(title, "Result changes are disabled while a job is running.")
            return
        confirm = messagebox.askyesno(
            title,
            (
                "Clear this result record from abqjobpilot queue history?\n\n"
                "This will not delete Abaqus files such as .inp, .odb, .sta, .msg, .dat, or .log.\n\n"
                f"Job: {job.get('job_name', '')}"
            )
            if self.lang == "en"
            else (
                "从 abqjobpilot 队列历史中清除这条结果记录？\n\n"
                "这不会删除 Abaqus 文件，例如 .inp、.odb、.sta、.msg、.dat 或 .log。\n\n"
                f"Job: {job.get('job_name', '')}"
            ),
        )
        if not confirm:
            return
        result = remove_result_job(job["queue_id"])
        self.refresh_all()
        if result.get("ok"):
            messagebox.showinfo(
                title,
                result["message"] if self.lang == "en" else "结果记录已清除，可以重新加入同一个 INP。",
            )
        else:
            messagebox.showerror(title, result.get("message", "Failed to clear result."))

    def open_selected_work_folder(self) -> None:
        job = self._inspection_job() or self._selected_job()
        if not job:
            messagebox.showwarning("Open Work Folder", "Select a queue or result row first.")
            return
        work_dir = job.get("work_dir", "")
        if not work_dir or not Path(work_dir).exists():
            messagebox.showerror("Open Work Folder", f"Folder does not exist:\n{work_dir}")
            return
        open_folder(work_dir)

    def copy_console_for_ai(self) -> None:
        if self._inspection_job():
            self._copy_text(self.log_text.get("1.0", "end-1c"))

    def _update_status_light(self, state: str) -> None:
        color = {"running": COLORS["accent"], "uncertain": COLORS["warning"],
                 "idle": COLORS["muted"]}[state]
        self.status_light.itemconfigure(self.status_light_id, fill=color, outline="")

    def _texts(self) -> dict:
        if self.lang == "zh":
            return {
                "menus": {"project": "项目", "task": "任务", "view": "视图", "tools": "工具", "agent_top": "智能体", "help": "帮助",
                          "about_app": "关于 AbqJobPilot",
                          "add_task": "添加任务", "add_inp": "添加 INP", "add_folder": "添加文件夹",
                          "view_details": "查看详情",
                          "skip": "跳过选中", "requeue": "重新入队", "delete_result": "删除结果记录",
                          "queue": "队列", "results": "结果", "refresh": "刷新", "settings": "基础设置",
                          "agent": "智能体命令", "language": "English", "task_manager": "任务管理器", "exit": "退出"},
                "agent_menu": {"console": "智能体命令控制台", "instruction": "复制 AI 指令模板",
                               "examples": "复制 CLI 示例", "capabilities": "接口能力",
                               "docs": "自动化 API 文档", "about": "关于自动化接口"},
                "about": {"title": "关于 AbqJobPilot", "version": "版本", "build": "开发版本",
                          "description": "一款面向 Abaqus 的轻量本地作业管理、批量运行与监控工具。用于管理 INP 作业队列、监控求解状态与日志、查看运行历史，并提供轻量的机器可读自动化接口。",
                          "ownership": "Project 仅保存作业、运行记录和文件引用；CAE、INP、ODB 等工程文件仍保留在原始工程目录中。",
                          "source": "稳定版 / 源代码：", "open": "打开 GitHub", "copy": "复制链接",
                          "unavailable": "仓库链接不可用"},
                "project_menu": {"new": "新建项目", "open": "打开项目", "close": "关闭项目",
                                 "folder": "打开管理项目目录", "recent": "最近项目", "export": "导出项目",
                                 "import": "导入项目", "legacy": "导入旧版 runtime"},
                "details": {"running": "查看运行任务", "work_folder": "打开任务工作目录", "more": "更多",
                            "collapse": "收起", "expand": "展开", "overview": "概览", "files": "文件引用",
                            "logs": "日志", "history": "运行历史", "follow": "跟随末尾",
                            "copy": "复制", "copy_path": "复制路径", "open_folder": "打开所在目录",
                            "open_file": "打开文本文件", "search": "搜索作业名、批次、策略或 INP 路径"},
                "buttons": {
                    "add_inp": "添加 INP",
                    "add_folder": "添加文件夹",
                    "settings": "基础设置",
                    "agent_command": "智能体命令",
                    "refresh": "刷新",
                    "start_queue": "开始队列",
                    "stop_after_current": "当前作业结束后停止",
                    "skip_selected": "跳过选中",
                    "clear_selected_result": "清除结果",
                    "open_work_folder": "打开工作文件夹",
                    "exit": "退出",
                    "language": "English",
                    "help": "帮助",
                },
                "frames": {
                    "status": "当前运行状态",
                    "queue": "当前队列",
                    "results": "结果",
                    "logs": "日志",
                    "sta_tail": "STA 尾部",
                    "console_tail": "控制台日志尾部",
                    "resource_usage": "资源使用率",
                },
                "status": {
                    "current_job": "当前 Job",
                    "strategy": "策略",
                    "batch": "批次",
                    "phase": "阶段",
                    "step": "Step",
                    "increment": "Increment",
                    "analysis_time": "分析时间",
                    "odb_size": "ODB 大小",
                    "started_at": "开始时间",
                    "elapsed_time": "已运行秒数",
                },
                "copy_console": "Copy",
                "resources": {"cpu": "CPU", "memory": "内存", "gpu": "GPU"},
                "task_manager": "任务管理器",
                "queue_headings": {
                    "index": "序号", "status": "状态", "batch": "批次", "strategy": "策略", "job": "Job 名称",
                    "cpus": "CPU", "gpus": "GPU", "created": "创建时间", "inp": "INP 路径",
                },
                "result_headings": {
                    "status": "状态", "batch": "批次", "strategy": "策略", "job": "Job 名称",
                    "started": "开始", "ended": "结束", "duration": "耗时", "odb": "ODB 大小",
                    "warnings": "警告", "fatal": "失败原因",
                },
            }
        return {
            "menus": {"project": "Project", "task": "Task", "view": "View", "tools": "Tools", "agent_top": "Agent", "help": "Help",
                      "about_app": "About AbqJobPilot",
                      "add_task": "Add Task", "add_inp": "Add INP", "add_folder": "Add Folder",
                      "view_details": "View Details",
                      "skip": "Skip Selected", "requeue": "Requeue", "delete_result": "Delete Result Record",
                      "queue": "Queue", "results": "Results", "refresh": "Refresh", "settings": "Settings",
                      "agent": "Agent Command", "language": "中文", "task_manager": "Task Manager", "exit": "Exit"},
            "agent_menu": {"console": "Agent Command Console", "instruction": "Copy AI Instruction",
                           "examples": "Copy CLI Examples", "capabilities": "Capabilities",
                           "docs": "Automation API Documentation", "about": "About Automation Interface"},
            "about": {"title": "About AbqJobPilot", "version": "Version", "build": "Development build",
                      "description": "A lightweight local job runner and monitoring tool for Abaqus. Organize INP queues, monitor live solver status and logs, review run history, and use a small machine-readable automation interface.",
                      "ownership": "Projects keep job metadata, run history, and file references. CAE, INP, ODB, and other solver files stay in their original engineering workspace.",
                      "source": "Stable release / source:", "open": "Open GitHub", "copy": "Copy Link",
                      "unavailable": "Repository link unavailable"},
            "project_menu": {"new": "New Project", "open": "Open Project", "close": "Close Project",
                             "folder": "Open Management Project Folder", "recent": "Recent Projects",
                             "export": "Export Project", "import": "Import Project", "legacy": "Import Legacy Runtime"},
            "details": {"running": "View Running Job", "work_folder": "Open Task Work Folder", "more": "More",
                        "collapse": "Collapse", "expand": "Expand", "overview": "Overview", "files": "File References",
                        "logs": "Logs", "history": "Run History", "follow": "Follow tail",
                        "copy": "Copy", "copy_path": "Copy Path", "open_folder": "Open Folder",
                        "open_file": "Open Text File", "search": "Search job, batch, strategy or INP path"},
            "buttons": {
                "add_inp": "Add INP",
                "add_folder": "Add Folder",
                "settings": "Settings",
                "agent_command": "Agent Command",
                "refresh": "Refresh",
                "start_queue": "Start Queue",
                "stop_after_current": "Stop After Current Job",
                "skip_selected": "Skip Selected",
                "clear_selected_result": "Clear Result",
                "open_work_folder": "Open Work Folder",
                "exit": "Exit",
                "language": "中文",
                "help": "Help",
            },
            "frames": {
                "status": "Current Running Status",
                "queue": "Current Queue",
                "results": "Results",
                "logs": "Logs",
                "sta_tail": "STA tail",
                "console_tail": "Console log tail",
                "resource_usage": "Resource Usage",
            },
            "status": {
                "current_job": "Current job",
                "strategy": "Strategy",
                "batch": "Batch",
                "phase": "Phase",
                "step": "Step",
                "increment": "Increment",
                "analysis_time": "Analysis time",
                "odb_size": "ODB size",
                "started_at": "Started at",
                "elapsed_time": "Elapsed time",
            },
            "copy_console": "Copy",
            "resources": {"cpu": "CPU", "memory": "Memory", "gpu": "GPU"},
            "task_manager": "Task Manager",
            "queue_headings": {
                "index": "Index", "status": "Status", "batch": "Batch", "strategy": "Strategy", "job": "Job Name",
                "cpus": "CPUs", "gpus": "GPUs", "created": "Created At", "inp": "INP Path",
            },
            "result_headings": {
                "status": "Status", "batch": "Batch", "strategy": "Strategy", "job": "Job Name",
                "started": "Started", "ended": "Ended", "duration": "Duration", "odb": "ODB Size",
                "warnings": "Warnings", "fatal": "Fatal Reason",
            },
        }

    def _apply_language(self) -> None:
        texts = self._texts()
        self._update_project_label()
        if getattr(self, "_menu_lang", None) != self.lang:
            self._build_menus()
            self._menu_lang = self.lang
        for key, button in self.toolbar_buttons.items():
            button.configure(text=texts["buttons"][key])
        for key, label in self.toolbar_button_labels.items():
            label.configure(text=texts["buttons"][key])
        details = texts["details"]
        self.view_running_button.configure(text=details["running"])
        self.detail_folder_button.configure(text=details["work_folder"])
        self.detail_more_button.configure(text=details["more"])
        self.detail_collapse_button.configure(text="关闭" if self.lang == "zh" else "Close")
        for tab, key in ((self.overview_tab, "overview"), (self.files_tab, "files"),
                         (self.logs_tab, "logs"), (self.history_tab, "history")):
            self.detail_notebook.tab(tab, text=details[key])
        self.follow_checkbox.configure(text=details["follow"])
        self.log_copy_button.configure(text=details["copy"])
        self.file_copy_button.configure(text=details["copy_path"])
        self.file_folder_button.configure(text=details["open_folder"])
        self.file_open_button.configure(text=details["open_file"])
        file_headings = (("kind", "类型" if self.lang == "zh" else "Kind"),
                         ("state", "当前状态" if self.lang == "zh" else "Current state"),
                         ("path", "已记录路径" if self.lang == "zh" else "Recorded path"))
        for column, title in file_headings:
            self.files_tree.heading(column, text=title)
        for column, title in (("attempt", "尝试"), ("status", "状态"), ("started", "开始"),
                              ("completed", "完成"), ("cpus", "CPU"), ("gpus", "GPU"),
                              ("working_dir", "工作目录"), ("odb", "ODB 路径")):
            self.history_tree.heading(column, text=title if self.lang == "zh" else column.replace("_", " ").title())
        self.refresh_button.configure(text=texts["menus"]["refresh"])
        self.queue_refresh_button.configure(text=texts["menus"]["refresh"])
        self.queue_more_button.configure(text=details["more"])
        self.results_more_button.configure(text=details["more"])
        self.search_label.configure(text="结果搜索" if self.lang == "zh" else "Search results")
        self.console_heading.configure(text="控制台日志" if self.lang == "zh" else "Console log")
        for side in ("solver", "console"):
            getattr(self, f"live_{side}_follow").configure(text=details["follow"])
        labels = self._status_filter_labels()
        self.status_filter.configure(values=labels)
        codes = ("all", "queued", "running", "completed", "warnings", "failed")
        self.status_filter.current(codes.index(self.filter_status_code))
        self._update_batch_choices()
        self._refresh_table_counts()
        self.footer_mode_var.set(("项目模式" if self.project_manager.current else "默认 runtime · 引用模式")
                                 if self.lang == "zh" else
                                 ("Project · reference mode" if self.project_manager.current else "Default runtime · reference mode"))
        if self.inspection_key is None:
            self.inspection_title_var.set("未选择任务" if self.lang == "zh" else "No task selected")
        for column, label in texts["queue_headings"].items():
            self.queue_tree.heading(column, text=label)
        for column, label in texts["result_headings"].items():
            self.results_tree.heading(column, text=label)

    def _selected_job(self, tree: ttk.Treeview | None = None) -> dict | None:
        widgets = (tree,) if tree else (self._last_selected_tree, self.queue_tree, self.results_tree)
        for widget in widgets:
            if widget is None:
                continue
            results = widget is self.results_tree
            selection = widget.selection()
            if selection:
                return self.job_by_id.get(selected_job_id(selection[0], results=results))
        return None


def main() -> None:
    app = AbqJobPilotApp()
    app.mainloop()
