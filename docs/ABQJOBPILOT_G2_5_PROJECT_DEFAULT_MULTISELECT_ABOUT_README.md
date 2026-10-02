# G2.5 Project Default, Multi-selection, About, and README

## Scope

This stage changes the desktop selection experience, the default directory offered by
Project creation/import dialogs, About copy, and the public README. It does not add
a solver-start path, change queue order, change the database schema, or relocate
engineering files. The initial HEAD was `6168397871f701f5f6f45e553be26e6a0dd57a97`;
G2.4 changes were already uncommitted. Baseline: 98 tests passed.

## Multi-selection

Queue and Results use extended Treeview selection. Click selects one row, Ctrl+click
adds/removes a row, Shift+click selects a range, and Ctrl+A selects only visible
rows in the focused table. More/context menus offer Select All and Clear Selection.
Each table retains its own selection; the heading shows its selected count.

Polling restores every still-visible selected row by stable queue ID, not row
position. If a selected record disappears or a filter hides it, only that row
loses selection. Selecting all after a filter never includes hidden records.
Right-click on a selected row preserves the multi-selection; clicking an
unselected row targets that row. Single-item reorder, skip, requeue, and delete
remain single-item actions.

Bulk Queue removal accepts only existing QUEUED records while no job is running.
Bulk Results deletion accepts only result-list records. Both require one explicit
confirmation naming the selected count and state that engineering files are
not deleted. The queue store validates all IDs before making one atomic JSON
write, so an invalid selection does not partially remove records. Database
Run/Attempt history is not deleted. No bulk reorder is offered.

## Default Project directory

`default_projects_root()` derives `<application-root>/projects` from
`config.APP_ROOT_PATH`, independently of the current working directory.
New/Import destination dialogs create and offer the folder lazily; users can
choose another parent directory. Existing external Projects and application-
level Recent Projects continue unchanged. `/projects/` is Git-ignored. A
Project here owns metadata and runtime only; external CAE/INP/ODB files remain
in their engineering workspace.

## About and public README

Help > About now summarizes the local Abaqus runner, live monitoring, history,
automation interface, and reference-only Project ownership in English/Chinese.
It retains version `0.2.0` from `abqjobpilot.__version__`, the development build
label, and the verified stable GitHub URL with Open/Copy actions.

The root README now documents only current functionality, source installation,
the operational dashboard, Projects, archives, CLI and Agent Command boundaries,
file ownership, version, and MIT license. The old `sample.png` was not embedded:
it shows a pre-dashboard UI and personal engineering paths. No performance
percentage, native agent integration, or distributed execution claim is made.

## Verification

Tests use temporary runtimes, Projects, and engineering-file fixtures. GUI tests
simulate selection and runner state; they do not start Abaqus. The local Tcl
installation occasionally fails to initialize individual GUI tests; a full
rerun passed with **102 passed** under `python -m pytest -q`. The system Python
3.12 also passed all 102 tests with `unittest discover` and no Tcl skips.
An isolated `run_gui.py` smoke confirmed the exact title, extended selection,
50:50 panes, bilingual About text, and lazy default Projects directory.
