"""Real MCP stdio and authenticated loopback against the isolated Fake Owner."""

from contextlib import asynccontextmanager
import asyncio
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import pytest
from mcp import Client, StdioServerParameters

from abqjobpilot import __version__
from abqjobpilot.execution import ExecutionError, ExperimentStore, create_experiment, open_existing_read_only
from abqjobpilot.execution.models import canonical_json, now
from abqjobpilot.execution.test_authority import revoke_delegated_fake
from abqjobpilot.mcp.agent_first_tools import CONTRACT_VERSION, SUBMIT_FIELDS
from execution_helpers import inventory
from supervisor_helpers import ProcessHarness, read_json
from test_delegated_grant import approve
from test_delegated_owner import DelegatedOwnerHarness
from test_service_attachment import connection

READ = {"abq_check_environment", "abq_get_grant_status", "abq_get_run_status", "abq_get_receipt"}
TOOLS = READ | {"abq_submit_job", "abq_extract_odb"}
WORKSPACE = Path(__file__).resolve().parents[1]


def arguments(request):
    return {key: request[key] for key in SUBMIT_FIELDS}


def provision(h, plan):
    current = now()
    with patch("abqjobpilot.execution.test_authority.now", return_value=current - 60):
        expired = approve(h, plan, approval_key="old-approval", expires_at=current - 1)
    revoked = approve(h, plan, approval_key="revoked-approval")
    revoke_delegated_fake(h.service, revoked["grant_id"])
    exact = h.plan(h.spec(job_id="legacy-single-run"))
    return {"expired": expired["grant_id"], "revoked": revoked["grant_id"],
            "exact": h.request(exact, h.grant(exact), "old-single"), "input": h.input}


@pytest.fixture
def isolated(tmp_path):
    h = DelegatedOwnerHarness(tmp_path, provision=provision)
    try:
        yield h
    finally:
        (h.root / "private" / "connection.json").unlink(missing_ok=True)
        h.close()


@asynccontextmanager
async def stdio(h, *, explicit_connection=False):
    args = ["-B", "-m", "abqjobpilot.mcp.agent_first_server", "--project", h.context.root]
    if explicit_connection:
        args.extend(["--connection-file", str(h.root / "private" / "connection.json")])
    options = StdioServerParameters(command=sys.executable, args=args, cwd=str(WORKSPACE),
                                    env={**os.environ, "USERPROFILE": str(h.root), "PYTHONDONTWRITEBYTECODE": "1"})
    async with asyncio.timeout(45):
        async with Client(options, mode="legacy", read_timeout_seconds=15) as client:
            assert client.protocol_version and client.server_info.version == __version__
            assert client.server_info.name == "AbqJobPilot Agent-first"
            yield client


async def call(client, tool, arguments=None, *, error=None):
    result = await client.call_tool(tool, arguments or {})
    assert result.is_error is (error is not None)
    payload = result.structured_content
    assert payload == json.loads(result.content[0].text)
    assert payload["contract_version"] == CONTRACT_VERSION
    if error is not None:
        assert payload["ok"] is False and payload["error"]["code"] == error, payload
        assert "receipt" not in payload and "data" not in payload
        return payload
    assert payload["ok"] is True and "project" in payload
    return payload["data"]


