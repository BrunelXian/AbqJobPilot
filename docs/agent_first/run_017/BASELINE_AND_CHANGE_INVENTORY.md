# Run017 — Dev 基线与累计资产

审计日期：2026-10-24。唯一工作区 `D:\Projects\abqjobpilot_dev`；`Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63`，应用 `0.3.0.dev0`，无未解决冲突。没有为匹配历史 SHA 切换或恢复 Git。适用根 AGENTS.md 与环境登记已经读取；明确的上级 AGENTS.md 检查未发现其他文件。沿用各 Run 的追加交付方式，不覆盖旧编号、冻结证据或历史结论。

## 盘点口径

- 开始时676个跟踪文件、404个未跟踪文件、117个忽略文件；跟踪修改21项，跟踪新增/删除0项，未暂存任何内容。
- 完整文件名、组别、大小、SHA-256，以及原始 status 见 [BASELINE.json](BASELINE.json)、[GIT_BEFORE.txt](GIT_BEFORE.txt)。1080个非忽略文件合计21,386,046 bytes。未跟踪不等于本轮新增。
- `SOURCE_ASSETS.csv` 覆盖91个应用/示例 Python 模块；[SOURCE_SYMBOLS.json](SOURCE_SYMBOLS.json)定位实际顶层函数/类。调用者、测试候选来自AST/词法索引，**不是动态覆盖或无副作用证明**；下面和架构报告是人工复核的主要边界。引入阶段依据对应 Run 报告；未有证据的旧文件标为 legacy/未知，不按名字猜时间。
- 只检查 Dev 内资产及明确保护文件摘要。没有访问 Stable，没有连接当前 Run016 owner、扫描其进程或操作已有GUI；历史事实只从保存报告取证。保护清单523项包括既有冻结材料和明确历史状态文件，末次核验另见 `FINAL_INTEGRITY.json`。

开始时21个跟踪修改：execution 包的 client、diagnostics、process_backend、process_contract、process_fixture、process_reconciliation、public_workflow、reconciliation、service、standard_backend、standard_contract、standard_process、supervisor；execution_gui；examples 的 dev_gui_demo、standard_client、standard_service；tests 的 run003_process、supervisor_helpers、test_execution_gui、test_execution_isolation。新的 closeout、managed_process、standard_sequence、相关测试/入口及 Run014–016 报告在未跟踪集合中。这些均为前置成果。

## 主要资产及处置建议

以下路径均相对 Dev；全文件级清单见 [SOURCE_ASSETS.csv](SOURCE_ASSETS.csv)。

