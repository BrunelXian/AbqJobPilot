"""Owner-only extractor for committed synthetic Fake evidence.

The native source/launcher requires separate qualification. This backend does
not open an ODB or execute a program. Its canonical JSON is committed inline.
"""

from contextlib import ExitStack
import json
import os

from .delegated_grant import environment_enabled
from .models import (ExecutionError, RESOURCES, bytes_digest, canonical_json, digest,
                     fixed_fake_content, identifier, now, require)
from .odb_contract import FIXTURE, FIXTURE_OPT_IN, REQUEST, VERSION, check_request
from .paths import result_path
from .store import document, gate_view

ACTION = "extract_odb_fixture_v1"
VALUES = ("0.0000", "-0.0125", "-0.0250", "-0.0500")


def fixture_enabled(connection):
    row = connection.execute("SELECT value FROM meta WHERE key=?", (FIXTURE_OPT_IN,)).fetchone()
    return row is not None and row[0] == VERSION


def fixture_source(context, connection, run_id, namespace, receipt_id, pins):
    run = document(connection, "runs", "run_id", run_id)
    row = connection.execute("SELECT body FROM receipts WHERE run_id=? AND namespace=?",
                             (run_id, namespace)).fetchone()
    require(row is not None, "ODB_SOURCE_UNTRUSTED", "Source requires the original committed submission")
    receipt = json.loads(row[0])
    consumed = connection.execute("SELECT 1 FROM consumption WHERE run_id=? AND grant_id=?",
                                  (run_id, run["grant_id"])).fetchone()
    require(receipt["request_id"] == receipt_id and receipt["run_id"] == run_id
            and receipt["request_status"] == "ACCEPTED" and receipt["job_id"] == run["job_id"]
            and consumed is not None and run["project_id"] == context.project_id
            and run["project_instance_id"] == context.project_instance_id and run["backend_id"] == "fake-v1"
            and run["execution"] == "FINISHED" and run["backend_outcome"] == "COMPLETED"
            and run["simulation"] is True and run["solver_conclusion"] == "NOT_RUN"
            and run["artifact_validation"] == "VALID" and run["reconciliation"] == "NONE",
            "ODB_SOURCE_UNTRUSTED", "Source is outside the validated Fake receipt scope")
    plan = document(connection, "plans", "plan_id", run["plan_id"])
    require(run["plan_digest"] == plan["plan_digest"] == digest({k: v for k, v in plan.items() if k != "plan_digest"})
            and plan["context_digest"] == context.context_digest and plan["job_id"] == run["job_id"]
            and plan["backend_id"] == "fake-v1" and "delegated_admission" not in plan,
            "ODB_SOURCE_UNTRUSTED", "Original Fake Plan binding differs")
    observations = connection.execute("SELECT body FROM observations WHERE run_id=? LIMIT 2", (run_id,)).fetchall()
    validations = connection.execute("SELECT body FROM validations WHERE run_id=? LIMIT 2", (run_id,)).fetchall()
    require(len(observations) == len(validations) == 1, "ODB_SOURCE_UNTRUSTED", "Exact source evidence required")
    observed, validation = json.loads(observations[0][0]), json.loads(validations[0][0])
    require(all(record["run_id"] == run_id and record["phase_attempt_id"] == run["phase_attempt_id"]
                for record in (observed, validation))
            and observed["kind"] == "FAKE_JSON" and observed["binding_status"] == "MATCHED"
            and observed["provenance"] == "fake-v1" and validation["scope"] == "simulation"
            and validation["verdict"] == "PASS" and validation["policy_id"] == "fake-result-v1"
            and validation["evidence_refs"] == [observed["observation_id"]],
            "ODB_SOURCE_UNTRUSTED", "Source evidence belongs to another attempt or policy")

    from ..abaqus_preview.inputs import _open_pinned

    try:
        path = result_path(context, run_id)
        require(observed["path"] == str(path), "ODB_SOURCE_UNTRUSTED", "Source path differs from the owned artifact")
        stream = pins.enter_context(_open_pinned(path))
        info = os.fstat(stream.fileno())
        content = stream.read(RESOURCES["max_output_bytes"] + 1)
    except (OSError, ExecutionError) as exc:
        missing = isinstance(exc, FileNotFoundError) or getattr(exc, "code", None) == "INPUT_NOT_FOUND"
        raise ExecutionError("ODB_SOURCE_NOT_FOUND" if missing else "ODB_SOURCE_UNTRUSTED",
                             "Cannot open the original owned artifact") from exc
    require(observed["file_identity"] == {"device": info.st_dev, "inode": info.st_ino}
            and observed["size"] == info.st_size == len(content)
            and observed["mtime"] == info.st_mtime_ns and bytes_digest(content) == observed["digest"]
            and content == fixed_fake_content(plan, run),
            "ODB_SOURCE_UNTRUSTED", "Original source identity or content changed")
    return {"kind": "FAKE_RESULT_JSON", "run_id": run_id, "phase_attempt_id": run["phase_attempt_id"],
            "plan_digest": plan["plan_digest"], "receipt_id": receipt_id,
            "observation_id": observed["observation_id"], "validation_id": validation["validation_id"],
            "sha256": observed["digest"]}


