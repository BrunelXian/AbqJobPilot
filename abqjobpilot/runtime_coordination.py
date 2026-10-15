"""Short runtime transactions and OS-backed, single-runner ownership."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import config
from .utils import write_json

try:
    import msvcrt
except ImportError:  # pragma: no cover - exercised on Windows in production
    msvcrt = None
    import fcntl


class CoordinationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


_LOCAL_GUARD = threading.Lock()
_LOCAL_LOCKS: dict[Path, threading.RLock] = {}
_DEPTH = threading.local()


def runtime_path(runtime_dir: str | Path | None = None) -> Path:
    return Path(runtime_dir or config.RUNTIME_DIR).expanduser().resolve()


def _local_lock(runtime: Path) -> threading.RLock:
    with _LOCAL_GUARD:
        return _LOCAL_LOCKS.setdefault(runtime, threading.RLock())


def _try_lock(stream) -> None:
    if msvcrt is not None:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:  # pragma: no cover
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(stream) -> None:
    if msvcrt is not None:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:  # pragma: no cover
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _acquire_file(path: Path, timeout: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                _try_lock(stream)
                return stream
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise CoordinationError("QUEUE_LOCK_TIMEOUT", f"Runtime lock timed out: {path}")
                time.sleep(min(0.025, max(0, deadline - time.monotonic())))
    except BaseException:
        stream.close()
        raise


@contextmanager
def queue_transaction(runtime_dir: str | Path | None = None, *, timeout: float = 5.0):
    """Lock the whole queue read/validate/write sequence across processes."""
    runtime = runtime_path(runtime_dir)
    local = _local_lock(runtime)
    if not local.acquire(timeout=timeout):
        raise CoordinationError("QUEUE_LOCK_TIMEOUT", f"Runtime lock timed out: {runtime}")
    depths = getattr(_DEPTH, "values", None)
    if depths is None:
        depths = _DEPTH.values = {}
    stream = None
    try:
        if depths.get(runtime, 0) == 0:
            stream = _acquire_file(runtime / ".queue.lock", timeout)
        depths[runtime] = depths.get(runtime, 0) + 1
        try:
            yield
        finally:
            depths[runtime] -= 1
            if depths[runtime] == 0:
                del depths[runtime]
                if stream is not None:
                    _unlock(stream)
                    stream.close()
    finally:
        local.release()


def runner_ownership_state(runtime_dir: str | Path | None = None) -> dict:
    """Probe ownership without creating files or trusting PID/metadata alone."""
    runtime = runtime_path(runtime_dir)
    lock_path = runtime / ".runner.lock"
    metadata_path = runtime / "runner_owner.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else None
        if metadata is not None and not isinstance(metadata, dict):
            metadata = None
    except (OSError, ValueError):
        metadata = None
    credible = (isinstance(metadata, dict) and metadata.get("runtime") == str(runtime)
                and isinstance(metadata.get("pid"), int)
                and isinstance(metadata.get("token"), str) and bool(metadata["token"]))
    if not lock_path.exists():
        return {"state": "STALE" if metadata_path.exists() else "ABSENT", "metadata": metadata}
    try:
        with lock_path.open("r+b") as stream:
            try:
                _try_lock(stream)
            except (OSError, BlockingIOError):
                return {"state": "ACTIVE" if credible else "UNCONFIRMED", "metadata": metadata}
            _unlock(stream)
        return {"state": "STALE" if metadata_path.exists() else "ABSENT", "metadata": metadata}
    except OSError:
        return {"state": "UNCONFIRMED", "metadata": metadata}


def _require_no_unconfirmed_run(runtime: Path) -> None:
    """A missing OS owner cannot prove an orphaned solver has stopped."""
    queue_file = runtime / "queue.json"
    live_file = runtime / "live_status.json"
    try:
        if queue_file.exists():
            payload = json.loads(queue_file.read_text(encoding="utf-8-sig"))
            jobs = payload if isinstance(payload, list) else payload.get("jobs")
            if not isinstance(jobs, list) or any(not isinstance(job, dict) for job in jobs):
                raise ValueError("invalid queue records")
            if any(job.get("status") in {"RUNNING", "DATACHECK_RUNNING", "FULL_RUNNING"} for job in jobs):
                raise CoordinationError("RECOVERY_REQUIRED", "Queue contains a running record without a confirmed owner")
        if live_file.exists():
            live = json.loads(live_file.read_text(encoding="utf-8-sig"))
            if not isinstance(live, dict) or not isinstance(live.get("phase"), str):
                raise ValueError("invalid live status")
            if live["phase"] in {"RUNNING", "RUNNER_ACTIVE", "DATACHECK_RUNNING", "FULL_RUNNING"}:
                raise CoordinationError("RECOVERY_REQUIRED", "Live status indicates an unconfirmed prior run")
    except (OSError, ValueError) as exc:
        raise CoordinationError("INVALID_STATUS_DATA", f"Invalid status data: {exc}") from exc


class RunnerOwnership:
    def __init__(self, runtime_dir: str | Path | None = None):
        self.runtime = runtime_path(runtime_dir)
        self.token = uuid.uuid4().hex
        self._stream = None

    def acquire(self) -> dict:
        if self._stream is not None:
            raise CoordinationError("RUNNER_OWNERSHIP_CONFLICT", "Runner already owns this runtime")
        with queue_transaction(self.runtime):
            state = runner_ownership_state(self.runtime)["state"]
            if state == "ACTIVE":
                raise CoordinationError("RUNNER_OWNERSHIP_CONFLICT", "Another runner owns this runtime")
            if state == "UNCONFIRMED":
                raise CoordinationError("RUNNER_OWNERSHIP_UNCONFIRMED", "Runner ownership cannot be confirmed")
            _require_no_unconfirmed_run(self.runtime)
            try:
                stream = _acquire_file(self.runtime / ".runner.lock", 0)
            except CoordinationError as exc:
                raise CoordinationError("RUNNER_OWNERSHIP_CONFLICT", str(exc)) from exc
            metadata = {"runtime": str(self.runtime), "pid": os.getpid(), "token": self.token,
                        "acquired_at": datetime.now().isoformat(timespec="seconds")}
            try:
                write_json(self.runtime / "runner_owner.json", metadata)
            except BaseException:
                _unlock(stream)
                stream.close()
                raise
            self._stream = stream
            return metadata

    def verify(self) -> bool:
        if self._stream is None:
            return False
        try:
            data = json.loads((self.runtime / "runner_owner.json").read_text(encoding="utf-8"))
            return data.get("token") == self.token and data.get("runtime") == str(self.runtime)
        except (OSError, ValueError, AttributeError):
            return False

    def release(self) -> None:
        if self._stream is None:
            return
        try:
            with queue_transaction(self.runtime):
                if self.verify():
                    (self.runtime / "runner_owner.json").unlink(missing_ok=True)
        finally:
            _unlock(self._stream)
            self._stream.close()
            self._stream = None


def require_enqueue_admission(runtime_dir: str | Path | None = None) -> None:
    """Call inside queue_transaction, immediately before queue mutation."""
    state = runner_ownership_state(runtime_dir)["state"]
    if state == "ACTIVE":
        raise CoordinationError("RUNNER_ACTIVE", "Runner is active; enqueue rejected")
    if state == "UNCONFIRMED":
        raise CoordinationError("RUNNER_OWNERSHIP_UNCONFIRMED", "Runner ownership is unconfirmed")
    _require_no_unconfirmed_run(runtime_path(runtime_dir))