| 实际模块/阶段 | 职责/调用者 | 副作用与权威 | 实际测试索引 | 建议 |
|---|---|---|---|---|
| execution/models, paths, planning, authorization, store, service / R2起 | 上下文、固定计划、许可、幂等、事务、派发；可信准备/Supervisor | plans/grants/receipts/runs/events 同一 execution.sqlite3；仅持有owner的写入口 | execution_contract/store/ownership/isolation | 保留；分层文档先于拆包 |
| execution/client, protocol, supervisor, ownership / R3 | 公共客户端、认证IPC、独立工作线程、OS排他锁 | 客户端连接；Supervisor独占Store；无公共mint/任意命令 | fake_supervisor, diagnostic_supervisor | 保留；Fake前缀是历史命名债务 |
| execution/fake_backend, validation / R2 | 固定模拟TXT/JSON与独立验证 | 显式临时根；无OS启动 | execution_contract, fake_reconciliation | 保留，不隐藏真实启动参数 |
| execution/reconciliation, process_reconciliation / R4/R7 | Fake产物采纳、已记录完整固定进程退出收尾 | 精确管理许可/回执/事件事务；不自动resume | fake_reconciliation, recorded_exit_reconciliation | 保留相互不同的证据资格 |
| execution/diagnostics, audit_export / R5 | 一致有界持久化投影、客户端导出 | 只读事务；导出仅指定新JSON，不读取Artifact字节 | run_diagnostics, diagnostic_supervisor | 保留；普通多次GUI读取不冒充此原子快照 |
| execution/process_contract/backend/fixture/handles / R6 | 固定Python执行、OS身份/句柄、退出事实 | 仅固定夹具；Run先持久；owner持有进程观察 | process_contract/fixture, recorded_exit_reconciliation | 保留；夹具与真实Backend不得共用自报完成判据 |
| execution/public_workflow, test_authority / R8 | 公共inspect/显式validation；可信TEST_ONLY操作 | 客户端不能mint；trusted函数仍受同用户shell信任边界 | public_workflow, public_client_example | 保留，明确操作者边界 |
| abaqus_preview/* / R9–10 | 受限INP离线prepare/inspect/export | 读取显式工程根；不创建Run/Grant/Store | abaqus_preview, abaqus_preview_integration | 保留独立类型，不能自动升级ExecutionPlan |
| execution_gui, gui_app显式连接分支, gui_legacy / R12 | 原GUI只读服务查看/延迟legacy依赖 | 公共client读取，不写旧历史库；关闭不停止owner | execution_gui | 保留；gui_legacy是导入集合，不是新Runner |
| execution/standard_contract/backend/process/dat / R13 | 固定2024轴向杆、真实能力类别、独立DAT解析 | 固定入口/资源/输出；启动意图；同一Store；真实路径本轮由替身覆盖 | standard_backend/admission/supervisor | 保留；安装/解释器硬编码仍是单机实验限制 |
| execution/closeout / R14 | 只读评估及行政槽位处置 | 不覆盖UNKNOWN；旧路径保留；PAUSED | standard_closeout, closeout_windows | 保留，不与正常完成合并 |
| execution/managed_process / R15 | 创建时JOB_LIST、直接Job范围查询、句柄生命周期 | native CreateProcessW；无Kill/Breakaway/普通启动回退 | managed_scope | 保留；仅当前受管范围不是整机进程树 |
| execution/standard_sequence / R16 | 固定A→B服务端资格/时间窗 | A正常收尾+Solver+数值+有效B；无DAG | standard_managed/windows, standard_pair_client | 保留为受限序列，不泛化工作流引擎 |
| api/*, mcp/*, agent/* / legacy | queue-only API/CLI、5只读MCP、GUI命令面板 | legacy Project/Runtime；非新服务入口 | public_api, queue_only_enqueue, mcp_readonly | 标注LEGACY_ONLY；未来适配不能静默改语义 |
| runner_core, queue_store, settings_store, config, project/*, database/* / legacy | GUI拥有Runner、JSON状态和历史同步 | 与AF不同锁/DB权威；部分load/query会写 | project_model/database/file_ownership；legacy native mock | 保留兼容；生产迁移单独设计 |
| examples/agent_first/* | 可信演示准备、服务启动、公共客户端、GUI入口 | 可创建隔离数据/许可/进程；VBS不是普通匿名API | public_client_example, execution_gui, standard_* | 不当最终安装器；真实历史按钮不得当新例子重跑 |
| docs/run010–011 控制器及历史执行脚本 | 冻结研究与一次性取证 | 存在历史真实入口，但不在服务生产调用链 | 本轮不重新运行 | 归档/废弃运行候选，保留字节；不删除 |

## 重复与技术债务（不是本轮重构指令）

1. legacy `process_identity`、AF `process_handles`、`ownership.current_process_identity`、Standard观察器职责相近但契约不同：候选身份、保留句柄、owner锁、受管范围不能简单合并。先提取契约测试再考虑共享纯函数。
2. AF `models.canonical_json/digest` 为统一计划/回执摘要；legacy JSON格式、历史控制器摘要有独立冻结含义。不能全仓替换改变既有授权摘要。
3. `FakeClient/FakeSupervisor` 及 execution 包test-only docstring已经落后于受限真实能力；命名/文档债务，非第二执行核心。此次不改已冻结源码。
4. `standard_contract.ENTRY/PYTHON/CMD` 与示例绝对路径是明确的本机固定验收约束，不是可迁移产品配置。未来显式profile改造需重新绑定计划/许可和宿主验收，禁止自行PATH回退。
5. default config/Recent/globalRuntime仍存在于legacy路径；AF连接分支隔离。新旧入口指向同一工程目录时没有统一跨框架输出租约，不能承诺安全混用。

## Git资产与检查点建议

[GIT_DATA_REVIEW.json](GIT_DATA_REVIEW.json)：在本轮基线非忽略文件中未发现 `.db/.sqlite/.sqlite3/.odb/.cae`；发现一个420-byte固定INP、测试INP、10,334-byte历史DAT离线样本、空stdout/stderr和约4.98MB历史PUBLIC_OBSERVATIONS.jsonl。它们不是生产工程目录扫描结果。JSON敏感键扫描未发现可用连接秘密字段；这不是通用匿名化/密钥审计证明。真实报告含机器路径、PID、安装信息；公开发布前需单独审查日志正文及许可相关文本，不改本地原证据。

`.gitignore`已排除pycache、旧runtime状态、Abaqus常用输出；缺少对实验DB、private/bootstrap/connection等新数据命名的完整规则。它不会保护每个任意文件名；提交前使用明确文件清单，禁止`git add .`式全收录。既有 `.pytest_cache`、`old_tests_tmp_*`、历史被拒绝清理的目录只记录，未删除。建议未来忽略规则修订单独审阅，不让规则遮蔽应保留证据。

可以准备本地Dev检查点的人工复核，尚未提交：

1. `Add audited closeout disposition with retained output isolation`（R14实现+测试）；
2. `Add managed Windows process scope and normal completion`（R15依赖上项）；
3. `Bind fixed Standard sequence to managed completion and bounded grants`（R16依赖前项）；
4. `Document Dev capability boundaries and Run017 audit`（文档/本轮格式测试）。

研究/历史报告可独立提交，保留必要manifest、结果摘要、有限离线fixture；大型轨迹与本机临时文件需先决定可复现价值和私密性。源码跨阶段有重叠，不能机械按目录拆提交；人工选择patch并逐提交回归。最终检查：文件allowlist、敏感数据复查、无私钥/真实Grant/DB、大文件、引用链接、相关测试、冻结摘要、版本/分支。检查点不等于0.3.0发布或Stable晋升。

本轮主动修改限定为两份README的当前能力说明，以及本目录审计、证据和两项格式隔离测试。没有应用源码、既有测试、版本/Schema、冻结历史材料修改。末次比较发现保留中的Run016 GUI A_reconnected/B的`view.json`持续变化；`tests/run012_gui.py:24–33`的渲染回调会写这些派生视图，与保留运行中的GUI一致。它们不属于523项冻结保护集合，既未被本轮写入也未停止刷新；在FINAL_INTEGRITY单列，不能把整个历史目录声称为逐字节静止。未发现其它非预期变化。
