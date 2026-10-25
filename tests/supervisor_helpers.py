"""Trusted test harness owns only the exact Popen handles it creates."""

from dataclasses import dataclass
import ctypes
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import pytest

from abqjobpilot.execution import ConfigSnapshot, ExecutionService, ExperimentStore, create_experiment
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.models import canonical_json
from abqjobpilot.execution.paths import confined
from execution_helpers import Harness, inventory


def wait_until(predicate, *, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.02)
    raise AssertionError("Deterministic condition did not arrive before deadline")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def bind_child_handle(process, identity):
    # Windows venv python.exe may be a redirector whose child hosts Python.
    # Bind the actual process once, while our launcher is alive, then retain
    # its kernel HANDLE. PID reuse cannot redirect later TerminateProcess.
    assert identity["pid"] == process.pid or identity["parent_pid"] == process.pid
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    api.OpenProcess.restype = ctypes.c_void_p
    api.GetProcessTimes.argtypes = [ctypes.c_void_p] * 5
    api.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
    api.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    api.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = api.OpenProcess(0x100000 | 0x1000 | 1, False, identity["pid"])
    assert handle, ctypes.get_last_error()
    try:
        times = [ctypes.c_uint64() for _ in range(4)]
        assert api.GetProcessTimes(handle, *(ctypes.byref(t) for t in times))
        assert times[0].value == identity["creation_time_100ns"]
        buffer, size = ctypes.create_unicode_buffer(32768), ctypes.c_uint32(32768)
        assert api.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        assert buffer.value.lower() == identity["image_path"].lower()
    except BaseException:
        api.CloseHandle(handle)
        raise
    return api, handle


@dataclass
class Child:
    process: object
    control: Path
    mode: str
    logs: tuple
    identity: dict
    terminated: bool = False
    native: object = None

    def reached(self, name):
        path = self.control / (name.replace(":", "_") + ".reached.json")
        wait_until(path.exists)
        return read_json(path)

    def release(self, name):
        (self.control / (name.replace(":", "_") + ".release.json")).write_text("{}", encoding="utf-8")

    def result(self):
        path = self.control / "result.json"
        wait_until(path.exists)
        return read_json(path)

    def terminate(self):
        assert self.process.poll() is None
        assert self.native is not None, "An identity-verified actual child handle is required"
        api, handle = self.native
        assert api.TerminateProcess(handle, 77)
        assert api.WaitForSingleObject(handle, 8000) == 0
        self.terminated = True
        self.process.wait(timeout=8)


