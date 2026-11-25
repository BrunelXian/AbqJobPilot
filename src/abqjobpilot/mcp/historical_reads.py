"""Local, project-bound projections for explicitly read-only stdio sessions."""

from pathlib import Path
from types import SimpleNamespace

from .. import __version__, sanity_api
from ..execution import odb_history, odb_verdict, sanity_hil, sanity_verdict
from ..execution.models import ExecutionError, require, text
from ..execution.store import open_existing_read_only
from ..product_project import validate_product
from ..sanity_admission import recorded_plan
from ..service_lifecycle import ServiceLifecycleManager
from .agent_first_tools import RUN_FIELDS

PROFILE = "sanity-history-read-only/1.0"


class HistoricalReads:
    def __init__(self, context):
        self.context = context
        self._plan()

    def _plan(self):
        manager = ServiceLifecycleManager(self.context.test_root)
        require(manager.context == self.context, "PROJECT_IDENTITY_MISMATCH", "Bound Project changed")
        validate_product(manager.context)
        plan = recorded_plan(manager)
        require(sanity_hil.from_plan(plan) and plan["sanity"]["mode"] == "REAL",
                "CAPABILITY_UNAVAILABLE", "Historical native Sanity Plan required")
        return manager, plan

    def environment(self):
        _, plan = self._plan()
        return {"product_version": __version__, "profile": PROFILE, "module": str(Path(__file__).resolve()),
                "plan_id": plan["plan_id"], "plan_digest": plan["plan_digest"],
                "supervisor": {"status": "NOT_QUERIED"}, "accepting_new_delegated_requests": False}

    def run_status(self, run_id):
        text(run_id)
        manager, plan = self._plan()
        receipt, run = sanity_api.execution(manager, plan)
        require(run["run_id"] == run_id, "NOT_FOUND", "Run outside bound Sanity Plan")
        verdict = sanity_verdict.read_verdict(self.context, plan, receipt, run)
        target = {key: receipt["request_id"] if key == "receipt_id" else run[key] for key in odb_history.TARGET}
        local = SimpleNamespace(context=self.context, client_namespace="product-client")
        with open_existing_read_only(self.context).read() as conn:
            conn.execute("BEGIN")
            try:
                grade, _, source = odb_history.source_status(conn, local, plan, target)
            except ExecutionError as exc:
                if exc.code != "ODB_SOURCE_UNTRUSTED":
                    raise
                grade, source = exc.code, None
        provenance = {"grade": grade, "source_bytes_checked": False}
        if source is not None:
            provenance.update(registration_id=source.get("registration_id"), sha256=source["artifact"]["sha256"],
                              size=source["artifact"]["size"])
        return {"run": {k: run[k] for k in RUN_FIELDS if k in run},
                "progress": {"status": "UNAVAILABLE", "records": []},
                "solver_verdict": verdict, "odb_provenance": provenance}

    def receipt(self, idempotency_key, operation_id=None):
        text(idempotency_key)
        manager, plan = self._plan()
        key = plan["sanity"]["request_key"]
        if operation_id is None:
            require(idempotency_key == key, "NOT_FOUND", "Original acceptance key required")
            accepted, _ = sanity_api.execution(manager, plan)
            return {"receipt": accepted}
        text(operation_id)
        require(idempotency_key == key + ".historical-odb", "NOT_FOUND", "Original extraction key required")
        accepted, run = sanity_api.execution(manager, plan)
        verdict = odb_verdict.read_verdict(self.context, plan, accepted, run, operation_id)
        # Return recorded disposition and native references without private process diagnostics.
        recorded = {**verdict["recorded"], "operation_id": verdict["operation_id"],
                    "operation_key": idempotency_key, "grant_id": verdict["grant_id"],
                    "run_id": verdict["run_id"], "phase_attempt_id": verdict["phase_attempt_id"],
                    "receipt_id": verdict["receipt_id"]}
        return {"receipt": recorded, "extraction_verdict": verdict}
