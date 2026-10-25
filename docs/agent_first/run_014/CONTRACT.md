# Run 014：真实 Standard Run 收尾政策 v1

日期：2026-10-24。本轮 Abaqus 调用 0。当前 Run013 实例未应用新逻辑，未取得新 owner、未登记管理许可、未释放槽、未恢复派发、未停服。

## 接入判断与实际阻断

| 接缝 | 实际实现与含义 |
|---|---|
| 原真实执行 | `standard_backend.StandardBackend.execute`：先持久意图，再一次创建，独立线程观察；300秒结束观察，关闭自身观察句柄，不终止进程 |
| 原结果 | `standard_backend.persist_result`：记录 Solver/DAT 独立结论，`execution=BLOCKED`、`reconciliation=RECONCILIATION_REQUIRED`，保留 slot |
| 单槽 | SQLite `slot(id=1).run_id`；`pending_for_owner` 不领取已有占用时的下一任务；`dispatch_scope` 另检查持久 gate |
| 原恢复 | `reconciliation.manage(RESUME)` 原本因 `needs_reconciliation(run)` 或 slot 非空拒绝；正常重新取得 owner 总是 PAUSED |
| 原对账 | `reconciliation._inspect` 只接受 Fake 产物；`process_reconciliation` 要求固定 Python 成员全集及持久退出证据。二者都不能解释真实 Standard 成员全集 |
| 原资源 | `.r013_bar_d48c54f7.intent.json` 一次尝试记录、同名输出检查、固定工程/scratch 路径；不是主机资源租约，也没有整机互斥 |
| 原正常停服 | `standard_service.main_action('stop')` 写显式 stop 请求；watcher 等 active_dispatches=0；`FakeSupervisor.serve` 退出 listener、join worker/handlers、关闭 store/owner lease。没有 Solver terminate/kill |

当前值见 `CURRENT_READONLY.json`、`CURRENT_CLOSEOUT_PREVIEW.json`。本轮查询旧 IPC 超时，未取得记录 PID/创建时间/映像匹配的 owner 引用。不能将这些当前查询结果解释为历史 owner/未知 Solver 已确认退出。数据库仍是 revision20 / gate PAUSED v3 / 原 slot；20条事件、1条验证、1次原执行授权消费、0管理回执。

## 三种事实必须分别表达

1. **观察结束**：已有 `STANDARD_OBSERVATION_ENDED`，不代表进程结束。
2. **证据充分的正常收尾**：本版 Standard 尚无完整的受管理成员边界证据，不提供此自动转换；preview 明确 `NO_COMPLETE_MANAGED_PROCESS_SCOPE_CONTRACT`。
3. **显式行政处置**：操作者可以接受明确残余不确定性后释放**逻辑槽**。它不改变原 Run 的 BLOCKED、RECONCILIATION_REQUIRED、member_completeness、overall_exit、exit_verification、Solver、DAT、ODB 或原事件。

新增投影 `administrative_closeout=LOGICAL_SLOT_RELEASED_WITH_RESIDUAL_UNCERTAINTY` 与 `disposition_record_id` 表明调度政策上的处置；并不将执行证据的 UNKNOWN 改成成功。GUI 同时展示原状态和行政处置。

## 一致只读评估

`ExecutionService.preview_closeout` → `closeout.preview_store/snapshot/assess`；`FakeClient.preview_closeout` 经现有认证、Project/owner 绑定的 IPC。

一个 `mode=ro + query_only + BEGIN` 事务读取 Run、固定 Plan、原回执、消费记录、事件、observation、validation、既有决定、gate及slot。事务结束后生成白名单评估。不读当前工程产物、不探测 OS、不启动观察器、不跑 validator、不写事件/许可/决定，不释放资源。活跃 owner 的 owner_id/active_dispatches 来自单独受 session lock 保护的内存，不伪称为文件系统或 OS 原子快照。

评估包含：policy/assessment_version、Run revision、原 Plan/attempt、当前绑定 owner（离线读为null）、gate version、证据指纹、source_refs、资源逻辑引用、未知项、两个动作及前提、各自影响。原始评估字段中没有 IPC 密钥或 Grant 凭据。

