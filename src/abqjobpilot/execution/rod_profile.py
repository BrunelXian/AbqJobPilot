"""Versioned rod candidate and exact *offline* Plan contract; no launch authority.

This additive profile is intentionally not registered in the live dispatcher.
Old Standard plans continue to use their frozen SHA and one-Run policy unchanged.
"""
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import re
import uuid

from .models import bytes_digest, canonical_json, digest, require
from .paths import confined
from .standard_contract import INPUT_DIGEST, RESOURCES

PROFILE = "axial_rod_cload_v1"
PLAN_SCHEMA = "rod-plan-preview-v1"
SLOT = b"*CLOAD\n2,1,1\n"
TOLERANCES = {"displacement_mm": "0.000001", "stress_mpa": "0.0001",
              "reaction_n": "0.0001", "balance_n": "0.0002", "zero_mm": "0.00000001"}


def decimal(value):
    require(type(value) is str and len(value) <= 32
            and re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value),
            "INVALID_ROD_NUMBER", "Canonical finite nonnegative decimal string required")
    number = Decimal(value)
    require(number.is_finite(), "INVALID_ROD_NUMBER", "Finite decimal required")
    return number


def _canonical(value):
    result = format(decimal(value), "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _label(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", value),
            "INVALID_REQUEST", "Bounded opaque identity required")
    return value


@dataclass(frozen=True)
class RodCandidate:
    input_bytes: bytes
    _json: str

    def to_dict(self):
        return json.loads(self._json)


def compile_candidate(frozen_template, load_n, *, unit="N", minimum="0.5", maximum="2.5"):
    require(type(frozen_template) is bytes and bytes_digest(frozen_template) == INPUT_DIGEST
            and frozen_template.count(SLOT) == 1,
            "ROD_TEMPLATE_MISMATCH", "Only the frozen rod template is supported")
    force, lower, upper = decimal(load_n), decimal(minimum), decimal(maximum)
    require(unit == "N" and Decimal("0.5") <= lower <= force <= upper <= Decimal("2.5"),
            "ROD_LOAD_OUT_OF_RANGE", "Frozen N range must fit qualified profile bounds")
    canonical_force = _canonical(load_n)
    rendered = frozen_template.replace(SLOT, b"*CLOAD\n2,1," + canonical_force.encode() + b"\n")
    # The inverse replacement is separate from the renderer and compares every byte.
    verify_mutation(frozen_template, rendered, canonical_force)
    body = {"profile": PROFILE, "schema": "rod-candidate-v1", "baseline_digest": INPUT_DIGEST,
            "input_digest": bytes_digest(rendered), "load_n": canonical_force,
            "unit": "N", "minimum_n": minimum, "maximum_n": maximum,
            "mutable_entity": {"keyword": "CLOAD", "node": 2, "dof": 1},
            "dimensions": {"length_mm": "10", "area_mm2": "1", "modulus_mpa": "1000"}}
    body["candidate_digest"] = digest(body)
    return RodCandidate(rendered, canonical_json(body))


def verify_mutation(template, candidate, load_n):
    require(type(template) is bytes and bytes_digest(template) == INPUT_DIGEST,
            "ROD_TEMPLATE_MISMATCH", "Baseline identity differs")
    require(type(candidate) is bytes and len(candidate) <= 65536,
            "ROD_MUTATION_DENIED", "Bounded input bytes required")
    prefix, suffix = template.split(b"*CLOAD\n2,1,1\n")
    expected = b"*CLOAD\n2,1," + _canonical(load_n).encode() + b"\n"
    require(candidate.startswith(prefix) and candidate.endswith(suffix)
            and candidate[len(prefix):len(candidate)-len(suffix)] == expected,
            "ROD_MUTATION_DENIED", "Only the single CLOAD scalar may differ")


def check_candidate(candidate):
    require(type(candidate) is RodCandidate, "INVALID_REQUEST", "Typed rod candidate required")
    value = candidate.to_dict()
    if value.get('profile') == 'axial_rod_cload_output_v2':
        from .rod_output_v2 import check_candidate as check_v2
        return check_v2(candidate)
    original = dict(value)
    claimed = original.pop("candidate_digest", None)
    require(claimed == digest(original), "ROD_CANDIDATE_STALE", "Candidate digest differs")
    # Rebuild from its one changed scalar, then demand exact profile metadata equality.
    force = value.get("load_n", "")
    decimal(force)
    marker = b"*CLOAD\n2,1," + force.encode("ascii", "strict") + b"\n"
    require(candidate.input_bytes.count(marker) == 1, "ROD_CANDIDATE_STALE", "Load slot differs")
    baseline = candidate.input_bytes.replace(marker, SLOT)
    rebuilt = compile_candidate(baseline, force, minimum=value["minimum_n"], maximum=value["maximum_n"])
    require(rebuilt.to_dict() == value and rebuilt.input_bytes == candidate.input_bytes,
            "ROD_CANDIDATE_STALE", "Candidate content or metadata differs")
    return value


def materialize_candidate(test_root, candidate):
    """Reserve a never-reused local directory. Partial failures are retained, not cleaned."""
    value = check_candidate(candidate)
    root = confined(test_root, Path(test_root), exists=True)
    require(root.is_dir(), "OUTPUT_SCOPE_VIOLATION", "Explicit test root required")
    target = confined(root, root / ("rod_" + uuid.uuid4().hex))
    target.mkdir(exist_ok=False)
    (target / "scratch").mkdir()
    (target / "outputs").mkdir()
    with (target / "axial_bar.inp").open("xb") as stream:
        stream.write(candidate.input_bytes)
    with (target / "candidate.json").open("x", encoding="utf-8") as stream:
        stream.write(canonical_json(value))
    return target


