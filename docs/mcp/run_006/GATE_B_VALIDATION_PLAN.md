# Gate B proposal: one bounded Abaqus lineage experiment

**Not authorized and not executed in Gate A.** This document requests a separate, explicit user decision. Nothing here instructs an agent to run the solver now.

## Isolation and prerequisites

Proposed disposable layout, created only after Gate B approval:

```text
%TEMP%\AbqJobPilot_Run006_<random-id>\
    project\                # new formal Project and runtime metadata
    engineering\            # unique INP and solver outputs; not Project-owned
    observation\            # bounded process samples and integrity hashes
```

Never use the historical RL-LAM Project, the stable release runtime, or a pre-existing job/output name. The candidate job name is `RUN006_LINEAGE_<random-id>`. No external engineering file is moved. Before a real run, confirm the selected launcher still matches the static configuration, verify license availability using non-executing local information if available, check free space, ensure no conflicting process/output identity, and review the proposed INP. The exact licensed release and license availability are currently unresolved; do not silently proceed if the setup differs.

## Candidate INP

Prepare a new, physically simple, one-element linear-elastic C3D8 cube in the disposable engineering directory. The draft below is a **proposal only**: it has not been parsed or executed by Abaqus, and must be reviewed before Gate B.

```text
*Heading
Run006 disposable process-lineage sanity model
*Node
1, 0., 0., 0.
2, 1., 0., 0.
3, 1., 1., 0.
4, 0., 1., 0.
5, 0., 0., 1.
6, 1., 0., 1.
7, 1., 1., 1.
8, 0., 1., 1.
*Element, type=C3D8, elset=EALL
1, 1, 2, 3, 4, 5, 6, 7, 8
*Nset, nset=BASE
1, 2, 3, 4
*Nset, nset=TOP
5, 6, 7, 8
*Material, name=MAT
*Elastic
1000., 0.3
*Solid Section, elset=EALL, material=MAT
,
*Step, name=LOAD
*Static
*Boundary
BASE, 1, 3, 0.
TOP, 3, 3, -0.001
*Output, field
*Node Output
U
*Element Output
S
*End Step
```

The existing `tests/fixtures/Job_test.inp` explicitly says it is fake and is **not** suitable for this experiment.

## Matrix and observation

| Case | Proposed action after approval | Evidence to collect |
| --- | --- | --- |
| B1 | One tiny full analysis via the existing GUI Start Queue path in the disposable Project | Runner lock/token, `cmd.exe` wrapper PID+creation, SMALauncher and candidate solver PIDs, creation times, executable paths, snapshot parent PIDs and times; whether wrapper remains active |
| B2 | Let the job finish naturally; no forced termination | `Popen` return code, final live/queue/report status, STA terminal text, file presence and mtime; distinguish each from physical validity |
| B3 | Compare live observations with persisted identity | Identify missed children, overwritten `live_status.json` identity, absent attempt linkage, and OS query errors |
| B4 | Using fixture-only API calls, inspect output-conflict admission after naturally confirmed exit | Existing `(working_dir, job_name)` safeguards; no reuse of the same solver output path in a second real run |
| B5 | Simulate unknown child/inaccessible PID/PID reuse with mocks only | Recovery remains blocked; no solver kill, orphan creation, or real crash experiment |

Use the new read-only `sample_lineage` helper (`abqjobpilot/passive_lineage.py`) with a launcher identity captured from the disposable runtime, sampling approximately every 100 ms while the job runs. One call is limited to 600 samples/60 seconds and 64 retained child records per sample; truncation is `UNCONFIRMED`. Retain only timestamp, PID, creation time, executable path, observed parent PID/creation time, queue ID, and job name; no command line. The helper itself does not start a process or write evidence, so a later Gate B harness must explicitly store a small observation summary in the disposable observation directory. This is **not** a claim that the current two-second runner poll offers complete lineage. Stop the observer cleanly. Never terminate the solver merely because the observation window expires. Do not commit solver outputs.

## Resource and stop rules

- CPUs: **1**; GPUs: **0**; parallel jobs: **1**. Override current development defaults only for the disposable test request, without changing global settings.
- Full-run only is proposed to avoid a second solver invocation for datacheck. Confirm that this is acceptable for the approved test and that the installation supports CPU 1/GPU 0; the actual solver has not validated it.
- Expected solver runtime: likely seconds to a few minutes for one element, but license startup and environment initialization are unknown. Proposed supervised observation budget: 10 minutes maximum, with 60-second bounded sample batches. If still running, stop observation and ask for instructions; do **not** kill it or enqueue another run.
- Expected disk use: likely under 100 MB, but unverified. Check free space first and request approval for a 500 MB disposable-directory budget. Exceeding it means stop further submissions and seek direction; do not delete live solver files.
- If launcher/child state becomes uncertain, do not apply recovery, requeue, reuse output identity, delete `.lck`, or mark completion. Preserve evidence for review.
- Cleanup is a separate decision after confirming all processes exited; no automatic deletion is authorized by Gate A or this proposal.

## Exact authorization needed

Before Gate B, the user must explicitly authorize: creating the disposable Project/engineering/observation directories; copying the reviewed tiny INP into that engineering directory; starting **one** real Abaqus full-run job through the existing `QueueRunner`/Start Queue path; consumption of one solver license; CPU 1/GPU 0; passive process/log observation and resulting solver-file writes; the proposed time/disk limits; and the handling of a run that exceeds them. Authorization to test is **not** authorization to kill processes, clean outputs, alter production data, or submit a second job.
