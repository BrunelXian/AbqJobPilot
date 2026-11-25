"""D7 output profile; compiled independently of GD, no authority."""
from decimal import Decimal
from .models import bytes_digest, canonical_json, digest, require
from .rod_profile import RodCandidate, decimal, _canonical
PROFILE = "axial_rod_cload_output_v2"
# Site model omitted from the public snapshot. The bytes-only guard rejects this sentinel.
TEMPLATE = None
BASELINE = "sha256:f200e353851d453c856a991d86a60f989ce6920a76db7723bb95730934d51bb0"


def compile_candidate(frozen_template, load_n, *, unit="N", minimum="0.5", maximum="2.5"):
    require(type(frozen_template) is bytes and frozen_template == TEMPLATE,
            "ROD_TEMPLATE_MISMATCH", "Exact v2 combined output template required")
    force = decimal(load_n)
    require(unit == "N" and Decimal("0.5") <= decimal(minimum) <= force <= decimal(maximum) <= Decimal("2.5"),
            "ROD_LOAD_OUT_OF_RANGE", "Exact N bounds required")
    rendered = TEMPLATE.replace(b"*CLOAD\n2,1,1\n", b"*CLOAD\n2,1," + _canonical(load_n).encode() + b"\n")
    body = {"profile": PROFILE, "schema": "rod-candidate-v2", "baseline_digest": BASELINE,
            "input_digest": bytes_digest(rendered), "load_n": _canonical(load_n), "unit": "N",
            "minimum_n": minimum, "maximum_n": maximum,
            "mutable_entity": {"keyword": "CLOAD", "node": 2, "dof": 1},
            "dimensions": {"length_mm": "10", "area_mm2": "1", "modulus_mpa": "1000"}}
    body["candidate_digest"] = digest(body)
    return RodCandidate(rendered, canonical_json(body))


def check_candidate(candidate):
    value = candidate.to_dict()
    rebuilt = compile_candidate(TEMPLATE, value.get("load_n", ""),
                                minimum=value.get("minimum_n", ""), maximum=value.get("maximum_n", ""))
    require(rebuilt.input_bytes == candidate.input_bytes and rebuilt.to_dict() == value,
            "ROD_CANDIDATE_STALE", "Every byte and metadata field must match v2")
    return value


OUTPUT = {"schema": "rod-output-v2", "node_set": "VERIFY", "nodes": [1, 2],
          "columns": ["U1", "U2", "U3", "RF1", "RF2", "RF3"],
          "element_set": "BAR", "element": 1, "integration_point": 1,
          "element_columns": ["S11"], "step": 1, "increment": 1,
          "units": "N_mm_MPa", "missing": "REJECT", "format_status": "REAL_OUTPUT_FORMAT_NOT_YET_OBSERVED"}

