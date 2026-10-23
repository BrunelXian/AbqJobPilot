"""Run010 offline profile and package change detection; no solver commands."""
import hashlib
import importlib.util
import os
from pathlib import Path

import pytest

from abqjobpilot.abaqus_preview import prepare, inspect, AbaqusPlanPreview
from abqjobpilot.abaqus_preview.preview import PROFILE, PROBE_PROFILE
from abqjobpilot.execution.models import ExecutionError, digest
from abaqus_preview_helpers import case, MODEL, STEP
from execution_helpers import guard_environment, harness, inventory

PRINT = """*NODE PRINT, FREQUENCY=1, SUMMARY=NO, TOTALS=NO, GLOBAL=YES
U
RF
*EL PRINT, ELSET=BAR, FREQUENCY=1, POSITION=INTEGRATION POINTS, SUMMARY=NO, TOTALS=NO
S
"""


def probe_case(tmp_path):
    args = case(tmp_path, contents=MODEL + STEP.replace("*END STEP", PRINT + "*END STEP"))
    args["support_profile_version"] = PROBE_PROFILE
    return args


def test_default_profile_remains_identical_and_rejects_new_keywords(tmp_path):
    args = case(tmp_path)
    assert inspect(prepare(**args))["body"] == inspect(prepare(**args, support_profile_version=PROFILE))["body"]
    path = Path(args["engineering_root"]) / "source.inp"
    path.write_text(MODEL + STEP.replace("*END STEP", PRINT + "*END STEP"))
    with pytest.raises(ExecutionError, match="UNSUPPORTED_KEYWORD"):
        prepare(**args)


def test_probe_profile_is_bounded_readonly_and_not_an_execution_plan(tmp_path):
    args = probe_case(tmp_path); before = inventory(tmp_path)
    value = inspect(prepare(**args))
    assert value["body"]["support_profile_version"] == PROBE_PROFILE
    assert value["body"]["checks"]["real_execution_capability"] == "UNAVAILABLE"
    assert value["body"]["checks"]["solver_conclusion"] == "NOT_RUN"
    assert value["body"]["execution_plan_compatible"] is False
    assert value["content_digest"] == inspect(prepare(**args))["content_digest"]
    assert inventory(tmp_path) == before
    value["body"]["support_profile_version"] = PROFILE
    value["content_digest"] = digest(value["body"])
    with pytest.raises(ExecutionError, match="INVALID_PREVIEW"):
        inspect(AbaqusPlanPreview.from_dict(value))


@pytest.mark.parametrize("old,new,code", [
    ("FREQUENCY=1", "FREQUENCY=0", "UNSUPPORTED_PARAMETER"),
    ("GLOBAL=YES", "GLOBAL=NO", "UNSUPPORTED_PARAMETER"),
    ("SUMMARY=NO", "SUMMARY=YES", "UNSUPPORTED_PARAMETER"),
    ("TOTALS=NO", "TOTALS=YES", "UNSUPPORTED_PARAMETER"),
    ("POSITION=INTEGRATION POINTS", "POSITION=NODES", "UNSUPPORTED_PARAMETER"),
    ("*EL PRINT, ELSET=BAR", "*EL PRINT, ELSET=OTHER", "UNSUPPORTED_PARAMETER"),
    ("U\nRF\n", "U1\nRF1\n", "UNSUPPORTED_DATA"),
    ("\nS\n", "\nS, E\n", "UNSUPPORTED_DATA"),
    ("GLOBAL=YES", "GLOBAL=YES, INPUT=outside", "UNSUPPORTED_PARAMETER"),
])
def test_only_exact_print_subset_is_supported(tmp_path, old, new, code):
    args = probe_case(tmp_path)
    path = Path(args["engineering_root"]) / "source.inp"
    path.write_text(path.read_text().replace(old, new))
    with pytest.raises(ExecutionError, match=code):
        prepare(**args)


@pytest.mark.parametrize("mode", ["missing", "duplicate", "model_section"])
def test_print_request_presence_and_placement(tmp_path, mode):
    args = probe_case(tmp_path)
    path = Path(args["engineering_root"]) / "source.inp"
    text = MODEL + STEP if mode == "missing" else (
        MODEL + STEP.replace("*END STEP", PRINT * 2 + "*END STEP") if mode == "duplicate"
        else MODEL + PRINT + STEP)
    path.write_text(text)
    with pytest.raises(ExecutionError, match="UNSUPPORTED_STAGE"):
        prepare(**args)


def test_new_preview_refused_before_execution_mutations(harness):
    h = harness; args = probe_case(h.root); value = prepare(**args)
    before = inventory(h.root); counts = h.counts()
    for request in (value, value.to_dict(), {**value.to_dict(), "approved": True, "executable": True}):
        with pytest.raises(ExecutionError):
            h.service.submit(h.context, request)
    assert h.counts() == counts and inventory(h.root) == before


def load_review():
    path = Path(__file__).parents[1] / "examples/agent_first/abaqus_probe_review.py"
    spec = importlib.util.spec_from_file_location("probe_review", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.review


def manifest_for(args):
    path = Path(args["engineering_root"]) / "source.inp"
    data = path.read_bytes()
    body = {"schema_version": "abaqus-first-probe-manifest-v1", "experiment_id": "isolated_test",
            "execution_authorized": False, "prepare_request": args,
            "preview_digest": inspect(prepare(**args))["content_digest"],
            "materials": [{"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}]}
    return {"body": body, "content_digest": digest(body)}


@pytest.mark.parametrize("change,code", [("none", None), ("input", "PACKAGE_CHANGED"),
    ("output", "OUTPUT_EXISTS"), ("profile", "PACKAGE_CHANGED"), ("manifest", "PACKAGE_CHANGED")])
def test_package_recheck_is_readonly_and_detects_changes(tmp_path, change, code):
    args = probe_case(tmp_path); m = manifest_for(args); expected = m["content_digest"]
    root = Path(args["engineering_root"])
    if change == "input": (root / "source.inp").write_bytes(b"**changed\n")
    if change == "output": (root / "candidate.dat").write_bytes(b"prior output")
    if change == "profile":
        m["body"]["prepare_request"]["runtime_profile"]["cpus"] = 2
    if change == "manifest": m["body"]["experiment_id"] = "other"
    before = inventory(tmp_path)
    if code:
        with pytest.raises(ExecutionError) as failure: load_review()(m, expected)
        assert failure.value.code == code
    else:
        result = load_review()(m, expected)
        assert result["execution_authorized"] is False and result["run_created"] is False
    assert inventory(tmp_path) == before


def test_static_metadata_hardlinks_do_not_relax_input_policy(tmp_path):
    args = probe_case(tmp_path); m = manifest_for(args)
    metadata = tmp_path / "installed-component.bin"; metadata.write_bytes(b"static component")
    os.link(metadata, tmp_path / "component-alias.bin")
    m["body"]["materials"].append({"path": str(metadata), "bytes": metadata.stat().st_size,
                                  "sha256": hashlib.sha256(metadata.read_bytes()).hexdigest()})
    m["content_digest"] = digest(m["body"])
    assert load_review()(m, m["content_digest"])["execution_authorized"] is False
    os.link(Path(args["engineering_root"]) / "source.inp", tmp_path / "input-alias.inp")
    with pytest.raises(ExecutionError) as failure:
        load_review()(m, m["content_digest"])
    assert failure.value.code == "UNSUPPORTED_PATH"
