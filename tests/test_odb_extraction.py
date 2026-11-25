"""Actual stdio/IPC and process interruption for the TEST_ONLY extraction backend."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from abqjobpilot.execution import ExecutionError, open_existing_read_only
from abqjobpilot.execution.models import bytes_digest, canonical_json
from abqjobpilot.execution.odb_contract import FIXTURE, SELECTOR, VERSION
from abqjobpilot.execution.odb_extractor import ACTION
from abqjobpilot.execution.paths import result_path
from test_agent_first_mcp import call, stdio
from test_delegated_owner import DelegatedOwnerHarness
from test_service_attachment import connection


def provision(h, unused):
    plan = h.plan(h.spec(job_id="fixture-source"))
    return h.request(plan, h.grant(plan), "source-key")


@pytest.fixture
def isolated_fixture(tmp_path):
    h = DelegatedOwnerHarness(tmp_path, provision=provision, odb_fixture_test_only=True)
    try:
        yield h
    finally:
        (h.root / "private" / "connection.json").unlink(missing_ok=True)
        h.close()


def complete_source(h):
    submitted = h.client().submit(h.provisioned)["receipt"]
    run = h.finished(submitted["run_id"])
    assert run["artifact_validation"] == "VALID" and run["solver_conclusion"] == "NOT_RUN"
    request = {"contract_version": VERSION, "mode": "TEST_ONLY", "receipt_id": submitted["request_id"],
               "idempotency_key": "extract-1", "script_id": FIXTURE, **SELECTOR, "first_frame": 1, "frame_count": 2}
    return run, request


def test_stdio_extracts_only_explicit_fixture_with_provenance(isolated_fixture):
    h = isolated_fixture
    h.owner()
    connection(h)
    run, request = complete_source(h)
    run_id = run["run_id"]
    parameters = {"run_id": run_id, "extraction": request}
    actual_source = result_path(h.context, run_id)

    async def exercise():
        async with stdio(h) as client:
            environment = await call(client, "abq_check_environment")
            assert environment["capabilities"]["abq_extract_odb"] == "UNAVAILABLE"
            assert environment["capabilities"]["odb_fixture_extraction"] == "TEST_ONLY"
            await call(client, "abq_extract_odb", {"run_id": run_id}, error="CAPABILITY_UNAVAILABLE")
            await call(client, "abq_extract_odb", {**parameters, "extraction": {**request, "mode": "REAL"}},
                       error="CAPABILITY_UNAVAILABLE")
            result = await call(client, "abq_extract_odb", parameters)
            receipt = result["receipt"]
            assert not result["replayed"] and receipt["operation_status"] == "TEST_ONLY_COMPLETED"
            assert receipt == h.client().management_receipt(ACTION, request["idempotency_key"])
            artifact = receipt["artifact"]
            data = artifact["data"]
            raw = canonical_json(data).encode("utf-8")
            assert artifact["sha256"] == bytes_digest(raw) and artifact["size"] == len(raw)
            assert data["source"]["sha256"] == bytes_digest(actual_source.read_bytes())
            assert data["source"]["kind"] == "FAKE_RESULT_JSON"
            assert data["source"]["receipt_id"] == request["receipt_id"] and data["source"]["run_id"] == run_id
            assert data["source"]["phase_attempt_id"] == run["phase_attempt_id"]
            assert data["script_version"] == FIXTURE and data["parameters"]["region"] == SELECTOR["region"]
            assert data["simulation"] is True and data["native_odb_verified"] is False and data["solver_conclusion"] == "NOT_RUN"
            assert [row["frame"] for row in data["rows"]] == [1, 2]
            replay = await call(client, "abq_extract_odb", parameters)
            assert replay["replayed"] and replay["receipt"] == receipt
            await call(client, "abq_extract_odb", {**parameters, "extraction": {**request, "first_frame": 0}},
                       error="IDEMPOTENCY_CONFLICT")
            (h.root / "fixture-extraction-proof.json").write_text(canonical_json(receipt), encoding="utf-8")

    asyncio.run(exercise())
    assert h.client().run(run_id) == run and not list(Path(h.context.runtime_root).rglob("*.odb"))


def test_extraction_refuses_untrusted_source_paths_scripts_and_selectors(isolated_fixture):
    h = isolated_fixture
    h.owner()
    connection(h)
    run, request = complete_source(h)
    run_id = run["run_id"]

    async def exercise():
        async with stdio(h) as client:
            cases = [({"script_id": "outside.py"}, "ODB_SCRIPT_NOT_ALLOWED"),
                     ({"field": "S"}, "ODB_FIELD_NOT_ALLOWED"), ({"region": "ALL"}, "ODB_FIELD_NOT_ALLOWED"),
                     ({"component": "U1"}, "ODB_FIELD_NOT_ALLOWED"), ({"frame_count": 4}, "ODB_RANGE_INVALID"),
                     ({"python": "untrusted"}, "INVALID_REQUEST"),
                     ({"odb_path": str(h.root.parent / "outside.odb")}, "INVALID_REQUEST"),
                     ({"output_path": str(h.root.parent / "outside.json")}, "INVALID_REQUEST"),
                     ({"receipt_id": "req-other"}, "ODB_SOURCE_UNTRUSTED")]
            for overrides, code in cases:
                await call(client, "abq_extract_odb", {"run_id": run_id, "extraction": {**request, **overrides}}, error=code)
            held = h.client().submit_delegated(h.requests[0])["receipt"]
            await call(client, "abq_extract_odb", {"run_id": held["run_id"],
                "extraction": {**request, "receipt_id": held["request_id"]}}, error="ODB_SOURCE_UNTRUSTED")
            params = {"run_id": run_id, "extraction": request}
            path = result_path(h.context, run_id)
            path.write_bytes(b"external substitute")
            await call(client, "abq_extract_odb", params, error="ODB_SOURCE_UNTRUSTED")
            path.unlink()
            await call(client, "abq_extract_odb", params, error="ODB_SOURCE_NOT_FOUND")
            with pytest.raises(ExecutionError) as missing:
                h.client().management_receipt(ACTION, request["idempotency_key"])
            assert missing.value.code == "NOT_FOUND"

    asyncio.run(exercise())


def test_fixture_cannot_be_enabled_by_an_ipc_argument(tmp_path):
    h = DelegatedOwnerHarness(tmp_path, provision=provision)
    try:
        h.owner()
        run, request = complete_source(h)
        with pytest.raises(ExecutionError) as denied:
            h.client().extract_odb(run["run_id"], request)
        assert denied.value.code == "CAPABILITY_UNAVAILABLE"
    finally:
        h.close()


def test_interrupted_owner_never_fabricates_extraction_completion(isolated_fixture):
    h = isolated_fixture
    owner = h.owner(barriers=["odb_fixture:before_receipt"])
    run, request = complete_source(h)
    run_id = run["run_id"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        interrupted = pool.submit(h.client().extract_odb, run_id, request)
        owner.reached("odb_fixture:before_receipt")
        owner.terminate()
        with pytest.raises(ExecutionError) as lost:
            interrupted.result(timeout=8)
        assert lost.value.code == "ACCEPTANCE_UNKNOWN"
    reader = open_existing_read_only(h.context)
    with pytest.raises(ExecutionError) as missing:
        reader.management_receipt("delegated-test-client", ACTION, request["idempotency_key"])
    assert missing.value.code == "NOT_FOUND"
    h.owner()
    assert h.client().run(run_id) == run
    with pytest.raises(ExecutionError) as paused:
        h.client().extract_odb(run_id, request)
    assert paused.value.code == "DISPATCH_PAUSED"
