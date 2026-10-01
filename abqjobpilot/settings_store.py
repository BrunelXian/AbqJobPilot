"""Persisted user settings for GUI defaults."""

from __future__ import annotations

from . import config
from .utils import ensure_runtime_dirs, read_json, write_json


DEFAULT_SETTINGS = {
    "abaqus_cmd": config.ABAQUS_CMD,
    "default_cpus": config.DEFAULT_CPUS,
    "use_gpu": False,
    "default_gpus": config.DEFAULT_GPUS,
    "run_datacheck": config.DEFAULT_RUN_DATACHECK,
    "run_full": config.DEFAULT_RUN_FULL,
    "auto_shutdown_enabled": False,
    "auto_shutdown_idle_minutes": 5,
}


def load_settings() -> dict:
    ensure_runtime_dirs()
    data = read_json(config.SETTINGS_FILE, {})
    settings = DEFAULT_SETTINGS.copy()
    if isinstance(data, dict):
        settings.update(data)
    settings["default_cpus"] = max(1, int(settings.get("default_cpus") or config.DEFAULT_CPUS))
    settings["default_gpus"] = max(0, int(settings.get("default_gpus") or 0))
    settings["use_gpu"] = bool(settings.get("use_gpu"))
    settings["run_datacheck"] = bool(settings.get("run_datacheck"))
    settings["run_full"] = bool(settings.get("run_full"))
    settings["auto_shutdown_enabled"] = bool(settings.get("auto_shutdown_enabled"))
    settings["auto_shutdown_idle_minutes"] = max(1, int(settings.get("auto_shutdown_idle_minutes") or 5))
    return settings


def save_settings(settings: dict) -> dict:
    merged = DEFAULT_SETTINGS.copy()
    merged.update(settings)
    merged["default_cpus"] = max(1, int(merged.get("default_cpus") or config.DEFAULT_CPUS))
    merged["default_gpus"] = max(0, int(merged.get("default_gpus") or 0))
    merged["use_gpu"] = bool(merged.get("use_gpu"))
    merged["run_datacheck"] = bool(merged.get("run_datacheck"))
    merged["run_full"] = bool(merged.get("run_full"))
    merged["auto_shutdown_enabled"] = bool(merged.get("auto_shutdown_enabled"))
    merged["auto_shutdown_idle_minutes"] = max(1, int(merged.get("auto_shutdown_idle_minutes") or 5))
    write_json(config.SETTINGS_FILE, merged)
    return merged
