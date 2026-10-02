# AbqJobPilot

A lightweight local job runner and monitoring tool for Abaqus.

AbqJobPilot is a Windows desktop application for organizing and monitoring batches of Abaqus INP jobs. It runs a local queue sequentially, shows current solver status and log tails, and keeps project-level history without taking ownership of your engineering files.

## Overview

Use the desktop dashboard to see the active job, execution-order queue, newest results, STA tail, console log, and local CPU/memory/GPU readings at once. English and Chinese UI modes are available.

## Key Features

- Add one INP or enqueue matching INP files from a folder.
- Run a datacheck before full analysis when enabled in Settings; process jobs sequentially.
- Start the queue from the GUI, or request **Stop After Current Job** without terminating the current solver process.
- Inspect Queue and Results side by side; search, filter, requeue, and use context actions for files and logs.
- View live STA and console tails; inspect STA, MSG, DAT, and LOG paths for a selected task in Task Details.
- Keep durable Job/Run attempt and artifact-path metadata in a formal Project's SQLite history.
- Export metadata archives or explicitly include files physically owned by a Project; import older runtime metadata.
- Use a JSON CLI, Python API, or the Agent Command Console for preparation, queueing, and inspection.

## Lightweight Project Model

A Project holds queue state, run history, metadata, and file references. It does **not** move your Abaqus files. New Projects default to the application's `projects/` folder, but you may choose any other location.

```text
Engineering workspace                    AbqJobPilot Project
D:\AbaqusProjects\Example\               <app-root>\projects\Example\
  model.cae                                 project.json
  model.inp                                 project.db
  model.odb                                 runtime\queue.json
  model.sta                                 runtime\live_status.json
```

The Job working directory remains the configured engineering workspace, normally the INP's directory. The Project database stores Job, Run, and artifact **metadata and paths only**; ODB and other solver files are never stored as SQLite BLOBs. Existing Projects outside `projects/` continue to work. Without a formal Project, the GUI can still use its local default runtime.

## Operational Dashboard

Queue shows the real execution order; Results shows the newest records first. The execution strip and home STA/console tails follow the current confirmed running job, not whichever historical result is selected. Open **View Details** or **View Logs** on a row to inspect that task separately. A historical log path may now contain a later attempt's file, so it is not an immutable snapshot.

## Installation / Requirements

- Windows with Python 3.10+ and Tkinter/ttk.
- A separately installed and licensed Abaqus command for actual solver execution.
- The core application currently has no third-party Python runtime dependencies; `requirements.txt` is intentionally empty.

```powershell
git clone https://github.com/BrunelXian/AbqJobPilot.git
cd AbqJobPilot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_gui.py
```

This runs the Python source with your environment; it does not build an EXE. In **Settings**, set the Abaqus command for your workstation and review CPU/GPU and datacheck/full-run defaults before starting a queue. The example paths here are illustrative, not configured defaults.

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

Version 0.2.1 lets local scripts and coding agents manage formal Project metadata and query Job/Run history through the same JSON CLI and Python API. Use an explicit `--project-id` or `--project` path to target a Project. Omitting a selector preserves the existing default runtime; it never silently selects the most recent Project.

```powershell
python -m abqjobpilot.api.cli project list --json
python -m abqjobpilot.api.cli project create --name "Example Study" --json
python -m abqjobpilot.api.cli project show --project-id "<uuid>" --json
python -m abqjobpilot.api.cli job list --project-id "<uuid>" --status FAILED --json
python -m abqjobpilot.api.cli enqueue --project-id "<uuid>" --inp "D:\AbaqusProjects\Example\model.inp" --json
```

`project register` adds an existing Project to the recent-project registry. `project unregister` removes that registration only: the Project directory, database, runtime, and external engineering files remain untouched. `project update --name` changes the display name, not the directory name. Export defaults to a metadata archive; `--mode project-owned` explicitly includes files physically inside the Project root, never referenced external files.

Automation tools should call AbqJobPilot's CLI or Python API, **not edit** `project.json`, `project.db`, `runtime/queue.json`, or `runtime/live_status.json` directly. They should not move or delete external engineering files or attempt solver execution through undocumented paths. See [Project Automation Surface v1](docs/ABQJOBPILOT_A4_PROJECT_AUTOMATION.md).

## Agent Command Console

The Console accepts an allow-listed internal command syntax such as `enqueue`, `enqueue-folder`, `list`, `help`, and `clear`. It is **not** a PowerShell or system-shell window. Its AI Instruction can be copied to a coding assistant to generate compatible command text.

External tools such as Codex, Claude Code, or another tool-using assistant can call the JSON CLI/Python API or prepare text for the Console. This is a general machine-readable interface, not an official integration with any assistant.

## Data and File Ownership

CAE, INP, ODB, STA, MSG, DAT, LOG, and other engineering files normally stay in their original workspace. Queueing, viewing, history projection, and ordinary Project import do not relocate them. An explicit archive may copy Project-owned files, never silently gather referenced external files. File existence alone is not proof of a valid solver result.

## Safety Boundaries

Agent Command accepts internal commands only; it does not execute arbitrary shell text. Preflight and dry-run do not run Abaqus. Queue and Results record deletion does not delete engineering files or the database's durable run history. AbqJobPilot is a local single-machine tool, not a distributed scheduler or AI runtime.

## Repository Structure

| Path | Purpose |
| --- | --- |
| `abqjobpilot/gui_app.py` | Tkinter dashboard and user actions |
| `abqjobpilot/runner_core.py` | Existing local Abaqus runner |
| `abqjobpilot/queue_store.py` | JSON queue/control state |
| `abqjobpilot/project/` | Project manifests and portable archives |
| `abqjobpilot/database/` | Per-Project historical metadata |
| `abqjobpilot/api/` | Safe Python API and JSON CLI |
| `docs/` | Detailed contracts and design notes |

## Current Version

Current version: **0.2.1**. AbqJobPilot is actively developed; the application version is defined in `abqjobpilot/__init__.py`. Run non-solver tests with `python -m pytest -q` if pytest is available.

## License

[MIT License](LICENSE).
