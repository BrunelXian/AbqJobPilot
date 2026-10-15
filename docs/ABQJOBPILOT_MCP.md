# AbqJobPilot MCP (0.2.2 development)

The optional MCP adapter exposes five Project-bound, read-only tools over local
stdio. It delegates to the existing public Python API; it is not a second
queue, runner, scheduler, database, or AI runtime.

## Requirements and launch

The official Python MCP SDK v2 is optional (`requirements-mcp.txt` declares
`mcp>=2,<3`). Ordinary GUI and API usage does not import it. In an environment
where that SDK is already installed, launch from the AbqJobPilot source root:

```powershell
python -m abqjobpilot.mcp.server --project "D:\AbaqusProjects\ExampleManager"
```

`--project` must name an existing formal Project containing `project.json` and
`runtime/queue.json`. The server validates it at startup without registering,
opening, migrating, or modifying it. There is no implicit recent-Project or
default-runtime binding. Start a separate process to inspect another Project.
The launching MCP client needs local process-start and file-read permission for
the Project and its referenced engineering files. It does not need an active GUI.

Generic MCP client configuration (adapt keys to the client's configuration
format; this is an example, not an installed global configuration):

```json
{
  "mcpServers": {
    "abqjobpilot-readonly": {
      "command": "C:\\path\\to\\python.exe",
      "args": ["-m", "abqjobpilot.mcp.server", "--project", "D:\\AbaqusProjects\\ExampleManager"],
      "cwd": "C:\\path\\to\\AbqJobPilot"
    }
  }
}
```

Use an interpreter containing the official SDK v2. This development Run was
tested with Python 3.12.10 and MCP SDK 2.3.0 in an existing environment;
no package installation is part of Run 001.

## Tools and identities

| Tool | Main inputs | Result / boundary |
| --- | --- | --- |
| `abq_preflight` | `inp_path`, optional `job_name`, `cpus`, `gpus`, `working_dir`, `batch`, `strategy` | Validates request and previews command; not Abaqus datacheck. |
| `abq_list_jobs` | `scope=queue\|history`, optional `status`, `batch`, `strategy`, `limit` | Queue uses `queue_id`; history uses logical `job_id`. Default limit 50, maximum 100. |
| `abq_job_status` | `scope`, `identifier` | Explicit queue/history identity. Stored `RUNNING` becomes `STATUS_UNCONFIRMED`; no process liveness is claimed. |
| `abq_locate_outputs` | Exactly one of `queue_id` or `inp_path` | Reports paths and file existence for ODB/STA/MSG/DAT/LOG/LCK. `recorded` versus `expected` is labeled; existence is not ODB validity. |
| `abq_prepare_enqueue` | Same request fields as preflight | Calls public dry-run enqueue only. `queue_mutated`, `solver_started`, and `runner_started` remain false. |

The five tools return structured JSON-compatible data with `schema_version`,
`status`, `project_id`, `data`, `errors`, `warnings`, and `error_details`.
Read-only tool annotations are published for clients, but the implementation
and public API calls, not annotations, enforce the safety boundary.

## Safety and limitations

- The MCP server exposes no actual enqueue, solver start, cancel, delete,
  approval, HTTP endpoint, or TCP listener.
- It does not alter `project.json`, `project.db`, queue/live status, reports,
  recent Projects, or engineering files. It does not reconcile stale state.
- `abq_prepare_enqueue` is a preview; a GUI runner already active elsewhere
  cannot be controlled by this MCP process.
- An ODB existing at a path is not a validated result. Referenced historical
  filenames may have been overwritten by a later attempt.
- Queue/status reading follows existing public API behavior. Log tails are
  capped at 256 KiB before selecting the final lines. This is not a general
  remote-file sandbox; only bind Projects and file references you trust.
- This integration was protocol-tested with the official SDK client, not with
  a particular vendor's graphical Codex/Claude configuration.

The [Run 001 evidence](mcp/run_001/FINAL_SUMMARY.md) records the actual tests.

## Run 002 cross-interface behavior

The Agent Command Console is an in-GUI, Project-targeted internal command
surface. Its `project use` selection does not retarget this MCP server. A
Console enqueue accepted by the existing public queue-only API can be seen by
an independently started read-only MCP server bound to the **same** Project.
MCP itself still has exactly the five Run 001 read-only tools; it cannot
enqueue, start, stop, or approve a solver job. See the
[Run 002 evidence](mcp/run_002/FINAL_SUMMARY.md).

## Run 003 admission boundary

The MCP tool list remains exactly five read-only tools. Queue-only writes from
the Agent Console, JSON CLI, Python API, and GUI share the runtime-scoped queue
transaction lock. Runner startup takes an independent OS-backed ownership lock
under that same transaction boundary. An actual enqueue during runner startup
or active ownership is rejected with `RUNNER_ACTIVE`; ambiguous ownership fails
closed. Preflight and MCP dry-run do not acquire or create queue locks. See
[runtime coordination](ABQJOBPILOT_RUNTIME_COORDINATION.md) and
[Run 003 evidence](mcp/run_003/FINAL_SUMMARY.md).
