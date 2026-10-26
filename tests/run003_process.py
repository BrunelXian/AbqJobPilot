"""Explicit, identity-recorded test processes. Not a product/RPC plugin loader."""

import argparse
import builtins
import json
from pathlib import Path
import sys
import subprocess
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.models import ExecutionError, canonical_json
from abqjobpilot.execution.ownership import current_process_identity
from abqjobpilot.execution.paths import confined
from abqjobpilot.execution.store import ExperimentStore, acquire_supervisor_store
from abqjobpilot.execution.supervisor import FakeSupervisor, load_bootstrap
from execution_helpers import guard_environment
from reconciliation_helpers import FakeManagementFixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-root", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    root = Path(args.test_root).resolve()
    config_path = confined(root, args.config, exists=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    control = config_path.parent
    # Publish only a complete identity. The parent intentionally treats file
    # visibility as the handshake boundary before retaining the kernel handle.
    identity_temporary = control / "identity.partial"
    identity_temporary.write_text(canonical_json(current_process_identity()), encoding="utf-8")
    identity_temporary.replace(control / "identity.json")
    identity_deadline = time.monotonic() + 12
    while not (control / "identity-bound.json").exists():
        if time.monotonic() >= identity_deadline:
            raise RuntimeError("Harness did not bind the child kernel handle")
        time.sleep(0.01)
    monkeypatch = pytest.MonkeyPatch()
    real_popen = subprocess.Popen
    process_config = None
    allowed_reads = set()
    native_resources=[]
    if config.get("trusted_process_config"):
        from abqjobpilot.execution.process_backend import ProcessFixtureConfig
        process_config = ProcessFixtureConfig(**config["trusted_process_config"])
        # Test support may be separate from an installed/runtime-only package.
        # Keep the exact-module allowlist; do not widen it to arbitrary scripts.
        from abqjobpilot.execution import process_fixture as fixture_module
        fixture = Path(fixture_module.__file__).resolve()
        allowed_reads = {Path(process_config.interpreter), Path(process_config.image), fixture}
        if process_config.managed_scope:
            allowed_reads.add(fixture.with_name('managed_process.py'))
    guard_environment.__wrapped__(monkeypatch)  # Keep original launch/default/legacy traps in every child.
    if process_config is not None:
        physical_launches = []
        def fixed_launch(command, **kwargs):
            assert command[:5] == [process_config.interpreter, "-I", "-S", "-B", str(fixture)]
            assert command[5:8] == ["--role", "launcher", "--directory"] and len(command) == 9
            confined(root, command[8], exists=True)
            assert kwargs["shell"] is False and kwargs["close_fds"] is True
            assert set(kwargs["env"]) == {"SystemRoot", "PYTHONDONTWRITEBYTECODE"}
            assert kwargs["cwd"] == command[8]
            process = real_popen(command, **kwargs)
            from abqjobpilot.execution.process_handles import ProcessReference
            reference = ProcessReference(process.pid)
            try:
                physical_launches.append({"run_id": Path(command[8]).name, "identity": reference.identity,
                                          "source": "trusted_launch_trap_retained_os_reference"})
                (control / "physical-launches.json").write_text(canonical_json(physical_launches), encoding="utf-8")
            finally:
                reference.close()
            return process
        monkeypatch.setattr(subprocess, "Popen", fixed_launch)
        if process_config.managed_scope:
            from abqjobpilot.execution.managed_process import ManagedScope
            original_create=ManagedScope.create
            def native_guard(event, values):
                if event=='abqjobpilot.managed_create':
                    command,cwd,environment=values
                    assert list(command[:5])==[process_config.interpreter,'-I','-S','-B',str(fixture)]
                    assert list(command[5:8])==['--role','launcher','--directory'] and len(command)==9
                    confined(root,command[8],exists=True)
                    assert cwd==command[8] and set(environment)=={'SystemRoot','PYTHONDONTWRITEBYTECODE'}
            sys.addaudithook(native_guard)
            def native_launch(scope,command,**kwargs):
                process=original_create(scope,command,**kwargs)
                native_resources.append((scope,process))
                from abqjobpilot.execution.process_handles import ProcessReference
                reference=ProcessReference(process.pid)
                try:
                    physical_launches.append({'run_id':Path(command[8]).name,'identity':reference.identity,
                        'source':'native_JOB_LIST_create_retained_os_reference','scope_id':scope.scope_id})
                    (control/'physical-launches.json').write_text(canonical_json(physical_launches),encoding='utf-8')
                finally:reference.close()
                return process
            monkeypatch.setattr(ManagedScope,'create',native_launch)
    real_open = Path.open
    accesses = []
    def checked_open(path, *pos, **kw):
        if path not in allowed_reads:
            confined(root, path)
        else:
            assert not any(c in (pos[0] if pos else kw.get("mode", "r")) for c in "wax+")
        accesses.append(str(path))
        return real_open(path, *pos, **kw)
    monkeypatch.setattr(Path, "open", checked_open)
    # C-level sqlite IO uses the separately validated explicit store URI.
    try:
        if config["mode"] == "owner":
            context, bootstrap = load_bootstrap(root, config["bootstrap"])
            owner = FakeSupervisor(context, bootstrap, process_config=process_config)
            (control / "owner-ready.json").write_text("{}", encoding="utf-8")
            stops = threading.Event()
            stop_file = control / "stop.json"
            hooks = set(config.get("barriers", []))
            seen, occurrences, lock = set(), {}, threading.Lock()
            def barrier(name):
                if name in config.get("faults", []):
                    raise OSError("Explicit test checkpoint fault")
                with lock:
                    if name not in hooks or (name in seen and name not in config.get("repeat_barriers", [])):
                        return
                    seen.add(name)
                    occurrences[name] = occurrences.get(name, 0) + 1
                    occurrence = occurrences[name]
                label = (name + (":" + str(occurrence) if occurrence > 1 else "")).replace(":", "_")
                (control / (label + ".reached.json")).write_text(canonical_json({"stage": name, "process": current_process_identity()}), encoding="utf-8")
                deadline = time.monotonic() + 30
                while not (control / (label + ".release.json")).exists():
                    if time.monotonic() >= deadline:
                        raise OSError("Test barrier expired")
                    time.sleep(0.01)
            owner._checkpoint = barrier
            owner.store._checkpoint = barrier
            def watcher():
                processed = set()
                while not stops.wait(0.02):
                    if stop_file.exists():
                        stops.set()
                    if config.get('managed_control') and 'pause' not in processed and (control/'pause.json').exists():
                        owner.store.pause_after_error()
                        processed.add('pause')
                    # Explicit trusted test control, absent from production main and IPC.
                    # Registration happens through the owner Store, never a second writer.
                    if config.get("management_control"):
                        for command in control.glob("grant_*.request.json"):
                            if command.name in processed:
                                continue
                            processed.add(command.name)
                            try:
                                value = json.loads(command.read_text(encoding="utf-8"))
                                grant_id = FakeManagementFixture(owner.store).issue(value["action"], value["scope"], **value.get("overrides", {}))
                                result = {"grant_id": grant_id}
                            except ExecutionError as exc:
                                result = exc.to_dict()
                            reply = command.with_name(command.name.replace(".request.json", ".reply.json"))
                            partial = reply.with_suffix(".tmp")
                            partial.write_text(canonical_json(result), encoding="utf-8")
                            partial.replace(reply)
            watch = threading.Thread(target=watcher, daemon=True)
            watch.start()
            try:
                owner.serve(stops)
            finally:
                stops.set()
                watch.join(1)
        elif config["mode"] == "client":
            endpoint = json.loads(confined(root, config["endpoint"], exists=True).read_text(encoding="utf-8"))
            client = FakeClient(endpoint, config["credential"])
            operation = config["operation"]
            result = client.call(operation, config["arguments"])
            (control / "result.json").write_text(canonical_json(result), encoding="utf-8")
            # An explicit client wait can be terminated by the owning test handle.
            if config.get("wait_after_response"):
                while True:
                    time.sleep(0.1)
        elif config["mode"] == "writer_probe":
            context, bootstrap = load_bootstrap(root, config["bootstrap"])
            errors = []
            for opener in (lambda: ExperimentStore(context),
                           lambda: acquire_supervisor_store(context, bootstrap["authority_instance"])):
                try:
                    store = opener()
                    store.close()
                    errors.append("UNEXPECTED_OWNER")
                except ExecutionError as exc:
                    errors.append(exc.code)
            (control / "result.json").write_text(canonical_json(errors), encoding="utf-8")
        else:
            raise AssertionError("Unknown test harness mode")
    except ExecutionError as exc:
        (control / "error.json").write_text(canonical_json(exc.to_dict()), encoding="utf-8")
        return 2
    finally:
        (control / "io.json").write_text(canonical_json({"paths": sorted(set(accesses)),
                    "all_confined": all(Path(p).is_relative_to(root) for p in accesses),
                    "all_data_accesses_confined": all(Path(p).is_relative_to(root) or Path(p) in allowed_reads for p in accesses),
                    "trusted_read_only_execution_objects": sorted(str(p) for p in allowed_reads),
                    "fixed_process_launch_whitelist": process_config is not None,
                    'managed_handle_cleanup':[{'scope_id':s.scope_id,'job_handle_closed':s.handle is None,
                        'root_handle_closed':p.handle is None} for s,p in native_resources],
                    "launch_and_legacy_traps": True}), encoding="utf-8")
        monkeypatch.undo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
