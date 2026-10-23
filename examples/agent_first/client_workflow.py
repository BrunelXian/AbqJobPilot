"""Connect-only TEST_ONLY example. No pytest, storage, approval or process launch."""

import argparse
import json
import os
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path, help="Explicit Dev import root; not an environment installation")
    parser.add_argument("--connection", required=True, type=Path, help="Private connection material outside session/export")
    parser.add_argument("--offer", required=True, type=Path, help="Private exact execution request prepared by operator")
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=["submit", "complete"])
    parser.add_argument("--validation-ticket", type=Path)
    parser.add_argument("--export-root", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    data_root = args.session.resolve(strict=True).parent
    read_roots = [args.source.resolve(), data_root, Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()]
    # Effective import guard: ordinary clients cannot accidentally acquire owner/store/issuer capabilities.
    def guard(event, values):
        if event == "import" and (values[0].startswith(("tests", "pytest")) or values[0] in {
            "abqjobpilot.execution.store", "abqjobpilot.execution.service", "abqjobpilot.execution.supervisor",
            "abqjobpilot.execution.test_authority", "abqjobpilot.execution.process_backend",
            "abqjobpilot.config", "abqjobpilot.runner_core", "abqjobpilot.settings_store", "abqjobpilot.project"}):
            raise RuntimeError("Client import boundary violated")
        if event in {"subprocess.Popen", "os.system", "sqlite3.connect"}:
            raise RuntimeError("Client execution/storage boundary violated")
        if event == "open" and isinstance(values[0], (str, bytes)):
            path = Path(os.fsdecode(values[0])).absolute()
            writing = bool(values[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if not any(path.is_relative_to(p) for p in read_roots) or (writing and not path.is_relative_to(data_root)):
                raise RuntimeError("Client I/O boundary violated")
    sys.addaudithook(guard)
    from abqjobpilot.execution.client import FakeClient
    from abqjobpilot.execution.models import ExecutionError, canonical_json, require
    from abqjobpilot.execution.paths import confined

    def read(path):
        require(path.is_absolute() and path.stat().st_size <= 65536, "INVALID_REQUEST", "Explicit bounded handoff file required")
        return json.loads(path.read_text(encoding="utf-8"))
    require(args.session.is_absolute() and args.session.is_dir(), "INVALID_REQUEST", "Existing explicit session directory required")
    def save(name, value):
        path = confined(args.session, args.session / name)
        with path.open("x", encoding="utf-8") as stream: stream.write(canonical_json(value))
    key = run_id = None
    try:
        connection, offer = read(args.connection), read(args.offer)
        require(not args.connection.is_relative_to(args.session) and not args.offer.is_relative_to(args.session),
                "INVALID_REQUEST", "Private materials must be outside the public session")
        client = FakeClient(connection["endpoint"], connection["credential"])
        request = offer["request"]; key = request["idempotency_key"]
        capability = client.health()
        require(capability["execution_scope"] == "TEST_ONLY" and capability["process_fixture_enabled"], "TEST_GRANT_ONLY", "Fixed test backend unavailable")
        plan = client.inspect_plan(request["plan_id"], request["plan_digest"])
        require(plan["project_instance_id"] == request["project_instance_id"] == connection["endpoint"]["project_instance_id"]
                and plan["backend_id"] == "python-process-fixture-v1" and plan["backend_version"] == 1
                and plan["job_id"] == request["job_id"] and plan["job_revision"] == request["job_revision"],
                "PROJECT_IDENTITY_MISMATCH", "Handoff and public fixed plan disagree")
        if args.phase == "submit":
            save("capabilities.json", {k: capability[k] for k in ("operations", "execution_scope", "backends", "plan_preparation", "slot_scope")})
            save("plan.json", plan)
            try:
                client.submit({**request, "grant_id": "unregistered", "idempotency_key": key + "-rejected"})
                raise RuntimeError("Unregistered execution grant was accepted")
            except ExecutionError as exc:
                require(exc.code == "GRANT_REQUIRED", "INVALID_REQUEST", "Unexpected refusal branch")
                save("rejection.json", {"code": exc.code, "request_status": "REJECTED", "request_key": key + "-rejected",
                                       "run_id": None, "next_step": "Obtain an exact TEST_ONLY grant from the trusted operator"})
            accepted = client.submit(request); run_id = accepted["receipt"]["run_id"]
            save("session.json", {"project_instance_id": plan["project_instance_id"], "plan_id": plan["plan_id"],
                                  "plan_digest": plan["plan_digest"], "idempotency_key": key, "run_id": run_id,
                                  "receipt": accepted["receipt"]})
            save("accepted.json", {"request_status": accepted["request_status"], "replayed": accepted["replayed"], "run_id": run_id,
                                   "client_pid": os.getpid()})
            return 0
        session = read(args.session / "session.json"); run_id = session["run_id"]
        require(session["project_instance_id"] == plan["project_instance_id"] and session["plan_digest"] == plan["plan_digest"]
                and session["idempotency_key"] == key, "PROJECT_IDENTITY_MISMATCH", "Session and handoff mismatch")
        require(client.receipt(key) == session["receipt"], "STATE_CONFLICT", "Original receipt differs")
        replay = client.submit(request)
        require(replay["replayed"] and replay["receipt"] == session["receipt"], "STATE_CONFLICT", "Replay must preserve receipt")
        deadline = time.monotonic() + 20
        while True:
            run = client.run(run_id)
            if run["execution"] == "FINISHED": break
            require(run["reconciliation_requirement"] != "RECONCILIATION_REQUIRED" or run["execution"] in {"START_INTENT", "VALIDATING"},
                    "RECONCILIATION_REQUIRED", "Explicit owner review required")
            require(time.monotonic() < deadline, "COMMUNICATION_UNKNOWN", "Wait budget ended; query the same Run")
            time.sleep(0.05)
        require(run["exit_verification"] == "VERIFIED" and run["solver_conclusion"] == "NOT_RUN",
                "VALIDATION_PRECONDITION_FAILED", "Recorded exit prerequisites unavailable")
        cursor = 0; refs = []
        for _ in range(16):
            events = client.events(cursor, 64)
            if not events: break
            cursor = events[-1]["project_sequence"]
            refs.extend({k: e[k] for k in ("event_id", "run_sequence", "project_sequence", "type", "recorded_at")}
                        for e in events if e["run_id"] == run_id)
        else: raise ExecutionError("LIMIT_EXCEEDED", "Event polling bound exceeded")
        require(args.validation_ticket is not None, "MANAGEMENT_GRANT_REQUIRED", "Separate operator validation ticket required")
        validation_request = read(args.validation_ticket)
        require(not args.validation_ticket.is_relative_to(args.session) and
                (args.export_root is None or not args.validation_ticket.is_relative_to(args.export_root)),
                "INVALID_REQUEST", "Private validation ticket must stay outside session/export")
        require(validation_request["run_id"] == run_id, "PROJECT_IDENTITY_MISMATCH", "Validation ticket targets another Run")
        validated = client.validate_run(validation_request)
        repeated = client.validate_run(validation_request)
        require(repeated["replayed"] and repeated["receipt"] == validated["receipt"], "STATE_CONFLICT", "Validation replay changed")
        report = client.diagnose(run_id)
        require(args.export_root is not None, "INVALID_REQUEST", "Explicit export root required")
        client.export_diagnostic(report, export_root=args.export_root, target=args.export_root / "diagnostic.json")
        save("complete.json", {"client_pid": os.getpid(), "request_status": "ACCEPTED", "replayed": True,
             "run_id": run_id, "original_receipt": session["receipt"], "event_cursor": cursor, "event_refs": refs,
             "run": {k: report["body"]["facts"]["run"][k] for k in ("execution", "backend_outcome", "process_observation",
                     "exit_verification", "artifact_validation", "solver_conclusion", "reconciliation")},
             "dispatch_gate": report["body"]["facts"]["dispatch_gate"],
             "explicit_validation": validated["receipt"]["projection_at_commit"],
             "validation_records": report["body"]["facts"]["validations"], "diagnostic_view": report["body"]["view"],
             "export_content_digest": report["content_digest"], "scope": "historical_TEST_ONLY_records_not_current_process_health"})
        return 0
    except ExecutionError as exc:
        save("error-" + args.phase + ".json", {"code": exc.code, "request_key": key, "run_id": run_id,
             "next_step": "Query original request key and Run; do not infer cancellation or start a new attempt"})
        return 2
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        # Never serialize a private handoff, exception payload or traceback.
        save("error-" + args.phase + ".json", {"code": "CLIENT_WORKFLOW_UNCONFIRMED", "request_key": key, "run_id": run_id,
             "next_step": "Inspect public session records; query original key before any new submission"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
