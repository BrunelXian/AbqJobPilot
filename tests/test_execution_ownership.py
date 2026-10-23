from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import threading

import pytest

from abqjobpilot.execution import ExecutionError, open_existing_read_only
from abqjobpilot.execution.fake_backend import FakeBackend
from abqjobpilot.execution.models import canonical_json, digest
from abqjobpilot.execution.store import acquire_supervisor_store
from execution_helpers import guard_environment, harness, inventory


def test_format_one_remains_readonly_and_never_migrated_or_adopted(harness):
    h = harness
    _, _, receipt = h.accept()
    h.service.execute_pending(h.context, receipt["run_id"])
    h.store.close()
    # Construct a v1 fixture explicitly, only inside the fresh temporary root.
    path = Path(h.context.root) / "experiment.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    path.write_text(canonical_json(manifest), encoding="utf-8")
    old_context = replace(h.context, schema_version=1, manifest_digest=digest(manifest))
    with sqlite3.connect(h.context.execution_store) as connection:
        connection.execute("UPDATE meta SET value='1' WHERE key='schema'")
        connection.execute("UPDATE meta SET value=? WHERE key='context_digest'", (old_context.context_digest,))
        connection.execute("DELETE FROM meta WHERE key IN ('authority_instance','supervisor_started')")
    before = inventory(h.root)
    reader = open_existing_read_only(old_context)
    assert reader.query_run(old_context, receipt["run_id"])["execution"] == "FINISHED"
    assert reader.query_receipt(old_context, "test-client", "request-1") == receipt
    assert len(reader.events(old_context)) == 4
    assert reader.validations(old_context, receipt["run_id"])[0]["verdict"] == "PASS"
    with pytest.raises(ExecutionError) as error:
        acquire_supervisor_store(old_context, "cannot-adopt")
    assert error.value.code == "UNSUPPORTED_FORMAT"
    assert inventory(h.root) == before


def test_local_owner_cannot_release_lock_during_active_fake(harness, monkeypatch):
    h = harness
    _, _, receipt = h.accept()
    entered, release = threading.Event(), threading.Event()
    original = FakeBackend.emit
    def held(backend, *args):
        entered.set()
        assert release.wait(8)
        return original(backend, *args)
    monkeypatch.setattr(FakeBackend, "emit", held)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(h.service.execute_pending, h.context, receipt["run_id"])
        try:
            assert entered.wait(8)
            with pytest.raises(ExecutionError) as error:
                h.store.close()
            assert error.value.code == "OWNER_BUSY"
            h.store._session.lease.check()
            with pytest.raises(ExecutionError) as error:
                acquire_supervisor_store(h.context, h.store._session.authority_instance)
            assert error.value.code == "OWNER_BUSY"
        finally:
            release.set()
        assert future.result()["execution"] == "FINISHED"
