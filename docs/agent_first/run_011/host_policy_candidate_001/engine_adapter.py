"""Single experiment attempt; internal injection seam for fixed non-Solver tests.

The public CLI never accepts this internal spec, spawn callback or host provider.
No locks/records are removed. No retry, observer thread, terminate or kill exists.
"""
from pathlib import Path
import time
import uuid

from records import (Refusal, Journal, require, safe_path, stable_read, read_json,
                     write_new, stamp)
from windows_host import ObservedProcesses, close_child_reference
from host_policy import admit
from printed_results import parse


def check_empty(spec):
    root = safe_path(spec['root'])
    for name in ('observations', 'engineering', 'engineering/scratch', 'extracted'):
        require(safe_path(root / name).is_dir(), 'DIRECTORY_UNAVAILABLE')
    require(not (root / 'observations/attempt.json').exists(), 'ATTEMPT_EXISTS')
    require(not any((root / 'observations').iterdir()) and not any((root / 'extracted').iterdir()),
            'OBSERVATION_OR_RESULT_EXISTS')
    require(not any((root / 'engineering').glob(spec['job'] + '.*')), 'OUTPUT_EXISTS')
    require(not any((root / 'engineering/scratch').iterdir()), 'SCRATCH_NOT_EMPTY')


def collect_files(spec, intent, process_view):
    root = Path(spec['root'])
    result = {'solver': 'EVIDENCE_INSUFFICIENT', 'numerical': 'EVIDENCE_INSUFFICIENT',
              'odb_content_validation': 'NOT_RUN', 'observations': []}
    if 'input_path' in spec:
        _, input_identity = stable_read(spec['input_path'])
        require('sha256:' + input_identity['sha256'] == spec['input_digest'], 'INPUT_CHANGED_DURING_ATTEMPT')
        result['input_identity'] = input_identity
    paths = list((root / 'engineering').glob(spec['job'] + '.*'))
    require(len(paths) <= 64, 'FILE_COUNT_LIMIT')
    for path in paths:
        info = safe_path(path).stat()
        result['observations'].append({'relative_path': str(path.relative_to(root)),
            'bytes': info.st_size, 'mtime_ns': info.st_mtime_ns, 'observed_at_ns': stamp(),
            'source': 'external_controller_file_metadata', 'may_still_be_written': True})
    dat = root / 'engineering' / (spec['job'] + '.dat')
    if not dat.exists():
        result['reason'] = 'DAT_MISSING'; return result
    data, identity = stable_read(dat)
    result['dat_identity'] = identity
    require(identity['ctime_ns'] >= intent['start_intent_at_ns']
            and identity['mtime_ns'] >= intent['start_intent_at_ns'], 'OLD_OR_UNATTRIBUTED_DAT')
    if not process_view.get('all_observed_exited'):
        result['reason'] = 'OBSERVED_PROCESS_EXIT_INCOMPLETE'; return result
    result.update(parse(data))
    result['scope'] = 'historical bounded text view; full process set and ODB unverified'
    return result


