"""Versioned dynamic rod contract using the existing Standard owner and tables.

Preparation is not approval. No capability mint, process launcher or independent
owner lives here. Real activation additionally requires trusted owner configuration
and the existing exact ProductStandardControl capability/Grant path.
"""

import json
import os
from pathlib import Path
import re

from .models import ExecutionPlan, canonical_json, digest, fields, integer, now, require
from .paths import confined, no_reparse
from .rod_profile import RodCandidate, check_candidate
from .standard_contract import HOST_POLICY, RESOURCES, identity
from .store import document

BACKEND = "abaqus-standard-rod-cload-v1"
SCHEMA = "standard-managed-rod-single-v1"
ACTION = "launch_exact_rod_standard_once"
VALIDATION = "axial-rod-owner-dat-v1"
GRANT_KIND = "REAL_ROD_STANDARD"
EVIDENCE_SCHEMA = "af-rod-owner-evidence-v1"


def is_rod(plan):
    return plan.get("backend_id") == BACKEND


def _sha(value):
    require(
        type(value) is str and re.fullmatch(r"sha256:[a-f0-9]{64}", value),
        "INVALID_REQUEST",
        "Exact SHA-256 reference required",
    )


def prepare(
    service,
    engineering,
    candidate,
    *,
    research_project_id,
    contract_digest,
    research_revision,
    candidate_id,
    request_nonce,
    expires_at,
    phase="A",
    local_contract=None,
):
    """Persist one exact A Plan, idempotently, without any Grant or Run writes."""
    from .product_standard import POLICY

    require(
        (phase == "A" and local_contract is None) or local_contract is not None,
        "REAL_A_EVIDENCE_REQUIRED",
        "Real B needs accepted A and a later exact Plan",
    )
    value = check_candidate(candidate)
    from .rod_local_hil import check_contract
    check_contract(local_contract, phase, value)
    _sha(contract_digest)
    for label in (research_project_id, candidate_id, request_nonce):
        require(
            type(label) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", label),
            "INVALID_REQUEST",
            "Bounded research identity required",
        )
    integer(research_revision, 1)
    integer(expires_at, 1)
    require(expires_at > now(), "PLAN_EXPIRED", "Exact A validity required")
    require(
        service._standard_backend is not None,
        "BACKEND_DISABLED",
        "Trusted configuration required for exact Plan",
    )
    config = service._standard_backend.config
    config.verify()
    runtime = config.value()
    if local_contract is not None:
        from .rod_local_hil import check_runtime
        check_runtime(config, local_contract['runtime'])
    require(
        runtime.get("process_management"),
        "PLAN_STALE",
        "Managed Standard configuration required",
    )
    root = confined(service.context.test_root, engineering, exists=True)
    require(
        not root.is_relative_to(Path(service.context.root)),
        "OUTPUT_SCOPE_VIOLATION",
        "External engineering directory required",
    )
    contract = {
        "research_project_id": research_project_id,
        "contract_digest": contract_digest,
        "research_revision": research_revision,
        "candidate_id": candidate_id,
        "request_nonce": request_nonce,
        "phase": phase,
        "candidate": value,
    }
    if local_contract is not None:
        contract['local_contract'] = local_contract
    suffix = digest(
        {
            "instance": service.context.project_instance_id,
            "contract": contract,
            "engineering": str(root),
            "expires_at": expires_at,
        }
    ).split(":")[1][:32]
    plan = {
        "plan_id": "rod_real_" + suffix,
        "job_id": "rod_job_" + suffix,
        "job_revision": 1,
        "job_spec": {"job_id": "rod_job_" + suffix, "revision": 1},
        "project_instance_id": service.context.project_instance_id,
        "context_digest": service.context.context_digest,
        "backend_id": BACKEND,
        "backend_version": 1,
        "action": ACTION,
        "phases": ["STANDARD_ANALYSIS"],
        "resources": dict(RESOURCES),
        "runtime_binding": runtime,
        "input_manifest": [identity(root / "axial_bar.inp", 65536)],
        "engineering": str(root),
        "scratch": str(root / "scratch"),
        "job_name": "rod_" + suffix,
        "output_key": digest({"cwd": str(root).casefold(), "job": "rod_" + suffix}),
        "output_policy": {
            "overwrite": False,
            "reservation": "exclusive_intent_file_at_dispatch",
            "scope": "same_output_directory_protocol_participants",
        },
        "validation_policy": validation_for_candidate(value),
        "expires_at": expires_at,
        "canonicalization": "af-experiment-json-v1",
        "plan_schema": SCHEMA,
        "environment_policy": "isolated_home_temp_minimal_windows_v1",
        "extra_abaqus_calls": 0,
        "member_completeness_policy": "ROOT_AND_INHERITING_CREATEPROCESS_DESCENDANTS_ONLY",
        "host_policy": HOST_POLICY,
        "process_management": runtime["process_management"],
        "product_dispatch": dict(POLICY),
        "rod_contract": contract,
    }
    plan["plan_digest"] = digest(plan)
    require(
        plan["input_manifest"][0]["digest"] == value["input_digest"],
        "PLAN_STALE",
        "Materialized candidate differs",
    )
    check_plan(service, plan)
    with service.store.transaction("prepare_rod_standard") as conn:
        prior = conn.execute(
            "SELECT body FROM plans WHERE plan_id=?", (plan["plan_id"],)
        ).fetchone()
        if prior:
            require(
                prior[0] == canonical_json(plan),
                "IDEMPOTENCY_CONFLICT",
                "Exact Plan changed",
            )
            return ExecutionPlan.from_dict(plan)
        require(
            conn.execute("SELECT state FROM dispatch_gate WHERE id=1").fetchone()[0]
            == "PAUSED"
            and conn.execute("SELECT run_id FROM slot WHERE id=1").fetchone()[0]
            is None,
            "DISPATCH_POLICY_MISMATCH",
            "Idle PAUSED preparation required",
        )
        require(
            all(
                conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
                for table in ("plans", "runs", "grants", "receipts", "consumption")
            ),
            "IDEMPOTENCY_CONFLICT",
            "One prospective real Plan per isolated execution Project",
        )
        conn.execute(
            "INSERT INTO jobs VALUES(?,?,?)",
            (plan["job_id"], 1, canonical_json(plan["job_spec"])),
        )
        conn.execute(
            "INSERT INTO plans VALUES(?,?,?,?)",
            (plan["plan_id"], plan["job_id"], 1, canonical_json(plan)),
        )
    service.store._checkpoint("prepare_rod_standard:after_commit")
    return ExecutionPlan.from_dict(plan)


