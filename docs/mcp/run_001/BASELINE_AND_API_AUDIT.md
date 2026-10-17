# MCP Run 001 baseline and API audit

Status: implementation and protocol verification completed using the user's specified existing environment. No new environment or package installation was performed.

## Installation and Git baseline

- `D:\Projects\abqjobpilot_legacy_archived`: absent on this host.
- `D:\Projects\abqjobpilot`: independent clean Git checkout, HEAD `557d3048fa7c9500ab5b94452a695bf075932e03`, branch `Develop`, version `0.2.1` (read only).
- `D:\Projects\abqjobpilot_dev`: independent clean Git checkout at the same initial HEAD and branch, version `0.2.1`.
- Development branch `dev/mcp-stdio` was created locally from that clean baseline; no commit or push.
- Both active checkouts have their own `.git` directory and the same `origin` URL. Git reads used a per-command `safe.directory` override because the sandbox account differs from the repository owner; no global Git setting was changed.
- Initial baseline with global Python 3.11.7: 109 passed, 1 skipped. The current specified LangChainEnv interpreter baseline: 110 passed (`-p no:cacheprovider`).
- The old checkout-local `.venv` is Python 3.9.13; it was not used. No `.venv-mcp` was created.

## Public API mapping

| Intended tool | Existing public API | Identity / scope | Read-only finding |
| --- | --- | --- | --- |
| `abq_preflight` | `AbqJobPilotClient.preflight(JobRequest)` | explicit bound Project runtime and INP path | Path/resource checks and command preview only; no Abaqus or queue write. |
| `abq_list_jobs` queue | `AbqJobPilotClient.list_jobs()` | `queue_id`; `runtime/queue.json` | Uses `read_queue(..., strict=True)` and does not initialize files. Response needs bounded projection, not full queue dicts. |
| `abq_list_jobs` history | `AbqJobPilotClient.list_project_jobs(project=...)` | logical `job_id`; Project DB | Uses `ProjectHistoryRepository(read_only=True)`; if `project.db` is absent, returns an empty list without creating it. |
| `abq_job_status` queue | `AbqJobPilotClient.status(job_id=queue_id)` | queue ID, not logical job ID | Reads queue/reports/live status and file existence. Historical `RUNNING` is not proof of an active process; MCP must label it unconfirmed. |
| `abq_locate_outputs` | `AbqJobPilotClient.locate_outputs(job_id=queue_id)` | queue ID | Reads metadata and tests file existence; does not open ODB. Derived paths are expected, not verified artifacts. |
| `abq_prepare_enqueue` | `AbqJobPilotClient.enqueue(JobRequest, dry_run=True)` | explicit bound Project runtime | Snapshots runtime metadata, returns preview; no queue mutation, runner start or solver launch. |

## Binding and side-effect findings

- `AbqJobPilotClient.for_project(project=...)` resolves via `ProjectAutomationSurface.resolve` and `ProjectManager.validate_project`, not `register_project` or `open_project`. It does not update Recent Projects.
- Project validation reads `project.json` and `runtime/queue.json` strictly. It does not initialize missing runtime files.
- Project history query uses a read-only SQLite connection and does not call `initialize_database`. No DB file should be created by a query.
- Before Run 001, `status()` called a helper that read entire `.log` files. Run 001 changed `last_log_lines()` to read at most 256 KiB from the end, then return the final lines. This remains read-only.
- `find_job()` adds `_report_path` to an in-memory parsed report dictionary; it does not rewrite the report file.
- The public queue status interface accepts `queue_id` (named `job_id` in the older API) or `inp_path`. Historical logical `job_id` is distinct and must not be passed as a queue ID.
- `locate_outputs()` may infer expected STA/MSG/DAT/LOG paths from the working directory and solver job name. It does not prove the files belong to a particular historical attempt or that an ODB is valid.

## Selected SDK/dependency state

The user subsequently confirmed the environment was prepared and explicitly directed Run 001 to use only `D:\XianLab\envs\conda\LangChainEnv\Scripts\python.exe`. Verified at execution: Python 3.12.10, official `mcp` 2.3.0, pytest 9.1.0, and pywin32 import success. `requirements-mcp.txt` declares the SDK as optional (`mcp>=2,<3`); it was **not installed or changed** during this Run. Ordinary GUI/API imports were tested under `python -S` with third-party site packages disabled.

The earlier environment audit correctly found the SDK absent at that earlier point, but it is superseded by the user's later environment preparation and the current interpreter inspection. The previously proposed `.venv-mcp` plan was not performed. Official references: [SDK](https://github.com/modelcontextprotocol/python-sdk), [client](https://py.sdk.modelcontextprotocol.io/client/), [stdio](https://py.sdk.modelcontextprotocol.io/run/).
