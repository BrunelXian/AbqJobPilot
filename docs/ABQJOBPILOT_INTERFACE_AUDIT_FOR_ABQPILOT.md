# abqjobpilot Interface Audit for AbqPilot-v2

Audit date: 2026-06-24  
Project audited: `D:\Projects\abqjobpilot_dev`  
Target integrator: `D:\Projects\AbqPilot-v2`  
AbqPilot status: `PASS_ABQPILOT_V2_STAGE2_2_RESUME_SKIP_RERUN_CONTROL_READY`  
Planned integration stage: `Stage 2.3: abqjobpilot Preflight Integration`

This audit is inspection-only. No Abaqus job was submitted, no INP was enqueued, and runtime queue/status files were not modified.

## A2 Queue-only Enqueue Contract

Status:

```text
ABQJOBPILOT_STAGE_A2_QUEUE_ONLY_ENQUEUE_CONTRACT_READY
```

A2 guarantees that public API enqueue-only mode writes queue metadata only and does not start Abaqus solver execution.

The public API path:

```python
from abqjobpilot.api import AbqJobPilotClient, JobRequest

request = JobRequest(
    inp_path=r"D:\path\model.inp",
    cpus=14,
    submission_mode="enqueue_only",
    allow_solver_submit=False,
)
result = AbqJobPilotClient().enqueue(request, dry_run=False)
```

must report:

```json
{
  "status": "ENQUEUED",
  "queue_only": true,
  "queue_file_mutated": true,
  "solver_started": false,
  "runner_started": false,
  "gui_required": false,
  "allowed_mutations": ["runtime/queue.json"],
  "forbidden_mutations_detected": false
}
```

Only `runtime\queue.json` may mutate during enqueue-only. `runtime\live_status.json`, `runtime\reports`, GUI startup, queue runner startup, subprocess launch, and Abaqus execution remain outside the public API contract.

The CLI exposes this as:

```powershell
python -m abqjobpilot.api.cli enqueue --inp D:\path\model.inp --cpus 14 --batch batch01 --strategy strategy01 --enqueue-only --json
```

Dry-run remains the default unless `--enqueue-only` is explicitly passed.

## 1. Current Entry Points

### GUI entry point

File:

```text
D:\Projects\abqjobpilot_dev\run_gui.py
```

Command:

```powershell
cd D:\Projects\abqjobpilot_dev
python run_gui.py
```

`run_gui.py` imports `main` from `abqjobpilot.gui_app` and starts the Tkinter GUI.

### Python package import root

Import root:

```python
import abqjobpilot
```

Relevant importable modules:

```text
D:\Projects\abqjobpilot_dev\abqjobpilot\queue_store.py
D:\Projects\abqjobpilot_dev\abqjobpilot\command_parser.py
D:\Projects\abqjobpilot_dev\abqjobpilot\runner_core.py
D:\Projects\abqjobpilot_dev\abqjobpilot\monitor.py
D:\Projects\abqjobpilot_dev\abqjobpilot\parsers.py
D:\Projects\abqjobpilot_dev\abqjobpilot\settings_store.py
D:\Projects\abqjobpilot_dev\abqjobpilot\utils.py
```

Useful callable functions/classes found:

```python
from abqjobpilot.queue_store import (
    add_inp_job_to_queue,
    add_folder_to_queue,
    load_queue,
    save_queue,
    queued_jobs,
    result_jobs,
    update_job,
    mark_job_skipped,
    remove_result_job,
    apply_resources_to_queued_jobs,
)

from abqjobpilot.command_parser import (
    parse_agent_command,
    extract_agent_commands,
)

from abqjobpilot.runner_core import (
    build_abaqus_datacheck_command,
    build_abaqus_full_run_command,
    run_next_job,
    QueueRunner,
)

from abqjobpilot.monitor import (
    read_sta_tail,
    read_console_tail,
)

from abqjobpilot.parsers import (
    parse_sta_status,
    parse_console_status,
    latest_attempt_block,
    classify_datacheck_attempt,
    classify_final_verdict,
)
```

### Agent Command Console

The Agent Command Console exists only inside the GUI. It is not an operating-system CLI.

Supported internal commands:

```text
enqueue
enqueue-folder
list
help
clear
```

Example internal command:

