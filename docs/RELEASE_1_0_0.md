# AbqJobPilot 1.0.0 for Windows x64

## Install and configure

Run `AbqJobPilot-1.0.0-Windows-x64-Setup.exe` under the Windows account that will use the desktop. Compare its SHA-256 with the accompanying SHA256SUMS.txt before installation. This public candidate is unsigned. Setup uses the Windows .NET Framework, installs Python 3.12 and Tcl/Tk privately, creates a per-user Start Menu shortcut and registers an uninstaller. Choose the suggested per-user version directory or a new empty local folder. Keep Projects outside the installation. An older installation can remain in its own directory.

Open **AbqJobPilot-1.0.0** from Start. Use the Project menu to create a management Project or reopen a recent one. Abaqus is optional for Project navigation and evidence inspection. In **Settings → Abaqus Environments**, use **Auto Detect**, or **Add Manually** to choose the Abaqus command BAT file provided by your own installation. Select **Set Default** and **Validate**, then reopen Settings to check the saved selection. With an open Project you can select its override. Validation checks launcher identity and accessibility. Solver availability and license checkout require separate evidence.

## Capability inventory

| Surface | Scope at freeze |
| --- | --- |
| Windows GUI and Projects | Native Tk, queue and task views, Project settings and recent Projects with full paths. GUI-01 and INSTALL-01 passed human acceptance on the development baseline. |
| Environment Manager | Discovers candidate launchers across versions, stores a global default and a Project override, and can snapshot and compare file identities. |
| Owner and Supervisor | Authenticated local IPC and a Project instance bind requests to an Owner. The Supervisor manages permitted dispatch and records process evidence. |
| Plan and Grant | Exact Plan and input identity, one-shot approval and bounded TEST_ONLY delegated budgets. Accepted requests and budget consumption share a Store transaction. Identical replay returns the original acceptance. |
| Run, Receipt and Evidence | Read back the original Run, Attempt and Receipt. Eligible new operations support ODB provenance, separate read authorization and output identity. Solver outcome, containment and qualification remain independently visible. |
| MCP | Classic Project inspection and Agent-first stdio. UAT-100 established Desktop interoperability for read-only communication on the development baseline. It did not exercise an installed 1.0.0 real-solver workflow. |

For installed Classic MCP, start `AbqJobPilotCLI\AbqJobPilotCLI.exe mcp --project "<absolute-project>"`. For Agent-first use the same executable with `agent-mcp --project "<absolute-project>" --connection-file "<private-original-connection-file>"`. Use `--historical-read-only` with the bound supported historical Project for the separate historical surface. Keep connection files private. Discovery alone does not establish Owner availability or a valid Grant.

## Execution limits

- **INSTALL-02 remains open.** General new REAL Plans do not yet complete environment selection, digest freezing and Owner-side revalidation end to end. Selecting a BAT file does not authorize execution. This distribution uses unprovisioned site contracts. The original private HIL bindings and model are omitted.
- **Owner loss requires reconciliation.** If the original authenticated Owner exits, the service can report `PROCESS_IDENTITY_UNKNOWN` or `UNAVAILABLE`. Preserve the original business key, Run, Attempt, Receipt and budget. Query the existing evidence through a trusted interface. A replacement process cannot assume the old Owner identity. Avoid resubmission and automatic refunds while acceptance or execution is unknown.
- The new-task execution bridge passed with a bounded Fake backend and `solver_conclusion=NOT_RUN`. INT-002B planning passed, execution stopped with the original Owner unavailable. No new submission was reported and the current balance is unknown.
- Historical INT-001 was **PARTIAL**. The solver completed, process and extraction qualifications remained **REVIEW_REQUIRED**, the original extraction Receipt was **FAILED**, and result-data integrity was **INSUFFICIENT**. Preserve these judgments when interpreting read-only observations.
- This freeze covers installation and desktop startup. It adds no solver entitlement, HIL qualification, automatic recovery, or Abaqus redistribution. Users supply their own Abaqus installation. The signed-publication and independent clean-machine acceptance stages remain outstanding.

## Dependencies and license

The installer targets Windows x64 with .NET Framework 4.x supporting WinForms and ZIP archives (4.5 or later). The bundled application includes CPython 3.12.10, Tcl/Tk, MCP SDK 2.3.0 and its dependencies. The install directory contains the build dependency lock, MIT LICENSE and third-party notices. No system Python installation is required. Uninstall from Windows Installed apps after closing the application and its service. The installer removes its registered files and preserves changed files and external Projects.

Maintainers can build from a committed checkout using a fresh x64 CPython 3.12.10 virtual environment, installing `src/requirements-build.lock.txt` and running its `python.exe packaging/build_windows.py <new-build-directory>`. The recipe uses the existing Windows .NET Framework x64 C# compiler and builds from tracked inputs at HEAD. The distribution folder contains the installer and its SHA-256.
