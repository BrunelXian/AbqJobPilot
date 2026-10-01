"""Explicit, portable Project ZIP export and guarded import."""

from __future__ import annotations

import json
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from abqjobpilot.utils import now_iso

from .manager import load_project_info
from .models import ProjectInfo


ARCHIVE_SCHEMA_VERSION = "1.0"
PROJECT_PATH_PREFIX = "project://"
PATH_FIELDS = frozenset({
    "inp_path", "work_dir", "working_dir", "odb_path", "sta_path",
    "msg_path", "dat_path", "log_path", "lck_path", "report_path",
})


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _portable_json(value, root: Path, references: list[dict]):
    if isinstance(value, list):
        return [_portable_json(item, root, references) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in PATH_FIELDS and isinstance(item, str) and item:
            if item.startswith(PROJECT_PATH_PREFIX):
                raise ValueError(f"Source metadata already contains a reserved project path: {item}")
            candidate = Path(item)
            candidate = (candidate if candidate.is_absolute() else root / candidate).resolve()
            if _within(candidate, root):
                relative = candidate.relative_to(root).as_posix()
                result[key] = PROJECT_PATH_PREFIX + relative
                kind = "project_owned" if candidate.exists() else "missing"
            else:
                result[key] = item
                kind = "external_reference" if candidate.exists() else "missing"
            references.append({"field": key, "kind": kind, "value": result[key]})
        elif key == "import_provenance" and isinstance(item, dict):
            provenance = dict(item)
            if provenance.get("source_path"):
                provenance["source_path"] = None
                provenance["source_path_redacted"] = True
            result[key] = provenance
        else:
            result[key] = _portable_json(item, root, references)
    return result


def _restore_json(value, root: Path):
    if isinstance(value, list):
        return [_restore_json(item, root) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in PATH_FIELDS and isinstance(item, str) and item.startswith(PROJECT_PATH_PREFIX):
            relative = item[len(PROJECT_PATH_PREFIX):]
            if not relative or "\\" in relative or PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts:
                raise ValueError(f"Invalid portable project path: {item}")
            resolved = (root / Path(*PurePosixPath(relative).parts)).resolve()
            if not _within(resolved, root):
                raise ValueError(f"Project path escapes destination: {item}")
            result[key] = str(resolved)
        else:
            result[key] = _restore_json(item, root)
    return result


def _is_metadata(relative: Path) -> bool:
    return relative.as_posix() in {"project.json", "project.db"} or (
        relative.parts and relative.parts[0] == "runtime" and relative.suffix.lower() == ".json"
    )


def export_project_archive(project_root: str | Path, archive_path: str | Path, mode: str = "metadata") -> Path:
    if mode not in {"metadata", "full"}:
        raise ValueError("Export mode must be 'metadata' or 'full'")
    project = load_project_info(project_root)
    root = project.root.resolve()
    destination = Path(archive_path).expanduser().resolve()
    if _within(destination, root):
        raise ValueError("Archive destination must be outside the Project root")
    if destination.exists():
        raise FileExistsError(f"Archive destination already exists: {destination}")
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"Archive parent directory does not exist: {destination.parent}")
    files = []
    for path in root.rglob("*"):
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if _within(parent, root)):
            continue
        if path.is_file():
            relative = path.relative_to(root)
            if relative.as_posix() in {"project.db-wal", "project.db-shm", "project.db-journal"}:
                continue
            if mode == "full" or _is_metadata(relative):
                files.append((path, relative))
    references: list[dict] = []
    manifest = {
        "archive_schema_version": ARCHIVE_SCHEMA_VERSION,
        "application": "abqjobpilot",
        "project_id": project.project_id,
        "mode": mode,
        "created_at": now_iso(),
        "files": ["project/" + relative.as_posix() for _, relative in sorted(files, key=lambda pair: pair[1].as_posix())],
        "path_references": references,
    }
    with destination.open("xb") as stream:
        try:
            with tempfile.TemporaryDirectory(prefix="abqjobpilot-db-backup-") as temporary:
                with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                    for directory in ("project/runtime/", "project/runtime/reports/"):
                        archive.writestr(directory, "")
                    for path, relative in sorted(files, key=lambda pair: pair[1].as_posix()):
                        name = "project/" + relative.as_posix()
                        if relative.as_posix() == "project.db":
                            from abqjobpilot.database.connection import backup_database
                            from abqjobpilot.database.portability import portabilize_database_snapshot
                            snapshot = backup_database(path, Path(temporary) / "project.db")
                            portabilize_database_snapshot(snapshot, root)
                            archive.write(snapshot, name)
                        elif _is_metadata(relative):
                            data = json.loads(path.read_text(encoding="utf-8-sig"))
                            portable = _portable_json(data, root, references)
                            archive.writestr(name, json.dumps(portable, ensure_ascii=False, indent=2))
                        else:
                            archive.write(path, name)
                    archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        except BaseException:
            stream.close()
            destination.unlink(missing_ok=True)
            raise
    return destination


