# Run017 — 架构、权威与兼容边界

结论：存在一个共用的 **Agent-first ExecutionService**，没有发现新Backend绕开该核心成为另一产品执行框架；但整个软件尚非“所有入口统一服务”。legacy队列执行、API/CLI/MCP与新服务并存。调用方向是客户端→Supervisor IPC适配→ExecutionService→Backend/Store，不是客户端直接拥有Supervisor生命周期。

## 实际调用链与写入权威

| 路径 | 实际函数/入口 | 写入/生命周期权威 |
|---|---|---|
| 新公共Python | `execution.client.FakeClient.submit` → `protocol` → `FakeSupervisor._handle/_invoke` → `ExecutionService.submit` | 原接收回执、Run、Grant消费、事件同一事务；客户端不持有DB |
| 派发 | `FakeSupervisor._work` → `ExecutionService.execute_pending` →固定Backend | 独立worker，slot原子领取；IPC接收线程不等待Solver循环 |
| 新GUI | `gui_app.AbqJobPilotApp.__init__`显式execution_connection分支→`ExecutionView/Reader._loop`→FakeClient | 只读、后台轮询、有界队列；不初始化旧Project/Runtime、不双写旧历史 |
| 可信设置 | `create_experiment/acquire_initial_preparation_store`、`planning/standard_contract.prepare`、`issue_execution/issue_pair` | 显式新存储及OSowner互斥；仅可信操作者可调用，不是普通RPC |
| legacy GUI | 默认`gui_app.main`→GUI拥有`QueueRunner`→`runner_core.run_next_job` | config.RUNTIME_DIR、queue/live_status/report，GUI刷新同步project.db |
| legacy程序接口 | `api.AbqJobPilotClient.for_project`/`api.cli.main`/`mcp.ReadOnlyTools` | queue-only写入或只读Project查询；不通过AF Supervisor |
| 文档实验控制器 | Run010/011固定控制器 | 历史一次性观察，不写AF正式Run，不是当前真实Backend入口 |

AF的`experiment.json`固定Project ID、instance、generation、root/文件身份与context摘要；`execution.sqlite3`为业务事务权威。运行输出及证据文件是非事务外部事实，摘要/观察记录指向确定内容；文件副作用不会被数据库回滚撤销。owner.lock的排他字节锁是写所有权，owner.json/endpoint.json是身份与发现信息，不能单凭文件/PID/超时接管。`ReadOnlyStore`不取得写owner。

## 已确认保证与限制

1. **显式上下文**：`store.validate_context`核对类型、路径、manifest摘要、Project实例、generation、目录device/inode；复制/移动不能继承活跃许可。每个Supervisor绑定一个Store，不接受请求改根。
2. **身份**：AF `JobSpec.job_id`是逻辑任务；`Run.run_id`执行前产生；`SubmissionReceipt.request_id`是业务回执；传输request_id仅关联一次RPC；idempotency_key由固定服务namespace限定。旧API的`job_id`仍可能代表queue_id，旧Project job_id是另一层逻辑身份，兼容层必须明确，不能统一字段名后悄悄换义。
3. **幂等与许可**：submit同键同内容返回原回执；异内容冲突；真正retry新Run并保留retry_of。Grant在接受事务消费，派发前再查计划/期限/输入/资源，不退款以便重跑。连接凭据、TEST_ONLY执行、管理许可、REAL_FIXED_STANDARD能力类别分开。`standard_contract.check_grant`拒绝Fake许可；离线AbaqusPlanPreview不是ExecutionPlan。
4. **可信边界**：测试/真实issue函数是同进程可信操作者API，非人类审批认证平台；普通RPC白名单无mint/approve、动态Backend、任意shell、可调用对象。拥有同OS用户任意shell/文件能力的人能调用可信代码，此机制不构成OS安全隔离。不得把审批来源字符串当成强身份认证。
5. **单owner/单槽**：`LocalOwnerLock`使用不可继承OS锁；`ExperimentStore.transaction`再验证lease，BEGIN IMMEDIATE；独立服务对象与进程不能并发越过同Store领取。保护只到本实验存储和声明输出策略，不承诺主机/跨Project/legacy互斥。
6. **进程/结果分维度**：Fake为process NOT_APPLICABLE、Solver NOT_RUN；ProcessFixture固定角色与可信OS退出/独立validation；Standard分别记录创建、观察、managed_scope、Solver文本、DAT、ODB NOT_RUN。三个Backend共用Run/回执/事件/许可机制，但证据资格不同，不能靠一个通用success布尔值互转。
7. **受管范围**：`ManagedScope`在CreateProcessW创建时使用JOB_LIST，无先运行后Assign窗口、无unmanaged fallback、无breakaway/伪父进程、无KILL_ON_JOB_CLOSE。直接Job accounting确认活动数0，且启动阶段结果与范围关联有效，才有范围结束依据；PID枚举不是全集证明。仅根及按该Job继承的后代；外部服务/域外工作不受此证明覆盖。嵌套外层Job、注销/关机仍有宿主限制。
8. **正常收尾与行政**：`service`将范围证据、正常终态、slot释放事务提交，失败保留不确定；`closeout.apply_recorded`仅精确授权的逻辑处置，不篡改UNKNOWN、不解除旧路径隔离、保持PAUSED。`standard_sequence.check_start`只接受正常COMMITTED_EMPTY_SCOPE与Solver/DAT通过，不接受行政放行替代。
9. **崩溃窗口**：Run接受→claim→启动意图→OS创建→身份→退出/范围观察→终态分别有可失败窗口。缺PID不证明没启动；owner失联/范围句柄失联不接管，不重新建空Job假装结束，不自动retry。既有测试覆盖真实owner终止、持久化失败和丢应答。
10. **重启**：`acquire_supervisor_store`仅全新且从未启动/无Run的实例首次保持OPEN；后续owner获取均PAUSED。GUI连接不触发它。恢复为独立授权动作；旧resume回执重放不重开新owner的门。

