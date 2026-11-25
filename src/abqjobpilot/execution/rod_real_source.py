"""Prospective dynamic Standard admission and real-source wire contract.

Read-only qualification of an existing inert Plan is not a real execution Plan
upgrade. Bundle validation checks declarations and bytes, not authentication.
No issuer, owner, process API, filesystem artifact reader or enable flag exists.
"""

from dataclasses import dataclass, field

from .models import bytes_digest, canonical_json, digest, fields, integer, require
from .rod_evidence import REAL_SCHEMA, validate_real_source_contract
from .rod_lifecycle import inspect_request, qualify_request
from .rod_plan_adapter import BACKEND
from .rod_profile import PROFILE, _label, decimal
from .rod_review import _sha

SCHEMA = "af-rod-real-evidence-v1"
PLAN_SCHEMA = "af-rod-real-plan-projection-v1"
PLAN_FIELDS = (
    "schema", "profile", "backend_id", "project_id", "project_instance_id",
    "plan_id", "plan_digest", "candidate_id", "input_digest", "input_size",
    "resources_digest", "output_identity", "contract_digest", "research_project_id",
    "research_revision", "phase", "load_n", "verification_policy_digest",
)
RECEIPT_FIELDS = (
    "request_id", "idempotency_key", "project_id", "project_instance_id", "plan_id",
    "plan_digest", "run_id", "grant_id", "request_status", "accepted_sequence",
)
RUN_FIELDS = (
    "run_id", "project_id", "project_instance_id", "plan_id", "plan_digest",
    "grant_id", "phase_attempt_id", "backend_id", "phase", "attempt_no", "retry_of",
    "simulation", "execution", "reconciliation", "backend_outcome", "solver_exit_code",
    "input_digest", "output_identity", "revision", "managed_scope",
)


def validate_plan_projection(plan):
    fields(plan, PLAN_FIELDS)
    require(plan["schema"] == PLAN_SCHEMA and plan["profile"] == PROFILE
            and plan["backend_id"] == BACKEND and plan["phase"] in ("A", "B"),
            "REAL_PLAN_MISMATCH", "Separate versioned rod projection required")
    for key in ("project_id", "project_instance_id", "plan_id", "candidate_id", "research_project_id"):
        _label(plan[key])
    for key in ("plan_digest", "input_digest", "resources_digest", "output_identity",
                "contract_digest", "verification_policy_digest"):
        _sha(plan[key])
    integer(plan["input_size"], 1)
    integer(plan["research_revision"], 1)
    require(plan["input_size"] <= 65536 and decimal("0.5") <= decimal(plan["load_n"]) <= decimal("2.5"),
            "REAL_PLAN_MISMATCH", "Bounded exact rod input and load required")
    return plan


def qualify_real_plan(product, plan_ref, request_key, *, at_time):
    """Recheck committed request, input, output and expiry without Store writes.

    The projection is path-free. Only A is preparable today; B remains blocked
    by the original public product until authentic A observation is available.
    """
    request = inspect_request(product, plan_ref, request_key, at_time=at_time)
    readiness = qualify_request(product, plan_ref, request_key, at_time=at_time)
    ref = request["plan_ref"]
    plan = {key: ref[key] for key in PLAN_FIELDS if key not in ("schema", "backend_id")}
    plan.update(schema=PLAN_SCHEMA, backend_id=BACKEND)
    validate_plan_projection(plan)
    return {
        "schema": "af-rod-real-admission-readiness-v1", "plan": plan,
        "projection_digest": digest(plan), "request_digest": request["request_digest"],
        "request_key": request_key, "max_attempts": 1,
        "not_before": request["not_before"], "expires_at": request["expires_at"],
        "attempt_identity": "ALLOCATED_ONLY_BY_AUTHORIZED_OWNER",
        "execution_authorized": False, "activation": "DISABLED",
        "admission": "OFFLINE_EXACT_INPUT_CHECKED",
        "dispatch": readiness["REAL_STANDARD_DISPATCH_QUALIFIED"],
        "source_authentication": "NOT_VERIFIED",
    }


def bundle_digest(bundle):
    """Bytes are bound by the checked artifact SHA; never JSON-encode raw DAT."""
    value = {k: v for k, v in bundle.items() if k != "bindings_digest"}
    value["artifact"] = {k: v for k, v in value["artifact"].items() if k != "dat_bytes"}
    return digest(value)


@dataclass(frozen=True)
class SchemaValidatedRealEvidence:
    """Typed result intentionally carries no live source authority."""

    bindings_digest: str
    dat_digest: str
    plan_digest: str
    source_authentication: str = field(default="NOT_VERIFIED", init=False)
    V2: str = field(default="NOT_VERIFIED", init=False)
    V3: str = field(default="INCONCLUSIVE", init=False)
    V4: str = field(default="NOT_ASSESSED", init=False)
    ODB: str = field(default="NOT_VERIFIED", init=False)


