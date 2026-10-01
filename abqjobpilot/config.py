"""Application configuration for abqjobpilot."""

from __future__ import annotations

from pathlib import Path

APP_ROOT_PATH = Path(__file__).resolve().parents[1]
RUNTIME_DIR_PATH = APP_ROOT_PATH / "runtime"

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
