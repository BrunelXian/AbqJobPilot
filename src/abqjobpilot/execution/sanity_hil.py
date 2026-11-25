"""Preparation and one exact human decision for a dedicated source-only Sanity HIL."""

import json
import os
from pathlib import Path

from .models import bytes_digest, canonical_json, digest, fields, identifier, integer, now, require, text
from .paths import local_path, no_reparse
from .sanity_model import BASELINE
from .standard_contract import CMD, ENTRY, PYTHON, RESOURCES, identity

VERSION = "abq-real-t3d2-hil-v1"
EXTERNAL_VERSION = "abq-real-t3d2-hil-v2"
EXTERNAL_PROJECT = Path(r"<unprovisioned>\profile-f18d9d82")
HIL_002_VERSION = "abq-real-t3d2-hil-v3"
HIL_002_PROJECT = Path(r"<unprovisioned>\profile-10dec6c4")
HIL_002_REQUEST_KEY = "unprovisioned-3db848af"
HIL_003_VERSION = "abq-real-t3d2-hil-v4"
HIL_003_PROJECT = Path(r"<unprovisioned>\profile-8b5e3142")
HIL_003_REQUEST_KEY = "unprovisioned-8ef92bc0"
HIL_003R_PROJECT = Path(r"<unprovisioned>\profile-38afcdbd")
HIL_003R_REQUEST_KEY = "unprovisioned-2a82a3ac"
HIL_ODB_VERSION = "abq-real-t3d2-hil-v5"
HIL_ODB_PROJECT = Path(r"<unprovisioned>\profile-ac81eb28")
HIL_ODB_REQUEST_KEY = "unprovisioned-218b6f7b"
HIL_ODB_001_PROJECT = Path(r"<unprovisioned>\profile-928005e5")
HIL_ODB_001_REQUEST_KEY = "unprovisioned-dc9a2b0f"
PROVENANCE_VERSIONS = (HIL_002_VERSION, HIL_003_VERSION, HIL_ODB_VERSION)
REVIEW = "review_hil"
GRANT_KIND = "REAL_T3D2_HIL_ONCE"
# Historic v1 has no deployed digest. External contracts bind exact paths.
APPROVED_PLAN_DIGEST = None

INSTALL = Path(r"<unprovisioned>\solver\win_b64")
HIL_PREPROCESSOR = INSTALL / "code" / "bin" / "pre.exe"
VS_ROOT = Path(r"<unprovisioned>\compiler")
ENVIRONMENT = {"VS2022INSTALLDIR": str(VS_ROOT)}
SCRIPT = Path(__file__).with_name("hil_odb_u2.py")
MATERIALS = (
    Path(r"<unprovisioned>\toolchain\env\vars.bat"),
    VS_ROOT / "VC/Auxiliary/Build/vcvarsall.bat",
    *(INSTALL / "code/bin" / name for name in (
        "SMALauncher.exe", "standard.exe", "SMAPython.exe", "odbAccess.pyd", "python310.dll")),
    INSTALL / "tools/SMApy/python3.10/python.exe",
    *(INSTALL / "SMA/site" / name for name in (
        "abaqus_v6.env", "basic_v6.env", "mpi_config.env", "graphicsConfig.env", "jleConfig.env",
        "custom_v6.env", "licensing.env", "EstablishedProductsConfig.ini")),
)
ODB_VERSION = "t3d2-final-tip-u2-v1"
ODB_SELECTOR = {"step": "LOAD", "field": "U", "region": "TIP", "node": 2,
                "component": "U2", "frame": "FINAL_AT_1", "output_format": "JSON", "unit": "mm"}
ODB_SECONDS = 60
ODB_MAX_BYTES = 64 * 1024 * 1024
DECISION_FIELDS = ("plan_id", "plan_digest", "scope_digest", "decision", "subject",
                   "approval_ref", "allow_odb", "expires_at")
DECISION_IDENTITY = ("project_id", "project_instance_id", "input_sha256")
REGISTRATION_CHOICE = "allow_odb_registration"


