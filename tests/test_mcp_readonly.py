"""Read-only MCP protocol tests; all state lives under pytest temporary paths."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from abqjobpilot.database import ProjectHistoryRepository
from abqjobpilot.mcp.tools import ReadOnlyTools
from abqjobpilot.project.manager import ProjectManager
from abqjobpilot.queue_store import build_queue_record, save_queue


def inventory(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


@pytest.fixture
def fixture_project(tmp_path):
    engineering = tmp_path / "engineering"
    engineering.mkdir()
    inp = engineering / "Model.inp"
    inp.write_text("*Heading\n", encoding="utf-8")
    project = ProjectManager(recent_file=tmp_path / "recent.json").create_project(
        tmp_path / "project", "MCP fixture")
    record = build_queue_record(inp, 4, 0, "batch", "strategy", "Model", True, True, "",
                                queue_id="q_fixture")
    save_queue([record], runtime_dir=project.runtime_dir)
    (project.runtime_dir / "reports" / "historical.json").write_text(
        json.dumps({"queue_id": "q_report", "job_name": "Older", "status": "FAILED",
                    "inp_path": str(engineering / "Older.inp")}), encoding="utf-8")
    (engineering / "Model.sta").write_text("STA fixture\n", encoding="utf-8")
    (engineering / "Model.msg").write_text("MSG fixture\n", encoding="utf-8")
    (engineering / "Model.dat").write_text("DAT fixture\n", encoding="utf-8")
    (engineering / "Model.log").write_text("LOG fixture\n", encoding="utf-8")
    repo = ProjectHistoryRepository(project)
    job = repo.get_or_create_job(job_name="Model", inp_path=str(inp), queue_id="q_fixture")
    run = repo.create_run(job["job_id"], queue_id="q_fixture", status="FAILED",
                          working_dir=str(engineering))
    repo.add_or_update_artifact(run["run_id"], "STA", str(engineering / "Model.sta"),
                                exists_flag=True)
    return project, engineering, inp, job["job_id"]


def test_read_only_adapter_and_project_isolation(fixture_project, tmp_path):
    project, engineering, inp, job_id = fixture_project
    before = inventory(tmp_path)
    tools = ReadOnlyTools(str(project.root))
    assert tools.preflight(str(inp), cpus=4)["status"] == "PREVIEW_READY"
    assert tools.preflight(str(engineering / "absent.inp"))["status"] == "INVALID_REQUEST"
    assert tools.preflight(str(inp), cpus=0)["status"] == "INVALID_REQUEST"
    preview = tools.prepare_enqueue(str(inp), cpus=4)
    assert preview["status"] == "DRY_RUN_READY"
    assert not preview["data"]["queue_mutated"]
    assert not preview["data"]["solver_started"]
    assert tools.list_jobs()["data"]["jobs"][0]["queue_id"] == "q_fixture"
    assert tools.list_jobs(scope="history")["data"]["jobs"][0]["job_id"] == job_id
    assert tools.list_jobs(limit=999)["data"]["limit"] == 100
    assert tools.list_jobs(scope="invalid")["status"] == "INVALID_REQUEST"
    assert tools.job_status("queue", "q_fixture")["status"] == "QUEUED"
    assert tools.job_status("history", job_id)["status"] == "FAILED"
    assert tools.job_status("history", "missing")["status"] == "JOB_NOT_FOUND"
    outputs = tools.locate_outputs(queue_id="q_fixture")
    assert outputs["data"]["artifacts"]["STA"]["exists"]
    assert outputs["data"]["artifacts"]["MSG"]["exists"]
    assert outputs["data"]["artifacts"]["DAT"]["exists"]
    assert outputs["data"]["artifacts"]["LOG"]["exists"]
    assert outputs["data"]["artifacts"]["STA"]["path_source"] == "recorded"
    assert outputs["data"]["artifacts"]["LCK"]["path_source"] == "expected"
    assert not outputs["data"]["artifacts"]["ODB"]["exists"]
    assert outputs["data"]["odb_validity_verified"] is False
    assert before == inventory(tmp_path)

    other = ProjectManager(recent_file=tmp_path / "recent2.json").create_project(
        tmp_path / "other", "Other")
    assert ReadOnlyTools(str(other.root)).list_jobs()["data"]["jobs"] == []
    assert ReadOnlyTools(str(other.root)).list_jobs(scope="history")["data"]["jobs"] == []
    assert not (other.root / "project.db").exists()
    assert ReadOnlyTools(str(other.root)).job_status("history", "missing")["status"] == "JOB_NOT_FOUND"


def test_existing_odb_and_missing_logs_are_only_existence_checks(fixture_project, tmp_path):
    project, engineering, _, _ = fixture_project
    tools = ReadOnlyTools(str(project.root))
    before = inventory(tmp_path)
    outputs = tools.locate_outputs(queue_id="q_fixture")["data"]["artifacts"]
    assert outputs["ODB"] == {"path": str(engineering / "Model.odb"),
                              "path_source": "recorded", "exists": False}
    assert before == inventory(tmp_path)
    (engineering / "Model.odb").write_bytes(b"dummy placeholder; never parsed")
    (engineering / "Model.msg").unlink()
    outputs = tools.locate_outputs(queue_id="q_fixture")["data"]["artifacts"]
    assert outputs["ODB"]["exists"] is True
    assert outputs["MSG"]["exists"] is False
    assert tools.locate_outputs(queue_id="q_fixture")["data"]["odb_validity_verified"] is False


def test_multiple_attempts_and_invalid_counts(fixture_project, tmp_path):
    project, _, inp, job_id = fixture_project
    repo = ProjectHistoryRepository(project)
    repo.create_run(job_id, queue_id="q_second", status="COMPLETED")
    tools = ReadOnlyTools(str(project.root))
    before = inventory(tmp_path)
    assert tools.list_jobs(scope="history")["data"]["jobs"][0]["run_count"] == 2
    assert tools.job_status("history", job_id)["status"] == "COMPLETED"
    assert tools.preflight(str(inp), gpus=-1)["status"] == "INVALID_REQUEST"
    assert tools.prepare_enqueue(str(inp), cpus=-1)["status"] == "REJECTED"
    assert before == inventory(tmp_path)


def test_stored_running_is_not_claimed_live(fixture_project):
    project, _, inp, job_id = fixture_project
    repo = ProjectHistoryRepository(project)
    repo.create_run(job_id, queue_id="q_stale", status="RUNNING")
    status = ReadOnlyTools(str(project.root)).job_status("history", job_id)
    assert status["status"] == "STATUS_UNCONFIRMED"
    assert status["data"]["observed_status"] == "RUNNING"
    assert status["data"]["active_execution_confirmed"] is False
    record = build_queue_record(inp, 4, 0, "batch", "strategy", "Model", True, True, "",
                                queue_id="q_running")
    record["status"] = "RUNNING"
    save_queue([record], runtime_dir=project.runtime_dir)
    queue_status = ReadOnlyTools(str(project.root)).job_status("queue", "q_running")
    assert queue_status["status"] == "STATUS_UNCONFIRMED"
    assert queue_status["data"]["active_execution_confirmed"] is False


def test_protocol_stdio_initialize_list_call_and_integrity(fixture_project, tmp_path):
    mcp = pytest.importorskip("mcp", reason="Optional official MCP SDK v2 is unavailable")
    from mcp import Client, StdioServerParameters

    project, _, inp, job_id = fixture_project
    before = inventory(tmp_path)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "abqjobpilot.mcp.server", "--project", str(project.root)],
        cwd=str(Path(__file__).resolve().parents[1]),
        env={**os.environ, "USERPROFILE": str(tmp_path)},
    )

    async def exercise():
        async with asyncio.timeout(45):
            async with Client(params, mode="legacy", read_timeout_seconds=15) as client:
                assert client.protocol_version is not None
                assert client.server_info is not None
                assert client.server_info.version == "0.2.2.dev0"
                tools = await client.list_tools()
                names = {tool.name for tool in tools.tools}
                assert names == {"abq_preflight", "abq_list_jobs", "abq_job_status",
                                 "abq_locate_outputs", "abq_prepare_enqueue"}
                assert all(tool.annotations.read_only_hint for tool in tools.tools)
                assert all(tool.annotations.destructive_hint is False for tool in tools.tools)
                async def call(name, args):
                    result = await client.call_tool(name, args)
                    assert not result.is_error, result
                    assert result.structured_content is not None
                    return result.structured_content
                assert (await call("abq_preflight", {"inp_path": str(inp), "cpus": 4}))["status"] == "PREVIEW_READY"
                assert (await call("abq_list_jobs", {"scope": "queue"}))["data"]["jobs"][0]["queue_id"] == "q_fixture"
                assert (await call("abq_list_jobs", {"scope": "history"}))["data"]["jobs"][0]["job_id"] == job_id
                assert (await call("abq_job_status", {"scope": "queue", "identifier": "q_fixture"}))["status"] == "QUEUED"
                assert (await call("abq_locate_outputs", {"queue_id": "q_fixture"}))["data"]["artifacts"]["STA"]["exists"]
                preview = await call("abq_prepare_enqueue", {"inp_path": str(inp), "cpus": 4})
                assert preview["status"] == "DRY_RUN_READY"
                assert preview["data"]["queue_mutated"] is False
                assert preview["data"]["solver_started"] is False
                invalid = await client.call_tool("abq_preflight", {"cpus": 4})
                assert invalid.is_error
                unknown = await call("abq_job_status", {"scope": "queue", "identifier": "missing"})
                assert unknown["status"] == "UNKNOWN"

    asyncio.run(exercise())
    assert before == inventory(tmp_path)


def test_invalid_project_refused_without_creating_files(tmp_path):
    from abqjobpilot.mcp.server import build_server

    before = inventory(tmp_path)
    from abqjobpilot.api.project_surface import SurfaceFailure
    with pytest.raises((ValueError, OSError, SurfaceFailure)):
        build_server(str(tmp_path / "not-a-project"))
    assert before == inventory(tmp_path)


def test_invalid_manifest_and_unsupported_schema(tmp_path):
    from abqjobpilot.mcp.server import build_server

    project = ProjectManager(recent_file=tmp_path / "recent.json").create_project(
        tmp_path / "project", "Fixture")
    manifest = project.project_file
    original = manifest.read_bytes()
    manifest.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        build_server(str(project.root))
    manifest.write_bytes(original.replace(b'"schema_version": "1.0"',
                                          b'"schema_version": "999"'))
    with pytest.raises(ValueError):
        build_server(str(project.root))


def test_optional_sdk_absence_reports_error_on_stderr(tmp_path):
    # -S removes third-party site packages without changing the selected interpreter.
    result = subprocess.run(
        [sys.executable, "-S", "-m", "abqjobpilot.mcp.server", "--project", str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=15,
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "MCP Python SDK v2 is unavailable" in result.stderr


def test_normal_api_and_gui_import_without_optional_sdk():
    result = subprocess.run(
        [sys.executable, "-S", "-c",
         "import abqjobpilot; from abqjobpilot.api import AbqJobPilotClient; "
         "import run_gui; print(abqjobpilot.__version__, callable(run_gui.main))"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.2.2.dev0 True"


def test_log_tail_is_bounded_and_chronological(tmp_path):
    from abqjobpilot.api.status_reader import last_log_lines

    path = tmp_path / "large.log"
    path.write_bytes((b"old line\n" * 100000) + b"recent one\nrecent two\n")
    assert last_log_lines(str(path), line_count=2, max_bytes=128) == ["recent one", "recent two"]


def test_two_simultaneous_read_only_stdio_clients(fixture_project, tmp_path):
    pytest.importorskip("mcp", reason="Optional official MCP SDK v2 is unavailable")
    from mcp import Client, StdioServerParameters

    project, _, inp, _ = fixture_project
    before = inventory(tmp_path)

    async def one_client():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "abqjobpilot.mcp.server", "--project", str(project.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            env={**os.environ, "USERPROFILE": str(tmp_path)},
        )
        async with Client(params, mode="legacy", read_timeout_seconds=15) as client:
            for _ in range(2):
                result = await client.call_tool("abq_prepare_enqueue", {"inp_path": str(inp)})
                assert result.structured_content["status"] == "DRY_RUN_READY"
                listing = await client.call_tool("abq_list_jobs", {"scope": "history"})
                assert len(listing.structured_content["data"]["jobs"]) == 1

    async def exercise():
        async with asyncio.timeout(45):
            await asyncio.gather(one_client(), one_client())

    asyncio.run(exercise())
    assert before == inventory(tmp_path)
