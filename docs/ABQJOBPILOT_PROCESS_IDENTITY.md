# Process Identity and Recovery Evidence (Run 005)

## Scope

Process identity is observation, not a solver verdict. It does not change Abaqus command arguments, queue/SQLite schemas, Job status taxonomy, or the five read-only MCP tools. It does not launch, stop, restart, or validate Abaqus. `FILE-OWNERSHIP-001`, `DB-STORAGE-001`, and `WORKDIR-001` remain in force.

## Launch lifecycle

`runner_core._run_command()` already starts the command with `subprocess.Popen(..., shell=False)` and waits for its return code. For a configured `.bat`/`.cmd`, this PID belongs to `cmd.exe`, not necessarily to the Abaqus solver. Immediately after launch, the runner records an optional `process_identity` object in `runtime/live_status.json`: runtime, queue ID, phase, launcher PID, Windows process creation FILETIME (100 ns ticks), executable path, SHA-256 of the command argument list, working directory, job name, launch time, last observation time, observed descendants, child scan state, and whether launcher exit was observed. No raw command line is stored in this new object. A database `run_id` is not reliably available at this launch point and is not fabricated.

During the existing poll, a Windows Toolhelp process snapshot identifies observed descendants of the verified launcher. Their PID, creation time, and executable path are captured separately. Names such as `standard.exe` and `explicit.exe` are **solver candidates**, not an assertion that actual Abaqus child behavior has been validated. A descendant whose snapshot name differs from its independently queried executable becomes `UNCONFIRMED`. The evidence is best-effort live telemetry; an unavailable OS query never creates a fictitious identity. Normal later live-status updates can replace old evidence, so this is not an immutable forensic process ledger.

## Windows inspection

The standard-library `ctypes` layer calls `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE)`, `GetProcessTimes`, `WaitForSingleObject`, `QueryFullProcessImageNameW`, and Toolhelp `CreateToolhelp32Snapshot`/`Process32FirstW`/`Process32NextW`. It does not require pywin32 or elevated access. An identity is matched by PID **and** creation FILETIME **and** executable path; a reused PID is `IDENTITY_MISMATCH`. Access denial, disappearing processes during inspection, malformed records, or child-discovery failure are `UNCONFIRMED`. An exited process with a still-open handle is recognized via wait state before attempting to query its image. The older `tasklist` scan remains an auxiliary, fail-closed check, not the primary identity proof.

`verify_launch_evidence` reports `CONFIRMED_ACTIVE`, `CONFIRMED_EXITED`, `IDENTITY_MISMATCH`, `POSSIBLE_ORPHAN`, or `UNCONFIRMED`. These are process-evidence levels, distinct from `QUEUED`, `RUNNING`, `COMPLETED`, or `UNKNOWN_INTERRUPTED`. An exited launcher with no observed solver-candidate child remains `UNCONFIRMED`. An observed active descendant remains a blocker even after the launcher exits. `CONFIRMED_EXITED` refers only to the tracked launcher and observed candidate identities; it is not proof of physical Abaqus result validity or completeness of an unobserved process tree.

## Recovery gate

Read-only runtime assessment exposes process evidence, ODB modification-time observation, `.lck` existence, reports, queue state, owner state, and SQLite disagreements without opening ODB. A recovery plan requires matching runtime/queue/phase identity, matching command-exit telemetry, `CONFIRMED_EXITED` tracked-process evidence, no active/unconfirmed runner, no `.lck`, no conflicting terminal report/history, and no recognized Abaqus process in the auxiliary scan. An ODB file or its timestamp never authorizes `COMPLETED`.

The plan stores both metadata and process-observation fingerprints. After local GUI confirmation, Apply takes the existing runtime lock and re-queries OS process state. A changed identity observation rejects the stale plan. The only queue correction remains `*_RUNNING -> UNKNOWN_INTERRUPTED`; no automatic requeue or solver control exists. The GUI recovery report displays the evidence and blockers through its structured JSON view. Human confirmation cannot override a hard process-identity block.

## Output identity and partial failure

Under the existing queue transaction, enqueue checks the requested `(working_dir, job_name)` against interrupted queue records, matching live process evidence, and the corresponding `.lck`. Potential collision returns `OUTPUT_CONFLICT_UNCONFIRMED`; a different output identity in an otherwise safe runtime follows existing queue rules. This does not delete, rename, inspect, or copy solver outputs. The public enqueue JSON error mapping preserves that code.

Queue JSON, live JSON, recovery audit JSON, and SQLite still do not form one atomic transaction. Run 004's `PARTIAL_OR_FAILED` outcome, read-only reassessment, one-record history retry, and queue-ID idempotency remain. The process identity gate also applies to retries. A failed audit preparation occurs before queue mutation. No claim of full crash consistency or solver-lineage completeness is made.

## Limits

Actual Abaqus launcher/child behavior has **not** been tested in this Run. Toolhelp polling may miss short-lived children or a child launched just before the wrapper exits. OS queries can fail for access or lifetime races. The global executable-name scan cannot exclude unusually named solver processes. These limitations block recovery where lineage is not established; they do not authorize guessing. Process evidence does not confer permission to start a new job or override the GUI's Start Queue control.
