"""Explicit Windows test owner; Fake by default, with bounded IPC and independent dispatch."""

import argparse
import hmac
import json
from pathlib import Path
import socket
import threading

from .models import ExecutionError, ProjectContext, canonical_json, fields, integer, require, text
from .paths import confined
from .protocol import (IO_TIMEOUT, MAX_CONNECTIONS, MAX_EVENTS, MAX_REQUEST, MAX_RESPONSE,
                       PROTOCOL, receive, send)
from .service import ExecutionService
from .store import acquire_supervisor_store

OPERATIONS = ("health", "submit", "receipt", "run", "events", "validations", "preview_reconciliation",
              "apply_reconciliation", "resume_dispatch", "dispatch_gate", "management_receipt", "reconciliations", "diagnose",
              "preview_process_reconciliation", "apply_process_reconciliation", "inspect_plan", "validate_run", "progress",
              "preview_closeout", "apply_closeout", "project_view", "lifecycle_stop", "product_standard_control")


def load_bootstrap(explicit_test_root, path):
    source = confined(explicit_test_root, path, exists=True)
    require(source.stat().st_size <= MAX_REQUEST, "INVALID_REQUEST", "Bootstrap exceeds bound")
    data = json.loads(source.read_text(encoding="utf-8"))
    fields(data, ("context", "authority_instance", "credential", "client_namespace", "endpoint_file"))
    context = ProjectContext(**data["context"])
    require(context.test_root == str(Path(explicit_test_root).resolve()), "PROJECT_IDENTITY_MISMATCH", "Wrong explicit test root")
    require(not source.is_relative_to(Path(context.root)), "INVALID_REQUEST", "Private bootstrap must be outside exportable Project")
    for key in ("authority_instance", "credential", "client_namespace"):
        text(data[key])
    require(len(data["credential"]) >= 32, "INVALID_REQUEST", "Explicit high-entropy local credential required")
    data["endpoint_file"] = str(confined(context.test_root, data["endpoint_file"]))
    return context, data