def test_six_tools_and_round_trip_with_independent_owner(isolated):
    h = isolated
    owner = h.owner()
    connection(h)

    async def exercise():
        async with stdio(h, explicit_connection=True) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            assert set(tools) == TOOLS
            for name, tool in tools.items():
                assert tool.annotations.read_only_hint is (name in READ)
                assert tool.annotations.open_world_hint is False
                assert tool.input_schema["additionalProperties"] is False
                assert tool.meta["abqjobpilot/contract_version"] == CONTRACT_VERSION
            assert tools["abq_submit_job"].meta["abqjobpilot/permission"] == "CONTROLLED_WRITE"
            assert tools["abq_submit_job"].annotations.idempotent_hint is True
            assert tools["abq_extract_odb"].meta["abqjobpilot/permission"] == "CONTROLLED_OPERATION"
            assert tools["abq_extract_odb"].meta["abqjobpilot/availability"] == "UNAVAILABLE"

            before = inventory(Path(h.context.root))
            environment = await call(client, "abq_check_environment")
            assert environment["product_version"] == __version__
            assert environment["supervisor"]["owner_id"] == h.client().endpoint["owner_id"]
            assert environment["supervisor"]["gate_state"] == "OPEN"
            assert environment["supervisor"]["execution_scope"] == "TEST_ONLY"
            assert environment["accepting_new_delegated_requests"]
            assert environment["capabilities"]["abq_extract_odb"] == "UNAVAILABLE"
            grant_args = {"grant_id": h.grant_id}
            status = (await call(client, "abq_get_grant_status", grant_args))["grant"]
            assert status["validity"] == "VALID" and status["remaining"] == 2
            assert "authority_instance" not in status and "input_scope" not in status
            assert inventory(Path(h.context.root)) == before
            submitted = []
            for request in h.requests:
                result = await call(client, "abq_submit_job", arguments(request))
                assert result["request_status"] == "ACCEPTED" and not result["replayed"]
                submitted.append(result["receipt"])
            first, second = submitted
            assert first["run_id"] != second["run_id"]
            replay = await call(client, "abq_submit_job", arguments(h.requests[0]))
            assert replay["replayed"] and replay["receipt"] == first
            await call(client, "abq_submit_job", {**arguments(h.requests[0]), "job_revision": 2},
                       error="IDEMPOTENCY_CONFLICT")
            await call(client, "abq_submit_job", {**arguments(h.requests[0]), "idempotency_key": "overflow"},
                       error="GRANT_BUDGET_EXHAUSTED")
            with pytest.raises(ExecutionError) as rejected:
                h.client().submit_delegated({**h.requests[0], "idempotency_key": "overflow"})
            assert rejected.value.code == "GRANT_BUDGET_EXHAUSTED"
            status = (await call(client, "abq_get_grant_status", grant_args))["grant"]
            assert status["validity"] == "VALID" and status["remaining"] == 0 and status["consumed"] == 2
            run_args = {"run_id": first["run_id"]}
            run = await call(client, "abq_get_run_status", run_args)
            assert run["run"]["admission_only"] is True and run["run"]["execution"] == "PLANNED"
            assert run["run"]["solver_conclusion"] == "NOT_RUN"
            assert run["progress"] == {"status": "NOT_APPLICABLE", "records": []}
            assert (await call(client, "abq_get_receipt", {"idempotency_key": "key-0"}))["receipt"] == first
            before = inventory(Path(h.context.root))
            await call(client, "abq_extract_odb", run_args, error="CAPABILITY_UNAVAILABLE")
            assert inventory(Path(h.context.root)) == before

        assert owner.process.poll() is None
        async with stdio(h) as client:
            assert (await call(client, "abq_get_run_status", run_args)) == run
            assert (await call(client, "abq_get_receipt", {"idempotency_key": "key-0"}))["receipt"] == first
            assert h.client().receipt("key-0") == first
            assert h.client().run(first["run_id"])["plan_id"] == run["run"]["plan_id"]
            assert inventory(Path(h.context.root)) == before
        assert [row["type"] for row in h.client().events()] == ["REQUEST_ACCEPTED", "REQUEST_ACCEPTED"]
        assert not list(Path(h.context.runtime_root).rglob("*"))

    asyncio.run(exercise())


def test_refusals_are_read_only_and_cannot_route_exact_grants(isolated):
    h = isolated
    h.owner()
    connection(h)
    source = h.provisioned["input"]
    other = create_experiment(h.root, h.root / "other-project")
    ExperimentStore(other).close()

    async def exercise():
        async with stdio(h) as client:
            request = arguments(h.requests[0])
            before = inventory(Path(h.context.root))
            missing = dict(request)
            missing.pop("grant_id")
            await call(client, "abq_submit_job", missing, error="GRANT_REQUIRED")
            await call(client, "abq_submit_job", {**request, "grant_id": "grant_unregistered"}, error="GRANT_REQUIRED")
            await call(client, "abq_get_receipt", {"idempotency_key": "key-0"}, error="NOT_FOUND")
            await call(client, "abq_get_grant_status", {"grant_id": "grant_unregistered"}, error="NOT_FOUND")
            for key in ("expired", "revoked"):
                grant_id = h.provisioned[key]
                await call(client, "abq_submit_job", {**request, "grant_id": grant_id}, error="GRANT_" + key.upper())
                status = (await call(client, "abq_get_grant_status", {"grant_id": grant_id}))["grant"]
                assert status["validity"] == key.upper() and status["consumed"] == 0
            for identity in ("project_id", "project_instance_id"):
                await call(client, "abq_submit_job", {**request, identity: getattr(other, identity)},
                           error="PROJECT_IDENTITY_MISMATCH")
            for name in ("abq_issue_grant", "abq_modify_grant", "abq_expand_grant", "abq_revoke_grant"):
                await call(client, name, error="UNKNOWN_TOOL")
            for overrides, code in (({"grant_id": None}, "GRANT_REQUIRED"),
                                    ({"project_id": other.project_id}, "PROJECT_IDENTITY_MISMATCH"),
                                    ({"project_instance_id": other.project_instance_id}, "PROJECT_IDENTITY_MISMATCH"),
                                    ({"mode": "REAL"}, "INVALID_REQUEST")):
                with pytest.raises(ExecutionError) as rejected:
                    h.client().submit_delegated({**h.requests[0], **overrides})
                assert rejected.value.code == code
            for extra in ({"max_runs": 100}, {"inp_path": str(h.root.parent / "outside.inp")}, {"mode": "REAL"},
                          {"retry_of": "r_missing"}):
                await call(client, "abq_submit_job", {**request, **extra}, error="INVALID_REQUEST")
            await call(client, "abq_submit_job", arguments(h.provisioned["exact"]), error="TEST_GRANT_ONLY")
            await call(client, "abq_get_grant_status", {"grant_id": h.provisioned["exact"]["grant_id"]},
                       error="DELEGATED_SCOPE_MISMATCH")
            assert inventory(Path(h.context.root)) == before

            outside = h.root / "outside.txt"
            source.replace(outside)
            source.hardlink_to(outside)
            try:
                await call(client, "abq_submit_job", request, error="OUTPUT_SCOPE_VIOLATION")
            finally:
                source.unlink()
                outside.replace(source)
            status = (await call(client, "abq_get_grant_status", {"grant_id": h.grant_id}))["grant"]
            assert status["remaining"] == 2 and h.client().events() == []

            native = h.client().submit(h.provisioned["exact"])["receipt"]
            assert h.finished(native["run_id"])["solver_conclusion"] == "NOT_RUN"
            await call(client, "abq_submit_job", arguments(h.provisioned["exact"]), error="TEST_GRANT_ONLY")
            with pytest.raises(ExecutionError) as rejected:
                h.client().submit_delegated(h.provisioned["exact"])
            assert rejected.value.code == "TEST_GRANT_ONLY"
            assert (await call(client, "abq_get_receipt", {"idempotency_key": "old-single"}))["receipt"] == native

    asyncio.run(exercise())


