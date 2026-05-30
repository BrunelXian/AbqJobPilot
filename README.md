# abqjobpilot

<h1 align="center">Abaque Job Pilot</h1>

<p align="center"><strong>Agent-friendly Abaqus INP queue runner and live monitor.</strong></p>
<p align="center"><strong>Batch upload, sequential execution, safe interruption, real-time STA/log diagnostics, and resource-aware job control.</strong></p>

<p align="center">
  <a href="README_CN.md">中文 README</a>A
</p>

[![Project Type](https://img.shields.io/badge/project-Abaqus%20job%20pilot-blue)](#)
[![Focus](https://img.shields.io/badge/focus-batch%20simulation%20automation-important)](#)
[![Scope](https://img.shields.io/badge/scope-INP%20queue%2C%20monitoring%2C%20agent%20commands-success)](#)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)](#)
[![Python](https://img.shields.io/badge/python-3.9%2B-blueviolet)](#)

![abqjobpilot GUI](sample.png)

## What It Does

`abqjobpilot` is a standalone desktop tool for managing Abaqus `.inp` job queues. It is designed for simulation batches, parameter sweeps, strategy pools, and long-running research workflows where manually submitting jobs one by one wastes time and compute availability.

The tool keeps Abaqus outputs in each `.inp` file's original folder while maintaining its own lightweight queue, live status, logs, and reports under `runtime/`.

## Key Features

### 1. Batch Upload And Sequential Execution

- Add a single Abaqus `.inp` file to the queue.
- Add all matching `.inp` files from a folder.
- Run jobs sequentially without manually launching each one.
- Run `datacheck` before full analysis.
- Stop safely after the current job finishes.
- Skip selected queued jobs.
- Open the selected job's working folder.
- Keep `.odb`, `.sta`, `.msg`, `.dat`, and `.log` next to the original `.inp` file.

### 2. Live Monitoring And Fast Diagnosis

- Current job status: batch, strategy, phase, step, increment, analysis time, ODB size, and elapsed time.
- Real-time `.sta` tail.
- Real-time console log tail.
- Completed result table with warning and failure status.
- One-click log copy for AI-assisted diagnosis or teammate review.
- CPU, memory, and GPU usage panel for checking whether the workstation is idle, overloaded, or underused.

### 3. Agent Prompt Friendly

`abqjobpilot` includes an Agent Command Console. It is not a system shell. It only accepts a small whitelist of internal commands.

You can ask ChatGPT, Codex, or another AI assistant to generate queue commands, then paste them back into `abqjobpilot`.

```text
enqueue --inp "D:\path\Job_xxx.inp" --cpus 14 --gpus 1
enqueue-folder --folder "D:\path\strategy_folder" --pattern "*.inp"
list
help
clear
```

The console supports:

- `Copy AI Prompt` for copying the command-generation instruction.
- `Paste` for importing commands from the clipboard.
- `Paste & Run` for importing and executing commands immediately.
- Multiple commands in one paste.
- Settings-based default CPU/GPU values when `--cpus` or `--gpus` is omitted.
- No arbitrary PowerShell, cmd, Python, or shell execution.

### 4. Better Resource Use And Higher Effective Throughput

In many Abaqus batch workflows, time is lost because jobs are manually submitted, failures are noticed late, or workstation resources sit idle overnight.

`abqjobpilot` reduces that idle time through queue execution, datacheck-first workflow, resource visibility, and faster log diagnosis. In batch simulation, parameter sweep, and strategy-pool generation workflows, it can improve effective compute throughput by roughly `15%-40%`, depending on job duration, machine configuration, queue size, and operator availability.

## Quick Start

```powershell
git clone https://github.com/BrunelXian/abq_job_pilot.git
cd abq_job_pilot
python run_gui.py
```

The current MVP uses only the Python standard library for core GUI functionality.

## Abaqus Command Path

Each workstation may have a different Abaqus installation path. Open `Settings` in the GUI and set the local Abaqus command, for example:

```text
D:\ABAQUS2024\Commands\abq2024.bat
```

Settings also include:

- default CPU count, such as `12` or `14`
- whether GPU is enabled
- default GPU count, such as `1`
- whether to run `datacheck`
- whether to run the full analysis

## Agent Command Examples

Add one job:

```text
enqueue --inp "D:\Projects\models\batch_a\strategy_01\Job_test.inp" --batch batch_a --strategy strategy_01
```

Add one job with explicit resources:

```text
enqueue --inp "D:\Projects\models\batch_b\strategy_02\Job_test.inp" --cpus 12 --gpus 1
```

Add a whole folder:

```text
enqueue-folder --folder "D:\Projects\models\batch_c\strategy_03" --pattern "*.inp"
```

List the queue:

```text
list
```

## Output Location

Abaqus runs in the `.inp` file's folder, so solver output files are created there:

```text
*.odb
*.sta
*.msg
*.dat
*.log
```

`abqjobpilot` runtime metadata is stored under:

```text
runtime/
```

Runtime files, virtual environments, and large Abaqus output files are ignored by git.

## Safety

- The Agent Command Console parses only whitelisted internal commands.
- It does not execute arbitrary system commands.
- Abaqus jobs start only after the user clicks `Start Queue`.
- The runner avoids `shell=True` for Abaqus execution.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests do not submit Abaqus jobs.

## Status

Current stage: usable MVP.

Planned work:

- finer failure classification: license, input, numerical, interrupted
- resume and rerun workflows
- more modern GUI theme
- optional SQLite queue backend
- packaged Windows release
