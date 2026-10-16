"""Tkinter Agent Command Console."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .agent_session import AgentCommandSession
from .command_parser import COMMAND_EXAMPLES, command_help_text, extract_agent_commands


EXAMPLE_COMMANDS = "\n".join(COMMAND_EXAMPLES[name] for name in ("project use", "enqueue", "enqueue-folder"))
COMMAND_REFERENCE = "\n".join(COMMAND_EXAMPLES.values())

AI_INSTRUCTION = f"""You are generating AbqJobPilot Agent Command strings.

Output only plain text commands, one command per line. Do not use Markdown.
Allowed commands:
{COMMAND_REFERENCE}

Rules:
- Use quoted Windows paths.
- Include --cpus only if the user explicitly gave a CPU count.
- Include --gpus only if the user explicitly asked for GPU or gave a GPU count.
- If CPU/GPU are not specified, omit them so abqjobpilot uses Settings.
- Select a Project explicitly with project use before enqueue; do not guess a recent Project.
- Never generate Project deletion, solver-start, or approval commands.
- Never output shell commands, Python code, PowerShell, explanations, or bullets.
"""
AI_SKILL_PROMPT = AI_INSTRUCTION

CLI_EXAMPLES = "\n".join((
    "python -m abqjobpilot.api.cli capabilities --json",
    'python -m abqjobpilot.api.cli preflight --inp "D:\\path\\Job_xxx.inp" --cpus 14 --json',
    'python -m abqjobpilot.api.cli enqueue --inp "D:\\path\\Job_xxx.inp" --dry-run --json',
    'python -m abqjobpilot.api.cli status --job-id "QUEUE_ID" --json',
    'python -m abqjobpilot.api.cli locate-outputs --job-id "QUEUE_ID" --json',
))

AGENT_UI_STRINGS = {
    "en": {
        "title": "Agent Command Console", "safety": "Internal commands only · No shell execution · Solver start unavailable",
        "instruction": "AI Instruction", "instruction_short": "Generate AbqJobPilot commands, one per line. No shell execution.",
        "copy_instruction": "Copy Instruction", "instruction_note": "", "show_more": "Show More", "show_less": "Show Less",
        "commands": "Commands", "paste": "Paste", "run": "Run Commands", "paste_run": "Paste & Run",
        "clear_input": "Clear Input", "reference": "Command Reference", "copy_examples": "Copy Examples",
        "output": "Output", "clear_output": "Clear Output", "copy_output": "Copy Output",
        "show_details": "Show Details", "hide_details": "Hide Details", "copy_details": "Copy Details",
        "summary_count": "{count} commands executed · {success} succeeded · {failed} failed",
        "success": "SUCCESS", "failed": "FAILED", "partial": "PARTIAL",
        "enqueued": "Job enqueued (solver not started): {job_id}",
        "project_selected": "Project selected: {message}", "project_created": "Project created: {name} ({project_id})",
        "projects_found": "{count} Project(s) listed", "jobs_found": "{count} Job(s) listed",
        "job_status": "Job status: {status} · {job_id}", "outputs_found": "Output references: {job_id}",
        "folder_partial": "{success} enqueued · {failed} failed; solver not started",
        "help_ready": "Command reference shown below", "output_cleared": "Output cleared",
        "pasted_notice": "Pasted; not executed: {count} supported command(s).",
        "ignored_notice": "Other input text was ignored; only supported commands were executed.",
        "clipboard_empty": "ERROR: clipboard is empty or does not contain text.",
        "pasted": "OK: pasted {count} supported command(s) from clipboard.",
        "no_lines": "WARNING: pasted text, but no supported Agent Command lines were found.",
        "no_commands": "ERROR: no supported Agent Command lines found.",
        "queue_empty": "Queue is empty.",
        "target_project": "Console target Project:", "no_project": "No target Project selected",
        "project_id": "Current Project ID:", "project_runtime": "Project Runtime:",
        "folder_confirm": "Target: {project} ({project_id})\nEnqueue {count} INP file(s)?\n\n{inputs}",
    },
    "zh": {
        "title": "智能体命令控制台", "safety": "仅支持 AbqJobPilot 内部命令 · 不执行系统 Shell · 不提供求解器启动",
        "instruction": "AI 指令", "instruction_short": "每行生成一条 AbqJobPilot 命令；不执行系统 Shell。",
        "copy_instruction": "复制指令", "instruction_note": "以上英文内容用于复制给 AI 编程助手。",
        "show_more": "展开", "show_less": "收起",
        "commands": "命令", "paste": "粘贴", "run": "运行命令", "paste_run": "粘贴并运行",
        "clear_input": "清空输入", "reference": "命令参考", "copy_examples": "复制示例",
        "output": "输出", "clear_output": "清空输出", "copy_output": "复制输出",
        "show_details": "查看详情", "hide_details": "收起详情", "copy_details": "复制详情",
        "summary_count": "已执行 {count} 条命令 · 成功 {success} 条 · 失败 {failed} 条",
        "success": "成功", "failed": "失败", "partial": "部分成功",
        "enqueued": "作业已入队（求解器未启动）：{job_id}",
        "project_selected": "已选择 Project：{message}", "project_created": "已创建 Project：{name}（{project_id}）",
        "projects_found": "列出 {count} 个 Project", "jobs_found": "列出 {count} 个作业",
        "job_status": "作业状态：{status} · {job_id}", "outputs_found": "输出文件引用：{job_id}",
        "folder_partial": "已入队 {success} 个 · 失败 {failed} 个；求解器未启动",
        "help_ready": "命令参考如下", "output_cleared": "输出已清空",
        "pasted_notice": "已粘贴，未执行：识别到 {count} 条支持的命令。",
        "ignored_notice": "其他输入文本已忽略；仅执行了支持的内部命令。",
        "clipboard_empty": "错误：剪贴板为空或不包含文本。",
        "pasted": "已粘贴 {count} 条支持的命令。",
        "no_lines": "提示：已粘贴文本，但未找到支持的智能体命令。",
        "no_commands": "错误：未找到支持的智能体命令。",
        "queue_empty": "队列为空。",
        "target_project": "控制台目标 Project：", "no_project": "尚未选择目标 Project",
        "project_id": "当前 Project ID：", "project_runtime": "Project 运行目录：",
        "folder_confirm": "目标：{project}（{project_id}）\n将 {count} 个 INP 加入队列？\n\n{inputs}",
    },
}


_SUCCESS_STATUSES = frozenset({"OK", "PROJECT_SELECTED", "PROJECT_CREATED", "ENQUEUED", "HELP", "CLEAR"})
_JOB_STATUSES = frozenset({"QUEUED", "DATACHECK", "RUNNING", "COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED",
                           "CANCELLED", "SKIPPED", "LOCKED", "ODB_MISSING", "UNKNOWN"})


def summarize_result(result: dict, language: str = "en") -> tuple[str, str]:
    """Summarize what the service returned, never what a command might do."""
    words = AGENT_UI_STRINGS[language if language in AGENT_UI_STRINGS else "en"]
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    status = str(result.get("status") or "UNKNOWN")
    errors = data.get("errors") if isinstance(data.get("errors"), list) else []
    if status == "PARTIAL":
        items = data.get("results") if isinstance(data.get("results"), list) else []
        successes = sum(item.get("status") == "ENQUEUED" for item in items if isinstance(item, dict))
        failures = len(items) - successes
        message = words["folder_partial"].format(success=successes, failed=failures)
        first_failure = next((item for item in items if isinstance(item, dict)
                              and item.get("status") != "ENQUEUED"), None)
        reason = errors[0] if errors else (first_failure or {}).get("errors") or (first_failure or {}).get("message")
        if isinstance(reason, list):
            reason = reason[0] if reason else None
        if reason:
            message += f" · {reason}"
        return "partial", message
    output_lookup = result.get("status") is None and "log_paths" in data and bool(data.get("job_id"))
    if errors or not (status in _SUCCESS_STATUSES or status in _JOB_STATUSES and data.get("job_id")
                      or output_lookup):
        reason = str(errors[0]) if errors else str(result.get("message") or status)
        return "failed", f"{status}: {reason}"
    if status == "ENQUEUED":
        if "results" in data:
            count = sum(item.get("status") == "ENQUEUED" for item in data["results"]
                        if isinstance(item, dict))
            return "success", words["folder_partial"].format(success=count, failed=0)
        return "success", words["enqueued"].format(job_id=data.get("job_id") or "--")
    if status == "PROJECT_SELECTED":
        return "success", words["project_selected"].format(message=result.get("message") or data.get("project_id"))
    if status == "PROJECT_CREATED":
        project = data.get("project") if isinstance(data.get("project"), dict) else {}
        return "success", words["project_created"].format(name=project.get("name") or "--",
                                                          project_id=project.get("project_id") or "--")
    if status == "HELP":
        return "success", words["help_ready"]
    if status == "CLEAR":
        return "success", words["output_cleared"]
    if "projects" in data:
        return "success", words["projects_found"].format(count=len(data["projects"]))
    if "jobs" in data:
        return "success", words["jobs_found"].format(count=len(data["jobs"]))
    if status in _JOB_STATUSES:
        return "success", words["job_status"].format(status=status, job_id=data.get("job_id") or "--")
    if "expected_odb_path" in data:
        return "success", words["outputs_found"].format(job_id=data.get("job_id") or "--")
    return "success", status


def detail_result(command_text: str, result: dict, language: str = "en") -> str:
    detail = f"> {command_text}\n{json.dumps(result, ensure_ascii=False, indent=2)}"
    if result.get("status") == "HELP":
        detail += "\n\n" + command_help_text(language)
    return detail


class AgentCommandConsole(tk.Toplevel):
    def __init__(self, master, on_queue_changed=None, language: str = "en",
                 project: str | None = None, recent_file: str | None = None,
                 runner_active=None):
        super().__init__(master)
        self.geometry("1040x760")
        self.minsize(860, 620)
        self.on_queue_changed = on_queue_changed
        self.language = language if language in AGENT_UI_STRINGS else "en"
        self._reference_open = False
        self._details_open = False
        self._instruction_window = None
        self._detail_records: list[str] = []
        self.buttons: dict[str, ttk.Button] = {}
        self.session = AgentCommandSession(project=project, recent_file=recent_file,
                                           runner_active=runner_active,
                                           confirm_folder=self._confirm_folder)
        self._project_options: dict[str, str] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        self._build_widgets()
        self._refresh_projects()
        self.set_language(self.language)
        self.input_text.focus_set()

    def _build_widgets(self) -> None:
        target = ttk.Frame(self)
        target.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 3))
        target.columnconfigure(1, weight=1)
        self.target_label = ttk.Label(target)
        self.target_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(target, textvariable=self.target_var, state="readonly")
        self.target_combo.grid(row=0, column=1, sticky="ew")
        self.target_combo.bind("<<ComboboxSelected>>", self._select_project)
        self.project_id_label = ttk.Label(target, foreground="#64748b")
        self.project_id_label.grid(row=1, column=0, columnspan=2, sticky="w")
        self.project_runtime_label = ttk.Label(target, foreground="#64748b")
        self.project_runtime_label.grid(row=2, column=0, columnspan=2, sticky="w")

        self.safety_label = ttk.Label(self, foreground="#475569")
        self.safety_label.grid(row=1, column=0, sticky="w", padx=16, pady=(4, 8))

        self.instruction_frame = ttk.LabelFrame(self, padding=8)
        self.instruction_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.instruction_frame.columnconfigure(0, weight=1)
        self.instruction_summary = ttk.Label(self.instruction_frame, foreground="#475569")
        self.instruction_summary.grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.buttons["copy_instruction"] = ttk.Button(self.instruction_frame, command=self.copy_ai_prompt)
        self.buttons["copy_instruction"].grid(row=0, column=1, sticky="e", padx=(0, 7))
        self.instruction_toggle = ttk.Button(self.instruction_frame, command=self._toggle_instruction)
        self.instruction_toggle.grid(row=0, column=2, sticky="e")

        self.workspace = ttk.PanedWindow(self, orient="vertical")
        self.workspace.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.commands_frame = ttk.LabelFrame(self, padding=8)
        self.workspace.add(self.commands_frame, weight=1)
        self.commands_frame.columnconfigure(0, weight=1)
        self.commands_frame.rowconfigure(0, weight=1)
        self.input_text = scrolledtext.ScrolledText(self.commands_frame, height=9, wrap="word",
                                                   undo=True, font=("Consolas", 10))
        self.input_text.grid(row=0, column=0, sticky="nsew")
        input_toolbar = ttk.Frame(self.commands_frame)
        input_toolbar.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        for column, (key, action) in enumerate((
            ("run", self.run_commands), ("paste", self.paste_clipboard),
            ("paste_run", self.paste_and_run), ("clear_input", self.clear_input),
        )):
            self.buttons[key] = ttk.Button(input_toolbar, command=action)
            self.buttons[key].grid(row=0, column=column, padx=(0, 7))

        reference = ttk.Frame(self.commands_frame)
        reference.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        reference.columnconfigure(0, weight=1)
        self.reference_toggle = ttk.Button(reference, command=self._toggle_reference)
        self.reference_toggle.grid(row=0, column=0, sticky="w")
        self.buttons["copy_examples"] = ttk.Button(reference, command=self.copy_examples)
        self.buttons["copy_examples"].grid(row=0, column=1, sticky="e")
        self.reference_body = ttk.Label(reference, text=COMMAND_REFERENCE, justify="left",
                                        foreground="#475569", wraplength=790)
        self.reference_body.grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 0))
        self.reference_body.grid_remove()

        self.output_frame = ttk.LabelFrame(self, padding=8)
        self.workspace.add(self.output_frame, weight=1)
        self.output_frame.columnconfigure(0, weight=1)
        self.output_frame.rowconfigure(1, weight=1)
        output_toolbar = ttk.Frame(self.output_frame)
        output_toolbar.grid(row=0, column=0, sticky="e", pady=(0, 6))
        for column, (key, action) in enumerate((("show_details", self._toggle_details),
                                                ("copy_details", self.copy_details),
                                                ("clear_output", self.clear_output))):
            self.buttons[key] = ttk.Button(output_toolbar, command=action)
            self.buttons[key].grid(row=0, column=column, padx=(7, 0))
        self.output = scrolledtext.ScrolledText(self.output_frame, wrap="word", state="disabled",
                                                font=("Consolas", 10))
        self.output.grid(row=1, column=0, sticky="nsew")
        for tag, color in (("success", "#166534"), ("failed", "#b91c1c"), ("partial", "#92400e")):
            self.output.tag_configure(tag, foreground=color)
        self.details_frame = ttk.Frame(self.output_frame)
        self.details_frame.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        self.details_frame.columnconfigure(0, weight=1)
        self.details_frame.rowconfigure(0, weight=1)
        self.details_text = scrolledtext.ScrolledText(self.details_frame, height=8, wrap="word",
                                                      state="disabled", font=("Consolas", 10))
        self.details_text.grid(row=0, column=0, sticky="nsew")
        self.details_frame.grid_remove()
        self.after(80, self._set_initial_split)

    def _set_initial_split(self) -> None:
        if self.winfo_exists() and self.workspace.winfo_height() > 100:
            self.workspace.sashpos(0, self.workspace.winfo_height() // 2)

    def _toggle_instruction(self) -> None:
        if self._instruction_window is not None and self._instruction_window.winfo_exists():
            self._close_instruction()
            return
        window = tk.Toplevel(self)
        window.title(AGENT_UI_STRINGS[self.language]["instruction"])
        window.geometry("760x430")
        window.minsize(500, 280)
        window.transient(self)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        self.skill_text = scrolledtext.ScrolledText(window, wrap="word", font=("Consolas", 10))
        self.skill_text.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 4))
        self.skill_text.insert("1.0", AI_INSTRUCTION)
        self.skill_text.configure(state="disabled")
        self.instruction_note = ttk.Label(window, foreground="#64748b")
        self.instruction_note.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))
        self._instruction_window = window
        window.protocol("WM_DELETE_WINDOW", self._close_instruction)
        self.set_language(self.language)

    def _close_instruction(self) -> None:
        if self._instruction_window is not None and self._instruction_window.winfo_exists():
            self._instruction_window.destroy()
        self._instruction_window = None
        self.set_language(self.language)

    def _toggle_details(self) -> None:
        self._details_open = not self._details_open
        if self._details_open:
            self.details_frame.grid()
        else:
            self.details_frame.grid_remove()
        self.set_language(self.language)

    def set_language(self, language: str) -> None:
        self.language = language if language in AGENT_UI_STRINGS else "en"
        words = AGENT_UI_STRINGS[self.language]
        self.title(words["title"])
        self.safety_label.configure(text=words["safety"])
        self.instruction_frame.configure(text=words["instruction"])
        self.instruction_summary.configure(text=words["instruction_short"])
        self.instruction_toggle.configure(text=words["show_less"] if self._instruction_window else words["show_more"])
        if self._instruction_window is not None and self._instruction_window.winfo_exists():
            self._instruction_window.title(words["instruction"])
            self.instruction_note.configure(text=words["instruction_note"])
        self.commands_frame.configure(text=words["commands"])
        self.output_frame.configure(text=words["output"])
        self.reference_toggle.configure(text=words["reference"] + (" ▴" if self._reference_open else " ▾"))
        self.target_label.configure(text=words["target_project"])
        self._show_target()
        for key, button in self.buttons.items():
            button.configure(text=words["hide_details"] if key == "show_details" and self._details_open else words[key])

    def _refresh_projects(self) -> None:
        result = self.session.api.list_projects().to_dict()
        self._project_options = {f"{item['name']} | {item['path']}": item["path"]
                                 for item in result.get("projects", []) if item.get("exists")}
        self.target_combo.configure(values=list(self._project_options))
        self._show_target()

    def _show_target(self) -> None:
        words = AGENT_UI_STRINGS[self.language]
        target = self.session.target
        if target:
            value = next((label for label, path in self._project_options.items()
                          if path == str(target.root)), target.name)
            self.target_var.set(value)
        else:
            self.target_var.set(words["no_project"])
        self.project_id_label.configure(text=f"{words['project_id']} {target.project_id if target else '--'}")
        self.project_runtime_label.configure(text=f"{words['project_runtime']} {target.runtime_dir if target else '--'}")

    def _select_project(self, _event=None) -> None:
        path = self._project_options.get(self.target_var.get())
        if path:
            self.session.use_project(path)
        self._show_target()

    def _confirm_folder(self, preview: dict) -> bool:
        words = AGENT_UI_STRINGS[self.language]
        inputs = "\n".join(
            f"{item['job_name']} | CPU {item['cpus']} GPU {item['gpus']} | {item['inp_path']}\n"
            f"  -> {item['expected_odb_path']}"
            for item in preview["requests"][:12])
        if preview["count"] > 12:
            inputs += f"\n... +{preview['count'] - 12}"
        return messagebox.askyesno(words["title"], words["folder_confirm"].format(
            count=preview["count"], project=preview["project"],
            project_id=preview["project_id"], inputs=inputs), parent=self)

    def _toggle_reference(self) -> None:
        self._reference_open = not self._reference_open
        if self._reference_open:
            self.reference_body.grid()
        else:
            self.reference_body.grid_remove()
        self.set_language(self.language)

    def _append_output(self, text: str, tag: str | None = None) -> None:
        self.output.configure(state="normal")
        if self.output.get("1.0", "end-1c"):
            self.output.insert("end", "\n")
        self.output.insert("end", text.rstrip() + "\n", tag)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _append_details(self, text: str) -> None:
        self._detail_records.append(text)
        self.details_text.configure(state="normal")
        if self.details_text.get("1.0", "end-1c"):
            self.details_text.insert("end", "\n\n")
        self.details_text.insert("end", text)
        self.details_text.configure(state="disabled")

    def clear_input(self) -> None:
        self.input_text.delete("1.0", "end")

    def clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self._detail_records.clear()
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.configure(state="disabled")

    def copy_output(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.output.get("1.0", "end-1c"))

    def copy_details(self) -> None:
        self.clipboard_clear()
        self.clipboard_append("\n\n".join(self._detail_records))

    def copy_ai_prompt(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(AI_INSTRUCTION)

    def paste_clipboard(self) -> bool:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            self._append_output(AGENT_UI_STRINGS[self.language]["clipboard_empty"])
            return False
        if not text.strip():
            self._append_output(AGENT_UI_STRINGS[self.language]["clipboard_empty"])
            return False
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", text)
        commands = extract_agent_commands(text)
        if commands:
            self._append_output(AGENT_UI_STRINGS[self.language]["pasted_notice"].format(count=len(commands)))
        else:
            self._append_output(AGENT_UI_STRINGS[self.language]["no_lines"])
        return True

    def paste_and_run(self) -> None:
        if not self.paste_clipboard():
            return
        pasted_text = self.input_text.get("1.0", "end-1c")
        if extract_agent_commands(pasted_text):
            self.run_commands()

    def copy_examples(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(EXAMPLE_COMMANDS)
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", EXAMPLE_COMMANDS)

    def run_commands(self) -> None:
        pasted_text = self.input_text.get("1.0", "end-1c")
        commands = extract_agent_commands(pasted_text)
        if not commands:
            self._append_output(AGENT_UI_STRINGS[self.language]["no_commands"])
            return

        words = AGENT_UI_STRINGS[self.language]
        any_queue_change = False
        outcomes = []
        for command_text in commands:
            result = self._run_one_command(command_text)
            outcome, summary = summarize_result(result, self.language)
            outcomes.append((outcome, summary, command_text, result))
            any_queue_change = any_queue_change or bool(result.get("queue_changed"))
            if result.get("target_changed"):
                self._refresh_projects()
        success_count = sum(outcome == "success" for outcome, *_ in outcomes)
        self._append_output(words["summary_count"].format(
            count=len(outcomes), success=success_count, failed=len(outcomes) - success_count))
        if len([line for line in pasted_text.splitlines() if line.strip()]) > len(commands):
            self._append_output(words["ignored_notice"], "partial")
        for index, (outcome, summary, command_text, result) in enumerate(outcomes, 1):
            self._append_output(f"{index}. {words[outcome]} — {summary}", outcome)
            if result.get("status") == "HELP":
                self._append_output(command_help_text(self.language))
            self._append_details(detail_result(command_text, result, self.language))
        if any_queue_change and self.on_queue_changed:
            self.on_queue_changed()

    def _run_one_command(self, command_text: str) -> dict:
        result = self.session.execute(command_text)
        if result["status"] == "CLEAR":
            self.clear_output()
        return result
