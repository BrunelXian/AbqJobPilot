"""Run006 real Windows fixture supervision; controller evidence never repairs the service."""

from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
from pathlib import Path
import time

import pytest

from abqjobpilot.execution import ExecutionError
from abqjobpilot.execution.models import canonical_json
from abqjobpilot.execution.process_handles import ProcessReference
from supervisor_helpers import ProcessHarness, read_json, wait_until


class FixtureHarness(ProcessHarness):
    def __init__(self, root, scenarios):
        super().__init__(root, process_scenarios=scenarios)
        self.references = {}

    def run_root(self, run_id):
        return Path(self.context.runtime_root) / "process_runs" / run_id

    def capture(self, run_id):
        root = self.run_root(run_id)
        for role in ("launcher", "worker_transport", "worker"):
            wait_until(lambda: (root / (role + ".json")).exists())
            record = read_json(root / (role + ".json"))
            assert record["run_id"] == run_id and record["project_instance_id"] == self.context.project_instance_id
            if (run_id, role) not in self.references:
                self.references[run_id, role] = ProcessReference(record["pid"], record, cleanup=True)
            if role == "launcher" and (run_id, "launcher_transport") not in self.references:
                # This controller's independently retained handle is not supplied to the owner.
                self.references[run_id, "launcher_transport"] = ProcessReference(record["parent_pid"], cleanup=True)
        (root / "controller-observations.json").write_text(canonical_json({role: ref.identity for (rid, role), ref in self.references.items() if rid == run_id}), encoding="utf-8")

    def start(self, scenario_index=0, *, stage="process:after_identity", **options):
        owner = self.owner(barriers=[stage], **options)
        accepted = self.client().submit(self.requests[scenario_index])
        run_id = accepted["receipt"]["run_id"]
        owner.reached(stage)
        if stage != "process:before_create":
            self.capture(run_id)
        return owner, accepted, run_id

    def close(self):
        rows = []
        for (run_id, role), ref in self.references.items():
            code = ref.exit_evidence()
            killed = False
            if code is None:
                api = ref.api
                api.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
                terminated = api.TerminateProcess(ref.handle, 78)
                assert api.WaitForSingleObject(ref.handle, 8000) == 0
                killed = bool(terminated)  # A transport can exit between observation and cleanup.
                code = ref.exit_evidence()
            rows.append({"run_id": run_id, "role": role, "controller_identity": ref.identity,
                         "cleanup_terminated": killed, "exit": code, "handle_closed": True})
            ref.close()
        (self.root / "fixture-lifecycle.json").write_text(canonical_json(rows), encoding="utf-8")
        super().close()
        for child in self.children:
            if (child.control / "io.json").exists():
                io = read_json(child.control / "io.json")
                assert io["all_data_accesses_confined"] and io["launch_and_legacy_traps"]
                assert all(Path(p).is_relative_to(self.root) or p in io["trusted_read_only_execution_objects"] for p in io["paths"])


@pytest.fixture
def factory(tmp_path):
    harnesses = []
    def create(*scenarios):
        root = tmp_path / ("experiment_" + str(len(harnesses)))
        root.mkdir()
        h = FixtureHarness(root, list(scenarios))
        harnesses.append(h)
        return h
    yield create
    for h in harnesses:
        h.close()


def assert_once(h, run_id):
    launches = [r for c in h.children for r in (read_json(c.control / "physical-launches.json")
                if (c.control / "physical-launches.json").exists() else []) if r["run_id"] == run_id]
    assert len(launches) == 1
    assert launches[0]["identity"] == h.references[run_id, "launcher_transport"].identity
    events = h.client().events()
    assert sum(e["run_id"] == run_id and e["type"] == "START_INTENT" for e in events) == 1
    run = h.client().run(run_id)
    assert len(run["process_records"]) == 4
    for item in run["process_records"]:
        ref = h.references[run_id, item["role"]]
        assert item["pid"] == ref.identity["pid"] and item["creation_time_100ns"] == ref.identity["creation_time_100ns"]
    return run


@pytest.mark.parametrize("scenario,backend,artifact", [("normal", "COMPLETED", "VALID"),
                            ("nonzero", "FAILED", "VALID"), ("invalid_result", "COMPLETED", "INVALID")])
