"""Application configuration for abqjobpilot."""

from __future__ import annotations

ABAQUS_CMD = r"D:\ABAQUS2024\Commands\abq2024.bat"
DEFAULT_CPUS = 14
DEFAULT_GPUS = 0
DEFAULT_RUN_DATACHECK = True
DEFAULT_RUN_FULL = True
APP_ROOT = r"D:\Projects\abqjobpilot"
RUNTIME_DIR = r"D:\Projects\abqjobpilot\runtime"
QUEUE_FILE = r"D:\Projects\abqjobpilot\runtime\queue.json"
LIVE_STATUS_FILE = r"D:\Projects\abqjobpilot\runtime\live_status.json"
SETTINGS_FILE = r"D:\Projects\abqjobpilot\runtime\settings.json"
APP_ICON_FILE = r"D:\Projects\abqjobpilot\abqjobpilot.ico"
POLL_INTERVAL_SECONDS = 2

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
