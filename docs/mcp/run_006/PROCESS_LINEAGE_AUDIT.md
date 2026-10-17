# Process lineage audit (Gate A)

## Static installation and configuration evidence

The development runtime `runtime/settings.json` specifies `D:\ABAQUS2024\Commands\abq2024.bat`, 14 default CPUs, 0 default GPUs, GPU disabled, datacheck disabled, and full run enabled. The code fallback is the same batch path with CPU 14/GPU 0 (`abqjobpilot/config.py:10-15`, `abqjobpilot/settings_store.py:10-20`). These are current settings, **not** the proposed Gate B resource limit.

The configured batch file exists (182 bytes). Static text shows it calls an Intel oneAPI environment batch file and then `D:\ABAQUS2024\product\win_b64\code\bin\SMALauncher.exe` with forwarded arguments. That executable exists; its PE ProductVersion/FileVersion are `6.426.0.23224`. Installed `standard.exe`, `explicit.exe`, and `pre.exe` have PE versions `6.426.0.23265`. The path labels the installation `ABAQUS2024`, but an exact licensed Abaqus release/hotfix cannot be proved from these observations alone. No launcher, version-probe command, license file, or solver was executed/read.

An unprivileged `Get-CimInstance Win32_Process` query returned access denied. Existing Toolhelp snapshot code returned 353 process entries at inspection time, none with the selected `abq`/`standard`/`explicit`/`SMALauncher` name prefixes. A separate `Get-Process` check found no matching visible processes. This point-in-time absence is **not** proof of historical or future solver absence, nor a machine-wide process guarantee.

## Code path and evidence lifetime

| Stage | Evidence and storage | Code |
| --- | --- | --- |
| GUI authority | `Start Queue` invokes existing `QueueRunner`; its runtime is the selected GUI runtime | `abqjobpilot/gui_app.py:2130-2160`, `abqjobpilot/runner_core.py:320-380` |
| Runner ownership | OS `.runner.lock` plus `runner_owner.json` with runner PID/token; this identifies runner ownership, not solver lineage | `abqjobpilot/runtime_coordination.py:108-219` |
| Job selection | First `QUEUED`/`DATACHECK_OK` record in queue order; queue ID is the record identity | `abqjobpilot/runner_core.py:351-371` |
| Command | Settings path; batch launch uses `cmd.exe /c`; datacheck/full command supplies `job=`, `input=`, CPU, optional GPU, `interactive`, `ask_delete=OFF` | `abqjobpilot/runner_core.py:20-76` |
| Process launch | `subprocess.Popen(..., shell=False, cwd=job['work_dir'])`; log receives START, command text, later END/return code | `abqjobpilot/runner_core.py:181-218` |
| Launcher identity | `Popen.pid`, creation FILETIME and executable path; SHA-256 of command arguments, runtime/queue/phase/workdir/job name | `abqjobpilot/process_identity.py:65-103`, `abqjobpilot/process_identity.py:178-187` |
| Descendant scan | Toolhelp parent-PID traversal, independently queried child PID/creation/exe and observed parent PID/creation time; name-based solver candidates. Run 006 rechecks launcher identity after a scan and marks a racing exit `UNCONFIRMED` | `abqjobpilot/process_identity.py:149-185`, `abqjobpilot/runner_core.py:204-209` |
| Passive validation helper | Bounded samples of an already identified launcher; no launch, termination, persistence, or command-line capture | `abqjobpilot/passive_lineage.py:1-30` |
| Live persistence | Optional `process_identity` and later command return code written to `runtime/live_status.json` via atomic JSON replacement, best-effort | `abqjobpilot/runner_core.py:109-141`, `abqjobpilot/runner_core.py:210-218`, `abqjobpilot/utils.py:43-66` |
| Terminal records | Queue status and report are written after classification; reports/SQLite do not provide a guaranteed immutable OS lineage record | `abqjobpilot/runner_core.py:220-318`, `abqjobpilot/runner_core.py:157-179` |
| Assessment | Reads queue/live, runner lock, report, `.lck`, ODB existence/mtime and optional SQLite history; process evidence is separate from solver verdict | `abqjobpilot/recovery_assessment.py:24-123` |
| Recovery | Plan fingerprints metadata plus process observation, requires command-exit and confirmed tracked exit; Apply rechecks under queue lock after human approval | `abqjobpilot/recovery_workflow.py:115-315` |
| Admission | Active runner or stale RUNNING blocks; same workdir/job name with interrupted record, `.lck`, or unconfirmed matching live identity blocks | `abqjobpilot/runtime_coordination.py:148-263`, `abqjobpilot/queue_store.py:211-260` |

## Direct evidence, indirect evidence, inference, unknown

- **Direct:** the configured wrapper and executable files exist; their static contents/PE metadata are readable. Code records the `Popen` wrapper PID, Windows creation time and executable path, and a command-exit return code. Windows Python-process fixture tests prove this API works for those fixtures.
- **Indirect:** the development runtime contains 844 JSON report files; its manifest has 718 `COMPLETED_WITH_WARNINGS`, 108 `DATACHECK_FAILED`, and 17 `FAILED_FATAL` entries. None of those report files contains `process_identity`. Parser tests include a synthetic Abaqus completion string. These establish historical classifications/text fixtures, not OS lineage.
- **Inference:** for this configured `.bat`, the initial PID should be `cmd.exe`; the script invokes `SMALauncher.exe`. Whether the launcher waits for `standard.exe` or other workers is not established without Gate B.
- **Unknown:** actual Abaqus process tree, launcher lifetime, child discovery rate, license behavior, precise installed release/hotfix, per-attempt OS lineage of historical jobs, and whether a detached/unusually named process can survive wrapper exit.

## Identity strength and persistence gaps

`inspect_pid` uses `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE)`, `GetProcessTimes`, `WaitForSingleObject`, and `QueryFullProcessImageNameW`. `verify_identity` requires PID + creation FILETIME + executable path for active identity; an inaccessible or partial query is `UNCONFIRMED` (`abqjobpilot/process_identity.py:65-123`). Toolhelp provides parent PID; Run 006 now retains that PID and the observed parent's creation time in new optional child records. This is still a point-in-time relationship, not enduring parent-child ownership. Older records lack those fields and remain compatible. The two-second runner poll can miss short-lived descendants. A recognized executable basename is a candidate, not solver authorization. The separate `sample_lineage` helper allows 0.05-1.0 second read-only observations, at most 600 samples/60 seconds and 64 retained children per sample; truncation becomes `UNCONFIRMED`.

`live_status.json` is overwritten as phases change. `_run_command` copies the job before attaching private process evidence; the later final-status write uses the queue record and may replace that evidence. GUI/runner abnormal exit may leave the last live observation, but a write may be missed because live telemetry intentionally tolerates `OSError`. On restart, absent or partial identity cannot be upgraded to verified exit. Reports preserve status/return metadata, not immutable per-attempt process lineage. `run_id` is not available at the launcher capture point. The existing log writes the full command text; new process identity metadata only stores a digest, so Gate B reports must not copy command lines.

## Recovery implications

The code distinguishes runner ownership from launcher/observed child identity. A stopped runner alone does not clear a solver. Active/unknown/mismatched lineage blocks recovery; `.lck` and ODB existence are observations, not proof of liveness/completion. The only approved queue correction remains `*_RUNNING -> UNKNOWN_INTERRUPTED`, never `COMPLETED`; no auto-requeue, `.lck` deletion, or process kill exists. A confirmed exit classification applies only to **tracked** candidates; missed or detached processes remain a known limitation. Run 006 adds only a conservative scan-race check; real Abaqus behavior remains unvalidated.
