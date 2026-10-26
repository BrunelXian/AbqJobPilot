<div align="center">

# AbqJobPilot

**Abaqus Job Queue, Project History & Agent-Ready Execution Workstation**

A local Windows desktop application for submitting and monitoring Abaqus `.inp` jobs, preserving run evidence, and exposing controlled automation interfaces for engineering workflows.

**English** · [简体中文](README_CN.md) · [Development branch](https://github.com/BrunelXian/AbqJobPilot/tree/Develop) · [Stable branch](https://github.com/BrunelXian/AbqJobPilot/tree/main)

[![Platform: Windows](https://img.shields.io/badge/platform-Windows-607D8B)](#installation)
[![Interface: Tkinter](https://img.shields.io/badge/interface-Tkinter-5A70A6)](#interface)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](#installation)
[![Abaqus: INP Queue](https://img.shields.io/badge/Abaqus-INP%20queue-2A9D8F)](#core-workflows)
<br>
[![MCP: Development](https://img.shields.io/badge/MCP-5%20preview%2Fread--only%20tools-7B61A8)](#agent-integration--mcp-development)
[![Status: Development](https://img.shields.io/badge/branch-Develop-E9A23B)](#release-channels)
[![License: MIT](https://img.shields.io/badge/license-MIT-4B8F72)](LICENSE)

</div>

## Overview

Abaqus parameter studies and simulation batches are often managed through separate command windows, manually inspected solver logs, and loose collections of result files. **AbqJobPilot** brings the operational parts together: a sequential job queue, live status and resource monitoring, Project-scoped run history, and a conservative execution/recovery model.

Its **Agent-ready** interfaces let an external coding assistant or automation script validate a request, inspect Jobs, locate outputs, and—with explicit queue-only APIs—prepare a queue. **AbqJobPilot is not an autonomous CAE agent**, and its current MCP server cannot enqueue Jobs or start Abaqus.

This README describes the **`Develop` branch (`0.3.0.dev0`)**. Features and validation boundaries differ from the stable `main` branch; see [Release Channels](#release-channels).

`0.3.0.dev0` remains a development version. The independent ExecutionService now supports Fake, fixed Python ProcessFixture, and a restricted Abaqus 2024 Standard backend. [Run016 recorded acceptance](docs/agent_first/run_016/real_001/FINAL_SUMMARY.md) covers two fixed axial-bar analyses, managed-scope completion, DAT checks, and GUI reconnect. It does not validate general Abaqus modes, ODB contents, production migration, or release 0.3.0. See the [Run017 product baseline](docs/agent_first/run_017/FINAL_SUMMARY.md) for current boundaries.

The default `run_gui.py` opens the Compact Engineering Cockpit (Queue left, Results right, persistent dual logs). On the registered Dev host, double-click `Open_Dev_GUI.vbs`, create or explicitly select a supported Project, then use **Agent Command → Project & Service → Start Service** or **Reconnect** and select a Run. Opening, reconnecting or closing the view never grants execution, submits a Run or resumes dispatch. Service start and safe idle stop are explicit operations using the separate lifecycle capability. Existing incompatible or uncertain owners are not replaced. The **Classic Queue** button (or `run_gui.py --legacy`) opens the separate Classic workflow; it is not a second view of the service's execution database. See [Run020 usage](docs/agent_first/run_020/USAGE.md).

**New Project** and the shared `create_project / open_project` Python API create an empty PAUSED Project, without Grants, Runs or automatic service start. Local IPC/operator material uses current-user Windows protection; copied/moved Projects cannot silently connect to their original owner. Run021B adds a separately provisioned, exact fixed-Standard operator capability and a server-enforced one-Run dispatch window; connection or TEST_ONLY permissions cannot approve real execution. This is a trusted local operator boundary, not a general human-approval UI or OS isolation from arbitrary code running as the same user. [Run021B real acceptance](docs/agent_first/run_021b/real_001/FINAL_SUMMARY.md) records one analysis, managed completion, DAT checks and safe stop/restart; its Solver-across-GUI-exit observation remains **NOT_OBSERVED**, and the report remains PARTIAL. See [Run022 scope/evidence](docs/agent_first/run_022/RC_SCOPE_AND_EVIDENCE.md) and [Project/credential boundaries](docs/agent_first/run_020/PROJECT_AND_CREDENTIAL_CONTRACT.md).

English is the default display language; saved Chinese preferences remain supported. French and German remain **Preview**. Managed-scope completion does not prove domain-external process completeness (**UNKNOWN**); ODB content validation remains **NOT_RUN**. The VBS and service launcher currently require the registered Dev interpreter; the generic setup below does not establish portable service-host support.

## Interface

<div align="center">
  <a href="sample.png"><img src="sample.png" alt="AbqJobPilot desktop queue and monitoring dashboard" width="95%"></a>
</div>

*Archived screenshot of an earlier interface, not the current Develop dashboard. Its sample job data is not a current run or a validation result. A current screenshot is still needed.*

The dashboard is designed around one question: **what is running, what is waiting, and what evidence exists for each completed attempt?** Queue ordering, result inspection, STA/console tails, and local resource readings are available within the same desktop workflow.

## Highlights

The first row is the new service path. The queue, archive and command-console rows describe the separate Classic workspace; they do not widen the fixed Standard service contract.

| Area | What is available in Develop |
| --- | --- |
| **Agent-first Execution MVP** | Explicit Project, authenticated independent Supervisor, public Python client, exact approval/one-shot dispatch, fixed Standard managed scope, separate Solver/DAT evidence, GUI observation and safe idle lifecycle. Restricted to the documented host/model; no general Solver approval UI. |
| **Job Queue** | Add an INP or discover INPs from a folder; configure CPU/GPU and optional datacheck, then run sequentially from the GUI. |
| **Live Operations** | View active phase, job status, STA/console tails, CPU/memory/GPU readings, and result-file locations. |
| **Safe Control** | Stop *after* the current Job; keep runner ownership, output collisions, and uncertain interruptions explicit. |
| **Projects** | Project-local queue, SQLite Job/Run history, reports, and artifact-path references—without moving solver files. |
| **Execution Evidence** | Best-effort launcher/child process identities for datacheck and full-run, with evidence retained after terminal status; legacy evidence limits remain; fixed service acceptance is documented separately in Run016. |
| **Portability** | Metadata-focused Project export/import; optional inclusion of files physically owned by a Project. |
| **Agent Command** | A compact GUI console for allow-listed internal commands, multiline input, and readable execution summaries. |
| **Automation & MCP** | Python API/JSON CLI for controlled operations; optional Project-bound stdio MCP with five read-only/preview tools. |

## Quick Start

**For the current development features**, open Windows PowerShell with Python 3.10+ and Tkinter available:

```powershell

git clone --branch Develop https://github.com/BrunelXian/AbqJobPilot.git
cd AbqJobPilot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_gui.py
```

For the default product view:

1. Select **New Project** and an explicit new directory/name, or select a supported existing Project.
2. In **Agent Command → Project & Service**, explicitly select **Start Service** for an empty supported Project, or **Reconnect** for its existing owner. A new Project remains PAUSED and has no execution authorization.
3. Select an existing Run to read state, bounded logs, process scope, Solver and validation evidence. The GUI does not create real Grants or submit analyses.
4. Closing the GUI disconnects observation. **Stop Service** is a separate explicit action and is refused for active or unresolved execution.

The fixed Standard operator workflow is documented in [Run021B usage](docs/agent_first/run_021b/USAGE.md). Its historical acceptance commands are not permission to repeat that experiment. New real execution requires a new, reviewed fixed Plan and explicit approval. Existing TEST_ONLY examples remain test harnesses.

For the **Classic / Legacy queue** only, first choose **Classic Queue** or launch `python run_gui.py --legacy`, then:

1. Open **Settings** and set the Abaqus command provided by your licensed installation. Review CPU/GPU and datacheck settings.
2. Create or open a **Project** (recommended); a Project may reference Abaqus models in any engineering folder.
3. Use **Add Task** to select a `.inp` or scan a folder. Review the Queue before execution.
4. Click **Start Queue** to run the queued Jobs sequentially. **Stop After Current Job** does not kill the active solver.
5. Review **Results**, log/STA tails, task details, and the Project's retained run history.

**Adding/queueing a Job is not the same as starting Abaqus.** A real solver run requires a valid Abaqus installation and license. The legacy Python/JSON CLI and MCP do not include a solver-start operation. The separate experimental Python client can submit only a service-bound, precisely authorized plan.

For source setup and Project behavior, see [Installation](#installation) and [Project Model](#project-model--data-ownership).

## Installation

| Requirement | Details |
| --- | --- |
| OS | Windows desktop |
| Python | Classic source GUI declares 3.10+; the Agent-first product path is currently verified and bound to registered LangChainEnv / Python 3.12.10 on the documented Windows host, not an arbitrary new venv |
| GUI | Tkinter/ttk (Python standard library, when included in your installation) |
| Abaqus | Separately installed and licensed; required only for actual solver runs |
| Core packages | `requirements.txt` currently declares no third-party runtime dependencies |
| Optional MCP | `requirements-mcp.txt` (`mcp>=2,<3`); validated with MCP SDK 2.3.0 in development testing |

These commands launch from **source**, not an installer. A fresh generic venv has not passed the full product lifecycle acceptance. `Open_Dev_GUI.vbs` and the product lifecycle currently bind `D:\XianLab\envs\LangChainEnv`; portable interpreter configuration is a release gate, not automatic discovery. Classic Settings configures the legacy Runner only. The restricted service Backend pins its own reviewed Abaqus 2024 entry, input bytes and CPU1/GPU0/2048MB policy; it does not use Classic Settings. Keep stable and Dev installations and active data separate.

## Core Workflows

```text
A · Human-operated Abaqus batch
Project → Add/validate INPs → Queue → GUI Start Queue
                                   ├─ Datacheck (optional)
                                   └─ Full run
                → STA/MSG/DAT/LOG/ODB → Results + Run History

B · Scripted preparation
External script / Agent → JSON CLI or Python API
                        → Preflight / Dry-run / Explicit queue-only enqueue
                        → Human-controlled GUI Start Queue

C · MCP-assisted inspection (Develop)
MCP client → Project-bound stdio server
           → Preflight / List / Status / Locate outputs / Prepare (dry-run)
           → No enqueue and no solver-start tool
```

**For this legacy API/MCP path, execution authority remains with the GUI Runner.** The independent Agent-first service is a separate authority over its experimental store; these stores must not be treated as interchangeable. The API's `--enqueue-only` can add queue metadata; the MCP tool named `abq_prepare_enqueue` is more restrictive and **never** writes a queue entry.

## Project Model & Data Ownership

The diagram and archive/default-directory behavior below describe **Classic Projects**. New Agent-first product Projects instead require an explicit new root, publish `agent_project.json`, use `project/execution.sqlite3` (execution format 3), and keep protected local credentials separately under that root. Do not open them with the Classic database writer or export them using the Classic archive contract. Moving/copying an Agent-first product Project requires future explicit reconfiguration; automatic migration/rebinding is not implemented.

**Project owns its operational data; the engineering workspace owns the solver files.** AbqJobPilot discovers, opens, and operates Projects, while its application-level recent-project list stores navigation metadata rather than run history. It tracks paths instead of collecting large ODB/CAE files into an application database.

```text
Engineering workspace                     AbqJobPilot Project
D:\Engineering\Study01\                  ~\.abqjobpilot\projects\Study01\
  model.cae                                  project.json
  model.inp                                  project.db  (lazy SQLite history)
  model.odb                                  runtime\queue.json
  model.sta                                  runtime\live_status.json
  model.msg                                  runtime\reports\
  model.dat                                    process_evidence\<queue_id>.json
  model.log
```

New Projects default to **`~/.abqjobpilot/projects/`**, outside the source repository; this parent folder is configurable in **Basic Settings**. Existing Projects are not moved. Project import/export preserves explicit ownership boundaries, while references to engineering files outside the Project remain external.

Without a formal Project, new installations use a per-installation runtime under `~/.abqjobpilot/installations/`. Existing application-local runtime data is still honored for backward compatibility instead of silently hiding prior Jobs. **Do not point stable and development builds at the same active Project/Queue.**

The Project database records metadata, Job/Run attempts, and artifact **paths**, not solver-file BLOBs. Moving a Project folder does not automatically relocate referenced external INPs or ODBs; those paths may require reconciliation.

Project export defaults to a **Metadata Archive**. The explicit **Archive with Project-Owned Files** mode adds files physically inside the Project root, but neither mode silently collects externally referenced engineering files. Legacy runtime import is metadata-first and leaves its source files in place. A historical log path may now contain a later attempt's file rather than an immutable snapshot.

Read the [Project model and ownership contract](docs/ABQJOBPILOT_PROJECT_MODEL.md) and [Project database documentation](docs/ABQJOBPILOT_PROJECT_DATABASE.md).

## Agent Integration & MCP (Development)

There are **three distinct interfaces**, with different execution permissions:

This table describes the Classic automation surface. The separate `abqjobpilot.execution.client` and `ServiceLifecycleManager` serve Agent-first Projects through authenticated IPC. MCP's five tools and the JSON CLI have not been upgraded to service write/real-approval tools.

| Interface | Typical user | Supported boundary |
| --- | --- | --- |
| **Agent Command Console** | An engineer pasting AI-generated internal commands | Project selection, inspection, queue-only enqueue. Not a shell. |
| **Python API / JSON CLI** | Scripts and coding agents | Project management, preflight, status, dry-run, explicit queue-only enqueue, outputs, history. |
| **MCP server (stdio)** | MCP-compatible clients | Five tools for a single explicit Project. Read-only or preview-only; **cannot enqueue**. |

### Agent Command Console

The in-GUI Console includes compact copyable AI instructions, a multiline command editor, and summary-first Output with full details on demand. Example internal commands:

```text
project list
project use --project "Example Study"
enqueue --inp "D:\Engineering\Study01\model.inp" --cpus 4 --gpus 0
list
status --job-id "QUEUE_ID"
outputs --job-id "QUEUE_ID"
```

It does **not** run arbitrary CMD/PowerShell, and `project use` changes the **Console target**—not the Project currently selected in the main GUI. A queued item does not mean the solver has started.

### Python API / JSON CLI

```powershell
python -m abqjobpilot.api.cli capabilities --json
python -m abqjobpilot.api.cli project create --name "Example Study" --path "C:\CAE\ExampleManager" --json
python -m abqjobpilot.api.cli project list --json
python -m abqjobpilot.api.cli preflight --project "C:\CAE\ExampleManager" --inp "D:\Engineering\Study01\model.inp" --cpus 4 --json
python -m abqjobpilot.api.cli enqueue --project "C:\CAE\ExampleManager" --inp "D:\Engineering\Study01\model.inp" --dry-run --json
python -m abqjobpilot.api.cli status --project "C:\CAE\ExampleManager" --job-id "QUEUE_ID" --json
python -m abqjobpilot.api.cli locate-outputs --project "C:\CAE\ExampleManager" --job-id "QUEUE_ID" --json
```

The `project create` example requires a destination that does not already exist; `QUEUE_ID` is a placeholder returned by a real queue record. To actually write a queue entry, use `--enqueue-only` with an intentional `--project` or `--project-id` selector. This writes queue metadata only; a running GUI Runner may subsequently pick up newly queued work. Without a selector, the CLI retains its legacy default-runtime behavior rather than choosing the latest Project. There is **no public CLI solver-start command**. See [Python/JSON API](docs/ABQJOBPILOT_PUBLIC_API.md) and [Project Automation](docs/ABQJOBPILOT_A4_PROJECT_AUTOMATION.md) for exact selectors and response contracts.

### MCP server: install and connect

MCP is **optional and currently a development feature**. In the activated `Develop` environment:

```powershell
python -m pip install -r requirements-mcp.txt
python -m abqjobpilot.mcp.server --help
```

The actual server launch command below opens a stdio session and waits for an MCP client; it does not start Abaqus:

```powershell
python -m abqjobpilot.mcp.server --project "C:\CAE\ExampleManager"
```

Configure a compatible client to launch the Project-bound server over stdio (replace the placeholders with actual local paths):

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

The selected Project must already exist and contain `project.json`. Client-specific configuration keys may vary; the generic JSON above is **not** a claim of verified setup in every vendor application. The Python executable must have the official MCP SDK v2 installed. A second Project requires a separate server process.

| MCP tool | Main inputs | Actual capability |
| --- | --- | --- |
| `abq_preflight` | `inp_path`; optional `job_name`, `cpus`, `gpus`, `working_dir`, `batch`, `strategy` | Validate and preview an INP request; **not** Abaqus datacheck. |
| `abq_list_jobs` | `scope=queue\|history`; optional filters and `limit` | List queue records or Project Job history; default limit 50, cap 100. |
| `abq_job_status` | `scope`, `identifier` | Read recorded status; an old `RUNNING` value alone does not prove process liveness. |
| `abq_locate_outputs` | Exactly one of `queue_id` or `inp_path` | Locate expected/recorded output paths; file existence does not prove ODB validity. |
| `abq_prepare_enqueue` | Same request fields as `abq_preflight` | **Dry-run only**. Does not mutate the queue or start a runner/solver. |

MCP tests cover stdio initialization, tool enumeration, calls, and invalid arguments using the official SDK. This is not a guarantee of end-to-end integration with each third-party MCP client. For input arguments, response schema, and troubleshooting, see the [MCP guide](docs/ABQJOBPILOT_MCP.md).

## Execution Evidence & Safety

AbqJobPilot is designed to distinguish **what was requested**, **what was recorded**, and **what has actually been verified**:

- The legacy GUI Runner controls legacy queue execution. The new Python client submits authorized plans to an independent Supervisor; neither client nor read-only service GUI owns the Solver lifecycle.
- Datacheck and full-run keep distinct execution phases and best-effort native process evidence.
- Process identity uses Windows **PID + creation time** when available; a PID by itself can be reused. Child relationships need actual supporting evidence.
- Evidence files may be stored under `runtime/reports/process_evidence/<queue_id>.json`, with references retained by Project history.
- Short-lived or detached solver processes may escape observation. **UNKNOWN is not VERIFIED.**
- A `.lck` file, a zero launcher exit code, or an existing `.odb` is not sufficient by itself to claim the analysis is physically valid.
- Stop After Current Job does not forcibly terminate a running solver. Interrupted/uncertain Jobs must not be silently retried or requeued.
- JSON runtime state, reports, and Project SQLite history are **not a cross-file atomic transaction**. Recoverable projection errors must remain visible.

**Validation note:** the improved native process tracking and persistence implementation has passed simulated regression tests, but its final real-Abaqus end-to-end acceptance was **still pending at the documented development snapshot**. See [Process Identity](docs/ABQJOBPILOT_PROCESS_IDENTITY.md), [Runtime Coordination](docs/ABQJOBPILOT_RUNTIME_COORDINATION.md), and [Recovery](docs/ABQJOBPILOT_RECOVERY_AND_RECONCILIATION.md).

## Release Channels

| Channel | Branch | Positioning |
| --- | --- | --- |
| Stable source | [`main`](https://github.com/BrunelXian/AbqJobPilot/tree/main) | Published stable code line; its feature set and version must be checked independently. |
| Development source | [`Develop`](https://github.com/BrunelXian/AbqJobPilot/tree/Develop) | **`0.3.0.dev0`** in the documented checkout; Project improvements, Agent interfaces and optional MCP. |

This repository's earlier `main` source reported `0.1.0`, while the separately installed local stable application may have a different version. Do not treat a locally installed stable version as a statement about the current GitHub `main` branch. This README documents the development source and does **not** advertise a compiled release artifact.

## Repository Structure

```text
AbqJobPilot/
├── abqjobpilot/
│   ├── gui_app.py             Desktop dashboard
│   ├── command_console.py     GUI Agent Command Console
│   ├── runner_core.py         Sequential Abaqus runner
│   ├── process_identity.py    Process identity checks
│   ├── run_evidence.py        Native process evidence
│   ├── queue_store.py         Queue runtime state
│   ├── project/               Project metadata and archives
│   ├── database/              Project history storage
│   ├── api/                   Python API and JSON CLI
│   └── mcp/                   Optional stdio MCP adapter
├── docs/                      Architecture and usage guides
├── tests/                     Unit and simulation-based regressions
├── requirements.txt           Core requirements
├── requirements-mcp.txt       Optional MCP dependencies
├── run_gui.py                 Start GUI from source
├── sample.png                 Interface screenshot
├── README.md / README_CN.md
└── LICENSE
```

## Documentation

| Guide | Read it for |
| --- | --- |
| [Python / JSON API](docs/ABQJOBPILOT_PUBLIC_API.md) | Automation commands and result contracts |
| [Agent MCP](docs/ABQJOBPILOT_MCP.md) | Stdio setup, five tools, arguments, safety limits |
| [Project Model](docs/ABQJOBPILOT_PROJECT_MODEL.md) | Ownership, runtime files, import/export |
| [Project Database](docs/ABQJOBPILOT_PROJECT_DATABASE.md) | Durable Job/Run and artifact history |
| [Project Automation](docs/ABQJOBPILOT_A4_PROJECT_AUTOMATION.md) | Project-targeted CLI/API operations |
| [Process Identity](docs/ABQJOBPILOT_PROCESS_IDENTITY.md) | PID identity, parent linkage, limitations |
| [Runtime Coordination](docs/ABQJOBPILOT_RUNTIME_COORDINATION.md) | Locks and runner ownership |
| [Recovery](docs/ABQJOBPILOT_RECOVERY_AND_RECONCILIATION.md) | Failure/interruption evidence and non-automatic recovery |

## Validation

From a development checkout with `pytest` available:

```powershell
python -m pytest -q
python -m compileall abqjobpilot
```

The non-solver suite covers GUI logic, Project history compatibility, warnings, native process-evidence behavior using simulated process snapshots, CLI, and MCP stdio protocol tests. **Mocked or skipped tests do not establish real Abaqus process lineage or solver-result validity.** Some Tk tests require an interactive desktop session. Actual solver testing requires separate authorization and a disposable INP/Project.

## Known Limitations

- Windows-first local desktop workflow; not a distributed HPC scheduler.
- No general-purpose shell. Legacy CLI/MCP have no solver-start capability; the independent service accepts only its supported, precisely authorized Backend plans.
- MCP is Project-bound, stdio-based and read-only/preview-only; it is not a full autonomous engineering Agent.
- Per-Project history stores referenced external paths; moving original engineering files may require relinking.
- Process evidence is best effort and can miss short-lived processes; physical correctness requires engineering verification.
- Stable and development versions must not concurrently operate the same active Project/Queue.
- Portable installers and client-specific MCP integrations are not asserted as released or validated here.

## Roadmap

Planned directions, not release commitments:

- General Abaqus mode/host coverage, production Project migration, and service lifecycle beyond isolated TEST_ONLY stores; Run019 adds explicit idle test-service startup/stop, while Run016 covers only its fixed Standard acceptance scope.
- Improved reconciliation when JSON/report/SQLite projections diverge.
- Safer explicit Project migration and external artifact path repair.
- Packaging and clean-machine Windows deployment validation.
- Better Agent-facing observability **without bypassing human-controlled execution authorization**.

## Contributors

<div align="center">
  <a href="https://github.com/BrunelXian">
    <img src="https://github.com/BrunelXian.png?size=120" width="76" alt="BrunelXian GitHub profile">
    <br>
    <sub><b>@BrunelXian</b></sub>
  </a>
  <br>
  Project maintainer
</div>

Contributions and reproducible bug reports are welcome. Please avoid attaching personal Project databases or proprietary Abaqus inputs/outputs to public issues.

## License

AbqJobPilot is licensed under the [MIT License](LICENSE). Abaqus is separate commercial software; using AbqJobPilot does not supply an Abaqus license.
