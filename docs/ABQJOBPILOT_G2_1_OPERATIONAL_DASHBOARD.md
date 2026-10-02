# G2.1 Operational Dashboard

> The G2.2 version and Agent Console polish supersedes G2.1's Agent child-window layout note. See `ABQJOBPILOT_G2_2_VERSION_AND_AGENT_UX.md` for current Agent UI behavior.

## Purpose and layout

AbqJobPilot is first a batch-running and live-monitoring console. G2.1 keeps the G2 inspection behavior while making the home screen operational: toolbar, combined execution/local-system status strip, side-by-side Queue and Results, side-by-side live solver and Console tails, and a small Project/runtime footer. Queue and Results use a draggable horizontal `ttk.PanedWindow` with 4:6 initial weights. The table/log region uses a draggable vertical splitter; both log sources remain visible.

The top toolbar directly exposes Project, Add Task, Agent Command, Start Queue, and Stop After Current Job. Menus, right-click actions, and their existing callbacks remain available. Start Queue still targets the entire executable queue, never a filtered subset. Requeue remains enqueue-only; an already active external runner may pick up the new record. Stop After Current Job does not terminate the current solver process.

## Two contexts

The execution strip and home logs use only a **verified current runner** (`QueueRunner.is_running()` plus an active phase from `live_status.json`). They do not follow table selection. A stale persisted RUNNING record without a live runner is labelled Status unconfirmed and never presented as current live logs. Idle does not show the prior job as running. Known Step, Increment and Elapsed values appear in the strip; no percentage or ETA is fabricated. The right side of the same strip is explicitly **Local machine** CPU, memory and GPU usage, not Abaqus-process usage.

Queue and Results each retain their selection independently by stable `queue_id`; the most recently selected table determines menu actions without clearing the other selection. Both tables keep their original order semantics. Queue has its own search, Results has a separately labelled search plus status and batch filters. Filtering changes only display, not execution order or persisted records.

## Live versus historical logs

Home solver log defaults to STA and can select MSG, DAT, or LOG. The separate Console pane remains visible. Paths come from the active queue record or its verified live status, never from the selected historical row. Both panes use bounded 64 KiB/80-line tail reads in chronological order. Each pane has independent follow-tail state. Manual scrolling disables follow and a refresh preserves position. With no verified active job, home logs say No active job and do not present a historical file as live.

Task Details is a separate reusable `Toplevel`, opened by double-click, View Details context action, Task menu, or the table's More button. Its Overview, File References, Logs, and Run History remain bound to the selected `(runtime_dir, queue_id)`. Historical log files can have been overwritten by later attempts; the detail viewer identifies content as the current contents of the recorded path, not a preserved snapshot. Project switching closes the detail window and clears the old Project's inspection and live-log content.

## Presentation and persistence boundary

`COMPLETED`, `COMPLETED_OK`, and `COMPLETED_WITH_WARNINGS` all use the exact same `success` Treeview tag and colors. Warning-complete text remains distinct, and raw status, warning counts, logs, queue JSON and database values are unchanged. No database schema, queue contract, archive format, public API, solver callback, or Project file-ownership rule changed. FILE-OWNERSHIP-001, DB-STORAGE-001, and WORKDIR-001 remain in force.

Unchanged tables are not rebuilt. Rebuilt tables restore stable-ID selection plus horizontal/vertical scroll. Log source, follow setting, table filters, column widths, and splitter positions survive polling. Programmatic selection restoration cannot take over a task being inspected.

## Verification and limitations

Baseline: clean HEAD `fb6e0d29db79eb3a0b703fd87382ea171e3f0d2a` before G2; G2 changes were already uncommitted at G2.1 start. Baseline full suite: 85 passed. G2.1 tests use temporary runtime/settings/recent-project paths and mocked solver callbacks; no Abaqus or real QueueRunner was started. The isolated `run_gui.py` smoke exited normally. Geometry checks at 1280 x 800 and 1440 x 900, including Tk scaling 125% and 150%, kept Queue, Results, both logs, Start Queue and resources visible. Tests cover both splitter drags, active A versus inspected B logs, no-active/stale logs, bounded tail/follow preservation, selections, colors, Project switch, and mock-only Start/Stop callbacks.

Limitations: G2.1 does not implement R1 recovery or prove another process's runner ownership. Historical files are references, not immutable per-attempt snapshots. The Settings and Agent Command child-window layouts are unchanged. Splitter positions are session-only, not persisted.
