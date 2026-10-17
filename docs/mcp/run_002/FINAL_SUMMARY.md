# MCP Run 002: Project-scoped Agent Command

Verdict: `PASS_ABQJOBPILOT_MCP_RUN002_PROJECT_SCOPED_AGENT_COMMAND`.

## Baseline and scope

- Development checkout: `D:\Projects\abqjobpilot_dev`, branch `dev/mcp-stdio`, HEAD `557d3048fa7c9500ab5b94452a695bf075932e03` at start and finish. The working tree already contained uncommitted Run 001 source/docs/tests; they were preserved. No commit or push.
- No applicable `AGENTS.md` was found in the development repository. Run 001's read-only MCP protocol and project safety boundary were retained.
- Interpreter: `D:\XianLab\envs\conda\LangChainEnv\Scripts\python.exe` (Python 3.12.10, MCP SDK 2.3.0). No packages or environments were installed or changed.
- Baseline: 121 passed. Final full suite: **130 passed**, exit 0. `git diff --check`: exit 0; only repository LF/CRLF conversion warnings.

## Command contract

Supported legacy commands remain `enqueue`, `enqueue-folder`, `list`, `help`, and `clear`. Added `project list`, `project create --name`, `project use --project`, `project show`, `status --job-id`, and `outputs --job-id`. `--project` on a task command overrides the Console target for that command. `status`/`outputs` use **queue ID**, not logical historical Job ID.

The Console shows an explicit target Project, ID, and runtime. It initializes only from an already validated active GUI Project; with no formal Project it says no target selected. `project use` updates only the Console session. The main GUI still blocks Project switching while the Console is open; it is never silently retargeted. Failed/ambiguous Project selection clears the previous target, so later commands cannot fall back into it. Duplicate names return `AMBIGUOUS_PROJECT`; unknown names return `PROJECT_NOT_FOUND`. The public JSON CLI/Python API keeps its existing default-runtime compatibility outside the Console.

`AgentCommandSession` contains GUI-free routing and calls `AbqJobPilotClient`/Project Automation Surface for create/list/resolve/show, queue list, preflight, enqueue, status, and output discovery. The Tk Console no longer calls the default-runtime `load_queue`, `add_inp_job_to_queue`, or `add_folder_to_queue` functions directly. Omitted CPU/GPU values come from the selected Project's Settings via a read-only settings loader; optional datacheck/full-run flags are carried through additive `JobRequest` fields. The canonical AI Instruction is generated from parseable command examples and forbids shell, Project deletion, and solver start.

## Enqueue admission and folder preview

- Before a single enqueue, the target is revalidated, INP/resources are preflighted, the local GUI runner callback must be inactive, `live_status.json` must explicitly say `IDLE`, and no queue record may normalize to `RUNNING`. Admission is checked again immediately before queue-only API enqueue. No target or uncertain/active state rejects the command.
- `enqueue-folder` limits matches to non-recursive `.inp` files inside the selected folder, uses public API dry-run previews, displays target Project plus count and resolved requests, and asks for explicit GUI confirmation. A second admission check precedes public API enqueue-folder. If only some requests enqueue, the public `PARTIAL` result is shown as partial, not as complete success.
- Existing `QueueRunner` repeatedly loads the queue, so adding a record while it is active may lead to immediate execution. Run 002 rejects *known* active/unconfirmed states. It does **not** provide a cross-process lease or eliminate the race where another process starts a runner between the final check and the queue write. That remains a later runtime-concurrency problem; no guarantee of global atomic admission is claimed.

## Cross-interface and safety evidence

`tests/test_agent_project_session.py` covers project registry/create/use/show, ambiguity, invalid selection sequences, explicit overrides, two-Project isolation, no-target refusal, CPU/GPU Settings, invalid inputs, active/uncertain runner refusal, folder confirmation/partial results, English/Chinese labels, and external INP ownership. A real official MCP stdio client initializes against the same temporary Project after Console-session enqueue, lists the five read-only tools, calls `abq_list_jobs` and `abq_job_status`, and sees the queue record. No `abq_enqueue` or solver-start tool was added; MCP did not mutate the queue.

Focused search found no `Popen`, `subprocess`, `QueueRunner`, `run_next_job`, direct queue/DB writer, or solver call in the new session/parser/Console/MCP layer. Existing API Abaqus hits only build command-preview text. File-operation search found no engineering-file move/copy/delete; only Tk `grid_remove` matched the broad `remove` term. Tests used temporary Projects, runtimes, registries, and INPs only. No Abaqus, real QueueRunner, ODB opening, stable/archived installation change, commit, or push occurred.

## Interface roles and remaining limits

- **Agent Command:** lightweight in-GUI human-readable commands, with explicit Project target and guarded queue-only enqueue.
- **JSON CLI / Python API:** public automation surface and shared business behavior; existing default-runtime behavior remains unchanged.
- **MCP:** standardized local stdio tool surface, still exactly five read-only tools in Run 002.

The GUI label test ran successfully in the final full suite; a separate focused run skipped that one test when Tk briefly reported no display. There was also one transient Tk destructor warning in an earlier full run; fixture cleanup was tightened and the final full run completed without warnings. The Console does not provide a cross-process runner lease or transactional bulk enqueue; these should be addressed before any MCP enqueue authorization work.

Run 003 was not started.
