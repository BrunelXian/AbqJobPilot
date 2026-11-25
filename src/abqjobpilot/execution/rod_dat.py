"""Bounded dynamic-rod DAT verification; no filesystem, execution or goal verdict.

The caller must independently authenticate provenance. G1 accepts only explicitly
labelled offline substitutions; an AF_REAL label cannot self-qualify the source.
"""
from decimal import Decimal
import re

from .models import bytes_digest, require
from .rod_profile import TOLERANCES, check_candidate, decimal
from .standard_dat import NUMBER, lines_of, number, parse

FIELDS = {"project_id", "project_instance_id", "plan_digest", "input_digest", "run_id",
          "attempt_id", "output_digest", "solver_exit_code", "managed_scope", "source"}


def parse_bound_dat(data, candidate, binding, expected_binding, tolerances=None):
    """Verify source binding and all printed values, never infer missing rows as zero."""
    value = check_candidate(candidate)
    require(type(data) is bytes and len(data) <= 1024 * 1024, "DAT_LIMIT", "Bounded DAT required")
    require(type(binding) is dict and type(expected_binding) is dict
            and set(binding) == set(expected_binding) == FIELDS and binding == expected_binding,
            "DAT_SOURCE_MISMATCH", "Exact separately pinned source binding required")
    require(binding["source"] == "OFFLINE_AF_SUBSTITUTE", "LIVE_AF_SOURCE_UNQUALIFIED",
            "Real artifact-source authentication is not registered in G1")
    require(binding["input_digest"] == value["input_digest"]
            and binding["output_digest"] == bytes_digest(data),
            "DAT_SOURCE_MISMATCH", "Input or DAT digest differs")
    require(all(type(binding[k]) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", binding[k])
                for k in ("project_id", "project_instance_id", "run_id", "attempt_id"))
            and type(binding["plan_digest"]) is str
            and re.fullmatch(r"sha256:[a-f0-9]{64}", binding["plan_digest"]),
            "DAT_SOURCE_MISMATCH", "Bounded source identities required")
    require(type(binding["solver_exit_code"]) is int and binding["solver_exit_code"] == 0
            and binding["managed_scope"] == "EMPTY_CONFIRMED",
            "DAT_EXECUTION_UNKNOWN", "Qualified completion and empty scope required")
    selected = dict(TOLERANCES if tolerances is None else tolerances)
    require(set(selected) == set(TOLERANCES)
            and all(0 < decimal(selected[k]) <= decimal(TOLERANCES[k]) for k in selected),
            "INVALID_TOLERANCE", "Frozen profile tolerance required")
    structural = parse(data)
    require(structural["solver"] == "DAT_COMPLETION_TEXT_OBSERVED", "DAT_INVALID_STRUCTURE",
            "Complete supported version, step, increment, tables and footer required")
    lines = lines_of(data)
    values = {}
    refs = {}
    for header, labels, offset, entities in (
        ("ELEMENT PT FOOT- S11", ("S11",), 2, {"1"}),
        ("NODE FOOT- U1 U2 U3", ("U1", "U2", "U3"), 1, {"1", "2"}),
        ("NODE FOOT- RF1 RF2 RF3", ("RF1", "RF2", "RF3"), 1, {"1", "2"}),
    ):
        cursor = lines.index(header) + 2
        while cursor < len(lines) and not lines[cursor]:
            cursor += 1
        seen = set()
        while cursor < len(lines) and lines[cursor]:
            row = lines[cursor].split()
            require(len(row) == offset + len(labels) and row[0] in entities
                    and row[0] not in seen and all(re.fullmatch(NUMBER, x) for x in row[offset:]),
                    "DAT_INVALID_ROW", "Exact unique entity rows required")
            require(offset != 2 or row[1] == "1", "DAT_INVALID_ROW", "Integration point differs")
            seen.add(row[0])
            for label, raw in zip(labels, row[offset:]):
                key = row[0] + "_" + label
                values[key] = number(raw)
                refs[key] = {"line": cursor + 1, "entity": row[0], "component": label,
                             "step": 1, "increment": 1, "raw": raw}
            cursor += 1
        require(seen == entities, "DAT_MISSING_ENTITY", "Every frozen entity must be printed")
    force = decimal(value["load_n"])
    expected = {"2_U1": (force * Decimal("10") / Decimal("1000"), "mm", "displacement_mm"),
                "1_S11": (force, "MPa", "stress_mpa"),
                "1_RF1": (-force, "N", "reaction_n")}
    for key in ("1_U1", "1_U2", "1_U3", "2_U2", "2_U3"):
        expected[key] = (Decimal(0), "mm", "zero_mm")
    for key in ("1_RF2", "1_RF3", "2_RF1", "2_RF2", "2_RF3"):
        expected[key] = (Decimal(0), "N", "reaction_n")
    comparisons = []
    for key, (target, unit, tolerance) in expected.items():
        error = abs(values[key] - target)
        comparisons.append({"quantity": key, "actual": str(values[key]), "expected": str(target),
                            "unit": unit, "absolute_error": str(error),
                            "tolerance": selected[tolerance], "source": refs[key],
                            "status": "PASS" if error <= decimal(selected[tolerance]) else "FAIL"})
    balance = abs(force + values["1_RF1"] + values["2_RF1"])
    comparisons.append({"quantity": "X_force_balance", "unit": "N", "absolute_error": str(balance),
                        "tolerance": selected["balance_n"],
                        "status": "PASS" if balance <= decimal(selected["balance_n"]) else "FAIL"})
    return {"schema": "axial-rod-bound-dat-v1", "source": binding["source"],
            "binding": dict(binding), "profile": value["profile"], "load_n": value["load_n"],
            "solver": "DAT_COMPLETION_TEXT_OBSERVED",
            "numerical": "PASS" if all(v["status"] == "PASS" for v in comparisons) else "FAIL",
            "comparisons": comparisons, "step": 1, "increment": 1,
            "metric": {"node": 2, "component": "U1", "unit": "mm", "value": str(values["2_U1"])},
            "goal": "NOT_EVALUATED", "V4": "NOT_ASSESSED", "ODB": "NOT_VERIFIED",
            "live_source_qualified": False}
