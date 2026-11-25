"""Isolated TEST_ONLY candidate identity, authorization and budget tests."""

from pathlib import Path

import pytest

from abqjobpilot.execution import ExecutionError
from abqjobpilot.execution.models import RESOURCES, bytes_digest, canonical_json, now
from execution_helpers import guard_environment
from test_delegated_grant import ADMISSION, approve, delegated, make_harness

DECK = """*HEADING
Static rod fixture
*NODE
1, 0, 0, 0
2, 0, 2, 0
*ELEMENT, TYPE=T3D2, ELSET=BAR
1, 1, 2
*INCLUDE, INPUT=material.inp
*STEP
*STATIC
0.1, 1, 0.0001, 1
*BOUNDARY
1, 1, 3, 0
*CLOAD
2, 2, -50
*END STEP
"""
MATERIAL = """*MATERIAL, NAME=ROD
*ELASTIC
1000, 0.3
*SOLID SECTION, ELSET=BAR, MATERIAL=ROD
1
"""


def candidate(h, name="candidate_a", *, deck=DECK, includes=("material.inp",)):
    root = Path(h.context.root) / "inputs" / name
    root.mkdir()
    (root / "main.inp").write_bytes(deck.encode("ascii"))
    (root / "material.inp").write_bytes(MATERIAL.encode("ascii"))
    return root, {"candidate_id": name, "main": "main.inp", "includes": list(includes)}


def prepared(h, evidence, *, resources=ADMISSION):
    root = Path(evidence["working_directory"])
    spec = h.spec(job_id=evidence["candidate_id"], input_refs=[str(root / item["reference"]) for item in evidence["files"]])
    return h.service.prepare(h.context, spec, h.config, expires_at=now() + 3600,
                             delegated_resources=resources, candidate=evidence)


def test_distinct_candidates_bind_receipts_without_dispatch(delegated):
    h = delegated
    a, first = candidate(h)
    b, second = candidate(h, "candidate_b", deck=DECK.replace("-50", "-73"))
    reviewed = [h.service.preflight_inp(h.context, request) for request in (first, second)]
    assert reviewed[0]["main_sha256"] != reviewed[1]["main_sha256"]
    plans = [prepared(h, item) for item in reviewed]
    grant = approve(h, *plans)
    receipts = []
    for index, (plan, expected, root) in enumerate(zip(plans, reviewed, (a, b))):
        request = h.request(plan, grant["grant_id"], f"candidate-{index}")
        accepted = h.service.submit(h.context, request, delegated_only=True)["receipt"]
        receipts.append(accepted)
        assert h.service.submit(h.context, request)["receipt"] == accepted
        run = h.store.query_run(h.context, accepted["run_id"])
        binding = accepted["input_binding"]
        assert binding == run["input_binding"] and binding["plan_digest"] == plan.to_dict()["plan_digest"]
        assert binding["project_id"] == h.context.project_id and binding["grant_id"] == grant["grant_id"]
        assert grant["plans"][binding["plan_id"]] == binding["plan_digest"]
        assert binding["main_sha256"] == bytes_digest((root / "main.inp").read_bytes())
        assert binding["input_manifest_digest"] == expected["input_manifest_digest"]
        assert binding["v0"] == "INPUT_BOUND" and binding["v1"] == "STATIC_SUBSET_PASS" and binding["v2"] == "NOT_RUN"
        assert run["admission_only"] is True and run["solver_conclusion"] == "NOT_RUN"
    assert h.store.delegated_budget(h.context, grant["grant_id"])["consumed"] == 2
    assert h.store.pending_for_owner() is None and not list(Path(h.context.runtime_root).rglob("*"))
    (h.root / "controlled-inp-proof.json").write_text(canonical_json(receipts), encoding="utf-8")


