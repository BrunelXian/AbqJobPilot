"""Pure bounded audit projection and deterministic explanation, never validation."""

import json

from .models import ExecutionError, canonical_json, digest, require

REPORT_VERSION = "af-run-diagnostic-v1"
RULES_VERSION = "fake-diagnostic-rules-v1"
MAX_RECORD_BYTES = 16384
MAX_RAW_BYTES = 262144
MAX_REPORT_BYTES = 131072  # Leaves room in the unchanged 256 KiB IPC response.
MAX_FIELD_CHARS = 1024


def valid_id(value, prefix):
    return (type(value) is str and value.startswith(prefix + "_") and len(value) == len(prefix) + 33
            and all(c in "0123456789abcdef" for c in value[len(prefix) + 1:]))


def ref(*prefixes):
    return lambda v: any(valid_id(v, p) for p in prefixes)


def number(v):
    return type(v) is int and 0 <= v <= 2**63 - 1


def boolean(v):
    return type(v) is bool


def hash_ref(v):
    return type(v) is str and len(v) == 71 and v.startswith("sha256:") and all(c in "0123456789abcdef" for c in v[7:])


def choice(*values):
    return lambda v: type(v) is str and v in values


def project(value, schema):
    """Whitelist first, with finite vocabularies. Unknown/missing fields are null."""
    if value is None:
        return None
    if type(schema) is dict:
        if type(value) is not dict:
            return None
        return {k: project(value.get(k), child) for k, child in schema.items()}
    if type(schema) is list:
        if type(value) is not list:
            return None
        return [project(v, schema[0]) for v in value]
    return value if schema(value) else None


def bounded_tree(value, depth=0, budget=None):
    budget = [8192] if budget is None else budget
    budget[0] -= 1
    require(depth <= 16 and budget[0] >= 0, "LIMIT_EXCEEDED", "Diagnostic JSON structure exceeds limit")
    if type(value) is str:
        require(len(value) <= MAX_FIELD_CHARS, "LIMIT_EXCEEDED", "Diagnostic field length exceeds limit")
    elif type(value) is dict:
        for key, child in value.items():
            bounded_tree(key, depth + 1, budget)
            bounded_tree(child, depth + 1, budget)
    elif type(value) is list:
        for child in value:
            bounded_tree(child, depth + 1, budget)
    else:
        require(value is None or type(value) in (int, bool), "STORE_UNAVAILABLE", "Unsupported persisted value")


READ_CODES = {"LIMIT_EXCEEDED", "NOT_FOUND", "STORE_UNAVAILABLE", "STORE_REQUIRES_MAINTENANCE",
              "UNSUPPORTED_FORMAT", "PROJECT_IDENTITY_MISMATCH", "OUTPUT_SCOPE_VIOLATION", "PATH_UNAVAILABLE"}


def read_error(error):
    code = error.code if isinstance(error, ExecutionError) and error.code in READ_CODES else "STORE_UNAVAILABLE"
    return ExecutionError(code, "Diagnostic read refused; no records were changed", stage="QUERY")


ERROR_CODES = choice("PLAN_STALE", "PLAN_EXPIRED", "PROJECT_IDENTITY_MISMATCH", "PATH_UNAVAILABLE",
                     "GRANT_REQUIRED", "GRANT_EXPIRED", "GRANT_SCOPE_MISMATCH", "GRANT_CONSUMED",
                     "TEST_GRANT_ONLY", "RESOURCE_LIMIT", "OUTPUT_SCOPE_VIOLATION", "EVIDENCE_WRITE_FAILED",
                     "TERMINAL_COMMIT_FAILED", "STORE_UNAVAILABLE", "ACCEPTANCE_UNKNOWN", "RECONCILIATION_REQUIRED",
                     "STORE_REQUIRES_MAINTENANCE", "OWNER_UNCONFIRMED", "SLOT_BUSY", "INVALID_REQUEST", "NOT_FOUND")