class FakeSupervisor:
    def __init__(self, context, bootstrap, *, process_config=None, standard_config=None, lifecycle=None):
        self.context = context
        if lifecycle is not None:
            from .lifecycle import LifecycleControl
            require(type(lifecycle) is LifecycleControl and
                    ((standard_config is None and lifecycle.standard_binding is None) or
                     (standard_config is not None and lifecycle.standard_binding is not None)),
                    'LIFECYCLE_SCOPE_UNSUPPORTED','Exact provisioned lifecycle profile required')
        self.lifecycle=lifecycle
        self.store = acquire_supervisor_store(context, bootstrap["authority_instance"],idle_only=lifecycle is not None,
                                              lifecycle_admit=lifecycle.admit if lifecycle else None,
                                              standard_binding=lifecycle.standard_binding if lifecycle else None)
        self._stop = threading.Event()
        self._handlers = set()
        self._handlers_lock = threading.Lock()
        self._capacity = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self._credential = bootstrap["credential"]
        self.last_error = None
        self.listener = None
        try:
            self.service = ExecutionService(context, self.store, client_namespace=bootstrap["client_namespace"], process_config=process_config, standard_config=standard_config)
            if lifecycle and lifecycle.standard_binding:
                from .product_standard import ProductStandardControl
                self.service.product_control=ProductStandardControl(lifecycle.standard_binding)
            self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self.listener.bind(("127.0.0.1", 0))
            self.listener.listen(MAX_CONNECTIONS)
            self.listener.settimeout(0.1)
            self.endpoint = {"protocol": PROTOCOL, "host": "127.0.0.1", "port": self.listener.getsockname()[1],
                             "project_id": context.project_id, "project_instance_id": context.project_instance_id,
                             "context_digest": context.context_digest, "owner_id": self.store._session.owner_id,
                             "process": self.store._session.lease.process, "execution_store": context.execution_store}
            for target in (Path(context.root) / "owner.json", Path(bootstrap["endpoint_file"])):
                target = confined(context.test_root, target)
                temporary = target.with_name(target.name + ".tmp")
                confined(context.test_root, temporary)
                temporary.write_text(canonical_json(self.endpoint), encoding="utf-8")
                temporary.replace(target)
        except BaseException:
            if self.listener:
                self.listener.close()
            self.store.close()
            raise

    def _checkpoint(self, name):
        """Trusted test harness seam, never RPC configurable. No normal behavior."""

    @property
    def dispatch_enabled(self):
        if self.service.product_control: return self.service.product_control.pending(self.service) is not None
        return self.store.dispatch_allowed()

    def _work(self):
        while not self._stop.wait(0.02):
            try:
                if not self.dispatch_enabled:
                    continue
                run_id = (self.service.product_control.pending(self.service) if self.service.product_control
                          else self.store.pending_for_owner())
                if run_id:
                    self.service.execute_pending(self.context, run_id)
            except ExecutionError as exc:
                self.last_error = exc.to_dict()
                # Conservative stop on any dispatch/evidence/store failure; no retry loop.
                try:
                    self.store.pause_after_error()
                except ExecutionError:
                    pass  # Inaccessible/maintenance storage cannot admit a new dispatch.
            except Exception:
                self.last_error = ExecutionError("OWNER_WORKER_FAILED", "Worker stopped; explicit diagnosis required",
                                                 stage="DISPATCH", reconcile=True).to_dict()
                try:
                    self.store.pause_after_error()
                except ExecutionError:
                    pass

    def _invoke(self, operation, args):
        ctx = self.context
        if operation == 'product_standard_control':
            fields(args, ('request',))
            require(self.service.product_control is not None, 'CAPABILITY_UNAVAILABLE', 'No product Standard control')
            result=self.service.product_control.invoke(self.service,args['request'])
            self._checkpoint('product_control:before_response')
            return result
        if operation == 'lifecycle_stop':
            fields(args,('request',))
            require(self.lifecycle is not None,'CAPABILITY_UNAVAILABLE','Existing owner has no product stop capability')
            result=self.lifecycle.stop(self.service,args['request'])
            self._checkpoint('lifecycle_stop:before_response')
            return result
        if operation == 'project_view':
            fields(args, ('before_row','limit'))
            return self.service.project_view(ctx, args['before_row'], args['limit'])
        if operation == "progress":
            fields(args, ("run_id", "after_sequence", "limit"))
            from .progress_log import read_progress
            return read_progress(self.store, ctx, args['run_id'], args['after_sequence'], args['limit'])
        if operation == "inspect_plan":
            fields(args, ("plan_id", "expected_digest"))
            return self.service.inspect_plan(ctx, args["plan_id"], args["expected_digest"])
        if operation == "validate_run":
            fields(args, ("request",))
            result = self.service.validate_run(ctx, args["request"])
            self._checkpoint("management:before_response")
            return result
        if operation == "diagnose":
            fields(args, ("run_id",))
            result = self.store.diagnose(ctx, args["run_id"])
            self._checkpoint("diagnostic:before_response")
            return result
        if operation == "health":
            fields(args, ())
            return {"operations": [v for v in OPERATIONS if v!='lifecycle_stop' or self.lifecycle is not None], "backend": "abaqus-standard-axial-2024-v1" if self.service._standard_backend is not None else "fake-v1", "simulation": self.service._standard_backend is None,
                    'lifecycle_start_id':self.lifecycle.start_id if self.lifecycle else None,
                    "execution_scope": "REAL_FIXED_STANDARD_AND_TEST_ONLY" if self.service._standard_backend is not None else "TEST_ONLY", "plan_preparation": "trusted_operator_preprovisioned",
                    "backends": [{"backend_id": "fake-v1", "version": 1}] +
                                ([{"backend_id": "python-process-fixture-v1", "version": 1}] if self.service._process_backend is not None else []) +
                                ([{"backend_id": "abaqus-standard-axial-2024-v1", "version": 1}] if self.service._standard_backend is not None else []),
                    "process_fixture_enabled": self.service._process_backend is not None,
                    "dispatch_enabled": self.dispatch_enabled, "slot_scope": "experiment_store",
                    "process": self.endpoint["process"], "max_events": MAX_EVENTS,
                    "max_connections": MAX_CONNECTIONS, "max_request": MAX_REQUEST, "max_response": MAX_RESPONSE,
                    "io_timeout_ms": int(IO_TIMEOUT * 1000), "last_error": self.last_error}
        if operation == "submit":
            fields(args, ("request",))
            result = self.service.submit(ctx, args["request"])
            self._checkpoint("submit:before_response")
            return result
        if operation == "preview_reconciliation":
            fields(args, ("run_id",))
            return self.service.preview_reconciliation(ctx, args["run_id"])
        if operation == 'preview_closeout':
            fields(args,('run_id',))
            return self.service.preview_closeout(ctx,args['run_id'])
        if operation == 'apply_closeout':
            fields(args,('request',))
            result=self.service.apply_closeout(ctx,args['request'])
            self._checkpoint('management:before_response')
            return result
        if operation == "preview_process_reconciliation":
            fields(args, ("run_id",))
            return self.service.preview_process_reconciliation(ctx, args["run_id"])
        if operation == "apply_process_reconciliation":
            fields(args, ("request",))
            result = self.service.apply_process_reconciliation(ctx, args["request"])
            self._checkpoint("management:before_response")
            return result
        if operation in {"apply_reconciliation", "resume_dispatch"}:
            fields(args, ("request",))
            result = (self.service.apply_reconciliation(ctx, args["request"]) if operation == "apply_reconciliation"
                      else self.service.resume_dispatch(ctx, args["request"]))
            self._checkpoint("management:before_response")
            return result
        if operation == "dispatch_gate":
            fields(args, ())
            return self.store.gate()
        if operation == "management_receipt":
            fields(args, ("action", "idempotency_key"))
            text(args["action"])
            text(args["idempotency_key"])
            return self.store.management_receipt(self.service.client_namespace, args["action"], args["idempotency_key"])
        if operation == "reconciliations":
            fields(args, ("run_id",))
            text(args["run_id"])
            return self.store.reconciliations(ctx, args["run_id"])
        if operation == "receipt":
            fields(args, ("idempotency_key",))
            text(args["idempotency_key"])
            return self.store.query_receipt(ctx, self.service.client_namespace, args["idempotency_key"])
        if operation == "run":
            fields(args, ("run_id",))
            text(args["run_id"])
            return self.store.query_run(ctx, args["run_id"])
        if operation == "validations":
            fields(args, ("run_id",))
            text(args["run_id"])
            return self.store.validations(ctx, args["run_id"])
        if operation == "events":
            fields(args, ("after_sequence", "limit"))
            integer(args["after_sequence"])
            integer(args["limit"], 1)
            require(args["limit"] <= MAX_EVENTS, "INVALID_REQUEST", "Event page exceeds limit")
            return self.store.events(ctx, args["after_sequence"], args["limit"])
        raise ExecutionError("UNKNOWN_OPERATION", "Operation is not supported")

    def _handle(self, stream):
        request_id = None
        identity = {key: self.endpoint[key] for key in ("project_id", "project_instance_id", "context_digest", "owner_id")}
        try:
            with stream:
                try:
                    message = receive(stream, MAX_REQUEST)
                    fields(message, ("protocol", "request_id", "project_id", "project_instance_id", "context_digest",
                                     "owner_id", "credential", "operation", "arguments"))
                    text(message["request_id"])
                    if message["operation"] == "diagnose":
                        from .diagnostics import valid_id
                        require(valid_id(message["request_id"], "wire"), "INVALID_REQUEST", "Invalid diagnostic transport identity")
                    request_id = message["request_id"]
                    text(message["credential"])
                    require(hmac.compare_digest(message["credential"].encode("utf-8"), self._credential.encode("utf-8")),
                            "AUTHENTICATION_FAILED", "Local connection credential rejected")
                    require(message["protocol"] == PROTOCOL, "PROTOCOL_MISMATCH", "Protocol version rejected")
                    require(all(message[key] == value for key, value in identity.items()),
                            "ENDPOINT_IDENTITY_MISMATCH", "Wrong Project, instance or owner")
                    require(type(message["operation"]) is str and message["operation"] in OPERATIONS,
                            "UNKNOWN_OPERATION", "Operation is not supported")
                    result = self._invoke(message["operation"], message["arguments"])
                    ok = True
                except ExecutionError as exc:
                    result, ok = exc.to_dict(), False
                except (ValueError, TypeError, KeyError, RecursionError):
                    result, ok = ExecutionError("INVALID_REQUEST", "Malformed request").to_dict(), False
                send(stream, {"protocol": PROTOCOL, "request_id": request_id, **identity,
                              "ok": ok, "result": result}, MAX_RESPONSE)
        except (OSError, EOFError, ExecutionError):
            pass  # Communication lifetime never cancels an accepted Run or the worker.
        finally:
            self._capacity.release()
            with self._handlers_lock:
                self._handlers.discard(threading.current_thread())

    def serve(self, stop_event=None):
        worker = threading.Thread(target=self._work, name="fake-owner-worker")
        worker.start()
        try:
            while not self._stop.is_set() and not (stop_event and stop_event.is_set()) and not (self.lifecycle and self.lifecycle.stop_requested.is_set()):
                try:
                    stream, _ = self.listener.accept()
                except TimeoutError:
                    continue
                if not self._capacity.acquire(blocking=False):
                    stream.close()
                    continue
                thread = threading.Thread(target=self._handle, args=(stream,), name="fake-ipc-request")
                with self._handlers_lock:
                    self._handlers.add(thread)
                thread.start()
        finally:
            self._stop.set()
            self.listener.close()
            worker.join()  # Do not release the OS owner while a Fake effect can still write.
            with self._handlers_lock:
                handlers = list(self._handlers)
            for thread in handlers:
                thread.join()
            # A normal owner shutdown is control-plane quiescence, never Solver
            # exit evidence. Persist PAUSED without clearing Runs, slots/intents.
            self.store.pause_after_error()
            self.store.close()


def main():
    parser = argparse.ArgumentParser(description="Explicit Fake-only experiment Supervisor")
    parser.add_argument("--test-root", required=True)
    parser.add_argument("--bootstrap", required=True)
    args = parser.parse_args()
    context, bootstrap = load_bootstrap(args.test_root, args.bootstrap)
    FakeSupervisor(context, bootstrap).serve()


if __name__ == "__main__":
    main()
