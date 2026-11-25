from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import pytest

from abqjobpilot.execution import ExecutionError
from execution_helpers import guard_environment
from test_delegated_grant import approve, delegated, prepare


def test_two_plans_spend_one_budget_and_never_dispatch(delegated):
    h = delegated
    plans = [prepare(h, job_id=label) for label in ("first", "second")]
    grant_id = approve(h, *plans)["grant_id"]
    receipts = [h.service.submit(h.context, h.request(plan, grant_id, str(index)))["receipt"]
                for index, plan in enumerate(plans)]
    run_ids = [receipt["run_id"] for receipt in receipts]
    assert len(set(run_ids)) == 2
    assert h.store.delegated_budget(h.context, grant_id) == {
        "grant_id": grant_id, "max_runs": 2, "consumed": 2, "remaining": 0,
        "run_ids": run_ids, "revoked_at": None,
    }
    with pytest.raises(ExecutionError) as error:
        h.service.submit(h.context, h.request(plans[0], grant_id, "over-budget"))
    assert error.value.code == "GRANT_BUDGET_EXHAUSTED"
    assert h.store.pending_for_owner() is None
    for run_id in run_ids:
        with pytest.raises(ExecutionError) as error:
            h.service.execute_pending(h.context, run_id)
        assert error.value.code == "DELEGATED_DISPATCH_UNAVAILABLE"
        run = h.store.query_run(h.context, run_id)
        assert run["admission_only"] and run["execution"] == "PLANNED"
        assert run["simulation"] is True and run["solver_conclusion"] == "NOT_RUN"
    assert h.counts() == dict(runs=2, receipts=2, events=2, consumption=0, observations=0, validations=0)
    assert not list(Path(h.context.runtime_root).rglob("*"))


@pytest.mark.parametrize("same_key", [False, True])
def test_parallel_submissions_cannot_overspend_last_unit(delegated, same_key):
    h = delegated
    plan = prepare(h)
    grant_id = approve(h, plan)["grant_id"]
    h.service.submit(h.context, h.request(plan, grant_id, "first"))
    competitors = 8
    barrier = threading.Barrier(competitors)

    def compete(index):
        request = h.request(plan, grant_id, "same" if same_key else f"competing-{index}")
        barrier.wait(timeout=8)
        try:
            return h.service.submit(h.context, request)
        except ExecutionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=competitors) as executor:
        results = list(executor.map(compete, range(competitors)))
    accepted = [result for result in results if isinstance(result, dict)]
    assert sum(not result["replayed"] for result in accepted) == 1
    assert len({result["receipt"]["run_id"] for result in accepted}) == 1
    assert results.count("GRANT_BUDGET_EXHAUSTED") == (0 if same_key else competitors - 1)
    assert h.store.delegated_budget(h.context, grant_id)["remaining"] == 0
    assert h.counts()["receipts"] == h.counts()["runs"] == 2


def test_same_key_different_approved_request_conflicts(delegated):
    h = delegated
    a, b = prepare(h, job_id="a"), prepare(h, job_id="b")
    grant_id = approve(h, a, b)["grant_id"]
    request = h.request(a, grant_id)
    receipt = h.service.submit(h.context, request)["receipt"]
    assert h.service.submit(h.context, request)["receipt"] == receipt
    with pytest.raises(ExecutionError) as error:
        h.service.submit(h.context, h.request(b, grant_id))
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    assert h.store.delegated_budget(h.context, grant_id)["run_ids"] == [receipt["run_id"]]


def test_rollback_leaves_no_acceptance_or_budget_spend(delegated, monkeypatch):
    h = delegated
    plan = prepare(h)
    grant_id = approve(h, plan, max_runs=1)["grant_id"]
    request = h.request(plan, grant_id)

    def fail(stage):
        if stage == "accept:before_commit":
            raise OSError("injected precommit fault")

    with monkeypatch.context() as fault:
        fault.setattr(h.store, "_checkpoint", fail)
        with pytest.raises(ExecutionError) as error:
            h.service.submit(h.context, request)
        assert error.value.code == "STORE_UNAVAILABLE"
    assert h.store.delegated_budget(h.context, grant_id)["remaining"] == 1
    assert not any(h.counts().values())
    assert not h.service.submit(h.context, request)["replayed"]
    assert h.store.delegated_budget(h.context, grant_id)["remaining"] == 0


def test_pause_between_gate_read_and_accept_does_not_spend(delegated, monkeypatch):
    h = delegated
    plan = prepare(h)
    grant_id = approve(h, plan)["grant_id"]

    def stale_gate_read():
        h.store.pause_after_error()
        return True

    monkeypatch.setattr(h.store, "dispatch_allowed", stale_gate_read)
    with pytest.raises(ExecutionError) as error:
        h.service.submit(h.context, h.request(plan, grant_id))
    assert error.value.code == "DISPATCH_PAUSED"
    assert h.store.delegated_budget(h.context, grant_id)["consumed"] == 0
