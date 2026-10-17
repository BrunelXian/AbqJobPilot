# Run 001 protocol and safety evidence

## Test setup

- Interpreter: `D:\XianLab\envs\conda\LangChainEnv\Scripts\python.exe` (Python 3.12.10).
- Official MCP SDK: 2.3.0; pytest: 9.1.0; no dependency installation.
- Temporary Project, queue, live status, report JSON, SQLite history, recent-projects file, and external dummy INP/log fixtures only.
- No real Project, Abaqus executable, GUI runner, or production queue was used.

## Actual stdio protocol

`tests/test_mcp_readonly.py::test_protocol_stdio_initialize_list_call_and_integrity`
spawns `python -m abqjobpilot.mcp.server --project <temporary Project>` through
the official MCP `Client(StdioServerParameters(...), mode="legacy")`. The
`legacy` mode performs the actual initialize exchange. The test observes a
protocol version and server info, lists **exactly five** tools, checks every
tool's read-only annotation, and invokes all five with structured responses.
Malformed tool arguments return an MCP tool error. The client context exits
without hanging or protocol contamination.

`tests/test_mcp_readonly.py::test_two_simultaneous_read_only_stdio_clients`
opens two independent server processes at once, repeats dry-run preparation
and history listing, then exits within a timeout.

## Integrity

The tests SHA-256 inventory every temporary file before and after direct and
stdio tool calls, including `project.json`, `project.db`, `runtime/queue.json`,
`runtime/live_status.json`, `runtime/reports/historical.json`, the application
recent-projects file, and referenced engineering fixtures. The inventory also
detects newly created files. All comparisons passed. A second formal Project
without a database remains DB-free after history listing.

Covered errors and ambiguity: missing/invalid Project and future manifest
schema, absent SDK (`python -S`), missing INP, invalid CPU/GPU, unknown queue
and history identities, two historical attempts, stale RUNNING state, missing
and existing ODB path, missing log path, bounded log tail, malformed MCP input.
An existing dummy ODB is only reported as present; it is never parsed or
treated as valid solver evidence.

## Code review boundary

- `abqjobpilot/mcp/` has no GUI imports, file-write helpers, SQLite writes,
  `QueueRunner`, `Popen`, or solver launch calls.
- Public API changes are additive `lck_path`/`path_sources` on output discovery
  and a bounded log-tail read; no queue/schema/runner behavior changed.
- `abq_prepare_enqueue` always passes `dry_run=True`; there is no MCP mutation
  tool.
- The five registered tools have `readOnlyHint=true` and
  `destructiveHint=false`. These are metadata; the implementation is the guard.
- There is no network transport, HTTP endpoint, or direct AI/LLM call.

See `FINAL_SUMMARY.md` for the final full-suite result and verdict.