def test_non_opted_in_owner_advertises_no_delegated_submission(tmp_path):
    h = ProcessHarness(tmp_path)
    try:
        h.owner()
        connection(h)

        async def exercise():
            async with stdio(h) as client:
                environment = await call(client, "abq_check_environment")
                assert environment["supervisor"]["status"] == "CONNECTED"
                assert not environment["accepting_new_delegated_requests"]
                assert environment["capabilities"]["abq_submit_job"] == "UNAVAILABLE"
                assert environment["capabilities"]["abq_get_grant_status"] == "UNAVAILABLE"
                await call(client, "abq_submit_job", arguments(h.requests[0]), error="TEST_SCOPE_REQUIRED")
                assert h.client().events() == []

        asyncio.run(exercise())
    finally:
        (h.root / "private" / "connection.json").unlink(missing_ok=True)
        h.close()


def test_missing_and_wrong_owner_credentials_do_not_start_or_write(isolated):
    h = isolated

    async def exercise():
        async with stdio(h) as client:
            assert (await call(client, "abq_check_environment", error="NOT_FOUND"))["supervisor"]["status"] == "UNAVAILABLE"
            assert not h.children
            h.owner()
            path = connection(h)
            original = read_json(path)
            path.write_text(canonical_json({**original, "credential": "untrusted-test-token"}), encoding="utf-8")
            before = inventory(Path(h.context.root))
            denied = await call(client, "abq_submit_job", arguments(h.requests[0]), error="AUTHENTICATION_FAILED")
            assert "untrusted-test-token" not in json.dumps(denied)
            assert denied["request_status"] == "REJECTED"
            assert inventory(Path(h.context.root)) == before
            assert h.client().events() == []

    asyncio.run(exercise())


def test_ipc_reply_lost_then_stdio_reconnect_reads_committed_acceptance(isolated):
    h = isolated
    owner = h.owner(barriers=["submit:before_response"])
    connection(h)

    async def exercise():
        async with stdio(h) as client:
            unknown = await call(client, "abq_submit_job", arguments(h.requests[0]), error="ACCEPTANCE_UNKNOWN")
            assert unknown["request_status"] == "ACCEPTANCE_UNKNOWN"
            assert unknown["idempotency_key"] == "key-0" and unknown["error"]["recovery"] == "QUERY_ORIGINAL_RECEIPT"
        owner.reached("submit:before_response")
        assert owner.process.poll() is None
        owner.release("submit:before_response")
        original = h.client().receipt("key-0")
        assert [row["type"] for row in h.client().events()] == ["REQUEST_ACCEPTED"]
        reader = open_existing_read_only(h.context)
        budget = reader.delegated_budget(h.context, h.grant_id)
        assert budget["run_ids"] == [original["run_id"]] and budget["remaining"] == 1
        async with stdio(h) as restarted:
            assert (await call(restarted, "abq_get_receipt", {"idempotency_key": "key-0"}))["receipt"] == original
            run = (await call(restarted, "abq_get_run_status", {"run_id": original["run_id"]}))["run"]
            assert run["execution"] == "PLANNED" and run["revision"] == 1
            assert (await call(restarted, "abq_get_grant_status", {"grant_id": h.grant_id}))["grant"]["remaining"] == 1
        assert reader.delegated_budget(h.context, h.grant_id) == budget

    asyncio.run(exercise())
