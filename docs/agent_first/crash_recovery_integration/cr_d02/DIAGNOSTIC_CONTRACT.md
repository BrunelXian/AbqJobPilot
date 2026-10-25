# CR-D02 — 中断分类与证据契约 v1

报告 `af-interruption-diagnostic-v1`，规则 `interruption-rules-v1`。`UNKNOWN_INTERRUPTED` 是诊断/显示投影，绝非新Run状态。报告摘要不能作为执行、恢复或释放许可。

## 判定优先级

| 条件 | classification | display_projection / 含义 |
|---|---|---|
| Plan/Run/消费/事件关系不完整，或有效scope结束与同身份活动成员矛盾 | EVIDENCE_CONFLICT | 不推断安全，不允许由此取得恢复资格 |
| 原行政释放标记与处置、管理消费/回执匹配 | ADMINISTRATIVE_DISPOSITION_RECORDED | 逻辑槽已行政处置；原 UNKNOWN / 退出证据不变 |
| PLANNED+PENDING，无记录START_INTENT/进程/管理范围/外部调用 | NEVER_STARTED_RECORDED | 仅表示未记录启动；不是自动Requeue许可 |
| 原scope proof经既有绑定校验且有同一proof的提交事件，或已有受支持非managed正常终态事件 | COMPLETION_RECORDED | 范围/历史完成证据；不等于Solver、数值或ODB通过 |
| 有未决START_INTENT，原owner当次精确退出观察或持久owner已改变，且已知成员仍活 | OWNER_LOST_WORKER_ACTIVE | UNKNOWN_INTERRUPTED；监督中断，执行可能仍继续 |
| 同上但未观察到活动成员；或启动后缺退出+后续boot估计+原owner身份不匹配/不可查询 | SUPERVISION_INTERRUPTION_SUSPECTED | UNKNOWN_INTERRUPTED；只是可解释的怀疑 |
| 当前原owner或记录成员身份匹配且仍活 | EXECUTION_ACTIVITY_OBSERVED | GUI/连接中断不是Solver中断；不证明成员全集 |
| 其余证据不足 | EXECUTION_STATE_UNKNOWN | 不将所有UNKNOWN转换为Interrupted |

先保留历史行政处置/正常完成，后分析当前监督缺口。Solver已正常完成但数值未验证不会单独触发中断；如果同时存在独立监督中断证据，两项事实并列。实际失败结论也不被覆盖。

## 返回结构

- `identity`：Project/instance/storage generation/context摘要、Run/Plan身份。`facts.run.phase_attempt_id / attempt_no` 是现有Attempt标识；不生成新ID。
- `view`：读取时点、Run revision、事件上界/覆盖序列、`snapshot_digest`。快照包括完整**限额内**目标Run相关记录和slot/gate，不能逐条独立读取后冒称一致。
- `facts`：原有白名单JSON投影，包括原执行阶段、receipt、启动/退出/验证/对账事件、已记录进程及管理范围、Solver/DAT/Artifact/ODB；完整原始路径/任意载荷不导出。
- `owner`：原owner ID/epoch、快照中的store owner ID。历史进程身份若未持久化或旧owner.json被新owner替换，明确缺失，不虚构旧PID。
- `last_recorded_event`：最后一条已记录的白名单事件；发生关系冲突时不宣称该记录已经验证为真实事件。
- `current_observation`：独立来源、起止时间、原owner/记录成员的查询状态、采样boot估计。member `record_index` 对应 `facts.run.process_records`；当前观察不是当时Supervisor已持久化的exit。
- `recorded_process_identities`：记录序号、PID、创建时间和原映像路径摘要；无绝对映像路径。`managed_scope_diagnostic`区分已提交绑定proof、未确认记录、预期但丢失的scope、未启动及未配置；不以空字段推断范围已经结束。
- `diagnosis`：有限机器分类、投影、message_key、reason_codes、known_member_active及范围说明；`reason_evidence` 提供指向**本报告**事实的JSON pointers。
- `resources`：同事务slot Run、gate/版本、已提交行政释放、旧路径逻辑引用及摘要。非行政路径显示 `RECORDED_PLAN_SCOPE_NO_RELEASE_BY_DIAGNOSTIC`，不声称取得物理排他权。
- `unknowns`：缺少退出、历史boot ID、原scope完成、当前OS观察等。`DOMAIN_EXTERNAL_PROCESSES_UNKNOWN` 永远不因本诊断消失。
- `recovery_preview`：是否可以向现有只读政策请求进一步评估；未执行政策准入，`apply_allowed=false`。当前已知政策仅Standard closeout和非managed固定Python recorded-exit review。Fake的产物采纳及managed新对账政策不被伪装成通用恢复预览。
- `disclosure`：无凭据/映像绝对路径/产物字节，无业务写入。摘要不是签名、授权或不可篡改凭证。

