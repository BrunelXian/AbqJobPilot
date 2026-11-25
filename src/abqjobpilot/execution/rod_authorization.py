"""Local TEST_ONLY operator review seam, never registered in ordinary client RPC.

Uses the existing trusted TEST_ONLY issuer/validator and existing receipt tables.
No real grants, launches or schema migration. This verifies interface separation,
NOT human identity or same-Windows-user isolation. OS isolation remains blocked.
"""
import hmac
import json

from .models import canonical_json, digest, fields, identifier, integer, now, require, text
from .store import document
from .test_authority import _issue_process_execution


class TestOnlyReviewControl:
    __test__ = False

    def __init__(self, *, plan_id, plan_digest, operator_digest):
        for value in (plan_id, plan_digest, operator_digest):
            text(value)
        self.plan_id = plan_id
        self.plan_digest = plan_digest
        self.operator_digest = operator_digest

    def invoke(self, service, request):
        fields(request, ("operation_key", "operator_token", "project_id", "project_instance_id",
                         "owner_id", "plan_id", "plan_digest", "decision", "expires_at"))
        for key in request:
            if key != "expires_at":
                text(request[key])
        integer(request["expires_at"])
        require(hmac.compare_digest(digest(request["operator_token"]), self.operator_digest),
                "TEST_OPERATOR_REQUIRED", "Ordinary client permission cannot approve")
        require(request["decision"] in ("APPROVE", "DENY"), "INVALID_REQUEST", "Explicit review required")
        context = service.context
        service._context(context)
        require(request["project_id"] == context.project_id
                and request["project_instance_id"] == context.project_instance_id
                and request["owner_id"] == service.store._session.owner_id,
                "PROJECT_IDENTITY_MISMATCH", "Exact active owner and project required")
        require(request["plan_id"] == self.plan_id and request["plan_digest"] == self.plan_digest,
                "GRANT_SCOPE_MISMATCH", "Exact operator-provisioned Plan required")
        fingerprint = digest({k: v for k, v in request.items() if k != "operator_token"})
        namespace = canonical_json([context.project_instance_id, "rod_test_review", self.plan_id])
        store = service.store
        with store.transaction("rod_test_review") as conn:
            prior = conn.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?",
                                 (namespace, request["operation_key"])).fetchone()
            if prior:
                require(prior[0] == fingerprint, "IDEMPOTENCY_CONFLICT", "Review key content differs")
                return {"replayed": True, "receipt": json.loads(prior[1])}
            require(conn.execute("SELECT COUNT(*) FROM management_receipts WHERE namespace=?", (namespace,)).fetchone()[0] == 0,
                    "REVIEW_FINAL", "Plan already received its one final review")
            plan = document(conn, "plans", "plan_id", self.plan_id)
            require(plan["backend_id"] == "python-process-fixture-v1"
                    and plan["plan_digest"] == self.plan_digest
                    and digest({k: v for k, v in plan.items() if k != "plan_digest"}) == self.plan_digest,
                    "TEST_GRANT_ONLY", "Only an exact existing TEST_ONLY process Plan may be reviewed")
            require(conn.execute("SELECT state FROM dispatch_gate WHERE id=1").fetchone()[0] == "PAUSED"
                    and conn.execute("SELECT run_id FROM slot WHERE id=1").fetchone()[0] is None,
                    "DISPATCH_POLICY_MISMATCH", "Idle PAUSED owner required")
            require(conn.execute("SELECT COUNT(*) FROM grants WHERE plan_id=?", (self.plan_id,)).fetchone()[0] == 0,
                    "GRANT_CONSUMED", "No previous authorization may exist")
            require(now() < request["expires_at"] <= min(plan["expires_at"], now() + 600),
                    "GRANT_EXPIRED", "Exact bounded review validity required")
            from .planning import check_plan
            configuration = json.loads(conn.execute("SELECT body FROM configuration WHERE id=1").fetchone()[0])
            check_plan(context, plan, configuration, process_binding=plan["process_fixture"])
            # Existing trusted issuer validates the fixed process configuration.
            grant_id = None
            if request["decision"] == "APPROVE":
                grant_id = _issue_process_execution(service, conn, self.plan_id,
                                                    expires_at=request["expires_at"])
            receipt = {"operation_id": identifier("op"), "scope": "TEST_ONLY",
                       "decision": request["decision"], "plan_id": self.plan_id,
                       "plan_digest": self.plan_digest, "grant_id": grant_id,
                       "project_id": context.project_id, "project_instance_id": context.project_instance_id,
                       "recorded_at": now(), "real_execution_authorized": False,
                       "human_identity": "NOT_ESTABLISHED", "os_isolation": "NOT_ESTABLISHED",
                       "input_manifest_digest": digest(plan["input_manifest"]),
                       "resources_digest": digest(plan["resources"])}
            conn.execute("INSERT INTO management_receipts VALUES(?,?,?,?,?)",
                         (namespace, request["operation_key"], fingerprint, receipt["operation_id"], canonical_json(receipt)))
            conn.execute("INSERT INTO control_events(body) VALUES(?)", (canonical_json(receipt),))
        store._checkpoint("rod_test_review:after_commit")
        return {"replayed": False, "receipt": receipt}
