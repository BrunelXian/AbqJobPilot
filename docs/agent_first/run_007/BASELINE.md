# Run 007 — 本地基线与范围

本轮Dev为 `D:\Projects\abqjobpilot_dev`，`Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，应用0.3.0.dev0。起始无冲突、无已跟踪文件修改；Run002～006未跟踪交付完整保留。36个前轮实验源码/测试与Run006 SOURCE_HASHES逐一一致。原始状态与逐文件副本保存于本轮临时根；没有要求工作区干净或执行Git恢复。

读取根AGENTS及用户提供的环境策略；D:\、D:\Projects没有AGENTS，Dev内无更深AGENTS。读取Run001R ADR、Run002～006实际源码/测试、最终报告和验收矩阵、Run006协议及基线。沿用每Run独立目录、保存真实JUnit/输出/哈希/逐项映射的现有约定。本轮run_007此前不存在，未覆盖历史证据。

先读取 `D:\XianLab\envs\ENVIRONMENTS.md`，复用登记环境 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`。实测Python3.12.10 64位、pytest9.1.0、SQLite3.49.1、Windows11 build26300。没有安装或变更共享环境。测试关闭pytest插件自动加载、pyc及缓存，所有数据使用新的显式临时根。

本轮根：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run007_717d72f5f4784e26bf62031e26475d93`。每次测试均使用新的子目录作为basetemp，保留旧轮证据；私有连接凭据由各自harness清理，非秘密数据保留用于审计。

唯一写入主体为本任务。允许改动只在实验execution包、相关测试和本Run文档；没有旧GUI、Runner、Settings、Datacheck、Project或MCP行为修改。Schema3和应用版本不变；不迁移任何数据。

Stable完全排除，未访问；生产Project/Runtime/Recent/数据库未访问，未启动Abaqus、Datacheck、旧Runner或真实队列。没有切分支、恢复、stash、commit、push或同步；未清理旧备份及保护引用。测试进程终止仅针对本轮明确创建并核验身份、持续持有引用的进程。
