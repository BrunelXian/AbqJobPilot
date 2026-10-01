"""Small shared utilities."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from . import config

_JSON_LOCK = threading.RLock()
_JSON_RETRY_COUNT = 20
_JSON_RETRY_DELAY_SEC = 0.05


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_runtime_dirs() -> None:
    Path(config.RUNTIME_DIR).mkdir(parents=True, exist_ok=True)
    (Path(config.RUNTIME_DIR) / "logs").mkdir(parents=True, exist_ok=True)
    (Path(config.RUNTIME_DIR) / "reports").mkdir(parents=True, exist_ok=True)


def read_json(path: str | Path, default):
    target = Path(path)
    if not target.exists():
        return default
    for _attempt in range(_JSON_RETRY_COUNT):
        try:
            with _JSON_LOCK:
                return json.loads(target.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError, PermissionError):
            time.sleep(_JSON_RETRY_DELAY_SEC)
    return default


def write_json(path: str | Path, data) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    last_error: OSError | None = None
    for _attempt in range(_JSON_RETRY_COUNT):
        tmp = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with _JSON_LOCK:
                with tmp.open("w", encoding="utf-8") as stream:
                    stream.write(text)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(str(tmp), str(target))
                return
        except OSError as exc:
            last_error = exc
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            time.sleep(_JSON_RETRY_DELAY_SEC)
    if last_error:
        raise last_error


def tail_text(path: str | Path, line_count: int = 80) -> str:
    target = Path(path)
    if not target.exists():
        return ""
    try:
        lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-line_count:])


def format_bytes(value: int | None) -> str:
    if value is None:
        return ""
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return str(value)


def open_folder(path: str | Path) -> bool:
    target = Path(path)
    if not target.exists():
        return False
    os.startfile(str(target))
    return True