```text
enqueue --inp "D:\path\Job_xxx.inp" --cpus 14 --gpus 0 --batch some_batch --strategy some_strategy
```

### Missing entry points

No standalone CLI entry point was found for enqueue/status/preflight.

Not found:

```text
main.py
abqjobpilot.cli
python -m abqjobpilot ...
setup.py console_scripts
pyproject.toml project.scripts
batch enqueue script
status CLI
JSON CLI
```

## 2. Current Enqueue Interface

### Internal command parser

File:

```text
D:\Projects\abqjobpilot_dev\abqjobpilot\command_parser.py
```

Supported command:

```text
enqueue --inp path\to\model.inp --cpus 14 --batch some_batch --strategy some_strategy
```

Required argument:

```text
--inp
```

Optional arguments:

```text
--cpus
--gpus
--batch
--strategy
--job-name
--datacheck
--full-run
--notes
```

Defaults:

```text
cpus: config.DEFAULT_CPUS, currently 14 unless Settings override is applied by GUI console
gpus: config.DEFAULT_GPUS, currently 0 unless Settings override is applied by GUI console
datacheck: config.DEFAULT_RUN_DATACHECK, True
full-run: config.DEFAULT_RUN_FULL, True
notes: ""
```

Important detail: the parser itself returns `cpus=None` / `gpus=None` when those flags are omitted. The GUI console then applies values from `settings_store.load_settings()`.

### Python enqueue function

File:

```text
D:\Projects\abqjobpilot_dev\abqjobpilot\queue_store.py
```

Function:

```python
def add_inp_job_to_queue(
    inp_path: str,
    cpus: int = config.DEFAULT_CPUS,
    gpus: int = config.DEFAULT_GPUS,
    batch_name: str | None = None,
    strategy_name: str | None = None,
    job_name: str | None = None,
    run_datacheck: bool = config.DEFAULT_RUN_DATACHECK,
    run_full: bool = config.DEFAULT_RUN_FULL,
    notes: str = "",
) -> dict:
    ...
```

Validation currently performed:

```text
INP path exists
file suffix is .inp
cpus is a positive integer
gpus is a non-negative integer
work_dir exists
duplicate active inp_path is rejected
duplicate active job_name + work_dir is rejected
```

Behavior:

```text
Does it copy the INP? No.
Does it create a separate run directory? No.
Does it use the INP parent directory as work_dir? Yes.
Does it immediately start Abaqus? No.
Does it only append to queue.json? Yes.
Does it return structured Python output? Yes.
Does it return process exit codes? No OS CLI exists, so no.
```

Successful enqueue returns a Python dictionary containing:

```text
ok
message
queue_id
job_name
strategy_name
batch_name
inp_path
work_dir
cpus
gpus
queue_position
job
```

Failed enqueue returns:

```text
ok: False
message: error detail
```

### Folder enqueue

Function:

```python
def add_folder_to_queue(
    folder: str,
    pattern: str = "*.inp",
    cpus: int = config.DEFAULT_CPUS,
    gpus: int = config.DEFAULT_GPUS,
    batch_name: str | None = None,
    strategy_name: str | None = None,
) -> dict:
    ...
```

Behavior:

```text
Scans only the selected folder.
Does not recurse.
Sorts matching INP files by filename.
Calls add_inp_job_to_queue for each INP.
Does not submit Abaqus.
```

## 3. Current Job Status Interface

There is no formal status API such as:

```python
status(job_id: str) -> JobStatusResult
```

However, status is stored in machine-readable JSON files.

### Status storage

Primary queue file:

```text
D:\Projects\abqjobpilot_dev\runtime\queue.json
```

Live status file:

```text
D:\Projects\abqjobpilot_dev\runtime\live_status.json
```

Completed/failed report manifest:

```text
D:\Projects\abqjobpilot_dev\runtime\reports\manifest.json
```

Per-job report files:

```text
D:\Projects\abqjobpilot_dev\runtime\reports\{queue_id}_{job_name}.json
```

Abaqus output files are expected beside the INP file:

```text
{work_dir}\{job_name}.sta
{work_dir}\{job_name}.msg
{work_dir}\{job_name}.dat
{work_dir}\{job_name}.log
{work_dir}\{job_name}.odb
```

### Internal status values

Configured status values include:

