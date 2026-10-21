# Development workspace rules

- Development tasks operate only in this Dev workspace; the default branch is `Develop`.
- `D:\Projects\abqjobpilot` is the user's Stable installation and is outside development-task scope. Do not inspect, scan, compare, modify or launch it or its data unless a separate task explicitly authorizes that scope.
- Do not automatically switch, restore or synchronize branches. If the branch/HEAD changes unexpectedly, conflicts appear, or another task keeps modifying relevant sources, stop related writes and report. Preserve unrelated user changes.
- Commit, push and promotion to Stable require explicit task authorization.
- Development tests must use isolated temporary Project, Runtime and Recent files, with explicit paths. Never infer a test target from the GUI selection or default Recent data.
- Avoid concurrent tasks that modify source files or Git state in this workspace.
- Before Python or dependency work, read `D:\XianLab\envs\ENVIRONMENTS.md`, reuse a suitable registered environment, verify its absolute interpreter/version/dependencies, and follow the task's environment restrictions. Do not alter shared dependencies without authorization.
