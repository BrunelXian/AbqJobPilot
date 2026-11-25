"""User preferences for the native shell; never stores execution authority."""
from __future__ import annotations

import os
import json
from functools import wraps
import threading
from pathlib import Path
import re
import tempfile
import tomllib

SCHEMA_VERSION = 1
DEFAULTS = {
    "settings_schema_version": SCHEMA_VERSION,
    "setGUIskin": "default",
    "language": "en",
    "appearance": "light",
    "ui_scale": 1.0,
    "restore_window": True,
    "auto_connect_last_project": False,
    "auto_start_owner": False,
    "check_updates": True,
}
_ALLOWED = frozenset(DEFAULTS)
_LANGUAGES = {"en", "zh-CN", "ja-JP", "fr-FR", "de-DE"}
_SAVE_LOCK = threading.RLock()


def _serialized_save(function):
    @wraps(function)
    def save(*args, **kwargs):
        with _SAVE_LOCK:
            return function(*args, **kwargs)
    return save


def user_settings_path() -> Path:
    """Return per-user config storage, outside the install and every Project."""
    root = os.environ.get("APPDATA")
    if not root:
        root = str(Path.home() / "AppData" / "Roaming")
    return Path(root) / "AbqJobPilot" / "settings.toml"


def _validate(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("settings root must be a table")
    unknown = set(value) - _ALLOWED
    if unknown:
        raise ValueError("unknown settings keys: " + ", ".join(sorted(unknown)))
    result = {**DEFAULTS, **value}
    if type(result["settings_schema_version"]) is not int or result["settings_schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported settings_schema_version")
    if not isinstance(result["setGUIskin"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", result["setGUIskin"]):
        raise ValueError("setGUIskin must be a valid skin id")
    if not isinstance(result["language"], str) or result["language"] not in _LANGUAGES:
        raise ValueError("unsupported language")
    if not isinstance(result["appearance"], str) or result["appearance"] not in {"light", "dark"}:
        raise ValueError("appearance must be light or dark")
    scale = result["ui_scale"]
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not 0.75 <= scale <= 1.5:
        raise ValueError("ui_scale must be between 0.75 and 1.5")
    for key in ("restore_window", "auto_connect_last_project", "auto_start_owner", "check_updates"):
        if not isinstance(result[key], bool):
            raise ValueError(f"{key} must be a boolean")
    return result


def load_settings(path: str | Path | None = None) -> dict:
    target = Path(path) if path is not None else user_settings_path()
    if not target.exists():
        return dict(DEFAULTS)
    with target.open("rb") as stream:
        value = tomllib.load(stream)
    value.pop("abaqus_environments", None)
    return _validate(value)


@_serialized_save
def save_settings(value: dict, path: str | Path | None = None) -> dict:
    """Atomically save native UI preferences, preserving the environment section."""
    normalized = _validate(value)
    target = Path(path) if path is not None else user_settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"settings_schema_version = {SCHEMA_VERSION}"]
    for key in ("setGUIskin", "language", "appearance"):
        escaped = normalized[key].replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key} = "{escaped}"')
    lines.append(f"ui_scale = {float(normalized['ui_scale']):.2f}")
    for key in ("restore_window", "auto_connect_last_project", "auto_start_owner", "check_updates"):
        lines.append(f"{key} = {str(normalized[key]).lower()}")
    data = ("\n".join(lines) + "\n").encode("utf-8")
    if target.exists():
        with target.open("rb") as stream:
            environments = tomllib.load(stream).get("abaqus_environments")
        if environments is not None:
            data += _environment_toml(environments)
    _save_bytes(target, data)
    return normalized


def _toml(value):
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False)
    if type(value) is bool:
        return str(value).lower()
    if type(value) is int:
        return str(value)
    if type(value) is float:
        return repr(value)
    if type(value) is list:
        return "[" + ", ".join(_toml(item) for item in value) + "]"
    if type(value) is dict:
        if not all(re.fullmatch(r"[a-zA-Z0-9_]+", key) for key in value):
            raise ValueError("Invalid environment setting key")
        return "{ " + ", ".join(key + " = " + _toml(item) for key, item in value.items()) + " }"
    raise ValueError("Unsupported environment setting value")


def _environment_toml(value):
    if not isinstance(value, dict) or not all(re.fullmatch(r"[a-zA-Z0-9_]+", key) for key in value):
        raise ValueError("Invalid environment settings section")
    return ("\n[abaqus_environments]\n" + "\n".join(
        key + " = " + _toml(item) for key, item in value.items()) + "\n").encode("utf-8")


def load_environment_settings(path=None):
    target = Path(path) if path is not None else user_settings_path()
    if not target.exists():
        return None
    with target.open("rb") as stream:
        value = tomllib.load(stream).get("abaqus_environments")
    if value is not None and not isinstance(value, dict):
        raise ValueError("Invalid environment settings section")
    if value is not None and value.get("default_id") == "":
        value["default_id"] = None
    return value


@_serialized_save
def save_environment_settings(value, path=None):
    target = Path(path) if path is not None else user_settings_path()
    normalized = load_settings(target)
    # Preserve UI settings through the same writer and atomic publication path.
    lines = [key + " = " + _toml(item) for key, item in normalized.items()]
    storage = {**value, "default_id": value["default_id"] or ""}
    target.parent.mkdir(parents=True, exist_ok=True)
    _save_bytes(target, ("\n".join(lines) + "\n").encode("utf-8") + _environment_toml(storage))


def _save_bytes(target, data):
    fd, name = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        Path(name).replace(target)
    finally:
        Path(name).unlink(missing_ok=True)