```text
QUEUED
DATACHECK_RUNNING
DATACHECK_OK
DATACHECK_FAILED
DATACHECK_FAILED_INVALID_GPU_OPTION
FULL_RUNNING
COMPLETED_OK
COMPLETED_WITH_WARNINGS
FAILED_FATAL
FAILED_NUMERICAL
FAILED_INPUT
FAILED_LICENSE
SKIPPED
CANCELLED
UNKNOWN_INTERRUPTED
```

### Requested status categories

Mapping quality:

```text
QUEUED: supported directly
RUNNING: supported through DATACHECK_RUNNING and FULL_RUNNING
COMPLETED: supported through COMPLETED_OK and COMPLETED_WITH_WARNINGS
FAILED: supported through DATACHECK_FAILED*, FAILED_*
CANCELLED: status exists
LOCKED: no first-class .lck status interface found
ODB_MISSING: no first-class status interface found
UNKNOWN: UNKNOWN_INTERRUPTED exists, but no generic status API found
```

Status can be inferred from queue/report JSON, but AbqPilot currently has no stable function or CLI contract for status polling.

## 4. Current Output and Log Contract

### Command used

The Abaqus command is written into each job log by the runner before execution:

```text
Command: ...
```

The command is not currently stored as a dedicated JSON field in the queue/report metadata.

### stdout/stderr

`runner_core._run_command(...)` redirects Abaqus stdout and stderr into:

```text
{work_dir}\{job_name}.log
```

### Abaqus output files

Expected output paths are stored in job records:

```text
odb_path
sta_path
msg_path
dat_path
log_path
```

### Metadata outputs

Queue metadata:

```text
D:\Projects\abqjobpilot_dev\runtime\queue.json
```

Live status:

```text
D:\Projects\abqjobpilot_dev\runtime\live_status.json
```

Completed/failed reports:

```text
D:\Projects\abqjobpilot_dev\runtime\reports\
```

### Can AbqPilot reliably discover these today?

```text
job working directory: Yes, from work_dir
expected ODB path: Yes, from odb_path
final status: Mostly yes, from status/final_verdict in queue/report JSON
lock file status: No stable contract; .lck is not exposed as a field
last log lines: Yes through monitor.read_console_tail or direct log tail
STA tail: Yes through monitor.read_sta_tail or direct file tail
Abaqus command used: Partially; parse from .log, not structured JSON
cpus used: Yes, from cpus
gpus used: Yes, from gpus
```

## 5. Current Python Importability

AbqPilot can import `abqjobpilot` as a Python package if `D:\Projects\abqjobpilot_dev` is on `PYTHONPATH`.

Low-risk imports:

```python
from abqjobpilot.command_parser import parse_agent_command
from abqjobpilot.queue_store import load_queue, queued_jobs, result_jobs
from abqjobpilot.monitor import read_sta_tail, read_console_tail
from abqjobpilot.parsers import classify_final_verdict
from abqjobpilot.runner_core import build_abaqus_datacheck_command
```

Higher-risk imports/calls:

```python
from abqjobpilot.runner_core import run_next_job, QueueRunner
```

`run_next_job(job)` and `QueueRunner.start()` are real execution paths. They can submit Abaqus jobs.

Import side effects:

```text
Importing modules does not launch the GUI.
Importing modules does not submit Abaqus.
Calling queue_store load/save helpers can initialize or write runtime JSON files.
Calling add_inp_job_to_queue mutates queue.json.
Calling run_next_job or QueueRunner.start can submit Abaqus.
```

Can functions be called without GUI?

```text
Queue read/write: Yes
Command parsing: Yes
Log parsing: Yes
Tail reading: Yes
Command building: Yes
Solver submission: Yes, but must be avoided unless explicitly authorized
```

Does a dry-run / preview mode exist?

```text
No formal dry-run/preflight API exists.
```

## 6. Current Dry-run / Preview Capability

Current support:

```text
dry-run enqueue: No
command preview from request: No formal API
job request validation without enqueue: No public API
queue preview: Partial, by load_queue/queued_jobs
status-only read: Partial, by load_queue/result_jobs/read_json/monitor functions
```

Existing pieces that can support a future preflight:

```text
command_parser.parse_agent_command can parse request strings safely.
queue_store has validation logic, but it is private and tied to enqueue.
runner_core.build_abaqus_datacheck_command can build a command from a job dict.
runner_core.build_abaqus_full_run_command can build a command from a job dict.
```

