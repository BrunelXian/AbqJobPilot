"""Dynamic rod dispatch specification compiler; live routing is closed.

The owner-side adapter can reuse the exact versioned command/resources and
independent candidate checks without redirecting a dynamic input through the
legacy fixed-input collector. No command is executed or persisted here.
"""

from .models import bytes_digest, digest, fields, integer, require
from .rod_plan_adapter import BACKEND
from .rod_profile import check_candidate
from .rod_real_source import qualify_real_plan, validate_plan_projection
from .rod_review import _sha
from .standard_contract import RESOURCES

SCHEMA = "af-rod-standard-dispatch-spec-v1"
ACTION = "execute_axial_rod_cload_once"


def compile_dispatch_spec(product, plan_ref, request_key, *, at_time):
    """Compile reproducible single-use prospective arguments from committed data.

    Does not insert another Plan, claim an attempt, consume a Grant, update the
    PAUSED gate or call a runner. Existing input and output checks run again.
    """
    qualification = qualify_real_plan(product, plan_ref, request_key, at_time=at_time)
    plan = qualification["plan"]
    # No caller-controlled command, job name, filenames, resources or flags.
    # Fixed physical DAT leaf agrees with the wire contract. Distinct immutable
    # candidate output directories, not a caller-selected job name, own identity.
    job_name = "axial_rod"
    spec = {
        "schema": SCHEMA, "backend_id": BACKEND, "action": ACTION,
        "plan": plan, "request_digest": qualification["request_digest"],
        "job_name": job_name, "input_filename": "axial_bar.inp",
        "dat_filename": job_name + ".dat", "resources": dict(RESOURCES),
        "arguments": ["job=" + job_name, "input=axial_bar.inp", "analysis", "interactive",
                      "cpus=1", "gpus=0", "memory=2048 mb"],
        "output_identity": plan["output_identity"],
        "not_before": qualification["not_before"], "expires_at": qualification["expires_at"],
        "attempt_policy": "ONE_OWNER_ALLOCATED_ATTEMPT_NO_RETRY",
        "dispatch_route": "DISABLED", "execution_authorized": False,
    }
    spec["spec_digest"] = digest(spec)
    return spec


def check_dispatch_spec(spec, candidate, *, expected_spec_digest, at_time):
    """Validate a prospective compile result and exact bytes at runner boundary.

    This is an engineering predicate, not an authority check. An untrusted
    dictionary plus a matching hash cannot enable a backend or authorize a Run.
    """
    fields(spec, ("schema", "backend_id", "action", "plan", "request_digest", "job_name",
                  "input_filename", "dat_filename", "resources", "arguments", "output_identity",
                  "attempt_policy", "dispatch_route", "execution_authorized", "spec_digest",
                  "not_before", "expires_at"))
    original = {k: v for k, v in spec.items() if k != "spec_digest"}
    require(spec["spec_digest"] == expected_spec_digest == digest(original),
            "PLAN_STALE", "Exact compiled dispatch specification differs")
    plan = validate_plan_projection(spec["plan"])
    value = check_candidate(candidate)
    _sha(spec["request_digest"])
    for stamp in (at_time, spec["not_before"], spec["expires_at"]):
        integer(stamp, 1)
    require(spec["not_before"] <= at_time < spec["expires_at"]
            and spec["expires_at"] - spec["not_before"] <= 600,
            "REQUEST_EXPIRED", "Frozen prospective request window is closed")
    job_name = "axial_rod"
    require(spec["schema"] == SCHEMA and spec["backend_id"] == BACKEND
            and spec["action"] == ACTION and spec["job_name"] == job_name
            and spec["input_filename"] == "axial_bar.inp" and spec["dat_filename"] == job_name + ".dat"
            and spec["resources"] == RESOURCES and spec["arguments"] == [
                "job=" + job_name, "input=axial_bar.inp", "analysis", "interactive",
                "cpus=1", "gpus=0", "memory=2048 mb"]
            and spec["output_identity"] == plan["output_identity"]
            and spec["attempt_policy"] == "ONE_OWNER_ALLOCATED_ATTEMPT_NO_RETRY"
            and spec["dispatch_route"] == "DISABLED" and spec["execution_authorized"] is False,
            "PLAN_STALE", "Dynamic dispatch policy must remain exact and disabled")
    require(plan["input_digest"] == value["input_digest"] == bytes_digest(candidate.input_bytes)
            and plan["input_size"] == len(candidate.input_bytes) and plan["load_n"] == value["load_n"],
            "PLAN_STALE", "Actual candidate bytes differ from dispatch Plan")
    return {"schema": SCHEMA, "spec_digest": expected_spec_digest,
            "input_verified": True, "execution_authorized": False}


def validate_prospective_approval(approval, spec, candidate, *, expected_spec_digest, at_time):
    """Offline exact approval semantics only; never recognizes a real capability."""
    check_dispatch_spec(spec, candidate, expected_spec_digest=expected_spec_digest, at_time=at_time)
    fields(approval, ("scope", "decision", "plan_digest", "spec_digest", "input_digest",
                      "resources_digest", "output_identity", "not_before", "expires_at", "max_uses"))
    integer(at_time, 1)
    integer(approval["not_before"], 1)
    integer(approval["expires_at"], 1)
    require(approval["scope"] == "OFFLINE_NON_EXECUTABLE" and approval["decision"] == "APPROVE"
            and type(approval["max_uses"]) is int and approval["max_uses"] == 1,
            "APPROVAL_DENIED", "Only explicit inert single-use approval may be checked")
    require(approval["not_before"] <= at_time < approval["expires_at"]
            and spec["not_before"] <= approval["not_before"]
            and approval["expires_at"] <= spec["expires_at"],
            "APPROVAL_EXPIRED", "Approval window is closed or unbounded")
    require(approval["spec_digest"] == spec["spec_digest"] and all(
        approval[k] == spec["plan"][k] for k in
        ("plan_digest", "input_digest", "resources_digest", "output_identity")),
        "APPROVAL_SCOPE_MISMATCH", "Approval must bind exact prospective execution")
    return {"semantics": "PASS_OFFLINE", "human_identity": "NOT_ESTABLISHED",
            "execution_authorized": False}


def dispatch(spec, candidate, *, expected_spec_digest, at_time):
    """Explicit default-disabled route, with no configurable bypass or fallback."""
    check_dispatch_spec(spec, candidate, expected_spec_digest=expected_spec_digest, at_time=at_time)
    require(False, "ROD_EXECUTION_UNQUALIFIED",
            "Protected Operator, owner admission and dynamic recovery integration remain unqualified")
