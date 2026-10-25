# Run015：受管范围与正常收尾契约

## 接入与兼容

复用 `ExecutionService.prepare/submit/execute_pending`、`ProcessBackend.execute`、独立 `FakeSupervisor`（历史名称）、现有 Project SQLite、TEST_ONLY 精确授权、公共 `FakeClient` 与 Dev GUI。新增 `managed_process.py` 是 Backend 内的 Win32 适配，不是新执行器、服务或实验控制器。真实 Standard Backend **未改用**此启动方式。

可信配置 `ProcessFixtureConfig.current(managed_scope=True)` 只用于新隔离实例。固定计划的 `process_fixture.managed_scope` 绑定 `windows-job-list-v1` 和适配实现摘要，另绑定原解释器/镜像/夹具摘要、枚举场景、输入、资源和输出。普通请求不能改配置、Backend、命令或开关。TEST_ONLY Grant仍绑定完整计划摘要、Project及一次预算；没有真实授权扩展。

默认旧配置仍不含新字段，其原摘要算法与执行契约保持。格式仍为实验schema3，利用现有JSON Run/事件扩展，无数据库迁移。没有新证据的历史记录不视为受管范围已完成。Run007的四角色对账明确拒绝含managed_scope的未决Run，不能通过旧对账绕过新后代范围。

## 所证明的范围

每次已领取的 Run/phase_attempt 创建一个**未命名、不继承句柄**的 Windows Job Object。范围标识是服务生成的scope_id及Run、Project instance、Plan摘要、尝试、owner/epoch关联；不是可跨重启使用的HANDLE或可重开的对象名。

根进程是固定解释器的启动对象，包括venv redirector；通过 `STARTUPINFOEX / PROC_THREAD_ATTRIBUTE_JOB_LIST / CreateProcessW` 在初始线程获准执行前纳入。随后使用原创建句柄核实 `IsProcessInJob(root, job)`。Job关系建立、创建或核验失败均拒绝，不回退普通Popen。

普通CreateProcess继承后代、子孙及其嵌套Job位于此范围。Supervisor、GUI、普通客户端不在单Run Job内。域外服务、WMI代创建、其他broker、伪造父进程、远程任务等不属于保证。不是针对同OS用户任意修改/调试的安全隔离。

本Job的LimitFlags实际查询须为0：不启用KILL_ON_JOB_CLOSE、BREAKAWAY_OK或SILENT_BREAKAWAY_OK，不主动设置终止、CPU或内存限制。关闭句柄没有本Job主动杀后代的语义。外层宿主仍可能有限制；自己的0 flags不是完整外层Job层级证明。当前Windows嵌套及venv链由真实固定夹具验证，不能推广到终端关闭、注销、系统重启或真实Abaqus。

新计划的max_process_members=32是固定夹具在绑定解释器下的数量预算声明，不是Job的ActiveProcessLimit。快速后代实测累计数为24（含venv传输链），必要关键角色记录仍为4；三者不能混同。采样数量不用于补造个别退出码。

创建使用明确解释器、参数数组转Windows quoting、固定cwd和最小环境，`bInheritHandles=False`、空标准句柄、无控制器管道；输出仍是原夹具有界JSON进度/结果。不会继承owner锁、数据库或IPC秘密。无breakaway、伪造父进程、服务或计划任务。

## 收尾时序与依据

1. 原接收及授权消费事务创建Run；原claim事务占单槽并持久START_INTENT。
2. 创建Job，持久 `MANAGED_SCOPE_PREPARED`（此时空Job**不算完成**）。固定执行对象/Grant再次检查。
3. 仅一次根CreateProcess尝试；成功建立关系后 `MANAGED_ROOT_CREATED`，按原机制核对四个关键角色及保留OS退出句柄。四角色现在明确是关键角色，不是整个后代集合。
4. 独立工作路径进行 `QueryInformationJobObject(JobObjectBasicAccountingInformation)`；按计数变化记录 `MANAGED_SCOPE_OBSERVED`。IPC及GUI读取不拥有Job，不探测或更改状态。
5. 必须成功创建并核验根、原Job句柄有效且政策未变、总进程数>0、直接查询ActiveProcesses=0、无limit termination。后端只允许一次根创建，无尚未完成的创建调用；无外部可用Job句柄及再次加入入口。不能用尚未启动的空Job、枚举PID、已观察关键角色全退出或通知推断范围结束。
6. 原独立Artifact验证后，在**同一现有terminal事务**写 `MANAGED_SCOPE_COMPLETED`、Run范围收尾投影、验证/观察、`VALIDATION_RECORDED` 和slot=NULL。事务前故障或owner崩溃不能留下无记录解锁。提交未确认时不重跑。

最终 `managed_completion=COMMITTED_EMPTY_SCOPE` 才表示正常范围收尾已提交。先前某条scope查询即使是EMPTY_CONFIRMED，也不等于terminal事务成功。Job句柄仅供当前Backend执行期间使用；查询结束后关闭原句柄，不隐藏后台观察，不在恢复时创建替代对象。

没有使用completion port来判终态：Microsoft说明普通Job通知交付不保证，因此本版直接查询计数。瞬时进程可以没有逐PID退出记录，仍由内核范围计数覆盖。

## 结果维度与派发

- 范围结束：仅指本次受管CreateProcess范围无活动进程。
- 关键角色退出：原四角色有身份关联的保留句柄退出码，继续单独记录；其他辅助后代不宣称每个退出码已捕获。
- Backend结果：固定任务的关键角色与动作结果，不是所有辅助后代退出码全0的声明。
- Artifact：原独立固定JSON验证；范围为空不能使INVALID变VALID。
- Solver始终NOT_RUN，未作Abaqus数值或ODB验收。

新managed档案只在关键执行成功且Artifact验证PASS时沿既有OPEN门继续下一项。非零关键退出或验证失败：范围可结束、槽可按完整范围证据释放，但同事务保持/设置PAUSED，不擅自自动继续。原门为PAUSED始终保持；正常收尾不是resume授权。

下一项仍走原计划、授权、期限、输入、资源和原子单槽claim。保护范围仍为**每实验存储单槽**，不是整机互斥。正常路径不调用Run014行政处置，不改历史UNKNOWN，不替旧工程解除隔离。

## 故障及恢复

建立Job/属性失败、创建已发生但身份尚未持久、查询失败、句柄丢失、证据/terminal提交失败：保留原START_INTENT/未决投影及槽，owner暂停派发，无自动重跑。

owner崩溃后句柄消失不证明对象为空。新owner不重新命名/创建同名Job补证，也不接管旧worker；重启保持PAUSED，查询标明RECONCILIATION_REQUIRED。测试控制器掌握的OS引用只用于验收和安全清理，不写回服务证据。worker自行结束或测试释放其屏障也不是业务对账。

## 官方依据与限制

- [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)：默认CreateProcess子进程继承、breakaway与Job句柄生命周期。
- [Nested Jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs)：嵌套范围、外层限制及后代计数归属；不允许breakaway的内层不会仅因外层允许就逃逸。
- [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)；[Microsoft创建时Job绑定说明](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812)：Windows10起JOB_LIST在初始线程运行前关联，避免先创建后Assign窗口。
- [Basic Accounting](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)：TotalProcesses、ActiveProcesses、TotalTerminatedProcesses的实际含义。
- [Job Notifications](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_associate_completion_port)：普通通知不保证交付；PID通知也不等同保留身份。

文档仅用于实现依据。实际Windows兼容性由本轮固定Python测试限定证明；真实Abaqus包装器、Solver、许可证/外部服务、脱离域外执行仍待单独审阅及实机授权，本轮没有调用它们。
