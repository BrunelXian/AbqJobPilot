# G2.2 Version and Agent UX

## Application version

AbqJobPilot application version is `0.2.0`, with one authoritative value in `abqjobpilot/__init__.py`. The development window title, Help/version display, and read-only public capabilities response use that value. It does not change Automation Surface `1.0`, JSON schema `1.0`, or SQLite schema version `1`.

## Dashboard split

The Queue/Results horizontal pane defaults to 50:50 after Tk has laid out the window. On resize it reapplies the current session ratio; a user sash drag changes that ratio instead of being reset to 50:50. Queue/Results remain simultaneous and the G2.1 live STA/Console dashboard is unchanged. No layout setting or database field was added.

G2.3 later moved the version/build text from the main title into Help > About; the application version remains `0.2.0`.

## Agent navigation

Top-level menu order is Project, Task, View, Tools, Agent, Help (项目、任务、视图、工具、智能体、帮助). Agent offers the existing Console, Copy AI Instruction, Copy CLI Examples, read-only Capabilities, the existing Automation API Documentation, and About Automation Interface. The home toolbar still exposes Agent Command directly. Both routes use the same console-opening function. Capabilities are read from `AbqJobPilotClient.capabilities()`, not a separate GUI list. The documentation action opens `docs/ABQJOBPILOT_PUBLIC_API.md` in the system text editor; if it is unavailable, it copies the expected path and warns.

## Console workflow and language

The Console now presents a subtle safety/mode line, AI Instruction, command input and actions, a collapsed Command Reference, then Output with its own actions. The reference and AI Instruction draw examples from the parser's supported command map. The AI Instruction is vendor-neutral and remains English so users can copy it to Codex, Claude Code, ChatGPT, or another assistant. The supported internal syntax (`enqueue`, `enqueue-folder`, `list`, `help`, `clear` and flags such as `--inp`, `--cpus`, `--gpus`) is never translated.

All Console labels, buttons, safety text, help notes, and basic clipboard/input feedback use centralized English/Chinese UI strings. In Chinese, Agent is **智能体**, not 代理. Language changes update an open Console; closing and reopening also uses the current language. Machine-facing parse errors and structured queue/result details remain in their original English protocol text. The Console neither executes arbitrary shell commands nor directly starts the solver; an item it enqueues may later be executed through the existing GUI Start Queue workflow or an already active runner.

## Verification and limits

At G2.2 start, HEAD was `fb6e0d29db79eb3a0b703fd87382ea171e3f0d2a`; the G2/G2.1 changes were already uncommitted. Baseline: 85 tests passed. G2.2 checks cover one version source, parser-aligned examples, 50:50 geometry and manual sash retention, Agent menu order/actions, Console section hierarchy, English/Chinese labels and `help` output, toolbar/menu reuse, capabilities and documentation, and unchanged G2.1 behavior. Final full-suite rerun: 86 passed. An earlier run had 85 passed and one older GUI test skipped because Tcl could not initialize; the next full run passed all 86. Isolated `run_gui.py` smoke checks measured Queue/Results widths of 628/622 at 1280x800 and 708/702 at 1440x900, at Tk scaling 125% and 150%. No solver was started.

Limitations: the AI Instruction itself intentionally remains English; existing Settings and other non-Agent child dialogs are outside this localization stage. The divider ratio is session-only. The Agent menu is discoverability for an existing thin automation surface, not an AI Runtime or MCP integration.