RUN = {"run_id": ref("r"), "plan_id": ref("plan"), "plan_digest": hash_ref, "job_revision": number,
       "revision": number, "attempt_no": number, "retry_of": ref("r"), "phase_attempt_id": ref("phase"),
       "queue_id": lambda v: v is None, "queue_state": choice("PENDING", "DISPATCHED", "BLOCKED"),
       "execution": choice("PLANNED", "START_INTENT", "VALIDATING", "BLOCKED", "FINISHED"), "phase": choice("FAKE"),
       "backend_id": choice("fake-v1"), "backend_outcome": choice("NOT_RUN", "COMPLETED", "UNKNOWN"),
       "simulation": boolean, "process_observation": choice("NOT_APPLICABLE"), "exit_verification": choice("NOT_APPLICABLE"),
       "solver_conclusion": choice("NOT_RUN"), "artifact_validation": choice("NOT_RUN", "VALID", "INVALID", "UNKNOWN"),
       "reconciliation": choice("NONE", "RECONCILIATION_REQUIRED"), "owner_id": ref("owner"), "owner_epoch": number,
       "created_at": number, "reconciled_at": number, "validation_scope": choice("simulation"),
       "backend_outcome_basis": choice("RECONCILED_FIXED_ARTIFACT"),
       "error": {"code": ERROR_CODES, "stage": choice("PRE_DISPATCH", "DISPATCH", "POST_CLAIM", "QUERY", "VALIDATE"),
                 "requires_reconciliation": boolean}}
RECEIPT = {"request_id": ref("req"), "request_status": choice("ACCEPTED"), "accepted_at": number,
           "run_id": ref("r"), "accepted_sequence": number, "initial_queue_state": choice("PENDING")}
EVENT_TYPES = choice("REQUEST_ACCEPTED", "START_INTENT", "DISPATCH_BLOCKED", "FAKE_COMPLETED",
                     "VALIDATION_RECORDED", "RECONCILIATION_REQUIRED", "RECONCILIATION_APPLIED")
RECORD_REF = ref("ev", "obs", "val", "rec", "disposition", "op", "control", "r", "req", "plan")
EVENT = {"event_id": ref("ev"), "run_id": ref("r"), "run_sequence": number, "project_sequence": number,
         "type": EVENT_TYPES, "observed_at": number, "recorded_at": number, "evidence_refs": [RECORD_REF],
         "payload": {k: RUN[k] for k in ("revision", "execution", "queue_state", "backend_outcome", "artifact_validation",
                                        "reconciliation", "validation_scope", "solver_conclusion", "reconciled_at")}}
SNAPSHOT = {"operation_id": ref("op"), "digest": hash_ref, "size": number}
OBSERVATION = {"observation_id": ref("obs"), "run_id": ref("r"), "phase_attempt_id": ref("phase"),
               "kind": choice("FAKE_JSON"), "exists": boolean, "file_identity": {"device": number, "inode": number},
               "size": number, "mtime": number, "digest": hash_ref, "provenance": choice("fake-v1", "reconciliation_capture"),
               "binding_status": choice("UNKNOWN", "MATCHED", "MISMATCH"), "observed_at": number, "snapshot": SNAPSHOT}
VALIDATION = {"validation_id": ref("val"), "run_id": ref("r"), "phase_attempt_id": ref("phase"),
              "scope": choice("simulation"), "policy_id": choice("fake-result-v1"), "policy_version": number,
              "validator_id": choice("fake-json-validator"), "validator_version": number,
              "verdict": choice("PASS", "FAIL", "UNKNOWN"), "recorded_at": number, "evidence_refs": [RECORD_REF],
              "source": choice("explicit_reconciliation"), "snapshot": SNAPSHOT}
RECONCILIATION = {"reconciliation_id": ref("rec"), "operation_id": ref("op"), "run_id": ref("r"),
                  "owner_id": ref("owner"), "recorded_at": number, "source": choice("TEST_ONLY_EXPLICIT_RECONCILIATION"),
                  "action": choice("adopt_verified_fake_artifact"), "conclusion": choice("FIXED_FAKE_COMPLETION_INFERRED_NOW"),
                  "observation_id": ref("obs"), "validation_id": ref("val"), "snapshot": SNAPSHOT}
GATE = {"owner_id": ref("owner"), "version": number, "state": choice("OPEN", "PAUSED")}

