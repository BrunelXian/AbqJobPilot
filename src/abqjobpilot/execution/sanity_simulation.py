"""Bindings for the exact TEST_ONLY Sanity route through the existing Fake backend."""

import json

from .models import RESOURCES, digest, require

ACTION = "simulate_once"
PERMIT_KIND = "SANITY_TEST_ONLY"
RECEIPT_VERSION = "sanity-simulation-receipt-v1"


def matches(plan):
    if plan.get("sanity", {}).get("mode") != "TEST_ONLY":
        return False
    from ..sanity_admission import BACKEND

    return plan["backend_id"] == BACKEND


def fake_plan(plan):
    require(matches(plan), "TEST_GRANT_ONLY", "The Fake projection requires exact TEST_ONLY Sanity")
    return {"plan_digest": plan["plan_digest"], "input_manifest": plan["input_manifest"],
            "config_snapshot": {"digest": digest(plan["runtime_binding"])}, "resources": RESOURCES}


def accepted_receipt(connection, plan, run):
    require(matches(plan) and run["backend_id"] == plan["backend_id"]
            and run["plan_id"] == plan["plan_id"] and run["plan_digest"] == plan["plan_digest"]
            and run["project_id"] == plan["sanity"]["project_id"]
            and run["project_instance_id"] == plan["project_instance_id"]
            and run["simulation"] is True and run["solver_conclusion"] == "NOT_RUN"
            and run["launch_state"] == "NOT_CALLED",
            "EVIDENCE_IDENTITY_MISMATCH", "Sanity exact Plan and simulation Run differ")
    row = connection.execute(
        "SELECT receipts.body FROM receipts JOIN consumption USING(run_id) "
        "WHERE receipts.run_id=? AND consumption.grant_id=?", (run["run_id"], run["grant_id"])).fetchone()
    require(row is not None, "EVIDENCE_INSUFFICIENT", "Original accepted Receipt and consumed Grant are required")
    receipt = json.loads(row[0])
    require(receipt["request_status"] == "ACCEPTED" and receipt["run_id"] == run["run_id"]
            and receipt["job_id"] == run["job_id"] == plan["job_id"]
            and receipt["idempotency_key"] == plan["sanity"]["request_key"],
            "EVIDENCE_IDENTITY_MISMATCH", "Sanity Run and original request Receipt differ")
    return receipt


def completion_receipt(connection, plan, run, observation, validation):
    accepted = accepted_receipt(connection, plan, run)
    permit = run["single_dispatch"]
    attempt = run["phase_attempt_id"]
    require(run.get("execution_backend") == "fake-v1" and permit.get("kind") == PERMIT_KIND
            and permit["state"] == "CLAIMED" and permit["phase_attempt_id"] == attempt
            and all(permit[key] == run[key] for key in ("run_id", "plan_digest", "owner_id", "grant_id"))
            and run["backend_outcome"] == "COMPLETED"
            and run["process_observation"] == run["exit_verification"] == "NOT_APPLICABLE"
            and run["process_records"] == run["process_exits"] == []
            and "managed_scope" not in run and "launch_intent" not in run
            and run["numerical_validation"] == run["odb_content_validation"] == "NOT_RUN",
            "EVIDENCE_INSUFFICIENT", "Original completed Fake attempt and claimed simulation permit required")
    require(all(record["run_id"] == run["run_id"] and record["phase_attempt_id"] == attempt
                for record in (observation, validation))
            and observation["kind"] == "FAKE_JSON" and observation["binding_status"] == "MATCHED"
            and validation["scope"] == "simulation" and validation["policy_id"] == "fake-result-v1"
            and validation["verdict"] == "PASS" and validation["evidence_refs"] == [observation["observation_id"]],
            "EVIDENCE_INSUFFICIENT", "Validated simulation evidence must belong to the same attempt")
    identity = ("project_id", "project_instance_id", "plan_id", "plan_digest", "run_id",
                "phase_attempt_id", "grant_id", "owner_id", "attempt_no")
    return {"contract_version": RECEIPT_VERSION, **{key: run[key] for key in identity},
            "acceptance_request_id": accepted["request_id"], "dispatch_operation_id": permit["operation_id"],
            "observation_id": observation["observation_id"], "validation_id": validation["validation_id"],
            "artifact_digest": observation["digest"], "recorded_at": validation["recorded_at"],
            "execution": "FINISHED", "execution_backend": "fake-v1", "simulation": True,
            "solver_conclusion": "NOT_RUN", "validation_verdict": "PASS"}


def require_completion(connection, plan, run):
    """Check the committed simulation proof for an idle stop without inventing process evidence."""
    observations = connection.execute("SELECT body FROM observations WHERE run_id=? LIMIT 2", (run["run_id"],)).fetchall()
    validations = connection.execute("SELECT body FROM validations WHERE run_id=? LIMIT 2", (run["run_id"],)).fetchall()
    require(len(observations) == len(validations) == 1 and run.get("artifact_validation") == "VALID",
            "SERVICE_NOT_IDLE", "Original simulation validation is required")
    receipt = completion_receipt(connection, plan, run, json.loads(observations[0][0]), json.loads(validations[0][0]))
    events = connection.execute(
        "SELECT body FROM events WHERE run_id=? AND json_extract(body,'$.type')='VALIDATION_RECORDED' LIMIT 2",
        (run["run_id"],)).fetchall()
    require(run.get("simulation_receipt") == receipt and len(events) == 1
            and json.loads(events[0][0])["payload"].get("simulation_receipt") == receipt,
        "SERVICE_NOT_IDLE", "Committed, attempt-bound simulation Receipt is required")