def check_plan(service, plan, *, started=False):
    from .product_standard import POLICY

    fields(
        plan,
        (
            "plan_id",
            "job_id",
            "job_revision",
            "job_spec",
            "project_instance_id",
            "context_digest",
            "backend_id",
            "backend_version",
            "action",
            "phases",
            "resources",
            "runtime_binding",
            "input_manifest",
            "engineering",
            "scratch",
            "job_name",
            "output_key",
            "output_policy",
            "validation_policy",
            "expires_at",
            "canonicalization",
            "plan_schema",
            "environment_policy",
            "extra_abaqus_calls",
            "member_completeness_policy",
            "host_policy",
            "process_management",
            "product_dispatch",
            "rod_contract",
            "plan_digest",
        ),
    )
    integer(plan["expires_at"], 1)
    require(
        type(plan["job_revision"]) is int
        and plan["job_revision"] == 1
        and plan["job_spec"] == {"job_id": plan["job_id"], "revision": 1}
        and canonical_json(plan["resources"]) == canonical_json(RESOURCES)
        and canonical_json(plan["product_dispatch"]) == canonical_json(POLICY)
        and plan["output_policy"]
        == {
            "overwrite": False,
            "reservation": "exclusive_intent_file_at_dispatch",
            "scope": "same_output_directory_protocol_participants",
        }
        and plan["environment_policy"] == "isolated_home_temp_minimal_windows_v1"
        and plan["member_completeness_policy"]
        == "ROOT_AND_INHERITING_CREATEPROCESS_DESCENDANTS_ONLY"
        and plan["canonicalization"] == "af-experiment-json-v1",
        "PLAN_STALE",
        "Immutable rod execution contract differs",
    )

    original = dict(plan)
    require(
        original.pop("plan_digest", None) == digest(original),
        "PLAN_STALE",
        "Exact rod Plan digest differs",
    )
    require(
        is_rod(plan)
        and plan["plan_schema"] == SCHEMA
        and plan["action"] == ACTION
        and plan["backend_version"] == 1
        and plan["resources"] == RESOURCES
        and plan["phases"] == ["STANDARD_ANALYSIS"]
        and plan["validation_policy"] == validation_for(plan)
        and plan["product_dispatch"] == POLICY
        and "standard_sequence" not in plan
        and plan["extra_abaqus_calls"] == 0
        and plan["host_policy"] == HOST_POLICY,
        "PLAN_STALE",
        "Versioned rod execution policy differs",
    )
    require(
        plan["project_instance_id"] == service.context.project_instance_id
        and plan["context_digest"] == service.context.context_digest,
        "PROJECT_IDENTITY_MISMATCH",
        "Original Project identity required",
    )
    require(plan["expires_at"] > now(), "PLAN_EXPIRED", "Exact Plan expired")
    backend = service._standard_backend
    require(backend is not None, "BACKEND_DISABLED", "Standard backend not configured")
    backend.config.verify()
    require(
        plan["runtime_binding"] == backend.config.value()
        and plan["process_management"]
        == backend.config.value().get("process_management")
        and plan["process_management"],
        "PLAN_STALE",
        "Managed runtime differs",
    )
    contract = plan["rod_contract"]
    fields(
        contract,
        (
            "research_project_id",
            "contract_digest",
            "research_revision",
            "candidate_id",
            "request_nonce",
            "phase",
            "candidate",
        ) + (("local_contract",) if "local_contract" in contract else ()),
    )
    require(
        (contract["phase"] == "A" and "local_contract" not in contract) or "local_contract" in contract,
        "REAL_A_EVIDENCE_REQUIRED",
        "B admission is not inferred from a declaration",
    )
    from .rod_local_hil import check_contract
    check_contract(contract.get('local_contract'), contract['phase'], contract['candidate'])
    if 'local_contract' in contract:
        from .rod_local_hil import check_runtime
        check_runtime(backend.config, contract['local_contract']['runtime'])
    _sha(contract["contract_digest"])
    integer(contract["research_revision"], 1)
    root = confined(service.context.test_root, plan["engineering"], exists=True)
    require(
        not root.is_relative_to(Path(service.context.root)),
        "OUTPUT_SCOPE_VIOLATION",
        "External engineering directory required",
    )
    source = confined(service.context.test_root, root / "axial_bar.inp", exists=True)
    pinned_input = identity(source, 65536)
    with source.open("rb") as stream:
        input_bytes = stream.read(65537)
    require(
        len(input_bytes) <= 65536 and identity(source, 65536) == pinned_input,
        "PLAN_STALE",
        "Bounded input changed during contract check",
    )
    value = check_candidate(
        RodCandidate(input_bytes, canonical_json(contract["candidate"]))
    )
    require(
        plan["input_manifest"] == [pinned_input]
        and value["input_digest"] == plan["input_manifest"][0]["digest"]
        and plan["scratch"] == str(root / "scratch")
        and re.fullmatch(r"rod_[a-f0-9]{32}", plan["job_name"])
        and plan["output_key"]
        == digest({"cwd": str(root).casefold(), "job": plan["job_name"]}),
        "PLAN_STALE",
        "Input, scratch or output differs",
    )
    no_reparse(root / "scratch")
    require(
        (root / "scratch").is_dir()
        and not (root / "abaqus_v6.env").exists()
        and not any(c in str(root) for c in '"%!?&|<>^\r\n'),
        "OUTPUT_SCOPE_VIOLATION",
        "Exact bounded command workspace required",
    )
    if not started:
        require(
            not list(root.glob(plan["job_name"] + ".*"))
            and not list(root.glob(".*.intent.json"))
            and not any((root / "scratch").iterdir()),
            "OUTPUT_CONFLICT",
            "Old output/attempt/scratch is never reused",
        )



