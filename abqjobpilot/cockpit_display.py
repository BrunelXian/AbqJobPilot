"""Display-only formatting; raw service states and records remain authoritative."""
from datetime import datetime


def short_identity(value):
    value=str(value)
    return value if len(value)<=25 else value[:12]+'…'+value[-8:]


def short_observed(value):
    try:return datetime.fromisoformat(value).isoformat(sep=' ',timespec='seconds')
    except (ValueError,TypeError):return value


def progress_title(source):
    if source=='fixed_worker_self_report_not_exit_or_validation':return 'workerLog'
    if source=='bounded_standard_text_latest':return 'staSummary'
    return 'progressUnavailable'