def material_paths(version=VERSION):
    extra = ()
    if version in PROVENANCE_VERSIONS:
        observation = tuple(Path(__file__).with_name(name) for name in (
            "job_process_observer.py", "process_handles.py", "standard_backend.py",
            "standard_exit_policy.py", "job_provenance.py"))
        extra = (HIL_PREPROCESSOR, *observation)
    if version in (HIL_003_VERSION, HIL_ODB_VERSION):
        extra += (Path(__file__).resolve().parents[1] / "service_owner.py",)
    return [str(path) for path in (*MATERIALS, *extra, SCRIPT)]


def from_plan(plan):
    return "hil" in plan.get("sanity", {})


def plan_version(plan):
    return plan.get("sanity", {}).get("hil", {}).get("contract_version")


def external(plan):
    return plan_version(plan) in (EXTERNAL_VERSION, *PROVENANCE_VERSIONS)


def uses_exit_semantics(plan):
    return plan_version(plan) in PROVENANCE_VERSIONS


def independent_registration(plan):
    return plan_version(plan) == HIL_ODB_VERSION


def critical_images(plan):
    binary = INSTALL / "code" / "bin"
    return {"wrapper": plan["runtime_binding"]["cmd"],
            "launcher": str(binary / "SMALauncher.exe"), "preprocessor": str(HIL_PREPROCESSOR),
            "standard": str(binary / "standard.exe")}


def _external_registration(path):
    path = local_path(path)
    registration = {
        EXTERNAL_PROJECT: (EXTERNAL_VERSION, None),
        HIL_002_PROJECT: (HIL_002_VERSION, HIL_002_REQUEST_KEY),
        HIL_003_PROJECT: (HIL_003_VERSION, HIL_003_REQUEST_KEY),
        HIL_003R_PROJECT: (HIL_003_VERSION, HIL_003R_REQUEST_KEY),
        HIL_ODB_PROJECT: (HIL_ODB_VERSION, HIL_ODB_REQUEST_KEY),
        HIL_ODB_001_PROJECT: (HIL_ODB_VERSION, HIL_ODB_001_REQUEST_KEY),
    }.get(path)
    require(registration is not None, "HIL_PROJECT_PATH", "Only a dedicated external HIL Project is eligible")
    no_reparse(path)
    return registration


def external_version(path):
    version, _ = _external_registration(path)
    return version


def require_external_project(path, version=EXTERNAL_VERSION):
    require(external_version(path) == version, "HIL_PROJECT_PATH", "HIL contract belongs to another Project path")


def check_request_key(version, request_key, *, project):
    if version == VERSION:
        return
    registered, expected = _external_registration(project)
    require(registered == version, "HIL_PROJECT_PATH", "HIL contract belongs to another Project path")
    require(expected is None or request_key == expected,
            "HIL_SCOPE_MISMATCH", "This HIL requires its dedicated request key")


def input_identity(path):
    """For external HIL retain physical identity as well as bytes while fingerprinting."""
    from ..abaqus_preview.inputs import _open_pinned

    with _open_pinned(path) as stream:
        info = os.fstat(stream.fileno())
        data = stream.read(8193)
        require(0 < len(data) == info.st_size <= 8192, "PLAN_STALE", "Unexpected fixed HIL input size")
        return {"path": str(path), "size": info.st_size, "digest": bytes_digest(data),
                "file_identity": {"device": info.st_dev, "inode": info.st_ino, "mtime_ns": info.st_mtime_ns}}


def profile(version=VERSION):
    require(version in (VERSION, EXTERNAL_VERSION, *PROVENANCE_VERSIONS), "HIL_SCOPE_MISMATCH", "Unknown HIL contract")
    odb = {"script_version": ODB_VERSION, "script": identity(SCRIPT, 16384),
           "selector": dict(ODB_SELECTOR), "timeout_seconds": ODB_SECONDS,
           "max_source_bytes": ODB_MAX_BYTES, "max_reads": 1}
    if version == HIL_003_VERSION:
        odb["registration_guard"] = identity(Path(__file__).with_name("hil_odb.py"))
    if version == HIL_ODB_VERSION:
        odb["registration"] = {
            "contract": "sanity-odb-source-registration/1.0",
            "policy": "FINGERPRINT_ONLY_THEN_INDEPENDENT_READ",
            "guard": identity(Path(__file__).with_name("odb_registration.py")),
            "dispatch": identity(Path(__file__).with_name("service.py")),
            "read_authority": identity(Path(__file__).with_name("odb_history.py")),
            "output_provenance": identity(Path(__file__).with_name("odb_output_provenance.py")),
        }
    return {"contract_version": version, "release": "2024", "environment": dict(ENVIRONMENT), "odb": odb}