限额：Run+Plan≤256KiB，单关联记录≤256KiB，每表累计≤1MiB；事件≤128、observation/validation/decision各≤16、回执1；公开评估≤64KiB。SQLite等待0.2秒、读取预算0.75秒；live session lock等待0.2秒。超限/忙/损坏/未来格式/日志待维护均拒绝，不截断或自动修复。已有诊断接口保持自身更严格限额。

指纹使用现有 canonical_json+SHA256，覆盖持久快照，包括 gate/slot/原始记录；preview_digest 覆盖评估正文，不含本次 read_at。它不是签名或授权。新事件、revision、gate、owner或证据变化均要求重新评估。

## 最小处置集合

| 动作 | 条件 | 事务效果 | 保留 |
|---|---|---|---|
| `retain_standard_resources` | 支持的 Standard v1，单次原接收/意图关联完整，Run待对账且占槽，当前 owner PAUSED/quiescent，精确许可 | 追加决定/管理回执/消费/事件，Run revision及gate version增加 | 槽、工程/输出、所有证据、UNKNOWN、PAUSED |
| `release_standard_logical_slot` | 上述条件；另有已记录观察结束、wrapper及所有已观察成员的身份匹配退出记录、投影与最近持久观察事件一致；操作者接受成员全集仍未知 | 追加行政决定，清除此 Run 的逻辑slot，记录独立处置投影 | 旧Run/attempt/接收回执/执行消费/输出意图；工程/scratch/输出隔离；UNKNOWN；PAUSED；禁止重跑 |
| 现有 `resume_dispatch` | **另一次**精确真实管理许可、当前gate版本、空slot、无其他未处理不确定性 | 仅 gate OPEN | 原Run仍不可执行；每个待派发任务仍须通过原Plan/Grant/资源/输入/期限检查；旧路径不能复用 |

本版不提供 release-output、force-success、Retry、终止、活进程重挂接或自动接管。对任一已观察成员尚无匹配退出证据时，行政释放也拒绝；可以记录保留资源决定。没有成员身份/启动意图等关键历史证据时整个评估明确拒绝。

行政释放不证明所有物理CPU/内存/许可证均已归还；不适合作为所有正常任务的默认结尾。没有整机或跨 Project 的总资源互斥保证。

## 权限、幂等与事务

沿用 `management_grants / management_consumption / management_receipts / reconciliations / control_events`，**实验 schema仍3，无初始化/迁移/新数据库**。决定以 policy/source/action 区分，虽复用存储表名 `reconciliations`，并非“证据对账成功”。

可信同 owner 入口 `closeout.issue(service,assessment,action,reason,approval_source,expires_at)` 签发 `EXPLICIT_STANDARD_DISPOSITION`。精确绑定 context_digest、Project instance、authority_instance、owner_id、Run、revision、preview_digest、evidence_fingerprint、理由、动作、最多1次、≤1小时有效期。reason和approval_source记录真实操作者来源；不是密码或生产级签名。普通 IPC 没有 mint/approve 方法；TEST_ONLY、原执行许可和普通连接凭据都不能替代。

`closeout.issue_resume` 复用同一真实管理能力类别但独立 action/gate scope，不能由 Fake 管理许可打开行政收尾后的门。任意同OS用户调试/改库/导入可信代码仍不在隔离威胁模型内。

`reconciliation.manage` 用原 `BEGIN IMMEDIATE` 管理事务：先按 Project/稳定namespace/action/idempotency_key 查原回执，然后核对授权/owner/revision/指纹/门禁。决定、Run投影及revision、slot、gate version、事件、原子管理回执及消费同事务提交。不同action的namespace分别存在，但旧评估不能跨另一处置后的revision使用。

同键同内容返回原回执，在已消费、revision变更、授权后来过期或owner改变后仍可重放；不会再次开门。异内容冲突。不同请求并发只能有一个按同一评估转换。原回执和当前Run/gate分别查询。提交结果不确定使用原key查询，不换key重试。

before_commit故障：整体回滚，slot不悄悄释放。after_commit丢应答：原key返回已提交决定。真正进程崩溃可能留下SQLite journal：正常接口报维护错误，不读成空状态、不清journal、不自动重开派发。