def _validated_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members = {}
    for info in archive.infolist():
        name = info.filename
        path = PurePosixPath(name)
        if (not name or "\\" in name or name.startswith("/") or ":" in name
                or ".." in path.parts or path.as_posix() != name.rstrip("/")
                or name not in {"manifest.json"} and path.parts[0] != "project"):
            raise ValueError(f"Unsafe archive member: {name}")
        if len(path.parts) < 2 and name != "manifest.json":
            raise ValueError(f"Unexpected archive member: {name}")
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError(f"Archive symlink is not allowed: {name}")
        member_type = stat.S_IFMT(info.external_attr >> 16)
        if member_type not in {0, stat.S_IFDIR, stat.S_IFREG}:
            raise ValueError(f"Unsupported archive member type: {name}")
        if name in members:
            raise ValueError(f"Duplicate archive member: {name}")
        members[name] = info
    return members


def import_project_archive(archive_path: str | Path, destination_root: str | Path,
                           *, preserve_project_id: bool = True) -> ProjectInfo:
    source = Path(archive_path).expanduser().resolve()
    destination = Path(destination_root).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Project destination already exists: {destination}")
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"Destination parent directory does not exist: {destination.parent}")
    with zipfile.ZipFile(source, "r") as archive:
        members = _validated_members(archive)
        if "manifest.json" not in members or "project/project.json" not in members:
            raise ValueError("Archive manifest or project.json is missing")
        manifest = json.loads(archive.read("manifest.json"))
        if (not isinstance(manifest, dict) or manifest.get("archive_schema_version") != ARCHIVE_SCHEMA_VERSION
                or manifest.get("application") != "abqjobpilot" or manifest.get("mode") not in {"metadata", "full"}
                or not isinstance(manifest.get("files"), list)
                or not all(isinstance(item, str) for item in manifest["files"])):
            raise ValueError("Unsupported archive manifest")
        actual = {name for name, info in members.items() if not info.is_dir() and name != "manifest.json"}
        if actual != set(manifest["files"]) or len(actual) != len(manifest["files"]):
            raise ValueError("Archive files do not match manifest")
        with tempfile.TemporaryDirectory(prefix=".abqjobpilot-import-", dir=destination.parent) as temporary:
            staged = Path(temporary) / "project"
            staged.mkdir()
            for name, info in members.items():
                if name == "manifest.json":
                    continue
                relative = PurePosixPath(name).relative_to("project")
                target = staged.joinpath(*relative.parts)
                if not _within(target.resolve(), staged.resolve()):
                    raise ValueError(f"Archive member escapes destination: {name}")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if _is_metadata(Path(*relative.parts)) and name != "project/project.db":
                        data = json.loads(archive.read(info))
                        data = _restore_json(data, destination)
                        if name == "project/project.json":
                            if not isinstance(data, dict) or data.get("project_id") != manifest.get("project_id"):
                                raise ValueError("Archive project identity does not match manifest")
                            if not preserve_project_id:
                                data["project_id"] = str(uuid.uuid4())
                                data["updated_at"] = now_iso()
                        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    else:
                        with archive.open(info) as source_stream, target.open("xb") as target_stream:
                            shutil.copyfileobj(source_stream, target_stream)
            for relative in ("runtime/reports",):
                (staged / relative).mkdir(parents=True, exist_ok=True)
            load_project_info(staged)
            database_path = staged / "project.db"
            if database_path.is_file():
                from abqjobpilot.database.portability import restore_database_snapshot
                project_id = json.loads((staged / "project.json").read_text(encoding="utf-8"))["project_id"]
                restore_database_snapshot(database_path, destination, project_id)
            if destination.exists():
                raise FileExistsError(f"Project destination already exists: {destination}")
            staged.rename(destination)
    return load_project_info(destination)
