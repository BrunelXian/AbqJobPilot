# MCP Run 003: Runtime coordination

Verdict: `PASS_ABQJOBPILOT_MCP_RUN003_RUNTIME_COORDINATION`.

## Scope

- Branch `dev/mcp-stdio`; initial HEAD `557d3048fa7c9500ab5b94452a695bf075932e03`.
- Initial tree contained uncommitted Run 001/002 work. A binary tracked diff
  plus inventory and copies of untracked files were saved at
  `C:\Users\wuxia\AppData\Local\Temp\abqjobpilot-run003-backup-d25bc973c7354168b8359b708cc1762b`
  before major edits. No reset, commit, or push.
- Selected interpreter: `D:\XianLab\envs\conda\LangChainEnv\Scripts\python.exe`.
- Baseline: 129 passed, 1 skipped. No dependency installation.

## Implementation and evidence

See [runtime coordination](../../ABQJOBPILOT_RUNTIME_COORDINATION.md) for
the writer audit, lock identity, Windows primitive, ownership lifecycle,
admission policy, read-only assessment, authority boundary, and limitations.
New tests use independent spawned Windows processes with an Event barrier for
simultaneous queue writes and actual overlapping ownership. They use temporary
INP files and runtimes only. A terminated fixture lock holder demonstrates
OS release; no solver process or actual QueueRunner is terminated.

`QueueRunner.start` obtains ownership before starting its thread; a mocked
loop test covers duplicate startup without invoking Abaqus. The five MCP
tools remain unchanged and read-only. Recovery assessment does not mutate
queue, live status, history, engineering files, or lock files.

## Verification

- `tests/test_runtime_coordination.py`: 19 passed. Independent spawned Windows
  processes overlap via Events for two-client and high-contention enqueue,
  competing GUI-style reorder/bulk removal and enqueue, queue-lock timeout,
  process termination/OS lock release, runner ownership, and exclusion of
  local coordination files from metadata/full archives. A mocked runner loop
  tests `QueueRunner.start` without solver execution.
- Actual official SDK MCP stdio and Agent Console regression tests: 20 passed;
  the MCP tool list is still five read-only tools.
- Final full suite: **149 passed**, exit 0. A transient earlier regression
  found a malformed-queue error-code mismatch; it was corrected to preserve
  `INVALID_STATUS_DATA`, and both focused and final suites passed.
- `git diff --check`: exit 0. SHA-256 before/after inventories of the stable
  release runtime queue/live status, the named RL-LAM Project manifest/DB/queue,
  and the per-user Recent Projects registry: 6/6 hashes unchanged after tests.
- No Abaqus, datacheck, real QueueRunner loop, production queue mutation,
  `.lck` deletion, package install, commit, or push occurred.

## Remaining limits

Direct edits outside `queue_store` do not participate in the lock. The
low-level whole-list `save_queue` cannot detect an unlocked stale caller
snapshot. Folder enqueue is per-record atomic, not all-or-nothing. Live
telemetry/report writes and SQLite history are not a single distributed
transaction with queue JSON. Recovery is assessment only: no solver-process
verification, stale-lock cleanup, or automatic resume. Run 004 is not started.