## 旧工程/输出保护

`standard_contract.check_plan` 增加同存储的历史 Standard engineering/scratch 路径保留检查，包括祖先/子目录重叠，新Job名不能复用。既有工程目录出现任意固定Standard意图文件时，新启动拒绝。原intent、输入、输出、scratch均不删除。本轮没有“解除路径隔离”的入口。

这是当前实验存储内的政策检查及已有目录意图保护，不是跨 Project 并发创建的原子主机租约；不得据此宣称所有其他软件都无法使用这些文件。候选路径的no-reparse/显式根约束仍由原check_plan负责。

## 停服与重启

`FakeSupervisor.serve` 新增正常退出前持久 PAUSED；先停接收、join当前worker/handler，再pause/close。若正在观察，等待该工作路径返回；不将 stop 请求解释为 Solver stop，不使用Popen context manager、terminate、kill或kill-on-close Job。持久化失败时停服流程报错，不能称为已完成可靠停服；后续读仍服从维护拒绝。

若外部创建或工作线程卡住，join也可能持续等待；没有“到期强制停服”保证。stop_requested、listener关闭或函数开始退出都不能代替owner OS退出证据，不能用杀进程补足正常收尾。

数据库记录及路径保留在owner退出后存在；重新取得现有OS排他锁才允许写入，重启总PAUSED；不会重跑旧Run。测试实际证明：在本轮Windows工具承载环境、会话存活时，owner和专属venv启动器退出后，固定Python worker仍存活/增长日志/自行退出。外部Job、终端关闭、注销/重启、真实Abaqus在owner退出时的行为没有因此得到证明。

当前真实owner不响应且身份未匹配，**不能直接对旧PID发停止操作**。原Run013静态启动包绑定了旧源码，当前新源码已不同；旧包的 `check/start/authorize/stop` 材料校验可能拒绝。没有更改旧清单摘要或绕过它。本轮新增可信管理入口只能在原owner已不持有锁且操作者明确同意交接时取得排他管理lease；不能热加载当前owner或抢占它。

## 未来正常完成：可达条件及最小缺口

管理范围应是“本次固定本地Standard启动会话拥有输出访问能力的受管进程集合”，不是整台机器所有Abaqus进程。正常自动收尾的组合条件：

1. 启动前固定版本化成员边界，启动尝试绑定该边界；成员从创建开始被纳入，任何脱离/外部代启动/身份缺口均明确使完整性未证。
2. 取得该受管集合封口/零活跃成员的权威证明，必要成员逐个保留OS身份和退出结果；失败退出是执行失败，不假造成功。
3. Solver完成/失败文本与独立DAT验证分别提交，ODB继续独立；策略判断结束状态与是否可派发，不因发现日志文本跳过进程条件。
4. 最终证据、结束投影、槽/受管资源释放在持久事务中一致；外部创建和数据库之间仍无exactly-once承诺。

**下一最小候选**：仅针对新启动的固定Standard v2，在根进程可开始产生后代之前建立专用、非kill-on-close、禁止breakaway的受管容器；持续保存成员身份/退出和封口证明。Windows Job默认子进程关联有例外，breakaway及外部代创建会破坏覆盖；关闭带KILL_ON_JOB_CLOSE的最后句柄会终止成员。因此必须先以替身验证嵌套/分配失败/缺失成员/owner退出，再单独获批测试Abaqus2024兼容性。本轮未创建/修改Job。[Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

可评估 `ActiveProcesses` 等受管对象计数与持续成员记录组合的封口证据；计数描述关联该Job的成员，不是整机无进程。[Microsoft accounting information](https://learn.microsoft.com/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)

根创建/关联的无竞态顺序、宿主嵌套限制、许可证/包装器是否经外部broker产生输出访问者、句柄释放与活动计数时序，都仍是待验证前提；不能只等一个普通Job句柄signaled就声称所有自然退出完整。现有轮询父PID发现短命成员的遗漏窗口，不能靠字段改名消除。

上述新机制仅能证明未来新Run的受管范围，不能反推Run013历史已具备它。当前历史Run只能保留阻断，或在精确授权下执行本版行政政策。
