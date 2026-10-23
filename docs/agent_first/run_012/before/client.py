"""Thin connect-only client. No store access, owner startup or owner shutdown."""

from .models import ExecutionError, fields, identifier, integer, require, text
from .protocol import MAX_REQUEST, MAX_RESPONSE, PROTOCOL, connect, receive, send


class FakeClient:
    def __init__(self, endpoint, credential):
        fields(endpoint, ("protocol", "host", "port", "project_id", "project_instance_id",
                          "context_digest", "owner_id", "process", "execution_store"))
        require(endpoint["protocol"] == PROTOCOL and endpoint["host"] == "127.0.0.1",
                "PROTOCOL_MISMATCH", "Only the local experimental protocol is supported")
        integer(endpoint["port"], 1)
        require(endpoint["port"] <= 65535, "INVALID_REQUEST", "Invalid local port")
        text(credential)
        self.endpoint = dict(endpoint)
        self._credential = credential

    def call(self, operation, arguments):
        request_id = identifier("wire")
        identity = {key: self.endpoint[key] for key in
                    ("project_id", "project_instance_id", "context_digest", "owner_id")}
        message = {"protocol": PROTOCOL, "request_id": request_id, **identity,
                   "credential": self._credential, "operation": operation, "arguments": arguments}
        try:
            with connect(self.endpoint["port"]) as stream:
                send(stream, message, MAX_REQUEST)
                response = receive(stream, MAX_RESPONSE)
        except (OSError, EOFError) as exc:
            raise ExecutionError("ACCEPTANCE_UNKNOWN" if operation in {"submit", "apply_reconciliation", "apply_process_reconciliation", "resume_dispatch", "validate_run"} else "COMMUNICATION_UNKNOWN",
                                 "Connection ended; query/replay original business key",
                                 stage="TRANSPORT") from exc
        fields(response, ("protocol", "request_id", "project_id", "project_instance_id", "context_digest",
                          "owner_id", "ok", "result"))
        require(response["protocol"] == PROTOCOL and response["request_id"] == request_id
                and all(response[key] == value for key, value in identity.items()),
                "ENDPOINT_IDENTITY_MISMATCH", "Response is from another or stale owner")
        if response["ok"] is not True:
            error = response["result"]["error"]
            raise ExecutionError(error["code"], error["message"], stage=error["stage"],
                                 run_id=error["run_id"], reconcile=error["requires_reconciliation"],
                                 project_instance_id=error["project_instance_id"], evidence_refs=error["evidence_refs"])
        return response["result"]

    def health(self):
        return self.call("health", {})

    def inspect_plan(self, plan_id, expected_digest):
        return self.call("inspect_plan", {"plan_id": plan_id, "expected_digest": expected_digest})

    def validate_run(self, request):
        return self.call("validate_run", {"request": request})

    def submit(self, request):
        return self.call("submit", {"request": request})

    def receipt(self, key):
        return self.call("receipt", {"idempotency_key": key})

    def run(self, run_id):
        return self.call("run", {"run_id": run_id})

    def events(self, after_sequence=0, limit=64):
        return self.call("events", {"after_sequence": after_sequence, "limit": limit})

    def validations(self, run_id):
        return self.call("validations", {"run_id": run_id})

    def preview_reconciliation(self, run_id):
        return self.call("preview_reconciliation", {"run_id": run_id})

    def apply_reconciliation(self, request):
        return self.call("apply_reconciliation", {"request": request})

    def resume_dispatch(self, request):
        return self.call("resume_dispatch", {"request": request})

    def preview_process_reconciliation(self, run_id):
        return self.call("preview_process_reconciliation", {"run_id": run_id})

    def apply_process_reconciliation(self, request):
        return self.call("apply_process_reconciliation", {"request": request})

    def dispatch_gate(self):
        return self.call("dispatch_gate", {})

    def management_receipt(self, action, key):
        return self.call("management_receipt", {"action": action, "idempotency_key": key})

    def reconciliations(self, run_id):
        return self.call("reconciliations", {"run_id": run_id})

    def diagnose(self, run_id):
        return self.call("diagnose", {"run_id": run_id})

    @staticmethod
    def export_diagnostic(report, *, export_root, target):
        from .audit_export import export_report
        return export_report(report, export_root=export_root, target=target)