def preflight(service, context, *, plan_id, expected_plan_digest, expected_contract):
    """Read-only prerequisite check, never an authorization or host qualification.

    The exact external research reference is supplied by the frozen caller contract,
    not copied from the stored Plan as proof that the caller still intends it.
    """
    require(context == service.context, "PROJECT_IDENTITY_MISMATCH", "Exact context required")
    fields(expected_contract, (
        "research_project_id", "contract_digest", "research_revision", "candidate_id",
        "request_nonce", "input_digest",
    ))
    with service.store.read() as conn:
        plan = document(conn, "plans", "plan_id", plan_id)
        require(plan["plan_digest"] == expected_plan_digest,
                "PLAN_STALE", "Exact persisted Plan reference required")
        check_plan(service, plan)
        contract = plan["rod_contract"]
        observed = {key: contract[key] for key in expected_contract if key != "input_digest"}
        observed["input_digest"] = contract["candidate"]["input_digest"]
        require(canonical_json(observed) == canonical_json(expected_contract),
                "PLAN_STALE", "Frozen caller contract or revision differs")
        gate = conn.execute("SELECT state,version FROM dispatch_gate WHERE id=1").fetchone()
        require(gate[0] == "PAUSED"
                and conn.execute("SELECT run_id FROM slot WHERE id=1").fetchone()[0] is None,
                "DISPATCH_POLICY_MISMATCH", "Readiness requires idle PAUSED state")
        require(all(conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
                    for table in ("runs", "grants", "receipts", "consumption")),
                "ROD_EXECUTION_UNQUALIFIED", "This pre-A check cannot qualify existing execution")
    return {
        **({"local_contract": contract["local_contract"]} if "local_contract" in contract else {}),
        "schema": "af-rod-preflight-v1", "status": "PRECONDITIONS_CHECKED",
        "project_id": context.project_id, "project_instance_id": context.project_instance_id,
        "plan_id": plan_id, "plan_digest": expected_plan_digest,
        "research_contract": observed, "resources": dict(plan["resources"]),
        "input_path": plan["input_manifest"][0]["path"],
        "load_n": contract["candidate"]["load_n"],
        "runtime_binding_digest": digest(plan["runtime_binding"]),
        "engineering": plan["engineering"], "scratch": plan["scratch"],
        "output_key": plan["output_key"], "expires_at": plan["expires_at"],
        "gate_version": gate[1], "declared_outputs": [
            {"logical_ref": "output:" + ext,
             "path": str(Path(plan["engineering"]) / (plan["job_name"] + "." + ext)),
             "binding": "ORIGINAL_RUN_ATTEMPT_INTENT_AND_COLLECTOR_DIGEST"}
            for ext in ("dat", "sta", "msg")
        ],
        "execution_authorized": False, "host_qualification": "NOT_VERIFIED",
        "operator_deployment": "NOT_VERIFIED", "real_a_output": "NOT_PRODUCED",
        "source_authentication": "NOT_VERIFIED",
    }


