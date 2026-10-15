"""Local human review for metadata-only runtime recovery."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .recovery_workflow import apply_approved_recovery, approve_local_plan, build_recovery_plan


class RecoveryDialog(tk.Toplevel):
    def __init__(self, parent, runtime_dir: str, project_db: str | None = None, *, language: str = "en"):
        super().__init__(parent)
        self.runtime_dir = runtime_dir
        self.project_db = project_db
        self.language = language
        self.plan = None
        self.title("运行时恢复评估" if language == "zh" else "Runtime Recovery Assessment")
        self.geometry("760x540")
        self.transient(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.report = scrolledtext.ScrolledText(self, wrap="word", state="disabled")
        self.report.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        buttons = ttk.Frame(self)
        buttons.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        ttk.Button(buttons, text="刷新评估" if language == "zh" else "Refresh Assessment",
                   command=self.refresh).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="复制报告" if language == "zh" else "Copy Report",
                   command=self.copy_report).pack(side="left", padx=(0, 8))
        self.apply_button = ttk.Button(buttons, text="应用已批准的元数据修正" if language == "zh"
                                       else "Apply Approved Metadata Corrections", command=self.apply)
        self.apply_button.pack(side="left")
        ttk.Button(buttons, text="取消" if language == "zh" else "Cancel",
                   command=self.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        self.plan = build_recovery_plan(self.runtime_dir, project_db=self.project_db)
        self.report.configure(state="normal")
        self.report.delete("1.0", "end")
        self.report.insert("1.0", self.plan.to_json())
        self.report.configure(state="disabled")
        self.apply_button.configure(state="normal" if self.plan.can_apply else "disabled")

    def copy_report(self) -> None:
        if self.plan is not None:
            self.clipboard_clear()
            self.clipboard_append(self.plan.to_json())

    def apply(self) -> None:
        plan = self.plan
        if plan is None or not plan.can_apply:
            return
        token = approve_local_plan(plan, self, language=self.language)
        if token is None:
            return
        result = apply_approved_recovery(plan, token)
        if result["status"] == "APPLIED":
            messagebox.showinfo(self.title(), "元数据修正已应用。" if self.language == "zh"
                                else "Metadata correction applied.", parent=self)
        else:
            messagebox.showwarning(self.title(), result.get("error", result["status"]), parent=self)
        self.refresh()
