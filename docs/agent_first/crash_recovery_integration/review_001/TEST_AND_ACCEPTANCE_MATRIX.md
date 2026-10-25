# CR-D01 — 检查结果与下一阶段验收矩阵

## 本轮实际执行

本轮是审查，不执行恢复故障试验。**应用 pytest 运行0，Abaqus0，GUI/Supervisor/Backend启动0，OS进程查询/终止0，Project修改0。** 读取源码、已有测试/报告和八份交接文档；普通Python仅标准库文件摘要/文档引用校验，不导入应用。无新增测试进程、句柄或私有凭据需要清理。

历史 Run022 的664项是其安全回归结果，不是本轮新测试数；Run007/014/015等也不求和。测试源码和历史报告共同作为“已有测试”依据。

本轮只读检查：
- 实际根目录、Develop、完整HEAD、git status、冲突和版本；
- 开始1503个既有非忽略文件SHA-256；写文档前再次全量比对无变化；
- 八份交接副本摘要与完整阅读；
- 实际模块/函数/测试定位，回避未确认文件名；
- 新文档引用和最终历史保留检查结果见 READ_ONLY_CHECKS.json。
命令检索初期有PowerShell不展开rg路径通配符和误猜cli模块位置，均为只读失败；已按实际 api/cli.py、mcp/tools.py 修正。部分过大输出被截断后对相关段落重读，没有当作完整源码阅读。

## 后续隔离测试前置

新临时 Project/Runtime/Recent/export 路径全部显式传入。测试数据标为模拟，不复制生产DB或有效凭据；Standard创建接缝用失败哨兵/固定Python替身完全切断。对真实Windows生命周期只创建有限运行、可自行退出的固定Python；如需故障owner，只终止本轮创建且持有身份核验句柄的测试owner，不能按进程名结束。boot/session/time由provider注入，不注销/关机/重启OS。

负向历史数据可以在**新临时DB夹具**构造，但不能伪造正向OS成功证明。正向退出/崩溃窗口用确定性屏障和真实测试句柄；记录源码/输入/证据来源，不依赖sleep猜时序。清理仅当前测试私有材料，保留不可确认状态；无历史清理。

## 故障及安全验收

“已有”表示应复用的覆盖，新增列为待实施，不能提前PASS。

