"""Internal service with explicit test backends; no GUI, legacy runtime or IPC dependencies."""

from contextlib import ExitStack
import json

from .authorization import check_grant
from .delegated_grant import (EXECUTE, KIND as DELEGATED_KIND, check_admission, check_registration,
                              environment_enabled, require_environment, validity)
from .fake_backend import FakeBackend
from .models import (CONTRACT, CANONICAL, ExecutionError, canonical_json, digest, fields,
                     identifier, integer, now, require, text, ExecutionPlan)
from .planning import check_plan, configuration, prepare_plan
from .sanity_simulation import completion_receipt, fake_plan, matches as is_sanity_simulation
from .store import (ExperimentStore, append_event, delegated_run_ids, document, gate_view,
                    update_run, validate_context)
from .validation import validate_artifact


class ExecutionService:
    def project_view(self, context, before_row=0, limit=32):
        self._context(context)
        return self.store.project_view(context, self.client_namespace, before_row, limit)

    def __init__(self, context, store, *, client_namespace="internal", process_config=None, standard_config=None):
        require(type(store) is ExperimentStore and store.context == context,
                "PROJECT_IDENTITY_MISMATCH", "Explicit matching experimental store required")
        text(client_namespace)
        validate_context(context)
        self.context, self.store = context, store
        self.client_namespace = client_namespace
        self._backend = FakeBackend()
        self._process_backend = None
        self._standard_backend = None
        self.product_control = None
        if standard_config is not None:
            from .standard_backend import StandardBackend
            self._standard_backend = StandardBackend(standard_config)
        if process_config is not None:  # Trusted construction only; never an IPC argument/plugin.
            from .process_backend import ProcessBackend
            self._process_backend = ProcessBackend(process_config)

    def _context(self, context):
        require(context == self.context, "PROJECT_IDENTITY_MISMATCH", "Service context mismatch")
        validate_context(context)

    def read_rod_artifact(self, context, *, plan_id, expected_plan_digest, request_key):
        from .rod_trusted import acquire
        return acquire(self, context, plan_id=plan_id, expected_plan_digest=expected_plan_digest, request_key=request_key)

    def preview_reconciliation(self, context, run_id):
        from .reconciliation import preview
        return preview(self, context, run_id)

    def preview_closeout(self, context, run_id):
        from .closeout import preview
        return preview(self, context, run_id)

    def apply_closeout(self, context, request):
        from .closeout import ACTIONS
        from .reconciliation import manage
        require(type(request) is dict and request.get('operation') in ACTIONS,
                'INVALID_REQUEST','Explicit supported closeout action required')
        return manage(self,context,request,request['operation'])

    def apply_reconciliation(self, context, request):
        from .reconciliation import ADOPT, manage
        return manage(self, context, request, ADOPT)

    def resume_dispatch(self, context, request):
        require(self.product_control is None, 'DISPATCH_POLICY_MISMATCH', 'Product single dispatch cannot open the general gate')
        from .reconciliation import RESUME, manage
        return manage(self, context, request, RESUME)

    def preview_process_reconciliation(self, context, run_id):
        from .process_reconciliation import preview
        return preview(self, context, run_id)

    def apply_process_reconciliation(self, context, request):
        from .process_reconciliation import RECONCILE_PROCESS
        from .reconciliation import manage
        return manage(self, context, request, RECONCILE_PROCESS)

    def inspect_plan(self, context, plan_id, expected_digest):
        self._context(context)
        with self.store.read() as connection:
            plan = document(connection, 'plans', 'plan_id', plan_id)
        if plan['backend_id'] == 'fake-v1':
            from .rod_evidence_port import inspect_fake_plan
            return inspect_fake_plan(self, context, plan_id, expected_digest)
        if plan['backend_id'] == 'abaqus-standard-rod-preview-v1':
            from .rod_plan_adapter import inspect_registered
            return inspect_registered(self, plan_id, expected_digest)
        if plan['backend_id'] in ('abaqus-standard-axial-2024-v1', 'abaqus-standard-rod-cload-v1', 'abaqus-standard-t3d2-sanity-v1'):
            from .standard_contract import inspect
            return inspect(self, plan_id, expected_digest)
        from .public_workflow import inspect_plan
        try:
            return inspect_plan(self, context, plan_id, expected_digest)
        except ExecutionError as exc:
            raise ExecutionError(exc.code, "Fixed plan inspection refused; correct the named precondition",
                                 stage=exc.stage) from None

    def validate_run(self, context, request):
        from .public_workflow import VALIDATE
        from .reconciliation import manage
        try:
            return manage(self, context, request, VALIDATE)
        except ExecutionError as exc:
            raise ExecutionError(exc.code, "Explicit validation not confirmed; query the original management key before retry",
                                 stage=exc.stage, run_id=exc.run_id, project_instance_id=exc.project_instance_id,
                                 evidence_refs=exc.evidence_refs, reconcile=exc.reconcile) from None

    def configure(self, context, snapshot):
        """Explicit fixture configuration change; invalidates old plans."""
        self._context(context)
        value = configuration(snapshot)
        with self.store.transaction("configure") as connection:
            connection.execute("INSERT INTO configuration VALUES(1,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                               (canonical_json(value),))
        return value

    def preflight_inp(self, context, request):
        from .dynamic_inp import preflight

        self._context(context)
        with self.store.read() as connection:
            require_environment(self, connection)
        return preflight(context, request)

    def prepare(self, context, spec, snapshot, *, expires_at, process_scenario=None, delegated_resources=None,
                candidate=None, delegated_execution=None):
        self._context(context)
        if delegated_resources is not None:
            require(process_scenario is None, "TEST_SCOPE_REQUIRED", "Delegated admission is Fake only")
            with self.store.read() as connection:
                require_environment(self, connection)
        config = configuration(snapshot)
        plan = prepare_plan(context, spec, config, expires_at, delegated_resources=delegated_resources,
                            candidate=candidate, delegated_execution=delegated_execution)
        data = plan.to_dict()
        if process_scenario is not None:
            require(self._process_backend is not None, "TEST_GRANT_ONLY", "Process fixture is not configured")
            binding = self._process_backend.config.binding(process_scenario)
            self._process_backend.config.verify(binding)
            data.update(backend_id="python-process-fixture-v1", backend_version=1,
                        action="launch_fixed_python_fixture", phases=["PROCESS_FIXTURE"],
                        validation_policy="process-fixture-result-v1", process_fixture=binding,
                        output_policy={"root": context.runtime_root, "template": "process_runs/{run_id}/result.json", "overwrite": False})
            data.pop("plan_digest")
            data["plan_digest"] = digest(data)
            plan = ExecutionPlan.from_dict(data)
        with self.store.transaction("prepare") as connection:
            row = connection.execute("SELECT body FROM configuration WHERE id=1").fetchone()
            if row is None:
                connection.execute("INSERT INTO configuration VALUES(1,?)", (canonical_json(config),))
            else:
                require(json.loads(row[0]) == config, "PLAN_STALE", "Configure explicitly before planning changed configuration")
            job = data["job_spec"]
            row = connection.execute("SELECT body FROM jobs WHERE job_id=? AND revision=?", (job["job_id"], job["revision"])).fetchone()
            require(row is None or row[0] == canonical_json(job), "JOB_REVISION_CONFLICT", "Job revision already has different content")
            if row is None:
                connection.execute("INSERT INTO jobs VALUES(?,?,?)", (job["job_id"], job["revision"], canonical_json(job)))
            connection.execute("INSERT INTO plans VALUES(?,?,?,?)", (data["plan_id"], job["job_id"], job["revision"], canonical_json(data)))
        return plan

    def _request(self, context, request):
        fields(request, ("contract_version", "operation", "project_id", "project_instance_id", "job_id",
                         "job_revision", "plan_id", "plan_digest", "grant_id", "idempotency_key", "retry_of"))
        require(request["contract_version"] == CONTRACT and request["operation"] == "submit",
                "INVALID_REQUEST", "Unsupported operation or contract")
        for name in ("job_id", "plan_id", "plan_digest", "idempotency_key"):
            text(request[name])
        integer(request["job_revision"], 1)
        if request["retry_of"] is not None:
            text(request["retry_of"])
        require(request["project_id"] == context.project_id and request["project_instance_id"] == context.project_instance_id,
                "PROJECT_IDENTITY_MISMATCH", "Request Project differs from context")
        semantic = {key: value for key, value in request.items() if key != "idempotency_key"}
        semantic.update(context_digest=context.context_digest, canonicalization=CANONICAL)
        return digest(semantic)

    def _check_delegated_dispatch(self, connection, context, plan, grant, run_id, consumed_ids):
        require(grant["allowed_action"] == EXECUTE and type(self._backend) is FakeBackend,
                "DELEGATED_DISPATCH_UNAVAILABLE", "Only explicitly approved Fake execution can dispatch")
        binding = {"project_id": context.project_id, "project_instance_id": context.project_instance_id,
                   "job_id": plan["job_id"], "job_revision": plan["job_revision"], "plan_id": plan["plan_id"],
                   "plan_digest": plan["plan_digest"], "grant_id": grant["grant_id"], "retry_of": None}
        run = document(connection, "runs", "run_id", run_id)
        require(run_id in consumed_ids and run["run_id"] == run_id and run.get("delegated_execution") == EXECUTE
                and run.get("admission_only") is False and run["simulation"] is True and run["backend_id"] == "fake-v1"
                and all(run[key] == value for key, value in binding.items()),
                "DELEGATED_SCOPE_MISMATCH", "Accepted Run binding differs")
        namespace = canonical_json([context.project_instance_id, self.client_namespace, "submit"])
        row = connection.execute("SELECT key,request_digest,body FROM receipts WHERE namespace=? AND run_id=?",
                                 (namespace, run_id)).fetchone()
        require(row is not None, "DELEGATED_SCOPE_MISMATCH", "Original receipt is missing")
        receipt = json.loads(row["body"])
        request = {**binding, "operation": "submit", "contract_version": CONTRACT, "idempotency_key": row["key"]}
        require(receipt["request_status"] == "ACCEPTED" and receipt["namespace"] == namespace
                and receipt["run_id"] == run_id and receipt["idempotency_key"] == row["key"]
                and receipt["request_digest"] == row["request_digest"] == self._request(context, request),
                "DELEGATED_SCOPE_MISMATCH", "Original accepted request differs")

    def _check(self, connection, context, plan, grant_id, run_id=None, *, pin_scope=None):
        if plan['backend_id'] == 'abaqus-standard-rod-cload-v1':
            from .rod_trusted import require_activation
            require_activation(self, plan)
        if plan['backend_id'] == 'abaqus-standard-rod-preview-v1':
            from .rod_plan_adapter import refuse_unqualified_execution
            refuse_unqualified_execution()
        if plan['backend_id'] in ('abaqus-standard-axial-2024-v1', 'abaqus-standard-rod-cload-v1', 'abaqus-standard-t3d2-sanity-v1'):
            from .standard_contract import check_plan as check_standard, check_grant as check_standard_grant
            check_standard(self, plan)
            from . import sanity_hil
            if sanity_hil.from_plan(plan):
                decision = sanity_hil.require_decision(self, connection, plan)
            row = connection.execute('SELECT body FROM grants WHERE grant_id=?', (grant_id,)).fetchone()
            consumed = connection.execute('SELECT run_id FROM consumption WHERE grant_id=?', (grant_id,)).fetchone()
            grant = json.loads(row[0]) if row else None
            check_standard_grant(self, plan, grant, consumed[0] if consumed else None, run_id)
            if sanity_hil.from_plan(plan):
                require(grant['approval_source'] == digest(decision) and grant['approval_subject'] == decision['subject'],
                        'HIL_SCOPE_MISMATCH', 'Stored Grant differs from the exact human decision')
            from .standard_sequence import check_start
            check_start(self, connection, plan, grant, run_id)
            from .product_standard import single
            if single(plan):
                require(self.product_control is not None, 'REAL_OPERATOR_REQUIRED', 'Provisioned product control required')
                if run_id: self.product_control.start_check(self, connection, plan, run_id)
                else: self.product_control.accept(self, connection, plan)
            return
        row = connection.execute("SELECT body FROM configuration WHERE id=1").fetchone()
        require(row is not None, "PLAN_STALE", "Missing explicit configuration")
        binding = None
        if plan["backend_id"] == "python-process-fixture-v1":
            require(self._process_backend is not None, "TEST_GRANT_ONLY", "Process fixture is not configured")
            binding = plan.get("process_fixture")
            self._process_backend.config.verify(binding)
        check_plan(context, plan, json.loads(row[0]), process_binding=binding, pin_scope=pin_scope)
        require(type(grant_id) is str and bool(grant_id), "GRANT_REQUIRED", "Registered grant ID required")
        row = connection.execute("SELECT plan_id,body FROM grants WHERE grant_id=?", (grant_id,)).fetchone()
        grant = json.loads(row["body"]) if row else None
        delegated = type(grant) is dict and grant.get("grant_kind") == DELEGATED_KIND
        if "delegated_admission" in plan or delegated:
            require(delegated,
                    "GRANT_REQUIRED", "Delegated Plan requires a registered delegated Grant")
            require_environment(self, connection)
            gate = gate_view(connection)
            require(gate["state"] == "OPEN" and gate["owner_id"] == self.store._session.owner_id,
                    "DISPATCH_PAUSED", "Owner is query-only; no new acceptance")
            check_admission(self, plan, grant, grant_id, row["plan_id"])
            used = delegated_run_ids(connection, grant_id, grant["max_runs"])
            if run_id is None:
                require(len(used) < grant["max_runs"], "GRANT_BUDGET_EXHAUSTED", "Delegated Run budget is exhausted")
            else:
                self._check_delegated_dispatch(connection, context, plan, grant, run_id, used)
            return grant
        consumed = connection.execute("SELECT run_id FROM consumption WHERE grant_id=?", (grant_id,)).fetchone()
        check_grant(context, plan, grant, self.store._session.authority_instance, consumed[0] if consumed else None, run_id)

    def delegated_environment(self, context):
        from .odb_extractor import fixture_enabled

        self._context(context)
        with self.store.read() as connection:
            connection.execute("BEGIN")
            enabled = environment_enabled(self, connection)
            gate = gate_view(connection)
            return {"delegation_enabled": enabled, "gate_state": gate["state"],
                    "delegated_fake_execution": enabled and type(self._backend) is FakeBackend,
                    "odb_fixture_enabled": enabled and fixture_enabled(connection),
                    "accepting_new": (enabled and gate["state"] == "OPEN"
                                      and gate["owner_id"] == self.store._session.owner_id
                                      and not self.store._session.stopping and not self.store._session.closed)}

    def delegated_grant_status(self, context, grant_id):
        self._context(context)
        text(grant_id)
        with self.store.read() as connection:
            connection.execute("BEGIN")
            require_environment(self, connection)
            row = connection.execute("SELECT plan_id,body FROM grants WHERE grant_id=?", (grant_id,)).fetchone()
            require(row is not None, "NOT_FOUND", "No registered delegated Grant")
            grant = json.loads(row["body"])
            require(type(grant) is dict and grant.get("grant_kind") == DELEGATED_KIND,
                    "DELEGATED_SCOPE_MISMATCH", "A delegated Grant is required")
            check_registration(self, grant_id, grant, row["plan_id"])
            used = len(delegated_run_ids(connection, grant_id, grant["max_runs"]))
            keys = ("grant_id", "contract_version", "grant_kind", "issuer", "issued_at", "expires_at", "revoked_at", "max_runs",
                    "allowed_action")
            return {**{key: grant[key] for key in keys}, "validity": validity(grant),
                    "consumed": used, "remaining": grant["max_runs"] - used}

    def extract_odb(self, context, run_id, request):
        from .odb_extractor import extract

        return extract(self, context, run_id, request)

    def _existing_receipt(self, connection, namespace, key, request_digest, *, delegated_only=False):
        row = connection.execute("SELECT request_digest,body FROM receipts WHERE namespace=? AND key=?",
                                 (namespace, key)).fetchone()
        if row:
            require(row[0] == request_digest, "IDEMPOTENCY_CONFLICT", "Same key has different request content")
            receipt = json.loads(row[1])
            if delegated_only:
                run = document(connection, "runs", "run_id", receipt["run_id"])
                require((run.get("admission_only") is True or run.get("delegated_execution") == EXECUTE)
                        and run["simulation"] is True and run["backend_id"] == "fake-v1",
                        "TEST_GRANT_ONLY", "Delegated submission cannot replay an exact Grant Run")
            return receipt
        return None

    def submit(self, context, request, *, delegated_only=False):
        self._context(context)
        request_digest = self._request(context, request)
        namespace = canonical_json([context.project_instance_id, self.client_namespace, "submit"])
        if not self.store.dispatch_allowed() and self.product_control is None:
            # Restarted owners expose only read-only replay; the same digest and
            # receipt rules are shared by the direct API and IPC adapter.
            with self.store.read() as connection:
                if delegated_only:
                    require_environment(self, connection)
                receipt = self._existing_receipt(connection, namespace, request["idempotency_key"], request_digest,
                                                 delegated_only=delegated_only)
            require(receipt is not None, "DISPATCH_PAUSED", "Owner is query-only; no new acceptance")
            return {"request_status": "ACCEPTED", "replayed": True, "receipt": receipt, "queue_id": None}
        replayed = False
        with ExitStack() as input_pins, self.store.transaction("accept") as connection:
            if delegated_only:
                require_environment(self, connection)
            receipt = self._existing_receipt(connection, namespace, request["idempotency_key"], request_digest,
                                             delegated_only=delegated_only)
            if receipt:
                replayed = True
            else:
                plan = document(connection, "plans", "plan_id", request["plan_id"])
                if delegated_only:
                    require(plan["backend_id"] == "fake-v1" and "delegated_admission" in plan and "sanity" not in plan,
                            "TEST_GRANT_ONLY", "Only registered delegated Fake Plans are eligible")
                if 'sanity' in plan:
                    s = plan['sanity']
                    require(s['request_key']==request['idempotency_key'] and s['launch_budget']==1 and
                            connection.execute('SELECT COUNT(*) FROM consumption').fetchone()[0]==0,
                            'SANITY_SCOPE_EXHAUSTED','Wrong request key or admission already spent')
                if self.product_control: self.product_control.accept(self, connection, plan)
                require(plan["plan_digest"] == request["plan_digest"] and plan["job_id"] == request["job_id"]
                        and plan["job_revision"] == request["job_revision"], "GRANT_SCOPE_MISMATCH", "Request does not identify the fixed Job/Plan")
                delegated = self._check(connection, context, plan, request["grant_id"], pin_scope=input_pins)
                if delegated:
                    require(request["retry_of"] is None, "INVALID_RETRY", "Delegated admission does not authorize retry")
                if request["retry_of"]:
                    previous = document(connection, "runs", "run_id", request["retry_of"])
                    require(previous["job_id"] == request["job_id"] and previous["execution"] == "FINISHED"
                            and previous["reconciliation"] == "NONE" and previous["plan_id"] != request["plan_id"]
                            and previous["grant_id"] != request["grant_id"], "INVALID_RETRY", "Retry needs a terminal same-Job Run and new Plan/Grant")
                attempt = connection.execute("SELECT COALESCE(MAX(attempt_no),0)+1 FROM runs WHERE job_id=?", (request["job_id"],)).fetchone()[0]
                run = {"run_id": identifier("r"), "project_id": context.project_id,
                       "project_instance_id": context.project_instance_id, "job_id": request["job_id"],
                       "job_revision": request["job_revision"], "plan_id": request["plan_id"],
                       "plan_digest": request["plan_digest"], "grant_id": request["grant_id"],
                       "attempt_no": attempt, "retry_of": request["retry_of"], "phase_attempt_id": identifier("phase"),
                       "queue_id": None, "queue_state": "PENDING", "execution": "PLANNED", "phase": "FAKE",
                       "backend_id": "fake-v1", "backend_outcome": "NOT_RUN", "simulation": True,
                       "process_observation": "NOT_APPLICABLE", "exit_verification": "NOT_APPLICABLE",
                       "solver_conclusion": "NOT_RUN", "artifact_validation": "NOT_RUN", "reconciliation": "NONE",
                       "revision": 1, "owner_id": self.store._session.owner_id, "owner_epoch": 1, "created_at": now()}
                if delegated:
                    run["admission_only"] = delegated["allowed_action"] != EXECUTE
                    if not run["admission_only"]:
                        run["delegated_execution"] = EXECUTE
                if "dynamic_inp" in plan:
                    from .dynamic_inp import receipt_binding

                    run["input_binding"] = receipt_binding(plan, run["grant_id"])
                if plan["backend_id"] == "python-process-fixture-v1":
                    run.update(backend_id=plan["backend_id"], phase="PROCESS_FIXTURE",
                               process_observation="NOT_STARTED", exit_verification="UNKNOWN",
                               process_records=[], process_exits=[])
                if plan['backend_id'] in ('abaqus-standard-axial-2024-v1', 'abaqus-standard-rod-cload-v1', 'abaqus-standard-t3d2-sanity-v1'):
                    require(request['retry_of'] is None, 'INVALID_RETRY', 'Standard automatic/replacement retry is unsupported')
                    run.update(backend_id=plan['backend_id'],phase='STANDARD_ANALYSIS',simulation=plan.get('sanity',{}).get('mode')=='TEST_ONLY',
                        process_observation='NOT_STARTED',exit_verification='UNKNOWN',process_records=[],process_exits=[],
                        member_completeness='UNKNOWN',overall_exit='UNKNOWN',launch_state='NOT_CALLED',
                        execution_phase='WAITING_START',
                        numerical_validation='NOT_RUN',odb_content_validation='NOT_RUN')
                    if 'standard_sequence' in plan:
                        from .standard_sequence import batch_deadline,start_deadline
                        run.update(batch_observation_not_after=batch_deadline(connection,plan,run),
                                   start_not_after=start_deadline(connection,plan,document(connection,'grants','grant_id',request['grant_id'])),
                                   batch_position=plan['standard_sequence']['position'])
                connection.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)", (run["run_id"], run["job_id"], run["job_revision"],
                                   run["plan_id"], run["grant_id"], attempt, run["retry_of"], canonical_json(run)))
                event = append_event(connection, run["run_id"], "REQUEST_ACCEPTED", {"revision": 1})
                receipt = {"request_id": identifier("req"), "namespace": namespace,
                           "idempotency_key": request["idempotency_key"], "request_digest": request_digest,
                           "request_status": "ACCEPTED", "accepted_at": run['created_at'] if 'standard_sequence' in plan else now(), "run_id": run["run_id"],
                           "job_id": run["job_id"], "accepted_sequence": event["project_sequence"], "initial_queue_state": "PENDING"}
                if "input_binding" in run:
                    receipt["input_binding"] = run["input_binding"]
                connection.execute("INSERT INTO receipts VALUES(?,?,?,?,?)", (namespace, request["idempotency_key"],
                                   request_digest, run["run_id"], canonical_json(receipt)))
                if not delegated:
                    connection.execute("INSERT INTO consumption VALUES(?,?)", (run["grant_id"], run["run_id"]))
        try:
            self.store._checkpoint("accept:after_commit")
        except OSError as exc:
            raise ExecutionError("ACCEPTANCE_UNKNOWN", "Response failed after commit; query original key", stage="ACCEPT") from exc
        return {"request_status": "ACCEPTED", "replayed": replayed, "receipt": receipt, "queue_id": None}

    def execute_pending(self, context, run_id):
        try:
            with self.store.dispatch_scope(product_service=self if self.product_control else None, run_id=run_id):
                return self._execute_pending(context, run_id)
        except ExecutionError as exc:
            # A dispatch/storage failure never retracts a previously accepted receipt.
            if self.product_control: self.product_control.blocked = True
            if exc.code in {"STORE_UNAVAILABLE", "ACCEPTANCE_UNKNOWN"}:
                exc.run_id = run_id
                exc.reconcile = True
            raise

    def _execute_pending(self, context, run_id):
        self._context(context)
        pre_error = None
        claimed = False
        with self.store.transaction("claim") as connection:
            run = document(connection, "runs", "run_id", run_id)
            if run.get("admission_only"):
                raise ExecutionError("DELEGATED_DISPATCH_UNAVAILABLE", "Delegated Run is admission-only",
                                     stage="PRE_DISPATCH", run_id=run_id)
            if run["queue_state"] == "PENDING" and run["execution"] == "PLANNED":
                plan = document(connection, "plans", "plan_id", run["plan_id"])
                simulation = is_sanity_simulation(plan)
                standard = not simulation and plan['backend_id'] in (
                    'abaqus-standard-axial-2024-v1', 'abaqus-standard-rod-cload-v1', 'abaqus-standard-t3d2-sanity-v1')
                try:
                    if self.product_control: self.product_control.check_plan(plan)
                    self._check(connection, context, plan, run["grant_id"], run_id)
                except ExecutionError as exc:
                    exc.run_id, exc.stage = run_id, "PRE_DISPATCH"
                    update_run(connection, run, "DISPATCH_BLOCKED", queue_state="BLOCKED", execution="BLOCKED", error=exc.to_dict()["error"])
                    pre_error = exc
                else:
                    cursor = connection.execute("UPDATE slot SET run_id=? WHERE id=1 AND run_id IS NULL", (run_id,))
                    if cursor.rowcount != 1:
                        raise ExecutionError("SLOT_BUSY", "This experiment store already has a claimed Run",
                                             stage="DISPATCH", run_id=run_id,
                                             project_instance_id=context.project_instance_id)
                    start = {}
                    if simulation:
                        start = {"execution_backend": "fake-v1", "execution_phase": "SIMULATING",
                                 "backend_outcome": "UNKNOWN", "process_observation": "NOT_APPLICABLE",
                                 "exit_verification": "NOT_APPLICABLE", "member_completeness": "NOT_APPLICABLE",
                                 "overall_exit": "NOT_APPLICABLE"}
                    elif plan["backend_id"] == "python-process-fixture-v1":
                        start = {"backend_outcome": "UNKNOWN", "process_observation": "UNKNOWN"}
                    run = update_run(connection, run, "START_INTENT", queue_state="DISPATCHED", execution="START_INTENT",
                                     owner_id=self.store._session.owner_id,
                                     owner_epoch=run["owner_epoch"] + (run["owner_id"] != self.store._session.owner_id),
                                     **start)
                    if standard:
                        run=update_run(connection,run,'STANDARD_STARTING',execution_phase='STARTING')
                    if (standard or simulation) and self.product_control:
                        run = self.product_control.claim(self, connection, run)
                    claimed = True
        if pre_error:
            raise pre_error
        if not claimed:
            return self.store.query_run(context, run_id)
        completed = False
        managed_result = None
        registering_odb = False
        try:
            self.store._checkpoint("dispatch:after_claim")
            if standard:
                def record_standard(event, **changes):
                    with self.store.transaction('standard_observe') as connection:
                        current = document(connection,'runs','run_id',run_id)
                        update_run(connection,current,event,**changes)
                def authorize_standard(*, started=False):
                    from .standard_contract import check_plan as check_standard, check_grant as check_standard_grant
                    self.store._session.lease.check()
                    check_standard(self,plan,started=started)
                    with self.store.read() as connection:
                        grant=document(connection,'grants','grant_id',run['grant_id'])
                        consumed=connection.execute('SELECT run_id FROM consumption WHERE grant_id=?',(run['grant_id'],)).fetchone()
                        check_standard_grant(self,plan,grant,consumed[0] if consumed else None,run_id)
                        from .standard_sequence import check_start
                        check_start(self,connection,plan,grant,run_id)
                        if self.product_control: self.product_control.start_check(self, connection, plan, run_id)
                from .sanity_hil import external, independent_registration
                bindings = {'hil_service': self} if external(plan) else {}
                result=self._standard_backend.execute(context,plan,run,record_standard,self.store._checkpoint,authorize_standard, **bindings)
                from .standard_backend import persist_result
                self.store._checkpoint('standard:before_result_commit')
                persist_result(self,run_id,result)
                if independent_registration(plan):
                    from .odb_registration import register_finished
                    registering_odb = True
                    register_finished(self, run_id, run["phase_attempt_id"])
                return self.store.query_run(context,run_id)
            if plan["backend_id"] == "python-process-fixture-v1":
                def record(event, **changes):
                    with self.store.transaction("process_observe") as connection:
                        current = document(connection, "runs", "run_id", run_id)
                        if event == "PROCESS_EXIT_OBSERVED":
                            previous, incoming = current["process_exits"], changes["process_exits"]
                            if incoming == previous:
                                return  # Same observation replay is not another fact/event.
                            require(incoming[:-1] == previous and len(incoming) == len(previous) + 1
                                    and incoming[-1]["role"] not in {v["role"] for v in previous},
                                    "PROCESS_IDENTITY_MISMATCH", "Exit observations are append-only and non-contradictory")
                        update_run(connection, current, event, **changes)
                def authorize_start():
                    self.store._session.lease.check()
                    with self.store.read() as connection:
                        self._check(connection, context, plan, run["grant_id"], run_id)
                managed_result = self._process_backend.execute(context, plan, run, record, self.store._checkpoint, authorize_start)
                completed = True
                from .process_validation import validate_process_artifact
                observation, validation = validate_process_artifact(context, plan, run)
                self.store._checkpoint("process:before_terminal")
            else:
                fixture = fake_plan(plan) if simulation else plan
                if simulation:
                    from .sanity_model import hold_candidate
                    with hold_candidate(plan):
                        self.store._session.lease.check()
                        with self.store.read() as connection:
                            self._check(connection, context, plan, run["grant_id"], run_id)
                        emission = self._backend.emit(context, fixture, run)
                elif run.get("delegated_execution") == EXECUTE:
                    # Keep the Owner lock through the bounded in-process write so
                    # revocation cannot interleave with the final authority check.
                    with self.store.read() as connection:
                        self.store._session.lease.check()
                        self._check(connection, context, plan, run["grant_id"], run_id)
                        emission = self._backend.emit(context, fixture, run)
                else:
                    emission = self._backend.emit(context, fixture, run)
                completed = True
                self.store._checkpoint("dispatch:after_artifact")
                with self.store.transaction("observe") as connection:
                    run = document(connection, "runs", "run_id", run_id)
                    run = update_run(connection, run, "FAKE_COMPLETED", execution="VALIDATING", backend_outcome="COMPLETED")
                observation, validation = validate_artifact(context, fixture, run, emission)
            with self.store.transaction("terminal") as connection:
                run = document(connection, "runs", "run_id", run_id)
                managed_changes={}
                if plan.get('process_fixture',{}).get('managed_scope'):
                    from .managed_process import check_completion
                    proof=managed_result.get('managed_scope') if isinstance(managed_result,dict) else None
                    check_completion(proof,run)
                    require(run.get('managed_scope',{}).get('scope_id')==proof['scope_id'],
                            'MANAGED_SCOPE_UNKNOWN','Scope identity changed before terminal commit')
                    managed_changes={'managed_scope':proof,'managed_completion':'COMMITTED_EMPTY_SCOPE',
                                     'managed_completion_recorded_at':now()}
                    update_run(connection,run,'MANAGED_SCOPE_COMPLETED',**managed_changes)
                    run=document(connection,'runs','run_id',run_id)
                    # The new profile only auto-continues on both successful key
                    # exits and valid artifact; empty Job alone is not success.
                    if run['backend_outcome']!='COMPLETED' or validation['verdict']!='PASS':
                        connection.execute("UPDATE dispatch_gate SET state='PAUSED',version=version+1 WHERE id=1 AND state!='PAUSED'")
                connection.execute("INSERT INTO observations VALUES(?,?,?)", (observation["observation_id"], run_id, canonical_json(observation)))
                connection.execute("INSERT INTO validations VALUES(?,?,?)", (validation["validation_id"], run_id, canonical_json(validation)))
                finish = {}
                if run.get("delegated_execution") == EXECUTE:
                    finish["fake_result_evidence"] = {
                        "contract": "delegated-fake-result-v1", "simulation": True,
                        "backend_id": observation["provenance"], "run_id": observation["run_id"],
                        "phase_attempt_id": observation["phase_attempt_id"], "observation_id": observation["observation_id"],
                        "validation_id": validation["validation_id"], "verdict": validation["verdict"],
                        "digest": observation["digest"], "size": observation["size"],
                        "result": observation.get("verified_result"),
                    }
                if simulation:
                    finish = {"execution_phase": "EVIDENCE_RECORDED",
                              "simulation_receipt": completion_receipt(connection, plan, run, observation, validation)}
                update_run(connection, run, "VALIDATION_RECORDED", execution="FINISHED",
                           artifact_validation={"PASS": "VALID", "FAIL": "INVALID", "UNKNOWN": "UNKNOWN"}[validation["verdict"]],
                           validation_scope="simulation", evidence_refs=(observation["observation_id"], validation["validation_id"]),
                           **finish)
                connection.execute("UPDATE slot SET run_id=NULL WHERE id=1 AND run_id=?", (run_id,))
        except (ExecutionError, OSError) as exc:
            if registering_odb:
                raise ExecutionError("ODB_REGISTRATION_UNKNOWN", "Preserve the committed Solver result and ODB registration intent",
                                     run_id=run_id, stage="ODB_REGISTRATION") from exc
            if standard:
                # Never convert a creation/storage ambiguity into no-start or free
                # the slot. Keep any previously recorded evidence dimensions.
                try:
                    with self.store.transaction('standard_uncertain') as connection:
                        current=document(connection,'runs','run_id',run_id)
                        update_run(connection,current,'RECONCILIATION_REQUIRED',execution='BLOCKED',
                            reconciliation='RECONCILIATION_REQUIRED',standard_error=exc.code if isinstance(exc,ExecutionError) else 'IO_FAILURE')
                    self.store.pause_after_error()
                except ExecutionError:
                    pass
                raise ExecutionError('RECONCILIATION_REQUIRED','Standard evidence incomplete; no automatic retry',
                    run_id=run_id,stage='POST_CLAIM',reconcile=True) from exc
            error = ExecutionError("TERMINAL_COMMIT_FAILED" if completed else "EVIDENCE_WRITE_FAILED",
                                   ("Post-claim evidence or storage failure; explicit reconciliation required"
                                    if plan["backend_id"] == "python-process-fixture-v1" else str(exc)), stage="POST_CLAIM", run_id=run_id,
                                   project_instance_id=context.project_instance_id, reconcile=True)
            try:
                with self.store.transaction("uncertain") as connection:
                    current = document(connection, "runs", "run_id", run_id)
                    update_run(connection, current, "RECONCILIATION_REQUIRED", execution="BLOCKED",
                               backend_outcome=(current["backend_outcome"] if plan["backend_id"] == "python-process-fixture-v1"
                                                else "COMPLETED" if completed else "UNKNOWN"),
                               artifact_validation="UNKNOWN", reconciliation="RECONCILIATION_REQUIRED", error=error.to_dict()["error"],
                               **({"process_failure_code": exc.code if isinstance(exc, ExecutionError) else "PROCESS_IO_FAILURE"}
                                  if plan["backend_id"] == "python-process-fixture-v1" else {}))
                    # Slot deliberately remains claimed. File effects cannot be rolled back.
            except ExecutionError:
                pass  # START_INTENT / VALIDATING already durably forbids re-execution.
            raise error from exc
        return self.store.query_run(context, run_id)
