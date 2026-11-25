"""Public read-only evidence composition. Real Solver provenance stays unqualified.

The actual client uses existing read RPC operations. The explicitly separate
offline port is a deterministic fixture, never authenticated AF or real evidence.
"""

import copy

from .models import canonical_json, digest, fields, integer, require
from .rod_evidence import read_synthetic_dat
from .rod_profile import _label
from .rod_review import _sha
from .store import document

SCHEMA = "af-rod-public-evidence-bundle-v1"
FAKE_PLAN_SCHEMA = "af-public-fake-plan-v1"


def inspect_fake_plan(service, context, plan_id, expected_digest):
    """New bounded read projection of an existing persisted Fake Plan only."""
    service._context(context)
    with service.store.read() as conn:
        plan = document(conn, "plans", "plan_id", plan_id)
    require(
        plan["backend_id"] == "fake-v1"
        and plan["backend_version"] == 1
        and plan["project_instance_id"] == context.project_instance_id
        and plan["context_digest"] == context.context_digest
        and plan["plan_digest"]
        == expected_digest
        == digest({k: v for k, v in plan.items() if k != "plan_digest"}),
        "PLAN_STALE",
        "Exact persisted Fake Plan required",
    )
    require(
        len(plan["input_manifest"]) == 1,
        "UNSUPPORTED_EVIDENCE_POLICY",
        "One exact Fake input required by this evidence interface",
    )
    item = plan["input_manifest"][0]
    _sha(item["digest"])
    integer(item["size"], 1)
    return {
        "schema": FAKE_PLAN_SCHEMA,
        "source": "PERSISTED_FAKE_PLAN",
        "project_id": context.project_id,
        "project_instance_id": context.project_instance_id,
        "plan_id": plan_id,
        "plan_digest": expected_digest,
        "backend_id": "fake-v1",
        "backend_version": 1,
        "input_digest": item["digest"],
        "input_size": item["size"],
        "resources_digest": digest(plan["resources"]),
        "output_identity": digest(plan["output_policy"]),
        "configuration_digest": plan["config_snapshot"]["digest"],
        "execution_authorized": False,
    }


class OfflineReadPort:
    """Explicit synthetic public-port response fixture; no connection or Store."""

    def __init__(self, *, plan, receipt, run, events, validations):
        self.records = copy.deepcopy(
            dict(
                plan=plan,
                receipt=receipt,
                run=run,
                events=events,
                validations=validations,
            )
        )

    def inspect_plan(self, plan_id, expected_digest):
        require(
            self.records["plan"]["plan_id"] == plan_id
            and self.records["plan"]["plan_digest"] == expected_digest,
            "PLAN_STALE",
            "Fixture Plan lookup differs",
        )
        return copy.deepcopy(self.records["plan"])

    def receipt(self, key):
        require(
            self.records["receipt"]["idempotency_key"] == key,
            "REQUEST_UNKNOWN",
            "Fixture receipt lookup differs",
        )
        return copy.deepcopy(self.records["receipt"])

    def run(self, run_id):
        require(
            self.records["run"]["run_id"] == run_id,
            "RUN_UNKNOWN",
            "Fixture Run lookup differs",
        )
        return copy.deepcopy(self.records["run"])

    def events(self, after_sequence=0, limit=64):
        return copy.deepcopy(
            [
                v
                for v in self.records["events"]
                if v["project_sequence"] > after_sequence
            ][:limit]
        )

    def validations(self, run_id):
        self.run(run_id)
        return copy.deepcopy(self.records["validations"])


def _snapshot(client, fake, run_id):
    result = {
        "plan": client.inspect_plan(fake["plan_id"], fake["plan_digest"]),
        "receipt": client.receipt(fake["request_key"]),
        "run": client.run(run_id),
        "events": client.events(0, 64),
        "validations": client.validations(run_id),
    }
    require(
        all(type(result[key]) is dict for key in ("plan", "run"))
        and type(result["receipt"]) in (dict, type(None))
        and type(result["events"]) is list
        and type(result["validations"]) is list
        and all(
            type(value) is dict
            for key in ("events", "validations")
            for value in result[key]
        ),
        "EVIDENCE_INCOMPLETE",
        "Typed public response records required",
    )
    require(
        len(canonical_json(result).encode("utf-8")) <= 262144,
        "LIMIT_EXCEEDED",
        "Bounded public evidence records required",
    )
    return result


