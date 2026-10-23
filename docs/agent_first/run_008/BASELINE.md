# Run 008 — Dev 基线与改动边界

实际工作区 `D:\Projects\abqjobpilot_dev`，分支 `Develop`，HEAD `fb7912ec9e0107b18f65948b147c87579c87cded`，应用 `0.3.0.dev0`。开始与实施中复核无冲突、无 tracked 修改。Run002～007 为已有未跟踪工作；起始38个实验源码/测试逐一匹配Run007 SOURCE_HASHES，已在本轮独立临时根保存哈希和逐文件副本。没有要求工作区干净或执行Git恢复。

读取实际根AGENTS、适用上级指令存在性、环境登记、Run001R设计、Run002～007最终报告/验收矩阵及当前执行、IPC、验证、授权、诊断和测试代码。沿用每Run独立目录、原始JUnit/输出、逐项验收、源码哈希与进程清理记录的协议。run_008原先不存在；历史交付没有覆盖。

唯一写入主体为当前任务。前置修改与本轮增量见 [CHANGE_SCOPE.json](CHANGE_SCOPE.json)；前轮全部测试保持原内容。本轮新增两模块public_workflow/test_authority、两示例、两测试文件；增量修改六个已有实验模块：__init__、service、client、supervisor、reconciliation、diagnostics。旧产品GUI、Runner、Settings、queue-only API/CLI、MCP未改。应用版本、IPC envelope版本、实验Schema3不变；无迁移。

先读 `D:\XianLab\envs\ENVIRONMENTS.md`。使用登记绝对解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，实际Python3.12.10、pytest9.1.0、SQLite3.49.1、Windows11 build26300。venv launcher与实际Python进程分别核验；实际image为基础Python312。未安装或更改共享依赖；没有调用模型API。

本轮独立临时根为 `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run008_4668b8a810324ba288be12587006710a`。演示、每次pytest使用新的子目录；显式Project、Runtime、Recent哨兵、输入、会话、私有连接材料与导出分开。关闭pyc、pytest自动插件和cacheprovider。最终测试结果不引用前轮passed数字。

Stable完全排除，未访问；生产Project/Runtime/Recent/数据库未访问。没有Abaqus、Datacheck、旧Runner、真实队列、共享环境修改、Git切换/恢复/commit/push/同步。进程清理仅本轮明确创建且按OS身份核验的测试进程。
