# AbqJobPilot

A lightweight local job runner and monitoring tool for Abaqus.

AbqJobPilot is a Windows desktop application for organizing and monitoring batches of Abaqus INP jobs. It runs a local queue sequentially, shows solver status and log tails, and keeps Project-level history without taking ownership of engineering files. Its Agent-ready interfaces let external tools prepare, inspect, and (through the public CLI/API or in-GUI Console) enqueue work; they do not make AbqJobPilot an autonomous CAE agent.

## Overview

Use the desktop dashboard to see the active job, execution-order queue, newest results, STA tail, console log, and local CPU/memory/GPU readings at once. English and Chinese UI modes are available.

**Version and branch:** the checked `main` release checkout and local `origin/main` report **0.1.0**. The `Develop` branch reports **0.2.2.dev0**. The features below describe **Develop** unless explicitly stated otherwise; in particular, MCP and native process-evidence persistence are development features, not claims about `main`. Check the version in your own checkout before relying on a feature. The repaired native process tracker still awaits its final real-Abaqus end-to-end acceptance.

## Key Features

- Add one INP or enqueue matching INP files from a folder.
- Run a datacheck before full analysis when enabled in Settings; process jobs sequentially.
- Start the queue from the GUI, or request **Stop After Current Job** without terminating the current solver process.
- Inspect Queue and Results side by side; search, filter, requeue, and use context actions for files and logs.
- View live STA and console tails; inspect STA, MSG, DAT, and LOG paths for a selected task in Task Details.
- Keep durable Job/Run attempt and artifact-path metadata in a formal Project's SQLite history.
- Capture best-effort launcher/child process identity evidence per run phase in `Develop`; use PID plus Windows creation time when available. This is not a guarantee of complete solver lineage.
- Export metadata archives or explicitly include files physically owned by a Project; import older runtime metadata.
- Use the JSON CLI, Python API, or Agent Command Console for preparation, queueing, and inspection. An optional Project-bound MCP adapter provides five read-only/preview tools in `Develop`.

## Lightweight Project Model

A Project holds queue state, run history, metadata, and file references. It does **not** move your Abaqus files. New Projects default to `~/.abqjobpilot/projects/`, outside the source/install directory. Basic Settings can change this default to another directory outside the application tree; you can also choose a different parent when creating or importing an individual Project. Existing Projects are not moved.

```text
Engineering workspace                    AbqJobPilot Project
D:\AbaqusProjects\Example\               <user-home>\.abqjobpilot\projects\Example\
  model.cae                                 project.json
  model.inp                                 project.db
  model.odb                                 runtime\queue.json
  model.sta                                 runtime\live_status.json
```

The Job working directory remains the configured engineering workspace, normally the INP's directory. The Project database stores Job, Run, and artifact **metadata and paths only**; ODB and other solver files are never stored as SQLite BLOBs. Existing Projects anywhere, including an older application-local `projects/`, continue to work. Without a formal Project, a new installation uses a per-installation runtime under `~/.abqjobpilot/installations/`. If an older application-local `runtime/` already has queue/status/settings or report data, that installation continues to use it rather than silently treating its jobs as a fresh queue. Choose separate Projects for stable and development builds; do not operate the same active Queue from both versions.

## Operational Dashboard

Queue shows the real execution order; Results shows the newest records first. The execution strip and home STA/console tails follow the current confirmed running job, not whichever historical result is selected. Open **View Details** or **View Logs** on a row to inspect that task separately. A historical log path may now contain a later attempt's file, so it is not an immutable snapshot.

## Installation / Requirements

- Windows with Python 3.10+ and Tkinter/ttk for the source GUI. The development MCP protocol tests were run with Python 3.12.10 and the official MCP SDK 2.3.0; other interpreter/SDK combinations are not claimed as tested here.
- A separately installed and licensed Abaqus command for actual solver execution.
- The core application has no declared third-party runtime packages (`requirements.txt` is intentionally empty). MCP is optional; `requirements-mcp.txt` declares `mcp>=2,<3`.

For the stable `main` checkout:

```powershell
git clone https://github.com/BrunelXian/AbqJobPilot.git
cd AbqJobPilot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_gui.py
```

For the development features described below, clone the `Develop` branch instead:

```powershell
git clone --branch Develop https://github.com/BrunelXian/AbqJobPilot.git
cd AbqJobPilot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_gui.py
```

These commands run source code, not a packaged EXE. In **Settings**, configure the Abaqus command for your workstation and review CPU/GPU and datacheck/full-run defaults before starting a queue. No public example assumes a particular local Abaqus installation path. The GUI and non-MCP CLI do not need the MCP SDK.

## Quick Start

1. Run `python run_gui.py`.
2. Optionally create or open a Project. Existing external Project folders are supported.
3. Choose **Add Task** to add an INP or a folder, then inspect the Queue.
4. Click **Start Queue** to begin local execution. **Stop After Current Job** lets the active job finish.
5. Monitor the execution strip, STA/console tails, Results, and Task Details.

Adding a task while a queue runner is already active may let that runner pick up the new item. The public automation interface itself never exposes a solver-start command.

## Project Workflow

Project actions include New, Open, Recent, Close, Export, Import, and Import Legacy Runtime. Recent Projects is application-level navigation for Projects anywhere; it is not the default storage folder.

- **Metadata Archive** (default): Project manifest, database/history when present, and runtime metadata.
- **Archive with Project-Owned Files** (explicit): also includes files physically inside the Project root. Large project-owned solver files may make this archive large.
- Files referenced outside the Project root are not silently copied in either mode. Legacy runtime import copies metadata/history into a new Project, leaving the legacy source unchanged.

## Automation Interface

The thin public interface supports capabilities, preflight, enqueue/enqueue-folder, queue list, status, output discovery, Project management, and read-only Job history. Use `--json` for machine-readable output; `enqueue` defaults to a dry run. Use `--enqueue-only` to write queue metadata without directly starting Abaqus.

```powershell
python -m abqjobpilot.api.cli capabilities --json
python -m abqjobpilot.api.cli preflight --inp "D:\AbaqusProjects\Example\model.inp" --cpus 14 --json
python -m abqjobpilot.api.cli enqueue --inp "D:\AbaqusProjects\Example\model.inp" --dry-run --json
python -m abqjobpilot.api.cli status --job-id "QUEUE_ID" --json
python -m abqjobpilot.api.cli locate-outputs --job-id "QUEUE_ID" --json
```

The public automation interface does not expose solver start. Actual execution remains controlled by the desktop application's **Start Queue** workflow. See [the public API guide](docs/ABQJOBPILOT_PUBLIC_API.md) for request fields, runtime selection, and Python API examples.

## Project Automation

The public CLI and Python API let local scripts and coding agents manage formal Project metadata and query Job/Run history. Use an explicit `--project-id` or `--project` path to target a Project. Omitting a selector preserves the existing default runtime; it never silently selects the most recent Project.

```powershell
python -m abqjobpilot.api.cli project list --json
python -m abqjobpilot.api.cli project create --name "Example Study" --json
python -m abqjobpilot.api.cli project show --project-id "<uuid>" --json
python -m abqjobpilot.api.cli job list --project-id "<uuid>" --status FAILED --json
python -m abqjobpilot.api.cli enqueue --project-id "<uuid>" --inp "D:\AbaqusProjects\Example\model.inp" --json
```

`project register` adds an existing Project to the recent-project registry. `project unregister` removes that registration only: the Project directory, database, runtime, and external engineering files remain untouched. `project update --name` changes the display name, not the directory name. Export defaults to a metadata archive; `--mode project-owned` explicitly includes files physically inside the Project root, never referenced external files.

Automation tools should call AbqJobPilot's CLI or Python API, **not edit** `project.json`, `project.db`, `runtime/queue.json`, or `runtime/live_status.json` directly. They should not move or delete external engineering files or attempt solver execution through undocumented paths. See [Project Automation Surface v1](docs/ABQJOBPILOT_A4_PROJECT_AUTOMATION.md).

## Agent Integration & MCP (Development)

Three interfaces share Project and Queue services but have different permissions:

| Interface | How to use it | Capability |
| --- | --- | --- |
| **Agent Command Console** | Open **Agent Command** in the GUI; paste allow-listed AbqJobPilot commands. | Project selection, preparation, queue-only enqueue, and inspection. No system shell or solver-start command. |
| **Python API / JSON CLI** | Import `AbqJobPilotClient` or run `python -m abqjobpilot.api.cli ... --json`. | Project management, preflight, dry-run, explicit queue-only enqueue, status, outputs, Job/Run queries. No public solver start. |
| **MCP server** | An MCP client launches `python -m abqjobpilot.mcp.server --project "<Project folder>"` over **stdio**. | Five Project-bound read-only/preview tools. No actual enqueue, runner control, HTTP service, or solver start. |

To use MCP in a separate development virtual environment, first check out `Develop` as above, then install its **optional** dependency:

```powershell
python -m pip install -r requirements-mcp.txt
python -m abqjobpilot.mcp.server --help
```

Configure your MCP client to launch the server from the source checkout (replace both placeholder paths; the Project must already contain `project.json`):

```json
{
  "mcpServers": {
    "abqjobpilot-readonly": {
      "command": "C:\\path\\to\\AbqJobPilot\\.venv\\Scripts\\python.exe",
      "args": ["-m", "abqjobpilot.mcp.server", "--project", "C:\\CAE\\ExampleManager"],
      "cwd": "C:\\path\\to\\AbqJobPilot"
    }
  }
}
```

Clients differ in their configuration keys; this is the common `mcpServers` stdio shape, **not** a claim of verified integration with a specific vendor GUI. `cwd` must be the checkout root (or the package must otherwise be importable), and the chosen Python interpreter must contain the official MCP SDK v2. The server binds to **one explicit formal Project** at startup; it does not choose the latest Project or follow a later GUI Project switch. Launch a separate server process for another Project.

| MCP tool | Inputs | What it actually does |
| --- | --- | --- |
| `abq_preflight` | `inp_path`; optional `job_name`, `cpus`, `gpus`, `working_dir`, `batch`, `strategy` | Validates and previews a request; **not** Abaqus datacheck. |
| `abq_list_jobs` | `scope=queue\|history` (default `queue`); optional `status`, `batch`, `strategy`, `limit` | Lists queue IDs or logical history Job IDs; default limit 50, cap 100. |
| `abq_job_status` | `scope` (`queue` or `history`), `identifier` | Reads stored status. A stored RUNNING state alone does not prove an active process. |
| `abq_locate_outputs` | Exactly one of `queue_id` or `inp_path` | Reports expected/recorded file paths and existence, not ODB validity. |
| `abq_prepare_enqueue` | Same request fields as `abq_preflight` | Calls **dry-run only**; neither queue nor runner nor solver is started. |

Responses carry `schema_version`, `status`, `project_id`, `data`, `errors`, `warnings`, and `error_details`. MCP `abq_prepare_enqueue` is **not** the CLI's `--enqueue-only`: the latter explicitly writes a queue record, while MCP only previews. **Enqueue is not execution** in either interface. Actual execution remains under the GUI's **Start Queue** path.

If a client cannot connect, check the interpreter and SDK version, source `cwd`, formal Project path, and stderr from server startup; do not send explanatory text over stdio stdout. If a call is rejected, inspect `errors`/`error_details`, use the exact required `scope` and identifier type, and remember that external INP paths must be accessible to the server process. The adapter was tested with the official SDK's real stdio client (`initialize`, tool listing, calls, and argument errors), **not** with every Codex/Claude/other client UI. See [MCP setup, response contract, and safety](docs/ABQJOBPILOT_MCP.md).

## Agent Command Console

The Console accepts allow-listed internal commands: `project list`, `project create`, `project use`, `project show`, `enqueue`, `enqueue-folder`, `list`, `status`, `outputs`, `help`, and `clear`. It is **not** a PowerShell or system-shell window. Its AI Instruction can be copied to a coding assistant to generate compatible command text. Queue and inspection commands require a selected formal Project; `project use` changes only the Console target, never the live GUI Project. An explicit `--project` on a task command overrides the Console target for that command. An active or unconfirmed runner blocks Console enqueue; folder enqueue previews all matching requests and requires confirmation.

