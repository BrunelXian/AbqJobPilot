# Run016 接缝与固定顺序契约

本轮是实现及实机准备；真实 Abaqus 调用 0。没有改动 Run010/011/013 原实验，也没有对历史 owner 发出请求。当前实际基线见 BASELINE.json；源码修改前快照保存在 before/。

## 复用及必要修改

| 位置 | 复用 / 改动 | 权限及影响 |
|---|---|---|
| execution/standard_contract.py | 保留 Standard 固定模板；显式 managed 配置、计划模式和管理材料摘要 | 原未管理计划含义不变；不在派发时切换策略；TEST_ONLY 不升级 |
| execution/managed_process.py | Run015 原 Job/创建/查询；增加固定 Standard 文件句柄传递 | 同一 CreateProcessW 接缝，JOB_LIST 在根运行前关联；HANDLE_LIST 仅 stdin NUL、stdout、stderr；无降级 |
| execution/standard_backend.py | 原启动意图、文本读取和独立 DAT validator；增加 Job 查询及原终态事务内收尾 | 仅 Supervisor worker 可执行；不在 IPC 请求线程等待；失败保留槽、PAUSED |
| execution/standard_sequence.py | 新增仅本次 A/B 的固定政策 | 原授权事务同时登记精确两项；原接收/派发前置校验调用；无 DAG/动态条件 |
| execution/service.py | 原提交幂等、Grant 消耗、领取、owner 写互斥 | 增加顺序资格复核及批次截止投影；无新调度器/表/Schema 迁移 |
| execution/standard_process.py | 原 OS 身份及保留句柄退出观察 | 适配原生创建句柄，并检查已观察执行候选属于本 Run Job |
| execution/diagnostics.py、execution_gui.py | 原白名单、公共查询和 GUI | 分开显示范围收尾、Solver、DAT、UNKNOWN、序号及观察截止 |
| execution/closeout.py | 原行政处置入口保持 | 新管理计划的评估说明区分已正常收尾；不调用行政释放来完成新 Run |
| examples/agent_first/standard_service.py | 原 prepare/check/authorize/start/owner/submit/gui/report/stop | `--pair` 选择唯一 Run016 清单，原 R13 默认不变；没有第二套服务 |
| standard_client.py | 原薄客户端 | `run_pair` 只通过已有 inspect/submit/run/receipt/diagnose；不发批准或数据库写入 |
| standard_pair_package.py | 准备数据辅助函数 | 两个输入副本、新存储、计划和单份清单；不签发 Grant、不创建 Run、不启动进程 |

## 受管范围与证据

每项独立未命名 Job 由当前 Supervisor worker 持有；绑定 Project instance、Run、Plan、启动尝试、owner/epoch。Supervisor 和 GUI 不加入该 Job。创建使用 JOB_LIST；Standard 专用日志为文件，显式 HANDLE_LIST 防止继承 owner 锁、Job、IPC 等无关句柄。未启用 KILL_ON_JOB_CLOSE、breakaway 或父进程伪装；没有 Assign-after-launch、同名重开或失败后 Popen 回退。

范围是根 cmd.exe 及继承 CreateProcess 的后代。外部服务、broker、WMI/远程启动不在保证内；外层宿主 Job/Windows 会话约束不由本 Job 消除。若观察到可归属执行候选不在范围内，以 MANAGED_SCOPE_UNCOVERED 阻断。未被观察到的域外工作仍是实机验收缺口，不能把上次 11 个名称/PID 当完整集合。

直接查询原 Job 的 BasicAccounting 确认：根已创建并核实关联、没有待决加入、累计进程大于零、活动进程为零、没有限制终止；再验证同 Run/attempt/owner 绑定。只收到通知、已枚举 PID 退出或对象不可见均不足。Job 查询/持久化失败、owner 崩溃均保留不确定性；不重建空对象证明过去已结束，不重跑。

终态事务内一起提交 STANDARD_MANAGED_COMPLETED、文本 observation、独立 ValidationRecord、Run revision/投影和逻辑槽 NULL。范围证明只证明受管范围结束；历史 `member_completeness/overall_exit/exit_verification` 仍为 UNKNOWN。已观察关键进程退出、Solver、DAT、ODB 各自保留。正常收尾不改变既有旧路径禁复用条件。若范围结束但执行或验证失败，可记录范围已结束并释放逻辑槽，门仍 PAUSED，B 不合格。范围未确认时槽保持占用。

