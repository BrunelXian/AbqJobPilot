"""Bounded read-only fixed-fixture log projection. No arbitrary file API."""
import json
import os
import stat

from .models import ExecutionError, fields, integer, now, require, text
from .paths import confined
from .process_contract import BACKEND, directory

MAX_BYTES, MAX_RECORDS, PAGE = 65536, 128, 64
EVENTS = {'WORKER_READY', 'WAITING', 'RESULT_WRITTEN', 'WORKER_RETURNING'}


def read_progress(store, context, run_id, after_sequence=0, limit=64):
    text(run_id); integer(after_sequence); integer(limit, 1)
    require(limit <= PAGE, 'LIMIT_EXCEEDED', 'Progress page bound exceeded')
    run = store.query_run(context, run_id)
    if run['backend_id'] == 'abaqus-standard-axial-2024-v1':
        from .standard_backend import progress
        return progress(store,context,run_id,after_sequence,limit)
    require(run['backend_id'] == BACKEND, 'UNSUPPORTED_EVIDENCE_POLICY', 'Only fixed process progress is supported')
    path = confined(context.test_root, directory(context, run) / 'progress.jsonl')
    envelope = {'run_id': run_id, 'phase_attempt_id': run['phase_attempt_id'],
                'project_instance_id': context.project_instance_id, 'read_at': now(),
                'source': 'fixed_worker_self_report_not_exit_or_validation', 'records': [],
                'next_sequence': after_sequence, 'has_more': False, 'complete_line_count': 0}
    try:
        with path.open('rb') as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES, 'LIMIT_EXCEEDED', 'Progress bytes exceeded')
            raw = stream.read(before.st_size)
        after = confined(context.test_root, path, exists=True).stat()
        require((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino) and
                after.st_size >= before.st_size and len(raw) == before.st_size,
                'EVIDENCE_CHANGED', 'Progress identity changed or shrank')
    except FileNotFoundError:
        return {**envelope, 'status': 'NOT_RECORDED'}
    except OSError as exc:
        raise ExecutionError('EVIDENCE_UNAVAILABLE', 'Fixed progress cannot be read') from exc
    # Writer may be between append and newline; only complete prefix is visible.
    raw = raw[:raw.rfind(b'\n')+1]
    lines = raw.splitlines()
    require(len(lines) <= MAX_RECORDS, 'LIMIT_EXCEEDED', 'Progress record bound exceeded')
    binding = {'run_id': run_id, 'project_instance_id': context.project_instance_id,
               'phase_attempt_id': run['phase_attempt_id'], 'plan_digest': run['plan_digest']}
    rows = []
    try:
        for i, line in enumerate(lines, 1):
            require(len(line) <= 1024, 'LIMIT_EXCEEDED', 'Progress field bound exceeded')
            row = json.loads(line.decode('utf-8'))
            fields(row, (*binding, 'sequence', 'event', 'observed_at'))
            integer(row['sequence'], 1)
            require(all(row[k] == v for k, v in binding.items()) and row['sequence'] == i,
                    'EVIDENCE_IDENTITY_MISMATCH', 'Progress binding or sequence differs')
            require(row['event'] in EVENTS, 'INVALID_REQUEST', 'Unsupported fixed progress message')
            integer(row['observed_at'])
            rows.append({k: row[k] for k in ('sequence','event','observed_at')})
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise ExecutionError('EVIDENCE_FORMAT_UNSUPPORTED', 'Progress format rejected') from exc
    require(after_sequence <= len(rows), 'CURSOR_INVALID', 'Progress cursor exceeds recorded prefix')
    selected = rows[after_sequence:after_sequence+limit]
    next_sequence = selected[-1]['sequence'] if selected else after_sequence
    return {**envelope, 'status': 'RECORDED_PREFIX', 'records': selected,
            'next_sequence': next_sequence, 'has_more': next_sequence < len(rows), 'complete_line_count': len(rows)}