def _collected_artifact(context, root, plan, intent, validation, extension):
    """Recheck required original outputs using a bounded stable open handle."""
    from .models import bytes_digest

    path = confined(context.test_root, root / (plan["job_name"] + "." + extension),
                    exists=True)
    records = [a for a in validation["details"].get("artifacts", [])
               if a.get("logical_ref") == "output:" + extension]
    require(len(records) == 1, "DAT_SOURCE_MISMATCH", "Unique original output required")
    record = records[0]
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(before.st_size <= 1048576, "LIMIT_EXCEEDED", "Bounded output required")
        raw = stream.read(1048577)
        after = os.fstat(stream.fileno())
    no_reparse(path)
    current = path.stat()
    attrs = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    # Windows Python may expose metadata-change ctime through fstat but legacy
    # creation ctime through stat. Compare explicit birthtime across both APIs;
    # retain same-handle change-time stability and all file/content identities.
    def birth(info):
        return getattr(info, "st_birthtime_ns", info.st_ctime_ns)

    require(len(raw) == before.st_size <= 1048576
            and before.st_ctime_ns == after.st_ctime_ns
            and birth(before) == birth(after) == birth(current)
            and all(getattr(before, a) == getattr(after, a) == getattr(current, a)
                    for a in attrs), "EVIDENCE_CHANGED", "Output changed during acquisition")
    require(birth(before) >= intent["intent_at_ns"]
            and before.st_mtime_ns >= intent["intent_at_ns"]
            and all(record.get(k) == v for k, v in {
                "digest": bytes_digest(raw), "size": len(raw), "device": before.st_dev,
                "inode": before.st_ino, "mtime_ns": before.st_mtime_ns,
            }.items()), "DAT_SOURCE_MISMATCH", "Output differs from original collector")
    return raw, record


