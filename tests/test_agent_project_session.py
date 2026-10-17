"""Project-scoped Agent Command tests using only temporary state."""

from __future__ import annotations

import asyncio
import gc
import os
import sys
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

import pytest

from abqjobpilot.agent_session import AgentCommandSession
from abqjobpilot.command_console import AGENT_UI_STRINGS, AI_INSTRUCTION, AgentCommandConsole
from abqjobpilot.command_parser import COMMAND_EXAMPLES, parse_agent_command
from abqjobpilot.project.manager import ProjectManager
from abqjobpilot.queue_store import read_queue, save_queue
from abqjobpilot.utils import write_json


@pytest.fixture
def workspace(tmp_path):
    recent = tmp_path / "recent.json"
    manager = ProjectManager(recent_file=recent)
    a = manager.create_project(tmp_path / "project_A", "Project A")
    b = manager.create_project(tmp_path / "project_B", "Project B")
    engineering = tmp_path / "engineering"
    engineering.mkdir()
    for name in ("A01.inp", "A02.inp"):
        (engineering / name).write_text("*Heading\n", encoding="utf-8")
    return tmp_path, recent, a, b, engineering


def session(workspace, **kwargs):
    return AgentCommandSession(recent_file=str(workspace[1]), **kwargs)


def test_parser_reference_and_legacy_commands():
    for name, example in COMMAND_EXAMPLES.items():
        parsed = parse_agent_command(example)
        assert parsed["command"] == name.split()[0]
        if name.startswith("project "):
            assert parsed["project_action"] == name.split()[1]
        assert example in AI_INSTRUCTION
    assert parse_agent_command('enqueue --inp "D:\\Study\\A.inp"')["cpus"] is None
    assert parse_agent_command('enqueue-folder --folder "D:\\Study"')["gpus"] is None
    for forbidden in ("solver-start", "project delete", "powershell"):
        assert forbidden not in COMMAND_EXAMPLES


def test_project_list_create_use_show_and_ambiguity(workspace):
    root, recent, a, b, _ = workspace
    agent = session(workspace)
    assert agent.target is None
    listing = agent.execute("project list")
    assert listing["status"] == "OK"
    assert {item["name"] for item in listing["data"]["projects"]} == {"Project A", "Project B"}
    with patch("abqjobpilot.api.project_surface.ensure_default_projects_root", return_value=root / "projects"):
        created = agent.execute('project create --name "Project C"')
    assert created["status"] == "PROJECT_CREATED"
    assert (root / "projects" / "Project C" / "project.json").is_file()
    assert agent.target is None
    assert agent.execute('project use --project "Project A"')["status"] == "PROJECT_SELECTED"
    shown = agent.execute("project show")
    assert shown["data"]["project"]["project_id"] == a.project_id
    duplicate = ProjectManager(recent_file=recent).create_project(root / "duplicate", "Project A")
    assert duplicate.project_id != a.project_id
    assert agent.execute('project use --project "Project A"')["status"] == "AMBIGUOUS_PROJECT"
    assert agent.target is None
    assert agent.execute('project use --project "Unknown"')["status"] == "PROJECT_NOT_FOUND"
    assert agent.execute(f'project use --project "{a.root}"')["status"] == "PROJECT_SELECTED"


