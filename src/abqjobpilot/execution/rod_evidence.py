"""Read-only, bounded artifact acquisition for explicitly synthetic rod DAT.

An inert Plan has no real Run. Fake IPC identities are a separate execution_link,
never represented as a rod Solver run. Real artifact acquisition is fail-closed
until an independently qualified real execution/authority path exists.
"""

import json
from pathlib import Path

from .models import bytes_digest, digest, fields, require
from .rod_profile import _label

SCHEMA = "af-rod-evidence-envelope-v1"
DESCRIPTOR = "synthetic-evidence.json"
DAT_FILE = "synthetic.dat"
SELECTOR = {
    "step": 1,
    "increment": 1,
    "node": 2,
    "dof": 1,
    "element": 1,
    "integration_point": 1,
}
UNITS = {"displacement": "mm", "stress": "MPa", "reaction": "N"}
REAL_SCHEMA = "af-real-rod-source-contract-v1"
REAL_FIELDS = {
    "schema",
    "source",
    "profile",
    "backend_id",
    "project_id",
    "project_instance_id",
    "plan_id",
    "plan_digest",
    "candidate_id",
    "input_digest",
    "grant_id",
    "receipt_id",
    "run_id",
    "phase_attempt_id",
    "phase",
    "resources_digest",
    "output_identity",
    "output_digest",
    "output_size",
    "verification_policy_digest",
    "selector",
    "units",
    "solver_exit_code",
    "execution",
    "reconciliation",
    "managed_scope",
    "stable_read",
}


def _selector(value):
    return (
        type(value) is dict
        and value == SELECTOR
        and all(type(item) is int for item in value.values())
    )


def validate_real_source_contract(record, expected_binding):
    """Check a versioned declaration, never authenticate its claimed real source.

    The independent expected binding is mandatory. A forged pair can still pass
    structural checks: no caller-supplied dictionary unlocks real reading or V2.
    """
    import re
    from .rod_plan_adapter import BACKEND
    from .rod_profile import PROFILE

    fields(record, REAL_FIELDS)
    fields(expected_binding, REAL_FIELDS)
    require(
        record == expected_binding,
        "DAT_SOURCE_MISMATCH",
        "Separately pinned source declaration differs",
    )
    require(
        record["schema"] == REAL_SCHEMA
        and record["source"] in {"TEST_ONLY_REAL_SCHEMA_FIXTURE", "AF_REAL_DECLARATION"}
        and record["profile"] == PROFILE
        and record["backend_id"] == BACKEND,
        "DAT_SOURCE_MISMATCH",
        "Wrong versioned rod source contract",
    )
    for key in (
        "project_id",
        "project_instance_id",
        "plan_id",
        "candidate_id",
        "grant_id",
        "receipt_id",
        "run_id",
        "phase_attempt_id",
    ):
        _label(record[key])
    for key in (
        "plan_digest",
        "input_digest",
        "resources_digest",
        "output_identity",
        "output_digest",
        "verification_policy_digest",
    ):
        require(
            type(record[key]) is str
            and re.fullmatch(r"sha256:[a-f0-9]{64}", record[key]),
            "DAT_SOURCE_MISMATCH",
            "Strict content digest required",
        )
    require(
        record["phase"] in {"A", "B"}
        and type(record["output_size"]) is int
        and 0 < record["output_size"] <= 1024 * 1024
        and _selector(record["selector"])
        and record["units"] == UNITS,
        "DAT_SOURCE_MISMATCH",
        "Frozen selectors, units and bounded output required",
    )
    require(
        type(record["solver_exit_code"]) is int
        and record["solver_exit_code"] == 0
        and record["execution"] == "FINISHED"
        and record["reconciliation"] == "NONE"
        and record["managed_scope"] == "COMMITTED_EMPTY_SCOPE"
        and record["stable_read"] is True,
        "DAT_EXECUTION_UNKNOWN",
        "Completion and stable scope declarations are incomplete",
    )
    return {
        "schema": REAL_SCHEMA,
        "schema_valid": True,
        "declaration_digest": digest(record),
        "source_authentication": "NOT_VERIFIED",
        "V2": "NOT_VERIFIED",
        "live_read_enabled": False,
    }