def require_activation(service, plan):
    """Trusted config is never an RPC argument; absent deployment stays disabled."""
    require(
        service._standard_backend is not None
        and service._standard_backend.config.value().get("rod_profile") == plan['rod_contract']['candidate']['profile']
        and service.product_control is not None,
        "ROD_EXECUTION_DISABLED",
        "Protected deployment and exact one-shot Operator are not configured",
    )
    service.product_control.check_plan(plan)


def collect_dynamic(data, plan):
    """Independent printed-value checks; caller supplies original collected bytes."""
    from .rod_dat import parse_bound_dat

    candidate = RodCandidate(
        Path(plan["input_manifest"][0]["path"]).read_bytes(),
        canonical_json(plan["rod_contract"]["candidate"]),
    )
    # Reuse numerical parser only. This adapter does not relabel its deliberately
    # unauthenticated parser binding as actual provenance; the owner records it.
    from .models import bytes_digest

    binding = {
        "project_id": "numerical_only",
        "project_instance_id": "numerical_only",
        "plan_digest": plan["plan_digest"],
        "input_digest": candidate.to_dict()["input_digest"],
        "run_id": "numerical_only",
        "attempt_id": "numerical_only",
        "output_digest": bytes_digest(data),
        "solver_exit_code": 0,
        "managed_scope": "EMPTY_CONFIRMED",
        "source": "OFFLINE_AF_SUBSTITUTE",
    }
    if candidate.to_dict()['profile'] == 'axial_rod_cload_output_v2':
        from .rod_output_dat_v2 import parse
        parsed = parse(data, candidate.to_dict()['load_n'])
        return {**parsed, 'validation_policy': validation_for(plan)}
    parsed = parse_bound_dat(data, candidate, binding, binding)
    return {
        "solver": parsed["solver"],
        "numerical": "PRIMARY_THREE_PASS"
        if parsed["numerical"] == "PASS"
        else "NUMERICAL_FAIL",
        "comparisons": parsed["comparisons"],
        "step": parsed["step"],
        "increment": parsed["increment"],
        "metric": parsed["metric"],
        "validation_policy": VALIDATION,
    }


