# Runtime coordination (Run 003)

`runtime/queue.json` remains active control state, `runtime/live_status.json`
remains observation, and `project.db` remains the durable history projection.
No solver command or public solver-start endpoint was added.

## Queue transaction

The canonical resolved runtime directory identifies the lock. Every production
queue-store read/validate/mutate/write operation runs under `.queue.lock`, using
Windows `msvcrt.locking` byte-range OS locking plus a per-runtime reentrant
in-process lock. The bounded default wait is 5 seconds. `QUEUE_LOCK_TIMEOUT`
is machine-readable; no success is reported if the queue write fails. The
critical section includes queue read, duplicate/admission validation, mutation,
and JSON write. `write_json` flushes and fsyncs a unique temporary file before
`os.replace`. This protects against lost updates among cooperating writers.
Different resolved runtime paths use independent locks. A lock file's mere
existence is never treated as proof of an active owner. Project creation and
legacy/archive import initialize a *new* runtime offline; they do not edit an
active queue through the normal queue-store path.
The local `.queue.lock`, `.runner.lock`, and `runner_owner.json` coordination
artifacts are excluded from both metadata and full portable Project archives.

The production writer paths are:

| Writer | State | Coordination |
| --- | --- | --- |
| GUI / Agent Console / CLI / Python API via `enqueue_record` | queue | transaction + runner admission |
| GUI `add_inp_job_to_queue`, `add_folder_to_queue`, requeue | queue | per-record transaction; folder may return `PARTIAL` |
| GUI remove, bulk remove, reorder, resource edit | queue | transaction |
| Runner `update_job` status transitions | queue | transaction |
| Runner live-status/report telemetry | live JSON / reports | existing atomic JSON replacement; not queue admission state |
| GUI history sync | project.db | existing SQLite transactions/projection |

`save_queue` is a low-level whole-list writer. Production read-modify-write
callers invoke it *within* the transaction; external clients should use the
public API, not compute a stale list and call `save_queue` independently.

## Runner ownership and admission

`QueueRunner.start` acquires `.runner.lock` under `.queue.lock` before launching
its background thread. The OS lock is retained for the runner lifetime.
`runner_owner.json` records canonical runtime, PID, random owner token, and
acquisition time for diagnosis, but metadata or PID alone never proves liveness.
The runner releases the OS lock in its loop's `finally` block. A competing
runner receives `RUNNER_OWNERSHIP_CONFLICT`; malformed/ambiguous ownership
receives `RUNNER_OWNERSHIP_UNCONFIRMED`. External enqueue takes the same queue
transaction, probes the OS-backed runner lock, and rejects confirmed ownership
with `RUNNER_ACTIVE`. Thus an enqueue either commits before ownership or is
rejected after ownership; it cannot pass an earlier idle check and append
behind an already-started runner. A stale metadata file with no OS lock is
diagnostic only and does not indefinitely block new ownership.
If no OS owner exists but queue or live status still records a running phase,
new runner ownership and external enqueue return `RECOVERY_REQUIRED`; they do
not assume the solver has stopped or rewrite the stale state. Malformed
queue/live observations fail closed with `INVALID_STATUS_DATA`.

The runner still dynamically consumes queued jobs. The admission policy is
therefore intentionally reject-while-active. This does not alter the GUI's
Start Queue or Stop After Current Job actions.

## Read-only recovery assessment

`assess_runtime(runtime_dir, project_db=optional_path)` reads queue, live
status, OS-backed ownership, report presence, `.lck`/ODB existence, and
SQLite run statuses in read-only mode. It returns `CLEAN`, `ACTIVE_RUNNER`,
`STALE_RUNNING`, `RECOVERY_REQUIRED`, or `UNCONFIRMED` with the underlying
observations. It never changes statuses, removes `.lck`, opens ODB content,
or resumes Abaqus. `.lck` and ODB existence are not proof of an active solver
or valid completion. Solver process confirmation remains `UNKNOWN` unless a
future, separately verified mechanism provides it. Historical RUNNING rows
are not rewritten to match current ownership. JSON/SQLite disagreements are
reported, not reconciled by this assessment.

## Limits

All *cooperating* queue-store writers share the lock; a program editing
`queue.json` directly can still violate the contract. The low-level
whole-list `save_queue` cannot detect that a caller constructed its list from
an earlier unlocked read. Folder enqueue is a sequence of individually atomic
records, not an all-or-nothing batch. Live-status and report metadata retain
their prior last-writer behavior. SQLite history sync remains idempotent but is
not made into a distributed transaction with queue JSON. No crash repair,
solver-process verification, stale `.lck` deletion, or automatic resume is
performed. Engineering files remain external references.