# Stable explanation codes are not persisted execution states or permissions.
RULES = {
    'MANAGED_SCOPE_ENDED':('SIMULATION','A retained Job query recorded no active scoped processes after root creation; completion and slot release committed together. This is not Solver or artifact success.','review_recorded_evidence'),
    'MANAGED_SCOPE_UNCONFIRMED':('UNCERTAINTY','Managed range completion has not committed; enumerated key-role exits do not prove the descendant range ended.','review_recorded_evidence'),
    "STANDARD_RECORDED_TEXT": ("EVIDENCE", "Recorded fixed Standard text and DAT checks have separate verdicts. Membership and overall exit remain unknown; no process or artifact was probed by this query.", "review_recorded_evidence"),
    "RECORDED_EXITS_RECONCILED": ("RECONCILIATION", "Explicit reconciliation used historical OS exit records only; no process probe or artifact validation occurred, and dispatch permission is separate.", "review_recorded_evidence"),
    "TEST_PROCESS_COMPLETED": ("SIMULATION", "Required fixed test processes have recorded zero exits; artifact validation is separate and Solver was not run.", "review_recorded_evidence"),
    "TEST_PROCESS_FAILED": ("EVIDENCE", "Required test process exit records include a nonzero code; a valid artifact cannot override this.", "review_recorded_evidence"),
    "HISTORICAL_PROCESS_IDENTITY": ("INFORMATION", "Identities were verified at the recorded observation time; this is not a current liveness probe.", "review_recorded_evidence"),
    "PROCESS_EXIT_NOT_ESTABLISHED": ("UNCERTAINTY", "Complete required process exit evidence is not recorded; missing processes or files cannot supply it.", "review_recorded_evidence"),
    "REQUEST_ACCEPTED": ("ACCEPTANCE", "A durable receipt records acceptance; this is not completion.", "review_run"),
    "WAITING_DISPATCH": ("DISPATCH", "The recorded Run is pending; dispatch prerequisites still apply.", "review_dispatch_prerequisites"),
    "EXECUTION_STARTED": ("DISPATCH", "A START_INTENT records a claim, not a verified completion.", "review_recorded_evidence"),
    "EXECUTION_UNCERTAIN": ("UNCERTAINTY", "Existing Run semantics require reconciliation; do not execute again.", "request_explicit_preview"),
    "EVIDENCE_INSUFFICIENT": ("EVIDENCE", "Persisted records do not establish a validated result; artifact bytes were not inspected.", "request_explicit_preview"),
    "HISTORICAL_VALIDATION_FAILED": ("EVIDENCE", "A historical validator recorded failure; no validation was run now.", "review_recorded_evidence"),
    "HISTORICAL_VALIDATION_PASSED": ("EVIDENCE", "A historical validator recorded PASS in simulation scope only.", "review_recorded_evidence"),
    "EXPLICITLY_RECONCILED": ("RECONCILIATION", "An explicit reconciliation is recorded; it does not authorize dispatch.", "review_dispatch_prerequisites"),
    "ADMINISTRATIVE_DISPOSITION": ("RECONCILIATION", "An operator disposition is recorded, not a verified complete process exit. Retained paths and separate dispatch permission still apply.", "review_dispatch_prerequisites"),
    "DISPATCH_PAUSED": ("DISPATCH", "The database gate was PAUSED in this snapshot.", "request_separate_resume_review"),
    "FAKE_COMPLETED": ("SIMULATION", "The stored Fake outcome is COMPLETED; Solver was not run.", "review_recorded_evidence"),
    "NO_RECORDED_ERROR": ("INFORMATION", "No Run error was recorded; absence of an error does not prove success.", "review_run"),
    "DISPATCH_BLOCKED": ("DISPATCH", "The stored dispatch is BLOCKED; no automatic retry is suggested.", "review_dispatch_prerequisites"),
}
UNKNOWN = ("CURRENT_ARTIFACT_CONTENT_NOT_READ", "OWNER_HEALTH_NOT_OBSERVED", "LIVE_PROCESS_NOT_OBSERVED",
           "EXECUTION_OR_MANAGEMENT_PERMISSION_NOT_EVALUATED", "FAILURE_CLASSIFICATION_NOT_RECORDED",
           "NULL_FIELDS_UNRECORDED_OR_OUTSIDE_PUBLIC_VOCABULARY", "ORIGINAL_RECEIPT_NOT_RECORDED",
           "PLAN_RECORD_NOT_RECORDED", "RUN_EVENT_SEQUENCE_GAP", "VALIDATION_NOT_RECORDED", "GATE_NOT_RECORDED")
PRECONDITIONS = ("Authenticated explicit Project query", "Separate authorization for any mutation",
                 "Fresh owner, evidence, Plan and Grant checks at action time")
FACTS = {"run": RUN, "receipt": RECEIPT,
         "plan": {"plan_id": ref("plan"), "plan_digest": hash_ref, "backend_id": choice("fake-v1"), "backend_version": number},
         "events": [EVENT], "observations": [OBSERVATION], "validations": [VALIDATION],
         "reconciliations": [RECONCILIATION], "dispatch_gate": GATE}
