"""Read-profile boundaries with empty, isolated Projects. No HIL or Grant is created."""
import asyncio

import pytest
from mcp import Client

from abqjobpilot.execution.models import ExecutionError
from abqjobpilot.execution.store import create_experiment
from abqjobpilot.mcp.agent_first_server import build_server
from abqjobpilot.mcp import historical_reads
from abqjobpilot.product_project import create_project
from test_product_project import inventory


def test_historical_profile_requires_a_product_project(tmp_path):
    ctx = create_experiment(tmp_path, tmp_path / "project")
    before = inventory(tmp_path)
    with pytest.raises(ExecutionError) as caught:
        build_server(ctx.root, historical_read_only=True)
    assert caught.value.code in {"PROJECT_INCOMPLETE", "NOT_AN_AGENT_FIRST_PROJECT"}
    assert inventory(tmp_path) == before


def test_historical_profile_requires_existing_sealed_plan(tmp_path):
    project = tmp_path / "sample"
    create_project(project, "Offline")
    before = inventory(project)
    with pytest.raises(ExecutionError) as caught:
        build_server(project, historical_read_only=True)
    assert caught.value.code == "PLAN_NOT_PREPARED"
    with pytest.raises(ExecutionError) as caught:
        build_server(project, connection_file="other.json", historical_read_only=True)
    assert caught.value.code == "INVALID_REQUEST"
    assert inventory(project) == before


def test_historical_catalog_is_read_only_and_live_catalog_is_unchanged(tmp_path, monkeypatch):
    project = tmp_path / "sample"
    create_project(project, "Offline")
    before = inventory(project)
    monkeypatch.setattr(historical_reads, "recorded_plan", lambda m: {"sanity": {"mode": "REAL", "hil": {}}})
    history = build_server(project, historical_read_only=True)
    live = build_server(project)
    async def catalog_for(server):
        async with Client(server, mode="legacy") as client:
            if server is history:
                for name in ("abq_submit_job", "abq_extract_odb", "abq_get_grant_status"):
                    reply = await client.call_tool(name, {})
                    assert reply.is_error and reply.structured_content["error"]["code"] == "UNKNOWN_TOOL"
            return {t.name: t for t in (await client.list_tools()).tools}

    catalog = asyncio.run(catalog_for(history))
    assert set(catalog) == {"abq_check_environment", "abq_get_run_status", "abq_get_receipt"}
    assert all(t.annotations.read_only_hint for t in catalog.values())
    receipt = catalog["abq_get_receipt"].input_schema
    assert receipt["required"] == ["idempotency_key"]
    assert set(receipt["properties"]) == {"idempotency_key", "operation_id"}
    standard = asyncio.run(catalog_for(live))
    assert set(standard) == set(catalog) | {"abq_get_grant_status", "abq_submit_job", "abq_extract_odb"}
    assert set(standard["abq_get_receipt"].input_schema["properties"]) == {"idempotency_key"}
    assert inventory(project) == before
