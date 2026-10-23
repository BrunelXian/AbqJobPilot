"""Test-only authority and isolated data. Not imported by application modules."""

import builtins
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess

import pytest

from abqjobpilot.execution import (ConfigSnapshot, ExecutionService, ExperimentStore, JobSpec,
                                   create_experiment)
from abqjobpilot.execution.models import CONTRACT, RESOURCES, canonical_json, identifier, now


@pytest.fixture(autouse=True)
def guard_environment(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Legacy/default paths and process launch are forbidden in Fake tests")
    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, blocked)
    for name in dir(os):
        if name == "system" or name == "startfile" or name.startswith(("spawn", "exec", "posix_spawn")):
            if callable(getattr(os, name)):
                monkeypatch.setattr(os, name, blocked)
    monkeypatch.setattr(Path, "home", blocked)
    original = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {"tkinter", "abqjobpilot.config", "abqjobpilot.utils", "abqjobpilot.runner_core",
                    "abqjobpilot.queue_store", "abqjobpilot.settings_store", "abqjobpilot.project",
                    "abqjobpilot.database", "abqjobpilot.gui_app"}:
            blocked()
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded_import)


class FakeGrantFixture:
    def __init__(self, store):
        self.store = store

    def issue_exact(self, plan, **overrides):
        data = plan.to_dict()
        context = self.store.context
        grant = {"grant_id": identifier("grant"), "issuer": "FakeGrantFixture",
                 "authority_instance": self.store._session.authority_instance, "grant_kind": "TEST_ONLY",
                 "project_instance_id": context.project_instance_id, "plan_id": data["plan_id"],
                 "plan_digest": data["plan_digest"], "job_id": data["job_id"], "job_revision": data["job_revision"],
                 "allowed_action": "emit_fixture_result", "resource_limits": dict(RESOURCES),
                 "output_scope": context.runtime_root, "expires_at": now() + 3600, "max_runs": 1}
        grant.update(overrides)
        with self.store.transaction("fixture_grant") as connection:
            connection.execute("INSERT INTO grants VALUES(?,?,?)", (grant["grant_id"], data["plan_id"], canonical_json(grant)))
        return grant["grant_id"]


@dataclass
class Harness:
    root: Path
    context: object
    store: ExperimentStore
    service: ExecutionService
    input: Path
    config: ConfigSnapshot

    def spec(self, **overrides):
        value = {"job_id": "j_fixture", "revision": 1, "project_id": self.context.project_id,
                 "project_instance_id": self.context.project_instance_id, "input_refs": [str(self.input)],
                 "resources": dict(RESOURCES), "metadata": {"label": "测试"}}
        value.update(overrides)
        return JobSpec.from_dict(value)

    def plan(self, spec=None, **kwargs):
        return self.service.prepare(self.context, spec or self.spec(), self.config,
                                    expires_at=kwargs.get("expires_at", now() + 7200))

    def grant(self, plan, **overrides):
        return FakeGrantFixture(self.store).issue_exact(plan, **overrides)

    def request(self, plan, grant, key="request-1", **overrides):
        data = plan.to_dict()
        result = {"contract_version": CONTRACT, "operation": "submit", "project_id": self.context.project_id,
                  "project_instance_id": self.context.project_instance_id, "job_id": data["job_id"],
                  "job_revision": data["job_revision"], "plan_id": data["plan_id"], "plan_digest": data["plan_digest"],
                  "grant_id": grant, "idempotency_key": key, "retry_of": None}
        result.update(overrides)
        return result

    def accept(self, *, key="request-1", spec=None, **overrides):
        plan = self.plan(spec)
        request = self.request(plan, self.grant(plan), key, **overrides)
        receipt = self.service.submit(self.context, request)["receipt"]
        return plan, request, receipt

    def counts(self):
        with self.store.read() as connection:
            return {table: connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                    for table in ("runs", "receipts", "events", "consumption", "observations", "validations")}


@pytest.fixture
def harness(tmp_path, guard_environment):
    source = tmp_path / "inputs"
    source.mkdir()
    inp = source / "source.txt"
    inp.write_text("fixture input", encoding="utf-8")
    (tmp_path / "recent-fixture.json").write_text('{"sentinel":true}', encoding="utf-8")
    context = create_experiment(tmp_path, tmp_path / "project")
    store = ExperimentStore(context)
    service = ExecutionService(context, store, client_namespace="test-client")
    config = ConfigSnapshot.from_dict({"config_revision": 1, "values": {"label": "simulation 测试"}})
    yield Harness(tmp_path, context, store, service, inp, config)
    store.close()


def inventory(root):
    return {str(path.relative_to(root)): (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()}