参考：[Microsoft UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)、[DuplicateHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle)、[Job accounting](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)。本机固定 Python 替身验证了创建时关联、文件句柄和嵌套链；这些不是 Abaqus 新路径的动态证据。

## 精确批准、服务端 B 条件

两个 Plan 固定 `windows-job-list-v1`、实现摘要、`explicit-file-handle-list-v1`、精确输入/配置/工程 cwd/scratch/输出键、CPU1/GPU0/2048MB/300s 和 fixed-standard-pair-v1。B 精确引用 A plan_id/digest；不可由客户端提供任意前置表达式。Run009 预览仍不是 ExecutionPlan；普通客户端不能 mint/approve。

可信本地 `issue_pair` 在原独占准备存储与单事务中创建两项 REAL_FIXED_STANDARD（各 max_runs=1），有共同批准登记时间、batch 和 Plan 对。原 TEST_ONLY 测试授权不匹配此类别。批准来源仍是审计引用，不是密码学人类认证；同 OS 用户任意代码权限不属于隔离承诺。本轮只有替身测试存储使用该类别，待审实例没有真实 Grant。

B 提交、领取及 OS 创建前均检查：原门 OPEN；相同批准批次；恰好一个 A；A 本次管理策略、owner、启动事实及正常收尾事件匹配；直接 Job 完成证明已持久化；A 已 FINISHED/reconciliation NONE、槽已释放；Solver COMPLETED_TEXT_EVIDENCE、DAT PRIMARY_THREE_PASS、Artifact VALID、Backend COMPLETED；无行政处置替代；B 当前 Grant/input/output/窗口有效。所有检查在现有存储互斥及事务/只读边界内执行。

重复请求先返回原接受回执；不会因为当前输入已产生输出或 Grant 已消耗而重复启动。创建前原启动意图和工程意图文件持久化。意图后任何失败不清除、不自动再试。

## 固定时间与失联语义

设 T 为未来精确两项 Grant 同事务登记 UTC 秒，S 为 A 原始持久回执 accepted_at：

- A 必须在 T+600 秒之前创建，Grant 也在该时刻到期。
- B 必须在 `min(T+930, S+330)` 之前创建；前者是批准有效上限，后者限制本批次不延后启动。
- 每项观察从 CreateProcess 返回后最多单调时钟 300 秒，且受 S+630 的全批观察截止约束。外部创建耗时单独记录，不冒充求解运行硬上限。
- 客户端最多等待 A 到 S+330；未满足条件不提交 B。B 已接受后最多观察到 S+630。不新增后台编排者。
- 超时只结束观察，不 terminate、kill、重试、删除或恢复；A 晚于其观察预算才完成也不满足已提交的正常收尾条件。
- B 尚未接受时，客户端超时/连接错误即停止编排，服务没有预先排队的 B。B **已经接受但应答丢失**时，它是原持久请求，可能在原窗口内执行；通信丢失不是取消。按原键查询回执，不能换新键。服务在创建前再次核验窗口，绝不在原窗口后补启动。
- GUI 连接/退出不控制执行，不批准、不恢复、不重新提交。owner 重启默认 PAUSED；要求相同 owner 的固定批次不在重启后继续。

时钟窗口使用既有 UTC 秒；本轮没有建设抗恶意系统时间更改的安全时间源。单次观察使用单调时钟。操作者需保持 Windows 会话；终端关闭、注销、重启及外部 Job 所有者关闭不在保证范围。

## 仍待实机核验

批准后才验证 cmd/包装器在 JOB_LIST 下可启动、实际 Solver/输出写入位于声明范围、外部许可证服务的边界、两项各一次及范围查询/事务顺序、Solver 三类日志、三项 DAT、GUI 关闭重连。不能用历史样本标记新 Run 已运行。ODB 内容不读取。若错过 A 仍运行时关闭 GUI 的时机，记未观察到，不增第三项。