def run_once(spec, candidate_digest, verify, host_query, spawn, *, observer=ObservedProcesses,
             close_child=close_child_reference, checkpoint=lambda phase: None):
    """Durable O_EXCL intent is the concurrency claim, independent of candidate digest."""
    verify()
    check_empty(spec)
    host = host_query()
    admit(host)  # Must precede ANY attempt or log write.
    root = safe_path(spec['root'])
    require(0 < spec['budget_seconds'] <= 300, 'OBSERVATION_BUDGET_INVALID')
    attempt = root / 'observations/attempt.json'
    started = time.monotonic()
    intent = {'schema': 'r011-experiment-attempt-v1', 'experiment_id': spec['experiment_id'],
              'attempt_id': 'attempt_' + uuid.uuid4().hex, 'output_identity': spec['output_identity'],
              'candidate_digest': candidate_digest, 'original_digest': spec['original_digest'],
              'start_intent_at_ns': stamp(), 'budget_seconds': spec['budget_seconds'],
              'state': 'START_INTENT', 'source': 'external_experiment_controller_not_Project_Run',
              'input_digest': spec.get('input_digest', 'TEST_FIXTURE_NO_SOLVER_INPUT'),
              'host': host, 'preexisting_job_outputs': [], 'authorization_claim': 'NONE',
              'invocation_context': 'explicit_operator_operation; digest is not approval'}
    write_new(attempt, intent)  # If partial write/fsync fails: no launch, residue retained.
    child = observed = journal = stdout = stderr = None
    report = {'schema': 'r011-experiment-report-v1', 'attempt_id': intent['attempt_id'],
              'experiment_id': spec['experiment_id'], 'candidate_digest': candidate_digest,
              'source': intent['source'], 'creation': 'NOT_CALLED', 'processes': {'overall_exit':'UNKNOWN',
              'member_completeness':'UNKNOWN'}, 'solver':'NOT_OBSERVED', 'numerical':'NOT_RUN',
              'odb_content_validation':'NOT_RUN', 'overall':'PARTIAL', 'deadline_reached':False}
    try:
        checkpoint('intent_persisted')
        # Race check after winning claim; old evidence never overwritten.
        require(not any((root / 'engineering').glob(spec['job'] + '.*')), 'OUTPUT_EXISTS')
        journal = Journal(root / 'observations/controller_events.jsonl')
        stdout = safe_path(root / 'observations/stdout.bin').open('xb', buffering=0)
        stderr = safe_path(root / 'observations/stderr.bin').open('xb', buffering=0)
        journal.append('START_INTENT_PERSISTED', attempt_id=intent['attempt_id'],
                       logs={'stdout':'observations/stdout.bin','stderr':'observations/stderr.bin',
                             'kind':'exclusive_regular_files', 'owner':'controller; child inherits copies'})
        require(time.monotonic() - started < spec['budget_seconds'], 'BUDGET_EXHAUSTED_BEFORE_CREATE')
        journal.append('CREATE_CALL_ENTERING', meaning='not proof of OS creation')
        report['creation'] = 'CALL_ENTERED_OUTCOME_UNKNOWN'
        creation_start = time.monotonic()
        child = spawn(stdout, stderr)
        report.update(creation='PROCESS_OBJECT_RETURNED', launch_pid=child.pid,
                      creation_duration_seconds=time.monotonic() - creation_start)
        checkpoint('process_created')
        journal.append('PROCESS_OBJECT_RETURNED', pid=child.pid,
                       creation_duration_seconds=report['creation_duration_seconds'])
        observed = observer(child, journal)
        while time.monotonic() - started < spec['budget_seconds']:
            report['processes'] = observed.sample()
            time.sleep(min(0.05, max(0, spec['budget_seconds'] - (time.monotonic() - started))))
        report['deadline_reached'] = True
        report['processes'] = observed.view()  # No additional blocking wait after deadline.
        report['observation_finished_at_ns'] = stamp()
        report['observation_elapsed_seconds'] = time.monotonic() - started
        journal.append('OBSERVATION_ENDED', processes=report['processes'],
                       reason='STOP_WAITING_ONLY', no_termination=True)
        report['results'] = collect_files(spec, intent, report['processes'])
        report['solver'], report['numerical'] = report['results']['solver'], report['results']['numerical']
    except BaseException as exc:
        report['failure'] = getattr(exc, 'code', type(exc).__name__)
        report['outcome'] = 'UNKNOWN_NO_RETRY'
        if observed is not None:
            report['processes'] = observed.view()
    finally:
        # Closing process references and our file handles cannot terminate descendants.
        for obj in (observed, journal, stdout, stderr):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    report.setdefault('close_errors', []).append(type(obj).__name__)
        if child is not None:
            try:
                close_child(child)
            except Exception:
                report.setdefault('close_errors', []).append('child_reference')
    report['returned_at_ns'] = stamp()
    report['elapsed_including_creation_and_reporting_seconds'] = time.monotonic() - started
    try:
        write_new(root / 'observations/controller_report.json', report)
    except Exception:
        raise Refusal('REPORT_COMMIT_UNKNOWN_QUERY_EXISTING_ATTEMPT') from None
    return report


def read_report(spec):
    """Only recorded views. No live process check, repair, result revalidation or writes."""
    root = safe_path(spec['root'])
    attempt = root / 'observations/attempt.json'
    if not attempt.exists():
        return {'status':'NO_ATTEMPT_RECORDED', 'solver':'NOT_RUN', 'numerical':'NOT_RUN',
                'odb_content_validation':'NOT_RUN'}
    intent = read_json(attempt)
    require(intent['schema'] == 'r011-experiment-attempt-v1'
            and intent['experiment_id'] == spec['experiment_id']
            and intent['output_identity'] == spec['output_identity'], 'ATTEMPT_INVALID')
    report = root / 'observations/controller_report.json'
    if not report.exists():
        return {'status':'ATTEMPT_WITHOUT_CONFIRMED_REPORT', 'attempt_id':intent['attempt_id'],
                'creation':'UNKNOWN', 'overall_exit':'UNKNOWN', 'retry':'FORBIDDEN'}
    value = read_json(report)
    require(value['attempt_id'] == intent['attempt_id'], 'REPORT_IDENTITY_MISMATCH')
    return {'status':'HISTORICAL_RECORDED_VIEW', 'read_at_ns':stamp(), 'report':value,
            'current_process_state':'NOT_PROBED', 'current_artifacts':'NOT_REVALIDATED'}
