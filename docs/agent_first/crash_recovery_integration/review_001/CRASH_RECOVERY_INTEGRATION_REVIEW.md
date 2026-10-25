# CR-D01 — Crash Recovery 集成审查

审查日期：2026-10-25。结论：**设计就绪，未实施恢复**。本报告中的“已有测试”指已阅读的测试源码及历史验收记录；本轮没有重新运行应用回归，也没有查询历史实例或当前 OS 进程。

## 基线、读取范围与证据等级

- 仓库 D:\Projects\abqjobpilot_dev；Develop；HEAD 271c6f82fd6a4599dbae2df30d903dab2cef1f63；版本 0.3.0.dev0；无未解决冲突。
- 开始时 25 个 tracked 修改、827 个 untracked 文件；1503 个非忽略候选文件逐文件 SHA-256 留存于 BASELINE.json。包含前轮成果，均不清理、不暂存。
- 已读实际 AGENTS.md、环境登记、Run003 的实现协议和各相关阶段总结/契约。当前没有额外的统一 Run 协议文件被发现；采用独立追加目录、原记录不覆盖及阶段停止规则。
- Python 仅用登记的 D:\XianLab\envs\LangChainEnv\Scripts\python.exe，3.12.10，标准库只读 inventory/文档校验；不导入应用、不启动 GUI/Supervisor/Backend。
- 完整阅读授权交接副本的八份文档：README、INCIDENT_AND_ROOT_CAUSE、STABLE_IMPLEMENTATION、RECOVERY_CONTRACT、DEV_COMPATIBILITY_MATRIX、DEV_INTEGRATION_PLAN、TEST_AND_ACCEPTANCE、OPEN_ISSUES。原文摘要见 BASELINE.json。交接包中描述的 Stable 实现/生产事故属于**来源报告**，本轮不访问 Stable，也不打开其提及的生产目录。
- 实际核实 Dev 源码/测试；阅读 Run003–008、014–016、018–021B 总结及 Run014 disposition_001、Run016 real_001、Run021B real_001 的独立结果；对照 Run022 RC 和 Run023 设计。没有把历史测试数加总成当前通过数。
- 所有路径引用均指 Dev 中代码/报告，除上述明确允许的交接副本。没有检查历史实验外部数据库、运行凭据或活动 owner。

## 可以直接复用的原则，不能照搬的机制

| 交接原则 | Dev 采用方式 |
|---|---|
| 异常中断不等于求解失败；存在 ODB/.lck 不等于完成 | 分离 execution、managed_scope、solver_conclusion、numerical_validation、ODB；诊断不可改写这些字段 |
| GUI 崩溃不等于执行 owner 崩溃 | 使用既有独立 Supervisor 和身份认证；GUI 只是观察者 |
| 精确对象、重新评估、显式授权、审计和输出保留 | 复用原 LocalOwnerLock、management_grants/receipts/consumption、reconciliations、control_events 和同一事务 |
| 正常退出遥测缺失不能让恢复永远只有误导性“仍运行”显示 | 增加有出处的疑似中断诊断；并不因此允许释放槽或重跑 |
| 已经排队的其他任务不受处置影响 | 保留原 PENDING/PLANNED、receipt、Grant 消费；绝不转换为新请求 |
| 新尝试与旧结果隔离 | 未来独立新 Run/phase_attempt_id、Plan、Grant、Job/output，保留 retry/source 关联；当前 Standard 不支持 retry |

不复制 Stable QueueRunner、queue.json/live_status.json 写入、Tk 内存批准 token、跨文件 PREPARED/APPLIED 事务补偿、按进程名扫描“全部 Abaqus 消失”或把 UNKNOWN_INTERRUPTED 直接塞入新 Run.execution。Stable 交接明确列出的跨 JSON/SQLite 非原子性，Dev 已用同库事务提供更严格保证。

## 已有能力与真正缺口

