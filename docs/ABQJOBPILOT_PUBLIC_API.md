# abqjobpilot Public API

Stage:

```text
ABQJOBPILOT_STAGE_A3_AUTOMATION_CONTRACT_AND_QUEUE_CONSISTENCY
```

This API exists so external tools such as `D:\Projects\AbqPilot-v2` can interact with abqjobpilot through a stable, GUI-free, safe contract.

The public API defaults to preflight/dry-run behavior. Explicit queue-only mode writes queue metadata and does not start Abaqus solver execution.

## Safety Boundary

The API layer:

```text
does not import Tkinter GUI modules
does not launch run_gui.py
does not call QueueRunner.start()
does not call run_next_job()
does not call Abaqus
does not open ODB files
does not mutate queue.json during preflight or dry-run enqueue
does not mutate live_status.json or runtime/reports during enqueue-only
```

The only allowed public API mutation is an explicit queue-only enqueue:

```python
AbqJobPilotClient().enqueue(request, dry_run=False)
```

That path is accepted only for `submission_mode="enqueue_only"` or `"preview_only"` with `allow_solver_submit=False`. It writes `runtime\queue.json` only and reports `solver_started=False`, `runner_started=False`, and `gui_required=False`.

## Import

```python
from abqjobpilot.api import AbqJobPilotClient, JobRequest
```

## JobRequest

```python
JobRequest(
    inp_path="D:\\path\\model.inp",
    job_name=None,
    cpus=14,
    gpus=0,
    batch=None,
    strategy=None,
    working_dir=None,
    submission_mode="preview_only",
    allow_solver_submit=False,
    metadata={},
)
```

Defaults are intentionally safe:

```text
submission_mode = "preview_only"
allow_solver_submit = False
```

Supported submission modes:

```text
preview_only
enqueue_only
submit
```

In this stage, `submit` is rejected by the public API even if `allow_solver_submit=True`.

## Result Objects

All result objects support:

```python
to_dict()
to_json()
```

### JobPreflightResult

```python
{
  "status": "PREVIEW_READY | INVALID_REQUEST | UNSAFE_REQUEST",
  "job_id": None,
  "inp_path": "...",
  "inp_exists": True,
  "job_name": "...",
  "cpus": 14,
  "batch": "...",
  "strategy": "...",
  "working_dir": "...",
  "expected_odb_path": "...",
  "command_preview": "...",
  "errors": [],
  "warnings": []
}
```

### JobSubmitResult

```python
{
  "status": "DRY_RUN_READY | ENQUEUED | REJECTED | REJECTED_UNSAFE_DIRECT_SUBMIT | FAILED | FAILED_FORBIDDEN_RUNTIME_MUTATION",
  "job_id": "...",
  "queue_file": "...",
  "expected_odb_path": "...",
  "command_preview": "...",
  "queue_only": true,
  "queue_file_mutated": true,
  "solver_started": false,
  "runner_started": false,
  "gui_required": false,
  "allowed_mutations": ["runtime/queue.json"],
  "forbidden_mutations_detected": false,
  "runtime_snapshot_before": {},
  "runtime_snapshot_after": {},
  "errors": [],
  "warnings": []
}
```

### JobStatusResult

```python
{
  "status": "QUEUED | RUNNING | COMPLETED | FAILED | LOCKED | ODB_MISSING | UNKNOWN",
  "job_id": "...",
  "inp_path": "...",
  "working_dir": "...",
  "expected_odb_path": "...",
  "odb_exists": false,
  "lock_exists": false,
  "status_sources": [],
  "last_log_lines": [],
  "errors": [],
  "warnings": []
}
```

### JobOutputResult

```python
{
  "job_id": "...",
  "working_dir": "...",
  "expected_odb_path": "...",
  "odb_exists": false,
  "lock_exists": false,
  "log_paths": [],
  "sta_path": "...",
  "msg_path": "...",
  "dat_path": "...",
  "errors": [],
  "warnings": []
}
```

## Python Examples

### Preflight

```python
from abqjobpilot.api import AbqJobPilotClient, JobRequest

client = AbqJobPilotClient()
request = JobRequest(
    inp_path=r"D:\path\model.inp",
    cpus=14,
    batch="batch01",
    strategy="strategy01",
)

result = client.preflight(request)
print(result.to_json())
```

### Dry-run Enqueue

```python
result = client.enqueue(request, dry_run=True)
print(result.to_json())
```

This does not modify `runtime\queue.json`.

### Queue-only Enqueue

```python
request.submission_mode = "enqueue_only"
result = client.enqueue(request, dry_run=False)
print(result.to_json())
```

