# AbqJobPilot

**Current Development: 0.5.3 DEV** · [Development source](https://github.com/BrunelXian/AbqJobPilot/tree/dev/0.5.3) · [Stable branch](https://github.com/BrunelXian/AbqJobPilot/tree/main)

AbqJobPilot is a Windows desktop tool for managing Abaqus jobs and recording what happened to each one. Use it on its own to manage Projects and inspect task history, or as the controlled execution layer for [VeriCAE](https://github.com/BrunelXian/Goal-Driven-CAE-Orchestrator).

## Start the development GUI

Use **64-bit CPython 3.12 for Windows with Tcl/Tk**. From the root of the development checkout, run these commands in PowerShell:

```powershell
py -3.12-64 .\src\launch_gui.py --check
py -3.12-64 .\src\launch_gui.py
```

The first command checks the desktop runtime. The GUI and Project navigation work without Abaqus installed. In **Project**, create or open a Project, or switch using **Recent Projects**. In **Settings → Abaqus Environments**, select **Auto Detect** to find candidate launchers or **Add Manually** to choose an Abaqus BAT file. Save a global default or select an environment for one Project. **Validate** checks the launcher files and their identity; it does not start a solver or check out a license.

## Execution and evidence

| User question | What the development version records or controls |
| --- | --- |
| Which job was accepted? | The Native Tk workspace shows the selected Project and its tasks. A persisted acceptance Receipt links the original request to a Run. |
| Who may start a job? | The Owner and Supervisor manage admission and process lifetime. Exact Grants bind an approved Plan and input identity. Bounded multi-run Grants enforce a transactional budget for supported TEST_ONLY submissions. |
| Where did the result come from? | Controlled inputs carry an INP SHA-256. For an eligible Run the Owner can register the ODB against its Attempt and Receipt. Extraction requires a separate, scoped read approval. New extraction transactions can bind the output JSON to its source and digest. |
| How should I interpret a result? | Solver outcome, process containment and execution qualification are reported separately. Extraction also distinguishes program outcome, containment, extraction qualification and result-data integrity. A completed program can still require review. |
| How can an agent read these records? | The Agent-first MCP uses stdio. Its historical read-only mode exposes environment identity, Run status and Receipt lookup for the bound Sanity Project. MCP support uses the optional [SDK dependency](src/requirements-mcp.txt). |

## Validation status and limits

- **GUI-01** Project navigation and **INSTALL-01** environment management have passed manual acceptance. Settings changes apply to future environment selection. Existing frozen Plans retain their original binding. General-purpose new Plans have yet to complete end-to-end acceptance of the selected execution environment.
- **MCP historical reads** have passed integration preflight against persisted records. **VeriCAE INT-001** succeeded in the scientific cross-check and retains an overall verdict of **PARTIAL**.
- In the real benchmark, the solver completed and process containment was verified. Unexplained auxiliary exits kept execution qualification at **REVIEW_REQUIRED**. The historical ODB extraction also requires review. Its native Receipt recorded **FAILED**, and its diagnostic JSON lacks the Owner-bound output digest required for full data integrity.
- This public DEV snapshot contains source and selected offline tests. Private site bindings, benchmark inputs, run databases and evidence files are excluded. The exact site-specific REAL workflow requires a separately provisioned and qualified environment. This branch is for development evaluation.

[License](src/LICENSE)
