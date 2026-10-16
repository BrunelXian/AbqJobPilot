"""Agent Console presentation tests; no solver or real queue runner."""

from unittest.mock import patch
import time
import tkinter as tk

import pytest

from abqjobpilot.command_console import (AGENT_UI_STRINGS, AI_INSTRUCTION,
                                         AgentCommandConsole, detail_result,
                                         summarize_result)


@pytest.fixture
def console(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display unavailable")
    root.withdraw()
    window = AgentCommandConsole(root, recent_file=str(tmp_path / "recent.json"))
    root.update_idletasks()
    yield window
    window.destroy()
    root.destroy()


def test_summary_uses_service_result_not_command_guess():
    queued = {"status": "ENQUEUED", "message": "queued", "data": {"job_id": "q_123"}}
    refused = {"status": "PROJECT_REQUIRED", "message": "No target Project selected", "data": {}}
    partial = {"status": "PARTIAL", "message": "some failed", "data": {
        "results": [{"status": "ENQUEUED", "job_id": "q_1"}, {"status": "INVALID_REQUEST"}],
        "errors": ["second input invalid"]}}
    assert summarize_result(queued)[0] == "success"
    assert "solver not started" in summarize_result(queued)[1]
    assert summarize_result(refused) == ("failed", "PROJECT_REQUIRED: No target Project selected")
    assert summarize_result(partial)[0] == "partial"
    assert "1 enqueued" in summarize_result(partial)[1]
    assert "second input invalid" in summarize_result(partial)[1]
    assert "q_123" in detail_result("enqueue --inp test.inp", queued)
    status = {"status": "COMPLETED_WITH_WARNINGS", "message": "", "data": {
        "job_id": "q_2", "expected_odb_path": "C:\\test\\a.odb"}}
    assert "Job status: COMPLETED_WITH_WARNINGS" in summarize_result(status)[1]
    output = {"status": "OK", "message": "", "data": {
        "job_id": "q_2", "expected_odb_path": "C:\\test\\a.odb"}}
    assert "Output references" in summarize_result(output)[1]


def test_compact_instruction_and_full_copy(console):
    assert not hasattr(console, "skill_text")
    assert "No shell execution" in console.instruction_summary.cget("text")
    console.copy_ai_prompt()
    assert console.clipboard_get() == AI_INSTRUCTION
    console.instruction_toggle.invoke()
    console.update_idletasks()
    assert console._instruction_window.winfo_exists()
    assert console.skill_text.get("1.0", "end-1c") == AI_INSTRUCTION
    console.instruction_toggle.invoke()
    assert console._instruction_window is None
    assert console.commands_frame.winfo_exists()


def test_command_layout_and_button_order(console):
    assert int(console.input_text.cget("height")) >= 8
    assert console.input_text.cget("wrap") == "word"
    assert str(console.workspace.cget("orient")) == "vertical"
    assert [console.buttons[key].grid_info()["column"] for key in
            ("run", "paste", "paste_run", "clear_input")] == [0, 1, 2, 3]
    assert not console.reference_body.winfo_ismapped()
    console.reference_toggle.invoke()
    console.update_idletasks()
    assert console.reference_body.winfo_ismapped()
    time.sleep(0.1)
    console.update()
    height = console.workspace.winfo_height()
    assert abs(console.workspace.sashpos(0) - height / 2) < 25
    console.workspace.sashpos(0, int(height * 0.6))
    console.geometry("1000x700")
    console.update()
    assert console.workspace.sashpos(0) > console.workspace.winfo_height() / 2


def test_multiline_paste_run_and_details(console):
    text = 'project use --project "missing"\nenqueue --inp "C:\\test\\a.inp"'
    console.clipboard_clear()
    console.clipboard_append(text)
    executed = []

    def execute(command):
        executed.append(command)
        if command.startswith("project"):
            return {"status": "PROJECT_NOT_FOUND", "message": "missing", "data": {},
                    "queue_changed": False, "target_changed": False}
        return {"status": "PROJECT_REQUIRED", "message": "No target Project selected", "data": {},
                "queue_changed": False, "target_changed": False}

    with patch.object(console.session, "execute", side_effect=execute):
        console.paste_and_run()
    assert executed == text.splitlines()
    summary = console.output.get("1.0", "end-1c")
    assert "2 commands executed" in summary and "2 failed" in summary
    assert "PROJECT_NOT_FOUND" in summary and "PROJECT_REQUIRED" in summary
    assert not console.details_frame.winfo_ismapped()
    console.copy_details()
    assert '"status": "PROJECT_NOT_FOUND"' in console.clipboard_get()
    console.buttons["show_details"].invoke()
    console.update_idletasks()
    assert console.details_frame.winfo_ismapped()
    console.clear_input()
    assert console.input_text.get("1.0", "end-1c") == ""
    assert "2 commands executed" in console.output.get("1.0", "end-1c")
    console.clear_output()
    assert console.output.get("1.0", "end-1c") == ""
    assert console._detail_records == []


def test_no_project_and_shell_rejection(console):
    console.input_text.insert("1.0", 'enqueue --inp "C:\\test\\a.inp"')
    console.run_commands()
    assert "PROJECT_REQUIRED" in console.output.get("1.0", "end-1c")
    console.clear_input()
    console.input_text.insert("1.0", "powershell Start-Process abq2024")
    with patch.object(console.session, "execute") as execute:
        console.run_commands()
    execute.assert_not_called()
    assert "no supported Agent Command" in console.output.get("1.0", "end-1c")


def test_chinese_labels_and_details_toggle(console):
    console.set_language("zh")
    assert console.buttons["run"].cget("text") == AGENT_UI_STRINGS["zh"]["run"]
    assert console.instruction_toggle.cget("text") == AGENT_UI_STRINGS["zh"]["show_more"]
    console.buttons["show_details"].invoke()
    assert console.buttons["show_details"].cget("text") == AGENT_UI_STRINGS["zh"]["hide_details"]
    console.buttons["show_details"].invoke()
    assert console.buttons["show_details"].cget("text") == AGENT_UI_STRINGS["zh"]["show_details"]
