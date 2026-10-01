# AbqJobPilot Project Database (P2)

## Responsibility boundary

Each formal Project may have `<ProjectRoot>/project.db`. It indexes durable historical metadata; it is **not** the queue execution engine. `runtime/queue.json` remains the operational source for queue order and current job records. `runtime/live_status.json` remains the running observation. SQLite never changes either JSON file and does not submit Abaqus jobs. No-project/default mode requires no database.

## File Ownership and Lightweight Project Contract

The Project contains metadata, runtime state, and history. CAE, INP, ODB, STA, MSG, DAT, and LOG files normally stay in their engineering workspace; queue/history/artifact rows reference their paths. `FILE-OWNERSHIP-001` forbids implicit copy, move, rename, relocation, or ownership transfer during Project open, queue, run, recording, metadata import, and viewing. Only an explicit archive action with a clear scope may copy files. `DB-STORAGE-001` forbids storing solver/model bytes or BLOBs in `project.db`. `WORKDIR-001` keeps the Job's configured working directory independent of the Project root; the database never redirects Abaqus outputs into `results/`.

For example, a Project under `D:\AbqJobPilotProjects\Stage5_Manager\` indexes paths in `D:\Research\Stage5\` such as `BC01.inp` and `BC01.odb`; it does not take ownership of them. A source CAE path, if recorded in metadata, is optional and reference-only.

The GUI creates/synchronizes the database on opening a formal Project and when queue/report timestamps change. `ProjectManager.open_project()` alone still validates a P1 Project without creating a database. `sync_history_from_runtime(project_root)` may also be called explicitly. It reads queue and report JSON, inserts missing history, and updates safe status/artifact fields. It is idempotent for the same `queue_id`; it never removes historical rows or downgrades a terminal status. If synchronization fails, the GUI's JSON Queue/Results remain available and the failure is logged. An API process that enqueues without the GUI will be indexed on the next GUI/explicit reconciliation, not synchronously by the public API.

## Schema and identity

Schema version **1** lives in `schema_meta(key, value)`. `0 -> 1` creates four tables transactionally; repeated initialization does not recreate or clear them. A database marked with a future version is rejected with `UNSUPPORTED_DATABASE_SCHEMA` before any migration. Unknown unversioned user tables are not adopted or dropped. Foreign keys are enabled on repository connections.

| Table | Meaning | Identity / constraints |
| --- | --- | --- |
| `schema_meta` | Version marker | `key` primary key |
| `jobs` | Logical Abaqus Job | `job_id` UUID-derived; unique `(project_id, logical_key)` |
| `runs` | One queue record / attempt | `run_id` UUID-derived; unique `queue_id` and `(job_id, attempt_no)` |
| `artifacts` | File metadata only | `artifact_id`; unique `(run_id, kind, path)` |

`project_id` comes from `project.json`. A logical Job key uses normalized `inp_path` and `job_name`; if the INP path is absent, it falls back to work directory/name, then to `queue_id`. The key is internal and not a replacement for any existing identifier. `queue_id` continues to identify one runtime record and is used as the idempotent bridge to one Run. Requeue creates a new `queue_id`, which becomes another Run under the same logical `job_id`. `run_id` identifies the database attempt. `attempt_no` increases per logical Job in a SQLite write transaction and is never based on GUI row position.

Run status is a canonical projection of legacy raw status; `raw_status` retains the original string. Earlier FAILED attempts remain even after a later COMPLETED attempt. Unknown or missing source timestamps stay null. Artifacts initially index INP, ODB, STA, MSG, DAT, and LOG using path, existence, size, and mtime. Solver file bytes are never read into the database; an ODB is **not** a BLOB. Missing files have `exists_flag = 0`.

## Repository operations

```python
from abqjobpilot.database import ProjectHistoryRepository, sync_history_from_runtime

sync_history_from_runtime(project.root)
history = ProjectHistoryRepository(project)
job = history.find_job_by_queue_id(queue_id)
runs = history.list_runs(job["job_id"])  # newest attempt first
artifacts = history.list_artifacts(runs[0]["run_id"])
```

The repository also supports `get_or_create_job`, `create_run`, `update_run_status`, `complete_run`, `add_or_update_artifact`, `list_jobs`, `get_run`, and `latest_completed_run`. SQL writes use parameters and transactions. Public errors have stable `code` and `message` through `DatabaseFailure.to_dict()`, including `DATABASE_OPEN_FAILED`, `DATABASE_READ_FAILED`, `DATABASE_WRITE_FAILED`, `DATABASE_MIGRATION_FAILED`, `UNSUPPORTED_DATABASE_SCHEMA`, `JOB_NOT_FOUND`, and `RUN_NOT_FOUND` where applicable.

The Results context menu has **View Run History** in formal Project mode. It refreshes the projection and displays attempts newest-first with status, start/end, CPU/GPU, working directory, and expected ODB. **Delete Result Record** still removes only the runtime JSON result record; it does not delete database Job/Run history or solver files.

## Backup, archives, and legacy import

`backup_database(source, destination)` uses SQLite's online backup API, refuses an existing destination, and produces a readable standalone DB. Future destructive/non-trivial migrations must use this helper before changing a user's database; P2 only has the non-destructive `0 -> 1` migration.

P1 archives with no `project.db` remain valid. Both P2 archive modes include `project.db` when present. The default Metadata Archive excludes engineering files. The opt-in `full` mode includes only files physically inside the Project root; it never follows external paths stored in the database. Export packages an online backup rather than a blind file copy and excludes SQLite journal/WAL sidecars. Project-owned indexed paths in the archive DB backup use `project://` markers. External references stay as paths and can be missing after import. Import restores Project-owned paths against the selected destination, recomputes logical keys, and intentionally preserves or reassigns the Project identity. The source Project DB is never rewritten by export. Older P1/P2 archives with project-owned INP/ODB files remain valid.

Explicit legacy-runtime import remains metadata-only and read-only to its source. It copies queue/status/reports into a new Project, records provenance, and then builds Job/Run history from available records. It does not invent absent legacy timestamps or copy ODB bytes. Records without `queue_id` remain in JSON but cannot be mapped idempotently to a Run; reconciliation reports a skip count.

## Limitations and next stage

- SQLite transactions protect database rows, but independent processes writing the same `queue.json` are **not** coordinated.
- A short-lived status transition may only be observed in its later persisted state; reconciliation preserves the attempt, not every intermediate event.
- The projection may lag an API enqueue until a GUI refresh or explicit sync.
- Project-owned paths are portable in known indexed columns; external paths stay external references.
- No automatic recovery of stale RUNNING records, stale `.lck`, or crashed solver processes is provided here.
- P2 does not add a database-backed active queue, solver submit path, general event system, or AI runtime.

`ABQJOBPILOT_STAGE_R1_RUNTIME_RECOVERY_AND_CONCURRENCY` should address cross-process queue coordination, single-runner ownership, crash/stale-lock recovery, and restart reconciliation. It is not part of P2.