def test_real_process_exit_and_independent_artifact_dimensions(factory, scenario, backend, artifact):
    h = factory(scenario)
    owner, accepted, rid = h.start()
    run = h.client().run(rid)
    assert run["execution"] == "START_INTENT" and run["exit_verification"] == "UNKNOWN"
    assert h.client().receipt("key-0") == accepted["receipt"]
    assert h.references[rid, "worker"].exit_evidence() is None
    owner.release("process:after_identity")
    run = h.finished(rid)
    assert_once(h, rid)
    assert run["backend_outcome"] == backend and run["artifact_validation"] == artifact
    assert run["solver_conclusion"] == "NOT_RUN" and run["exit_verification"] == "VERIFIED"
    assert len(run["process_exits"]) == 4 and all(r["exit_source"] == "retained_windows_handle" for r in run["process_exits"])
    assert next(e for e in run["process_exits"] if e["role"] == "worker")["exit_code"] == (23 if scenario == "nonzero" else 0)
    report = h.client().diagnose(rid)
    assert report["body"]["report_version"] == "af-run-diagnostic-v2"
    assert "FAKE_COMPLETED" not in [d["reason_code"] for d in report["body"]["diagnostics"]]
    export = h.root / "exports"
    export.mkdir()
    h.client().export_diagnostic(report, export_root=export, target=export / "normal.json")
    assert json.loads((export / "normal.json").read_text()) == report


@pytest.mark.parametrize("scenario", ["launcher_early", "result_wait"])
def test_launcher_exit_and_result_do_not_end_worker_or_release_slot(factory, scenario):
    h = factory(scenario, "result_wait")
    owner, accepted, rid = h.start(repeat_barriers=["process:after_identity"])
    second = h.client().submit(h.requests[1])["receipt"]["run_id"]
    owner.release("process:after_identity")
    wait_until(lambda: h.references[rid, "launcher"].exit_evidence())
    wait_until(lambda: h.client().run(rid)["process_exits"])
    if scenario == "result_wait":
        wait_until(lambda: (h.run_root(rid) / "result.json").exists())
    assert h.references[rid, "worker"].exit_evidence() is None
    run = h.client().run(rid)
    assert run["execution"] == "START_INTENT" and run["exit_verification"] == "PARTIAL"
    assert run["artifact_validation"] == "NOT_RUN" and h.client().run(second)["queue_state"] == "PENDING"
    assert not h.run_root(second).exists()
    report = h.client().diagnose(rid)
    assert "PROCESS_EXIT_NOT_ESTABLISHED" in [d["reason_code"] for d in report["body"]["diagnostics"]]
    (h.run_root(rid) / "release.json").write_text("{}")
    h.finished(rid)
    owner.reached("process:after_identity:2")
    h.capture(second)
    owner.release("process:after_identity:2")
    (h.run_root(second) / "release.json").write_text("{}")
    h.finished(second)