This appends queue metadata only. It does not start Abaqus, the queue runner, or the GUI. The result must report:

```json
{
  "status": "ENQUEUED",
  "queue_only": true,
  "queue_file_mutated": true,
  "solver_started": false,
  "runner_started": false,
  "gui_required": false,
  "forbidden_mutations_detected": false
}
```

### Status

```python
result = client.status(job_id="q_...")
print(result.to_json())
```

### Locate Outputs

```python
result = client.locate_outputs(job_id="q_...")
print(result.to_json())
```

## CLI

The CLI is available as:

```powershell
python -m abqjobpilot.api.cli
```

### Preflight

```powershell
python -m abqjobpilot.api.cli preflight --inp D:\path\model.inp --cpus 14 --batch batch01 --strategy strategy01 --json
```

### Dry-run Enqueue

```powershell
python -m abqjobpilot.api.cli enqueue --inp D:\path\model.inp --cpus 14 --batch batch01 --strategy strategy01 --dry-run --json
```

Dry-run is the default for the enqueue CLI.

### Queue-only Enqueue

```powershell
python -m abqjobpilot.api.cli enqueue --inp D:\path\model.inp --cpus 14 --batch batch01 --strategy strategy01 --enqueue-only --json
```

For tests and controlled smoke runs, a temporary runtime can be used:

```powershell
python -m abqjobpilot.api.cli enqueue --inp D:\path\model.inp --cpus 14 --batch batch01 --strategy strategy01 --enqueue-only --runtime-dir D:\temp\abqjobpilot_runtime --json
```

`--enqueue-only` is not solver submission. It writes queue metadata only.

### Status

```powershell
python -m abqjobpilot.api.cli status --job-id q_... --json
```

### Locate Outputs

```powershell
python -m abqjobpilot.api.cli locate-outputs --job-id q_... --json
```

### Capabilities, List, and Folder Preview

```powershell
python -m abqjobpilot.api.cli capabilities --json
python -m abqjobpilot.api.cli list --runtime-dir D:\temp\abqjobpilot_runtime --json
python -m abqjobpilot.api.cli enqueue-folder --folder D:\path\strategy --pattern "*.inp" --json
```

`enqueue-folder` is non-recursive and defaults to dry-run. `--enqueue-only` explicitly appends matching INPs to the queue; it never starts the solver. Each CLI command accepts `--runtime-dir`. `list` reads queue-file records in persisted order and reports both canonical `status` and `raw_status`.

## Automation Surface v1

AbqJobPilot exposes a thin automation interface for deterministic job preparation,
queueing, status inspection, and output discovery.

It is not an AI Runtime, agent framework, orchestration engine, or evidence authority.

The public surface consists of `capabilities`, `preflight`, `enqueue`, `enqueue-folder`, `list`, `status`, and `locate-outputs`. `AbqJobPilotClient(runtime_dir=X)` uses X for queue writes, queue/status/report reads, and output discovery. Preflight and capabilities do not need to read or create runtime files. The default runtime is the development application's configured runtime directory, resolved when the client is constructed.

## Schema Versioning

New public JSON responses include `"schema_version": "1.0"`. New queue writes use:

```json
{"schema_version": "1.0", "jobs": []}
```

New queue records, live status files, and job reports also carry `schema_version`. A legacy queue file containing a top-level list, and legacy records without the field, remain readable. Opening the GUI does not rewrite an existing queue file solely to add a version. The first explicit queue mutation writes the versioned envelope. The reports manifest remains a list for compatibility; new manifest entries carry `schema_version`.

Queue writes use a same-directory temporary file, flush and fsync it, then replace `queue.json` atomically. A process-local lock covers the application's queue read/modify/write operations. This protects threads within one Python process and avoids a partly written canonical JSON file. It does not provide full inter-process serialization: simultaneous independent GUI/CLI processes can still lose an update. Use one queue writer at a time until a tested cross-process lock or database transaction is added.

## Stable Identifiers

`queue_id` identifies exactly one queue/history record. A requeue gets a new `queue_id`; old IDs remain valid for their retained records. Newly generated IDs use `q_` plus a UUID; existing timestamp-based IDs remain readable. `job_id` in the public API is an alias for `queue_id`, not another identifier. `job_name` is the Abaqus solver job name. `inp_path` is the source input file path. `batch` and `strategy` are descriptive request labels stored as `batch_name` and `strategy_name`. Look up by `queue_id` when multiple attempts share an INP; lookup by `inp_path` selects the latest matching queue record.

## Canonical Status Values