def read_synthetic_dat(
    product, plan_id, expected_digest, *, expected_output_digest, evidence_key, at_time
):
    """Acquire only fixed filenames under this exact inert Plan's output directory.

    Output bytes are for deterministic code only. Callers must project an
    allowlisted numerical record before sending anything to an Agent tool.
    """
    from ..product_rod import _file_bytes

    _label(evidence_key)
    plan_ref = product.inspect(plan_id, expected_digest, at_time=at_time)
    root = Path(plan_ref["output_path"])
    metadata_bytes = _file_bytes(product.context.test_root, root / DESCRIPTOR, 16384)
    metadata = json.loads(metadata_bytes)
    fields(
        metadata,
        (
            "schema",
            "source",
            "evidence_key",
            "plan_ref_digest",
            "plan_id",
            "plan_digest",
            "project_id",
            "project_instance_id",
            "candidate_id",
            "input_digest",
            "output_identity",
            "output_digest",
            "selector",
            "units",
            "execution_link",
        ),
    )
    require(
        metadata["schema"] == SCHEMA and metadata["source"] == "SYNTHETIC_DAT",
        "LIVE_AF_SOURCE_UNQUALIFIED",
        "Only explicitly synthetic DAT is admitted",
    )
    require(
        metadata["evidence_key"] == evidence_key
        and metadata["plan_ref_digest"] == digest(plan_ref)
        and all(
            metadata[key] == plan_ref[key]
            for key in (
                "plan_id",
                "plan_digest",
                "project_id",
                "project_instance_id",
                "candidate_id",
                "input_digest",
                "output_identity",
            )
        )
        and metadata["output_digest"] == expected_output_digest
        and _selector(metadata["selector"])
        and metadata["units"] == UNITS,
        "DAT_SOURCE_MISMATCH",
        "Exact frozen Plan, selector, units and separately pinned artifact required",
    )
    link = metadata["execution_link"]
    if link is not None:
        fields(
            link,
            (
                "source",
                "project_id",
                "project_instance_id",
                "plan_id",
                "plan_digest",
                "run_id",
                "phase_attempt_id",
                "receipt_id",
                "input_digest",
            ),
        )
        require(
            link["source"] == "FAKE_TEST_ONLY"
            and link["plan_id"] != plan_id
            and link["project_instance_id"] != plan_ref["project_instance_id"],
            "DAT_SOURCE_MISMATCH",
            "Fake execution must use its own distinct Plan and Project",
        )
    data = _file_bytes(product.context.test_root, root / DAT_FILE, 1024 * 1024)
    require(
        bytes_digest(data) == expected_output_digest,
        "DAT_SOURCE_MISMATCH",
        "Current DAT differs from the pinned original bytes",
    )
    require(
        _file_bytes(product.context.test_root, root / DESCRIPTOR, 16384)
        == metadata_bytes
        and product.inspect(plan_id, expected_digest, at_time=at_time) == plan_ref
        and _file_bytes(product.context.test_root, root / DAT_FILE, 1024 * 1024)
        == data,
        "DAT_SOURCE_MISMATCH",
        "Evidence or input changed during acquisition",
    )
    return {
        "schema": SCHEMA,
        "source": "SYNTHETIC_DAT",
        "evidence_key": evidence_key,
        "plan_ref": plan_ref,
        "plan_ref_digest": digest(plan_ref),
        "artifact": {
            "filename": DAT_FILE,
            "output_identity": plan_ref["output_identity"],
            "output_digest": expected_output_digest,
            "size": len(data),
            "stable_read": True,
            "selector": dict(SELECTOR),
            "units": dict(UNITS),
        },
        "execution_link": link,
        "real_solver_executed": False,
        "real_solver_status": "NOT_RUN",
        "dat_bytes": data,
    }


def read_real_dat(*_args, **_kwargs):
    require(
        False,
        "LIVE_AF_SOURCE_UNQUALIFIED",
        "Actual Solver and Operator source path is not qualified",
    )


def verify_synthetic_dat(
    product, plan_id, expected_digest, *, expected_output_digest, evidence_key, at_time
):
    """AF's numerical oracle, using persisted tolerances and acquired bytes only."""
    from .rod_dat import parse_bound_dat

    envelope = read_synthetic_dat(
        product,
        plan_id,
        expected_digest,
        expected_output_digest=expected_output_digest,
        evidence_key=evidence_key,
        at_time=at_time,
    )
    plan, candidate = product._checked(plan_id, expected_digest, at_time)
    # The low-level G1 parser's legacy source is used internally as an explicit
    # substitute. Its completion-text observation is not a real Solver verdict.
    binding = {
        "project_id": product.context.project_id,
        "project_instance_id": product.context.project_instance_id,
        "plan_digest": expected_digest,
        "input_digest": envelope["plan_ref"]["input_digest"],
        "run_id": "synthetic_run",
        "attempt_id": "synthetic_attempt",
        "output_digest": expected_output_digest,
        "solver_exit_code": 0,
        "managed_scope": "EMPTY_CONFIRMED",
        "source": "OFFLINE_AF_SUBSTITUTE",
    }
    parsed = parse_bound_dat(
        envelope["dat_bytes"],
        candidate,
        binding,
        binding,
        plan["rod_preview"]["tolerances"],
    )
    return {
        "schema": "af-synthetic-rod-verification-v1",
        "source": "SYNTHETIC_DAT",
        "plan_ref_digest": envelope["plan_ref_digest"],
        "output_digest": expected_output_digest,
        "numerical": parsed["numerical"],
        "metric": parsed["metric"],
        "comparisons": parsed["comparisons"],
        "real_solver_status": "NOT_RUN",
        "V2": "NOT_VERIFIED",
        "V4": "NOT_ASSESSED",
        "ODB": "ODB_NOT_VERIFIED",
        "goal": "NOT_EVALUATED",
    }
