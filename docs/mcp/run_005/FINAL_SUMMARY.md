# MCP Run 005: Process Identity, Recovery Evidence, Develop Branch

Verdict: `PASS_ABQJOBPILOT_MCP_RUN005_PROCESS_IDENTITY_AND_RECOVERY_EVIDENCE`.

## Git and baseline

- Starting HEAD `8d3cbc4e485947ec81a9f628cce849596eb5d5ae`, branch `dev/mcp-stdio`; Run 004 source, tests, and documents were uncommitted and preserved.
- Existing local and remote `Develop` were both at `557d304`, an ancestor of `8d3cbc4`. The local `Develop` ref was fast-forwarded to the existing checkpoint and checked out at the **same HEAD**, then redundant local `dev/mcp-stdio` was deleted. `main` stayed at `345faac`. No merge, rebase, reset, commit, push, remote deletion, or release-installation edit occurred.
- Final local branch `Develop` tracks `origin/Develop` and is ahead by one checkpoint commit. No `origin/dev/mcp-stdio` remote-tracking branch was present. Run 004/005 changes remain uncommitted, ready for the user's GitHub Desktop review and normal commit/push workflow.
- Interpreter `D:\XianLab\envs\conda\LangChainEnv\Scripts\python.exe`; application version remains `0.2.2.dev0`. Baseline full suite: **172 passed**.

## Implementation

- `process_identity.py` uses native Windows read-only process APIs. It records launcher PID plus creation FILETIME and executable path, command digest, and best-effort observed descendant identities without treating a launcher as the solver.
- Existing runner launch/poll points add optional evidence to live status without changing command construction, execution flags, or queue scheduling.
- Read-only recovery assessment and plan include process evidence. Missing lineage, active descendants, PID mismatch, or unknown liveness block approval. The plan's process fingerprint is rechecked under the existing queue lock before any metadata write.
- Queue admission rejects a colliding interrupted/locked/unconfirmed output identity with `OUTPUT_CONFLICT_UNCONFIRMED`; unrelated fixture jobs retain ordinary queue behavior. Existing Run 004 partial-failure and audit behavior remains.
- The five MCP tools remain read-only; no MCP enqueue or recovery Apply tool was added.

## Verification

- Full pytest: **189 passed**. Run 003/004/005 focused tests: **59 passed**. Genuine MCP stdio protocol suite: **11 passed**.
- Real independent Windows Python fixture processes verified PID/creation-time/executable matching, normal exit, and a parent that exits while a child remains alive. Mocked tests cover PID reuse, access failure, process-state change after approval, a solver-candidate classification, and interrupted-write cases. No physical Abaqus process was run or claimed to be validated.
- GUI-compatible tests passed within the full suite. Six pre/post SHA-256 checks of production metadata matched. `git diff --check` passed (Git only warned about future LF-to-CRLF conversion).

See `docs/ABQJOBPILOT_PROCESS_IDENTITY.md` for API mechanics, evidence strength, collision policy, and limitations. The next Run should not begin automatically.