| ID | 场景/构造 | 必须断言 | 已有基础 / 新增阶段 |
|---|---|---|---|
| CR-T01 | GUI崩溃或完整退出，owner/worker正常 | 不分类Solver中断；无数据库变化；重连同Run | test_managed_scope 的实际GUI关闭；test_attachment_gui；D02分类/D04显示 |
| CR-T02 | owner确定性崩溃，worker继续写日志 | SUPERVISION_LOST/UNKNOWN，不Requeue；槽与PAUSED保留；第二项PENDING不动 | test_managed_owner_crash_leaves_worker_alive_and_restart_blocked；D02 |
| CR-T03 | 模拟新boot session、缺exit | 明确证据来源；疑似中断不是FAILED/FINISHED；旧closeout release仍拒绝 | 新D02；D03新政策另验 |
| CR-T04 | PID复用、创建时间/映像不符 | IDENTITY_MISMATCH不能当原进程退出；不控制该PID | ProcessReference现有；新D02 |
| CR-T05 | boot估计误差交叠、时钟回拨、查询拒绝 | UNKNOWN+reason，不用墙钟单点推定新会话 | 新D02 |
| CR-T06 | 原owner锁仍持有，IPC失联；同时管理请求 | OWNER_BUSY/明确拒绝；不删锁、不新owner；只读预览无抢锁 | test_trusted_operator_entry_refuses_active_owner_and_has_no_backend；D03产品桥接 |
| CR-T07 | Job句柄失联/查询失败；四角色均退出 | 不重建空Job；不能用PID枚举证明全范围；槽保持 | test_managed_fault_never_releases_slot_or_restarts；recorded process拒managed；D02 |
| CR-T08 | 原scope为空已持久化，终态前owner崩溃 | 当前仍待对账；新证据policy须核对完整绑定，未实现时拒绝Apply | test_managed_true_crash_after_empty_before_commit_does_not_release；D03证据策略 |
| CR-T09 | 历史Solver完成、validation缺失/INVALID | 进程、Solver、验证分别投影，不重新验证/改为PASS | test_run_diagnostics；D02 |
| CR-T10 | 有DAT/ODB/.lck但无Run归属 | 不因存在判成功；preview不读取/删文件；输出继续保护 | R5只读陷阱/R14retention；D02 |
| CR-T11 | 同key同请求重放、应答丢失、owner改变 | 原receipt；无第二decision/消费/事件；新key旧grant拒绝 | test_lost_management_response_and_new_owner_replay；D03 |
| CR-T12 | 同key不同请求/动作，或两操作同revision | 冲突/STALE_PREVIEW；最多一个可见转换 | test_standard_closeout replay/concurrent/competing；D03 |
| CR-T13 | preview后证据/gate/owner/slot/retention变化 | 当前锁内重评估拒绝；不重解释为其他批准 | test_stale_assessment_rejected；D03 |
| CR-T14 | Apply提交前故障/真实owner崩溃 | 完整回滚，无无记录解锁；原证据与槽不丢 | test_true_owner_crash_during_disposition_no_unrecorded_unlock；D03 |
| CR-T15 | commit成功应答丢失/未知 | 用原key读取，不换请求；一次决定可追溯 | test_atomic_management_failure_and_unknown_commit；D03 |
| CR-T16 | 仅连接/StartStop/Solver/Test权限，伪approved字段 | 无权登记/Apply；scope/owner/expiry/maxuses严格匹配 | R14/R21B授权测试；D03新恢复能力 |
| CR-T17 | 另有未启动排队和历史完成Run | 不修改其状态、receipt或消费；不自动启动；完成Run不降级 | R7其他未决阻断；D02/D03 |
| CR-T18 | 行政释放成功 | 原UNKNOWN/exits/Solver/DAT逐字节/摘要保持；旧路径保留、gatePAUSED；不Stop、不重跑 | test_explicit_release_preserves_evidence_receipt_gate_and_intent；D03 |
| CR-T19 | 正常证据收尾与行政释放对照 | 正常范围终态proof成立；行政不得填COMMITTED_EMPTY_SCOPE，不能满足A→B正常收尾前置 | test_standard_managed/test_standard_closeout；D03 |
| CR-T20 | 产品unknown启动reservation，副本/错Project/旧schema | 普通start拒绝、不替换owner；inspect无迁移；复制凭据无效 | lifecycle_boundaries/product_project/service_attachment；D02/D03 |
| CR-T21 | 读取限额、busy、缺关键记录、导出失败 | 明确失败/不完整，不部分结果假装全证据；无写/探测/验证 | test_run_diagnostics limits/export/read-only；D02 |
| CR-T22 | GUI/Python/CLI/MCP兼容 | 同reason/provenance；未知操作明确不支持；旧5工具不增加写能力 | test_mcp_readonly/test_attachment_gui；D04 |
| CR-T23 | Classic Interrupted标签及过滤 | raw保留，canonical UNKNOWN，显示未验证中断，不Failed；新旧数据源隔离 | 当前偏差已定位；D04独立补丁 |
| CR-T24 | 新尝试准备与旧尝试混用 | 旧budget不可复用；新输出/Plan/Grant/Run；Apply不自动创建；Standard未实现时INVALID_RETRY | test_execution_contract/test_execution_store；D05 |
| CR-T25 | 管理会话输入为全新空Project | 拒绝恢复管理，不让底层fresh acquisition建立OPEN | 新D03；不改原正常启动语义 |
| CR-T26 | 当前OS观察与提交之间状态变化 | 不声称原子OS+DB；冲突/超期拒绝；若无法达到policy前置仅retain | 新D03；不能以短TTL替代锁/隔离 |

## 必要回归集合（未来，不在本轮运行）

- D02：tests/test_run_diagnostics.py、test_diagnostic_supervisor.py、新分类/probe测试、test_execution_isolation.py（新模块依赖需精确审查）。
- D03：test_standard_closeout.py、test_closeout_windows.py、test_recorded_exit_reconciliation.py、test_fake_reconciliation.py、test_reconciliation_supervisor.py、test_lifecycle_boundaries.py、test_product_standard_control.py、test_managed_scope.py，以及受影响的product凭据测试。
- D04：test_execution_gui.py、test_attachment_gui.py、test_service_attachment.py、test_mcp_readonly.py及实际Classic presentation相关测试；GUI测试必须隔离Recent/Runtime。
- D05：test_execution_contract.py、test_execution_store.py、test_standard_managed.py、test_standard_managed_windows.py、test_product_standard_control.py。
- 每阶段重新静态审查选集副作用；记录收集nodeid去重、首次失败原因、PASS/FAIL/SKIP、句柄和私有凭据清理。不能把测试数量代替表中保证。

当前只对设计交付检查；上述 CR-T01～26 是验收计划，不是新功能已经通过的结果。

