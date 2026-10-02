# G2.3 Log Access, Running Highlight, and About

## Scope and baseline

This is a Tkinter/ttk presentation change only. At the start, HEAD was
`fb6e0d29db79eb3a0b703fd87382ea171e3f0d2a`; G2/G2.1/G2.2 changes were
uncommitted. The baseline suite had 86 passing tests. No Abaqus solver, real
QueueRunner, database migration, or production runtime was used.

## Queue and Results logs

Both row context menus expose **View Logs / 查看日志** directly after View Details.
They share `open_task_details(..., initial_tab="logs")`; double-click still
opens ordinary Task Details. Single-click only selects. The existing Logs tab
offers STA, MSG, DAT, and LOG sources; Console remains available for existing
users and points to the recorded `.log` path. The view uses recorded paths first
and the existing `expected_paths()` derivation when a legacy record lacks one.

For a not-yet-started queued item, absent logs are **Not yet created**, not an
error. Other absent recorded files are **Missing**; an unavailable path is
**Path unknown**. Existing files are **Available**. These labels describe the
current path only, not output validity. Historical logs retain the warning that
the file at that path may have been overwritten by a later attempt. Reads remain
bounded to 64 KiB and 80 tail lines and retain chronological order. Inspecting
a Queue or Result row never changes the home live STA/Console binding, which
continues to follow only a confirmed running job.

## Running action

**View Running Job / 查看运行任务** uses the existing action callback. It is blue
and enabled only while the local runner is confirmed active and a queue ID is
available. IDLE and STATUS UNCONFIRMED use the normal disabled button style.
Stale persisted RUNNING records are not treated as active execution.

## Title and About

The main title is exactly **AbqJobPilot**. Help > About / 帮助 > 关于 AbqJobPilot
shows the centralized `abqjobpilot.__version__` (`0.2.0`), development-build
designation, product purpose, and verified stable GitHub source. The stable
checkout at `D:\Projects\abqjobpilot` reported origin fetch remote
`https://github.com/BrunelXian/AbqJobPilot.git` during this stage. The
application holds one normalized URL, `https://github.com/BrunelXian/AbqJobPilot`,
and About offers Open GitHub and Copy Link. Normalization also accepts the
equivalent GitHub SSH remote form. About does not invoke Git or touch the stable
checkout at runtime. Product name, URL, and STA/MSG/DAT/LOG syntax stay
untranslated; surrounding controls have English and Chinese labels.

## Verification and limits

Tests cover URL normalization, About contents and safe browser call, both menus,
queued and completed log inspection, home-log isolation, simulated RUNNING/IDLE/
STATUS UNCONFIRMED button states, and the retained G2.2 dashboard tests.
`run_gui.py` remains the entry point. The new About window uses the system window
close control; language selection is applied when it is opened. No immutable
per-attempt log snapshot is created in this stage.

Final `python -m pytest -q`: **88 passed**. One earlier run skipped a Tk test
because the local Tcl installation intermittently failed to load a script; the
full rerun passed. An isolated `run_gui.py` smoke with temporary runtime and
recent-project state confirmed the exact title, approximately equal panes,
and About version/repository link without starting a runner.