def validate_real_bundle(bundle, *, expected_plan):
    """Offline/declaration wire validation, independent of source authenticity.

    Caller-provided expected Plan is a comparison pin, never an authentication
    credential. No self-asserted REAL/AUTHENTICATED flag can promote this result.
    """
    require(type(bundle) is dict and set(bundle) == {
        "schema", "source", "plan", "receipt", "run", "events", "artifact", "bindings_digest"},
        "INVALID_REQUEST", "Exact bounded real bundle required")
    require(bundle["schema"] == SCHEMA and bundle["source"] in
            ("OFFLINE_REAL_SCHEMA_FIXTURE", "AF_REAL_DECLARATION"),
            "DAT_SOURCE_MISMATCH", "Versioned declaration source required")
    plan = validate_plan_projection(bundle["plan"])
    validate_plan_projection(expected_plan)
    require(plan == expected_plan, "DAT_SOURCE_MISMATCH", "Exact independently pinned Plan differs")
    receipt, run, artifact = bundle["receipt"], bundle["run"], bundle["artifact"]
    fields(receipt, RECEIPT_FIELDS)
    fields(run, RUN_FIELDS)
    require(type(artifact) is dict and set(artifact) == {
        "filename", "dat_bytes", "size", "sha256", "run_id", "phase_attempt_id",
        "input_digest", "output_identity", "selector", "units", "stable_read"},
        "INVALID_REQUEST", "Exact bounded DAT artifact required")
    canonical_json({key: value for key, value in artifact.items() if key != "dat_bytes"})
    for key in ("project_id", "project_instance_id", "plan_id", "plan_digest"):
        require(receipt[key] == run[key] == plan[key], "DAT_SOURCE_MISMATCH", "Run/Receipt Plan differs")
    for key in ("run_id", "grant_id"):
        _label(run[key])
        require(receipt[key] == run[key], "DAT_SOURCE_MISMATCH", "Original Receipt/Run differs")
    for key in ("request_id", "idempotency_key"):
        _label(receipt[key])
    _label(run["phase_attempt_id"])
    integer(receipt["accepted_sequence"], 1)
    require(receipt["request_status"] == "ACCEPTED" and run["backend_id"] == BACKEND
            and run["phase"] == "STANDARD" and type(run["attempt_no"]) is int and run["attempt_no"] == 1
            and run["retry_of"] is None and run["simulation"] is False
            and run["execution"] == "FINISHED" and run["reconciliation"] == "NONE"
            and run["managed_scope"] == "COMMITTED_EMPTY_SCOPE"
            and run["backend_outcome"] == "COMPLETED" and type(run["solver_exit_code"]) is int
            and run["solver_exit_code"] == 0 and type(run["revision"]) is int and run["revision"] == 3,
            "DAT_EXECUTION_UNKNOWN", "Exact completed non-retried attempt required")
    require(all(run[k] == plan[k] for k in ("input_digest", "output_identity")),
            "DAT_SOURCE_MISMATCH", "Run input/output identity differs")
    require(type(artifact["dat_bytes"]) is bytes and type(artifact["size"]) is int
            and 0 < artifact["size"] == len(artifact["dat_bytes"]) <= 1048576
            and artifact["sha256"] == bytes_digest(artifact["dat_bytes"])
            and artifact["filename"] == "axial_rod.dat"
            and artifact["stable_read"] is True,
            "DAT_SOURCE_MISMATCH", "Bounded exact original DAT bytes required")
    require(all(artifact[k] == run[k] for k in ("run_id", "phase_attempt_id", "input_digest", "output_identity")),
            "DAT_SOURCE_MISMATCH", "Artifact attempt/input/output differs")
    events = bundle["events"]
    require(type(events) is list and len(events) == 3, "DAT_SOURCE_MISMATCH", "Three ordered records required")
    prior = 0
    for number, (event, kind) in enumerate(zip(events, ("REQUEST_ACCEPTED", "START_INTENT", "ROD_DAT_COMMITTED")), 1):
        fields(event, ("type", "project_sequence", "run_sequence", "run_id", "phase_attempt_id"))
        integer(event["project_sequence"], 1)
        integer(event["run_sequence"], 1)
        require(event["type"] == kind and event["project_sequence"] > prior
                and event["run_sequence"] == number
                and all(event[k] == run[k] for k in ("run_id", "phase_attempt_id")),
                "DAT_SOURCE_MISMATCH", "Ordered same-attempt evidence required")
        prior = event["project_sequence"]
    require(events[0]["project_sequence"] == receipt["accepted_sequence"],
            "DAT_SOURCE_MISMATCH", "Original acceptance sequence differs")
    # Reuse the existing real-source schema checker; this declaration remains
    # unauthenticated even if every field and digest agrees.
    declaration = {key: plan[key] for key in (
        "profile", "backend_id", "project_id", "project_instance_id", "plan_id", "plan_digest",
        "candidate_id", "input_digest", "phase", "resources_digest", "output_identity", "verification_policy_digest")}
    declaration.update(schema=REAL_SCHEMA, source="AF_REAL_DECLARATION",
        grant_id=run["grant_id"], receipt_id=receipt["request_id"], run_id=run["run_id"],
        phase_attempt_id=run["phase_attempt_id"], output_digest=artifact["sha256"], output_size=artifact["size"],
        selector=artifact["selector"], units=artifact["units"], solver_exit_code=run["solver_exit_code"],
        execution=run["execution"], reconciliation=run["reconciliation"],
        managed_scope=run["managed_scope"], stable_read=artifact["stable_read"])
    validate_real_source_contract(declaration, declaration)
    require(bundle["bindings_digest"] == bundle_digest(bundle), "DAT_SOURCE_MISMATCH", "Bundle content differs")
    return SchemaValidatedRealEvidence(bundle["bindings_digest"], artifact["sha256"], plan["plan_digest"])


def acquire_authenticated_real_dat(*, plan, request_id):
    """Reserved public typed acquisition seam; authentic adapter is NOT_RUN.

    No caller-supplied paths, callbacks, bools or TEST_ONLY receipts are accepted.
    Enabling later requires protected Operator and owner-committed artifact
    provenance, separately reviewed dispatcher/recovery and actual host proof.
    """
    validate_plan_projection(plan)
    _label(request_id)
    require(False, "REAL_SOURCE_ADAPTER_UNQUALIFIED", "Authentic owner-bound source acquisition is not qualified")