Minimal changes needed:

```text
Expose a non-mutating JobRequest validation function.
Expose command preview without touching queue.json.
Add dry_run=True behavior to enqueue.
Add status lookup by queue_id.
Add output locator that includes .lck, .odb, .sta, .msg, .dat, .log.
Add JSON CLI output for AbqPilot.
```

## 7. Integration Risk Assessment

### Subprocess launch risk

Abaqus solver launch is mostly centralized in:

```text
D:\Projects\abqjobpilot_dev\abqjobpilot\runner_core.py
```

The dangerous call path is:

```text
QueueRunner.start()
QueueRunner._run_loop()
run_next_job(job)
_run_command(job, phase, command)
subprocess.Popen(...)
```

This is good because solver submission is not scattered across many modules.

GUI code also uses subprocess for non-solver actions such as Task Manager / shutdown-related utilities. Those should not be part of the AbqPilot interface.

### Path hardcoding

Runtime paths are currently project-relative through `config.py`, which is good for dev/stable copies.

The default Abaqus command remains workstation-specific:

```text
D:\ABAQUS2024\Commands\abq2024.bat
```

Settings can override the Abaqus command path, but AbqPilot should not rely on the hardcoded default.

### GUI / queue separation

Queue logic is reasonably separated in `queue_store.py`.

Agent Command execution is partly GUI-owned in `command_console.py`, because it applies GUI settings and writes output to widgets. This is not ideal for programmatic integration.

### Status storage stability

Status is machine-readable JSON, but not yet a stable public contract.

AbqPilot can technically read:

```text
runtime\queue.json
runtime\live_status.json
runtime\reports\manifest.json
runtime\reports\*.json
```

But this would couple AbqPilot to internal file shapes.

### Can AbqPilot use abqjobpilot without rewriting it?

Yes, but only with a small adapter layer and a few interface additions.

AbqPilot should not directly call GUI classes.

AbqPilot should not call `run_next_job` or `QueueRunner.start` during Stage 2.3.

AbqPilot should initially call only a dry-run/preflight API once it exists.

### Can AbqPilot use it today without importing GUI code?

Partially yes:

```text
parse_agent_command: yes
load_queue/result_jobs/queued_jobs: yes
monitor tails: yes
runner command builders: yes
```

But safe preflight is not available as a clean public function.

## 8. Recommended Interface Contract

Recommended minimal public interface:

```python
class AbqJobPilotClient:
    def preflight(self, request: JobRequest) -> JobPreflightResult:
        ...

    def enqueue(self, request: JobRequest, dry_run: bool = True) -> JobSubmitResult:
        ...

    def status(self, job_id: str) -> JobStatusResult:
        ...

    def locate_outputs(self, job_id: str) -> JobOutputResult:
        ...
```

Recommended request shape:

```json
{
  "inp_path": "...",
  "job_name": "...",
  "cpus": 14,
  "gpus": 0,
  "batch": "...",
  "strategy": "...",
  "working_dir": "...",
  "submission_mode": "preview_only",
  "allow_solver_submit": false
}
```

Recommended result shape:

```json
{
  "status": "PREVIEW_READY",
  "job_id": "...",
  "command_preview": "...",
  "working_dir": "...",
  "expected_odb_path": "...",
  "status_file": "...",
  "log_paths": [],
  "errors": [],
  "warnings": []
}
```

Recommended CLI contract:

```powershell
python -m abqjobpilot.cli preflight --json request.json
python -m abqjobpilot.cli enqueue --json request.json --dry-run
python -m abqjobpilot.cli status --job-id JOB_ID --json-output
python -m abqjobpilot.cli outputs --job-id JOB_ID --json-output
```

Safety rules for the CLI:

```text
Default submission_mode must be preview_only.
Default allow_solver_submit must be false.
enqueue --dry-run must not modify queue.json.
Real submit must require an explicit allow_solver_submit=true gate.
Status/output commands must never start Abaqus.
Datacheck commands must never include gpus.
```

## 9. Minimal Adaptation Plan

### Stage A: Interface audit only

Completed by this report.

### Stage B: Extract pure job request/status data models

Add simple standard-library data models, preferably dataclasses:

```text
JobRequest
JobPreflightResult
JobSubmitResult
JobStatusResult
JobOutputResult
```

