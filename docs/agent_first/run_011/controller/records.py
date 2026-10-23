"""Bounded local experiment records; no database, discovery, repair or deletion."""
import hashlib
import json
import os
from pathlib import Path
import stat
import time


class Refusal(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise Refusal(code)


def stamp():
    return time.time_ns()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return 'sha256:' + hashlib.sha256(canonical(value)).hexdigest()


def safe_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts
            and not str(path).startswith(('\\\\', '//'))
            and all(':' not in p for p in path.parts[1:]), 'UNSUPPORTED_PATH')
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and
                not getattr(info, 'st_file_attributes', 0) & 0x400, 'UNSUPPORTED_PATH')
    return path


def stable_read(path, limit=16 * 1024 * 1024):
    path = safe_path(path)
    with path.open('rb') as stream:
        a = os.fstat(stream.fileno())
        require(stat.S_ISREG(a.st_mode) and a.st_size <= limit, 'READ_LIMIT_OR_TYPE')
        data = stream.read(limit + 1)
        stream.seek(0)
        require(data == stream.read(limit + 1), 'UNSTABLE_READ')
    b = safe_path(path).stat()
    require((a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns) ==
            (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns)
            and len(data) <= limit, 'UNSTABLE_READ')
    return data, {'device': a.st_dev, 'inode': a.st_ino, 'bytes': len(data),
                  'mtime_ns': a.st_mtime_ns, 'ctime_ns': a.st_ctime_ns,
                  'sha256': hashlib.sha256(data).hexdigest()}


def read_json(path):
    return json.loads(stable_read(path, 1024 * 1024)[0])


def write_new(path, value):
    """O_EXCL + complete write + fsync. Any residue blocks, including empty files."""
    path = safe_path(path)
    payload = canonical(value) + b'\n'
    require(len(payload) <= 1024 * 1024, 'RECORD_LIMIT')
    try:
        with path.open('xb', buffering=0) as stream:
            require(stream.write(payload) == len(payload), 'SHORT_WRITE')
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise Refusal('ATTEMPT_OR_RECORD_EXISTS') from exc


class Journal:
    def __init__(self, path):
        self.stream = safe_path(path).open('xb', buffering=0)
        self.sequence = 0

    def append(self, kind, **data):
        self.sequence += 1
        payload = canonical({'sequence': self.sequence, 'observed_at_ns': stamp(),
                             'kind': kind, **data}) + b'\n'
        require(len(payload) <= 65536 and self.sequence <= 20000, 'JOURNAL_LIMIT')
        require(self.stream.write(payload) == len(payload), 'SHORT_WRITE')
        os.fsync(self.stream.fileno())

    def close(self):
        self.stream.close()
