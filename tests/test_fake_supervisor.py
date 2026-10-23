"""Windows multiprocess acceptance R3-01..12; every process belongs to this harness."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import socket
import struct
import time

import pytest

from abqjobpilot.execution import ExecutionError, ExperimentStore, open_existing_read_only
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.models import canonical_json, identifier
from abqjobpilot.execution.protocol import (IO_TIMEOUT, MAX_CONNECTIONS, MAX_EVENTS, MAX_REQUEST,
                                           MAX_RESPONSE, PROTOCOL, connect, receive, send)
from abqjobpilot.execution.store import acquire_supervisor_store
from execution_helpers import inventory
from supervisor_helpers import processes, read_json, wait_until


def wire(h, operation="health", arguments=None, **overrides):
    endpoint = read_json(h.endpoint_file)
    message = {key: endpoint[key] for key in ("project_id", "project_instance_id", "context_digest", "owner_id")}
    message.update(protocol=PROTOCOL, request_id=identifier("wire"), credential=h.credential,
                   operation=operation, arguments={} if arguments is None else arguments)
    message.update(overrides)
    return message


def business_inventory(h):
    return inventory(Path(h.context.root))


def test_independent_client_exit_owner_continues_and_reconnects(processes):
    h = processes
    owner = h.owner(barriers=["dispatch:after_claim"])
    client = h.spawn("client", operation="submit", arguments={"request": h.requests[0]}, wait_after_response=True)
    receipt = client.result()["receipt"]
    owner.reached("dispatch:after_claim")
    assert owner.identity["pid"] != client.identity["pid"]
    assert h.client().run(receipt["run_id"])["execution"] == "START_INTENT"
    client.terminate()  # Actual test client process exit; owner has not finished Fake yet.
    assert owner.process.poll() is None
    owner.release("dispatch:after_claim")
    run = h.finished(receipt["run_id"])
    second = h.spawn("client", operation="run", arguments={"run_id": receipt["run_id"]})
    assert second.result() == run
    assert second.process.wait(timeout=8) == 0
    assert run["artifact_validation"] == "VALID" and run["solver_conclusion"] == "NOT_RUN"
    assert h.client().receipt("key-0") == receipt
    assert h.client().validations(run["run_id"])[0]["scope"] == "simulation"


def test_accept_commit_response_lost_reconnect_reuses_receipt_and_effect(processes):
    h = processes
    owner = h.owner(barriers=["submit:before_response"])
    lost = h.spawn("client", operation="submit", arguments={"request": h.requests[0]})
    owner.reached("submit:before_response")  # Service.submit already returned after COMMIT.
    receipt = h.client().receipt("key-0")
    h.finished(receipt["run_id"])  # Execution continues while first reply is still blocked.
    lost.terminate()
    owner.release("submit:before_response")
    replay = h.client().submit(h.requests[0])
    assert replay["replayed"] and replay["receipt"] == receipt
    assert len(list(Path(h.context.runtime_root).rglob("result.json"))) == 1
    reader = open_existing_read_only(h.context)
    with reader.read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM consumption").fetchone()[0] == 1
    assert [e["type"] for e in h.client().events()].count("START_INTENT") == 1


def test_multiclient_idempotency_and_different_requests_single_slot(processes):
    h = processes
    owner = h.owner(barriers=["dispatch:after_claim"])
    with ThreadPoolExecutor(max_workers=6) as executor:
        receipts = list(executor.map(lambda _: h.client().submit(h.requests[0]), range(6)))
    assert sum(not r["replayed"] for r in receipts) == 1
    assert len({r["receipt"]["run_id"] for r in receipts}) == 1
    first = receipts[0]["receipt"]["run_id"]
    owner.reached("dispatch:after_claim")
    second = h.client().submit(h.requests[1])["receipt"]["run_id"]
    assert h.client().run(second)["queue_state"] == "PENDING"
    assert not (Path(h.context.runtime_root) / "fake_runs" / second).exists()
    owner.release("dispatch:after_claim")
    h.finished(first)
    h.finished(second)
    events = h.client().events()
    first_end = next(e["project_sequence"] for e in events if e["run_id"] == first and e["type"] == "VALIDATION_RECORDED")
    second_start = next(e["project_sequence"] for e in events if e["run_id"] == second and e["type"] == "START_INTENT")
    assert first_end < second_start
    conflict = {**h.requests[0], "plan_digest": "different"}
    with pytest.raises(ExecutionError, match="Same key") as error:
        h.client().submit(conflict)
    assert error.value.code == "IDEMPOTENCY_CONFLICT"


def test_competing_supervisor_and_supported_writer_cannot_bypass_owner(processes):
    h = processes
    first = h.owner()
    endpoint = read_json(h.endpoint_file)
    before = business_inventory(h)
    second = h.spawn("owner")
    assert second.process.wait(timeout=8) == 2
    assert read_json(second.control / "error.json")["error"]["code"] == "OWNER_BUSY"
    probe = h.spawn("writer_probe")
    assert probe.result() == ["OWNER_UNCONFIRMED", "OWNER_BUSY"]
    assert probe.process.wait(timeout=8) == 0
    with pytest.raises(ExecutionError) as error:
        acquire_supervisor_store(h.context, read_json(h.bootstrap)["authority_instance"])
    assert error.value.code == "OWNER_BUSY"
    with pytest.raises(ExecutionError):
        ExperimentStore(h.context)
    assert read_json(h.endpoint_file) == endpoint and business_inventory(h) == before
    assert h.client().health()["process"]["pid"] == first.identity["pid"]


def test_running_query_nonblocking_readonly_pages_reconnect_and_caps(processes):
    h = processes
    owner = h.owner(barriers=["dispatch:after_artifact"])
    run_id = h.client().submit(h.requests[0])["receipt"]["run_id"]
    owner.reached("dispatch:after_artifact")
    before = business_inventory(h)
    start = time.monotonic()
    page = h.client().events(0, 1)
    assert len(page) == 1
    assert h.client().run(run_id)["execution"] == "START_INTENT"
    assert h.client().validations(run_id) == []
    assert h.client().health()["dispatch_enabled"]
    assert time.monotonic() - start < IO_TIMEOUT
    assert business_inventory(h) == before
    with pytest.raises(ExecutionError):
        h.client().events(0, MAX_EVENTS + 1)
    cursor = page[-1]["project_sequence"]
    owner.release("dispatch:after_artifact")
    h.finished(run_id)
    while True:
        portion = h.client().events(cursor, 1)  # Each call creates a new short connection.
        if not portion:
            break
        page.extend(portion)
        cursor = portion[-1]["project_sequence"]
    assert [e["project_sequence"] for e in page] == [1, 2, 3, 4]
    assert page == h.client().events()


@pytest.mark.parametrize("changes,code", [
    ({"credential": "wrong"}, "AUTHENTICATION_FAILED"),
    ({"protocol": "future"}, "PROTOCOL_MISMATCH"),
    ({"project_id": "wrong"}, "ENDPOINT_IDENTITY_MISMATCH"),
    ({"project_instance_id": "wrong"}, "ENDPOINT_IDENTITY_MISMATCH"),
    ({"context_digest": "wrong"}, "ENDPOINT_IDENTITY_MISMATCH"),
    ({"owner_id": "stale"}, "ENDPOINT_IDENTITY_MISMATCH"),
    ({"operation": "approve"}, "UNKNOWN_OPERATION"),
    ({"operation": "__getattribute__"}, "UNKNOWN_OPERATION"),
    ({"client_namespace": "bypass"}, "INVALID_REQUEST"),
])
def test_protocol_identity_authentication_whitelist_rejected_without_effect(processes, changes, code):
    h = processes
    h.owner()
    before = business_inventory(h)
    with connect(read_json(h.endpoint_file)["port"]) as stream:
        send(stream, {**wire(h, "submit", {"request": h.requests[0]}), **changes}, MAX_REQUEST)
        response = receive(stream, MAX_RESPONSE)
    assert not response["ok"] and response["result"]["error"]["code"] == code
    assert h.credential not in canonical_json(response)
    assert business_inventory(h) == before


def test_message_bounds_truncation_partial_arrival_and_absolute_deadline(processes):
    h = processes
    h.owner()
    port = read_json(h.endpoint_file)["port"]
    before = business_inventory(h)
    with connect(port) as stream:
        stream.sendall(struct.pack("!I", MAX_REQUEST + 1))
        assert receive(stream, MAX_RESPONSE)["result"]["error"]["code"] == "MESSAGE_TOO_LARGE"
    with connect(port) as stream:
        stream.sendall(struct.pack("!I", 100) + b'{"truncated":')
        stream.shutdown(socket.SHUT_WR)
        assert stream.recv(1) == b""
    message = canonical_json(wire(h)).encode("utf-8")
    frame = struct.pack("!I", len(message)) + message
    with connect(port) as stream:
        for offset in range(0, len(frame), 13):
            stream.sendall(frame[offset:offset + 13])
        assert receive(stream, MAX_RESPONSE)["ok"]
    with connect(port) as slow:
        slow.sendall(struct.pack("!I", 100))
        start = time.monotonic()
        assert h.client().health()["backend"] == "fake-v1"
        slow.settimeout(IO_TIMEOUT + 1)
        assert slow.recv(1) == b""
        assert time.monotonic() - start < IO_TIMEOUT + 1
    assert business_inventory(h) == before


def test_connection_cap_is_bounded_and_recovers_after_frame_deadline(processes):
    h = processes
    h.owner()
    streams = []
    try:
        for _ in range(MAX_CONNECTIONS + 4):
            stream = connect(read_json(h.endpoint_file)["port"])
            streams.append(stream)
        # Every held incomplete request expires. Excess sockets are closed immediately.
        for stream in streams:
            stream.settimeout(IO_TIMEOUT + 1)
            assert stream.recv(1) == b""
        assert h.client().health()["max_connections"] == MAX_CONNECTIONS
    finally:
        for stream in streams:
            stream.close()


def test_actual_owner_crash_after_artifact_restart_uncertain_and_pending_blocked(processes):
    h = processes
    owner = h.owner(barriers=["dispatch:after_artifact"])
    receipt = h.client().submit(h.requests[0])["receipt"]
    owner.reached("dispatch:after_artifact")
    pending = h.client().submit(h.requests[1])["receipt"]
    artifact = Path(h.context.runtime_root) / "fake_runs" / receipt["run_id"] / "result.json"
    original = artifact.read_bytes()
    owner.terminate()  # Actual Windows process handle termination at explicit post-file/pre-terminal barrier.
    assert owner.process.returncode is not None
    new_owner = h.owner()
    assert new_owner.identity != owner.identity
    client = h.client()
    assert not client.health()["dispatch_enabled"]
    uncertain = client.run(receipt["run_id"])
    assert uncertain["reconciliation_requirement"] == "RECONCILIATION_REQUIRED"
    assert uncertain["artifact_validation"] == "NOT_RUN" and client.validations(receipt["run_id"]) == []
    assert client.run(pending["run_id"])["queue_state"] == "PENDING"
    assert client.run(pending["run_id"])["reconciliation_requirement"] == "NONE"
    before = business_inventory(h)
    assert client.submit(h.requests[0])["receipt"] == receipt
    with pytest.raises(ExecutionError) as error:
        client.submit(h.requests[2])
    assert error.value.code == "DISPATCH_PAUSED"
    assert business_inventory(h) == before and artifact.read_bytes() == original
    assert len(list(Path(h.context.runtime_root).rglob("result.json"))) == 1
    assert len(client.events()) == 3  # Two accepts and one START_INTENT; queries/restart did not repair.


def test_stale_endpoint_metadata_does_not_connect_takeover_or_autostart(processes):
    h = processes
    owner = h.owner()
    old = read_json(h.endpoint_file)
    # Diagnostic file deliberately stale while kernel ownership remains held.
    (Path(h.context.root) / "owner.json").write_text(canonical_json({**old, "owner_id": "stale", "process": {"pid": 1}}), encoding="utf-8")
    competitor = h.spawn("owner")
    assert competitor.process.wait(timeout=8) == 2
    assert read_json(competitor.control / "error.json")["error"]["code"] == "OWNER_BUSY"
    owner.terminate()
    before = business_inventory(h)
    with pytest.raises(ExecutionError) as error:
        FakeClient(old, h.credential).health()
    assert error.value.code == "COMMUNICATION_UNKNOWN"
    assert business_inventory(h) == before
    h.owner()  # Only an explicit trusted harness start can acquire the now-released OS lock.
    fresh = read_json(h.endpoint_file)
    with pytest.raises(ExecutionError) as error:
        FakeClient({**old, "port": fresh["port"]}, h.credential).health()
    assert error.value.code == "ENDPOINT_IDENTITY_MISMATCH"
    assert not h.client().health()["dispatch_enabled"]


@pytest.mark.parametrize("sidecar", ["-journal", "-wal", "-shm"])
def test_maintenance_query_never_repairs_existing_sidecars(processes, sidecar):
    h = processes
    owner = h.owner()
    # Pause owner by a clean shutdown; restart is query-only and won't poll dispatch.
    (owner.control / "stop.json").write_text("{}", encoding="utf-8")
    assert owner.process.wait(timeout=8) == 0
    h.owner()
    path = Path(h.context.execution_store + sidecar)
    path.write_bytes(b"explicit test maintenance marker")
    before = business_inventory(h)
    with pytest.raises(ExecutionError) as error:
        h.client().events()
    assert error.value.code == "STORE_REQUIRES_MAINTENANCE"
    assert business_inventory(h) == before


def test_wrong_bootstrap_authority_cannot_adopt_and_does_not_poison_owner(processes):
    h = processes
    body = read_json(h.bootstrap)
    h.bootstrap.write_text(canonical_json({**body, "authority_instance": "wrong"}), encoding="utf-8")
    child = h.spawn("owner")
    assert child.process.wait(timeout=8) == 2
    assert read_json(child.control / "error.json")["error"]["code"] == "GRANT_SCOPE_MISMATCH"
    h.bootstrap.write_text(canonical_json(body), encoding="utf-8")
    h.owner()
    assert h.client().health()["dispatch_enabled"]


def test_client_timeout_after_accept_does_not_cancel_owner(processes):
    h = processes
    owner = h.owner(barriers=["submit:before_response", "dispatch:after_artifact"])
    with pytest.raises(ExecutionError) as error:
        h.client().submit(h.requests[0])
    assert error.value.code == "ACCEPTANCE_UNKNOWN"
    assert error.value.to_dict()["request_status"] == "ACCEPTANCE_UNKNOWN"
    owner.reached("submit:before_response")
    owner.reached("dispatch:after_artifact")
    receipt = h.client().receipt("key-0")
    assert owner.process.poll() is None
    owner.release("submit:before_response")
    owner.release("dispatch:after_artifact")
    h.finished(receipt["run_id"])
    assert h.client().submit(h.requests[0])["receipt"] == receipt


@pytest.mark.parametrize("raw", [b'\xff', b'{"operation":1,"operation":2}', b'{"number":NaN}', b'[]'])
def test_malformed_json_refused_and_owner_remains_responsive(processes, raw):
    h = processes
    h.owner()
    before = business_inventory(h)
    with connect(read_json(h.endpoint_file)["port"]) as stream:
        stream.sendall(struct.pack("!I", len(raw)) + raw)
        assert receive(stream, MAX_RESPONSE)["result"]["error"]["code"] == "INVALID_REQUEST"
    assert h.client().health()["simulation"] and business_inventory(h) == before


def test_response_serialization_bound_before_any_bytes_sent():
    left, right = socket.socketpair()
    try:
        with pytest.raises(ExecutionError) as error:
            send(left, {"oversize": "x" * MAX_RESPONSE}, MAX_RESPONSE)
        assert error.value.code == "MESSAGE_TOO_LARGE"
        right.settimeout(0.05)
        with pytest.raises(TimeoutError):
            right.recv(1)
    finally:
        left.close()
        right.close()