Public job lifecycle statuses are `QUEUED`, `DATACHECK`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`, `SKIPPED`, `LOCKED`, `ODB_MISSING`, and `UNKNOWN`. A2 compatibility is preserved: `DATACHECK_RUNNING` maps to `RUNNING`, `DATACHECK_OK` maps to `QUEUED`, and `SKIPPED` remains `SKIPPED`. Completed records without an expected ODB map to `ODB_MISSING`; unknown raw values map to `UNKNOWN`. `list` exposes the original status as `raw_status`. Preflight/enqueue operation results use separate operation statuses such as `PREVIEW_READY`, `DRY_RUN_READY`, and `ENQUEUED`.

## Machine-readable Error Codes

Existing human-readable `errors` remain. Public result JSON also contains `error_details` entries with `code` and `message`, for example:

```json
{"code": "INP_NOT_FOUND", "message": "INP file does not exist: D:\\missing.inp"}
```

Codes include `INP_NOT_FOUND`, `INVALID_CPU_COUNT`, `INVALID_GPU_COUNT`, `DUPLICATE_ACTIVE_JOB`, `INVALID_REQUEST`, `QUEUE_RECORD_NOT_FOUND`, `RUNTIME_NOT_FOUND`, `OUTPUT_NOT_FOUND`, `UNSAFE_OPERATION`, `QUEUE_WRITE_FAILED`, and `INVALID_STATUS_DATA`. A code describes the first matching failure category; the human message provides detail. CLI exits 0 when `errors` is empty and 1 otherwise.

## Capabilities

`AbqJobPilotClient().capabilities()` and the `capabilities --json` CLI command are read-only. They report surface version `1.0` and booleans for the implemented commands. `solver_start` is `false`.

## Execution Boundary

The public automation surface does not expose solver start/submit in A3.
Actual execution remains controlled by the existing GUI Start Queue workflow.
No public command accepts arbitrary shell commands, launches the queue runner, or opens ODB files.

## AbqPilot Integration Notes

For `D:\Projects\AbqPilot-v2`, recommended usage is:

```text
1. Build a JobRequest.
2. Call preflight().
3. Show command_preview to the user.
4. Call dry-run enqueue as a safety preview when needed.
5. Call queue-only enqueue only behind AbqPilot approval gates.
6. Do not call submit mode.
```

Recommended first integration mode:

```json
{
  "submission_mode": "preview_only",
  "allow_solver_submit": false
}
```

Recommended later queue-only integration mode:

```json
{
  "submission_mode": "enqueue_only",
  "allow_solver_submit": false
}
```

Real solver submission remains outside this public API stage.

AbqPilot-v2 can verify the queue-only contract from `JobSubmitResult` fields:

```text
queue_only=true
queue_file_mutated=true
solver_started=false
runner_started=false
gui_required=false
forbidden_mutations_detected=false
allowed_mutations=["runtime/queue.json"]
```

## Known Limitations

```text
No solver submit API is exposed.
No queue runner control API is exposed.
No SQLite-backed status layer exists yet.
The command preview uses the configured default Abaqus command path.
The API reads existing JSON status files but does not yet guarantee schema migration.
Queue write serialization is process-local; independent processes must not write the same queue concurrently.
```

## Project runtime ownership (P1)

A Project owns its runtime at `<ProjectRoot>/runtime`. Pass `AbqJobPilotClient(runtime_dir=str(project.runtime_dir))` explicitly for project-scoped queue, status, and output operations. The default client still targets the configured local runtime, not whichever Project another GUI process has opened. The public automation surface does not create/open Projects or start the solver. See `docs/ABQJOBPILOT_PROJECT_MODEL.md` for the Project filesystem, archive, and legacy-import contract.

## Agent and Coding-Assistant Integration

Codex, Claude Code, ChatGPT, and other tools may use the same vendor-neutral interface:

```text
Coding assistant -> JSON CLI / Python API / Agent Commands
                 -> AbqJobPilot Automation Surface v1
                 -> queue metadata, status, output references
```

The public Python client and JSON CLI support `capabilities`, `preflight`, `enqueue`, `enqueue-folder`, `list`, `status`, and `locate-outputs`. The Agent Command Console accepts only its internal `enqueue`, `enqueue-folder`, `list`, `help`, and `clear` grammar. These are related interfaces, not interchangeable command syntaxes. The GUI Agent menu links to the canonical AI Instruction and this document.

Public `solver_start` remains `false`. No assistant-specific SDK, MCP endpoint, HTTP service, or direct solver-start command is provided. Application version `0.2.0` is reported separately from `automation_surface` and `schema_version`, which remain `1.0`.
