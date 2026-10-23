"""Trusted TEST_ONLY operator. Preprovisions one result_wait plan; no tests imports.

This is a developer demonstration, not an approval UI. Only this operator starts
the owner, issues grants, releases the fixed fixture and cleans its own processes.
"""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--mode", choices=["demo", "owner"], default="demo")
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    from abqjobpilot.execution import ConfigSnapshot, ExecutionService, ExperimentStore, JobSpec, create_experiment
    from abqjobpilot.execution.client import FakeClient
    from abqjobpilot.execution.models import CONTRACT, RESOURCES, canonical_json, now, require
    from abqjobpilot.execution.ownership import current_process_identity
    from abqjobpilot.execution.paths import confined
    from abqjobpilot.execution.process_backend import ProcessFixtureConfig
    from abqjobpilot.execution.process_handles import ProcessReference
    from abqjobpilot.execution.supervisor import FakeSupervisor, load_bootstrap
    from abqjobpilot.execution.test_authority import issue_process_execution, issue_validation

    root = confined(Path(tempfile.gettempdir()), args.root)
    private, session, control = root / "operator_private", root / "client_session", root / "control"
    def write(path, value):
        path = confined(root, path)
        pending = path.with_name(path.name + ".partial")
        with pending.open("x", encoding="utf-8") as stream:
            stream.write(canonical_json(value)); stream.flush(); os.fsync(stream.fileno())
        pending.rename(path)  # Windows refuses an existing target; readers see complete JSON.
    def read(path):
        path = confined(root, path, exists=True)
        require(path.stat().st_size < 65536, "LIMIT_EXCEEDED", "Operator material exceeds bound")
        return json.loads(path.read_text(encoding="utf-8"))
    def wait(predicate, seconds=20):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            result = predicate()
            if result: return result
            time.sleep(0.02)
        raise RuntimeError("Bounded operator condition timed out")

    if args.mode == "owner":
        write(control / "owner-identity.json", current_process_identity())
        wait(lambda: (control / "owner-bound.json").exists())
        context, bootstrap = load_bootstrap(root, private / "bootstrap.json")
        setup = read(private / "setup.json")
        attempts = []
        # CPython's native audit hook observes every Popen attempt in this owner;
        # it neither substitutes Popen nor drives execution or client decisions.
        def audit(event, values):
            if event == "subprocess.Popen":
                argv = values[1]
                expected = [setup["process_config"]["interpreter"], "-I", "-S", "-B",
                            str(args.source.resolve() / "abqjobpilot/execution/process_fixture.py"), "--role", "launcher", "--directory"]
                # Windows audits the already-quoted command line, not necessarily a list.
                roots = list((Path(context.runtime_root) / "process_runs").iterdir())
                matches = [p for p in roots if argv == subprocess.list2cmdline(expected + [str(p)])
                           or argv == expected + [str(p)]]
                require(len(matches) == 1, "INVALID_REQUEST", "Only the fixed fixture may launch")
                confined(context.test_root, matches[0], exists=True)
                attempts.append({"attempt": len(attempts) + 1, "run_id": matches[0].name, "source": "cpython_subprocess_audit_before_os_create"})
                write(control / ("launch-attempt-" + str(len(attempts)) + ".json"), attempts[-1])
            if event == "import" and values[0] in {"abqjobpilot.config", "abqjobpilot.runner_core", "abqjobpilot.gui_app", "pytest"}:
                raise RuntimeError("Legacy/test dependency forbidden in standalone operator")
        sys.addaudithook(audit)
        owner = FakeSupervisor(context, bootstrap, process_config=ProcessFixtureConfig(**setup["process_config"]))
        stopped = threading.Event()
        def command_loop():
            expires = time.monotonic() + 90
            issued = False
            while not stopped.wait(0.02):
                if (control / "stop.json").exists() or time.monotonic() >= expires:
                    stopped.set(); return
                if not issued and (private / "approve-validation.json").exists():
                    command = read(private / "approve-validation.json")
                    require(set(command) == {"run_id"}, "INVALID_REQUEST", "Only exact validation approval supported")
                    run = owner.store.query_run(context, command["run_id"])
                    require(run["plan_id"] == setup["approved_plan_id"], "GRANT_SCOPE_MISMATCH", "Operator did not approve this plan")
                    ticket = issue_validation(owner.service, run["run_id"], expires_at=now() + 120)
                    write(private / "validation-ticket.json", ticket)
                    issued = True
        def commands():
            try: command_loop()
            except Exception:
                write(control / "operator-control-error.json", {"code": "OPERATOR_CONTROL_FAILED"})
                stopped.set()
        watcher = threading.Thread(target=commands, name="trusted-test-operator-control")
        watcher.start()
        try: owner.serve(stopped)
        finally: stopped.set(); watcher.join(2)
        return 0

    root.mkdir(exist_ok=False)
    for path in (private, session, control, root / "exports", root / "non_repository_cwd"): path.mkdir()
    write(root / "recent-fixture.json", {"untouched": True})
    source = root / "input.txt"; source.write_text("fixed public client fixture", encoding="utf-8")
    context = create_experiment(root, root / "project")
    store = ExperimentStore(context)
    configuration = ProcessFixtureConfig.current()
    service = ExecutionService(context, store, client_namespace="public-example", process_config=configuration)
    spec = JobSpec.from_dict({"job_id": "public_example_job", "revision": 1,
          "project_id": context.project_id, "project_instance_id": context.project_instance_id,
          "input_refs": [str(source)], "resources": dict(RESOURCES), "metadata": {"label": "TEST_ONLY public example"}})
    plan = service.prepare(context, spec, ConfigSnapshot.from_dict({"config_revision": 1, "values": {"label": "explicit TEST_ONLY"}}),
                           expires_at=now() + 600, process_scenario="result_wait").to_dict()
    grant = issue_process_execution(service, plan["plan_id"], expires_at=now() + 600)
    credential = secrets.token_urlsafe(36)
    bootstrap = {"context": context.to_dict(), "authority_instance": store._session.authority_instance,
                 "credential": credential, "client_namespace": "public-example", "endpoint_file": str(root / "endpoint.json")}
    write(private / "bootstrap.json", bootstrap)
    write(private / "setup.json", {"process_config": asdict(configuration), "approved_plan_id": plan["plan_id"]})
    request = {"contract_version": CONTRACT, "operation": "submit", "project_id": context.project_id,
               "project_instance_id": context.project_instance_id, "job_id": plan["job_id"], "job_revision": plan["job_revision"],
               "plan_id": plan["plan_id"], "plan_digest": plan["plan_digest"], "grant_id": grant,
               "idempotency_key": "public-example-request-1", "retry_of": None}
    write(private / "offer.json", {"request": request})
    store.close()
    children, references, lifecycle = [], [], []
    env = {"SystemRoot": os.environ["SystemRoot"], "PYTHONDONTWRITEBYTECODE": "1", "TEMP": str(root), "TMP": str(root)}
    script = Path(__file__).resolve(); client_script = script.with_name("client_workflow.py")
    def spawn(command, name):
        stdout = (control / (name + ".stdout.txt")).open("wb")
        stderr = (control / (name + ".stderr.txt")).open("wb")
        process = subprocess.Popen(command, cwd=str(root / "non_repository_cwd"), env=env,
                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, shell=False, close_fds=True,
                    creationflags=subprocess.CREATE_NO_WINDOW)
        ref = ProcessReference(process.pid, cleanup=True)
        references.append((name + "_transport", ref))
        children.append((name, process, stdout, stderr))
        return process
    owner_process = None
    try:
        owner_process = spawn([sys.executable, "-B", str(script), "--source", str(args.source.resolve()), "--root", str(root), "--mode", "owner"], "owner")
        identity = wait(lambda: read(control / "owner-identity.json") if (control / "owner-identity.json").exists() else None)
        require(identity["parent_pid"] == owner_process.pid or identity["pid"] == owner_process.pid,
                "PROCESS_IDENTITY_MISMATCH", "Explicit owner launch identity differs")
        references.append(("owner", ProcessReference(identity["pid"], identity, cleanup=True)))
        write(control / "owner-bound.json", {})
        endpoint = wait(lambda: read(root / "endpoint.json") if (root / "endpoint.json").exists() else None)
        write(private / "connection.json", {"endpoint": endpoint, "credential": credential})
        client = FakeClient(endpoint, credential)
        command = [sys.executable, "-B", str(client_script), "--source", str(args.source.resolve()),
                   "--connection", str(private / "connection.json"), "--offer", str(private / "offer.json"), "--session", str(session)]
        a = spawn(command + ["--phase", "submit"], "client_A")
        require(a.wait(timeout=30) == 0, "CLIENT_FAILED", "Client A failed; inspect sanitized session errors")
        received = read(session / "session.json"); rid = received["run_id"]
        run = wait(lambda: (r if len((r := client.run(rid))["process_records"]) == 4 else None))
        for member in run["process_records"]:
            # The launcher may already have exited. Its retained-handle exit is
            # recorded by the service; only waiting workers need controller cleanup references.
            if member["role"] in {"worker", "worker_transport"}:
                references.append((member["role"], ProcessReference(member["pid"], member, cleanup=True)))
        worker = next(ref for name, ref in references if name == "worker")
        require(worker.exit_evidence() is None and a.poll() == 0, "PROCESS_EXIT_UNKNOWN", "Worker must outlive exited client A")
        write(control / "client-exit-owner-continues.json", {"client_A_exited": True, "owner_running": owner_process.poll() is None,
              "worker_identity": worker.identity, "worker_exit_not_yet_observed": True,
              "source": "operator_cleanup_observation_not_client_business_evidence"})
        # Only the trusted operator releases the already-authorized fixed result_wait fixture.
        release = confined(root, Path(context.runtime_root) / "process_runs" / rid / "release.json")
        write(release, {})
        wait(lambda: client.run(rid)["execution"] == "FINISHED")
        write(private / "approve-validation.json", {"run_id": rid})
        wait(lambda: (private / "validation-ticket.json").exists())
        b = spawn(command + ["--phase", "complete", "--validation-ticket", str(private / "validation-ticket.json"),
                             "--export-root", str(root / "exports")], "client_B")
        require(b.wait(timeout=30) == 0, "CLIENT_FAILED", "Client B failed; inspect sanitized session errors")
        after = client.run(rid)
        require(after["process_records"] == run["process_records"] and len(list(control.glob("launch-attempt-*.json"))) == 1,
                "STATE_CONFLICT", "Replay must not create another physical launch")
        require(len(after["process_exits"]) == 4 and all(e["exit_code"] == 0 and e["exit_source"] == "retained_windows_handle"
                                                       for e in after["process_exits"]), "PROCESS_EXIT_UNKNOWN", "All fixed members must have OS exit evidence")
        write(root / "workflow-evidence.json", {"scope": "TEST_ONLY_preprovisioned_plan_and_grants", "run_id": rid,
              "project_instance_id": context.project_instance_id, "client_A_pid": read(session / "accepted.json")["client_pid"],
              "client_B_pid": read(session / "complete.json")["client_pid"], "owner_pid": identity["pid"],
              "non_repository_cwd": str(root / "non_repository_cwd"), "launch_attempts": 1,
              "os_verified_members": [{k: m[k] for k in ("role", "pid", "creation_time_100ns")} for m in run["process_records"]],
              "service_recorded_exits": [{k: m[k] for k in ("role", "pid", "creation_time_100ns", "exit_code", "exit_source")} for m in after["process_exits"]],
              "original_receipt_preserved": client.receipt(request["idempotency_key"]) == received["receipt"],
              "client_import_and_execution_guard": True, "recent_unchanged": read(root / "recent-fixture.json") == {"untouched": True}})
        return 0
    finally:
        # Close only processes created here. Retained references cannot be redirected by PID reuse.
        if owner_process is not None and owner_process.poll() is None:
            write(control / "stop.json", {})
        cleanup_errors = []
        # Allow normal owner shutdown first; failures must not skip exact-handle cleanup.
        if owner_process is not None:
            try: owner_process.wait(timeout=50)  # Fixed workers expire within 40s, even if a demo step fails.
            except subprocess.TimeoutExpired: pass
        for name, reference in references:
            try:
                evidence = reference.exit_evidence()
                if evidence is None:
                    import ctypes
                    reference.api.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
                    terminated = bool(reference.api.TerminateProcess(reference.handle, 79))
                    require(terminated or reference.exit_evidence() is not None, "PROCESS_EXIT_UNKNOWN", "Owned test cleanup failed")
                    require(reference.api.WaitForSingleObject(reference.handle, 8000) == 0, "PROCESS_EXIT_UNKNOWN", "Owned test did not exit")
                    evidence = reference.exit_evidence()
                lifecycle.append({"role": name, "identity": reference.identity, "exit": evidence, "handle_closed": True})
            except Exception:
                cleanup_errors.append(name)
            finally: reference.close()
        for name, process, stdout, stderr in children:
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: cleanup_errors.append(name)
            finally: stdout.close(); stderr.close()
        write(root / "lifecycle.json", lifecycle)
        removed = []
        for path in private.glob("*.json"):
            removed.append(path.name); path.unlink()
        require(not any(credential.encode() in p.read_bytes() for p in root.rglob("*") if p.is_file()),
                "SECRET_LEAK", "Connection credential escaped private handoff")
        write(root / "cleanup.json", {"private_materials_removed": removed, "remaining_private_files": len(list(private.iterdir())),
              "all_children_waited": all(p.poll() is not None for _, p, _, _ in children), "all_handles_closed": True,
              "cleanup_errors": cleanup_errors})
        require(not cleanup_errors, "PROCESS_EXIT_UNKNOWN", "Inspect exact-identity cleanup report")


if __name__ == "__main__":
    raise SystemExit(main())