def test_no_target_failed_use_and_explicit_override_are_safe(workspace):
    _, _, a, b, engineering = workspace
    agent = session(workspace)
    command = f'enqueue --inp "{engineering / "A01.inp"}"'
    assert agent.execute(command)["status"] == "PROJECT_REQUIRED"
    assert read_queue(a.runtime_dir) == read_queue(b.runtime_dir) == []
    results = agent.execute_lines(f'project use --project "Unknown"\n{command}\nlist')
    assert [item["status"] for item in results] == ["PROJECT_NOT_FOUND", "PROJECT_REQUIRED", "PROJECT_REQUIRED"]
    agent.use_project(str(a.root))
    result = agent.execute(f'enqueue --project "{b.root}" --inp "{engineering / "A01.inp"}"')
    assert result["status"] == "ENQUEUED"
    assert agent.target.project_id == a.project_id
    assert read_queue(a.runtime_dir) == []
    assert len(read_queue(b.runtime_dir)) == 1
    agent.use_project(str(a.root))
    failed_override = agent.execute('enqueue --project "Unknown" --inp "missing.inp"')
    assert failed_override["status"] == "PROJECT_NOT_FOUND"
    assert agent.target is None
    assert agent.execute(command)["status"] == "PROJECT_REQUIRED"
    assert agent.execute('project use --project')["status"] == "INVALID_COMMAND"
    assert agent.target is None


def test_queue_resources_status_outputs_and_project_isolation(workspace):
    _, _, a, b, engineering = workspace
    write_json(a.runtime_dir / "settings.json", {"default_cpus": 8, "default_gpus": 1,
                "use_gpu": True, "run_datacheck": False, "run_full": True})
    agent = session(workspace, project=str(a.root))
    source = engineering / "A01.inp"
    result = agent.execute(f'enqueue --inp "{source}" --notes "test note"')
    assert result["status"] == "ENQUEUED"
    assert result["queue_changed"] is True
    row = read_queue(a.runtime_dir)[0]
    assert (row["cpus"], row["gpus"], row["run_datacheck"], row["run_full"]) == (8, 1, False, True)
    assert row["notes"] == "test note"
    assert row["inp_path"] == str(source)
    assert row["work_dir"] == str(engineering)
    assert read_queue(b.runtime_dir) == []
    assert list(a.root.rglob("*.inp")) == []
    before = (a.runtime_dir / "queue.json").read_bytes()
    assert agent.execute("list")["status"] == "OK"
    assert agent.execute(f'status --job-id "{row["queue_id"]}"')["status"] == "QUEUED"
    output = agent.execute(f'outputs --job-id "{row["queue_id"]}"')
    assert output["data"]["expected_odb_path"] == str(engineering / "A01.odb")
    assert before == (a.runtime_dir / "queue.json").read_bytes()


def test_successful_multiline_sequence_and_invalid_inputs(workspace):
    _, _, a, _, engineering = workspace
    agent = session(workspace)
    commands = (f'project use --project "{a.root}"\n'
                f'enqueue --inp "{engineering / "A01.inp"}"\n'
                f'enqueue --inp "{engineering / "A02.inp"}"\nlist')
    results = agent.execute_lines(commands)
    assert [item["status"] for item in results] == ["PROJECT_SELECTED", "ENQUEUED", "ENQUEUED", "OK"]
    assert [item["job_name"] for item in results[-1]["data"]["jobs"]] == ["A01", "A02"]
    before = (a.runtime_dir / "queue.json").read_bytes()
    for command in (f'enqueue --inp "{engineering / "absent.inp"}"',
                    f'enqueue --inp "{engineering / "A01.inp"}" --cpus 0',
                    f'enqueue --inp "{engineering / "A01.inp"}" --gpus -1'):
        assert agent.execute(command)["status"] != "ENQUEUED"
    assert before == (a.runtime_dir / "queue.json").read_bytes()


def test_active_runner_and_uncertain_runtime_reject_enqueue(workspace):
    _, _, a, _, engineering = workspace
    flag = {"running": True}
    agent = session(workspace, project=str(a.root), runner_active=lambda: flag["running"])
    command = f'enqueue --inp "{engineering / "A01.inp"}"'
    assert agent.execute(command)["status"] == "RUNNER_ACTIVE"
    flag["running"] = False
    write_json(a.runtime_dir / "live_status.json", {"phase": "RUNNER_ACTIVE"})
    assert agent.execute(command)["status"] == "RUNNER_STATE_UNCONFIRMED"
    write_json(a.runtime_dir / "live_status.json", {"phase": "IDLE"})
    rows = read_queue(a.runtime_dir)
    rows.append({"queue_id": "q_old", "status": "FULL_RUNNING", "inp_path": str(engineering / "A02.inp")})
    save_queue(rows, runtime_dir=a.runtime_dir)
    assert agent.execute(command)["status"] == "RUNNER_STATE_UNCONFIRMED"
    assert len(read_queue(a.runtime_dir)) == 1