ITEM = {"reason_code": choice(*RULES), "classification": choice(*(r[0] for r in RULES.values())),
        "recorded_facts": {"request_status": choice("ACCEPTED"), "queue_state": RUN["queue_state"],
                           "execution": RUN["execution"], "backend_outcome": RUN["backend_outcome"],
                           "artifact_validation": RUN["artifact_validation"], "gate_state": GATE["state"]},
        "inference": choice(*(r[1] for r in RULES.values())), "unknowns": [choice(*UNKNOWN)],
        "source_refs": [RECORD_REF], "next_step": {"candidate": choice(*(r[2] for r in RULES.values())),
                                                   "preconditions": [choice(*PRECONDITIONS)]}}
OMITTED = ("credentials_and_grants", "namespaces_and_idempotency_keys", "absolute_paths_and_raw_job_names",
           "raw_event_payloads_and_error_messages", "configuration_inputs_environment_and_commands",
           "artifact_bytes_and_raw_logs", "management_receipts_and_other_runs", "filesystem_and_process_snapshot")
BODY = {"report_version": choice(REPORT_VERSION), "rules_version": choice(RULES_VERSION),
        "identity": {"project_id": ref("p"), "project_instance_id": ref("pi"), "storage_generation": ref("generation"),
                     "context_digest": hash_ref, "schema_version": number, "run_id": ref("r"), "job_ref": hash_ref,
                     "plan_id": ref("plan"), "historical_plan_digest": hash_ref},
        "view": {"source": choice("experiment_sqlite_read_transaction"), "read_at": number, "run_revision": number,
                 "project_event_upper_bound": number, "run_event_sequences": [number], "project_event_sequences": [number],
                 "all_run_records_within_limits": boolean, "atomic_scope": choice("database_records_only")},
        "facts": FACTS, "diagnostics": [ITEM], "unknowns": [choice(*UNKNOWN)],
        "coverage": {"events": number, "observations": number, "validations": number, "reconciliations": number},
        "disclosure": {"omitted": [choice(*OMITTED)], "artifact_bytes_included": boolean,
                       "artifacts_revalidated_now": boolean, "executable_authorization": boolean,
                       "anonymization": choice("field_whitelist_not_general_anonymization"),
                       "digest_scope": choice("canonical_public_body_only_not_original_records_or_signature")}}

# v1 exports remain readable without adding invented historical process evidence.
PROCESS_RECORD = {"pid": number, "creation_time_100ns": number,
                  "role": choice("launcher", "worker", "launcher_transport", "worker_transport"),
                  "identity_status": choice("VERIFIED"), "observed_at": number,
                  "execution_object_digest": hash_ref, "image_digest": hash_ref}
PROCESS_EXIT = {**PROCESS_RECORD, "exit_code": number, "exit_observed_at": number,
                "exit_source": choice("retained_windows_handle")}
MANAGED_SCOPE = {'scope_id':ref('scope'),'policy':choice('windows-job-list-v1'),
    'run_id':ref('r'),'phase_attempt_id':ref('phase'),'owner_id':ref('owner'),
    'project_instance_id':ref('pi'),'plan_digest':hash_ref,'owner_epoch':number,
    'binding':choice('CREATE_PROCESS_JOB_LIST'),'scope':choice('ROOT_AND_INHERITING_CREATEPROCESS_DESCENDANTS'),
    'kill_on_job_close':boolean,'breakaway_allowed':boolean,'named':boolean,'observed_at':number,
    'source':choice('QueryInformationJobObject.BasicAccounting'),'query_monotonic_ns':number,
    'creation_confirmed':boolean,'pending_additions':boolean,'active_processes':number,'total_processes':number,
    'limit_terminated_processes':number,'state':choice('EMPTY_CONFIRMED','NOT_COMPLETE')}
