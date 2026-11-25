"""Persistent non-executable rod lifecycle qualification, not an execution issuer.

Uses the existing inert public product and management receipts. Historical Plans,
fixed Standard dispatch and Store schemas are unchanged. No caller declaration
can qualify the protected Operator, host, real Grant or actual dispatch.
"""

import json

from .models import canonical_json, digest, fields, integer, require
from .paths import confined
from .rod_profile import _label
from .rod_review import _writer

SCHEMA = "af-rod-execution-readiness-v1"
REQUEST_SCHEMA = "af-rod-nonexecutable-submit-request-v1"


def _empty_output(product, plan):
    for key in ("output_path",):
        path = confined(product.context.test_root, plan[key], exists=True)
        require(
            path.is_dir() and not any(path.iterdir()),
            "OUTPUT_OCCUPIED",
            "Candidate output must be empty before a prospective request",
        )


def _plan(product, expected, at_time):
    require(type(expected) is dict, "INVALID_REQUEST", "Exact Plan reference required")
    actual = product.inspect(
        expected["plan_id"], expected["plan_digest"], at_time=at_time
    )
    require(
        actual == expected and actual["phase"] == "A",
        "PLAN_STALE",
        "Frozen A reference must match persisted input and policy",
    )
    return actual


def _namespace(product, plan_id):
    return canonical_json(
        [product.context.project_instance_id, "rod_g3_request", plan_id]
    )


def prepare_request(
    product,
    plan_ref,
    *,
    request_key,
    not_before,
    expires_at,
    budget_reservation,
    at_time,
):
    """Persist one exact, inert submit identity. Does not reserve research budget.

    The referenced reservation is a causal identifier only; GD-CAE remains the
    budget authority. A PAUSED inert Project is expected and is never resumed.
    """
    _label(request_key)
    _label(budget_reservation)
    for value in (not_before, expires_at, at_time):
        integer(value, 1)
    plan = _plan(product, plan_ref, at_time)
    require(
        not_before < expires_at <= plan["expires_at"]
        and expires_at - not_before <= 600,
        "REQUEST_EXPIRED",
        "Short prospective request window required",
    )
    _empty_output(product, plan)
    request = {
        "schema": REQUEST_SCHEMA,
        "scope": "OFFLINE_NON_EXECUTABLE",
        "project_id": plan["project_id"],
        "project_instance_id": plan["project_instance_id"],
        "plan_ref": plan,
        "plan_ref_digest": digest(plan),
        "request_key": request_key,
        "not_before": not_before,
        "expires_at": expires_at,
        "budget_reservation": budget_reservation,
        "max_uses": 1,
        "real_execution_authorized": False,
    }
    request["request_digest"] = digest(request)
    namespace = _namespace(product, plan["plan_id"])
    with _writer(product) as store:
        # Hold the existing preparation lease while rechecking external input.
        _plan(product, plan, at_time)
        _empty_output(product, plan)
        with store.transaction("rod_g3_prepare_request") as conn:
            prior = conn.execute(
                "SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?",
                (namespace, request_key),
            ).fetchone()
            if prior:
                require(
                    prior[0] == request["request_digest"]
                    and prior[1] == canonical_json(request),
                    "IDEMPOTENCY_CONFLICT",
                    "Prospective identity cannot change",
                )
                return request
            require(
                at_time <= not_before and expires_at <= at_time + 600,
                "REQUEST_EXPIRED",
                "A new identity requires a current short future window",
            )
            require(
                conn.execute(
                    "SELECT COUNT(*) FROM management_receipts WHERE namespace=?",
                    (namespace,),
                ).fetchone()[0]
                == 0,
                "REQUEST_ALREADY_FROZEN",
                "One prospective identity per candidate",
            )
            require(
                conn.execute("SELECT run_id FROM slot WHERE id=1").fetchone()[0]
                is None,
                "SLOT_BUSY",
                "No active execution slot permitted",
            )
            conn.execute(
                "INSERT INTO management_receipts VALUES(?,?,?,?,?)",
                (
                    namespace,
                    request_key,
                    request["request_digest"],
                    request_key,
                    canonical_json(request),
                ),
            )
            conn.execute(
                "INSERT INTO control_events(body) VALUES(?)", (canonical_json(request),)
            )
        store._checkpoint("rod_g3_prepare_request:after_commit")
    return request


