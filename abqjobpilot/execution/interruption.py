"""Read-only interruption projection. No recovery, permission or execution policy.

The report is evidence for review, never an executable request. Current OS
observations are opt-in and occur only AFTER the database read transaction ends.
"""
import json

from .models import ExecutionError, canonical_json, digest, require
from .diagnostics import build_report, bounded_tree, valid_id, project, number, ref

VERSION = 'af-interruption-diagnostic-v1'
RULES = 'interruption-rules-v1'
MAX_BYTES = 131072
LABELS = {'en': 'Interrupted (Unverified)', 'zh-CN': '异常中断（结果未验证）'}


def _decoded(raw, key):
    values = [json.loads(row[0]) for row in raw[key]]
    for value in values:
        bounded_tree(value)
        require(type(value) is dict, 'STORE_UNAVAILABLE', 'Invalid diagnostic record')
    return values


def _scope_valid(run, events):
    from .managed_process import check_completion
    try:
        check_completion(run.get('managed_scope'), run)
        scope = run['managed_scope']
        return (run.get('managed_completion') == 'COMMITTED_EMPTY_SCOPE'
                and valid_id(scope.get('scope_id'), 'scope')
                and any(e.get('type') in {'STANDARD_MANAGED_COMPLETED', 'MANAGED_SCOPE_COMPLETED'}
                        and e.get('payload', {}).get('managed_scope') == scope
                        and e.get('payload', {}).get('managed_completion') == 'COMMITTED_EMPTY_SCOPE'
                        for e in events))
    except (ExecutionError, KeyError, TypeError, AttributeError):
        return False


def _not_observed():
    return {'source': 'NOT_REQUESTED', 'started_at': None, 'finished_at': None,
            'owner': {'state': 'NOT_OBSERVED'}, 'members': [],
            'boot': {'state': 'NOT_OBSERVED', 'confidence': 'UNKNOWN'},
            'lock': 'NOT_ACQUIRED', 'scope_handle': 'NOT_QUERIED'}


