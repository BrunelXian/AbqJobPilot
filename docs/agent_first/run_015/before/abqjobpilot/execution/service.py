"""Internal service with explicit test backends; no GUI, legacy runtime or IPC dependencies."""

import json

from .authorization import check_grant
from .fake_backend import FakeBackend
from .models import (CONTRACT, CANONICAL, ExecutionError, canonical_json, digest, fields,
                     identifier, integer, now, require, text, ExecutionPlan)
from .planning import check_plan, configuration, prepare_plan
from .store import ExperimentStore, append_event, document, update_run, validate_context
from .validation import validate_artifact


class ExecutionService:
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
        if standard_config is not None:
            from .standard_backend import StandardBackend
            self._standard_backend = StandardBackend(standard_config)
        if process_config is not None:  # Trusted construction only; never an IPC argument/plugin.
            from .process_backend import ProcessBackend
            self._process_backend = ProcessBackend(process_config)

    def _context(self, context):
        require(context == self.context, "PROJECT_IDENTITY_MISMATCH", "Service context mismatch")
        validate_context(context)

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
        if plan['backend_id'] == 'abaqus-standard-axial-2024-v1':
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

    def prepare(self, context, spec, snapshot, *, expires_at, process_scenario=None):
        self._context(context)
        config = configuration(snapshot)
        plan = prepare_plan(context, spec, config, expires_at)
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

    def _check(self, connection, context, plan, grant_id, run_id=None):
        if plan['backend_id'] == 'abaqus-standard-axial-2024-v1':
            from .standard_contract import check_plan as check_standard, check_grant as check_standard_grant
            check_standard(self, plan)
            row = connection.execute('SELECT body FROM grants WHERE grant_id=?', (grant_id,)).fetchone()
            consumed = connection.execute('SELECT run_id FROM consumption WHERE grant_id=?', (grant_id,)).fetchone()
            check_standard_grant(self, plan, json.loads(row[0]) if row else None, consumed[0] if consumed else None, run_id)
            return
        row = connection.execute("SELECT body FROM configuration WHERE id=1").fetchone()
        require(row is not None, "PLAN_STALE", "Missing explicit configuration")
        binding = None
        if plan["backend_id"] == "python-process-fixture-v1":
            require(self._process_backend is not None, "TEST_GRANT_ONLY", "Process fixture is not configured")
            binding = plan.get("process_fixture")
            self._process_backend.config.verify(binding)
        check_plan(context, plan, json.loads(row[0]), process_binding=binding)
        require(type(grant_id) is str and bool(grant_id), "GRANT_REQUIRED", "Registered grant ID required")
        row = connection.execute("SELECT body FROM grants WHERE grant_id=?", (grant_id,)).fetchone()
        consumed = connection.execute("SELECT run_id FROM consumption WHERE grant_id=?", (grant_id,)).fetchone()
        check_grant(context, plan, json.loads(row[0]) if row else None, self.store._session.authority_instance,
                    consumed[0] if consumed else None, run_id)

    def _existing_receipt(self, connection, namespace, key, request_digest):
        row = connection.execute("SELECT request_digest,body FROM receipts WHERE namespace=? AND key=?",
                                 (namespace, key)).fetchone()
        if row:
            require(row[0] == request_digest, "IDEMPOTENCY_CONFLICT", "Same key has different request content")
            return json.loads(row[1])
        return None

    def submit(self, context, request):
        self._context(context)
        request_digest = self._request(context, request)
        namespace = canonical_json([context.project_instance_id, self.client_namespace, "submit"])
        if not self.store.dispatch_allowed():
            # Restarted owners expose only read-only replay; the same digest and
            # receipt rules are shared by the direct API and IPC adapter.
            with self.store.read() as connection:
                receipt = self._existing_receipt(connection, namespace, request["idempotency_key"], request_digest)
            require(receipt is not None, "DISPATCH_PAUSED", "Owner is query-only; no new acceptance")
            return {"request_status": "ACCEPTED", "replayed": True, "receipt": receipt, "queue_id": None}
        replayed = False
        with self.store.transaction("accept") as connection:
            receipt = self._existing_receipt(connection, namespace, request["idempotency_key"], request_digest)
            if receipt:
                replayed = True
            else:
                plan = document(connection, "plans", "plan_id", request["plan_id"])
                require(plan["plan_digest"] == request["plan_digest"] and plan["job_id"] == request["job_id"]
                        and plan["job_revision"] == request["job_revision"], "GRANT_SCOPE_MISMATCH", "Request does not identify the fixed Job/Plan")
                self._check(connection, context, plan, request["grant_id"])
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
                if plan["backend_id"] == "python-process-fixture-v1":
                    run.update(backend_id=plan["backend_id"], phase="PROCESS_FIXTURE",
                               process_observation="NOT_STARTED", exit_verification="UNKNOWN",
                               process_records=[], process_exits=[])
                if plan['backend_id'] == 'abaqus-standard-axial-2024-v1':
                    require(request['retry_of'] is None, 'INVALID_RETRY', 'Standard automatic/replacement retry is unsupported')
                    run.update(backend_id=plan['backend_id'],phase='STANDARD_ANALYSIS',simulation=False,
                        process_observation='NOT_STARTED',exit_verification='UNKNOWN',process_records=[],process_exits=[],
                        member_completeness='UNKNOWN',overall_exit='UNKNOWN',launch_state='NOT_CALLED',
                        execution_phase='WAITING_START',
                        numerical_validation='NOT_RUN',odb_content_validation='NOT_RUN')
                connection.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)", (run["run_id"], run["job_id"], run["job_revision"],
                                   run["plan_id"], run["grant_id"], attempt, run["retry_of"], canonical_json(run)))
                event = append_event(connection, run["run_id"], "REQUEST_ACCEPTED", {"revision": 1})
                receipt = {"request_id": identifier("req"), "namespace": namespace,
                           "idempotency_key": request["idempotency_key"], "request_digest": request_digest,
                           "request_status": "ACCEPTED", "accepted_at": now(), "run_id": run["run_id"],
                           "job_id": run["job_id"], "accepted_sequence": event["project_sequence"], "initial_queue_state": "PENDING"}
                connection.execute("INSERT INTO receipts VALUES(?,?,?,?,?)", (namespace, request["idempotency_key"],
                                   request_digest, run["run_id"], canonical_json(receipt)))
                connection.execute("INSERT INTO consumption VALUES(?,?)", (run["grant_id"], run["run_id"]))
        try:
            self.store._checkpoint("accept:after_commit")
        except OSError as exc:
            raise ExecutionError("ACCEPTANCE_UNKNOWN", "Response failed after commit; query original key", stage="ACCEPT") from exc
        return {"request_status": "ACCEPTED", "replayed": replayed, "receipt": receipt, "queue_id": None}

    def execute_pending(self, context, run_id):
        try:
            with self.store.dispatch_scope():
                return self._execute_pending(context, run_id)
        except ExecutionError as exc:
            # A dispatch/storage failure never retracts a previously accepted receipt.
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
            if run["queue_state"] == "PENDING" and run["execution"] == "PLANNED":
                plan = document(connection, "plans", "plan_id", run["plan_id"])
                try:
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
                    run = update_run(connection, run, "START_INTENT", queue_state="DISPATCHED", execution="START_INTENT",
                                     owner_id=self.store._session.owner_id,
                                     owner_epoch=run["owner_epoch"] + (run["owner_id"] != self.store._session.owner_id),
                                     **({"backend_outcome": "UNKNOWN", "process_observation": "UNKNOWN"}
                                        if plan["backend_id"] == "python-process-fixture-v1" else {}))
                    if plan['backend_id'] == 'abaqus-standard-axial-2024-v1':
                        run=update_run(connection,run,'STANDARD_STARTING',execution_phase='STARTING')
                    claimed = True
        if pre_error:
            raise pre_error
        if not claimed:
            return self.store.query_run(context, run_id)
        completed = False
        try:
            self.store._checkpoint("dispatch:after_claim")
            if plan['backend_id'] == 'abaqus-standard-axial-2024-v1':
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
                result=self._standard_backend.execute(context,plan,run,record_standard,self.store._checkpoint,authorize_standard)
                from .standard_backend import persist_result
                self.store._checkpoint('standard:before_result_commit')
                persist_result(self,run_id,result)
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
                self._process_backend.execute(context, plan, run, record, self.store._checkpoint, authorize_start)
                completed = True
                from .process_validation import validate_process_artifact
                observation, validation = validate_process_artifact(context, plan, run)
                self.store._checkpoint("process:before_terminal")
            else:
                emission = self._backend.emit(context, plan, run)
                completed = True
                self.store._checkpoint("dispatch:after_artifact")
                with self.store.transaction("observe") as connection:
                    run = document(connection, "runs", "run_id", run_id)
                    run = update_run(connection, run, "FAKE_COMPLETED", execution="VALIDATING", backend_outcome="COMPLETED")
                observation, validation = validate_artifact(context, plan, run, emission)
            with self.store.transaction("terminal") as connection:
                run = document(connection, "runs", "run_id", run_id)
                connection.execute("INSERT INTO observations VALUES(?,?,?)", (observation["observation_id"], run_id, canonical_json(observation)))
                connection.execute("INSERT INTO validations VALUES(?,?,?)", (validation["validation_id"], run_id, canonical_json(validation)))
                update_run(connection, run, "VALIDATION_RECORDED", execution="FINISHED",
                           artifact_validation={"PASS": "VALID", "FAIL": "INVALID", "UNKNOWN": "UNKNOWN"}[validation["verdict"]],
                           validation_scope="simulation", evidence_refs=(observation["observation_id"], validation["validation_id"]))
                connection.execute("UPDATE slot SET run_id=NULL WHERE id=1 AND run_id=?", (run_id,))
        except (ExecutionError, OSError) as exc:
            if plan['backend_id'] == 'abaqus-standard-axial-2024-v1':
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
