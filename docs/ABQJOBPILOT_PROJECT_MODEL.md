# AbqJobPilot Project Model (P1 filesystem, P2 history, P2B ownership)

## Project ownership

A Project owns its AbqJobPilot runtime state. Queue and result history must not leak between Projects. Portable archives are explicit copies of project state; opening a Project never mutates another Project or a legacy runtime source.

`project_id` is a UUID identifying the Project independently of its folder name. Export/import preserves it by default; `import_project_archive(..., preserve_project_id=False)` explicitly assigns a new identity. Each `queue_id` still identifies an individual queue/history record. Project names are display labels, not identifiers.

## Filesystem contract

```text
<ProjectRoot>/
  project.json
  project.db  # optional durable history, created when needed
  runtime/
    queue.json
    live_status.json
    reports/
```

`project.db` is created only when history functionality is used. `project.json` is a UTF-8 JSON object with `schema_version: "1.0"`, `application: "abqjobpilot"`, `project_id`, `name`, `description`, `created_at`, and `updated_at`. An imported legacy Project may also contain `import_provenance`. Queue and live status remain JSON; `runtime/queue.json` may contain both pending and completed/failed records. Older Projects may contain `models/`, `results/`, or `logs/`; these remain valid, are never removed automatically, and are not mandatory destinations for new Jobs.

## File Ownership and Lightweight Project Contract

A Project owns AbqJobPilot metadata, runtime state, and durable history, not the engineering workspace. Engineering files such as CAE, INP, ODB, STA, MSG, DAT, and LOG normally remain in their original workspace and are referenced by path. A Project can be created before any model exists. An optional source CAE path is only a reference; it is never required, opened, or copied by Project management.

- **FILE-OWNERSHIP-001:** Opening, queueing, running, recording, importing metadata, or viewing a Job must not copy, move, rename, relocate, or take ownership of external CAE, INP, ODB, STA, MSG, DAT, or LOG files. Copying is permitted only through an explicit user-requested archive operation whose scope is shown beforehand.
- **DB-STORAGE-001:** `project.db` stores metadata and paths only. Model and solver files are never SQLite BLOBs.
- **WORKDIR-001:** The Job working directory comes from its input/job configuration, not the Project storage directory. Creating or opening a Project does not redirect solver output.

For example, `D:\AbqJobPilotProjects\Stage5_Manager\` may contain `project.json`, `project.db`, and `runtime\`, while it references these files without moving them:

```text
D:\Research\Stage5\
  BC01.cae
  BC01.inp
  BC01.odb
  BC01.sta
  BC01.msg

D:\AbqJobPilotProjects\Stage5_Manager\
  project.json
  project.db
  runtime\
    queue.json
    live_status.json
    reports\
```

Queueing `D:\Research\Stage5\BC01.inp` retains that `inp_path`, defaults `work_dir` to `D:\Research\Stage5`, and expects `D:\Research\Stage5\BC01.odb` unless the Job explicitly specifies another working directory. No INP is copied into the Project.

The public automation API remains GUI-free. Use `AbqJobPilotClient(runtime_dir=str(project.runtime_dir))` to scope queue/status/output reads and queue-only writes. A client without an explicit runtime still uses the configured default runtime; it does not infer the GUI's active Project across processes.

## GUI modes and switching

`python run_gui.py` starts in **No Project (default runtime)** mode. It does not silently convert the old `runtime/` into a Project. The Project bar offers New, Open, Recent, Close, Project Folder, Export, Import, and Import Legacy. Opening a Project changes only this GUI process's runtime paths for Queue, Results, live status, reports, and runtime-specific Settings. Switching back to No Project restores the development application's default runtime. The active Project name is visible; table selection/render state is reset on switch. Switching is blocked while the internal runner is active or the Agent Command Console is open. Switching never starts or cancels a solver.

Settings remain runtime-specific in P1 (`runtime/settings.json`); a new Project initially uses application defaults until settings are saved. Recent Projects are **application-level**, stored by default at `%LOCALAPPDATA%/abqjobpilot/recent_projects.json` on Windows. The list is newest-first, deduplicated by canonical path/project ID, capped at 10, and tolerates missing paths. A different recent-file path can be supplied to `ProjectManager` for tests or controlled deployments.

## Python operations

```python
from abqjobpilot.project import ProjectManager, export_project_archive, import_project_archive, import_legacy_runtime
from abqjobpilot.api import AbqJobPilotClient