def _classify(run, facts, events, extra, os_view, coherent, managed_valid, admin_valid, managed_expected):
    reasons = []
    owner = os_view['owner']['state']
    active = any(m['state'] == 'EXACT_IDENTITY_ALIVE' for m in os_view['members'])
    changed = run.get('owner_id') != extra['store_owner_id']
    started = any(e.get('type') == 'START_INTENT' for e in events)
    incomplete = run.get('execution') in {'START_INTENT', 'VALIDATING', 'BLOCKED'}
    if managed_valid and active:
        coherent = False  # A same-identity active member contradicts scope completion.
    if not coherent:
        classification = 'EVIDENCE_CONFLICT'
        reasons.append('PERSISTED_BINDING_OR_HISTORY_INCOMPLETE')
    elif admin_valid:
        classification = 'ADMINISTRATIVE_DISPOSITION_RECORDED'
        reasons.append('ADMINISTRATIVE_RELEASE_IS_NOT_EXIT_EVIDENCE')
    elif (run.get('execution') == 'PLANNED' and run.get('queue_state') == 'PENDING'
          and not started and not run.get('process_records') and not run.get('managed_scope')
          and run.get('launch_state', 'NOT_CALLED') == 'NOT_CALLED'):
        classification = 'NEVER_STARTED_RECORDED'
        reasons.append('ACCEPTED_PENDING_NO_RECORDED_START')
    elif managed_valid or (run.get('execution') == 'FINISHED' and run.get('reconciliation') == 'NONE'
                          and not managed_expected and not run.get('managed_scope') and any(e.get('type') in {
                              'FAKE_COMPLETED', 'PROCESS_COMPLETED', 'PROCESS_RECONCILIATION_APPLIED',
                              'RECONCILIATION_APPLIED'} for e in events)):
        classification = 'COMPLETION_RECORDED'
        reasons.append('HISTORICAL_COMPLETION_NOT_CURRENT_PROCESS_HEALTH')
    elif started and incomplete and (owner == 'EXACT_IDENTITY_EXITED' or changed):
        classification = 'OWNER_LOST_WORKER_ACTIVE' if active else 'SUPERVISION_INTERRUPTION_SUSPECTED'
        reasons.append('OWNER_EXIT_OBSERVED_NOW' if owner == 'EXACT_IDENTITY_EXITED' else 'PERSISTED_OWNER_CHANGED')
    elif (started and incomplete and os_view['boot'].get('state') == 'LATER_BOOT_ESTIMATE'
          and owner in {'IDENTITY_MISMATCH', 'PROCESS_UNAVAILABLE'} and not active):
        classification = 'SUPERVISION_INTERRUPTION_SUSPECTED'
        reasons.append('BOOT_ESTIMATE_AND_OWNER_DISCONTINUITY_SUPPORT_SUSPICION_ONLY')
    elif active or owner == 'EXACT_IDENTITY_ALIVE':
        classification = 'EXECUTION_ACTIVITY_OBSERVED'
        reasons.append('GUI_OR_CONNECTION_LOSS_IS_NOT_SOLVER_INTERRUPTION')
    else:
        classification = 'EXECUTION_STATE_UNKNOWN'
        reasons.append('NO_SUFFICIENT_INTERRUPTION_EVIDENCE')
    if active:
        reasons.append('KNOWN_MEMBER_ACTIVE_NO_RECOVERY_PERMISSION')
    if (managed_expected or run.get('managed_scope')) and started and not managed_valid:
        reasons.append('MANAGED_COMPLETION_NOT_COMMITTED_OR_BINDING_INVALID')
    if run.get('solver_conclusion') == 'COMPLETED_TEXT_EVIDENCE':
        reasons.append('SOLVER_COMPLETION_RECORDED_SEPARATELY')
    if run.get('artifact_validation') in {'NOT_RUN', 'UNKNOWN', None}:
        reasons.append('ARTIFACT_VALIDATION_INCOMPLETE_NOT_CRASH_PROOF')
    if run.get('odb_content_validation') == 'NOT_RUN':
        reasons.append('ODB_NOT_RUN_NOT_CRASH_PROOF')
    if owner in {'IDENTITY_MISMATCH', 'PROCESS_UNAVAILABLE', 'QUERY_FAILED', 'IDENTITY_UNRECORDED'}:
        reasons.append('OWNER_ABSENCE_OR_MISMATCH_IS_NOT_DESCENDANT_EXIT')
    projection = ('UNKNOWN_INTERRUPTED' if classification in {
        'SUPERVISION_INTERRUPTION_SUSPECTED', 'OWNER_LOST_WORKER_ACTIVE'} else classification)
    return {'classification': classification, 'display_projection': projection,
            'message_key': 'interruption.' + projection.lower(),
            'reason_codes': reasons, 'known_member_active': active,
            'activity_coverage': 'recorded_identities_only_not_complete_membership',
            'interruption_confidence': 'SUSPECTED_ONLY' if projection == 'UNKNOWN_INTERRUPTED' else 'NOT_ASSERTED'}


def _reason_refs(reason):
    """JSON pointers into this exact report, not paths or fresh external facts."""
    if reason.startswith('OWNER_EXIT'): return ['/current_observation/owner']
    if reason.startswith('PERSISTED_OWNER'): return ['/owner', '/facts/events']
    if reason.startswith('BOOT_'): return ['/current_observation/boot', '/current_observation/owner', '/facts/events']
    if reason.startswith(('KNOWN_MEMBER', 'GUI_OR')): return ['/current_observation/members', '/current_observation/owner']
    if reason.startswith('ADMINISTRATIVE'): return ['/facts/reconciliations', '/resources']
    if reason.startswith('MANAGED_'): return ['/facts/run/managed_scope', '/facts/events']
    if reason.startswith('SOLVER_'): return ['/facts/run/solver_conclusion']
    if reason.startswith('ARTIFACT_'): return ['/facts/run/artifact_validation', '/facts/validations']
    if reason.startswith('ODB_'): return ['/facts/run/odb_content_validation']
    if reason.startswith('OWNER_ABSENCE'): return ['/current_observation/owner']
    return ['/facts/run', '/facts/events', '/view']