`snapshot_digest` 使用现有 canonical_json / SHA-256，包含有界原始DB记录及控制关系，排除读取时间；SQL tuple转为JSON array。`decision_digest` 绑定snapshot摘要、规则决定、scope/admin校验，不包含展示时间；相同持久快照的默认诊断稳定。`content_digest` 覆盖完整公开body，包括观察/读取时间。可选OS查询可因事实变化给出不同报告；不得将decision摘要作为恢复提交的版本检查替代品。

## 当前OS观察：严格保守

默认 `observe_os=False`，没有进程、Job、IPC或产物探测。明确设True后，仅核验绑定的 owner.json（最多16KiB）和Run已记录的最多32个成员。PID+创建时间100ns+映像同时匹配才可标EXACT_IDENTITY_ALIVE；只申请查询/等待权限，`cleanup=False`，finally关闭本次句柄。实际运行的exe路径不返回，仅返回摘要。

`PROCESS_UNAVAILABLE` 合并了当前无法打开/取得身份等情况，**不是确认不存在或已退出**。身份不匹配标 `IDENTITY_MISMATCH`。若拿到正确对象并确认句柄已signaled且退出码可取，标 `EXACT_IDENTITY_EXITED`，来源为当前新观察。不能把fixture先前持有的退出句柄结论借给未持有它的公共诊断。

Job不重开、不新建，不枚举全机；`scope_handle=NOT_QUERIED`。只有原提交proof能支持历史受管范围结束，不能从当前PID列表反推原成员全集。

boot来源为墙钟减 `GetTickCount64`，给出采样误差、采集时点及 `ESTIMATE_NOT_SESSION_PROOF`。Windows该计数包含睡眠/休眠，分辨率约10–16ms：[官方说明](https://learn.microsoft.com/en-us/windows/win32/sysinfo/windows-time)。实现增加1秒采样包络，但**这不是历史墙钟调整的误差上界**。历史时钟连续性、快速启动/重启会话身份未验证，仍列UNKNOWN；采样期间墙钟/单调时钟明显不一致返回CLOCK_UNSTABLE。估计晚于原owner创建时刻本身不触发Interrupted，还须未决启动及独立owner不可查询/身份不匹配，且无活动成员；结论仍只是疑似中断，不证明失败或全体退出。

预算：原DB事务最多0.75秒、单记录16KiB、总原始记录256KiB、events64、observations/validations各16、reconciliations8；公开报告128KiB。OS枚举数量严格有界，2秒为**开始下一次查询的合作预算**，没有后台线程/强行取消Win32调用，不能宣称硬墙钟上限。SQL、元数据文件和OS不是跨系统原子快照。

## 只读与错误

不初始化、迁移、修复、拿执行锁、修改revision/event/Grant/gate/slot/隔离/处置，不读STA/DAT/MSG/ODB内容，不调用验证器。错误沿用 `ExecutionError` 的稳定代码和脱敏QUERY消息；错误Project、不支持schema、超限、sidecar/DB忙、缺记录均安全拒绝。发现SQLite journal时仍按既有策略拒绝，不用rw连接恢复；在线写入期间可发生瞬时拒绝，使用者只可稍后重新查询，不能因此调用start/resume/retry。

历史OPEN按原值显示，不伪造PAUSED；没有有效owner时该OPEN不是执行许可。新诊断没有改变任何派发或停服准入。
