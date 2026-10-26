# CR-D03 — 实际接入与兼容范围

基线为 Develop `9553755a24ff521dd2ac694ea39cab5a03f88466`，版本 `0.3.0.dev0`。任务开始 Git 干净；历史 CR-D02 的旧 HEAD 不是本次基线。既有 1556 个文件身份见 BASELINE.json。只在 Dev 修改，下文没有授予任何历史实例操作权限。

## 实施前接入判断及最终补丁

CR-D02 已提供只读、版本化的诊断与当前进程查询。Run007 已有固定四角色退出对账，Run014 已有精确行政释放、路径保留和管理事务；无需第二个恢复数据库或 Runner。实质缺口是：产品本地可信管理桥接、统一 Preview/Apply、原受管 Job 空证据已落盘而终态未提交的窄对账策略，以及提交后核验。

| 实际源码/函数 | 最小变化/复用 |
|---|---|
| `execution/recovery.py` / preview_interrupted_recovery | 新统一只读投影；复用 ReadOnlyStore._diagnostic_snapshot、interruption.build_interruption_report、closeout.assess、process_reconciliation.inspect |
| 同文件 / RecoveryManagementSession | 新显式本地管理会话；复用 acquire_supervisor_store、ExecutionService、management_grants，不创建监听器或派发循环 |
| 同文件 / apply_recorded、verify_interrupted_recovery | 进入原 reconciliation.manage 事务；行政和四角色分支直接委托旧 apply_recorded；只新增原 Job 空证据窄策略和核验 |
| `recovery_management.py` / open_product_recovery | 产品层薄桥，open_project + ServiceLifecycleManager 的现有 DPAPI 配置；不 start/connect/stop Supervisor |
| `execution/store.py` / acquire_supervisor_store | 一个可选 management_admit(ctx, connection) 钩子；在原 owner.lock 内、owner/gate 写入之前核查目标和 OS 事实；默认调用行为不变 |
| `execution/reconciliation.py` / _request、_authorize、manage | 新精确动作 apply_interrupted_recovery；原原子事务、版本CAS、回执、消费表及幂等命名空间不变 |
| `execution/process_handles.py` / ProcessReference | 保持原错误码；仅附加 OpenProcess 明确 ERROR_INVALID_PARAMETER 的 pid_absent 来源，查询权限失败不当成 PID 不存在 |
| `execution/interruption_probe.py` / _observe_identity | 泛化 PROCESS_IDENTITY_UNKNOWN 改保守 QUERY_FAILED；只有上述明确来源才 PROCESS_UNAVAILABLE；两者都不表示历史完整退出 |
| tests/test_interrupted_recovery.py、test_recovery_windows.py | 新统一入口的精确权限、故障、真实 Windows 固定 Python、产品桥测试 |
| tests/test_interruption_probe.py、test_execution_isolation.py | 收紧查询失败断言；精确扩展依赖许可，保留禁止执行隔离断言 |

新增管理入口只用于新的隔离测试实例。ExecutionService 的提交/执行、Supervisor IPC 动作表、Backend、GUI、生命周期启停、Schema、Plan 摘要和执行 Grant 算法均未改。

## 持久数据与回退

不新增表、DDL、Schema 版本或全局 Run 状态。已有 JSON body 承载版本化记录：`interrupted-recovery-v1`、`recorded-managed-scope-v1`，管理 action 为 `apply_interrupted_recovery`。

原 Job 证据分支使用既有 FINISHED / reconciliation=NONE，并新增明确的 `recovery_scope_completion=RECONCILED_RECORDED_EMPTY_SCOPE` 投影。**不补写 managed_completion=COMMITTED_EMPTY_SCOPE**，不冒充历史自动终态提交；现有成对派发和严格停服判断不因此放宽。Solver、Artifact、原 managed_scope、exit、旧 Run owner/attempt 保持。

行政分支完全使用 `standard-closeout-v1` 原记录及 `RETAINED_NO_REUSE`；旧 UNKNOWN、路径和 PAUSED 不变。缺失退出证据的疑似 reboot 不满足该旧政策，保持 KEEP_BLOCKED。不存在“所有中断都可释放”的新政策。

旧格式、错 Project、缺证据或 SQLite 遗留 journal 按已有规则拒绝；不迁移或重建。新管理决定写在 Project 自己的 Store，未复制工程文件/凭据。旧版可忽略新投影但不能据此执行未知管理动作；应继续使用本版本读取管理回执。

代码回退应禁用新入口及新授权登记，保留新动作记录的只读解释和回执查询。不能删除决定/消费/证据、重占槽或修改历史 Run 来伪装回退。没有本轮生产数据需要回滚。

## 尚未覆盖

没有 live Job 重新挂接、丢失 Job 重建、自动接管、重启证明、Retry/Requeue/新 Attempt、Abaqus Restart 或远程审批。仅支持遵守原 owner.lock 的本地写者；不抵御同一 OS 用户任意修改源码/DB。真正不遵守该锁的未知写者不能通过本入口强行排除。