def read_test_evidence(
    product,
    client,
    *,
    rod_plan_ref,
    fake_plan_ref,
    run_id,
    receipt_id,
    phase_attempt_id,
    evidence_key,
    output_digest,
    goal_revision,
    model_revision,
    at_time,
):
    """Read exact public persisted records and separately bound synthetic bytes.

    No arbitrary pathname, latest-Run discovery, write operation, retry, real
    source switch or caller-controlled verification conclusion is accepted.
    """
    from .client import FakeClient

    require(
        type(client) in (FakeClient, OfflineReadPort),
        "UNSUPPORTED_EVIDENCE_PORT",
        "An explicit public IPC client or labelled offline fixture is required",
    )
    source = (
        "AF_FAKE_IPC_PLUS_SYNTHETIC_DAT"
        if type(client) is FakeClient
        else "OFFLINE_PUBLIC_PORT_FIXTURE_PLUS_SYNTHETIC_DAT"
    )
    for value in (goal_revision, model_revision):
        integer(value, 1)
    fields(
        fake_plan_ref,
        (
            "schema",
            "source",
            "phase",
            "project_id",
            "project_instance_id",
            "plan_id",
            "plan_digest",
            "input_digest",
            "grant_id",
            "request_key",
            "output_identity",
        ),
    )
    require(
        fake_plan_ref["schema"] == "af-fake-plan-ref-v1"
        and fake_plan_ref["source"] == "FAKE_TEST_ONLY"
        and fake_plan_ref["phase"] == "A",
        "DAT_SOURCE_MISMATCH",
        "Only the exact original test A execution reference is supported",
    )
    for value in (
        run_id,
        receipt_id,
        phase_attempt_id,
        fake_plan_ref["project_id"],
        fake_plan_ref["project_instance_id"],
        fake_plan_ref["plan_id"],
        fake_plan_ref["grant_id"],
        fake_plan_ref["request_key"],
    ):
        _label(value)
    for key in ("plan_digest", "input_digest", "output_identity"):
        _sha(fake_plan_ref[key])
    require(
        product.inspect(
            rod_plan_ref["plan_id"], rod_plan_ref["plan_digest"], at_time=at_time
        )
        == rod_plan_ref,
        "PLAN_STALE",
        "Frozen numerical candidate differs",
    )
    snap = _snapshot(client, fake_plan_ref, run_id)
    plan, receipt, run = snap["plan"], snap["receipt"], snap["run"]
    require(type(receipt) is dict, "ACCEPTANCE_UNKNOWN", "Original receipt unavailable")
    fields(
        plan,
        (
            "schema",
            "source",
            "project_id",
            "project_instance_id",
            "plan_id",
            "plan_digest",
            "backend_id",
            "backend_version",
            "input_digest",
            "input_size",
            "resources_digest",
            "output_identity",
            "configuration_digest",
            "execution_authorized",
        ),
    )
    integer(plan["input_size"], 1)
    for key in (
        "plan_digest",
        "input_digest",
        "resources_digest",
        "output_identity",
        "configuration_digest",
    ):
        _sha(plan[key])
    require(
        plan["schema"] == FAKE_PLAN_SCHEMA
        and plan["source"] == "PERSISTED_FAKE_PLAN"
        and plan["backend_id"] == "fake-v1"
        and type(plan["backend_version"]) is int
        and plan["backend_version"] == 1
        and plan["execution_authorized"] is False
        and all(
            plan[k] == fake_plan_ref[k]
            for k in (
                "project_id",
                "project_instance_id",
                "plan_id",
                "plan_digest",
                "input_digest",
                "output_identity",
            )
        )
        and plan["project_instance_id"] != rod_plan_ref["project_instance_id"],
        "DAT_SOURCE_MISMATCH",
        "Persisted Fake Plan must match independently pinned reference",
    )
    require(
        receipt.get("run_id") == run_id
        and receipt.get("request_id") == receipt_id
        and receipt.get("idempotency_key") == fake_plan_ref["request_key"]
        and receipt.get("request_status") == "ACCEPTED"
        and run.get("run_id") == run_id
        and run.get("phase_attempt_id") == phase_attempt_id
        and all(
            run.get(k) == fake_plan_ref[k]
            for k in (
                "project_id",
                "project_instance_id",
                "plan_id",
                "plan_digest",
                "grant_id",
            )
        )
        and run.get("backend_id") == "fake-v1"
        and run.get("phase") == "FAKE"
        and run.get("backend_outcome") == "COMPLETED"
        and type(run.get("attempt_no")) is int
        and run["attempt_no"] == 1
        and "retry_of" in run
        and run["retry_of"] is None
        and run.get("process_observation") == "NOT_APPLICABLE"
        and run.get("exit_verification") == "NOT_APPLICABLE"
        and run.get("simulation") is True
        and run.get("execution") == "FINISHED"
        and run.get("artifact_validation") == "VALID"
        and run.get("reconciliation") == "NONE"
        and run.get("solver_conclusion") == "NOT_RUN",
        "DAT_SOURCE_MISMATCH",
        "Exact terminal Fake receipt, Run and attempt required",
    )
    integer(run["revision"], 1)
    events, validations = snap["events"], snap["validations"]
    require(
        type(events) is list
        and len(events) == 4
        and type(validations) is list
        and 0 < len(validations) <= 16,
        "EVIDENCE_INCOMPLETE",
        "Bounded complete event and validation set required",
    )
    require(
        all(
            e.get("run_id") == run_id and type(e.get("project_sequence")) is int
            for e in events
        )
        and len({e["project_sequence"] for e in events}) == len(events)
        and any(
            e.get("type") == "REQUEST_ACCEPTED"
            and e["project_sequence"] == receipt.get("accepted_sequence")
            for e in events
        )
        and all(
            v.get("run_id") == run_id
            and v.get("phase_attempt_id") == phase_attempt_id
            and v.get("scope") == "simulation"
            and v.get("policy_id") == "fake-result-v1"
            and v.get("verdict") == "PASS"
            and type(v.get("evidence_refs")) is list
            and len(v["evidence_refs"]) > 0
            for v in validations
        ),
        "EVIDENCE_INCOMPLETE",
        "Raw event/validation identity must agree",
    )
    require(
        [event["type"] for event in events]
        == ["REQUEST_ACCEPTED", "START_INTENT", "FAKE_COMPLETED", "VALIDATION_RECORDED"]
        and [event["project_sequence"] for event in events]
        == sorted(event["project_sequence"] for event in events)
        and run["revision"] == 4
        and all(
            type(event.get("run_sequence")) is int
            and event["run_sequence"] == i
            and type(event.get("payload")) is dict
            and type(event["payload"].get("revision")) is int
            and event["payload"]["revision"] == i
            for i, event in enumerate(events, 1)
        )
        and type(events[-1].get("evidence_refs")) is list,
        "EVIDENCE_INCOMPLETE",
        "Four unique ordered lifecycle events must agree with terminal revision",
    )
    require(
        len(events[-1]["evidence_refs"]) <= 32,
        "LIMIT_EXCEEDED",
        "Bounded final evidence references required",
    )
    for reference in events[-1]["evidence_refs"]:
        _label(reference)
    for validation in validations:
        require(
            len(validation["evidence_refs"]) <= 8,
            "LIMIT_EXCEEDED",
            "Bounded observation references required",
        )
        for reference in validation["evidence_refs"]:
            _label(reference)
        _label(validation.get("validation_id"))
        require(
            set(validation["evidence_refs"] + [validation["validation_id"]])
            <= set(events[-1]["evidence_refs"]),
            "EVIDENCE_INCOMPLETE",
            "Final event must bind this validation and its artifact observations",
        )
    envelope = read_synthetic_dat(
        product,
        rod_plan_ref["plan_id"],
        rod_plan_ref["plan_digest"],
        expected_output_digest=output_digest,
        evidence_key=evidence_key,
        at_time=at_time,
    )
    link = {
        k: fake_plan_ref[k]
        for k in (
            "source",
            "project_id",
            "project_instance_id",
            "plan_id",
            "plan_digest",
            "input_digest",
        )
    }
    link.update(run_id=run_id, phase_attempt_id=phase_attempt_id, receipt_id=receipt_id)
    require(
        envelope["execution_link"] == link,
        "DAT_SOURCE_MISMATCH",
        "Synthetic artifact must bind this distinct Fake execution exactly",
    )
    require(
        _snapshot(client, fake_plan_ref, run_id) == snap,
        "EVIDENCE_CHANGED",
        "Public evidence changed during bounded acquisition",
    )
    result = {
        "schema": SCHEMA,
        "source": source,
        "rod_plan_ref": rod_plan_ref,
        "rod_plan_ref_digest": digest(rod_plan_ref),
        "contract_revisions": {
            "goal_revision": goal_revision,
            "model_revision": model_revision,
            "research_revision": rod_plan_ref["research_revision"],
        },
        "fake_plan": plan,
        "receipt": receipt,
        "run": run,
        "events": events,
        "validations": validations,
        "synthetic_envelope": envelope,
        "raw_solver_logs": "ABSENT_NOT_REAL_SOLVER",
        "real_solver_executed": False,
        "real_source_authentication": "NOT_VERIFIED",
        "V2": "NOT_VERIFIED",
        "V4": "NOT_ASSESSED",
        "ODB": "NOT_VERIFIED",
    }
    # Exact public records plus content digest, not raw bytes in JSON/Agent output.
    projection = {
        **result,
        "synthetic_envelope": {k: v for k, v in envelope.items() if k != "dat_bytes"},
    }
    result["bindings_digest"] = digest(projection)
    return result