## 查询副作用核查

| 入口 | 真实行为 | 使用边界 |
|---|---|---|
| AF ReadOnlyStore._connection | mode=ro、query_only、显式格式检查；journal/WAL/SHM拒绝维护；无建库/迁移 | 合格读取路径；不能把活库标immutable |
| diagnostics.collect / closeout.preview_store | 单一BEGIN读取有界快照，事务外投影/序列化 | 预览不批准/探测/修复；来源时间独立 |
| client.run/events/validations/progress + GUI | 多个只读调用；progress读取允许范围的有界日志 | 无写入；整屏不是单一跨DB/文件/OS原子快照 |
| legacy queue_store.load_queue | 调用init_storage | 不能作为生产审计的纯读取；显式read_queue才适合 |
| settings_store.load_settings | 创建runtime目录；load_settings_for_runtime为显式读取 | 不能沿用旧main补丁结论推断Dev写后严格校验 |
| ProjectManager.open_project/register_project | 验证后写Recent | 查询用validate_project/load_project_info，不用open |
| gui_app._sync_current_project_history | GUI刷新/动作可sync_history_from_runtime | legacy GUI打开/刷新不是只读审计工具 |
| ProjectHistoryRepository默认实例 | 查询连接也可能initialize_database | 严格read_only=True +显式schema检查；不以get/list命名判安全 |

IPC `af-local-json-v1`：loopback TCP、认证且绑定Project/owner/context、64KiB请求、256KiB应答、8连接、2秒分帧预算、事件每页最多64；诊断128KiB、字段/记录限额，超限报错不静默完整化。连接错误不等于任务失败/取消，也不许可新键重试。

## 格式与迁移矩阵

| 对象 | 当前格式/可用范围 | 兼容/风险/未来迁移 |
|---|---|---|
| legacy Project | project.json，application=abqjobpilot，schema1.0；runtime/queue/live、project.db schema1 | 原GUI/API/MCP使用；外部INP/CAE/ODB默认引用；显式导入导出才复制Project-owned文件 |
| AF实验Project | experiment.json；format abqjobpilot-agent-first-experiment；execution.sqlite3 format3 | 明确新建、显式路径；读取1/2/3，写入口只支持3；不自动把旧库升级为3 |
| 新旧混用 | 不同manifest、文件名、身份验证 | 两项新实际测试确认互相读取拒绝且字节不变；不能仅改manifest名让旧程序打开新Store |
| AF复制/导入 | context含根物理身份/generation/摘要 | 现有活动许可不随复制合法化；尚无生产迁移工具 |
| 公共计划 | af-experiment-v1、固定类型和digest | 应用版本不改变已有Plan摘要语义；预览schema abaqus-offline-preview-v1独立不可执行 |
| 诊断导出 | af-run-diagnostic-v1/v2/v3，backend对应rule版本 | 白名单历史投影；不含Artifact字节/权限；不是可恢复数据库或当前OS健康证明 |

Project owns its data：新旧Project各自拥有元数据、索引、Run/Event/Evidence引用，原工程文件继续外部引用。真实夹具复制输入是显式可信准备，不是平台默认搬迁工程。未来生产迁移必须离线备份/精确格式识别/独立新目标/验证后切换唯一写权威；禁止长期JSON↔SQLite双向写、伪造历史退出或验证证据。本轮没有迁移任何数据。

## 历史实测核对（不是本轮新执行）

- [Run014处置](../run_014/disposition_001/FINAL_SUMMARY.md)：r_609c9bbfd9c54b3ca2fce23bbd6059e4，revision20→21；NULL逻辑槽、PAUSED、RETAINED_NO_REUSE、UNKNOWN和原DAT/Solver不变。没有把管理lease当原owner接管。
- [Run016实测](../run_016/real_001/FINAL_SUMMARY.md)及POST_RUN_AUDIT：A r_9ae29c47995d457894c553da404e8680 rev37；B r_8ddc32af19a14ae7b16c19f2360e6c81 rev30。各一次，范围COMMITTED_EMPTY_SCOPE、各total12/active0、两项DAT三值通过；事件36/37 A收尾先于38 B接收及43/44创建，66/67 B收尾。整体成员/域外UNKNOWN，ODB NOT_RUN。GUI及venv退出后owner/Solver存活证据和原Run重连有保存记录。
- 本轮仅复核这些静态记录与保护摘要，没有重新运行、连接、停止或恢复历史服务。历史PASS不代表所有产品入口、所有分析模式或新的当前OS状态已验证。
