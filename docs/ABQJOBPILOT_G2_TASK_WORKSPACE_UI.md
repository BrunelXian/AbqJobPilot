# G2 Task Workspace UI

> Historical G2 layout note: G2.1 supersedes the home-screen Queue/Results notebook and permanent detail pane. The selection, filtering, status-color, and task-inspection rules below remain applicable; see `ABQJOBPILOT_G2_1_OPERATIONAL_DASHBOARD.md` for the current operational home layout.

## Scope and layout

G2 reorganizes the existing Tkinter/ttk application; it does not change the solver, queue JSON, database schema, archives, public API, or engineering-file ownership. `python run_gui.py` remains the entry point. The title identifies the Development edition.

The main window has Project/Task/View/Tools/Help menus, a compact command row, an always-visible runner status strip, a full-width Queue/Results notebook, a vertically resizable task detail area, and a one-line local-machine resource footer. The detail notebook contains Overview, File References, Logs, and Run History; it can be collapsed without removing the main table. The Queue table retains persisted execution order and shows original positions even when filtered. Results remain newest-first.

## Command locations

| Existing action | G2 entry |
| --- | --- |
| New/Open/Close/Recent Project, export/import, import legacy | Project menu and current-Project dropdown |
| Open Project Folder | Project menu: Open Management Project Folder |
| Add INP / Add Folder | Add Task dropdown and Task menu |
| Start Queue / Stop After Current Job | Always-visible command row, existing callbacks |
| Settings / Agent Command / language / Task Manager | Tools menu |
| Skip / Requeue / Delete Result Record | Task menu, context menus, and selected task's More menu |
| Open Work Folder | Task detail header (not the Project folder) |
| Refresh | Table controls, View menu, F5 |
| Help / Exit | Help menu |

The Task menu and detail More menu call existing action handlers. Mutating actions on a filtered-out old selection are disabled or require a visible selection. The runner is never started by a context menu. The existing runner scans `queue.json` repeatedly, so an external runner already active may pick up a newly enqueued job; the Requeue message says this explicitly. Start Queue confirms that it applies to the full executable queue, not the current filter or selection. Stop After Current Job is not immediate termination.

## Runner versus inspection

`runner_context` is derived from `live_status.json` plus the current GUI runner state. `inspection_key` is `(runtime_dir, queue_id)` and changes only through explicit table selection or View Running Job. Refreshing a running job never changes an inspected historical job. A Project switch clears inspection, table rows, and log content before loading the new runtime.

An explicit idle phase does not reuse old job names from `live_status.json`; stale persisted running records without a live runner are presented as **Status unconfirmed**, not as a verified live run. G2 does not perform R1 recovery or rewrite persisted statuses.

## Status and filtering

`abqjobpilot/gui_presentation.py` is the single display mapping used by Queue, Results, Overview, and both Run History views. `COMPLETED`, `COMPLETED_OK`, and `COMPLETED_WITH_WARNINGS` use the same success-green tag. The warning-complete label remains distinguishable. Original status, warning count, logs, and serialized records are unchanged. Warning counts do not turn FAILED, RUNNING, or UNKNOWN green. The Treeview theme uses white text on the selected blue row; the success tag remains available after deselection.

Search covers job name, batch, strategy, and INP path. Status and batch filters only affect visible rows. The Queue count explains that filtering does not change execution order. A filtered-out inspected task remains visible in the detail area with a notice; deletion and reordering are not silently applied to it. Results display canonical `COMPLETED`/`FAILED` records alongside the existing detailed statuses without changing the persistence contract.

## Details, logs, and history

Overview shows the stored raw status, warnings, CPU/GPU, timestamps, queue ID, and available attempt ID. File References lists **recorded paths only**, with current exists/missing/not-recorded state and copy/open-folder/open-text actions. File existence does not establish artifact validity. External INP/ODB/CAE ownership remains governed by FILE-OWNERSHIP-001, DB-STORAGE-001, and WORKDIR-001.

The Logs tab switches among STA, MSG, DAT, and Console for the inspected queue record, showing its job, attempt when known, and actual recorded path. It reads at most 64 KiB/80 tail lines per refresh and only while the Logs tab is visible. Lines remain chronological. Following the end is optional; scrolling upward disables follow, and updates preserve the manual position. A historical path may point to a file overwritten by a later attempt, so the viewer labels it as **current contents at the recorded path**, not a preserved historical snapshot. Run History queries the existing Project database read-only and shows real attempts newest-first; no-project mode shows an empty state. The legacy Run History popup is retained and uses the same display mapping.

## Refresh preservation

Unchanged row data is not rebuilt. Changed tables restore selection by `queue_id` and retain horizontal/vertical scroll positions. The selected table tab, detail tab, log source, follow setting, filters, column widths, and paned height are not reset by periodic polling. If the selected record is actually deleted or the Project changes, its inspection context is cleared. GUI history synchronization remains the existing JSON-to-SQLite projection.

Programmatic selection restoration suppresses `TreeviewSelect` callbacks, so a periodic rebuild cannot override an explicit View Running Job inspection with a stale selection from the other tab.

## Verification

- Baseline before G2: 81 tests passed, clean working tree at `fb6e0d29db79eb3a0b703fd87382ea171e3f0d2a`.
- G2 tests use temporary runtime, recent-project path, INP and log fixtures. They cover status color/data, runner versus inspection, filtering, three refresh cycles, result reordering, queue scroll/selection, log-follow pause, project switching, menus, requeue/delete safety, and responsive geometry.
- Final full suite: 85 passed on two consecutive `python -m pytest -q -rs` runs. An earlier run transiently reported 84 passed/1 Tk GUI test skipped when its window could not initialize; the subsequent GUI and full-suite reruns passed. No solver was started by tests.
- `run_gui.py` was launched with an isolated runtime without clicking Start Queue. A complete window screenshot was inspected at 1280 x 800; widget geometry was checked at 1280 x 800 and 1440 x 900. Tk scaling checks at 125% and 150% kept the Start, Refresh, More, and resource controls within the window.
- No real Abaqus run, QueueRunner start, file move/copy, database migration, commit, or push was performed.

Limitations: old attempts do not gain immutable log snapshots; a file referenced by more than one attempt may show its newest current contents. Unknown external runner ownership remains unconfirmed until the separate R1 runtime-recovery stage. The Settings and Agent Command dialogs retain their existing text/layout; G2 localizes the reorganized main workspace and menus.