def build_interruption_report(context, raw, os_view=None):
    """Internal pure rule seam; not an approval or caller-supplied evidence API."""
    audit = build_report(context, raw)['body']  # Reuse existing allowlisted historical facts.
    run = _decoded(raw, 'run')[0]
    require(type(run.get('process_records', [])) is list and len(run.get('process_records', [])) <= 32,
            'LIMIT_EXCEEDED', 'Recorded process list exceeds diagnostic bound')
    plans, events = _decoded(raw, 'plan'), _decoded(raw, 'events')
    decisions, validations = _decoded(raw, 'reconciliations'), _decoded(raw, 'validations')
    extra = raw['interruption']
    os_view = _not_observed() if os_view is None else os_view
    # Current observations are generated privately, and projected a second time
    # before return. No public request accepts an observation object.
    from .interruption_probe import public_observation
    os_view = public_observation(os_view)
    starts = [e for e in events if e.get('type') == 'START_INTENT']
    coherent = (len(plans) == 1 and plans[0].get('plan_digest') == run.get('plan_digest')
        and plans[0].get('plan_digest') == digest({k: v for k, v in plans[0].items() if k != 'plan_digest'})
        and plans[0].get('project_instance_id') == context.project_instance_id
        and plans[0].get('context_digest') == context.context_digest
        and len(raw['receipts']) == 1 and len(extra['consumption']) == 1
        and tuple(extra['consumption'][0]) == (run.get('grant_id'), run.get('run_id'))
        and [row[2] for row in raw['events']] == list(range(1, len(events) + 1))
        and len([e for e in events if e.get('type') == 'REQUEST_ACCEPTED']) == 1
        and len(starts) <= 1
        and all(v.get('phase_attempt_id') == run.get('phase_attempt_id') for v in validations))
    coherent = coherent and (valid_id(run.get('owner_id'), 'owner')
        and valid_id(run.get('phase_attempt_id'), 'phase') and number(run.get('owner_epoch'))
        and run.get('backend_id') == plans[0].get('backend_id')
        and run.get('backend_id') in {'fake-v1', 'python-process-fixture-v1', 'abaqus-standard-axial-2024-v1'}
        and run.get('execution') in {'PLANNED', 'START_INTENT', 'VALIDATING', 'BLOCKED', 'FINISHED'}
        and all(e.get('run_sequence') == row[2] for e, row in zip(events, raw['events'])))
    if run.get('execution') != 'PLANNED' and not starts:
        coherent = False
    if starts and any(starts[0].get('payload', {}).get(k) != run.get(k) for k in ('owner_id', 'owner_epoch')):
        coherent = False
    managed_valid = _scope_valid(run, events)
    admin_valid = any(d.get('reconciliation_id') == run.get('disposition_record_id')
        and d.get('policy') == 'standard-closeout-v1'
        and d.get('action') == 'release_standard_logical_slot'
        and d.get('operation_id') in extra['committed_operations']
        and d.get('retention', {}).get('state') == 'RETAINED_NO_REUSE'
        for d in decisions) and run.get('administrative_closeout') == 'LOGICAL_SLOT_RELEASED_WITH_RESIDUAL_UNCERTAINTY'
    if run.get('administrative_closeout') and not admin_valid:
        coherent = False
    managed_expected = bool(plans and (plans[0].get('process_management') or plans[0].get('process_fixture', {}).get('managed_scope')))
    classification = _classify(run, audit['facts'], events, extra, os_view, coherent, managed_valid, admin_valid, managed_expected)
    scope = run.get('managed_scope')
    unknowns = ['DOMAIN_EXTERNAL_PROCESSES_UNKNOWN', 'CURRENT_ARTIFACT_BYTES_NOT_READ',
                'NO_ATOMIC_DATABASE_AND_OS_VIEW', 'LOCK_OWNERSHIP_NOT_ACQUIRED',
                'NO_RECOVERY_OR_EXECUTION_AUTHORITY', 'HISTORICAL_BOOT_SESSION_NOT_RECORDED',
                'HISTORICAL_OWNER_OS_IDENTITY_NOT_IN_RUN']
    if not run.get('process_exits'): unknowns.append('PERSISTED_EXIT_EVIDENCE_MISSING')
    if (managed_expected or scope) and starts and not managed_valid: unknowns.append('ORIGINAL_MANAGED_SCOPE_COMPLETION_UNCONFIRMED')
    if os_view['source'] == 'NOT_REQUESTED': unknowns.append('CURRENT_OS_NOT_OBSERVED')
    preview_policy = ('standard-closeout-v1' if run.get('backend_id') == 'abaqus-standard-axial-2024-v1'
                      else 'recorded-process-reconciliation-v1' if run.get('backend_id') == 'python-process-fixture-v1'
                      and not scope else None)
    stable = json.loads(json.dumps({k: v for k, v in raw.items() if k != 'read_at'}))
    body = {'report_version': VERSION, 'rules_version': RULES, 'identity': audit['identity'],
        'view': {**audit['view'], 'snapshot_digest': digest(stable),
                 'atomic_scope': 'database_records_only; OS observation follows transaction close'},
        'facts': audit['facts'],
        'owner': {**project({'recorded_owner_id': run.get('owner_id'), 'recorded_epoch': run.get('owner_epoch'),
                  'store_owner_id': extra['store_owner_id']}, {'recorded_owner_id': ref('owner'),
                   'recorded_epoch': number, 'store_owner_id': ref('owner')}),
                  'process_identity_source': 'owner.json only if exact binding matches'},
        'last_recorded_event': audit['facts']['events'][-1] if audit['facts']['events'] else None,
        'current_observation': os_view, 'diagnosis': classification,
        'reason_evidence': [{'reason_code': reason, 'report_pointers': _reason_refs(reason)}
                            for reason in classification['reason_codes']],
        'managed_completion_checked': managed_valid,
        'managed_scope_diagnostic': ('COMMITTED_BOUND_COMPLETION' if managed_valid else
            'RECORDED_UNCONFIRMED' if scope else 'MISSING_RECORDED_SCOPE' if managed_expected and starts else
            'NOT_STARTED' if managed_expected else 'NOT_CONFIGURED'),
        'recorded_process_identities': [
            {**project(member, {'pid': number, 'creation_time_100ns': number}), 'record_index': i,
             'image_digest': digest(member['image_path']) if type(member.get('image_path')) is str else None}
            for i, member in enumerate(run.get('process_records', [])) if type(member) is dict],
        'resources': {'slot_run_id': extra['slot_run_id'], 'gate': audit['facts']['dispatch_gate'],
            'administrative_release_committed': admin_valid,
            'path_policy': 'RETAINED_NO_REUSE' if admin_valid else 'RECORDED_PLAN_SCOPE_NO_RELEASE_BY_DIAGNOSTIC',
            'paths': [{'logical_ref': 'plan:' + k, 'identity_digest': digest(plans[0][k])}
                      for k in ('engineering', 'scratch', 'output_key') if plans and k in plans[0]]},
        'unknowns': unknowns,
        'recovery_preview': {'may_request_readonly_review': bool(coherent and preview_policy
                               and classification['classification'] != 'EVIDENCE_CONFLICT'),
            'policy': preview_policy, 'eligibility_not_evaluated': True, 'apply_allowed': False,
            'preconditions': ['fresh matching snapshot', 'existing policy support', 'separate current owner admission']},
        'disclosure': {'credentials_included': False, 'absolute_image_paths_included': False,
            'artifact_bytes_included': False, 'business_writes': False,
            'digest_is_authorization': False}}
    # A deterministic decision fingerprint excludes presentation/read timestamps.
    body['decision_digest'] = digest({'snapshot_digest': body['view']['snapshot_digest'],
        'diagnosis': classification, 'managed_completion_checked': managed_valid, 'admin': admin_valid})
    bounded_tree(body)
    require(len(canonical_json(body).encode('utf-8')) <= MAX_BYTES, 'LIMIT_EXCEEDED', 'Interruption report too large')
    return {'body': body, 'content_digest': digest(body)}


def inspect_store(store, context, run_id, *, observe_os=False):
    require(type(observe_os) is bool, 'INVALID_REQUEST', 'Explicit observation flag required')
    from .diagnostics import read_error
    try:
        raw = store._diagnostic_snapshot(context, run_id, interruption=True)
        baseline = build_interruption_report(context, raw)
        if observe_os and baseline['body']['diagnosis']['classification'] != 'EVIDENCE_CONFLICT':
            from .interruption_probe import observe
            observation = observe(context, _decoded(raw, 'run')[0])
            return build_interruption_report(context, raw, observation)
        return baseline
    except (ExecutionError, ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, RecursionError) as exc:
        raise read_error(exc) from None


def inspect_interrupted_execution(project_context, run_id, *, observe_os=False):
    """Python read-only entry. Does not start/connect/adopt a Supervisor."""
    from .store import ReadOnlyStore
    return ReadOnlyStore(project_context).inspect_interrupted_execution(project_context, run_id, observe_os=observe_os)