def acquire(service, context, *, plan_id, expected_plan_digest, request_key,
            include_completion_artifacts=False):
    """Obtain original committed records and stable artifact through a read-only API.

    The host/transport trust qualification is deliberately not inferred from DB
    contents. No historical fixed-Standard or caller-provided bytes are accepted.
    """
    from .models import bytes_digest

    require(
        context == service.context,
        "PROJECT_IDENTITY_MISMATCH",
        "Exact read context required",
    )
    namespace = canonical_json(
        [context.project_instance_id, service.client_namespace, "submit"]
    )
    with service.store.read() as conn:
        plan = document(conn, "plans", "plan_id", plan_id)
        original = dict(plan)
        require(
            original.pop("plan_digest") == expected_plan_digest == digest(original)
            and is_rod(plan)
            and plan["plan_schema"] == SCHEMA
            and plan["project_instance_id"] == context.project_instance_id,
            "DAT_SOURCE_MISMATCH",
            "Exact original real rod Plan required",
        )
        row = conn.execute(
            "SELECT body FROM receipts WHERE namespace=? AND key=?",
            (namespace, request_key),
        ).fetchone()
        require(row is not None, "NOT_FOUND", "Original request receipt required")
        receipt = json.loads(row[0])
        require(
            receipt.get("request_status") == "ACCEPTED"
            and receipt.get("idempotency_key") == request_key
            and receipt.get("namespace") == namespace
            and receipt.get("job_id") == plan["job_id"],
            "DAT_SOURCE_MISMATCH",
            "Original accepted receipt identity differs",
        )
        require(conn.execute("SELECT COUNT(*) FROM receipts WHERE run_id=?",
                             (receipt["run_id"],)).fetchone()[0] == 1,
                "DAT_SOURCE_MISMATCH", "Ambiguous original Run receipt")
        run = document(conn, "runs", "run_id", receipt["run_id"])
        require(
            run["plan_id"] == plan_id
            and run["plan_digest"] == expected_plan_digest
            and run["project_id"] == context.project_id
            and run["project_instance_id"] == context.project_instance_id
            and run["backend_id"] == BACKEND
            and run["phase"] == "STANDARD_ANALYSIS"
            and run["simulation"] is False
            and run["execution"] == "FINISHED"
            and run["backend_outcome"] == "COMPLETED"
            and run["reconciliation"] == "NONE"
            and run.get("managed_completion") == "COMMITTED_EMPTY_SCOPE"
            and run.get("numerical_validation") == "PRIMARY_THREE_PASS"
            and run.get("solver_conclusion") == "COMPLETED_TEXT_EVIDENCE",
            "DAT_EXECUTION_UNKNOWN",
            "Original successful managed completion required",
        )
        events = [
            {**json.loads(r[1]), "project_sequence": r[0]}
            for r in conn.execute(
                "SELECT sequence,body FROM events WHERE run_id=? ORDER BY sequence LIMIT 513",
                (run["run_id"],),
            ).fetchall()
        ]
        require(
            0 < len(events) <= 512,
            "LIMIT_EXCEEDED",
            "Bounded original event history required",
        )
        require(all(event.get("run_id") == run["run_id"] for event in events)
                and [event.get("run_sequence") for event in events]
                == list(range(1, len(events) + 1)),
                "DAT_SOURCE_MISMATCH", "Contiguous original Run event identities required")
        from .managed_process import check_completion
        check_completion(run.get("managed_scope"), run)
        kinds = [event["type"] for event in events]
        required = [
            "REQUEST_ACCEPTED",
            "START_INTENT",
            "STANDARD_LAUNCH_INTENT",
            "STANDARD_CREATED",
            "STANDARD_MANAGED_COMPLETED",
            "STANDARD_RESULT_RECORDED",
        ]
        require(
            all(kinds.count(kind) == 1 for kind in required)
            and [kinds.index(kind) for kind in required]
            == sorted(kinds.index(kind) for kind in required)
            and events[kinds.index("REQUEST_ACCEPTED")]["project_sequence"]
            == receipt["accepted_sequence"],
            "DAT_SOURCE_MISMATCH",
            "Original acceptance-to-completion causal history required",
        )
        validations = [
            json.loads(r[0])
            for r in conn.execute(
                "SELECT body FROM validations WHERE run_id=? LIMIT 2", (run["run_id"],)
            ).fetchall()
        ]
        require(
            len(validations) == 1
            and validations[0]["run_id"] == run["run_id"]
            and validations[0]["policy_id"] == validation_for(plan)
            and validations[0]["phase_attempt_id"] == run["phase_attempt_id"]
            and validations[0]["verdict"] == "PASS",
            "DAT_SOURCE_MISMATCH",
            "Original dynamic validation required",
        )
        validation = validations[0]
        details = validation["details"]
        require(validation.get("scope") == "dynamic_rod_dat_only"
                and details.get("solver") == "COMPLETED_TEXT_EVIDENCE"
                and details.get("numerical") == "PRIMARY_THREE_PASS"
                and details.get("validation_policy") == validation_for(plan)
                and details.get("managed_observation_complete") is True
                and details.get("observed_exit_success") is True
                and details.get("managed_scope") == run.get("managed_scope"),
                "DAT_SOURCE_MISMATCH", "Original validation contradicts completed Run")
    root = confined(context.test_root, plan["engineering"], exists=True)
    intent_path = confined(
        context.test_root, root / ("." + plan["job_name"] + ".intent.json"), exists=True
    )
    require(
        intent_path.stat().st_size <= 65536,
        "LIMIT_EXCEEDED",
        "Bounded original intent required",
    )
    intent = json.loads(intent_path.read_bytes())
    require(
        intent == run.get("launch_intent")
        and all(
            intent[k] == run[k]
            for k in (
                "run_id",
                "phase_attempt_id",
                "project_instance_id",
                "plan_digest",
            )
        )
        and intent["output_key"] == plan["output_key"],
        "DAT_SOURCE_MISMATCH",
        "Original launch intent differs",
    )
    require(
        identity(root / "axial_bar.inp", 65536) == plan["input_manifest"][0],
        "DAT_SOURCE_MISMATCH",
        "Original input changed",
    )
    raw, record = _collected_artifact(context, root, plan, intent, validation, "dat")
    sta, sta_record = _collected_artifact(context, root, plan, intent, validation, "sta")
    msg, msg_record = _collected_artifact(context, root, plan, intent, validation, "msg")
    require(b"THE ANALYSIS HAS COMPLETED SUCCESSFULLY" in sta
            and b"THE ANALYSIS HAS BEEN COMPLETED" in msg
            and b"***ERROR" not in b"\n".join((raw, sta, msg))
            and b"HAS NOT BEEN COMPLETED" not in sta,
            "DAT_EXECUTION_UNKNOWN", "Original completion text is insufficient")
    pin = {"digest": bytes_digest(raw), "size": len(raw)}
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "source": "AF_OWNER_RECORD_CHAIN",
        "source_authentication": "NOT_VERIFIED",
        "collector_version": "rod-owner-collector-v1",
        "collected_at": record["read_at"],
        "acquired_at": now(),
        "plan": {
            "project_id": context.project_id,
            **{
                k: plan[k]
                for k in (
                    "plan_id",
                    "plan_digest",
                    "backend_id",
                    "backend_version",
                    "project_instance_id",
                    "resources",
                    "output_key",
                    "rod_contract",
                    "validation_policy",
                )
            },
        },
        "receipt": {
            k: receipt[k]
            for k in (
                "request_id",
                "request_digest",
                "idempotency_key",
                "run_id",
                "accepted_sequence",
            )
        },
        "run": {
            k: run[k]
            for k in (
                "run_id",
                "project_id",
                "project_instance_id",
                "plan_id",
                "plan_digest",
                "grant_id",
                "phase_attempt_id",
                "phase",
                "revision",
                "simulation",
                "execution",
                "backend_outcome",
                "reconciliation",
                "managed_completion",
            )
        },
        "events": [
            {
                k: event[k]
                for k in ("type", "project_sequence", "run_sequence", "run_id")
            }
            for event in events
        ],
        "artifact": {
            "logical_ref": "output:dat",
            "dat_bytes": raw,
            "sha256": pin["digest"],
            "size": pin["size"],
            "input_digest": plan["input_manifest"][0]["digest"],
            "step": 1,
            "increment": 1,
            "units": {"length": "mm", "force": "N", "stress": "MPa"},
        },
        "validation_ref": validation["validation_id"],
        "V2": "NOT_VERIFIED",
        "V3": "INCONCLUSIVE",
        "V4": "NOT_ASSESSED",
        "ODB": "NOT_VERIFIED",
    }
    if not include_completion_artifacts:
        return evidence
    return {
        "schema": "af-rod-owner-artifact-set-v1",
        "source": "AF_OWNER_RECORD_CHAIN",
        "source_authentication": "NOT_VERIFIED",
        "owner_evidence": evidence,
        "launch_intent": intent,
        "artifacts": [
            {
                "logical_ref": "output:" + extension,
                "bytes": content,
                "sha256": bytes_digest(content),
                "size": len(content),
                "run_id": run["run_id"],
                "phase_attempt_id": run["phase_attempt_id"],
                "project_instance_id": context.project_instance_id,
                "plan_digest": plan["plan_digest"],
                "input_digest": plan["input_manifest"][0]["digest"],
                "collected_record": collected,
            }
            for extension, content, collected in (
                ("dat", raw, record), ("sta", sta, sta_record), ("msg", msg, msg_record)
            )
        ],
    }


def validation_for_candidate(candidate):
    return "axial-rod-owner-dat-v2" if candidate['profile'] == "axial_rod_cload_output_v2" else VALIDATION


def validation_for(plan):
    return validation_for_candidate(plan['rod_contract']['candidate'])
