# Run 006 Gate A baseline

- Run: `ABQJOBPILOT_MCP_RUN006_ABAQUS_PROCESS_LINEAGE_VALIDATION`, Gate A only.
- Repository: `D:\Projects\abqjobpilot_dev`; branch `Develop`; initial HEAD `8d96dd811625dabecb1a211c30dfd4881dfcb35b`.
- Initial `git status --short` and `git diff --stat`: empty. The Run 004/005 work is present in the current commit; no reset, branch switch, commit, or push was made here.
- Interpreter: `D:\XianLab\envs\conda\LangChainEnv\Scripts\python.exe`, Python 3.12.10. No environment or dependency changes.
- Baseline: `189 passed in 53.47s` using that interpreter. Previous reported count was also 189, but this is an independent run.
- No applicable `AGENTS.md` was found at the repository root, its `docs/mcp` ancestors, or workspace parents. Run 001/003/004/005 safety and evidence documents were consulted.
- Before further testing, SHA-256 baselines were taken for six existing production metadata paths: stable runtime queue/live status, the historical Project manifest/database/queue, and the user recent-projects index. Hash values are intentionally omitted from this public report; the same paths are checked again at the end.

Gate A has no authorization to invoke `abq2024.bat`, `SMALauncher.exe`, datacheck, Abaqus solver, or a real `QueueRunner`.