@pytest.mark.parametrize("file, replacement", [
    ("main.inp", DECK.replace("-50", "-49").encode("ascii")),
    ("material.inp", MATERIAL.replace("1000", "1200").encode("ascii")),
    ("material.inp", None),
])
def test_changed_input_cannot_be_prepared_or_reuse_a_grant(delegated, file, replacement):
    h = delegated
    root, request = candidate(h)
    evidence = h.service.preflight_inp(h.context, request)
    plan = prepared(h, evidence)
    grant = approve(h, plan)
    original = h.request(plan, grant["grant_id"])
    accepted = h.service.submit(h.context, original)["receipt"]
    path = root / file
    if replacement is None:
        copy = root / "replace.inp"
        copy.write_bytes(path.read_bytes())
        copy.replace(path)
    else:
        path.write_bytes(replacement)
    for operation in (lambda: prepared(h, evidence),
                      lambda: h.service.submit(h.context, {**original, "idempotency_key": "new-key"})):
        with pytest.raises(ExecutionError) as rejected:
            operation()
        assert rejected.value.code == "INPUT_CHANGED"
    assert h.service.submit(h.context, original)["receipt"] == accepted
    assert h.store.delegated_budget(h.context, grant["grant_id"])["consumed"] == 1


@pytest.mark.parametrize("scenario, code", [
    ("escape", "UNSUPPORTED_PATH"), ("include", "INCLUDE_NOT_APPROVED"),
    ("hardlink", "UNSUPPORTED_PATH"), ("syntax", "UNSUPPORTED_KEYWORD"),
    ("unused", "INPUT_DECLARATION_MISMATCH"), ("command", "INVALID_REQUEST"),
    ("extra_file", "INPUT_DIRECTORY_NOT_CLOSED"),
])
def test_preflight_refuses_inputs_outside_the_closed_profile(delegated, scenario, code):
    h = delegated
    root, request = candidate(h)
    main = root / "main.inp"
    if scenario == "escape":
        main.write_bytes(DECK.replace("material.inp", "../material.inp").encode("ascii"))
    elif scenario == "include":
        request["includes"] = []
    elif scenario == "hardlink":
        link = root / "material.inp"
        outside = h.root / "outside.inp"
        link.replace(outside)
        link.hardlink_to(outside)
    elif scenario == "syntax":
        main.write_bytes(DECK.replace("*STEP", "*USER ELEMENT\n*STEP").encode("ascii"))
    elif scenario == "unused":
        request["includes"].append("unused.inp")
    elif scenario == "extra_file":
        (root / "abaqus_v6.env").write_text("unapproved input", encoding="ascii")
    else:
        request["command"] = "untrusted"
    with pytest.raises(ExecutionError) as rejected:
        h.service.preflight_inp(h.context, request)
    assert rejected.value.code == code
    assert h.counts()["runs"] == 0


def test_cross_project_evidence_and_resource_overrun_refused(delegated):
    h = delegated
    _, request = candidate(h)
    evidence = h.service.preflight_inp(h.context, request)
    root = h.root / "other"
    root.mkdir()
    other = make_harness(root)
    try:
        with pytest.raises(ExecutionError) as rejected:
            prepared(other, evidence)
        assert rejected.value.code == "PROJECT_IDENTITY_MISMATCH"
    finally:
        other.store.close()
    plan = prepared(h, evidence, resources={**ADMISSION, "wall_seconds": ADMISSION["wall_seconds"] + 1})
    grant = approve(h, plan, resource_limits={**RESOURCES, **ADMISSION})
    with pytest.raises(ExecutionError) as rejected:
        h.service.submit(h.context, h.request(plan, grant["grant_id"]))
    assert rejected.value.code == "RESOURCE_LIMIT"
    assert h.store.delegated_budget(h.context, grant["grant_id"])["consumed"] == 0


def test_input_sharing_lock_survives_until_accept_commit(delegated, monkeypatch):
    h = delegated
    root, request = candidate(h)
    plan = prepared(h, h.service.preflight_inp(h.context, request))
    grant = approve(h, plan)
    checked = []

    def inspect(stage):
        if stage == "accept:before_commit":
            for name in ("main.inp", "material.inp"):
                with pytest.raises(PermissionError):
                    (root / name).write_bytes(b"unexpected")
                checked.append(name)

    monkeypatch.setattr(h.store, "_checkpoint", inspect)
    h.service.submit(h.context, h.request(plan, grant["grant_id"]))
    assert checked == ["main.inp", "material.inp"]
