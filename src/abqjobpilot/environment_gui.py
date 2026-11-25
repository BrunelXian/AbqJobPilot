"""Native Tk controls for static Abaqus configuration."""
import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .abaqus_environments import EnvironmentManager
from .execution.models import ExecutionError


class EnvironmentDialog(tk.Toplevel):
    def __init__(self, workspace):
        super().__init__(workspace.app)
        self.workspace = workspace
        self.t = workspace.t
        self.title(self.t("abaqusEnvironments"))
        self.geometry("1100x550")
        self.minsize(800, 420)
        self.transient(workspace.app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        ttk.Label(self, text=self.t("environmentStaticNotice"), wraplength=1000).grid(
            row=0, column=0, sticky="w", padx=12, pady=10)
        table = ttk.Frame(self)
        table.grid(row=1, column=0, sticky="nsew", padx=12)
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = ("version", "entry", "default", "state", "checked", "error")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        for name, key, width in zip(columns,
                ("environmentVersion", "environmentEntry", "environmentDefault", "environmentState",
                 "environmentChecked", "environmentError"), (75, 390, 75, 240, 155, 180)):
            self.tree.heading(name, text=self.t(key))
            self.tree.column(name, width=width, minwidth=65, stretch=name in ("entry", "error"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.selected_path = tk.StringVar()
        ttk.Label(self, textvariable=self.selected_path, wraplength=1000).grid(
            row=2, column=0, sticky="w", padx=12, pady=(6, 0))
        self.tree.bind("<<TreeviewSelect>>", self.show_selected_path)
        bar = ttk.Frame(self)
        bar.grid(row=3, column=0, sticky="w", padx=12, pady=10)
        self.buttons = []
        for key, action in (("environmentDetect", workspace.detect_environments),
                            ("environmentAdd", self.add), ("environmentEdit", self.edit),
                            ("environmentRemove", self.remove), ("environmentSetDefault", self.set_default),
                            ("environmentValidate", self.validate)):
            button = ttk.Button(bar, text=self.t(key), command=action)
            button.pack(side="left", padx=(0, 6))
            self.buttons.append(button)
        project = ttk.Frame(self)
        project.grid(row=4, column=0, sticky="w", padx=12, pady=5)
        self.project_label = ttk.Label(project)
        self.project_label.pack(side="left", padx=(0, 8))
        self.project_buttons = []
        for key, action in (("environmentUseProject", self.use_project), ("environmentUseGlobal", self.use_global)):
            button = ttk.Button(project, text=self.t(key), command=action)
            button.pack(side="left", padx=4)
            self.project_buttons.append(button)
        self.message = tk.StringVar()
        ttk.Label(self, textvariable=self.message, wraplength=1000).grid(
            row=5, column=0, sticky="w", padx=12, pady=10)
        self.binding_label = ttk.Label(self, wraplength=1000)
        self.binding_label.grid(row=6, column=0, sticky="w", padx=12, pady=(0, 10))
        self.version = None
        self.timer = None
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    @property
    def manager(self):
        return self.workspace.environment_manager

    def selected(self):
        selection = self.tree.selection()
        if not selection:
            raise ValueError(self.t("environmentSelect"))
        return selection[0]

    def show_selected_path(self, event=None):
        selection = self.tree.selection()
        if selection and self.manager:
            item = self.manager.get(selection[0])
            detail = self.t("environmentEntry") + ": " + item["entry"]
            if item["error"]:
                detail += "\n" + self.t("environmentError") + ": " + item["error"]
            self.selected_path.set(detail)
        else:
            self.selected_path.set("")

    def perform(self, action):
        if self.workspace.environment_busy or self.manager is None:
            return
        try:
            action()
        except (ExecutionError, OSError, ValueError, KeyError, TypeError) as exc:
            messagebox.showerror(self.t("abaqusEnvironments"), str(exc), parent=self)
        self.version = None
        self.refresh(schedule=False)

    def add(self):
        path = filedialog.askopenfilename(parent=self, title=self.t("environmentAdd"),
                                         filetypes=[("Abaqus BAT", "*.bat")])
        if path:
            self.perform(lambda: self.manager.add(path))

    def edit(self):
        try:
            identifier = self.selected()
        except ValueError as exc:
            messagebox.showinfo(self.title(), str(exc), parent=self)
            return
        path = filedialog.askopenfilename(parent=self, title=self.t("environmentEdit"),
                                         initialdir=str(Path(self.manager.get(identifier)["entry"]).parent),
                                         filetypes=[("Abaqus BAT", "*.bat")])
        if path:
            self.perform(lambda: self.manager.add(path, replace_id=identifier))

    def remove(self):
        def action():
            identifier = self.selected()
            if messagebox.askyesno(self.title(), self.t("environmentRemoveConfirm"), parent=self):
                self.manager.remove(identifier)
        self.perform(action)

    def set_default(self):
        self.perform(lambda: self.manager.set_default(self.selected()))

    def validate(self):
        self.perform(lambda: self.manager.validate(self.selected()))

    def use_project(self):
        self.perform(lambda: self.manager.select_for_project(self.workspace.project, self.selected()))

    def use_global(self):
        self.perform(lambda: self.manager.select_for_project(self.workspace.project, None))

    def refresh(self, *, schedule=True):
        workspace = self.workspace
        signature = (workspace.environment_busy, str(self.manager.data) if self.manager else workspace.environment_error,
                     self.manager.unsaved if self.manager else False,
                     workspace.project, workspace.lifecycle_busy)
        if signature != self.version:
            self.version = signature
            busy = workspace.environment_busy
            for button in self.buttons:
                button.configure(state="disabled" if busy or self.manager is None else "normal")
            for button in self.project_buttons:
                button.configure(state="normal" if self.manager and workspace.project and not busy
                                 and not workspace.lifecycle_busy else "disabled")
            if not busy and self.manager:
                selection = self.tree.selection()
                self.tree.delete(*self.tree.get_children())
                for item in self.manager.data["environments"]:
                    configured = "CONFIGURED" if item["configured"] else "FOUND"
                    checked = item.get("checked_at")
                    stamp = datetime.datetime.fromtimestamp(checked).strftime("%Y-%m-%d %H:%M:%S") if checked else "—"
                    self.tree.insert("", "end", iid=item["id"], values=(
                        item["version"], item["entry"],
                        "✓" if self.manager.data["default_id"] == item["id"] else "",
                        configured + " / " + item["validation"], stamp, item["error"]))
                if selection and self.tree.exists(selection[0]):
                    self.tree.selection_set(selection[0])
                elif self.tree.get_children():
                    self.tree.selection_set(self.tree.get_children()[0])
                self.show_selected_path()
            choice = self.t("environmentGlobalChoice")
            if workspace.project and self.manager and not busy:
                try:
                    choice = self.manager.project_choice(workspace.project) or choice
                except (ExecutionError, OSError, ValueError):
                    choice = self.t("environmentProjectUnavailable")
            self.project_label.configure(text=self.t("environmentProjectChoice", choice=choice))
            bound = "—"
            if workspace.project:
                try:
                    from .service_lifecycle import ServiceLifecycleManager
                    from .sanity_admission import recorded_plan
                    plan = recorded_plan(ServiceLifecycleManager(workspace.project))
                    bound = plan["runtime_binding"]["entry"]
                except (ExecutionError, OSError, ValueError, KeyError):
                    pass
            self.binding_label.configure(text=self.t("environmentSavedNotice", entry=bound))
            self.message.set(self.t("environmentScanning") if busy else self.t("environmentUnsaved") if self.manager
                             and self.manager.unsaved else workspace.environment_error or self.t("environmentBindingNotice"))
        if schedule:
            self.timer = self.after(200, self.refresh)

    def close(self):
        if self.timer:
            self.after_cancel(self.timer)
        self.destroy()


def initialize(workspace):
    workspace.environment_busy = False
    workspace.environment_error = ""
    workspace.environment_thread = None
    workspace.environment_dialog = None
    try:
        workspace.environment_manager = EnvironmentManager()
    except (ExecutionError, OSError, ValueError, KeyError, TypeError) as exc:
        workspace.environment_manager = None
        workspace.environment_error = str(exc)
    if workspace.environment_manager and not workspace.environment_manager.data.get("detected"):
        workspace.detect_environments()