manager = ProjectManager()
project = manager.create_project(r"D:\Studies\StudyA", "StudyA")
project = manager.open_project(project.root)
client = AbqJobPilotClient(runtime_dir=str(project.runtime_dir))
archive = export_project_archive(project.root, r"D:\Exports\StudyA.abqjobpilot-project.zip", mode="metadata")
restored = import_project_archive(archive, r"D:\Studies\Restored")
```

Creating a Project requires a new destination directory. Opening validates the manifest and queue without rewriting them. No operation above launches Abaqus.

## Archive format

The extension is `.abqjobpilot-project.zip`. The ZIP contains root `manifest.json` with `archive_schema_version: "1.0"`, `application`, `project_id`, `mode`, `created_at`, a file list, and classified path references. Project files live under `project/`. The archive records project-owned metadata paths as `project://relative/path`; import remaps these to the chosen destination. External references remain external and may be missing on another computer. INP contents and Abaqus internal references are never rewritten.

`metadata` is the default **Metadata Archive**: it includes `project.json`, JSON files under `runtime/`, and `project.db` if present. It excludes external and project-owned CAE/INP/ODB/STA/MSG/DAT/LOG files. The opt-in `full` mode is labeled **Archive with Project-Owned Files** in the GUI: it includes regular files physically beneath the Project root, including any files deliberately placed in old `models/` or `results/` directories. It does **not** collect external files referenced by path. The GUI shows that scope before export and defaults to Metadata Archive. An existing database is archived from a SQLite backup, not a raw live-file copy. Neither mode follows external symlinks. A legacy provenance `source_path` is redacted in exported `project.json`.

Export refuses an existing destination and an archive path inside the Project. Import validates the archive schema, file list, Project identity, entry types and canonical names; rejects absolute paths, traversal, symlinks, and duplicate entries; extracts into a temporary directory; validates the Project; and renames it to a new destination. It refuses an existing destination. Import does not start a solver or open ODB files. Missing external references are retained without failing import or fabricating files. Older P1/P2 archives with `models/` or `results/` remain readable; their contained files stay Project-owned in the imported copy. The opt-in `full` mode may be large if old Projects contain ODBs.

## Legacy runtime import

`import_legacy_runtime(source_runtime_dir, destination_project_root, project_name)` reads `queue.json`, optional `live_status.json`, and `reports/*.json` from the source, then writes copies into a **new** Project. Legacy list-style queues without `schema_version` are accepted. Existing job records, timestamps, CPU/GPU values, statuses, and external paths are preserved without fabricating missing data. `project.json` records source type, local source path, import time, and source schema version (null if absent). The source is never modified. Artifacts such as `.odb` are not copied by default.

## Known limitations

- A metadata archive can reference an INP/ODB that is absent after import. The path remains discoverable, but preflight may fail until the user supplies the file.
- Portable path markers cover known job/report path fields. Unknown application-specific absolute paths in arbitrary JSON are not rewritten.
- Queue writes are atomic and serialized within one process, not transactionally safe across independent processes.
- Project creation is not a transactional multi-file operation; an I/O failure can leave a partial new destination for manual inspection.
- ZIP import checks path traversal and member types, but does not impose a universal uncompressed-size limit because full archives may intentionally contain large ODB files. Import only trusted archives with enough disk space.
- P1 archives without a database remain valid. P2 adds optional `project.db` for durable history; `runtime/queue.json` and `runtime/live_status.json` remain active runtime/control state. See `docs/ABQJOBPILOT_PROJECT_DATABASE.md`.