def validate_plan(plan):
    from ..application_runtime import is_frozen_runtime
    from ..sanity_admission import BACKEND

    sanity = plan["sanity"]
    runtime = plan["runtime_binding"]
    version = plan_version(plan)
    require(not is_frozen_runtime() and plan["backend_id"] == BACKEND
            and sanity["mode"] == "REAL" and sanity["candidate_sha256"] == BASELINE
            and sanity["F_N"] == "1" and sanity["launch_budget"] == 1
            and sanity["hil"] == profile(version) and plan["resources"] == RESOURCES
            and runtime["entry"] == ENTRY and runtime["cmd"] == CMD and runtime["interpreter"] == PYTHON
            and [item["path"] for item in runtime["materials"]] == [ENTRY, CMD, PYTHON, *material_paths(version)]
            and runtime["materials"][-1] == sanity["hil"]["odb"]["script"],
            "HIL_SCOPE_MISMATCH", "Only the frozen source T3D2 and reviewed installation profile are supported")
    if external(plan):
        check_request_key(version, sanity["request_key"], project=Path(plan["engineering"]).parent)


def require_activation(plan, *, service=None, connection=None, authorized_at=None):
    if external(plan):
        require(service is not None and connection is not None, "REAL_SANITY_DISABLED",
                "Exact activation requires the live Operator decision in the Owner Store")
        # Only terminal ODB registration evaluates authority at the original
        # launch time. Live Solver admission passes no historical timestamp.
        return require_decision(service, connection, plan, allow_odb=authorized_at is not None,
                                authorized_at=authorized_at)
    require(from_plan(plan) and APPROVED_PLAN_DIGEST is not None
            and plan["plan_digest"] == APPROVED_PLAN_DIGEST,
            "REAL_SANITY_DISABLED", "No exact Sanity HIL Plan is enabled in this source build")
    if service is not None and connection is not None:
        # The dormant v1 Solver path does not supply a service or connection.
        return require_decision(service, connection, plan, allow_odb=True, authorized_at=authorized_at)


def packet(plan):
    from .product_standard import scope

    validate_plan(plan)
    return {"contract_version": plan_version(plan), "project_id": plan["sanity"]["project_id"],
            "request_key": plan["sanity"]["request_key"], "scope": scope(plan),
            "scope_digest": digest(scope(plan)), "expires_at": plan["expires_at"],
            "execution_authorized": False}


def decision_input(args):
    fields(args, DECISION_FIELDS, (*DECISION_IDENTITY, REGISTRATION_CHOICE))
    for key in ("plan_id", "plan_digest", "scope_digest", "subject", "approval_ref",
                *(key for key in DECISION_IDENTITY if key in args)):
        text(args[key])
    integer(args["expires_at"])
    require(args["decision"] in ("APPROVE_EXACT", "DENY_TERMINAL") and type(args["allow_odb"]) is bool
            and (args["decision"] == "APPROVE_EXACT" or not args["allow_odb"]),
            "INVALID_REQUEST", "Exact human decision and explicit ODB choice required")
    if REGISTRATION_CHOICE in args:
        require(type(args[REGISTRATION_CHOICE]) is bool
                and (args["decision"] == "APPROVE_EXACT" or not args[REGISTRATION_CHOICE]),
                "INVALID_REQUEST", "Explicit registration-only choice required")


def decision_namespace(service, plan):
    return canonical_json([service.context.project_instance_id, plan_version(plan), plan["plan_id"], "decision"])


def _require_owner(service, conn):
    from .store import gate_view

    gate = gate_view(conn)
    started = conn.execute("SELECT value FROM meta WHERE key='supervisor_started'").fetchone()
    require(started is not None and started[0] == "1" and gate["state"] == "PAUSED"
            and gate["owner_id"] == service.store._session.owner_id,
            "OWNER_UNCONFIRMED", "Active PAUSED Supervisor Owner required")


def _approval_identity(service, plan):
    from ..sanity_admission import validate

    context = service.context
    require_external_project(context.test_root, plan_version(plan))
    validate(context, plan, live=False)
    return {"project_id": context.project_id, "project_instance_id": context.project_instance_id,
            "input_sha256": plan["input_manifest"][0]["digest"]}


