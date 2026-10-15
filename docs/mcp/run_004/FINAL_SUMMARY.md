# Run 004: Recovery and Reconciliation

Status: Run 004 implementation verified on temporary fixtures; no production recovery was applied.

Run 001–003 were checkpointed locally as `8d3cbc4` (`feat(mcp): establish readonly adapter and runtime coordination`) after the 149-test baseline passed. The checkpoint excluded ignored runtime, project, solver, environment, and user data. Run 004 changes are left uncommitted.

## Delivered

- `recovery_workflow.py` builds a reproducible read-only plan from Run 003 assessment, existing runner ownership, queue/live metadata, SQLite disagreement, artifact signatures, and a fail-closed Windows process listing.
- The only supported queue correction is active raw status to `UNKNOWN_INTERRUPTED` after matching managed-command exit telemetry. Live status becomes `IDLE`. No uncertain analysis is marked completed or requeued.
- `Tools > Runtime Recovery` opens a separate review dialog with refresh, copy, disabled/enabled apply, exact-runtime confirmation, and a short-lived plan-bound token.
- Apply revalidates under the Run 003 queue lock, writes a bounded audit JSON, updates via existing atomic stores, and projects only the affected record into an already-existing Project database.
- Tests use temporary runtime/Project/engineering fixtures. They cover read-only assessment, approval rejection, stale plans, active cross-process owner, partial failure, SQLite history protection, and isolated GUI entry.

## Verification

- Interpreter: `D:\XianLab\envs\conda\LangChainEnv\Scripts\python.exe` (Python 3.12.10, no dependency installation).
- Baseline before Run 004: 149 passed. Final full pytest: 172 passed. Focused Run 004: 23 passed. MCP read-only protocol suite: 11 passed.
- `git diff --check`: clean. Five MCP tool registration points remain unchanged.
- Isolated Tk tests opened the recovery dialog and exercised the confirmation route with mocks; the ordinary `run_gui.py` entry point was not launched against its default runtime to avoid loading production data.
- SHA-256 hashes of six selected production metadata files (stable runtime queue/live, research Project manifest/database/queue, user recent-project registry) matched before and after tests. No ODB was hashed or opened.

## Boundaries and remaining risks

Process enumeration is a point-in-time, executable-name-based check; it is not a forensic proof against an unusually named detached solver process. The operator must verify solver inactivity. JSON files, audit JSON, and SQLite cannot be committed atomically together. A failed final audit write may leave a `PREPARED` audit entry. The GUI does not provide autonomous crash recovery, solver restart, stale `.lck` deletion, or a general database repair command. MCP remains read-only with exactly five tools.

The detailed contract and partial-failure procedure are in `docs/ABQJOBPILOT_RECOVERY_AND_RECONCILIATION.md`.