RUN_V2 = {**RUN, "phase": choice("PROCESS_FIXTURE"), "backend_id": choice("python-process-fixture-v1"),
          "backend_outcome_basis": choice("RECONCILED_RECORDED_OS_EXITS"),
          "backend_outcome": choice("NOT_RUN", "UNKNOWN", "COMPLETED", "FAILED"),
          "process_observation": choice("NOT_STARTED", "UNKNOWN", "IDENTITIES_VERIFIED", "EXIT_PARTIAL", "EXIT_OBSERVED"),
          "exit_verification": choice("UNKNOWN", "PARTIAL", "VERIFIED"),
          "process_failure_code": choice("PROCESS_IDENTITY_UNKNOWN", "PROCESS_IDENTITY_MISMATCH", "PROCESS_EXIT_UNKNOWN",
                                        "PROCESS_IO_FAILURE", "STORE_UNAVAILABLE", "PLAN_STALE", "PLAN_EXPIRED",
                                        "GRANT_EXPIRED", "GRANT_SCOPE_MISMATCH", "INVALID_REQUEST",
                                        'MANAGED_SCOPE_UNKNOWN','MANAGED_SCOPE_UNAVAILABLE','MANAGED_CREATE_FAILED','MANAGED_SCOPE_POLICY_CHANGED'),
          "process_records": [PROCESS_RECORD], "process_exits": [PROCESS_EXIT],
          'managed_scope':MANAGED_SCOPE,'managed_completion':choice('NOT_CONFIRMED','COMMITTED_EMPTY_SCOPE'),
          'managed_completion_recorded_at':number}
FACTS_V2 = {**FACTS, "run": RUN_V2,
            "plan": {**FACTS["plan"], "backend_id": choice("python-process-fixture-v1")},
            "events": [{**EVENT, "type": choice("REQUEST_ACCEPTED", "START_INTENT", "DISPATCH_BLOCKED", "PROCESS_IDENTITIES",
                "PROCESS_EXIT_OBSERVED", "PROCESS_COMPLETED", "VALIDATION_RECORDED", "RECONCILIATION_REQUIRED", "PROCESS_RECONCILIATION_APPLIED",
                'MANAGED_SCOPE_PREPARED','MANAGED_ROOT_CREATED','MANAGED_SCOPE_OBSERVED','MANAGED_SCOPE_COMPLETED'),
                "payload": {**EVENT["payload"], "backend_outcome": RUN_V2["backend_outcome"],
                            "process_records": [PROCESS_RECORD], "process_exits": [PROCESS_EXIT],
                            'managed_scope':MANAGED_SCOPE,'managed_completion':RUN_V2['managed_completion'],
                            'managed_completion_recorded_at':number}}],
            "observations": [{**OBSERVATION, "kind": choice("PROCESS_FIXTURE_JSON"), "provenance": choice("python-process-fixture-v1")}],
            "validations": [{**VALIDATION, "policy_id": choice("process-fixture-result-v1"), "validator_id": choice("process-fixture-validator"),
                             "source": choice("explicit_reconciliation", "explicit_client_validation")}],
            "reconciliations": [{"reconciliation_id": ref("rec"), "operation_id": ref("op"), "run_id": ref("r"),
                "owner_id": ref("owner"), "recorded_at": number, "source": choice("TEST_ONLY_RECORDED_OS_EXIT_RECONCILIATION"),
                "action": choice("reconcile_recorded_process_exits"), "policy": choice("recorded-process-reconciliation-v1"),
                "conclusion": choice("RECORDED_EXIT_SUCCESS", "RECORDED_EXIT_FAILURE"), "evidence_refs": [RECORD_REF]}]}
BODY_V2 = {**BODY, "report_version": choice("af-run-diagnostic-v2"), "rules_version": choice("process-diagnostic-rules-v2", "process-diagnostic-rules-v3",'process-diagnostic-rules-v4'),
           "facts": FACTS_V2,
           "diagnostics": [{**ITEM, "recorded_facts": {**ITEM["recorded_facts"], "backend_outcome": RUN_V2["backend_outcome"]}}]}

STANDARD_PROCESS = {**PROCESS_RECORD, 'role': lambda v: type(v) is str and (v == 'wrapper' or
                    (v.startswith('candidate_') and v[10:].isdigit() and len(v)<30))}
STANDARD_EXIT = {**STANDARD_PROCESS,'exit_code':number,'exit_observed_at':number,
                 'exit_source':choice('retained_windows_handle','direct_Popen_handle')}