class ProcessHarness:
    def __init__(self, root, *, process_scenarios=None, managed_scope=False, fake_jobs=3):
        self.root, self.children = root, []
        source = root / "input.txt"
        source.write_text("simulation fixture", encoding="utf-8")
        (root / "recent-fixture.json").write_text('{"untouched":true}', encoding="utf-8")
        self.context = create_experiment(root, root / "project")
        store = ExperimentStore(self.context)
        self.process_config = None
        if process_scenarios is not None:
            from abqjobpilot.execution.process_backend import ProcessFixtureConfig
            self.process_config = ProcessFixtureConfig.current(managed_scope=managed_scope)
        service = ExecutionService(self.context, store, client_namespace="stable-test-client", process_config=self.process_config)
        config = ConfigSnapshot.from_dict({"config_revision": 1, "values": {"label": "Run003 simulation"}})
        h = Harness(root, self.context, store, service, source, config)
        self.requests = []
        for index, scenario in enumerate(process_scenarios if process_scenarios is not None else [None] * fake_jobs):
            if scenario is None:
                plan = h.plan(h.spec(job_id="job_" + str(index)))
                grant = h.grant(plan)
            else:
                from abqjobpilot.execution.models import now
                plan = service.prepare(self.context, h.spec(job_id="job_" + str(index)), config,
                                       expires_at=now() + 7200, process_scenario=scenario)
                grant = h.grant(plan, issuer="ProcessGrantFixture", allowed_action="launch_fixed_python_fixture")
            self.requests.append(h.request(plan, grant, "key-" + str(index)))
        self.credential = secrets.token_hex(32)
        self.bootstrap = root / "private-bootstrap.json"
        self.endpoint_file = root / "endpoint.json"
        self.bootstrap.write_text(canonical_json({"context": self.context.to_dict(),
                                  "authority_instance": store._session.authority_instance,
                                  "credential": self.credential, "client_namespace": "stable-test-client",
                                  "endpoint_file": str(self.endpoint_file)}), encoding="utf-8")
        store.close()  # Explicit authority handoff before starting a different OS process.
        self.recent = inventory(root)["recent-fixture.json"]

    def spawn(self, mode, **options):
        control = self.root / ("process_" + str(len(self.children)))
        control.mkdir()
        config = {"mode": mode, **options}
        if mode in {"owner", "writer_probe"}:
            config["bootstrap"] = str(self.bootstrap)
        if mode == "owner" and self.process_config is not None:
            from dataclasses import asdict
            config["trusted_process_config"] = asdict(self.process_config)
        if mode == "client":
            config.update(endpoint=str(self.endpoint_file), credential=self.credential)
        config_path = control / "private-process.json"
        config_path.write_text(canonical_json(config), encoding="utf-8")
        logs = ((control / "stdout.txt").open("wb"), (control / "stderr.txt").open("wb"))
        script = Path(__file__).with_name("run003_process.py").resolve()
        command = [sys.executable, "-B", str(script), "--test-root", str(self.root), "--config", str(config_path)]
        process = subprocess.Popen(command, cwd=str(script.parents[1]), stdin=subprocess.DEVNULL,
                                   stdout=logs[0], stderr=logs[1], creationflags=subprocess.CREATE_NO_WINDOW,
                                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
        child = Child(process, control, mode, logs, {"pid": process.pid})
        self.children.append(child)
        wait_until(lambda: (control / "identity.json").exists() or process.poll() is not None)
        assert (control / "identity.json").exists(), (control / "stderr.txt").read_text()
        child.identity = read_json(control / "identity.json")
        assert child.identity["executable"].lower() == str(Path(sys.executable).resolve()).lower()
        child.native = bind_child_handle(process, child.identity)
        (control / "identity-bound.json").write_text("{}", encoding="utf-8")
        return child

    def owner(self, **options):
        previous = read_json(self.endpoint_file)["owner_id"] if self.endpoint_file.exists() else None
        child = self.spawn("owner", **options)
        wait_until(lambda: (child.control / "owner-ready.json").exists() or child.process.poll() is not None)
        assert child.process.poll() is None, (child.control / "stderr.txt").read_text()
        assert read_json(self.endpoint_file)["owner_id"] != previous
        client = self.client()
        assert client.health()["process"]["pid"] == child.identity["pid"]
        return child

    def client(self):
        return FakeClient(read_json(self.endpoint_file), self.credential)

    def finished(self, run_id):
        def check():
            value = self.client().run(run_id)
            return value if value["execution"] == "FINISHED" else None
        return wait_until(check)

    def close(self):
        for child in self.children:
            if child.process.poll() is None:
                if child.mode == "owner":
                    # Release only barriers belonging to this harness, then request graceful test stop.
                    for path in child.control.glob("*.reached.json"):
                        path.with_name(path.name.replace(".reached.json", ".release.json")).write_text("{}", encoding="utf-8")
                    (child.control / "stop.json").write_text("{}", encoding="utf-8")
                    try:
                        child.process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        child.terminate()
                else:
                    child.terminate()
            assert child.process.poll() is not None
            for stream in child.logs:
                stream.close()
        rows = [{"mode": c.mode, "identity": c.identity, "exit_code": c.process.returncode,
                 "launcher_pid": c.process.pid,
                 "terminated_by_owned_handle": c.terminated, "exited": c.process.poll() is not None,
                 "control": str(c.control)} for c in self.children]
        for child, row in zip(self.children, rows):
            if child.native:
                api, handle = child.native
                assert api.WaitForSingleObject(handle, 0) == 0
                row["actual_process_handle_signaled"] = True
                api.CloseHandle(handle)
                child.native = None
        # Only files created by this fixture, inside its explicit root. Business
        # evidence stays available; ephemeral connection credentials are removed.
        removed = []
        for path in [self.bootstrap] + [c.control / "private-process.json" for c in self.children]:
            target = confined(self.root, path, exists=True)
            target.unlink()
            removed.append(str(target.relative_to(self.root)))
        (self.root / "lifecycle.json").write_text(canonical_json(rows), encoding="utf-8")
        assert inventory(self.root)["recent-fixture.json"] == self.recent
        files = [str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()]
        assert not any(Path(p).suffix.lower() in {".inp", ".cae", ".odb", ".jnl"} for p in files)
        assert not any(Path(p).name in {"project.db", "queue.json", "live_status.json"} for p in files)
        assert all(self.credential.encode("utf-8") not in (self.root / p).read_bytes() for p in files)
        (self.root / "inventory.json").write_text(canonical_json({"files": files, "temporary_root": str(self.root),
                                              "recent_unchanged": True, "all_owned_processes_exited": True,
                                              "private_credentials_removed": removed,
                                              "credential_absent_from_remaining_files": True}), encoding="utf-8")


@pytest.fixture
def processes(tmp_path):
    harness = ProcessHarness(tmp_path)
    try:
        yield harness
    finally:
        harness.close()
