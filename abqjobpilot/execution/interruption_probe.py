"""Opt-in bounded observation of recorded identities; never adoption or control.

No process enumeration, IPC, executable invocation or Job reopening. An unavailable
process is NOT exit evidence. The wall-clock/uptime estimate is not a boot ID.
"""
import ctypes
import json
from pathlib import Path
import time

from .models import ExecutionError, now, digest, require
from .paths import confined
from .diagnostics import project, number, hash_ref, choice, bounded_tree

STATES = ('NOT_OBSERVED', 'EXACT_IDENTITY_ALIVE', 'EXACT_IDENTITY_EXITED',
          'IDENTITY_MISMATCH', 'PROCESS_UNAVAILABLE', 'QUERY_FAILED',
          'IDENTITY_UNRECORDED', 'BUDGET_EXHAUSTED')
IDENTITY = {'pid': number, 'creation_time_100ns': number, 'image_digest': hash_ref}
PROCESS = {'state': choice(*STATES), 'expected': IDENTITY, 'observed_at': number,
           'exit_code': number, 'source': choice('CURRENT_RETAINED_HANDLE', 'NONE'),
           'record_index': number}
BOOT = {'state': choice('NOT_OBSERVED', 'QUERY_FAILED', 'ESTIMATE_ONLY', 'LATER_BOOT_ESTIMATE', 'CLOCK_UNSTABLE'),
        'confidence': choice('UNKNOWN', 'ESTIMATE_NOT_SESSION_PROOF'),
        'estimated_boot_unix_ms': number, 'sampling_uncertainty_ms': number,
        'uptime_ms': number, 'observed_at': number,
        'clock_history': choice('NOT_VERIFIABLE'), 'source': choice('WALL_CLOCK_MINUS_GETTICKCOUNT64')}


def public_observation(value):
    bounded_tree(value)
    require(type(value.get('members')) is list and len(value['members']) <= 32,
            'LIMIT_EXCEEDED', 'Too many recorded process observations')
    result = project(value, {'source': choice('NOT_REQUESTED', 'CURRENT_WINDOWS_READONLY'),
        'started_at': number, 'finished_at': number, 'owner': PROCESS, 'members': [PROCESS],
        'boot': BOOT, 'lock': choice('NOT_ACQUIRED'), 'scope_handle': choice('NOT_QUERIED')})
    require(result['source'] is not None and result['owner'] and result['owner']['state']
            and result['boot'] and result['boot']['state']
            and all(m and m['state'] for m in result['members']),
            'STORE_UNAVAILABLE', 'Invalid observation projection')
    return result


def _identity(value):
    return (type(value) is dict and number(value.get('pid')) and value['pid'] > 0
            and number(value.get('creation_time_100ns')) and value['creation_time_100ns'] > 0
            and type(value.get('image_path')) is str and 0 < len(value['image_path']) <= 1024
            and Path(value['image_path']).is_absolute())


def _observe_identity(expected):
    if not _identity(expected):
        return {'state': 'IDENTITY_UNRECORDED', 'source': 'NONE', 'observed_at': now()}
    result = {'expected': {'pid': expected['pid'], 'creation_time_100ns': expected['creation_time_100ns'],
                         'image_digest': digest(expected['image_path'])},
              'observed_at': now(), 'source': 'NONE'}
    handle = None
    try:
        from .process_handles import ProcessReference
        handle = ProcessReference(expected['pid'], expected, cleanup=False)
        exit_record = handle.exit_evidence()
        result.update(state='EXACT_IDENTITY_EXITED' if exit_record else 'EXACT_IDENTITY_ALIVE',
                      source='CURRENT_RETAINED_HANDLE')
        if exit_record: result['exit_code'] = exit_record['exit_code']
    except ExecutionError as exc:
        result['state'] = ('IDENTITY_MISMATCH' if exc.code == 'PROCESS_IDENTITY_MISMATCH'
                           else 'PROCESS_UNAVAILABLE' if exc.code == 'PROCESS_IDENTITY_UNKNOWN' else 'QUERY_FAILED')
    except (OSError, ValueError, AttributeError):
        result['state'] = 'QUERY_FAILED'
    finally:
        if handle: handle.close()
    return result


def _owner_identity(context, run):
    """Metadata is only an identity hint; never lock/ownership proof or credential."""
    try:
        path = confined(context.root, Path(context.root) / 'owner.json', exists=True)
        before = path.stat()
        if before.st_size > 16384: return None
        with path.open('rb') as stream: content = stream.read(16385)
        after = path.stat()
        if len(content) > 16384 or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            return None
        data = json.loads(content)
        if (data.get('project_id') != context.project_id or data.get('project_instance_id') != context.project_instance_id
            or data.get('context_digest') != context.context_digest or data.get('owner_id') != run.get('owner_id')
            or data.get('execution_store') != context.execution_store): return None
        return data.get('process') if _identity(data.get('process')) else None
    except (ExecutionError, OSError, ValueError, TypeError, AttributeError):
        return None


def _boot_observation():
    result = {'state': 'QUERY_FAILED', 'confidence': 'UNKNOWN', 'observed_at': now(),
              'clock_history': 'NOT_VERIFIABLE', 'source': 'WALL_CLOCK_MINUS_GETTICKCOUNT64'}
    try:
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.GetTickCount64.argtypes = []
        api.GetTickCount64.restype = ctypes.c_uint64
        start_wall, start_mono = time.time_ns(), time.monotonic_ns()
        uptime = api.GetTickCount64()
        end_wall, end_mono = time.time_ns(), time.monotonic_ns()
        if abs((end_wall-start_wall)-(end_mono-start_mono)) > 100_000_000:
            result['state'] = 'CLOCK_UNSTABLE'
            return result
        result.update(state='ESTIMATE_ONLY', confidence='ESTIMATE_NOT_SESSION_PROOF',
            uptime_ms=uptime, estimated_boot_unix_ms=max(0, end_wall//1_000_000-uptime),
            sampling_uncertainty_ms=1000 + (end_mono-start_mono)//1_000_000)
    except (OSError, AttributeError):
        pass
    return result


def observe(context, run):
    records = run.get('process_records', [])
    require(type(records) is list and len(records) <= 32, 'LIMIT_EXCEEDED', 'Recorded process list exceeds observation bound')
    start, deadline = now(), time.monotonic() + 2
    expected = _owner_identity(context, run)
    owner = _observe_identity(expected)
    members = []
    for i, record in enumerate(records):
        observation = (_observe_identity(record) if time.monotonic() < deadline else
                       {'state': 'BUDGET_EXHAUSTED', 'source': 'NONE', 'observed_at': now()})
        members.append({**observation, 'record_index': i})
    boot = _boot_observation()
    # A sampling envelope is NOT a bound on historical clock adjustments.
    # Require independent owner discontinuity at classification time as well.
    if expected and boot['state'] == 'ESTIMATE_ONLY':
        original_creation_ms = expected['creation_time_100ns']//10000 - 11644473600000
        if original_creation_ms > 0 and boot['estimated_boot_unix_ms'] - boot['sampling_uncertainty_ms'] > original_creation_ms:
            boot['state'] = 'LATER_BOOT_ESTIMATE'
    return public_observation({'source': 'CURRENT_WINDOWS_READONLY', 'started_at': start,
        'finished_at': now(), 'owner': owner, 'members': members, 'boot': boot,
        'lock': 'NOT_ACQUIRED', 'scope_handle': 'NOT_QUERIED'})