def inspect_request(product, plan_ref, request_key, *, at_time):
    """Read exact original identity after disconnect or lost preparation reply."""
    integer(at_time, 1)
    _label(request_key)
    plan = _plan(product, plan_ref, at_time)
    with product._reader().store.read() as conn:
        row = conn.execute(
            "SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?",
            (_namespace(product, plan["plan_id"]), request_key),
        ).fetchone()
    require(
        row is not None and len(row[1]) <= 32768,
        "REQUEST_UNKNOWN",
        "Query original key; do not replace unknown identity",
    )
    request = json.loads(row[1])
    fields(
        request,
        (
            "schema",
            "scope",
            "project_id",
            "project_instance_id",
            "plan_ref",
            "plan_ref_digest",
            "request_key",
            "not_before",
            "expires_at",
            "budget_reservation",
            "max_uses",
            "real_execution_authorized",
            "request_digest",
        ),
    )
    original = dict(request)
    claimed = original.pop("request_digest")
    require(
        request["schema"] == REQUEST_SCHEMA
        and request["scope"] == "OFFLINE_NON_EXECUTABLE"
        and row[0] == claimed == digest(original)
        and request["plan_ref"] == plan
        and request["plan_ref_digest"] == digest(plan)
        and request["request_key"] == request_key
        and all(request[k] == plan[k] for k in ("project_id", "project_instance_id"))
        and type(request["max_uses"]) is int
        and request["max_uses"] == 1
        and request["real_execution_authorized"] is False,
        "REQUEST_CORRUPT",
        "Committed request must retain its exact immutable scope",
    )
    integer(request["not_before"], 1)
    integer(request["expires_at"], 1)
    _label(request["budget_reservation"])
    require(
        request["not_before"] < request["expires_at"] <= plan["expires_at"]
        and request["expires_at"] - request["not_before"] <= 600,
        "REQUEST_CORRUPT",
        "Committed time window contradicts Plan",
    )
    return request


def qualify_request(product, plan_ref, request_key, *, at_time):
    request = inspect_request(product, plan_ref, request_key, at_time=at_time)
    require(
        request["not_before"] <= at_time < request["expires_at"],
        "REQUEST_EXPIRED",
        "Prospective request is not currently valid",
    )
    _empty_output(product, plan_ref)
    return {
        "schema": SCHEMA,
        "request_digest": request["request_digest"],
        "plan_ref_digest": request["plan_ref_digest"],
        "CAN_PREPARE_REAL_PLAN_OFFLINE": "PASS_OFFLINE",
        "REAL_GRANT_ISSUANCE_QUALIFIED": "BLOCKED",
        "REAL_STANDARD_DISPATCH_QUALIFIED": "BLOCKED",
        "protected_operator": "PENDING_PROTECTED_OPERATOR",
        "dynamic_backend": "BLOCKED_CORE_EXTENSION",
        "host_qualification": "NOT_TESTED",
        "dispatch_gate": "PAUSED",
        "execution_authorized": False,
        "grant_id": None,
    }


def predispatch(product, plan_ref, request_key, *, submitted, at_time):
    """Deterministic refusal for an exact prospective request; never sends IPC.

    No configurable enable flag, caller-provided authentication status, token,
    fake Grant conversion, resumed gate, launcher or real-Grant issuer exists.
    """
    fields(
        submitted,
        (
            "project_id",
            "project_instance_id",
            "plan_id",
            "plan_digest",
            "request_key",
            "request_digest",
            "acceptance_state",
        ),
    )
    require(
        submitted["acceptance_state"] == "NOT_SUBMITTED",
        "ACCEPTANCE_UNKNOWN",
        "Unknown or accepted requests require original-key reconciliation",
    )
    request = inspect_request(product, plan_ref, request_key, at_time=at_time)
    require(
        all(
            submitted[k] == plan_ref[k]
            for k in ("project_id", "project_instance_id", "plan_id", "plan_digest")
        )
        and submitted["request_key"] == request_key
        and submitted["request_digest"] == request["request_digest"],
        "REQUEST_SCOPE_MISMATCH",
        "Exact prospective submission scope required",
    )
    qualify_request(product, plan_ref, request_key, at_time=at_time)
    require(
        False,
        "PENDING_PROTECTED_OPERATOR",
        "Protected Operator, dynamic backend and actual host qualification absent",
    )
