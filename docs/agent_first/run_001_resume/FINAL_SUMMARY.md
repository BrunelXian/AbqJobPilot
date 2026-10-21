# Run 001R — 结论与下一步指令

日期：2026-10-21。结论：`PASS_ABQJOBPILOT_AGENT_FIRST_RUN001R_DEV_DESIGN_READY`。

该状态仅表示当前 Dev 的设计与 Run 002 施工边界具备审查/实施条件；不表示执行服务已实现、独立监督已具备或真实 Abaqus 已通过验收。本轮结束，不自动进入 Run 002。

## 1. 实际基线与范围

唯一工作区 `D:\Projects\abqjobpilot_dev`，分支 `Develop`，HEAD `af3fd79667ef70693d616f7f8cfba9c5a7f5b21b`，应用版本 `0.3.0.dev0`。起始工作区干净，无未解决冲突。Stable 完全排除，未访问，不作为本轮缺口。没有继续 Git 恢复工作。

## 2. 新增和修改

新增五份交付：

- [BASELINE.md](BASELINE.md)：Dev 起始事实、历史材料和版本入口检查。
- [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md)：调用链、写入路径、能力/限制及源码证据。
- [ADR_AND_CONTRACTS.md](ADR_AND_CONTRACTS.md)：七项 ADR 修订、对象、事务、授权、状态和单进程切片契约。
- [MVP_ACCEPTANCE_MATRIX.md](MVP_ACCEPTANCE_MATRIX.md)：Run 002 的16项验收、建议模块及后续完整模拟/真实验收边界。
- 本文件：结论与可直接交付下一任务的指令。

另新增根 [AGENTS.md](../../../AGENTS.md) 固定 Dev 边界；最小修改 [README.md](../../../README.md) 与 [README_CN.md](../../../README_CN.md) 当前 Develop 版本说明及设计阶段边界。总计8个文件。未改功能源码或测试代码；原 [Run 001 ADR](../run_001/ADR_AND_CONTRACTS.md) 与历史记录保留。

## 3. 保留与修订

保留显式 ProjectContext、统一 ExecutionService、独立 Supervisor、可替换 Backend、Project 内事务执行存储、客户端共用服务、单主机单槽及 Project-owned Data。外部 CAE/INP/ODB 保持引用。现有 Abaqus 适配规则、Process Identity、锁和保守恢复能力作为后续复用对象。

修订重点：当前 Dev Settings 未具备旧 main 的严格持久化校验与显式保存绑定；Runner 仍受全局 Runtime 和 GUI 线程生命周期影响。将 Project 身份、Plan 配置和 owner/进程身份分开；不可变请求回执与当前 Run 视图分开；Fake 完成、Solver 结论和 Artifact 验证分开。首个实现切片缩为单进程，不把独立 Supervisor/IPC/跨进程恢复一次带入。

已确认的后续真实执行风险包括 Datacheck 无完成证据的 PASS 兜底、launcher 退出后未等待子进程门禁、跨 Project/启动瞬间输出保护缺口，以及 Artifact 路径关联不等于本次产出证明。本轮仅记录，不顺手修功能。

## 4. Run 002 最小范围与完成标准

显式临时 ProjectContext→固定 Plan→测试夹具 Grant→幂等 submit→明确内部 execute_pending→Fake→Run/Event/Observation/Validation 持久化→只读查询。新实验格式不打开/迁移旧 project.db、不写旧 queue/live，不从默认 Recent 选目标。真实 Abaqus 路径必须在依赖和接口上不可达。

至少完成矩阵 R2-01～16：无 GUI；同键同内容同 Run/一次副作用；异内容结构化冲突；Project/计划/授权/资源错误拒绝；关闭后回执和事件可查；Fake 与验证分开；查询零初始化/迁移/修复；全部输出临时根内；并发、真正 Retry、失效计划、故障事务和 canonical digest 有相应测试证据。后续完整模拟 MVP 和真实验收分别执行，不借用本切片结果。

## 5. 已做检查与未验证能力

本轮执行静态源码/测试/历史文档阅读、只读 Git 起始状态、版本引用核查、文档本地链接和 diff 检查；结束检查记录见下文。没有运行 pytest 或 Python 导入，也未运行 GUI、CLI capabilities 或 MCP transport。没有当前测试 passed 数可报告。

未验证：新服务任何运行能力；独立 owner/IPC/断线监督；跨进程崩溃恢复；跨 Project 输出锁；真实批准隔离；实际 Windows/Abaqus 进程树；严格输入固定与真实 ODB/结果有效性。它们是明确后续验收项，不是 Fake 内部契约实施的待决前提。

旧 ADR 的3个本地交付链接缺目标，是历史中断留下的缺口，保持原文；新交付自包含，不依赖这些缺失文件。历史数据库/Process Identity 文档的阶段性描述与当前代码差异已在架构复核标明。

## 6. 下一条可直接执行的 Run 002 指令

