"""Persisted user settings for GUI defaults."""

from __future__ import annotations

import json
from pathlib import Path

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
    return _merged_settings(data)


def load_settings_for_runtime(runtime_dir: str | Path) -> dict:
    """Return effective defaults, not proof of persistence. See inspect_settings_for_runtime."""
    return _merged_settings(read_json(Path(runtime_dir) / "settings.json", {}))


def _validate_stored_settings(data) -> None:
    if not isinstance(data, dict):
        raise ValueError("settings.json must contain an object")
    for key, default in DEFAULT_SETTINGS.items():
        if key not in data:
            continue  # Older settings files may omit newer options.
        value = data[key]
        if type(value) is not type(default):
            raise ValueError(f"Invalid type for {key}")
        if isinstance(default, int) and not isinstance(default, bool):
            minimum = 0 if key == "default_gpus" else 1
            if value < minimum:
                raise ValueError(f"{key} must be >= {minimum}")
        if key == "abaqus_cmd" and not value.strip():
            raise ValueError("abaqus_cmd must not be empty")


def inspect_settings_for_runtime(runtime_dir: str | Path) -> dict:
    """Inspect actual disk data without creating files or disguising defaults as saved values."""
    runtime = Path(runtime_dir).expanduser().resolve()
    path = runtime / "settings.json"
    result = {"runtime_dir": str(runtime), "settings_file": str(path),
              "status": "NOT_PERSISTED", "persisted": False, "exists": False,
              "settings": None, "effective_settings": None, "defaulted_fields": [], "errors": []}
    try:
        if path.resolve() != path:
            result.update(status="SETTINGS_PATH_MISMATCH", errors=[f"Settings path redirects outside its runtime: {path}"])
            return result
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        result.update(exists=True, settings=data)
        _validate_stored_settings(data)
        result.update(status="PERSISTED", persisted=True, effective_settings=_merged_settings(data),
                      defaulted_fields=[key for key in DEFAULT_SETTINGS if key not in data])
    except FileNotFoundError:
        result.update(effective_settings=DEFAULT_SETTINGS.copy(), defaulted_fields=list(DEFAULT_SETTINGS))
    except (ValueError, UnicodeError) as exc:
        result.update(status="INVALID_SETTINGS", exists=True, errors=[str(exc)])
    except OSError as exc:
        result.update(status="SETTINGS_READ_FAILED", exists=None, errors=[str(exc)])
    return result


def _merged_settings(data) -> dict:
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


def save_settings(settings: dict, *, runtime_dir: str | Path | None = None) -> dict:
    """Write to a captured runtime, then verify the actual file rather than defaulted values."""
    runtime = Path(runtime_dir if runtime_dir is not None else Path(config.SETTINGS_FILE).parent).expanduser().resolve()
    path = runtime / "settings.json"
    if path.resolve() != path:
        raise OSError(f"Settings path mismatch: {path}")
    merged = _merged_settings(settings)
    _validate_stored_settings(merged)
    write_json(path, merged)
    actual = inspect_settings_for_runtime(runtime)
    if (actual["settings_file"] != str(path) or not actual["persisted"]
            or actual["settings"] != merged):
        raise OSError(f"Settings persistence verification failed at {path}: {actual['status']}; {actual['errors']}")
    return merged
