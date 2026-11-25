"""Persistent exact approval requests and TEST_ONLY canary review decisions.

No real Grant or task execution API. Possession of this same-user Python class
does not establish Operator isolation or actual human consent.
"""

from contextlib import contextmanager
import hmac
import json
import re

from .models import canonical_json, digest, fields, integer, require
from .rod_profile import _label
from .standard_contract import INPUT_DIGEST
from .store import acquire_initial_preparation_store
from ..service_lifecycle import ServiceLifecycleManager

SCHEMA = "af-rod-approval-request-v1"
REAL_PREFLIGHT_SCHEMA = "af-real-rod-preflight-review-request-v1"


def _current_ref(product, plan_ref, at_time, config, expected_contract):
    if plan_ref.get("schema") == "af-real-rod-plan-review-v1":
        require(config is not None and expected_contract is not None,
                "APPROVAL_SCOPE_MISMATCH", "Exact real preflight context required")
        return product.review_real_plan(
            plan_ref["plan_id"], plan_ref["plan_digest"], config=config,
            expected_contract=expected_contract, at_time=at_time)
    require(config is None and expected_contract is None,
            "APPROVAL_SCOPE_MISMATCH", "Do not mix old inert and real preflight reviews")
    return product.inspect(plan_ref["plan_id"], plan_ref["plan_digest"], at_time=at_time)


def _sha(value):
    require(
        type(value) is str and re.fullmatch(r"sha256:[a-f0-9]{64}", value),
        "INVALID_REQUEST",
        "SHA-256 content reference required",
    )
    return value


@contextmanager
def _writer(product):
    manager = ServiceLifecycleManager(product.directory)
    profile = manager._profile()
    store = acquire_initial_preparation_store(
        product.context, profile["authority_instance"]
    )
    try:
        yield store
    finally:
        store.close()


def request_approval(
    product,
    plan_ref,
    *,
    goal_digest,
    model_digest,
    nonce,
    not_before,
    expires_at,
    budget_remaining,
    at_time,
    config=None,
    expected_contract=None,
):
    """Persist one non-executable review request; never produces an authorization.

    In v1 goal_digest names the frozen combined rod contract bundle, exactly the
    Plan's contract_digest. model_digest names the fixed input template bytes.
    """
    _sha(goal_digest)
    _sha(model_digest)
    _label(nonce)
    for value in (not_before, expires_at, budget_remaining, at_time):
        integer(value)
    require(
        budget_remaining in (1, 2),
        "BUDGET_EXHAUSTED",
        "A remaining global allocation is required",
    )
    require(
        at_time
        <= not_before
        < expires_at
        <= min(plan_ref["expires_at"], at_time + 600),
        "APPROVAL_EXPIRED",
        "Exact short validity window required",
    )
    require(
        _current_ref(product, plan_ref, at_time, config, expected_contract) == plan_ref,
        "PLAN_STALE",
        "Exact current PlanRef required",
    )
    require(
        goal_digest == plan_ref["contract_digest"] and model_digest == INPUT_DIGEST,
        "APPROVAL_SCOPE_MISMATCH",
        "Goal bundle and frozen rod baseline must match the exact Plan",
    )
    real_preflight = plan_ref.get("schema") == "af-real-rod-plan-review-v1"
    request = {
        "schema": REAL_PREFLIGHT_SCHEMA if real_preflight else SCHEMA,
        "source": "REAL_ROD_PREFLIGHT_REVIEW_REQUEST" if real_preflight
        else "INERT_ROD_APPROVAL_REQUEST",
        "plan_ref": plan_ref,
        "plan_ref_digest": digest(plan_ref),
        "goal_digest": goal_digest,
        "model_digest": model_digest,
        "candidate_id": plan_ref["candidate_id"],
        "input_digest": plan_ref["input_digest"],
        "load_n": plan_ref["load_n"],
        "resources": plan_ref["resources"],
        "input_path": plan_ref["input_path"],
        "output_path": plan_ref["output_path"],
        "max_uses": 1,
        "nonce": nonce,
        "not_before": not_before,
        "expires_at": expires_at,
        "budget_remaining_at_request": budget_remaining,
        "decision_options": ["APPROVE", "DENY"],
        "real_execution_authorized": False,
        "human_consent": "NOT_OBTAINED",
    }
    request["request_digest"] = digest(request)
    namespace = canonical_json(
        [product.context.project_instance_id, "rod_review_request", plan_ref["plan_id"]]
    )
    with _writer(product) as store:
        with store.transaction("rod_review_request") as conn:
            row = conn.execute(
                "SELECT body FROM management_receipts WHERE namespace=? LIMIT 1",
                (namespace,),
            ).fetchone()
            if row:
                require(
                    row[0] == canonical_json(request),
                    "APPROVAL_REQUEST_FINAL",
                    "Plan already has its immutable approval request",
                )
                return json.loads(row[0])
            conn.execute(
                "INSERT INTO management_receipts VALUES(?,?,?,?,?)",
                (
                    namespace,
                    nonce,
                    request["request_digest"],
                    "rod_request_" + request["request_digest"][7:39],
                    canonical_json(request),
                ),
            )
            conn.execute(
                "INSERT INTO control_events(body) VALUES(?)", (canonical_json(request),)
            )
    return request