def test_folder_preview_confirmation_and_partial_result(workspace):
    _, _, a, b, engineering = workspace
    previews = []
    agent = session(workspace, project=str(a.root), confirm_folder=lambda info: previews.append(info) or True)
    command = f'enqueue-folder --folder "{engineering}" --pattern "*.inp"'
    result = agent.execute(command)
    assert result["status"] == "ENQUEUED"
    assert result["queue_changed"]
    assert previews[0]["project_id"] == a.project_id
    assert previews[0]["count"] == 2
    assert len(previews[0]["previews"]) == 2
    assert previews[0]["requests"][0]["cpus"] == 14
    assert previews[0]["requests"][0]["expected_odb_path"].endswith("A01.odb")
    assert len(read_queue(a.runtime_dir)) == 2
    assert read_queue(b.runtime_dir) == []
    unapproved = session(workspace, project=str(b.root))
    assert unapproved.execute(command)["status"] == "CONFIRMATION_REQUIRED"
    assert read_queue(b.runtime_dir) == []
    (engineering / "A03.inp").write_text("*Heading\n", encoding="utf-8")
    partial = agent.execute(command)
    assert partial["status"] == "PARTIAL"
    assert partial["queue_changed"] is True
    assert len(read_queue(a.runtime_dir)) == 3


def test_console_labels_in_both_languages_with_isolated_project(workspace):
    _, recent, a, _, _ = workspace
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display unavailable")
    root.withdraw()
    console = None
    try:
        console = AgentCommandConsole(root, language="en", project=str(a.root), recent_file=str(recent))
        assert console.session.target.project_id == a.project_id
        assert console.target_label.cget("text") == AGENT_UI_STRINGS["en"]["target_project"]
        console.set_language("zh")
        assert console.target_label.cget("text") == AGENT_UI_STRINGS["zh"]["target_project"]
        assert "Project A" in console.target_var.get()
    finally:
        if console is not None:
            console.destroy()
            del console
        gc.collect()
        root.destroy()
        gc.collect()


def test_console_enqueue_visible_through_read_only_mcp(workspace):
    pytest.importorskip("mcp")
    from mcp import Client, StdioServerParameters

    root, recent, a, _, engineering = workspace
    agent = session(workspace, project=str(a.root))
    queued = agent.execute(f'enqueue --inp "{engineering / "A01.inp"}"')
    assert queued["status"] == "ENQUEUED"
    queue_id = queued["data"]["job_id"]
    before = (a.runtime_dir / "queue.json").read_bytes()

    async def check():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "abqjobpilot.mcp.server", "--project", str(a.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            env={**os.environ, "USERPROFILE": str(root)},
        )
        async with asyncio.timeout(30):
            async with Client(params, mode="legacy", read_timeout_seconds=15) as client:
                assert client.protocol_version is not None
                tools = await client.list_tools()
                names = {tool.name for tool in tools.tools}
                assert "abq_list_jobs" in names and "abq_job_status" in names
                assert "abq_enqueue" not in names
                listing = await client.call_tool("abq_list_jobs", {"scope": "queue"})
                assert listing.structured_content["data"]["jobs"][0]["queue_id"] == queue_id
                status = await client.call_tool("abq_job_status", {"scope": "queue", "identifier": queue_id})
                assert status.structured_content["status"] == "QUEUED"

    asyncio.run(check())
    assert before == (a.runtime_dir / "queue.json").read_bytes()
