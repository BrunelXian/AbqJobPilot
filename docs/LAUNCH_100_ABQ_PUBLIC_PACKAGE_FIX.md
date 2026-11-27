# 1.0.0 public Windows installer verification

**READY_TO_PUBLISH** for the reviewed source and installer, subject to final publication approval. The Windows setup is unsigned. Independent clean-machine testing remains outstanding.

| Item | Verified value |
| --- | --- |
| Build source | `34632670680c25227c851a2368d9f3b0d8987e86` on `release/1.0.0` |
| Source lineage | Public preview `779b2990aa49d006414acaf2f7027bd647edb6fd` plus the 1.0.0 freeze changes |
| Asset | `AbqJobPilot-1.0.0-Windows-x64-Setup.exe`, 71,418,880 bytes |
| SHA-256 | `078392d3ccc09c6a6af2f14e8fb7139c127be2b2951db60734bfd504bf22984d` |
| Embedded build ID | `sha256:86229294dfde94e3d4cbd4b7b5a1a8e88cf992fb174a983da2dee2b080cbf3d1` |
| Local delivery directory | `dist/1.0.0-public/` in the engineering checkout |

## What changed

The engineering freeze built all three roles from its private tracked source. The interpreter path came from a string constant in `standard_contract.py`; the six Project paths came from constants in `sanity_hil.py`. Transitive imports placed those modules in the GUI, CLI and Owner PYZ archives. A search of the outer Setup or its plain-text configuration missed them. The earlier public preview already had unprovisioned values and omitted a private site model in `rod_output_v2.py`.

The release branch inherits those three reviewed public modules byte-for-byte. The frozen version metadata, GUI branding and CLI transport entry are carried over. The build recipe now checks the three source hashes before compilation. The installer template in `packaging/Setup.cs` protects application/source locations by directory name on any drive, in place of the original workstation-specific protected paths. The tracked settings template contains UI defaults and no selected Abaqus installation. Settings remains the normal selection interface. INSTALL-02 is still open.

The build took a fresh Git archive, empty PyInstaller work and cache directories and the isolated locked x64 build environment. No executable was edited after compilation. The old installer stays internal. The release branch descends only from public Git history. The README uses the previously approved screenshot of the same Native Tk workspace.

## What the scan established

- The exact payload ZIP occurs once in the final Setup. Inspection covered all 3,619 ZIP entries including FILES.json, nested standard-library archives, the three CArchives and their decompressed PYZ modules. All 3,618 inventoried files matched their installed bytes.
- The three sensitive modules in each executable compared equal as Python code objects to fresh compilations of the reviewed source. All nine comparisons passed. The build identity was checked against tracked file bytes.
- Across the three roles the scan visited 3,183 PYZ modules and 75,905 code objects, counting shared modules in each role. No absolute Python `co_filename` was present. The developer home, private interpreter, site HIL paths, private license-server markers and common credential patterns were absent from the scanned material. No private Project, run database, real ODB or engineering input/output file was identified.
- Native compiler metadata is a separate layer. Thirty-two distinct bundled libraries have absolute upstream PDB debug paths under supplier build roots. All 32 matched the installed dependency or runtime bytes. These strings identify upstream debug-symbol locations. The application does not use them to select an interpreter, a Project or an Abaqus environment.
- The package contains the product MIT license, CPython and Tk notices and license material for the locked distributions. The public safety scan is also available as [a maintainer tool](../packaging/audit_public.py). It accepts a local private-marker list. Its checks establish coverage for those markers and artifact classes.

## Minimum regression

| Check | Result |
| --- | --- |
| Per-user install | The final Setup exited 0 under a non-elevated account. An isolated test registration reported 1.0.0 in HKCU and its Start Menu shortcut resolved to the installed GUI. |
| Desktop | The installed GUI returned READY with private CPython 3.12.10 and Tk 8.6.15. The Native Tk workspace opened on an empty profile and closed normally. The startup check recorded zero Abaqus calls and no service start. |
| Environment Manager | Three isolated Native Tk tests against the public build source passed. They covered no-install use, static discovery, manual BAT selection, validation, persisted default, Project override and missing-file reporting. The installed window was smoke-tested separately. |
| CLI and Owner | The installed CLI reported 1.0.0. Launching the installed Owner with no command exited 2 with `OWNER_FIXED_COMMAND_REQUIRED`, the expected refusal. No Owner service or job was started. |
| MCP | Two installed CLI transports completed real stdio initialization and tool discovery. Classic advertised five tools and read an empty Project. Agent-first advertised six. Both advertised 1.0.0. |
| Uninstall | The test uninstaller reported UNINSTALLED. Its directory, test registration and shortcut were removed. The external disposable Project survived. |

No solver or Abaqus Python ran. No ODB content was read, Grant issued, task submitted or historical record changed. See the [release notes](RELEASE_1_0_0.md) for execution and recovery limitations.
