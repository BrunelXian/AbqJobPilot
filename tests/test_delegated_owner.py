from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import secrets

import pytest

from abqjobpilot.execution import ExecutionError, open_existing_read_only
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.models import canonical_json
from execution_helpers import inventory
from supervisor_helpers import ProcessHarness
from test_delegated_grant import approve, make_harness, prepare


class DelegatedOwnerHarness(ProcessHarness):
    def __init__(self, root, provision=None, *, odb_fixture_test_only=False):
        self.root, self.children, self.process_config = root, [], None
        h = make_harness(root, odb_fixture_test_only=odb_fixture_test_only)
        self.context = h.context
        try:
            plan = prepare(h)
            self.grant_id = approve(h, plan)["grant_id"]
            self.requests = [h.request(plan, self.grant_id, f"key-{index}") for index in range(2)]
            if provision is not None:
                self.provisioned = provision(h, plan)
            self.credential = secrets.token_hex(32)
            self.bootstrap = root / "private-bootstrap.json"
            self.endpoint_file = root / "endpoint.json"
            self.bootstrap.write_text(canonical_json({
                "context": self.context.to_dict(), "authority_instance": h.store._session.authority_instance,
                "credential": self.credential, "client_namespace": h.service.client_namespace,
                "endpoint_file": str(self.endpoint_file),
            }), encoding="utf-8")
        finally:
            h.store.close()
        self.recent = inventory(root)["recent-fixture.json"]


def test_lost_reply_and_killed_owner_leave_same_receipt_and_budget(tmp_path):
    h = DelegatedOwnerHarness(tmp_path)
    try:
        owner = h.owner(barriers=["submit:before_response"])
        client = h.client()
        with pytest.raises(ExecutionError) as error:
            FakeClient(client.endpoint, "wrong-credential").submit(h.requests[0])
        assert error.value.code == "AUTHENTICATION_FAILED"
        for operation in ("issue_delegated_fake", "revoke_delegated_fake"):
            with pytest.raises(ExecutionError) as error:
                client.call(operation, {})
            assert error.value.code == "UNKNOWN_OPERATION"
        reader = open_existing_read_only(h.context)
        assert reader.delegated_budget(h.context, h.grant_id)["consumed"] == 0
        with ThreadPoolExecutor(max_workers=1) as executor:
            lost = executor.submit(client.submit, h.requests[0])
            owner.reached("submit:before_response")
            receipt = client.receipt("key-0")
            original = client.run(receipt["run_id"])
            before = reader.delegated_budget(h.context, h.grant_id)
            assert before["run_ids"] == [receipt["run_id"]] and before["remaining"] == 1
            owner.terminate()  # The kernel-verified test Owner, while the committed reply is withheld.
            with pytest.raises(ExecutionError) as error:
                lost.result(timeout=8)
            assert error.value.code == "ACCEPTANCE_UNKNOWN"
        h.owner()
        restarted = h.client()
        assert restarted.endpoint["owner_id"] != client.endpoint["owner_id"]
        assert not restarted.health()["dispatch_enabled"]
        assert restarted.receipt("key-0") == receipt
        assert restarted.submit(h.requests[0])["receipt"] == receipt
        assert restarted.run(receipt["run_id"]) == original
        assert [e["type"] for e in restarted.events()] == ["REQUEST_ACCEPTED"]
        with pytest.raises(ExecutionError) as error:
            restarted.submit(h.requests[1])
        assert error.value.code == "DISPATCH_PAUSED"
        assert reader.delegated_budget(h.context, h.grant_id) == before
        assert not list(Path(h.context.runtime_root).rglob("*"))
    finally:
        h.close()