class CanaryReviewControl:
    """Trusted TEST_ONLY constructor; same-user code/token protection NOT VERIFIED."""

    def __init__(self, *, operator_digest, subject):
        self.operator_digest = _sha(operator_digest)
        self.subject = _label(subject)

    def decide(
        self,
        product,
        request,
        *,
        decision,
        operator_token,
        subject,
        operation_key,
        at_time,
        config=None,
        expected_contract=None,
    ):
        _label(subject)
        _label(operation_key)
        integer(at_time)
        require(
            type(operator_token) is str
            and len(operator_token) <= 256
            and subject == self.subject
            and hmac.compare_digest(digest(operator_token), self.operator_digest),
            "TEST_OPERATOR_REQUIRED",
            "Exact canary capability and subject required",
        )
        require(
            decision in {"APPROVE", "DENY"},
            "INVALID_REQUEST",
            "Explicit final canary decision required",
        )
        fields(
            request,
            (
                "schema",
                "source",
                "plan_ref",
                "plan_ref_digest",
                "goal_digest",
                "model_digest",
                "candidate_id",
                "input_digest",
                "load_n",
                "resources",
                "input_path",
                "output_path",
                "max_uses",
                "nonce",
                "not_before",
                "expires_at",
                "budget_remaining_at_request",
                "decision_options",
                "real_execution_authorized",
                "human_consent",
                "request_digest",
            ),
        )
        require(
            request["request_digest"]
            == digest({k: v for k, v in request.items() if k != "request_digest"}),
            "APPROVAL_SCOPE_MISMATCH",
            "Approval request content differs",
        )
        plan = request["plan_ref"]
        real_preflight = plan.get("schema") == "af-real-rod-plan-review-v1"
        require(
            request["schema"] == (REAL_PREFLIGHT_SCHEMA if real_preflight else SCHEMA)
            and request["source"] == ("REAL_ROD_PREFLIGHT_REVIEW_REQUEST" if real_preflight
                                      else "INERT_ROD_APPROVAL_REQUEST")
            and request["plan_ref_digest"] == digest(plan)
            and request["goal_digest"] == plan["contract_digest"]
            and request["model_digest"] == INPUT_DIGEST
            and request["max_uses"] == 1
            and type(request["max_uses"]) is int
                and type(request["budget_remaining_at_request"]) is int
                and request["budget_remaining_at_request"] in (1, 2)
            and request["real_execution_authorized"] is False
            and request["human_consent"] == "NOT_OBTAINED"
            and request["decision_options"] == ["APPROVE", "DENY"]
            and all(
                request[key] == plan[key]
                for key in (
                    "candidate_id",
                    "input_digest",
                    "load_n",
                    "resources",
                    "input_path",
                    "output_path",
                )
            ),
            "APPROVAL_SCOPE_MISMATCH",
            "Committed request contradicts its frozen Plan or model",
        )
        require(
            _current_ref(product, plan, min(at_time, request["expires_at"] - 1),
                         config, expected_contract) == plan,
            "PLAN_STALE",
            "Current input or exact Plan differs",
        )
        namespace = canonical_json(
            [product.context.project_instance_id, "rod_review_request", plan["plan_id"]]
        )
        final_ns = canonical_json(
            [
                product.context.project_instance_id,
                "rod_review_decision",
                plan["plan_id"],
            ]
        )
        fingerprint = digest(
            {
                "request_digest": request["request_digest"],
                "decision": decision,
                "subject": subject,
                "operation_key": operation_key,
            }
        )
        with _writer(product) as store:
            with store.transaction("rod_review_decision") as conn:
                original = conn.execute(
                    "SELECT body FROM management_receipts WHERE namespace=? LIMIT 1",
                    (namespace,),
                ).fetchone()
                require(
                    original is not None and original[0] == canonical_json(request),
                    "APPROVAL_SCOPE_MISMATCH",
                    "Original committed immutable request required",
                )
                prior = conn.execute(
                    "SELECT key,request_digest,body FROM management_receipts WHERE namespace=? LIMIT 1",
                    (final_ns,),
                ).fetchone()
                if prior:
                    require(
                        prior[0] == operation_key and prior[1] == fingerprint,
                        "REVIEW_FINAL",
                        "Cannot change key or decision after a final review",
                    )
                    return {"replayed": True, "decision": json.loads(prior[2])}
                outcome = (
                    decision
                    if request["not_before"] <= at_time < request["expires_at"]
                    else "EXPIRED"
                )
                result = {
                    "schema": "af-rod-canary-review-v1",
                    "source": "TEST_ONLY_CANARY",
                    "request_digest": request["request_digest"],
                    "plan_digest": plan["plan_digest"],
                    "input_digest": request["input_digest"],
                    "subject": subject,
                    "decision": outcome,
                    "recorded_at": at_time,
                    "grant_id": None,
                    "real_execution_authorized": False,
                    "human_consent": "NOT_OBTAINED",
                    "hil_enforcement": "NOT_VERIFIED",
                }
                conn.execute(
                    "INSERT INTO management_receipts VALUES(?,?,?,?,?)",
                    (
                        final_ns,
                        operation_key,
                        fingerprint,
                        "rod_decision_" + fingerprint[7:39],
                        canonical_json(result),
                    ),
                )
                conn.execute(
                    "INSERT INTO control_events(body) VALUES(?)",
                    (canonical_json(result),),
                )
        return {"replayed": False, "decision": result}
