# Run 006 interim repair: native evidence and warning counts

This is an implementation checkpoint, **not** final Run 006 acceptance. No
historical Retry 01/02/03 records are rewritten.

## Native process evidence

For a new managed launch, `runner_core._run_command` captures the `Popen`
launcher PID, Windows creation FILETIME and executable identity when available.
It samples Toolhelp descendants separately for datacheck and full-run. Each
observed child records PID, creation time, executable, parent PID, the
parent's captured creation time, and the Windows snapshot as relationship
source. Unavailable queries remain `UNKNOWN`/`UNVERIFIED`; a name or PID alone
does not establish a solver identity. Sampling is best-effort and may miss a
short-lived or detached process. No raw high-frequency snapshots are stored
in `queue.json`.

The compact, runner-native file is
`runtime/reports/process_evidence/<queue_id>.json`. It contains separate
`DATACHECK_RUNNING` and `FULL_RUNNING` entries, accumulated identities,
`VERIFIED`/`UNVERIFIED`/`UNKNOWN` strengths, and command-exit observations.
The `solver_candidate` strength verifies an observed candidate's process
identity and ancestry, **not** Abaqus result validity or complete solver
lineage. A failed evidence write is recorded as `process_evidence_error` in
the final queue/report metadata; it does not abandon an already launched
process. An early write failure remains recorded even when a later evidence
write succeeds, so a transient projection gap is not silently erased. The
terminal queue record and report carry only the runtime-relative
`process_evidence_path`. Formal Project SQLite Runs keep the same reference in
`metadata_json`, without a schema change or solver-file BLOBs. Terminal report
creation invokes the existing one-way runtime-to-SQLite projection; if it
fails, the report records `history_projection_error` for later reconciliation.
Old Projects and Runs without the reference continue to open and return no
native evidence. Metadata archives include the evidence JSON and rebase its
Project-owned runtime path on import. External passive-monitor JSONL is not
converted into native evidence.

## Warning counting

`0 WARNING MESSAGES` is a zero-valued summary, not a warning. Nonzero
summaries are counted by category within a source; cross-file copies of a
summary or detail line are not added twice, while repeated warnings within
one source retain their multiplicity. Final classification
uses the latest full-run console block, so an older datacheck warning in the
same log cannot color a clean full run. Genuine Abaqus fatal phrases still
take precedence. The persisted raw success status remains the established
`COMPLETED_OK`, which normalizes to public/SQLite `COMPLETED` and displays as
green in the GUI. `COMPLETED_WITH_WARNINGS` remains distinct and green when
real warnings exist. The Retry 03 logs were recalculated read-only to
`COMPLETED_OK`, `warning_count=0`; the original historical record is unchanged.

## Limits

Mock-process tests cover persistence and failure paths, but this repair has
not been validated with another real Abaqus run. The one earlier real run's
external JSONL is independent evidence, not a replayable native capture.
Neither an exited launcher nor an ODB file alone proves all solver processes
exited or that the analysis is physically valid. No recovery transition,
solver command, Project ownership rule, MCP tool, or GUI layout is changed.
