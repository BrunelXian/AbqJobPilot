"""Tkinter Agent Command Console."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from .command_parser import (COMMAND_EXAMPLES, CommandParseError, command_help_text,
                             extract_agent_commands, parse_agent_command)
from .queue_store import add_folder_to_queue, add_inp_job_to_queue, load_queue
from .settings_store import load_settings


EXAMPLE_COMMANDS = "\n".join(COMMAND_EXAMPLES[name] for name in ("enqueue", "enqueue-folder"))
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
        "instruction": "AI Instruction", "copy_instruction": "Copy Instruction", "instruction_note": "",
        "commands": "Commands", "paste": "Paste", "run": "Run Commands", "paste_run": "Paste && Run",
        "clear_input": "Clear Input", "reference": "Command Reference", "copy_examples": "Copy Examples",
        "output": "Output", "clear_output": "Clear Output", "copy_output": "Copy Output",
        "clipboard_empty": "ERROR: clipboard is empty or does not contain text.",
        "pasted": "OK: pasted {count} supported command(s) from clipboard.",
        "no_lines": "WARNING: pasted text, but no supported Agent Command lines were found.",
        "no_commands": "ERROR: no supported Agent Command lines found.",
        "queue_empty": "Queue is empty.",
    },
    "zh": {
        "title": "智能体命令控制台", "safety": "仅支持 AbqJobPilot 内部命令 · 不执行系统 Shell · 不提供求解器启动",
        "instruction": "AI 指令", "copy_instruction": "复制指令", "instruction_note": "以上英文内容用于复制给 AI 编程助手。",
        "commands": "命令", "paste": "粘贴", "run": "运行命令", "paste_run": "粘贴并运行",
        "clear_input": "清空输入", "reference": "命令参考", "copy_examples": "复制示例",
        "output": "输出", "clear_output": "清空输出", "copy_output": "复制输出",
        "clipboard_empty": "错误：剪贴板为空或不包含文本。",
        "pasted": "已粘贴 {count} 条支持的命令。",
        "no_lines": "提示：已粘贴文本，但未找到支持的智能体命令。",
        "no_commands": "错误：未找到支持的智能体命令。",
        "queue_empty": "队列为空。",
    },
}


class AgentCommandConsole(tk.Toplevel):
    def __init__(self, master, on_queue_changed=None, language: str = "en"):
        super().__init__(master)
        self.geometry("1040x760")
        self.minsize(860, 620)
        self.on_queue_changed = on_queue_changed
        self.language = language if language in AGENT_UI_STRINGS else "en"
        self._reference_open = False
        self.buttons: dict[str, ttk.Button] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=2)
        self.rowconfigure(4, weight=3)
        self._build_widgets()
        self.set_language(self.language)
        self.input_text.focus_set()

    def _build_widgets(self) -> None:
        self.safety_label = ttk.Label(self, foreground="#475569")
        self.safety_label.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 8))

        self.instruction_frame = ttk.LabelFrame(self, padding=8)
        self.instruction_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.instruction_frame.columnconfigure(0, weight=1)
        self.skill_text = scrolledtext.ScrolledText(self.instruction_frame, height=7, wrap="word", relief="flat")
        self.skill_text.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.skill_text.insert("1.0", AI_INSTRUCTION)
        self.skill_text.configure(state="disabled")
        self.buttons["copy_instruction"] = ttk.Button(self.instruction_frame, command=self.copy_ai_prompt)
        self.buttons["copy_instruction"].grid(row=0, column=1, sticky="n")
        self.instruction_note = ttk.Label(self.instruction_frame, foreground="#64748b")
        self.instruction_note.grid(row=1, column=0, sticky="w", pady=(3, 0))

        self.commands_frame = ttk.LabelFrame(self, padding=8)
        self.commands_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.commands_frame.columnconfigure(0, weight=1)
        self.commands_frame.rowconfigure(0, weight=1)
        self.input_text = scrolledtext.ScrolledText(self.commands_frame, height=8, wrap="word", font=("Consolas", 10))
        self.input_text.grid(row=0, column=0, sticky="nsew")
        input_toolbar = ttk.Frame(self.commands_frame)
        input_toolbar.grid(row=1, column=0, sticky="w", pady=(7, 0))
        for column, (key, action) in enumerate((
            ("paste", self.paste_clipboard), ("run", self.run_commands),
            ("paste_run", self.paste_and_run), ("clear_input", self.clear_input),
        )):
            self.buttons[key] = ttk.Button(input_toolbar, command=action)
            self.buttons[key].grid(row=0, column=column, padx=(0, 7))

        reference = ttk.Frame(self)
        reference.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
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
        self.output_frame.grid(row=4, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.output_frame.columnconfigure(0, weight=1)
        self.output_frame.rowconfigure(1, weight=1)
        output_toolbar = ttk.Frame(self.output_frame)
        output_toolbar.grid(row=0, column=0, sticky="e", pady=(0, 6))
        for column, (key, action) in enumerate((("clear_output", self.clear_output),
                                                ("copy_output", self.copy_output))):
            self.buttons[key] = ttk.Button(output_toolbar, command=action)
            self.buttons[key].grid(row=0, column=column, padx=(7, 0))
        self.output = scrolledtext.ScrolledText(self.output_frame, wrap="word", state="disabled",
                                                font=("Consolas", 10))
        self.output.grid(row=1, column=0, sticky="nsew")

    def set_language(self, language: str) -> None:
        self.language = language if language in AGENT_UI_STRINGS else "en"
        words = AGENT_UI_STRINGS[self.language]
        self.title(words["title"])
        self.safety_label.configure(text=words["safety"])
        self.instruction_frame.configure(text=words["instruction"])
        self.instruction_note.configure(text=words["instruction_note"])
        self.commands_frame.configure(text=words["commands"])
        self.output_frame.configure(text=words["output"])
        self.reference_toggle.configure(text=words["reference"] + (" ▴" if self._reference_open else " ▾"))
        for key, button in self.buttons.items():
            button.configure(text=words[key])

    def _toggle_reference(self) -> None:
        self._reference_open = not self._reference_open
        if self._reference_open:
            self.reference_body.grid()
        else:
            self.reference_body.grid_remove()
        self.set_language(self.language)

    def _append_output(self, text: str) -> None:
        self.output.configure(state="normal")
        if self.output.get("1.0", "end-1c"):
            self.output.insert("end", "\n")
        self.output.insert("end", text.rstrip() + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def clear_input(self) -> None:
        self.input_text.delete("1.0", "end")

    def clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def copy_output(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.output.get("1.0", "end-1c"))

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
            self._append_output(AGENT_UI_STRINGS[self.language]["pasted"].format(count=len(commands)))
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

        any_queue_change = False
        for command_text in commands:
            result = self._run_one_command(command_text)
            any_queue_change = any_queue_change or bool(result.get("queue_changed"))
        if any_queue_change and self.on_queue_changed:
            self.on_queue_changed()

    def _run_one_command(self, command_text: str) -> dict:
        try:
            parsed = parse_agent_command(command_text)
        except CommandParseError as exc:
            self._append_output(f"> {command_text}\n\nERROR: {exc}")
            return {"queue_changed": False}

        command = parsed["command"]
        if command == "clear":
            self.clear_output()
            return {"queue_changed": False}
        if command == "help":
            self._append_output(f"> {command_text}\n\n{command_help_text(self.language)}")
            return {"queue_changed": False}
        if command == "list":
            self._append_output(f"> {command_text}\n\n{self._format_queue_list()}")
            return {"queue_changed": False}
        if command == "enqueue":
            result = self._enqueue(parsed)
            self._append_output(f"> {command_text}\n\n{self._format_enqueue_result(result)}")
            return {"queue_changed": bool(result.get("ok"))}
        if command == "enqueue-folder":
            result = self._enqueue_folder(parsed)
            self._append_output(f"> {command_text}\n\n{self._format_folder_result(result)}")
            return {"queue_changed": bool(result.get("added"))}
        self._append_output(f"> {command_text}\n\nERROR: unsupported command: {command}")
        return {"queue_changed": False}

    def _resource_defaults(self, parsed: dict) -> tuple[int, int]:
        settings = load_settings()
        cpus = parsed["cpus"] if parsed.get("cpus") is not None else settings["default_cpus"]
        gpus = parsed["gpus"] if parsed.get("gpus") is not None else (
            settings["default_gpus"] if settings["use_gpu"] else 0
        )
        return cpus, gpus

    def _enqueue(self, parsed: dict) -> dict:
        cpus, gpus = self._resource_defaults(parsed)
        return add_inp_job_to_queue(
            parsed["inp"],
            cpus=cpus,
            gpus=gpus,
            batch_name=parsed.get("batch_name"),
            strategy_name=parsed.get("strategy_name"),
            job_name=parsed.get("job_name"),
            run_datacheck=parsed.get("datacheck", True),
            run_full=parsed.get("full_run", True),
            notes=parsed.get("notes", ""),
        )

    def _enqueue_folder(self, parsed: dict) -> dict:
        cpus, gpus = self._resource_defaults(parsed)
        return add_folder_to_queue(
            parsed["folder"],
            pattern=parsed.get("pattern", "*.inp"),
            cpus=cpus,
            gpus=gpus,
            batch_name=parsed.get("batch_name"),
            strategy_name=parsed.get("strategy_name"),
        )

    def _format_enqueue_result(self, result: dict) -> str:
        if not result.get("ok"):
            return result.get("message", "ERROR: failed to add job")
        return (
            "OK: added job to queue\n"
            f"Queue ID: {result['queue_id']}\n"
            f"Job: {result['job_name']}\n"
            f"Strategy: {result['strategy_name']}\n"
            f"Batch: {result['batch_name']}\n"
            f"CPUs: {result['cpus']}\n"
            f"GPUs: {result.get('gpus', 0)}\n"
            f"Work dir: {result['work_dir']}\n"
            f"Queue position: {result['queue_position']}"
        )

    def _format_folder_result(self, result: dict) -> str:
        lines: list[str] = []
        if result.get("added"):
            lines.append(f"OK: added {len(result['added'])} job(s) to queue")
            for item in result["added"]:
                lines.append(
                    f"- {item['job_name']} | {item['strategy_name']} | "
                    f"CPUs {item['cpus']} | GPUs {item.get('gpus', 0)} | position {item['queue_position']}"
                )
        if result.get("errors"):
            if lines:
                lines.append("")
            lines.append("Errors:")
            lines.extend(result["errors"])
        if not lines:
            lines.append(result.get("message", "ERROR: no jobs were added"))
        return "\n".join(lines)

    def _format_queue_list(self) -> str:
        jobs = load_queue()
        if not jobs:
            return AGENT_UI_STRINGS[self.language]["queue_empty"]
        header = "index | status | batch_name | strategy_name | job_name | inp_path | cpus | gpus | created_at"
        lines = [header, "-" * len(header)]
        for index, job in enumerate(jobs, start=1):
            lines.append(
                f"{index} | {job.get('status', '')} | {job.get('batch_name', '')} | "
                f"{job.get('strategy_name', '')} | {job.get('job_name', '')} | "
                f"{job.get('inp_path', '')} | {job.get('cpus', '')} | "
                f"{job.get('gpus', 0)} | {job.get('created_at', '')}"
            )
        return "\n".join(lines)