def extract(service, context, run_id, request):
    service._context(context)
    check_request(run_id, request)
    require(request["mode"] == "TEST_ONLY", "CAPABILITY_UNAVAILABLE", "Native ODB execution is unqualified")
    namespace = canonical_json([context.project_instance_id, service.client_namespace, ACTION])
    source_namespace = canonical_json([context.project_instance_id, service.client_namespace, "submit"])
    key = request["idempotency_key"]
    fingerprint = digest({"run_id": run_id, "request": request})
    with ExitStack() as pins, service.store.transaction("management") as connection:
        require(environment_enabled(service, connection) and fixture_enabled(connection),
                "CAPABILITY_UNAVAILABLE", "The isolated fixture backend was not provisioned")
        row = connection.execute("SELECT request_digest,body FROM management_receipts WHERE namespace=? AND key=?",
                                 (namespace, key)).fetchone()
        if row:
            require(row[0] == fingerprint, "IDEMPOTENCY_CONFLICT", "Extraction key already names another request")
            return {"replayed": True, "receipt": json.loads(row[1])}
        gate = gate_view(connection)
        session = service.store._session
        require(gate["state"] == "OPEN" and gate["owner_id"] == session.owner_id and session.active_dispatches == 0
                and connection.execute("SELECT run_id FROM slot WHERE id=1").fetchone()[0] is None,
                "DISPATCH_PAUSED", "Extraction requires the active idle TEST_ONLY Owner")
        source = fixture_source(context, connection, run_id, source_namespace, request["receipt_id"], pins)
        start = request["first_frame"]
        output = {"contract_version": VERSION, "simulation": True, "solver_conclusion": "NOT_RUN",
                  "native_odb_verified": False, "source": source, "script_version": FIXTURE,
                  "parameters": {k: request[k] for k in REQUEST if k not in ("contract_version", "idempotency_key", "receipt_id")},
                  "rows": [{"frame": index, "fixture_value": VALUES[index]}
                           for index in range(start, start + request["frame_count"])]}
        content = canonical_json(output).encode("utf-8")
        receipt = {"operation_id": identifier("op"), "operation": ACTION, "operation_status": "TEST_ONLY_COMPLETED",
                   "project_id": context.project_id, "project_instance_id": context.project_instance_id,
                   "owner_id": session.owner_id, "idempotency_key": key, "recorded_at": now(),
                   "artifact": {"format": "JSON", "sha256": bytes_digest(content), "size": len(content), "data": output}}
        service.store._checkpoint("odb_fixture:before_receipt")
        connection.execute("INSERT INTO management_receipts VALUES(?,?,?,?,?)",
                           (namespace, key, fingerprint, receipt["operation_id"], canonical_json(receipt)))
    return {"replayed": False, "receipt": receipt}