Keep these independent of Tkinter.

### Stage C: Add dry-run preflight API

Extract current validation into a public non-mutating function.

Preflight should return:

```text
resolved job_name
resolved batch/strategy
working_dir
expected output paths
datacheck command preview
full-run command preview
errors
warnings
```

### Stage D: Add CLI JSON output

Add:

```text
D:\Projects\abqjobpilot_dev\abqjobpilot\cli.py
```

The CLI should support JSON request/response and useful exit codes.

Recommended exit codes:

```text
0: success
1: validation failed
2: not found
3: unsafe submit rejected
4: internal error
```

### Stage E: Add AbqPilot adapter in AbqPilot-v2

AbqPilot-v2 Stage 2.3 should initially generate previews only:

```text
abqjobpilot-ready request JSON
abqjobpilot Agent Command string preview
no enqueue
no solver submit
```

### Stage F: Add controlled submit gate with human approval

Only after preflight is stable:

```text
submission_mode=enqueue_only
allow_solver_submit=false
```

Later, real solver submit can be added only behind explicit human approval:

```text
submission_mode=submit
allow_solver_submit=true
```

## Inspection Commands Run

Safe commands run:

```powershell
dir
dir abqjobpilot
dir tests
dir runtime
dir docs
tree /F /A abqjobpilot
tree /F /A tests
rg -n "enqueue|submit|Popen|subprocess|os.system|abaqus|abq|odb|sta|msg|lck|status|queue|job_id|dry|preview" .
rg -n "^def |^class |add_argument|SUPPORTED_COMMANDS|DEFAULT_|STATUS_VALUES|ACTIVE_STATUSES|RESULT_STATUSES" abqjobpilot tests
rg -n "subprocess|Popen|run_next_job|QueueRunner|start_queue|add_inp_job_to_queue|add_folder_to_queue|parse_agent_command|build_abaqus|write_json|read_json|report|manifest" abqjobpilot tests
python -m pytest -q
```

Test result:

```text
16 passed in 0.33s
```

No Abaqus job was run by the tests.

## Final Recommendation

abqjobpilot is close to integration-ready, but it does not yet expose a stable AbqPilot-facing interface.

Current state:

```text
GUI app: usable
Internal Agent Command: usable
Python queue functions: usable but internal-contract quality
Structured JSON files: present
Stable public client API: missing
CLI JSON contract: missing
Dry-run/preflight API: missing
Status/output lookup API: missing
```

AbqPilot-v2 should not directly depend on GUI code or raw internal JSON file shapes.

Recommended next step:

```text
Stage B: Extract pure job request/status data models
Stage C: Add dry-run preflight API
Stage D: Add CLI JSON output
```

Final verdict:

```text
WARNING_ABQJOBPILOT_ADAPTATION_REQUIRED
```

## A1 Adaptation Status

Stage A1 adds a GUI-free public API layer under:

```text
D:\Projects\abqjobpilot_dev\abqjobpilot\api
```

Added public contract:

```text
JobRequest
JobPreflightResult
JobSubmitResult
JobStatusResult
JobOutputResult
AbqJobPilotClient
python -m abqjobpilot.api.cli
```

Safety status:

```text
preflight: read-only, no queue mutation, no Abaqus submit
enqueue dry-run: read-only, no queue mutation, no Abaqus submit
status: read-only
locate-outputs: read-only, does not open ODB
```

The API intentionally does not import GUI modules and does not start the queue runner.

Updated stage verdict:

```text
ABQJOBPILOT_STAGE_A1_PUBLIC_PREFLIGHT_API_READY
```

## A3 Automation Contract Status

A3 adds Automation Surface v1: runtime-scoped `preflight`, queue-only `enqueue`, `enqueue-folder`, `list`, `status`, `locate-outputs`, and read-only `capabilities`. The canonical queue record builder lives in `abqjobpilot/queue_store.py` and is shared by GUI/Agent Command and the public API. New queue JSON is versioned while legacy lists remain readable. Writes use a flushed, fsynced temporary file and atomic replacement plus a process-local queue lock; full cross-process writer safety is not claimed. Public JSON includes schema version and structured error details. The GUI remains the only solver-start entry point. See `docs/ABQJOBPILOT_PUBLIC_API.md` for the current contract; earlier sections above document historical audit findings before A1/A2/A3.