@pytest.mark.parametrize("stage", ["process:before_create", "process:after_create", "process:after_identity", "process:after_handoff", "process:before_exit_record", "process:after_exit", "process:before_terminal"])
def test_actual_owner_crash_windows_preserves_uncertainty_no_relaunch(factory, stage):
    h = factory("result_wait" if stage in {"process:after_create", "process:after_identity", "process:after_handoff"} else "normal", "normal")
    if stage in {"process:after_exit", "process:before_terminal", "process:after_handoff", "process:before_exit_record"}:
        owner = h.owner(barriers=["process:after_identity", stage])
        accepted = h.client().submit(h.requests[0])
        rid = accepted["receipt"]["run_id"]
        owner.reached("process:after_identity")
        h.capture(rid)
        owner.release("process:after_identity")
        owner.reached(stage)
        if stage == "process:after_handoff":
            wait_until(lambda: (h.run_root(rid) / "result.json").exists())
            wait_until(lambda: h.references[rid, "launcher"].exit_evidence())
        if stage == "process:before_exit_record":
            wait_until(lambda: all(ref.exit_evidence() for (r, _), ref in h.references.items() if r == rid))
    else:
        owner, accepted, rid = h.start(stage=stage)
    other = h.client().submit(h.requests[1])["receipt"]["run_id"]
    before = h.client().run(rid)
    if stage == "process:before_exit_record":
        assert before["process_exits"] == [] and before["exit_verification"] == "UNKNOWN"
    owner.terminate()  # Actual retained Windows handle, no service finally.
    worker_survived = False
    if stage in {"process:after_create", "process:after_identity", "process:after_handoff"}:
        worker_survived = h.references[rid, "worker"].exit_evidence() is None
        assert worker_survived
    fresh = h.owner(management_control=True)
    assert fresh.identity["pid"] != owner.identity["pid"]
    assert not h.client().health()["dispatch_enabled"]
    if worker_survived:
        assert h.references[rid, "worker"].exit_evidence() is None
    run = h.client().run(rid)
    assert run["reconciliation_requirement"] == "RECONCILIATION_REQUIRED"
    assert run["revision"] == before["revision"] and h.client().receipt("key-0") == accepted["receipt"]
    assert h.client().submit(h.requests[0])["receipt"] == accepted["receipt"]
    assert h.client().run(other)["queue_state"] == "PENDING" and not h.run_root(other).exists()
    if stage in {"process:before_create", "process:after_create"}:
        assert run["process_records"] == [] and run["exit_verification"] == "UNKNOWN"
    if stage == "process:before_create":
        assert not (h.run_root(rid) / "launcher.json").exists()
    if stage == "process:after_exit":
        assert len(run["process_exits"]) == 4 and run["exit_verification"] == "PARTIAL"
    preview = h.client().preview_reconciliation(rid)
    assert preview["candidate_action"] is None
    assert preview["reasons"][0]["code"] == "UNSUPPORTED_EVIDENCE_POLICY"
    from test_reconciliation_supervisor import permit
    from reconciliation_helpers import adoption_scope
    from abqjobpilot.execution.reconciliation import ADOPT, RESUME
    adopt = permit(h, fresh, ADOPT, adoption_scope(preview), "reject-process-adoption")
    with pytest.raises(ExecutionError) as error:
        h.client().apply_reconciliation(adopt)
    assert error.value.code == "EVIDENCE_INSUFFICIENT"
    resume = permit(h, fresh, RESUME, {"expected_gate_version": h.client().dispatch_gate()["version"]}, "reject-process-resume")
    with pytest.raises(ExecutionError) as error:
        h.client().resume_dispatch(resume)
    assert error.value.code == "RECONCILIATION_REQUIRED"
    assert h.client().reconciliations(rid) == [] and h.client().run(rid)["revision"] == before["revision"]
    launches = [r for c in h.children for r in (read_json(c.control / "physical-launches.json")
                if (c.control / "physical-launches.json").exists() else [])]
    assert len(launches) == (0 if stage == "process:before_create" else 1)
    report = h.client().diagnose(rid)
    export = h.root / "exports"
    export.mkdir()
    h.client().export_diagnostic(report, export_root=export, target=export / "blocked.json")
    (h.root / "crash-evidence.json").write_text(canonical_json({"stage": stage, "old_owner": owner.identity,
            "new_owner": fresh.identity, "worker_survived_owner": worker_survived,
            "service_before": before, "service_after": run,
            "controller_exit_observations": {role: ref.exit_evidence() for (r, role), ref in h.references.items() if r == rid},
            "physical_launches": launches}), encoding="utf-8")


def test_actual_candidate_identity_mismatch_blocks_owner_without_guessing(factory):
    h = factory("normal")
    owner, accepted, rid = h.start(stage="process:after_create")
    path = h.run_root(rid) / "worker.json"
    candidate = read_json(path)
    path.write_text(canonical_json({**candidate, "creation_time_100ns": candidate["creation_time_100ns"] + 1}))
    owner.release("process:after_create")
    wait_until(lambda: not h.client().health()["dispatch_enabled"])
    run = h.client().run(rid)
    assert run["exit_verification"] == "UNKNOWN" and run["execution"] == "BLOCKED"
    assert h.references[rid, "worker"].exit_evidence() is None
    assert run["process_records"] == [] and not (h.run_root(rid) / "result.json").exists()
    assert h.client().submit(h.requests[0])["receipt"] == accepted["receipt"]


def test_fixture_does_not_inherit_private_owner_environment(factory, monkeypatch):
    monkeypatch.setenv("ABQ_R6_PRIVATE_SENTINEL", "PRIVATE_PROCESS_SECRET_DO_NOT_PASS")
    h = factory("normal")
    owner, accepted, rid = h.start()
    for role in ("launcher", "worker"):
        candidate = read_json(h.run_root(rid) / (role + ".json"))
        assert "ABQ_R6_PRIVATE_SENTINEL" not in candidate["environment_keys"]
        assert set(candidate["environment_keys"]) <= {"SystemRoot", "SYSTEMROOT", "PYTHONDONTWRITEBYTECODE"}
    assert all(h.credential not in p.read_text() for p in h.run_root(rid).glob("*.json"))
    owner.release("process:after_identity")
    h.finished(rid)


