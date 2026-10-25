# CR-D03 — 最小后续范围（未实施、未授权执行）

D02只提供诊断。下一阶段应先做**产品凭据到现有受控管理会话的桥接**，不要直接扩大所有reboot/缺exit的释放政策。

开始条件：确认本报告机器契约；独立批准管理权限、同一owner锁、允许的既有policy及作用域。D02报告不是可消费授权，OS观察也不是跨数据库/操作系统原子快照。

第一切片：仅显式、非空、已有未决Run且现有closeout策略可处理的产品Project。优先新增产品层薄适配，复用 product_project、local_credentials、LocalOwnerLock、acquire_supervisor_store、closeout.issue、reconciliation.manage。先证明无dispatcher管理会话取得**旧owner同一把排他锁**；锁冲突即拒绝，不删文件、不用IPC超时/PID消失替代。拒绝全新空Store进入恢复管理，避免通用fresh acquisition的OPEN语义被误用。

在锁内重新读当前revision/slot/gate/owner/隔离，按精确scope登记管理Grant；普通连接、Start/Stop和真实Solver token不自动得到恢复权。原key原请求查原回执；冲突、过期、证据变化拒绝。保留SQL原子决定/消费/回执/事件；应答不确定只查原key。Apply后重新读取验证旧证据、UNKNOWN、PAUSED、路径隔离和其他PENDING不变。不得隐式Stop、Resume、Retry或创建Attempt。

第二切片须另审：managed EMPTY proof已写但终态事务缺失的证据对账；缺exit/疑似重启的残余风险行政政策。D02的LATER_BOOT_ESTIMATE不满足“确认所有进程退出”，不能据此放宽现有closeout。证据不足保持retain；原scope丢失不能新建空Job替代。新政策如需持久当前OS观察，另标时间/source，不能覆写历史exit。

目前不需要新全局Run状态或DDL。优先管理表和reconciliations；若字段/约束不能表达精确政策，停止并单独评审Schema版本，而非绕过现有规则。

最小回归：CR-D01 T06/T08/T11–19/T25–26，产品凭据隔离、同锁竞争、revision变化、旧key重放、事务前/后故障、无记录解锁、PAUSED与输出隔离、未授权Agent、正常与行政收尾区别。所有实例新建，固定Python替身；不操作历史owner，不运行Abaqus。

回退仅关闭新管理入口/新权限登记，保留已提交处置/消费/回执的读取。不能通过删除决定或重占槽伪装回退。完成后停止，CR-D04显示/只读IPC及CR-D05新尝试继续独立授权。

RC影响：本轮未发现新的P0执行安全缺陷，Run022的受限RC结论不被扩展。通用系统崩溃恢复仍未实现；Classic误显示Failed为Run024必修P1；历史真实Run的NOT_OBSERVED、域外UNKNOWN和ODB NOT_RUN原样保留。
