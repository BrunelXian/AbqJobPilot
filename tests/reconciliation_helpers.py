"""TEST_ONLY management issuance. Requires the actual live owner's Store."""

from abqjobpilot.execution.models import canonical_json, identifier, now
from abqjobpilot.execution.reconciliation import ADOPT, MANAGEMENT_CONTRACT, RESUME


class FakeManagementFixture:
    def __init__(self, store):
        self.store = store

    def issue(self, issued_action, issued_scope, **overrides):
        ctx, session = self.store.context, self.store._session
        value = {"grant_id": identifier("mg"), "issuer": "FakeManagementFixture",
                 "grant_kind": "TEST_ONLY_MANAGEMENT", "authority_instance": session.authority_instance,
                 "project_instance_id": ctx.project_instance_id, "context_digest": ctx.context_digest,
                 "owner_id": session.owner_id, "action": issued_action, "scope": issued_scope,
                 "expires_at": now() + 3600, "max_uses": 1}
        value.update(overrides)
        with self.store.transaction("fixture_management_grant") as connection:
            connection.execute("INSERT INTO management_grants VALUES(?,?)", (value["grant_id"], canonical_json(value)))
        return value["grant_id"]


def management_request(context, owner_id, action, scope, grant_id, key):
    return {"contract_version": MANAGEMENT_CONTRACT, "operation": action, "project_id": context.project_id,
            "project_instance_id": context.project_instance_id, "owner_id": owner_id,
            "management_grant_id": grant_id, "idempotency_key": key, **scope}


def adoption_scope(preview):
    return {"run_id": preview["run_id"], "expected_run_revision": preview["run_revision"],
            "preview_digest": preview["preview_digest"]}