STANDARD_RUN = {**RUN_V2,'backend_id':choice('abaqus-standard-axial-2024-v1'),'phase':choice('STANDARD_ANALYSIS'),
    'execution_phase':choice('WAITING_START','STARTING','OBSERVING','OBSERVATION_ENDED','EVIDENCE_RECORDED'),
    'process_observation':choice('NOT_STARTED','UNKNOWN','OBSERVED_SUBSET'),
    'process_records':[STANDARD_PROCESS],'process_exits':[STANDARD_EXIT],
    'solver_conclusion':choice('NOT_RUN','EVIDENCE_INSUFFICIENT','COMPLETED_TEXT_EVIDENCE','FAILED_TEXT_EVIDENCE'),
    'numerical_validation':choice('NOT_RUN','EVIDENCE_INSUFFICIENT','PRIMARY_THREE_PASS','NUMERICAL_FAIL'),
    'odb_content_validation':choice('NOT_RUN'),'member_completeness':choice('UNKNOWN'),'overall_exit':choice('UNKNOWN'),
    'launch_state':choice('NOT_CALLED','INTENT_PERSISTED','CALL_ENTERED_OUTCOME_UNKNOWN','PROCESS_OBJECT_RETURNED'),
    'all_observed_exited':boolean,'observation_deadline_reached':boolean,'observation_ended_at':number,
    'administrative_closeout':choice('LOGICAL_SLOT_RELEASED_WITH_RESIDUAL_UNCERTAINTY'),
    'disposition_record_id':ref('disposition'),
    'disposition_action':choice('retain_standard_resources','release_standard_logical_slot'),
    'validation_scope':choice('fixed_standard_dat_only')}
STANDARD_FACTS = {**FACTS_V2,'run':STANDARD_RUN,
    'plan':{**FACTS['plan'],'backend_id':choice('abaqus-standard-axial-2024-v1')},
    'events':[{**EVENT,'type':choice('REQUEST_ACCEPTED','START_INTENT','DISPATCH_BLOCKED','RECONCILIATION_REQUIRED',
        'STANDARD_STARTING','STANDARD_LAUNCH_INTENT','STANDARD_CREATE_ENTERING','STANDARD_CREATED','STANDARD_PROCESS_OBSERVATION',
        'STANDARD_OBSERVATION_ENDED','STANDARD_RESULT_RECORDED','STANDARD_DISPOSITION_RECORDED'),
        'payload':{k:STANDARD_RUN[k] for k in ('revision','execution','launch_state','solver_conclusion','numerical_validation','member_completeness')}}],
    'observations':[{'observation_id':ref('obs'),'run_id':ref('r'),'kind':choice('STANDARD_TEXT'),'observed_at':number,
        'artifacts':[{'logical_ref':choice('output:dat','output:sta','output:msg','output:log'),'digest':hash_ref,'size':number,'read_at':number}]}],
    'validations':[{**VALIDATION,'scope':choice('fixed_standard_dat_only'),'policy_id':choice('fixed-2024-axial-dat-v1'),
        'validator_id':choice('standard-dat-validator')}], 'reconciliations':[{
            'reconciliation_id':ref('disposition'),'operation_id':ref('op'),'run_id':ref('r'),
            'owner_id':ref('owner'),'recorded_at':number,'policy':choice('standard-closeout-v1'),
            'action':choice('retain_standard_resources','release_standard_logical_slot'),
            'source':choice('EXPLICIT_OPERATOR_POLICY_NOT_EXIT_EVIDENCE'),
            'effect':choice('LOGICAL_SLOT_RELEASED_ONLY','ALL_RESOURCES_RETAINED'),'evidence_refs':[RECORD_REF]}]}
BODY_V3 = {**BODY_V2,'report_version':choice('af-run-diagnostic-v3'),'rules_version':choice('standard-diagnostic-rules-v1','standard-diagnostic-rules-v2'),'facts':STANDARD_FACTS}
BODY_V3_LEGACY = {**BODY_V3, 'facts':{**STANDARD_FACTS,
    'run':{k:v for k,v in STANDARD_RUN.items() if k not in {'administrative_closeout','disposition_record_id','disposition_action'}},
    'reconciliations':[RECONCILIATION]}}


def report_bytes(report):
    """Verify only the public audit envelope; never consult the store or artifacts."""
    bounded_tree(report)
    encoded = canonical_json(report).encode("utf-8")
    require(len(encoded) <= MAX_REPORT_BYTES, "LIMIT_EXCEEDED", "Diagnostic response exceeds bound")
    report = json.loads(encoded)  # Validate the exact detached bytes that will be exported.
    require(type(report) is dict and set(report) == {"body", "content_digest"}, "INVALID_REPORT", "Invalid audit envelope")
    schema = {'af-run-diagnostic-v2':BODY_V2,'af-run-diagnostic-v3':BODY_V3}.get(report['body'].get('report_version'),BODY)
    if report['body'].get('rules_version')=='standard-diagnostic-rules-v1': schema=BODY_V3_LEGACY
    require(project(report["body"], schema) == report["body"] and report["body"].get("report_version") in {REPORT_VERSION, "af-run-diagnostic-v2", 'af-run-diagnostic-v3'},
            "INVALID_REPORT", "Audit fields are outside the public projection")
    require(digest(report["body"]) == report["content_digest"], "INVALID_REPORT", "Audit projection digest mismatch")
    return encoded


