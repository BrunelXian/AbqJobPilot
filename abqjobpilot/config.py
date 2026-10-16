"""Application configuration for abqjobpilot."""

from __future__ import annotations

from pathlib import Path
import hashlib

APP_ROOT_PATH = Path(__file__).resolve().parents[1]


def default_runtime_path() -> Path:
    legacy = APP_ROOT_PATH / "runtime"
    if any((legacy / name).is_file() for name in ("queue.json", "live_status.json", "settings.json")):
        return legacy
    for folder in ("reports", "logs"):
        if (legacy / folder).is_dir() and any(child.is_file() and child.name != ".gitkeep" for child in (legacy / folder).iterdir()):
            return legacy
    installation = hashlib.sha256(str(APP_ROOT_PATH).casefold().encode("utf-8")).hexdigest()[:12]
    return Path.home() / ".abqjobpilot" / "installations" / installation / "runtime"


RUNTIME_DIR_PATH = default_runtime_path()

ABAQUS_CMD = r"D:\ABAQUS2024\Commands\abq2024.bat"
DEFAULT_CPUS = 14
DEFAULT_GPUS = 0
DEFAULT_RUN_DATACHECK = True
DEFAULT_RUN_FULL = True
APP_ROOT = str(APP_ROOT_PATH)
RUNTIME_DIR = str(RUNTIME_DIR_PATH)
QUEUE_FILE = str(RUNTIME_DIR_PATH / "queue.json")
LIVE_STATUS_FILE = str(RUNTIME_DIR_PATH / "live_status.json")
SETTINGS_FILE = str(RUNTIME_DIR_PATH / "settings.json")
APP_ICON_FILE = str(APP_ROOT_PATH / "abqjobpilot.ico")
POLL_INTERVAL_SECONDS = 2
SCHEMA_VERSION = "1.0"

STATUS_VALUES = (
    "QUEUED",
    "DATACHECK_RUNNING",
    "DATACHECK_OK",
    "DATACHECK_FAILED",
    "DATACHECK_FAILED_INVALID_GPU_OPTION",
    "FULL_RUNNING",
    "COMPLETED_OK",
    "COMPLETED_WITH_WARNINGS",
    "FAILED_FATAL",
    "FAILED_NUMERICAL",
    "FAILED_INPUT",
    "FAILED_LICENSE",
    "SKIPPED",
    "CANCELLED",
    "UNKNOWN_INTERRUPTED",
)

ACTIVE_STATUSES = {
    "QUEUED",
    "DATACHECK_RUNNING",
    "DATACHECK_OK",
    "FULL_RUNNING",
}

RESULT_STATUSES = set(STATUS_VALUES) - ACTIVE_STATUSES


def use_runtime_dir(runtime_dir: str | Path | None = None) -> None:
    """Select the GUI process's runtime; None restores the legacy default."""
    global RUNTIME_DIR, QUEUE_FILE, LIVE_STATUS_FILE, SETTINGS_FILE
    runtime = Path(runtime_dir).expanduser().resolve() if runtime_dir is not None else RUNTIME_DIR_PATH
    RUNTIME_DIR = str(runtime)
    QUEUE_FILE = str(runtime / "queue.json")
    LIVE_STATUS_FILE = str(runtime / "live_status.json")
    SETTINGS_FILE = str(runtime / "settings.json")
