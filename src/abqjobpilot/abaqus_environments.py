"""Static local Abaqus discovery and user configuration. Never executes an entry."""
import ctypes
import json
import os
from pathlib import Path
import re
import tempfile

from .execution.models import Document, ExecutionError, bytes_digest, digest, now, require
from .execution.paths import local_path, no_reparse
from .gui_settings import user_settings_path, load_environment_settings, save_environment_settings

SCHEMA = "abaqus-environments/1.0"
BINDING_SCHEMA = "abaqus-environment-binding/1.0"
MAX_BYTES = 262144
ENTRY_NAME = re.compile(r"(?:abaqus|abq20\d\d[^\\/]*)\.bat", re.I)


def _read(path):
    no_reparse(path)
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "LIMIT_EXCEEDED", "Environment configuration exceeds its bound")
    return json.loads(data)


def _write(path, value):
    no_reparse(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    require(len(data) <= MAX_BYTES, "LIMIT_EXCEEDED", "Environment configuration exceeds its bound")
    fd, temporary = tempfile.mkstemp(prefix=".abaqus-environments-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _file(path, maximum=MAX_BYTES):
    from .abaqus_preview.inputs import _open_pinned
    path = local_path(path)
    no_reparse(path)
    with _open_pinned(path) as stream:
        before = os.fstat(stream.fileno())
        require(0 < before.st_size <= maximum, "LIMIT_EXCEEDED", "Installation material size is unsupported")
        data = stream.read(maximum + 1)
        after = path.stat()
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        require(identity == (after.st_dev, after.st_ino, len(data), after.st_mtime_ns),
                "ENVIRONMENT_CHANGED", "Installation material changed while reading")
    return {"path": str(path), "device": before.st_dev, "file_id": before.st_ino,
            "size": len(data), "mtime_ns": before.st_mtime_ns, "sha256": bytes_digest(data)}, data


def inspect_entry(value):
    """Pin BAT and directly named literal local launcher dependencies, without executing."""
    path = local_path(value)
    require(path.suffix.lower() == ".bat", "INVALID_ENVIRONMENT", "Select an Abaqus BAT entry")
    entry, raw = _file(path)
    text = raw.decode("utf-8-sig", errors="replace")
    materials = [entry]
    # Follow a literal, same-directory versioned alias such as abaqus.bat -> abq2024.bat.
    alias = re.search(r'(?i)(?:call\s+)?(?:"%~dp0)?(abq20\d\d[^"\s/\\]*\.bat)"?', text)
    if alias and alias.group(1).lower() != path.name.lower():
        target = path.parent / alias.group(1)
        if target.is_file():
            entry, raw = _file(target)
            path = target
            text = raw.decode("utf-8-sig", errors="replace")
            materials = [entry]
    require(ENTRY_NAME.fullmatch(path.name) is not None or "smalauncher.exe" in text.lower(),
            "INVALID_ENVIRONMENT", "BAT does not identify an Abaqus launcher")
    for literal in re.findall(r'"([^"\r\n]+\.(?:exe|bat|cmd))"', text, re.I)[:8]:
        target = Path(literal)
        if target.is_absolute() and not str(target).startswith(("\\\\", "//")) and target != path:
            material, _ = _file(target, 32 * 1024 * 1024)
            if material not in materials:
                materials.append(material)
    match = re.search(r"(?i)(?:abq|abaqus)[-_ ]?(20\d\d)", path.name + " " + str(path.parent) + " " + text)
    return {"entry": str(path), "version": match.group(1) if match else "UNKNOWN",
            "materials": materials, "validation_scope": "STATIC_LITERAL_FILES_ONLY",
            "solver": "NOT_RUN", "abaqus_python": "NOT_RUN", "license": "NOT_CHECKED"}


def _fixed_drives():
    if os.name != "nt":
        return []
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    mask = api.GetLogicalDrives()
    return [Path(chr(65 + index) + ":\\") for index in range(26)
            if mask & (1 << index) and api.GetDriveTypeW(ctypes.c_wchar_p(chr(65 + index) + ":\\")) == 3]


def _registry_locations():
    if os.name != "nt":
        return []
    import winreg
    found = []
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                               0, winreg.KEY_READ | view) as root:
                for index in range(min(winreg.QueryInfoKey(root)[0], 512)):
                    try:
                        with winreg.OpenKey(root, winreg.EnumKey(root, index)) as key:
                            name = winreg.QueryValueEx(key, "DisplayName")[0]
                            if isinstance(name, str) and re.search(r"Abaqus|SIMULIA", name, re.I):
                                location = winreg.QueryValueEx(key, "InstallLocation")[0]
                                if isinstance(location, str) and location:
                                    found.append(Path(location))
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def discover(*, path_value=None, drive_roots=None, registry_locations=None):
    """Bounded PATH and known directory search. No recursive walk or subprocess."""
    candidates = []
    path_value = os.environ.get("PATH", "") if path_value is None else path_value
    candidates.extend(Path(item.strip('"')) for item in path_value.split(os.pathsep)[:64] if item)
    drives = _fixed_drives() if drive_roots is None else drive_roots
    for drive in drives:
        drive = Path(drive)
        candidates.extend([drive / "SIMULIA/Commands", drive / "SIMULIA/Abaqus/Commands"])
        try:
            names = sorted(drive.iterdir(), key=lambda p: p.name.lower())[:256]
            roots = [p for p in names if re.fullmatch(r"(?:ABAQUS|SIMULIA)[-_ ]?(?:20\d\d)?", p.name, re.I)]
        except OSError:
            roots = []
        for vendor in (drive / "Program Files/SIMULIA", drive / "Program Files/Dassault Systemes"):
            roots.append(vendor)
        for root in roots:
            candidates.append(root / "Commands")
            try:
                for child in sorted(root.iterdir(), key=lambda p: p.name.lower())[:32]:
                    if re.search(r"(?:20\d\d|Abaqus|SIMULIA)", child.name, re.I):
                        candidates.extend([child / "Commands", child / "Abaqus/Commands"])
            except OSError:
                continue
    locations = _registry_locations() if registry_locations is None else registry_locations
    for location in locations[:32]:
        candidates.extend([Path(location), Path(location) / "Commands", Path(location).parent / "Commands"])
    unique = {}
    visited = set()
    for directory in candidates[:512]:
        if not directory.is_absolute() or str(directory).startswith(("\\\\", "//")) or directory in visited:
            continue
        visited.add(directory)
        if os.name == "nt" and ctypes.WinDLL("kernel32").GetDriveTypeW(ctypes.c_wchar_p(directory.anchor)) != 3:
            continue
        try:
            no_reparse(directory)
            for path in sorted(directory.glob("*.bat"))[:64]:
                if not ENTRY_NAME.fullmatch(path.name):
                    continue
                try:
                    item = inspect_entry(path)
                    key = tuple((m["device"], m["file_id"]) for m in item["materials"])
                    unique.setdefault(key, item)
                except (ExecutionError, OSError, ValueError):
                    continue
        except (ExecutionError, OSError):
            continue
    return list(unique.values())[:64]


class EnvironmentBinding(Document):
    """Immutable static material snapshot for a future Plan adapter."""


class EnvironmentManager:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else user_settings_path()
        self.unsaved = False
        self.data = {"schema": SCHEMA, "default_id": None, "environments": [], "detected": False}
        value = load_environment_settings(self.path)
        if value is not None:
            require(isinstance(value, dict) and value.get("schema") == SCHEMA
                    and isinstance(value.get("environments"), list) and len(value["environments"]) <= 64,
                    "INVALID_ENVIRONMENT_CONFIG", "Unsupported environment configuration")
            identifiers = []
            for item in value["environments"]:
                require(isinstance(item, dict) and isinstance(item.get("id"), str)
                        and isinstance(item.get("entry"), str) and isinstance(item.get("snapshot"), dict)
                        and isinstance(item.get("configured"), bool)
                        and isinstance(item.get("version"), str) and isinstance(item.get("error"), str)
                        and type(item.get("checked_at")) is int
                        and item.get("validation") in ("NOT_CHECKED", "VALIDATED", "UNAVAILABLE"),
                        "INVALID_ENVIRONMENT_CONFIG", "Malformed environment entry")
                identifiers.append(item["id"])
            require(len(set(identifiers)) == len(identifiers) and value.get("default_id") in (None, *identifiers),
                    "INVALID_ENVIRONMENT_CONFIG", "Invalid default environment")
            self.data = value

    def save(self):
        self.unsaved = True
        save_environment_settings(self.data, self.path)
        self.unsaved = False

    def add(self, path, *, replace_id=None, configured=True):
        snapshot = inspect_entry(path)
        existing = next((item for item in self.data["environments"]
                         if os.path.normcase(item["entry"]) == os.path.normcase(snapshot["entry"])
                         and item["id"] != replace_id), None)
        if existing:
            require(replace_id is None, "ENVIRONMENT_ALREADY_EXISTS", "That BAT entry is already configured")
            if configured and not existing["configured"]:
                existing["configured"] = True
                self.save()
            return existing
        require(len(self.data["environments"]) < 64 or replace_id is not None,
                "LIMIT_EXCEEDED", "At most 64 environments")
        identifier = replace_id or "env_" + digest(snapshot["entry"].casefold())[7:31]
        item = {"id": identifier, "entry": snapshot["entry"], "version": snapshot["version"],
                "configured": configured, "snapshot": snapshot, "checked_at": now(),
                "validation": "NOT_CHECKED", "error": ""}
        if replace_id:
            require(any(e["id"] == replace_id for e in self.data["environments"]),
                    "NOT_FOUND", "Selected environment no longer exists")
            self.data["environments"] = [item if e["id"] == replace_id else e for e in self.data["environments"]]
        else:
            self.data["environments"].append(item)
        self.save()
        return item

    def auto_detect(self):
        for found in discover():
            self.add(found["entry"], configured=False)
        for item in self.data["environments"]:
            if item["configured"]:
                self.validate(item["id"])
        self.data["detected"] = True
        self.save()

    def remove(self, identifier):
        self.data["environments"] = [e for e in self.data["environments"] if e["id"] != identifier]
        if self.data["default_id"] == identifier:
            self.data["default_id"] = None
        self.save()

    def set_default(self, identifier):
        item = self.get(identifier)
        item["configured"] = True
        self.data["default_id"] = identifier
        self.save()

    def get(self, identifier):
        item = next((e for e in self.data["environments"] if e["id"] == identifier), None)
        require(item is not None, "ENVIRONMENT_UNAVAILABLE", "Select an installed Abaqus environment")
        return item

    def validate(self, identifier):
        item = self.get(identifier)
        try:
            current = inspect_entry(item["entry"])
            require(current == item["snapshot"], "ENVIRONMENT_CHANGED", "Installation identity or bytes changed")
            item.update(validation="VALIDATED", error="")
        except (ExecutionError, OSError, ValueError) as exc:
            item.update(validation="UNAVAILABLE", error=getattr(exc, "code", "PATH_UNAVAILABLE"))
        item["checked_at"] = now()
        self.save()
        return item

    def project_choice(self, project):
        from .product_project import open_project
        root = Path(project)
        manifest = open_project(root)
        path = root / "abaqus-environment.json"
        if not path.exists():
            return None
        value = _read(path)
        require(value.get("schema") == SCHEMA and all(value.get(k) == manifest[k] for k in
                ("project_id", "project_instance_id", "context_digest")),
                "PROJECT_IDENTITY_MISMATCH", "Environment selection belongs to another Project")
        return value["environment_id"]

    def select_for_project(self, project, identifier):
        from .product_project import open_project
        root = Path(project)
        manifest = open_project(root)
        if identifier is not None:
            self.get(identifier)["configured"] = True
            self.save()
        _write(root / "abaqus-environment.json", {"schema": SCHEMA, "environment_id": identifier,
               **{k: manifest[k] for k in ("project_id", "project_instance_id", "context_digest")}})

    def freeze(self, project=None):
        require(not self.unsaved, "UNSAVED_SETTINGS", "Reload the saved environment configuration")
        identifier = self.project_choice(project) if project is not None else None
        project_binding = None
        if project is not None:
            from .product_project import open_project
            manifest = open_project(project)
            project_binding = {key: manifest[key] for key in ("project_id", "project_instance_id", "context_digest")}
        item = self.get(identifier or self.data["default_id"])
        current = inspect_entry(item["entry"])
        require(current == item["snapshot"], "ENVIRONMENT_CHANGED", "Reconfigure environment and generate a new Plan")
        body = {"schema": BINDING_SCHEMA, "environment_id": item["id"], "snapshot": current,
                "project": project_binding,
                "selection": "PROJECT" if identifier else "GLOBAL_DEFAULT",
                "execution_authorized": False, "real_plan_adapter": "UNAVAILABLE"}
        return EnvironmentBinding.from_dict({**body, "binding_digest": digest(body)})


def verify_binding(binding):
    require(type(binding) is EnvironmentBinding, "INVALID_ENVIRONMENT", "An immutable environment binding is required")
    value = binding.to_dict()
    body = {k: v for k, v in value.items() if k != "binding_digest"}
    require(value["schema"] == BINDING_SCHEMA and value["binding_digest"] == digest(body)
            and value["execution_authorized"] is False and value["real_plan_adapter"] == "UNAVAILABLE",
            "INVALID_ENVIRONMENT", "Environment binding differs")
    require(inspect_entry(value["snapshot"]["entry"]) == value["snapshot"],
            "ENVIRONMENT_CHANGED", "Frozen environment drifted; generate a new Plan")
    return value
