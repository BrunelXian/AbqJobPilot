# Run 006 — 开发基线与变更来源

仅操作 `D:\Projects\abqjobpilot_dev`。起始为 `Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，应用版本 `0.3.0.dev0`。没有冲突或已跟踪文件修改；66个既有未跟踪文件属于Run002～005。29个前轮源码/测试与Run005 SOURCE_HASHES逐一一致。前置成果保留，不要求工作区干净。

已读取根AGENTS、环境登记、Run001R ADR、Run002～005最终报告/验收矩阵、Run003协议及实际实验实现和测试。上级D:\、D:\Projects没有AGENTS。沿用按Run独立目录保存证据的约定；历史MCP交接不构成本轮Git操作授权。run_006起始不存在，未覆盖历史报告。

环境登记：`D:\XianLab\envs\ENVIRONMENTS.md`；使用 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`。本轮实测Python3.12.10（64位）、SQLite3.49.1、pytest9.1.0。虚拟环境python.exe是Windows转发器，实际Python映像与转发器分别核验。未安装或更改依赖。Python测试均关闭pyc和pytest插件自动加载，禁用pytest cache。

本轮独立临时根记录在[TEMP_ROOT.txt](TEMP_ROOT.txt)。起始git状态和源码哈希保存在该根的baseline-status.txt、before-hashes.json；各次测试使用新的basetemp，不删除旧轮证据。产品代码仅修改实验execution包；测试仅相关隔离工具和契约/进程验收；未改旧GUI、Runner、Settings、Datacheck、MCP、Project格式或应用版本。

Stable完全排除，未访问；没有生产Project、Runtime、Recent或数据库访问。未运行Solver、Datacheck、旧Runner或真实队列。没有分支切换、恢复、stash、commit、push、同步、共享环境修改。仅终止本轮创建且核验身份的测试进程，没有按进程名清理。

结束状态、实际文件差异、测试与清理统计见[最终总结](FINAL_SUMMARY.md)及[测试证据](TEST_AND_PROCESS_EVIDENCE.md)。