def build_report(context, raw):
    try:
        decoded = {}
        for table in ("run", "plan", "receipts", "events", "observations", "validations", "reconciliations"):
            decoded[table] = []
            for row in raw[table]:
                value = json.loads(row[0])
                bounded_tree(value)
                require(type(value) is dict, "STORE_UNAVAILABLE", "Persisted record is not an object")
                if table == "events":
                    value.update(project_sequence=row[1], run_sequence=row[2])
                decoded[table].append(value)
        r = decoded["run"][0]
        require(r.get("run_id") == raw["requested_run_id"] and r.get("project_id") == context.project_id
                and r.get("project_instance_id") == context.project_instance_id
                and valid_id(r.get("plan_id"), "plan") and number(r.get("revision")),
                "STORE_UNAVAILABLE", "Persisted Run binding is inconsistent")
        if decoded["plan"]:
            require(decoded["plan"][0].get("plan_id") == r["plan_id"], "STORE_UNAVAILABLE", "Persisted Plan binding is inconsistent")
        for table in ("receipts", "events", "observations", "validations", "reconciliations"):
            require(all(row.get("run_id") == r["run_id"] for row in decoded[table]),
                    "STORE_UNAVAILABLE", "Persisted evidence binding is inconsistent")
        process_run = r.get("backend_id") == "python-process-fixture-v1"
        standard_run = r.get('backend_id') == 'abaqus-standard-axial-2024-v1'
        facts = project({"run": r, "receipt": next(iter(decoded["receipts"]), None),
                         "plan": next(iter(decoded["plan"]), None), "dispatch_gate": raw["gate"],
                         **{k: decoded[k] for k in ("events", "observations", "validations", "reconciliations")}}, STANDARD_FACTS if standard_run else FACTS_V2 if process_run else FACTS)
        run, receipt, gate = facts["run"], facts["receipt"], facts["dispatch_gate"]
        seqs = [e["run_sequence"] for e in facts["events"]]
        unknowns = list(UNKNOWN[:6])
        if not receipt:
            unknowns.append("ORIGINAL_RECEIPT_NOT_RECORDED")
        if not facts["plan"]:
            unknowns.append("PLAN_RECORD_NOT_RECORDED")
        if seqs != list(range(1, len(seqs) + 1)) or not seqs:
            unknowns.append("RUN_EVENT_SEQUENCE_GAP")
        if not facts["validations"]:
            unknowns.append("VALIDATION_NOT_RECORDED")
        if not gate:
            unknowns.append("GATE_NOT_RECORDED")
        uncertain = run["execution"] in {"START_INTENT", "VALIDATING"} or run["reconciliation"] == "RECONCILIATION_REQUIRED"
        codes = []
        if receipt and receipt["request_status"] == "ACCEPTED": codes.append("REQUEST_ACCEPTED")
        if run["queue_state"] == "PENDING": codes.append("WAITING_DISPATCH")
        if any(e["type"] == "START_INTENT" for e in facts["events"]): codes.append("EXECUTION_STARTED")
        if uncertain: codes.append("EXECUTION_UNCERTAIN")
        if uncertain and not any(v["verdict"] == "PASS" for v in facts["validations"]): codes.append("EVIDENCE_INSUFFICIENT")
        if any(v["verdict"] == "FAIL" for v in facts["validations"]): codes.append("HISTORICAL_VALIDATION_FAILED")
        if not standard_run and any(v["verdict"] == "PASS" for v in facts["validations"]): codes.append("HISTORICAL_VALIDATION_PASSED")
        if facts["reconciliations"]: codes.append("ADMINISTRATIVE_DISPOSITION" if standard_run else "EXPLICITLY_RECONCILED")
        if gate and gate["state"] == "PAUSED": codes.append("DISPATCH_PAUSED")
        if not process_run and not standard_run and run["backend_outcome"] == "COMPLETED": codes.append("FAKE_COMPLETED")
        if standard_run:
            codes.extend(['STANDARD_RECORDED_TEXT','PROCESS_EXIT_NOT_ESTABLISHED'])
        if process_run:
            if run.get('managed_scope'):
                codes.append('MANAGED_SCOPE_ENDED' if run.get('managed_completion')=='COMMITTED_EMPTY_SCOPE' else 'MANAGED_SCOPE_UNCONFIRMED')
            records, exits = run.get("process_records") or [], run.get("process_exits") or []
            roles = {"launcher", "worker", "launcher_transport", "worker_transport"}
            complete_exits = (run["exit_verification"] == "VERIFIED" and len(records) == len(exits) == 4
                and {p["role"] for p in records} == {p["role"] for p in exits} == roles
                and all(p["identity_status"] == "VERIFIED" and p["pid"] is not None and p["creation_time_100ns"] is not None for p in records)
                and all(e["exit_source"] == "retained_windows_handle" and e["exit_observed_at"] is not None
                    and e["exit_code"] is not None and any(p["role"] == e["role"] and p["pid"] == e["pid"]
                        and p["creation_time_100ns"] == e["creation_time_100ns"] for p in records) for e in exits))
            if complete_exits and run["backend_outcome"] == "COMPLETED" and all(e["exit_code"] == 0 for e in exits):
                codes.append("TEST_PROCESS_COMPLETED")
            if run["backend_outcome"] == "FAILED": codes.append("TEST_PROCESS_FAILED")
            if run.get("process_records"): codes.append("HISTORICAL_PROCESS_IDENTITY")
            if not complete_exits: codes.append("PROCESS_EXIT_NOT_ESTABLISHED")
            if any(v.get("action") == "reconcile_recorded_process_exits" for v in facts["reconciliations"]):
                codes.append("RECORDED_EXITS_RECONCILED")
        if r.get("error") is None: codes.append("NO_RECORDED_ERROR")
        if run["queue_state"] == "BLOCKED": codes.append("DISPATCH_BLOCKED")
        refs = [run["run_id"]] + ([receipt["request_id"]] if receipt else [])
        refs += [row[key] for table, key in (("events", "event_id"), ("validations", "validation_id"), ("reconciliations", "reconciliation_id")) for row in facts[table]]
        findings = [{"reason_code": code, "classification": RULES[code][0],
                     "recorded_facts": {"request_status": receipt["request_status"] if receipt else None,
                                        **{k: run[k] for k in ("queue_state", "execution", "backend_outcome", "artifact_validation")},
                                        "gate_state": gate["state"] if gate else None},
                     "inference": RULES[code][1], "unknowns": unknowns, "source_refs": refs,
                     "next_step": {"candidate": RULES[code][2], "preconditions": list(PRECONDITIONS)}} for code in codes]
        body = project({"report_version": 'af-run-diagnostic-v3' if standard_run else "af-run-diagnostic-v2" if process_run else REPORT_VERSION,
                        "rules_version": 'standard-diagnostic-rules-v2' if standard_run else ('process-diagnostic-rules-v4' if run.get('managed_scope') else "process-diagnostic-rules-v3") if process_run else RULES_VERSION,
                        "identity": {"project_id": context.project_id, "project_instance_id": context.project_instance_id,
                                     "storage_generation": context.storage_generation, "context_digest": context.context_digest,
                                     "schema_version": context.schema_version, "run_id": run["run_id"],
                                     "job_ref": digest(r["job_id"]) if "job_id" in r else None,
                                     "plan_id": run["plan_id"], "historical_plan_digest": run["plan_digest"]},
                        "view": {"source": "experiment_sqlite_read_transaction", "read_at": raw["read_at"], "run_revision": run["revision"],
                                 "project_event_upper_bound": raw["event_upper_bound"], "run_event_sequences": seqs,
                                 "project_event_sequences": [e["project_sequence"] for e in facts["events"]],
                                 "all_run_records_within_limits": True, "atomic_scope": "database_records_only"},
                        "facts": facts, "diagnostics": findings, "unknowns": unknowns,
                        "coverage": {k: len(facts[k]) for k in ("events", "observations", "validations", "reconciliations")},
                        "disclosure": {"omitted": list(OMITTED), "artifact_bytes_included": False,
                                       "artifacts_revalidated_now": False, "executable_authorization": False,
                                       "anonymization": "field_whitelist_not_general_anonymization",
                                       "digest_scope": "canonical_public_body_only_not_original_records_or_signature"}}, BODY_V3 if standard_run else BODY_V2 if process_run else BODY)
        result = {"body": body, "content_digest": digest(body)}
        report_bytes(result)
        return result
    except (ExecutionError, ValueError, TypeError, KeyError, RecursionError) as exc:
        raise read_error(exc) from None
