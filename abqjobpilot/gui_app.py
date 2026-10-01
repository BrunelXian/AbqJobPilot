"""Main Tkinter GUI for abqjobpilot."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import subprocess
import tkinter as tk
import time
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

from . import config
from .command_console import AgentCommandConsole
from .gui_table_state import queue_display_jobs, result_display_jobs, restore_iid, row_iid, selected_job_id
from .queue_store import (
    add_folder_to_queue,
    add_inp_job_to_queue,
    apply_resources_to_queued_jobs,
    init_storage,
    load_queue,
    mark_job_skipped,
    move_queued_job,
    remove_queued_job,
    remove_result_job,
    requeue_result_job,
)
from .api import AbqJobPilotClient, JobRequest
from .project import ProjectInfo, ProjectManager, export_project_archive, import_legacy_runtime, import_project_archive
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
        self.title("abqjobpilot")
        self._apply_icon()
        self._set_initial_geometry()
        self.configure(background=COLORS["bg"])
        self.job_by_id: dict[str, dict] = {}
        self._rendered_rows: dict[str, list[tuple]] = {}
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
        self.rowconfigure(1, weight=1)
        self._build_widgets()
        self.refresh_all()
        self.after(config.POLL_INTERVAL_SECONDS * 1000, self._poll_refresh)

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
        width = min(1760, max(1500, int(screen_width * 0.9)))
        height = min(980, max(880, int(screen_height * 0.86)))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(1360, 760)

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
        style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground=COLORS["text"], rowheight=28, bordercolor=COLORS["panel_border"])
        style.configure("Treeview.Heading", background=COLORS["table_head"], foreground=COLORS["text"], font=("Segoe UI Semibold", 10), padding=(6, 6))
        style.map("Treeview", background=[("selected", COLORS["accent"])], foreground=[("selected", "#ffffff")])
        style.configure("Vertical.TScrollbar", background="#e2e8f0", troughcolor="#f8fafc", bordercolor="#e2e8f0")
        style.configure("Horizontal.TScrollbar", background="#e2e8f0", troughcolor="#f8fafc", bordercolor="#e2e8f0")

    def _build_widgets(self) -> None:
        self._build_toolbar()

        main_pane = ttk.PanedWindow(self, orient="vertical")
        main_pane.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        top_frame = ttk.Frame(main_pane)
        bottom_frame = ttk.Frame(main_pane)
        main_pane.add(top_frame, weight=3)
        main_pane.add(bottom_frame, weight=2)

        top_frame.columnconfigure(0, weight=0)
        top_frame.columnconfigure(1, weight=1)
        top_frame.rowconfigure(0, weight=1)
        self._build_status_area(top_frame)
        self._build_queue_area(top_frame)

        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.rowconfigure(0, weight=1)
        bottom_frame.rowconfigure(1, weight=1)
        self._build_results_area(bottom_frame)
        self._build_log_area(bottom_frame)

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self, padding=(14, 10, 14, 8))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(2, weight=1)

        left = ttk.Frame(toolbar)
        left.grid(row=0, column=0, sticky="w")
        run = ttk.Frame(toolbar)
        run.grid(row=0, column=1, sticky="w", padx=(18, 0))
        right = ttk.Frame(toolbar)
        right.grid(row=0, column=3, sticky="e")

        self._make_button(left, "add_inp", self.add_inp, 0)
        self._make_button(left, "add_folder", self.add_folder, 1)
        self._make_button(left, "agent_command", self.open_agent_console, 2)
        self._make_button(left, "settings", self.open_settings, 3)

        self._make_primary_button(run, "start_queue", self.start_queue, 0)
        self._make_button(run, "stop_after_current", self.stop_after_current, 1)
        self._make_button(run, "skip_selected", self.skip_selected, 2)
        self._make_button(run, "clear_selected_result", self.clear_selected_result, 3)
        self._make_button(run, "refresh", self.refresh_all, 4)

        self._make_button(right, "open_work_folder", self.open_selected_work_folder, 0)
        self._make_button(right, "language", self.toggle_language, 1)
        self._make_button(right, "help", self.show_help, 2)
        self._make_button(right, "exit", self.destroy, 3)

        project_bar = ttk.Frame(toolbar)
        project_bar.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(7, 0))
        ttk.Label(project_bar, textvariable=self.project_name_var, width=38).pack(side="left", padx=(0, 12))
        for key, action in (("new", self.new_project), ("open", self.open_project_dialog),
                            ("close", self.close_project), ("folder", self.open_project_folder),
                            ("export", self.export_project_dialog), ("import", self.import_project_dialog),
                            ("legacy", self.import_legacy_dialog)):
            button = ttk.Button(project_bar, command=action)
            button.pack(side="left", padx=(0, 5))
            self.project_controls[key] = button
        self.recent_menu = tk.Menu(self, tearoff=False)
        self.recent_button = ttk.Menubutton(project_bar, menu=self.recent_menu)
        self.recent_button.pack(side="left")
        self.recent_menu.configure(postcommand=self._populate_recent_menu)
        self._update_project_label()

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
        config.use_runtime_dir(project.runtime_dir if project else None)
        self.project_manager.current = project
        self._runner_was_running = False
        self._queue_completed_monotonic = None
        self._shutdown_requested = False
        self.job_by_id.clear()
        self._rendered_rows.clear()
        self._history_signature = None
        self.queue_tree.delete(*self.queue_tree.get_children())
        self.results_tree.delete(*self.results_tree.get_children())
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
        parent = filedialog.askdirectory(parent=self, title=title)
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

    def _populate_recent_menu(self) -> None:
        self.recent_menu.delete(0, "end")
        entries = self.project_manager.recent_projects()
        if not entries:
            self.recent_menu.add_command(label="No recent projects", state="disabled")
        for item in entries:
            self.recent_menu.add_command(
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
            project = import_project_archive(archive, destination[0])
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
            project = import_legacy_runtime(source, destination[0], destination[1])
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
        frame = ttk.LabelFrame(parent, text="Current Running Status", padding=10)
        self.frames["status"] = frame
        frame.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        frame.columnconfigure(2, weight=1)

        self.status_light = tk.Canvas(frame, width=18, height=18, highlightthickness=0, background=COLORS["panel"])
        self.status_light.grid(row=0, column=2, sticky="ne", padx=(10, 0))
        self.status_light_id = self.status_light.create_oval(3, 3, 15, 15, fill="#2fb344", outline="#1f7a2e")

        labels = ("current_job", "strategy", "batch", "phase", "step", "increment", "analysis_time", "odb_size", "started_at", "elapsed_time")
        for row, key in enumerate(labels):
            label_widget = ttk.Label(frame)
            label_widget.grid(row=row, column=0, sticky="w", pady=2)
            self.status_label_widgets[key] = label_widget
            var = tk.StringVar(value="")
            self.status_vars[key] = var
            ttk.Label(frame, textvariable=var, width=30).grid(row=row, column=1, sticky="w", pady=2)

    def _build_queue_area(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Current Queue", padding=8)
        self.frames["queue"] = frame
        frame.grid(row=0, column=1, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.queue_tree = ttk.Treeview(frame, columns=QUEUE_COLUMNS, show="headings", selectmode="browse")
        widths = {"index": 54, "status": 130, "batch": 120, "strategy": 140, "job": 220, "cpus": 58, "gpus": 58, "created": 150, "inp": 360}
        self._configure_tree(self.queue_tree, {column: column for column in QUEUE_COLUMNS}, widths)
        self._configure_status_tags(self.queue_tree)
        self.queue_tree.grid(row=0, column=0, sticky="nsew")
        self._attach_scrollbars(frame, self.queue_tree)
        self.queue_tree.bind("<Button-3>", self._show_queue_menu)
        self.queue_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_table_select(self.queue_tree, self.results_tree))

    def _build_results_area(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Results", padding=8)
        self.frames["results"] = frame
        frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.results_tree = ttk.Treeview(frame, columns=RESULT_COLUMNS, show="headings", selectmode="browse")
        widths = {"status": 150, "batch": 120, "strategy": 140, "job": 220, "started": 150, "ended": 150, "duration": 90, "odb": 90, "warnings": 80, "fatal": 360}
        self._configure_tree(self.results_tree, {column: column for column in RESULT_COLUMNS}, widths)
        self._configure_status_tags(self.results_tree)
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        self._attach_scrollbars(frame, self.results_tree)
        self.results_tree.bind("<Button-3>", self._show_results_menu)
        self.results_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_table_select(self.results_tree, self.queue_tree))

    def _build_log_area(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Logs", padding=8)
        self.frames["logs"] = frame
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(1, weight=2)
        frame.columnconfigure(2, weight=1, minsize=190)
        frame.rowconfigure(0, weight=1)

        sta_frame = ttk.LabelFrame(frame, text="STA tail", padding=6)
        self.frames["sta_tail"] = sta_frame
        sta_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        sta_frame.rowconfigure(0, weight=1)
        sta_frame.columnconfigure(0, weight=1)
        self.sta_text = scrolledtext.ScrolledText(
            sta_frame,
            height=8,
            wrap="none",
            font=("Consolas", 10),
            background="#fbfdff",
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            borderwidth=1,
        )
        self.sta_text.grid(row=0, column=0, sticky="nsew")

        log_frame = ttk.LabelFrame(frame, text="Console log tail", padding=6)
        self.frames["console_tail"] = log_frame
        log_frame.grid(row=0, column=1, sticky="nsew", padx=4)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        title_bar = ttk.Frame(log_frame)
        title_bar.place(relx=1.0, x=-6, y=-28, anchor="ne")
        self.copy_console_button = ttk.Button(title_bar, command=self.copy_console_for_ai, width=7)
        self.copy_console_button.grid(row=0, column=0)
        self.console_text = scrolledtext.ScrolledText(
            log_frame,
            height=8,
            wrap="word",
            font=("Consolas", 10),
            background="#fbfdff",
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            borderwidth=1,
        )
        self.console_text.grid(row=0, column=0, sticky="nsew")

        resource_frame = ttk.LabelFrame(frame, text="Resource Usage", padding=10)
        self.frames["resource_usage"] = resource_frame
        resource_frame.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        resource_frame.columnconfigure(1, weight=1)
        self.resource_label_widgets: dict[str, ttk.Label] = {}
        for row, (key, value_var) in enumerate(
            (
                ("cpu", self.cpu_percent_var),
                ("memory", self.memory_percent_var),
                ("gpu", self.gpu_percent_var),
            )
        ):
            label = ttk.Label(resource_frame)
            label.grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
            self.resource_label_widgets[key] = label
            ttk.Label(resource_frame, textvariable=value_var, style="ResourceValue.TLabel").grid(row=row, column=1, sticky="e", pady=4)
        self.task_manager_button = ttk.Button(resource_frame, command=self.open_task_manager_performance)
        self.task_manager_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _configure_tree(self, tree: ttk.Treeview, headings: dict[str, str], widths: dict[str, int]) -> None:
        for column, label in headings.items():
            tree.heading(column, text=label)
            tree.column(column, width=widths.get(column, 120), minwidth=50, anchor="w")

    def _configure_status_tags(self, tree: ttk.Treeview) -> None:
        tree.tag_configure("queued", background="#ffffff", foreground=COLORS["text"])
        tree.tag_configure("running", background="#eff6ff", foreground=COLORS["accent_dark"])
        tree.tag_configure("success", background="#f0fdf4", foreground="#166534")
        tree.tag_configure("warning", background="#fffbeb", foreground="#92400e")
        tree.tag_configure("failed", background="#fef2f2", foreground="#991b1b")
        tree.tag_configure("skipped", background="#f8fafc", foreground=COLORS["muted"])

    def _status_tag(self, status: str) -> str:
        upper = status.upper()
        public_status = normalize_status(upper)
        if public_status in {"DATACHECK", "RUNNING"}:
            return "running"
        if upper in {"COMPLETED_OK", "DATACHECK_OK"}:
            return "success"
        if upper == "COMPLETED_WITH_WARNINGS":
            return "warning"
        if public_status == "FAILED" or upper == "UNKNOWN_INTERRUPTED":
            return "failed"
        if public_status in {"CANCELLED", "SKIPPED"}:
            return "skipped"
        return "queued"

    def _attach_scrollbars(self, parent: ttk.Frame, tree: ttk.Treeview) -> None:
        y_scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

    def refresh_all(self) -> None:
        self._sync_project_history_if_changed()
        jobs = load_queue()
        self.job_by_id = {job["queue_id"]: job for job in jobs if job.get("queue_id")}
        self._refresh_status()
        self._refresh_queue(jobs)
        self._refresh_results(jobs)
        self._refresh_logs()
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
        self.after(config.POLL_INTERVAL_SECONDS * 1000, self._poll_refresh)

    def _refresh_status(self) -> None:
        data = read_json(config.LIVE_STATUS_FILE, {})
        values = {
            "current_job": data.get("current_job", ""),
            "strategy": data.get("strategy_name", ""),
            "batch": data.get("batch_name", ""),
            "phase": data.get("phase", "IDLE"),
            "step": data.get("step", ""),
            "increment": data.get("increment", ""),
            "analysis_time": data.get("analysis_time", ""),
            "odb_size": format_bytes(data.get("odb_size_bytes")),
            "started_at": data.get("started_at", ""),
            "elapsed_time": data.get("elapsed_time", ""),
        }
        for label, value in values.items():
            self.status_vars[label].set(str(value))
        self._update_status_light(str(values["phase"]))

    def _refresh_queue(self, jobs: list[dict]) -> None:
        active = queue_display_jobs(jobs)
        rows = []
        for index, job in enumerate(active, start=1):
            rows.append((
                row_iid(job),
                (
                    index,
                    job.get("status", ""),
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
        self._render_tree(self.queue_tree, "queue", rows, active)

    def _refresh_results(self, jobs: list[dict]) -> None:
        results = result_display_jobs(jobs)
        rows = []
        for job in results:
            rows.append((
                row_iid(job, results=True),
                (
                    job.get("status", ""),
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
        self._render_tree(self.results_tree, "results", rows, results)

    def _render_tree(self, tree: ttk.Treeview, key: str, rows: list[tuple], jobs: list[dict]) -> None:
        if rows == self._rendered_rows.get(key):
            return
        current = tree.selection()
        selected_id = selected_job_id(current[0] if current else None, results=key == "results")
        y_start = tree.yview()[0]
        x_start = tree.xview()[0]
        tree.delete(*tree.get_children())
        for iid, values, tag in rows:
            tree.insert("", "end", iid=iid, values=values, tags=(tag,))
        selected_iid = restore_iid(selected_id, jobs, results=key == "results")
        if selected_iid:
            tree.selection_set(selected_iid)
            tree.focus(selected_iid)
        tree.yview_moveto(y_start)
        tree.xview_moveto(x_start)
        self._rendered_rows[key] = rows

    def _on_table_select(self, selected_tree: ttk.Treeview, other_tree: ttk.Treeview) -> None:
        if selected_tree.selection() and other_tree.selection():
            other_tree.selection_remove(*other_tree.selection())

    def _menu_label(self, key: str) -> str:
        return MENU_LABELS[key][1 if self.lang == "zh" else 0]

    def _menu_item(self, menu: tk.Menu, key: str, callback, enabled: bool = True) -> None:
        menu.add_command(label=self._menu_label(key), command=callback, state="normal" if enabled else "disabled")

    def _show_queue_menu(self, event) -> None:
        iid = self.queue_tree.identify_row(event.y)
        self.queue_tree.selection_set(iid if iid else ())
        job_id = selected_job_id(iid)
        job = self.job_by_id.get(job_id) if job_id else None
        active = queue_display_jobs(load_queue())
        index = next((index for index, item in enumerate(active) if item.get("queue_id") == job_id), -1)
        editable = bool(job and job.get("status") == "QUEUED" and self._queue_mutations_allowed(active))
        menu = tk.Menu(self, tearoff=False)
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
        self._post_menu(menu, event)

    def _show_results_menu(self, event) -> None:
        iid = self.results_tree.identify_row(event.y)
        self.results_tree.selection_set(iid if iid else ())
        job_id = selected_job_id(iid, results=True)
        job = self.job_by_id.get(job_id) if job_id else None
        mutable = bool(job and self._queue_mutations_allowed(queue_display_jobs(load_queue())))
        menu = tk.Menu(self, tearoff=False)
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
        self._post_menu(menu, event)

    def _post_menu(self, menu: tk.Menu, event) -> None:
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _queue_mutations_allowed(self, active: list[dict]) -> bool:
        return not self.runner.is_running() and not any(
            job.get("status") in {"DATACHECK_RUNNING", "FULL_RUNNING"} for job in active
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
            result = AbqJobPilotClient().preflight(request)
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
        if not job or job.get("status") not in config.RESULT_STATUSES:
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
            status = AbqJobPilotClient().status(job_id=job_id)
            details = "\n".join(filter(None, (status.status, f"ODB exists: {status.odb_exists}",
                                               f"Lock exists: {status.lock_exists}", *status.warnings, *status.errors)))
            messagebox.showinfo("Job Status", details)
            self.refresh_all()
        elif action == "locate_outputs":
            outputs = AbqJobPilotClient().locate_outputs(job_id=job_id)
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
                messagebox.showinfo("Requeue", f"Queued {result['job_name']}. Use Start Queue to run it.")
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
        for run in runs:
            tree.insert("", "end", values=(run["attempt_no"], run["status"], run["started_at"] or "",
                                             run["completed_at"] or "", run["cpus"] if run["cpus"] is not None else "",
                                             run["gpus"] if run["gpus"] is not None else "",
                                             run["working_dir"] or "", run["expected_odb_path"] or ""))

    def _refresh_logs(self) -> None:
        data = read_json(config.LIVE_STATUS_FILE, {})
        self._set_text(self.sta_text, self._sta_table_text(tail_text(data.get("sta_path", ""), 80)))
        self._set_text(self.console_text, tail_text(data.get("log_path", ""), 80))

    def _sta_table_text(self, text: str) -> str:
        if not text:
            return STA_HEADER + "\n" + "-" * len(STA_HEADER)
        return STA_HEADER + "\n" + "-" * len(STA_HEADER) + "\n" + text

    def _set_text(self, widget: scrolledtext.ScrolledText, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.see("end")
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
        self._agent_console = AgentCommandConsole(self, on_queue_changed=self.refresh_all)

    def toggle_language(self) -> None:
        self.lang = "zh" if self.lang == "en" else "en"
        self._apply_language()

    def show_help(self) -> None:
        title = "Help" if self.lang == "en" else "帮助"
        messagebox.showinfo(title, "abqjobpilot\nVersion: 0.1.0")

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
            f"This will submit {queued_count} Abaqus job(s) from the queue. Continue?",
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

    def skip_selected(self) -> None:
        job = self._selected_job()
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
        job = self._current_job(job_id) if job_id else self._selected_job(self.results_tree)
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
        job = self._selected_job()
        if not job:
            messagebox.showwarning("Open Work Folder", "Select a queue or result row first.")
            return
        work_dir = job.get("work_dir", "")
        if not work_dir or not Path(work_dir).exists():
            messagebox.showerror("Open Work Folder", f"Folder does not exist:\n{work_dir}")
            return
        open_folder(work_dir)

    def copy_console_for_ai(self) -> None:
        data = read_json(config.LIVE_STATUS_FILE, {})
        content = (
            "Please diagnose this Abaqus job log.\n\n"
            f"Phase: {data.get('phase', '')}\n"
            f"Job: {data.get('current_job', '')}\n"
            f"STA path: {data.get('sta_path', '')}\n"
            f"Log path: {data.get('log_path', '')}\n\n"
            "STA tail:\n"
            f"{self.sta_text.get('1.0', 'end-1c')}\n\n"
            "Console log tail:\n"
            f"{self.console_text.get('1.0', 'end-1c')}\n"
        )
        self.clipboard_clear()
        self.clipboard_append(content)
        title = "Copied" if self.lang == "en" else "已复制"
        msg = "Diagnostic text copied." if self.lang == "en" else "诊断文本已复制。"
        messagebox.showinfo(title, msg)

    def _update_status_light(self, phase: str) -> None:
        running = phase in {"RUNNER_ACTIVE", "DATACHECK_RUNNING", "FULL_RUNNING"}
        color = "#d93025" if running else "#2fb344"
        outline = "#9b1c16" if running else "#1f7a2e"
        self.status_light.itemconfigure(self.status_light_id, fill=color, outline=outline)

    def _texts(self) -> dict:
        if self.lang == "zh":
            return {
                "buttons": {
                    "add_inp": "添加 INP",
                    "add_folder": "添加文件夹",
                    "settings": "基础设置",
                    "agent_command": "智能命令",
                    "refresh": "刷新",
                    "start_queue": "开始队列",
                    "stop_after_current": "当前完成后停止",
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
        project_texts = ({"new": "新建", "open": "打开", "close": "关闭", "folder": "打开项目文件夹",
                          "export": "导出", "import": "导入", "legacy": "导入旧版"} if self.lang == "zh" else
                         {"new": "New", "open": "Open", "close": "Close", "folder": "Project Folder",
                          "export": "Export", "import": "Import", "legacy": "Import Legacy"})
        self._update_project_label()
        for key, button in self.project_controls.items():
            button.configure(text=project_texts[key])
        self.recent_button.configure(text="最近项目" if self.lang == "zh" else "Recent")
        for key, button in self.toolbar_buttons.items():
            button.configure(text=texts["buttons"][key])
        for key, label in self.toolbar_button_labels.items():
            label.configure(text=texts["buttons"][key])
        for key, frame in self.frames.items():
            frame.configure(text=texts["frames"].get(key, ""))
        self.copy_console_button.configure(text=texts["copy_console"])
        self.task_manager_button.configure(text=texts["task_manager"])
        for key, label in self.resource_label_widgets.items():
            label.configure(text=texts["resources"][key] + ":")
        for key, label in self.status_label_widgets.items():
            label.configure(text=texts["status"][key] + ":")
        for column, label in texts["queue_headings"].items():
            self.queue_tree.heading(column, text=label)
        for column, label in texts["result_headings"].items():
            self.results_tree.heading(column, text=label)

    def _selected_job(self, tree: ttk.Treeview | None = None) -> dict | None:
        for widget, results in ((tree, tree is self.results_tree),) if tree else (
            (self.queue_tree, False), (self.results_tree, True)
        ):
            selection = widget.selection()
            if selection:
                return self.job_by_id.get(selected_job_id(selection[0], results=results))
        return None


def main() -> None:
    app = AbqJobPilotApp()
    app.mainloop()