def test_multiclient_replay_lost_response_and_client_exit_do_not_start_twice(factory):
    h = factory("result_wait")
    owner = h.owner(barriers=["submit:before_response", "process:after_identity"])
    child = h.spawn("client", operation="submit", arguments={"request": h.requests[0]})
    owner.reached("submit:before_response")
    owner.reached("process:after_identity")
    rid = h.client().receipt("key-0")["run_id"]
    h.capture(rid)
    child.terminate()
    with ThreadPoolExecutor(max_workers=4) as pool:
        replies = list(pool.map(lambda _: h.client().submit(h.requests[0]), range(4)))
    assert all(r["receipt"]["run_id"] == rid and r["replayed"] for r in replies)
    owner.release("submit:before_response")
    owner.release("process:after_identity")
    wait_until(lambda: (h.run_root(rid) / "result.json").exists())
    assert h.references[rid, "worker"].exit_evidence() is None
    (h.run_root(rid) / "release.json").write_text("{}")
    h.finished(rid)
    assert_once(h, rid)


def test_identity_mismatch_is_not_exit_or_permission_to_kill(factory):
    h = factory("result_wait")
    owner, accepted, rid = h.start()
    identity = h.references[rid, "worker"].identity
    with pytest.raises(ExecutionError, match="candidate") as error:
        ProcessReference(identity["pid"], {**identity, "creation_time_100ns": identity["creation_time_100ns"] + 1})
    assert error.value.code == "PROCESS_IDENTITY_MISMATCH"
    assert h.references[rid, "worker"].exit_evidence() is None
    with pytest.raises(ExecutionError) as error:
        ProcessReference(0xFFFFFFFE)
    assert error.value.code == "PROCESS_IDENTITY_UNKNOWN"
    owner.release("process:after_identity")
    (h.run_root(rid) / "release.json").write_text("{}")
    h.finished(rid)


@pytest.mark.parametrize("fault", ["process_observe:before_commit", "terminal:before_commit"])
def test_post_creation_storage_failure_never_releases_claim_or_restarts(factory, fault):
    h = factory("normal", "normal")
    stage = "process:after_create" if fault.startswith("process_observe") else "process:after_identity"
    owner, accepted, rid = h.start(stage=stage, faults=[fault])
    other = h.client().submit(h.requests[1])["receipt"]["run_id"]
    owner.release(stage)
    wait_until(lambda: not h.client().health()["dispatch_enabled"])
    run = h.client().run(rid)
    assert run["reconciliation_requirement"] == "RECONCILIATION_REQUIRED" and run["execution"] != "FINISHED"
    assert h.client().run(other)["execution"] == "PLANNED"
    assert not h.run_root(other).exists()
    assert h.client().submit(h.requests[0])["receipt"] == accepted["receipt"]
    if fault.startswith("process_observe"):
        assert run["process_records"] == [] and run["exit_verification"] == "UNKNOWN"
        assert h.references[rid, "worker"].exit_evidence() is None
    else:
        assert run["exit_verification"] == "VERIFIED" and h.client().validations(rid) == []


def test_process_diagnosis_is_historical_readonly_redacted(factory, monkeypatch):
    h = factory("result_wait")
    owner, accepted, rid = h.start()
    owner.terminate()
    h.owner()
    from abqjobpilot.execution.store import open_existing_read_only
    from execution_helpers import inventory
    reader = open_existing_read_only(h.context)
    before = inventory(Path(h.context.root))
    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only report must not probe or execute a process")
    monkeypatch.setattr(ProcessReference, "__init__", forbidden)
    report = reader.diagnose(h.context, rid)
    assert inventory(Path(h.context.root)) == before
    encoded = canonical_json(report)
    assert h.credential not in encoded and str(h.root) not in encoded
    assert h.process_config.interpreter not in encoded
    assert report["body"]["facts"]["run"]["exit_verification"] == "UNKNOWN"
    assert len(report["body"]["facts"]["run"]["process_records"]) == 4
    assert "LIVE_PROCESS_NOT_OBSERVED" in report["body"]["unknowns"]


def test_exit_code_query_failure_on_real_exited_reference_is_unknown(factory, monkeypatch):
    h = factory("normal")
    owner, accepted, rid = h.start()
    owner.release("process:after_identity")
    h.finished(rid)
    reference = h.references[rid, "worker"]
    assert reference.exit_evidence()["exit_code"] == 0
    with monkeypatch.context() as patch:
        patch.setattr(reference.api, "GetExitCodeProcess", lambda *args: 0)
        with pytest.raises(ExecutionError) as error:
            reference.exit_evidence()
        assert error.value.code == "PROCESS_EXIT_UNKNOWN"
    assert reference.exit_evidence()["exit_code"] == 0