def record_decision(service, conn, plan, args, owner):
    _require_owner(service, conn)
    snapshot = packet(plan)
    if external(plan):
        require(all(args.get(key) == value for key, value in _approval_identity(service, plan).items()),
                "HIL_SCOPE_MISMATCH", "Confirm the original Project, Instance and INP SHA-256")
    else:
        require(not any(key in args for key in DECISION_IDENTITY), "INVALID_REQUEST", "Legacy decision fields differ")
    require(args["plan_id"] == plan["plan_id"] and args["plan_digest"] == plan["plan_digest"]
            and args["scope_digest"] == snapshot["scope_digest"],
            "HIL_SCOPE_MISMATCH", "Human decision differs from the exact Plan")
    if Path(service.context.test_root) == HIL_003R_PROJECT:
        require(not args["allow_odb"], "ODB_NOT_AUTHORIZED", "HIL-003R requires NO_ODB")
    require((REGISTRATION_CHOICE in args) == independent_registration(plan),
            "INVALID_REQUEST", "Registration choice is required only for the independent registration contract")
    if independent_registration(plan):
        require(not args["allow_odb"], "ODB_INDEPENDENT_READ_REQUIRED", "Solver approval cannot authorize ODB extraction")
    require(now() < args["expires_at"] <= min(now() + 600, plan["expires_at"]),
            "HIL_APPROVAL_EXPIRED", "Use an explicit decision window of at most 600 seconds")
    namespace = decision_namespace(service, plan)
    require(all(conn.execute("SELECT 1 FROM " + table + " LIMIT 1").fetchone() is None
                for table in ("runs", "grants"))
            and conn.execute("SELECT 1 FROM management_receipts WHERE namespace=?", (namespace,)).fetchone() is None,
            "HIL_DECISION_FINAL", "One decision must precede every Grant and Run")
    decision = {**args, "contract_version": plan_version(plan), "owner_id": owner,
                "project_id": service.context.project_id, "project_instance_id": service.context.project_instance_id,
                "operation_id": identifier("op"), "decided_at": now()}
    conn.execute("INSERT INTO management_receipts VALUES(?,?,?,?,?)",
                 (namespace, "decision", digest(decision), decision["operation_id"], canonical_json(decision)))
    return decision


def require_decision(service, conn, plan, *, allow_odb=False, authorized_at=None):
    is_external = external(plan)
    if not is_external:
        require_activation(plan)
    _require_owner(service, conn)
    row = conn.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key='decision'",
                       (decision_namespace(service, plan),)).fetchone()
    require(row is not None, "REAL_SANITY_DISABLED" if is_external else "HIL_DECISION_REQUIRED",
            "A separate exact human decision is required")
    decision = json.loads(row[1])
    checked_at = now() if authorized_at is None else authorized_at
    require(row[0] == digest(decision) and decision["contract_version"] == plan_version(plan)
            and decision["decision"] == "APPROVE_EXACT" and decision["owner_id"] == service.store._session.owner_id
            and decision["project_id"] == service.context.project_id
            and decision["project_instance_id"] == service.context.project_instance_id
            and decision["plan_id"] == plan["plan_id"] and decision["plan_digest"] == plan["plan_digest"]
            and decision["scope_digest"] == packet(plan)["scope_digest"]
            and decision["decided_at"] <= checked_at < decision["expires_at"] <= plan["expires_at"],
            "HIL_DECISION_DENIED", "Human decision expired, denied or differs from the current Owner and Plan")
    if is_external:
        require(all(decision.get(key) == value for key, value in _approval_identity(service, plan).items()),
                "HIL_SCOPE_MISMATCH", "Stored approval no longer matches Project, Instance and INP")
    if allow_odb:
        require(not independent_registration(plan), "ODB_INDEPENDENT_READ_REQUIRED",
                "Use a separate ODB read permit after trusted registration")
        require(decision["allow_odb"] is True, "ODB_NOT_AUTHORIZED", "Human approval did not include the one ODB read")
        if authorized_at is None:
            from .odb_history import independent_review_exists
            require(not independent_review_exists(conn, service, plan),
                    "ODB_READ_ALREADY_USED", "Use the existing independent ODB permission and original key")
    return decision
