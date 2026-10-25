"""Reproduce current product integration gaps without issuing any real Grant."""
from pathlib import Path
import subprocess

import pytest
from abqjobpilot.product_project import create_project
from abqjobpilot.service_lifecycle import ServiceLifecycleManager
from abqjobpilot.execution import ExecutionService
from abqjobpilot.execution.store import acquire_initial_preparation_store, open_existing_read_only
from abqjobpilot.execution.standard_contract import StandardConfig, management_binding, prepare
from abqjobpilot.execution.standard_sequence import prepare_pair
from abqjobpilot.execution.models import canonical_json, now, ExecutionError

SOURCE = Path(__file__).resolve().parents[3]


@pytest.fixture
def empty(tmp_path, monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError('No external process in readiness checks')
    monkeypatch.setattr(subprocess, 'Popen', reject)
    root = tmp_path/'candidate'
    create_project(root, 'Readiness boundary')
    manager = ServiceLifecycleManager(root)
    store = acquire_initial_preparation_store(manager.context, manager._profile()['authority_instance'])
    for name in ('a', 'b'):
        eng = root/name; eng.mkdir(); (eng/'scratch').mkdir()
        (eng/'axial_bar.inp').write_bytes((SOURCE/'docs/agent_first/run_010/axial_bar.inp').read_bytes())
    config = StandardConfig(canonical_json({'interpreter': 'INJECTED_NO_REAL_CAPABILITY',
                                           'process_management': management_binding()}))
    monkeypatch.setattr(StandardConfig, 'verify', lambda self: None)
    service = ExecutionService(manager.context, store, standard_config=config)
    try:
        yield root, manager, store, service
    finally:
        store.close()


def test_managed_single_cannot_be_mislabeled_ready(empty):
    root, manager, store, service = empty
    with pytest.raises(ExecutionError) as exc:
        prepare(service, root/'a', 'r016_bar_a_1234abcd', expires_at=now()+600)
    assert exc.value.code == 'INVALID_REQUEST'
    with store.read() as conn:
        assert conn.execute('SELECT COUNT(*) FROM plans').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM grants').fetchone()[0] == 0
    assert store.gate()['state'] == 'PAUSED'


def test_product_rejects_real_plan_before_start_reservation(empty):
    root, manager, store, service = empty
    prepare_pair(service, root/'a', 'r016_bar_a_1234abcd', root/'b', 'r016_bar_b_1234abcd', expires_at=now()+600)
    store.close()
    with pytest.raises(ExecutionError) as exc:
        manager.start()
    assert exc.value.code == 'LIFECYCLE_SCOPE_UNSUPPORTED'
    assert not manager._path('lifecycle-current.json').exists()
    with open_existing_read_only(manager.context).read() as conn:
        for table in ('grants', 'runs', 'consumption', 'receipts', 'events'):
            assert conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] == 0
        assert conn.execute('SELECT state FROM dispatch_gate').fetchone()[0] == 'PAUSED'