@dataclass(frozen=True)
class RodPlanPreview:
    _json: str

    def to_dict(self):
        return json.loads(self._json)


def prepare_preview(candidate, *, test_root, workspace, project_id, project_instance_id,
                    research_project_id, contract_digest, expires_at, at_time,
                    tolerances=None):
    """Pure exact preview, never inserts an AF Plan/Grant or changes any execution store."""
    value = check_candidate(candidate)
    root = confined(test_root, workspace, exists=True)
    require(type(at_time) is int and type(expires_at) is int and 0 < at_time < expires_at,
            "PLAN_EXPIRED", "Explicit valid time bounds required")
    require(re.fullmatch(r"sha256:[a-f0-9]{64}", contract_digest or ""),
            "INVALID_REQUEST", "Frozen contract digest required")
    for name in ("axial_bar.inp", "candidate.json", "scratch", "outputs"):
        confined(test_root, root / name, exists=True)
    require((root / "axial_bar.inp").is_file() and (root / "candidate.json").is_file()
            and (root / "axial_bar.inp").stat().st_size <= 65536
            and (root / "candidate.json").stat().st_size <= 65536,
            "PLAN_STALE", "Bounded regular input and manifest files required")
    require((root / "axial_bar.inp").read_bytes() == candidate.input_bytes
            and json.loads((root / "candidate.json").read_text(encoding="utf-8")) == value,
            "PLAN_STALE", "Actual materialized candidate differs")
    require(not any((root / "outputs").iterdir()) and not any((root / "scratch").iterdir()),
            "OUTPUT_CONFLICT", "Fresh empty output and scratch required")
    require(set(p.name for p in root.iterdir()) == {"axial_bar.inp", "candidate.json", "scratch", "outputs"},
            "OUTPUT_CONFLICT", "Unexpected environment, output or intent file")
    selected = dict(TOLERANCES if tolerances is None else tolerances)
    require(set(selected) == set(TOLERANCES)
            and all(0 < decimal(selected[k]) <= decimal(TOLERANCES[k]) for k in selected),
            "INVALID_TOLERANCE", "Frozen tolerances may not exceed profile caps")
    body = {"schema": PLAN_SCHEMA, "profile": PROFILE, "source": "OFFLINE_PLAN_PREVIEW",
            "plan_id": "rod_preview_" + uuid.uuid4().hex,
            "project_id": _label(project_id), "project_instance_id": _label(project_instance_id),
            "research_project_id": _label(research_project_id), "contract_digest": contract_digest,
            "candidate": value, "input_path": str(root / "axial_bar.inp"),
            "output_path": str(root / "outputs"), "scratch": str(root / "scratch"),
            "resources": dict(RESOURCES), "max_runs": 1, "expires_at": expires_at,
            "tolerances": selected, "managed_scope": "REQUIRED_NOT_VERIFIED",
            "dispatch_state": "LIVE_DISPATCH_UNREGISTERED", "execution_authorized": False}
    body["plan_digest"] = digest(body)
    return RodPlanPreview(canonical_json(body))


def check_preview(plan, *, expected_digest, project_id, project_instance_id, at_time):
    require(type(plan) is RodPlanPreview, "INVALID_REQUEST", "Typed preview required")
    value = plan.to_dict()
    raw = dict(value)
    claimed = raw.pop("plan_digest", None)
    require(claimed == expected_digest == digest(raw), "PLAN_STALE", "Exact reviewed digest differs")
    require(value["schema"] == PLAN_SCHEMA and value["profile"] == PROFILE
            and value["source"] == "OFFLINE_PLAN_PREVIEW"
            and value["execution_authorized"] is False
            and value["dispatch_state"] == "LIVE_DISPATCH_UNREGISTERED"
            and value["managed_scope"] == "REQUIRED_NOT_VERIFIED"
            and value["resources"] == RESOURCES and value["max_runs"] == 1,
            "PLAN_STALE", "Preview policy differs")
    require(value["project_id"] == project_id and value["project_instance_id"] == project_instance_id,
            "PROJECT_IDENTITY_MISMATCH", "Exact AF project and instance required")
    require(type(at_time) is int and value["expires_at"] > at_time, "PLAN_EXPIRED", "Preview expired")
    return value


def require_live_dispatch(_plan):
    require(False, "LIVE_DISPATCH_UNREGISTERED", "G1 preview is not a registered executable AF Plan")


def revalidate_materialization(plan, candidate, *, test_root, expected_digest, project_id,
                               project_instance_id, at_time):
    """Rehash current files and reject changed paths/old outputs before a handoff."""
    value = check_preview(plan, expected_digest=expected_digest, project_id=project_id,
                          project_instance_id=project_instance_id, at_time=at_time)
    input_path = confined(test_root, value["input_path"], exists=True)
    rebuilt = prepare_preview(candidate, test_root=test_root, workspace=input_path.parent,
                              project_id=project_id, project_instance_id=project_instance_id,
                              research_project_id=value["research_project_id"],
                              contract_digest=value["contract_digest"], expires_at=value["expires_at"],
                              at_time=at_time, tolerances=value["tolerances"]).to_dict()
    ignored = {"plan_id", "plan_digest"}
    require({k: v for k, v in value.items() if k not in ignored}
            == {k: v for k, v in rebuilt.items() if k not in ignored},
            "PLAN_STALE", "Current candidate, paths or profile differ from frozen preview")
    return value
