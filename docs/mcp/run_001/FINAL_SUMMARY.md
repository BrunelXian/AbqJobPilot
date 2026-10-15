# MCP Run 001 final summary

Verdict: `PASS_ABQJOBPILOT_MCP_RUN001_READONLY_STDIO_READY`.

## Scope and baseline

- Run: `ABQJOBPILOT_MCP_RUN001_READONLY_STDIO_ADAPTER`.
- Development repository: `D:\Projects\abqjobpilot_dev`, branch `dev/mcp-stdio`, initial/current HEAD `557d3048fa7c9500ab5b94452a695bf075932e03`. It was clean before Run work except the Run audit evidence created during the preceding environment-check turn. No commit or push.
- Stable repository: `D:\Projects\abqjobpilot`, branch `Develop`, same initial HEAD, version `0.2.1`. It remained clean and was only read.
- Expected `D:\Projects\abqjobpilot_legacy_archived` was **absent**, so no archived installation was accessed or modified.
- Selected interpreter: `D:\XianLab\envs\conda\LangChainEnv\Scripts\python.exe`, Python 3.12.10, official MCP SDK 2.3.0, pytest 9.1.0, pywin32 import success. No environment or dependency creation/installation/upgrade.
- Baseline with this interpreter: 110 passed. Development version is now `0.2.2.dev0`; Project/data schema versions were not changed.

## Implementation

- Entry point: `python -m abqjobpilot.mcp.server --project <formal Project path>`.
- Transport: official SDK v2 stdio; explicit immutable Project binding per process. No GUI, HTTP/TCP, or default-runtime fallback.
- Exactly five tools: `abq_preflight`, `abq_list_jobs`, `abq_job_status`, `abq_locate_outputs`, `abq_prepare_enqueue`.
- All use the existing public API for preflight, Project-scoped list/history, status, output discovery, and dry-run enqueue. `scope` distinguishes `queue_id` from logical `job_id`. Stored RUNNING becomes `STATUS_UNCONFIRMED` with no active-process claim.
- Tool responses use the SDK structured output mechanism with common schema/status/project/data/errors/warnings fields. SDK annotations mark all tools read-only and non-destructive. No actual enqueue or solver-start tool exists.
- Public API output discovery gained additive LCK and path-source fields, and status log reading now limits reads to a 256 KiB tail. Queue persistence, SQLite schema, runner behavior, and GUI wiring were not changed.

## Verification

- Actual official-client stdio `initialize`, `tools/list`, and `tools/call` passed. All five calls returned structured results; tool list contains no mutation tool. Invalid MCP arguments produced a protocol tool error; client disconnect completed cleanly within timeout.
- Two independent stdio server processes were called concurrently against the same temporary Project. Before/after SHA-256 inventories matched, including Project manifest/DB, queue/live/report JSON, recent-projects state, and external fixtures; no absent DB or runtime file was created.
- Tests cover missing/invalid/unsupported Project, missing DB and empty queue, missing INP, invalid CPU/GPU, unknown identity, multiple attempts, stale RUNNING, missing/existing dummy ODB, missing log, bounded chronological log tail, missing optional SDK, and no-SDK ordinary GUI/API import.
- Final command: `D:\XianLab\envs\conda\LangChainEnv\Scripts\python.exe -m pytest -q -rs -p no:cacheprovider` -> **121 passed**, exit 0. One earlier run had 118 passed / 1 environment-sensitive GUI skip; two later full runs passed all tests, latest 121 passed.
- `git diff --check` -> exit 0; only LF/CRLF warnings. Focused search found no process launcher, `QueueRunner`, direct queue/DB write, or GUI import in `abqjobpilot/mcp`. The only Abaqus-command search hits in the public API are pre-existing command-preview construction, not execution.
- Stable repository `git status --short` remained empty. No Abaqus, QueueRunner, solver job, production Project, queue, or DB was touched. Normal API and `run_gui` import successfully under `python -S` without optional SDK packages.

## Limitations and next Run

- No graphical GUI launch or vendor-specific Codex/Claude client configuration was exercised. The test is genuine SDK stdio protocol, not a vendor desktop integration claim.
- MCP status does not establish runner liveness or ODB validity, and historical log paths may point at files overwritten by later attempts.
- The archived installation path was absent; its contents/version cannot be verified.
- Recommended but **not started**: `ABQJOBPILOT_MCP_RUN002_ENQUEUE_AUTHORIZATION_DESIGN`, covering admission, approval, idempotency, and runner/queue coordination before any actual enqueue tool is considered.