1. **不是缺少恢复核心。** ExecutionService 已提供 Fake 证据采纳、固定四角色 OS 退出对账、Standard 行政处置、独立 resume、同键管理回执重放。见 [能力矩阵](DEV_CAPABILITY_GAP_MATRIX.md)。
2. **不是缺少排他管理锁。** examples/agent_first/standard_closeout_operator.py 的 review-and-decide 使用 acquire_supervisor_store，最终仍取得原 owner.lock 的同一 Windows 字节锁。活动 owner 存在就拒绝。它会写 owner/gate，不能当成只读 Inspect，也不是产品 Project 的通用恢复入口。
3. **不是受管范围正常收尾失败。** managed_process.ManagedScope 将根进程在 CreateProcess JOB_LIST 时纳入未命名 Job；原句柄查询并持久化 EMPTY_CONFIRMED 才可正常收尾。owner 崩溃后不能重新构造这个证明，Test test_managed_true_crash_after_empty_before_commit_does_not_release 明确保留阻断。
4. **缺少跨重启诊断模型。** 现有 owner/run 身份没有统一启动会话/boot provenance 对照；当前 PID 不存在、IPC 不通或 Job 句柄丢失只会保守阻断。缺少明确原因和时间来源的产品可读中断分类。
5. **现有处置策略覆盖不够，但不能放宽旧策略。** closeout.assess 要求 BLOCKED、PAUSED、占槽、结束观察事件和所有已观察成员真实退出匹配，才可行政释放。断电/owner 异常导致这些记录缺失时不能适用。四角色 process_reconciliation 显式拒绝 managed_scope，不能偷用它释放未知后代范围。
6. **产品入口桥接缺口。** ServiceLifecycleManager.start 只接受可证明空闲及正常停服等受支持状态；START_UNCONFIRMED 不会自动替换 owner。产品 DPAPI 凭据与现有 bootstrap 管理示例不同。需要受控的无 dispatcher 管理会话入口，不能调用普通 start 以“恢复”未决实例。
7. **证据已落盘、终态未提交的 managed Run 也没有专门证据收尾策略。** 完整 proof 与最终提交之间的故障不能用新空 Job 或四角色对账修复。未来需单独验证 proof 的 scope/owner/attempt、启动完整性、最后查询和有无后续加入，不能将任何历史 active=0 当作最终 proof。
8. **Classic 的确有语义偏差。** 当前 gui_presentation.status_presentation 将 raw UNKNOWN_INTERRUPTED 显示 Failed/失败，status_codes.normalize_status 却返回 UNKNOWN。这与交接的 Interrupted (Unverified) 不一致；属于 Classic 展示 P1，不能误称 Agent-first 已经把 UNKNOWN 存成 FAILED。

另一个存储恢复缺口：store._check_sidecars在连接前拒绝-journal/-wal/-shm，_connection只接受DELETE模式。异常写入留下sidecar时，业务快照也可能不可读。D02必须返回STORE_REQUIRES_MAINTENANCE及“业务状态未读到”，不删sidecar、不触发SQLite自动修复。不能承诺任意崩溃后都能直接Inspect完整Run；安全存储维护需单独设计，不属于默认Recovery Apply。

## RC 影响与风险分级

- **未确认 P0 安全缺陷。** 本次是静态审查，未得到未授权启动、重复执行、无记录解锁或 unsafe stop 的复现。当前缺证据时保留槽/PAUSED，属于 fail-closed。此结论不是完整安全证明。
- **P1 能力声明**：若 RC 承诺 Windows 重启/崩溃后可正常产品恢复，则被本次缺口阻断。Run022 原本仅冻结登记主机、固定 Standard、正常收尾/安全空闲停服的窄范围，未宣称通用 Crash Recovery，因此不改写其历史 PASS。
- **P1 Classic 展示**：UNKNOWN_INTERRUPTED→Failed 是已定位的误导性结果结论。对外包含 Classic 恢复体验时应在单独补丁修正，或明确排除相关承诺；不能靠文案宣布 Solver 失败。测试预期、过滤器和历史展示一起审查。
- **P1 维护可达性**：产品异常停服后会保守阻止普通 start；需要独立管理能力，不能让用户删锁或改 DB 作为操作指引。
- **P2**：部分历史模块类名、注释仍写 Fake/TEST_ONLY；实际多 Backend 支持以白名单和精确 binding 为准。
- Run021B 的 NOT_OBSERVED、ODB NOT_RUN、域外 UNKNOWN 仍保留；本轮不补跑、不改变 Run014 revision21 行政记录。

## 最小决策

CR-D02 可开始：只读单 Run 分类器 + 有界快照 + 独立显式当前观察结构 + 模拟故障测试。**不新增持久 Run 状态、不迁移 Schema、不调用管理 lease、不开放新的 Apply。**

CR-D03 先把既有可适用策略桥接到产品可信管理上下文；“退出缺失时接受残余风险”作为独立版本化政策评审，不伪装为正常收尾。CR-D04 对接现有 public client 和 Run023 信息架构。CR-D05 最后另审新尝试，不把它嵌入 Apply。

[状态/API 契约](RECOVERY_STATE_AND_API_CONTRACT.md) · [阶段与回退](IMPLEMENTATION_AND_ROLLBACK_PLAN.md) · [测试矩阵](TEST_AND_ACCEPTANCE_MATRIX.md)

