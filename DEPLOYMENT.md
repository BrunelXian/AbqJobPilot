# AbqJobPilot 0.3.0.dev0 — Windows source candidate

Native Tk Compact Cockpit and independent Project-scoped execution service.
This is a source distribution, not an installer or a Python bundle.

## Requirements and startup

Use 64-bit CPython **3.12.x with Tk** on Windows. Qualification has run on
3.12.10 / Tk 8.6.15 on the recorded development host. Other users, hosts and
Windows versions require separate acceptance. The GUI/service uses the standard
library; optional MCP requires `mcp>=2,<3` in your chosen environment.

Extract all files into a writable application folder. Select one interpreter:

1. Set `ABQJOBPILOT_PYTHON` to an absolute `python.exe` path in the launching
   process environment; or
2. Put that absolute path, without quotes, on the first line of local
   `python-path.txt` beside Open_Dev_GUI.vbs; or
3. Supply an application-specific `.venv\Scripts\python.exe`.

No global PATH search or installation occurs. An invalid explicit choice fails
instead of falling back. The existing registered LangChainEnv path is retained
only as the final development-machine fallback, not a deployment requirement.
The VBS configuration text is a local path file, not a portable secret/config
export. Do not include a machine-specific python-path.txt in a public archive.

Run your selected Python with `-I -B launch_gui.py --check`, then double-click
Open_Dev_GUI.vbs. A missing interpreter shows an error; incompatible Python or Tk
produces a structured preflight error. GUI startup errors produce a native
message instead of disappearing silently. The launcher never starts a service,
creates a Project, issues a Grant or calls Abaqus. It waits for the GUI to exit;
the Supervisor has its own lifetime and disk output handles.

## Projects and service

New Project creates an empty, PAUSED Project with no Run or execution Grant.
Open Project only validates existing data. Keep Projects outside the application
folder. Project owns its data; external INP/CAE/ODB files are not automatically
copied. Credentials are Windows-user/host/Project bound, not portable Project
assets. Moving an application folder is distinct from moving a Project.

Agent Command contains Project & Service, evidence and recovery views. Start
Service is explicit. Reconnect verifies identity and uses the public client.
Closing the GUI disconnects monitoring; it does not stop workers. Stop Service
requires the exact owner/operator capability and safe idle state; active,
uncertain or unreconciled execution can block it. Never delete locks to retry.

Queue stays left, Results right, with Current Run and two persistent log panes.
Classic Queue has a one-click return to Execution Workspace; the two data models
and authorization paths remain separate. Results is an evidence view, not a
promise of successful computation. Partial process exit, managed scope end,
Solver and validation are separate. Stale cached data is not Live.

English is default; saved Chinese preferences remain effective. French and
German are **Preview**, not fully reviewed localization.

## Agent and execution scope

Python clients use the same explicitly selected Project and Supervisor. The
read-only example is `examples/agent_first/product_inspect.py`. The five MCP tools remain read-only/preview. The legacy CLI also supports
explicit queue-only enqueue; it does not dispatch a service Run or sign a real
Grant. Neither interface is a generic Solver authorization interface. No real Grant is created by installation.

The real Backend remains the separately approved fixed Abaqus 2024 Standard
axial-bar model, CPU=1/GPU=0/2048 MB, exact input/entry/Job/output and attempt
budget. Its fixed entry and interpreter pins are unchanged. An alternative
application interpreter supports empty Projects and TEST_ONLY workflows but
does **not** qualify that host for real Standard execution. No generic Abaqus
path/argument editor or new real approval is supplied in this release task.

Crash Recovery identifies evidence and provides a read-only preview. Interrupted
(Unverified) is not Failed or verified success. Apply needs a separate precise
trusted authorization; it does not Retry, Requeue, Resume Solver or open dispatch.

## Errors and limits

- Python/Tk error: verify the chosen full path and run `launch_gui.py --check`.
- PROJECT_IDENTITY_MISMATCH / LOCAL_CREDENTIAL_UNAVAILABLE: do not copy private
  files between Projects or users; no automatic migration or credential rebinding.
- START_UNCONFIRMED / OWNER_BUSY: inspect existing evidence; do not start another
  owner or remove reservations/locks. Reconnect is not Retry.
- HOST_UNCONFIRMED on an existing fixture/Standard Project: use its pinned
  interpreter; changing an application preference cannot change a Plan.
- Missing optional MCP: GUI remains available; no automatic package install.
- Missing Abaqus: no implicit probe, version check or Solver launch; ordinary
  GUI/empty Project workflows remain usable. Real execution stays unavailable.

Not supported/verified: arbitrary analysis modes, ODB content validation,
unattended arbitrary Solver grants, automatic logoff/reboot recovery, seamless
cross-machine credentials, machine-wide/cross-Project resource scheduling or
autonomous CAE decision making. Historical out-of-scope processes remain UNKNOWN,
ODB NOT_RUN, and Run021B GUI-close/Solver overlap NOT_OBSERVED.

The previously disclosed historical test-credential risk has bounded user
acceptance; credentials were not proved globally revoked. Never reuse historical
materials. Report problems with version, error code and redacted evidence;
never attach private credential files, raw databases or unreviewed logs.
