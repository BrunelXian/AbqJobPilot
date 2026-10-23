import json
from pathlib import Path

import pytest

from abqjobpilot.execution import ExecutionError
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.diagnostics import report_bytes
from abqjobpilot.execution.models import canonical_json, identifier
from abqjobpilot.execution.protocol import MAX_REQUEST, MAX_RESPONSE, PROTOCOL, connect, receive, send
from abqjobpilot.execution.reconciliation import ADOPT, RESUME
from execution_helpers import inventory
from reconciliation_helpers import adoption_scope
from supervisor_helpers import processes
from test_reconciliation_supervisor import permit


def reasons(report):
    return {item["reason_code"] for item in report["body"]["diagnostics"]}


def test_windows_three_stage_diagnostic_export_and_detached_response(processes):
    h = processes
    first = h.owner(barriers=["dispatch:after_artifact"])
    original = h.client().submit(h.requests[0])["receipt"]
    run_id = original["run_id"]
    first.reached("dispatch:after_artifact")
    pending = h.client().submit(h.requests[1])["receipt"]
    artifact = Path(h.context.runtime_root) / "fake_runs" / run_id / "result.json"
    original_bytes = artifact.read_bytes()
    first.terminate()
    owner = h.owner(management_control=True, barriers=["diagnostic:before_response"])
    initial_inventory = inventory(Path(h.context.root))
    waiting = h.spawn("client", operation="diagnose", arguments={"run_id": run_id})
    owner.reached("diagnostic:before_response")
    assert inventory(Path(h.context.root)) == initial_inventory
    # The diagnostic DB transaction is gone even while its transport is blocked.
    client = h.client()
    preview = client.preview_reconciliation(run_id)
    client.apply_reconciliation(permit(h, owner, ADOPT, adoption_scope(preview), "r5-adopt"))
    owner.release("diagnostic:before_response")
    before = waiting.result()
    assert waiting.process.wait(timeout=8) == 0
    assert {"EXECUTION_UNCERTAIN", "EVIDENCE_INSUFFICIENT", "DISPATCH_PAUSED"} <= reasons(before)
    assert "EXPLICITLY_RECONCILED" not in reasons(before)
    after_adoption_inventory = inventory(Path(h.context.root))
    adopted = client.diagnose(run_id)
    assert inventory(Path(h.context.root)) == after_adoption_inventory
    assert {"EXPLICITLY_RECONCILED", "DISPATCH_PAUSED"} <= reasons(adopted)
    assert "EXECUTION_UNCERTAIN" not in reasons(adopted)
    assert client.run(pending["run_id"])["queue_state"] == "PENDING"
    client.resume_dispatch(permit(h, owner, RESUME, {"expected_gate_version": client.dispatch_gate()["version"]}, "r5-resume"))
    h.finished(pending["run_id"])
    after_resume_inventory = inventory(Path(h.context.root))
    resumed = client.diagnose(run_id)
    assert inventory(Path(h.context.root)) == after_resume_inventory
    assert "DISPATCH_PAUSED" not in reasons(resumed)
    assert resumed["body"]["facts"]["dispatch_gate"]["state"] == "OPEN"
    assert before["body"]["facts"]["receipt"] == adopted["body"]["facts"]["receipt"] == resumed["body"]["facts"]["receipt"]
    assert artifact.read_bytes() == original_bytes
    assert len([e for e in client.events() if e["run_id"] == run_id and e["type"] == "START_INTENT"]) == 1
    exports = h.root / "audit_exports"
    exports.mkdir()
    for name, report in (("01_uncertain", before), ("02_reconciled_paused", adopted), ("03_resumed", resumed)):
        client.export_diagnostic(report, export_root=exports, target=exports / (name + ".json"))
        content = (exports / (name + ".json")).read_bytes()
        assert content == report_bytes(report)
        assert h.credential.encode() not in content
        assert str(h.root).encode() not in content
        assert b"grant_id" not in content and b"authority_instance" not in content
    assert inventory(Path(h.context.root)) == after_resume_inventory
    (h.root / "diagnostic-demonstration.json").write_text(canonical_json({"run_id": run_id,
        "reports": ["01_uncertain.json", "02_reconciled_paused.json", "03_resumed.json"],
        "digests": [r["content_digest"] for r in (before, adopted, resumed)],
        "original_effect_count": 1, "explicit_control_operations": ["apply_reconciliation", "resume_dispatch"]}), encoding="utf-8")


def test_authenticated_bound_diagnostic_rejects_dangerous_parameters_and_echo(processes):
    h = processes
    owner = h.owner(barriers=["dispatch:after_artifact"])
    run_id = h.client().submit(h.requests[0])["receipt"]["run_id"]
    owner.reached("dispatch:after_artifact")
    baseline = inventory(Path(h.context.root))
    for change, expected in (("credential", "AUTHENTICATION_FAILED"), ("project", "ENDPOINT_IDENTITY_MISMATCH"),
                             ("extra", "INVALID_REQUEST"), ("run", "INVALID_REQUEST")):
        client = h.client()
        if change == "credential": client._credential = "R5_SECRET_bad_credential"
        if change == "project": client.endpoint["project_id"] = "R5_SECRET_wrong_Project"
        arguments = {"run_id": run_id}
        if change == "extra": arguments["export_path"] = "C:/R5_SECRET_do_not_access"
        if change == "run": arguments["run_id"] = "R5_SECRET_no_run"
        with pytest.raises(ExecutionError) as error: client.call("diagnose", arguments)
        assert error.value.code == expected and "R5_SECRET" not in str(error.value)
    client = h.client()
    request = {"protocol": PROTOCOL, "request_id": h.credential, "credential": h.credential,
               **{k: client.endpoint[k] for k in ("project_id", "project_instance_id", "context_digest", "owner_id")},
               "operation": "diagnose", "arguments": {"run_id": run_id}}
    with connect(client.endpoint["port"]) as stream:
        send(stream, request, MAX_REQUEST)
        response = receive(stream, MAX_RESPONSE)
    assert not response["ok"] and response["request_id"] is None
    assert h.credential not in canonical_json(response)
    assert inventory(Path(h.context.root)) == baseline
