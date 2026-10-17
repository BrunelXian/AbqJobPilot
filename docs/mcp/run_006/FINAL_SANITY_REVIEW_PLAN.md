# Run 006 final native-evidence sanity review (proposal only)

**Not authorized by this document.** The repaired native process tracker has
mock-process coverage but has not yet been accepted through a new real Abaqus
run. Obtain a separate, explicit one-job authorization before starting a
solver, datacheck, or QueueRunner. This plan does not close Run 006.

## Isolated fixture and preflight

1. Under a new disposable root such as `%TEMP%\AbqJobPilot_Run006_Final_<unique>`, create a **new** formal Project (`manager\`) and a separate engineering directory (`engineering\`). Do not reuse the previous Run 006 Project, job name, INP, or output paths. Do not put INP/ODB files in the Project metadata directory.
2. Prepare and manually inspect a small one-element C3D8 static INP with a positive-Jacobian node order, fully constrained bottom face, small top-face displacement, elastic material and solid section, and U/RF/S/E requests. A Python static check is not Abaqus datacheck. Use a fresh unique job name and verify there is no existing `.odb`, `.lck`, or conflicting solver process for that name/work directory.
3. In the ordinary Windows user session, verify WMI CPU queries, Abaqus launcher configuration, license availability, and free disk space without launching the solver. Do not run Abaqus from a restricted Codex sandbox. Confirm an empty queue, correct Project ID/runtime, only **one** planned Job, CPU **1**, GPU **0**, and the intended datacheck/full-run Settings. Set a supervised window and disk ceiling with the user before execution; do not silently retry or clean up if a limit is reached.

## One authorized GUI execution

After the user separately approves the exact fixture and limits, add only that
INP through the existing GUI workflow. Recheck the Queue has exactly one
`QUEUED` record, then use the existing **Start Queue** action once. Do not use
MCP to enqueue/start, and do not add a second job or auto-retry. Let any solver
process exit normally; a monitoring timeout is **not** permission to kill it.

## Evidence to inspect after natural termination

| Check | Expected evidence, not a shortcut |
| --- | --- |
| Solver result | Full-run return code and terminal `.sta` agree; `.msg` says zero warning/error messages; `COMPLETED_OK` normalizes to `COMPLETED` with `warning_count=0`. ODB presence is recorded but not treated as physical validation. |
| Native process file | `runtime/reports/process_evidence/<queue_id>.json` exists with `source=native_runner`, separate `DATACHECK_RUNNING` and `FULL_RUNNING` phases, launcher PID/Windows creation time when accessible, observed children and relationship source/status, and command-exit evidence. `UNKNOWN`/`UNVERIFIED` is reported honestly. |
| Terminal persistence | Final Queue row and report reference the evidence file; neither terminal status nor final `live_status.json` erases that reference. Any `process_evidence_error` or `history_projection_error` remains visible. |
| SQLite | The formal Project's Run metadata references the evidence; `ProjectHistoryRepository(..., read_only=True).get_run_process_evidence(run_id)` resolves it. No solver bytes/BLOBs are stored. |
| Reopen | Close and reopen the Project without changing its history, then read the same Run and evidence reference. Compare the evidence file checksum before/after. |
| Recovery boundary | If any process identity, child lineage, `.lck`, or output state is uncertain, do not requeue, reuse the output name, delete `.lck`, or infer completion. Record uncertainty for review. |

An external passive monitor may supplement the native evidence but is no longer
the sole acceptance source. Capture actual PID/creation-time/parent evidence
only when observed; a very short job can leave lineage **inconclusive**.
Preserve all outputs and prior Run 006 evidence. Publish no raw sensitive
command lines, machine-specific Project paths, or large solver files. Only a
separate post-run review can decide whether full Run 006 acceptance is justified.
