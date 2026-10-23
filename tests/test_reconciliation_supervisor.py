from pathlib import Path

import pytest

from abqjobpilot.execution import ExecutionError
from abqjobpilot.execution.models import canonical_json, identifier
from abqjobpilot.execution.reconciliation import ADOPT, RESUME
from execution_helpers import inventory
from reconciliation_helpers import adoption_scope, management_request
from supervisor_helpers import processes, read_json, wait_until


def permit(h, owner, action, scope, key):
    path = owner.control / (identifier("grant") + ".request.json")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(canonical_json({"action": action, "scope": scope}), encoding="utf-8")
    temporary.replace(path)
    reply = path.with_name(path.name.replace(".request.json", ".reply.json"))
    wait_until(reply.exists)
    grant_id = read_json(reply)["grant_id"]
    return management_request(h.context, read_json(h.endpoint_file)["owner_id"], action, scope, grant_id, key)


@pytest.mark.parametrize("lose_response", [False, True])
def test_windows_crash_reconcile_explicit_resume_end_to_end(processes, lose_response):
    h = processes
    original_owner = h.owner(barriers=["dispatch:after_artifact"])
    accepted = h.client().submit(h.requests[0])["receipt"]
    run_id = accepted["run_id"]
    original_owner.reached("dispatch:after_artifact")
    pending = h.client().submit(h.requests[1])["receipt"]
    artifact = Path(h.context.runtime_root) / "fake_runs" / run_id / "result.json"
    original_bytes, original_mtime = artifact.read_bytes(), artifact.stat().st_mtime_ns
    original_owner.terminate()
    owner = h.owner(management_control=True, barriers=["management:before_response"] if lose_response else [])
    client = h.client()
    before = inventory(Path(h.context.root))
    preview = client.preview_reconciliation(run_id)
    assert preview == client.preview_reconciliation(run_id)
    assert preview["candidate_action"] == ADOPT and preview["gate"]["state"] == "PAUSED"
    assert inventory(Path(h.context.root)) == before
    unauth = management_request(h.context, preview["owner_id"], ADOPT, adoption_scope(preview), "no-permission", "denied")
    with pytest.raises(ExecutionError) as error:
        client.apply_reconciliation(unauth)
    assert error.value.code == "MANAGEMENT_GRANT_REQUIRED"
    assert inventory(Path(h.context.root)) == before
    request = permit(h, owner, ADOPT, adoption_scope(preview), "adopt-original")
    if lose_response:
        waiting = h.spawn("client", operation="apply_reconciliation", arguments={"request": request})
        owner.reached("management:before_response")
        receipt = client.management_receipt(ADOPT, "adopt-original")
        waiting.terminate()
        owner.release("management:before_response")
        replay = client.apply_reconciliation(request)
        assert replay["replayed"] and replay["receipt"] == receipt
    else:
        receipt = client.apply_reconciliation(request)["receipt"]
    assert client.receipt("key-0") == accepted
    assert client.run(run_id)["execution"] == "FINISHED"
    assert client.dispatch_gate()["state"] == "PAUSED"
    assert client.run(pending["run_id"])["queue_state"] == "PENDING"
    assert len(client.reconciliations(run_id)) == 1
    assert artifact.read_bytes() == original_bytes and artifact.stat().st_mtime_ns == original_mtime
    assert len(list(Path(h.context.runtime_root).rglob("result.json"))) == 1
    resume_request = permit(h, owner, RESUME, {"expected_gate_version": client.dispatch_gate()["version"]}, "resume-explicit")
    resume_receipt = client.resume_dispatch(resume_request)["receipt"]
    h.finished(pending["run_id"])
    events = client.events()
    assert len([e for e in events if e["run_id"] == run_id and e["type"] == "START_INTENT"]) == 1
    assert len(list(Path(h.context.runtime_root).rglob("result.json"))) == 2
    # Reboot after a committed resume: old receipt is queryable but never reopens.
    (owner.control / "stop.json").write_text("{}", encoding="utf-8")
    assert owner.process.wait(timeout=8) == 0
    h.owner(management_control=True)
    current = h.client()
    assert current.dispatch_gate()["state"] == "PAUSED"
    assert current.resume_dispatch(resume_request)["receipt"] == resume_receipt
    assert current.dispatch_gate()["state"] == "PAUSED"
    (h.root / "demonstration.json").write_text(canonical_json({"original_submission": accepted,
        "reconciliation": receipt, "resume": resume_receipt, "final_gate": current.dispatch_gate(),
        "old_run": current.run(run_id), "pending_then_finished": current.run(pending["run_id"]),
        "events": current.events(), "reconciliation_records": current.reconciliations(run_id)}), encoding="utf-8")


def test_owner_restart_invalidates_old_preview_and_management_permission(processes):
    h = processes
    first = h.owner(barriers=["dispatch:after_artifact"])
    run_id = h.client().submit(h.requests[0])["receipt"]["run_id"]
    first.reached("dispatch:after_artifact")
    first.terminate()
    second = h.owner(management_control=True)
    preview = h.client().preview_reconciliation(run_id)
    old = permit(h, second, ADOPT, adoption_scope(preview), "owner-bound")
    (second.control / "stop.json").write_text("{}", encoding="utf-8")
    assert second.process.wait(timeout=8) == 0
    h.owner(management_control=True)
    before = inventory(Path(h.context.root))
    with pytest.raises(ExecutionError) as error:
        h.client().apply_reconciliation(old)
    assert error.value.code == "STALE_OWNER"
    assert inventory(Path(h.context.root)) == before
