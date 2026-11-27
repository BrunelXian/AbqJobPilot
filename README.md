# AbqJobPilot

**1.0.0 release candidate · Windows x64 · MIT**

[Installation and release notes](docs/RELEASE_1_0_0.md) · [Package verification](docs/LAUNCH_100_ABQ_PUBLIC_PACKAGE_FIX.md) · [Stable 0.2.2](https://github.com/BrunelXian/AbqJobPilot/tree/main)

AbqJobPilot is a Windows desktop application for managing Abaqus jobs and keeping the evidence behind each result. Use the GUI to organize Projects, inspect the queue and review job history. Research clients such as VeriCAE can use MCP to look up the same Run and Receipt.

![Native Tk desktop showing the Project selector, navigation, job queue and results](docs/images/native-tk-preview.png)

*The Native Tk workspace, captured on the 0.5.3 development baseline with an empty profile. The 1.0.0 candidate retains this interface.*

## Get started on Windows

The installer is pending publication. The release branch is available for source review. When the binary is released:

1. Compare the SHA-256 of `AbqJobPilot-1.0.0-Windows-x64-Setup.exe` with the [candidate checksum](packaging/SHA256SUMS.txt). In PowerShell, run `Get-FileHash .\AbqJobPilot-1.0.0-Windows-x64-Setup.exe -Algorithm SHA256`. The candidate is unsigned.
2. Run Setup as your normal Windows user and open **AbqJobPilot-1.0.0** from Start. Python and Tk are included. Keep Projects outside the install directory.
3. Choose **Project → New Project** or **Open Project**. The Project selector shows the active name and provides the recent-project list. You can use Project management and inspect the queue without Abaqus installed.
4. Open **Settings → Abaqus Environments**. Choose **Auto Detect** or **Add Manually**, select your installation’s Abaqus BAT file, then choose **Set Default** and **Validate**. An individual Project can select another configured environment. Validation checks the launcher’s file identity and availability. Solver and license availability require separate checks.

To open the GUI from this source branch with Windows x64 CPython 3.12 and Tcl/Tk, run `py -3.12-64 .\src\launch_gui.py --check`, then `py -3.12-64 .\src\launch_gui.py`.

## From queue to evidence

| Component | What you can establish |
| --- | --- |
| Project and Plan | Which Project instance, job revision, input identity, resource bounds and backend a request targets. |
| Grant, Owner and Supervisor | A trusted operator approves a bounded operation. The authenticated Owner checks admission and accounts for the budget. The Supervisor manages permitted execution. |
| Run and Receipt | Whether the original request was accepted, which Run and Attempt it created, and which lifecycle and validation evidence actually exists. |
| Result provenance | Eligible operations can bind inputs and artifacts by SHA-256. ODB result extraction requires a separately scoped read authorization. Execution and extraction qualifications are reported independently of observed results. |

## Connect a research client

The installed `AbqJobPilotCLI\AbqJobPilotCLI.exe` serves Classic MCP with `mcp --project "<existing-project>"` and Agent-first MCP with `agent-mcp --project "<existing-project>"`. A live Agent-first session uses the original authenticated Owner connection. Store its connection document privately. Each transport uses standard input and output.

The installed candidate passed real stdio initialization and discovery for five Classic and six Agent-first tools. UAT-100 verified Desktop read-only communication on the development baseline. A separate bounded TEST_ONLY execution test demonstrated same-Run readback using the Fake backend. [VeriCAE preview](https://github.com/BrunelXian/Goal-Driven-CAE-Orchestrator/tree/codex/vericae-0.5.5-public) · [Evidence and qualification limits](docs/research-preview-evidence.md)

## Known limitations

- **General REAL execution remains unqualified.** INSTALL-02 still needs to bind the selected environment to general new Plans and revalidate it before dispatch. The public candidate ships with unprovisioned site contracts.
- **An interrupted Owner requires reconciliation.** Preserve the original business key, Grant, Run, Attempt and Receipt. Query existing evidence before considering another submission. Unknown acceptance or execution carries no automatic retry or budget refund.
- **Read a verdict in context.** A solver can complete while execution qualification remains `REVIEW_REQUIRED`. Historical INT-001 retained an overall `PARTIAL` verdict and its original failed extraction Receipt.
- The installer passed non-administrator installation, startup and removal on the build host. Independent clean-machine acceptance and public release approval are pending.

[MIT license](LICENSE) · [Changelog](CHANGELOG.md)