For example, in the Console:

```text
project use --project "Example Study"
enqueue --inp "D:\AbaqusProjects\Example\model.inp"
list
status --job-id "QUEUE_ID"
outputs --job-id "QUEUE_ID"
```

The JSON CLI/Python API remains a separate public automation interface and retains its existing default-runtime behavior. The optional MCP server remains Project-bound and **read-only**; a Console enqueue becomes visible through MCP when both target the same Project. None of these interfaces adds solver start or autonomous execution.

External tools such as Codex, Claude Code, or another tool-using assistant can call the JSON CLI/Python API or prepare text for the Console. This is a general machine-readable interface, not an official integration with any assistant.

## Data and File Ownership

CAE, INP, ODB, STA, MSG, DAT, LOG, and other engineering files normally stay in their original workspace. Queueing, viewing, history projection, and ordinary Project import do not relocate them. An explicit archive may copy Project-owned files, never silently gather referenced external files. File existence alone is not proof of a valid solver result.

## Safety Boundaries

Agent Command accepts internal commands only; it does not execute arbitrary shell text. Preflight and dry-run do not run Abaqus. Queue and Results record deletion does not delete engineering files or the database's durable run history. The local Runner, not MCP, owns Abaqus execution.

In `Develop`, runtime queue operations use an OS-backed transaction lock and a single-runner ownership lock. Process evidence uses PID **and** Windows creation time when available, but short-lived/detached children may escape sampling and access errors remain uncertain. A launcher exit or existing ODB alone does not prove that every solver process exited or that the analysis is valid. Recovery does not silently requeue, delete `.lck`, or retry without evidence. JSON runtime/report files and SQLite history are **not one cross-file atomic transaction**; reconciliation and explicit projection-error reporting cover detectable partial failures. The repaired native evidence path still needs a final one-job real-Abaqus end-to-end acceptance. AbqJobPilot is a local single-machine tool, not a distributed scheduler or AI runtime.

## Architecture and Development

```text
GUI / Agent Command / Python API / JSON CLI / read-only MCP
                    -> explicit Project context
                    -> Queue control state -> GUI Start Queue -> Runner
                    -> phase process evidence + reports -> SQLite Run history
```

Only the GUI Start Queue workflow invokes the Runner. Queue JSON remains active control state; `live_status.json` is observation; `project.db` is durable metadata/history. External CAE, INP, ODB, and solver logs stay in their engineering workspace. Development occurs on `Develop`; `main` is the release branch. Contributors should use disposable Projects/INPs for tests, run `python -m pytest -q` in an environment with pytest installed, and review [Project ownership](docs/ABQJOBPILOT_PROJECT_MODEL.md), [runtime coordination](docs/ABQJOBPILOT_RUNTIME_COORDINATION.md), [MCP](docs/ABQJOBPILOT_MCP.md), and the [Run 006 manual acceptance plan](docs/mcp/run_006/FINAL_SANITY_REVIEW_PLAN.md) before touching execution or recovery behavior. Do not commit local `projects/`, runtime locks, solver output, or personal configuration.

## Repository Structure

| Path | Purpose |
| --- | --- |
| `abqjobpilot/gui_app.py` | Tkinter dashboard and user actions |
| `abqjobpilot/runner_core.py` | Existing local Abaqus runner |
| `abqjobpilot/queue_store.py` | JSON queue/control state |
| `abqjobpilot/project/` | Project manifests and portable archives |
| `abqjobpilot/database/` | Per-Project historical metadata |
| `abqjobpilot/api/` | Safe Python API and JSON CLI |
| `abqjobpilot/mcp/` | Optional, read-only Project-bound stdio MCP adapter |
| `docs/` | Detailed contracts and design notes |

## Current Version

Development version: **0.2.2.dev0**; checked local `main` version: **0.1.0**. The authoritative application version is in `abqjobpilot/__init__.py`; this README describes the `Develop` checkout. The live GitHub state may change after this documentation is written.

## License

[MIT License](LICENSE).