```text
# AbqJobPilot Agent-first — Run 002

请仅在 D:\Projects\abqjobpilot_dev 实现 Run 001R 定义的单进程 Fake 内部服务切片。
先读本目录及适用上级实际 AGENTS.md、docs/agent_first/run_001_resume 的五份交付，
并按 D:\XianLab\envs\ENVIRONMENTS.md 核验已有绝对 Python 解释器、版本与测试依赖。
不要访问 Stable、真实 Project/Runtime/Recent 或生产数据库；不要安装共享依赖。

预期分支 Develop，已知设计基线 af3fd79667ef70693d616f7f8cfba9c5a7f5b21b，
版本保持0.3.0.dev0。先只读确认实际 HEAD/状态/冲突，保留 Run 001R 文档和用户修改。
如果分支/HEAD 与预期不一致或有未解决冲突，停止相关写入并报告，不恢复或切分支。

按 ADR_AND_CONTRACTS.md 和 MVP_ACCEPTANCE_MATRIX.md 实现：
显式 ProjectContext、固定 Plan、仅测试夹具可登记的精确 TEST_ONLY grant、
事务一致的 receipt/Run/idempotency/event、单进程单槽 ExecutionService、
显式 execute_pending、唯一 Fake Backend、独立 Artifact validation 和只读查询。
Run ID 必须先于 Fake 副作用持久化。使用新的独立实验 Project/存储格式；
create 只接受全新临时目录，open_existing_read_only 不创建、迁移或修复。
同键同内容返回原 receipt/Run；同键不同内容冲突；真正 Retry 建新 Run 并关联 retry_of。
按建议新增 execution 包和隔离测试；必要的局部实现细节自主决定并记录，
不扩展到旧 GUI/Runner/API/MCP 的行为变更或旧 schema 迁移。

真实 Abaqus 启动必须结构上不可达：不导入或调用旧 runner_core，
不接受 arbitrary command/callable/dynamic Backend，不存在 real backend 开关。
Fake 只写临时根内 JSON/TXT；不生成 CAE/INP/JNL/ODB 作业或结果。
测试必须使用显式临时 Project、Runtime、Recent 哨兵与输入；禁止默认路径访问。
完成 R2-01～16，并提供启动 trap、调用边界、临时文件 inventory、事务及只读查询证据。
只跑与该切片有关的隔离测试；旧测试先静态确认副作用，不能直接全量运行。

排除独立 Supervisor、IPC、GUI/MCP/外部 SDK 适配、跨 Project 主机输出协调、
跨进程崩溃恢复、真实授权 UI、真实 Backend、Solver 控制、生产迁移与发布。
不执行 checkout/reset/restore/clean/stash/merge/rebase/commit/push，不改共享环境。

按 Run 约定在新 docs/agent_first/run_002 保存基线、实现说明、实测结果与总结；
若目录存在使用新编号，不覆盖证据。发现关键并行修改或基线变化停止相关写入并报告。
完成后报告实际修改、执行过的测试、未通过/未覆盖项及后续最小切片，停止，
不自动开始下一 Run，不将 Fake 验收称为真实 Abaqus 或正式0.3.0验收。
```

## 7. 未执行的受限操作

未访问 Stable；未改功能源码/测试或 Schema；未启动 Solver/Datacheck/真实 Runner/真实队列；未打开已有生产 Project；未创建、初始化、迁移或修复生产数据库/Runtime；未操作快捷方式、共享环境或用户进程；未切换/恢复分支、写 stash、merge/rebase/commit/push、清理备份或保护引用、修改远端设置。本轮只读 Git 与 Markdown 交付，不自动进入 Run 002。

## 8. 版本说明与发布门槛

应用版本修改前后均为 `0.3.0.dev0`：当前基线已完成版本调整，本轮不改 `__init__.py` 或断言。英中 README 各两处当前 Develop 文案从 `0.2.2.dev0` 改为 `0.3.0.dev0`。GUI About、CLI capabilities、MCP Server 静态均引用同一 `__version__`；未做运行验收。历史版本记录、API/JSON/Project/数据库 schema 不变。

正式 `0.3.0` 至少需要完成最终声明范围的内部服务与完整模拟验收、真实 Abaqus Backend/结果验证及相关客户端/兼容回归；若承诺迁移或控制能力还需对应专项证据。之后单独授权版本发布、提交/推送和 Stable 晋升；设计 PASS 或 Fake PASS 均不自动触发。

## 结束检查记录

- 8个交付/修改文件的89个本地文件链接目标均存在；检查目标限于 Dev，没有跟随外部链接或访问 Stable。历史原 ADR 的缺失链接不在本轮修改集合内，已单独披露。
- 8个文件代码围栏配对、行尾空白检查通过；`git diff --check` 无错误。已人工审查 README diff，保留历史版本文字。
- 分支与完整 HEAD 保持上述基线；最终变更集合仅2份 README、根 AGENTS 和本轮5份文档。`abqjobpilot/`、`tests/`、旧 `docs/agent_first/run_001/` 无 diff。
- 原 ADR SHA-256 保持 `7254F40818A9957AAF92D953FAD3AFFA65B34EB0814AC1AC6DE9ACA0804DA124`。
- 版本入口检查为静态检查；pytest、进程启动、真实 Abaqus、生产数据验收均未运行。
