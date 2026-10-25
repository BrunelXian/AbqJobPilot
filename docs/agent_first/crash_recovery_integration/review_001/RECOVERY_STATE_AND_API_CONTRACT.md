# CR-D01 — 术语、识别与操作契约（设计 v1）

**本文件新增名称均为拟议契约，不是已经存在的调用入口或执行授权。** 已有函数名见能力矩阵。D02 保持执行 Schema3、Run 状态和已有摘要不变。

## 术语与允许的转换

| 概念 | 定义与边界 |
|---|---|
| Crash Recovery | 异常监督中断后的识别及可审计处置；不代表重新求解 |
| Execution Reconciliation | 以原 Run/Plan/attempt 的可信持久证据评估；不能凭 IPC 超时/PID 消失写 exit |
| Interrupted (Unverified) / 异常中断（结果未验证） | 疑似监督/执行会话中断诊断，不能表示 Solver 已失败、已停止或可从断点继续 |
| Requeue | 从未创建外部副作用的原排队请求与新尝试分开。START_INTENT 即不再归为可安全重新入队；其他原 PENDING 不动 |
| Retry | 独立新 Run/phase_attempt_id、新 Plan/Grant/幂等身份和独立 output；旧消费不退还；当前 Standard 明确拒绝 |
| Solver Restart / Resume | Abaqus 原生重启动语义、数据与输入校验，另行设计/授权/验收；不由本交接证明 |
| 自动正常收尾 | 原有效受管句柄、创建已确认、无待决加入、直接 OS 空范围证明及终态事务成立 |
| 行政释放 | 操作者明确接受剩余不确定性，只改政策处置/逻辑槽；不改原 UNKNOWN、Solver、Artifact、物理资源结论 |
| Resume dispatch | 独立权限和派发前提；不是 Recovery Apply 的隐式后续 |
| Stop owner | 独立安全空闲策略；释放槽也不必然允许 Stop |

保持现有 execution=PLANNED/START_INTENT/VALIDATING/BLOCKED/FINISHED 等值及原 reconciliation 投影。不增加全局 UNKNOWN_INTERRUPTED。该名称只作为版本化诊断的兼容显示 alias；稳定机器 code 建议 SUPERVISION_INTERRUPTION_SUSPECTED，旁列 evidence confidence/unknowns，而非给 Run 写“FAILED”。

已确认正常/失败仅来自原有持久证据：例如 managed_completion=COMMITTED_EMPTY_SCOPE 说明范围结束；solver_conclusion=COMPLETED_TEXT_EVIDENCE 与 DAT PASS 独立成立。非零进程退出不自动等同所有 Solver 失败。已行政处置显示 ADMINISTRATIVE_DISPOSITION_RECORDED，同时保留原疑似中断/UNKNOWN。

## 识别算法：持久快照与当前观察分开

1. 显式 ProjectContext 只读打开；格式不支持/维护状态/缺记录/超限即结构化失败。不修复、不初始化、不获取写 owner。
2. 单一只读事务取得目标 Run、原 Plan/receipt/消费、完整有界事件、observation/validation/decision、持久 gate/slot/owner 元数据。保留 schema/projection/rules version、revision、事件覆盖上界、内容摘要和 read_at。
3. 判断终态、管理收尾、现有行政处置、START_INTENT 及未决证据。对纯 PENDING+PLANNED 单列 NEVER_STARTED_RECORDED；若存在无法解释的历史或冲突，降为 EVIDENCE_CONFLICT，不断言“从未发生副作用”。
4. 可选**单独明确调用**的当前观察：只读取已记录 PID+创建时间+映像，持有只查询权限句柄；标记 EXACT_IDENTITY_ALIVE / IDENTITY_MISMATCH / NOT_FOUND / ACCESS_DENIED / QUERY_FAILED。不能请求 cleanup/terminate 权限，不枚举整机进程名作完成依据。
5. owner 认证 health 成功是当前对应实例响应证据；超时不是死亡。锁元数据只说明历史 owner；Inspect 不探测抢锁，写互斥状态返回 NOT_ACQUIRED/UNKNOWN。真正管理 Apply 才取得原 LocalOwnerLock。
6. 可选 boot/session 观察返回来源、采集起止、host identity、估计误差和可比较性。当前 Dev 没有可回溯的每次启动 boot 标识；缺失不得回填。墙钟减 uptime、文件mtime或报告的 reboot 时间只能辅助；时钟调整/休眠/快速启动/误差区间交叠不得断言“新会话已证明旧进程结束”。
7. UNKNOWN_INTERRUPTED 的投影须满足未决启动/监督证据 + 可解释的 owner/session 失联依据，并列其不确定性。只有 GUI 退出、网络超时、查询失败、单个 PID 不在，不足以确认执行中断；显示 EXECUTION_STATE_UNKNOWN 并给 reason。
8. 当前 worker 身份匹配仍活：显示 WORKER_STILL_OBSERVED / SUPERVISION_LOST（如适用）；禁止释放/重排/重跑。已知范围句柄遗失：MANAGED_SCOPE_EVIDENCE_LOST；禁止新建空对象代替。
9. STA/DAT/MSG/ODB/.lck 的存在、mtime或内容不能被自动补成该 Run 的验证。Inspect 默认不读产物。未来显式验证继续走已有独立验证策略；历史完成证据但验证缺失显示 VALIDATION_NOT_RECORDED。
10. 完成后关闭本次只读句柄；没有后台观察者。OS、文件、DB是不同时间域，报告不得称为跨系统原子快照。

D02 默认无需当前 OS probe 即可报告“缺证据/原状态/待对账”。实现可注入测试事实，**生产公共参数不能接受调用者自报 boot_changed=true 或 members_complete=true**。真实 probe 适配单列来源；提供的历史测试事实不能获得 Apply 资格。

持久派发门也必须按读取结果表达：owner突然死亡可能留下历史OPEN；读取不会自动写成PAUSED。无有效owner时这个OPEN不是可用执行许可。显式取得新管理所有权后才记录PAUSED；产品单次派发还需独立核对single_dispatch的原owner和窗口，不能只读gate判定权限。

若_check_sidecars阻止读取，Inspect只能报告显式manifest身份（已核验部分）、STORE_REQUIRES_MAINTENANCE、读取失败时间和缺失范围；不能返回编造的Run快照或调用普通rw连接让SQLite恢复。存储维护不属于本契约的默认Apply。

## Phase A — Inspect（拟议）

最小入口：纯分类器 build_interruption_report(context, snapshot, observation=None)，加既有只读 Store 适配；后续 public client inspect_interruption(run_id)，不额外创建服务。owner 不在线时提供明确 offline 只读模式，不调用 ServiceLifecycleManager.start。

返回：
- contract/rules versions；Project/instance/context/storage generation；Run/Plan/phase_attempt_id/attempt_no；
- recorded owner/epoch、已记录成员身份/证据引用；当前 observation 独立 provenance；
- persisted execution/reconciliation/gate/slot、scope proof、Solver/Artifact/DAT/ODB；
- engineering/scratch/output 的相对引用与 RETAINED/UNKNOWN，不导出完整环境/凭据；
- classification、稳定 reason_codes、unknowns、禁止动作；
- snapshot_digest、run_revision、event_upper_bound、read_at、evidence scope。
建议上限沿用 diagnose 单 Run 现有预算；分页32项、单报告128KiB以内、DB读0.75s；OS probe 单次总预算2s且逐项拒绝无界列表。超限显式 LIMIT_EXCEEDED，不截断后宣称成员完整。

## Phase B — Preview（拟议组合，不替换已有政策）

基于同一 DB snapshot 调用相应纯评估器，附版本化 interruption classification。返回 action 列表、eligibility、preconditions、effect/preserves、authority_required、unknowns、snapshot/preview digest。保持无写、无OS探测、无产物重读；如含 probe，仅引用此前显式捕获的独立观察，其时间和来源必须可见。

- Fake：已有 adopt_verified_fake_artifact 是不同契约，会捕获固定 Fake 内容；不得当作新通用 Crash Preview 的实现。
- 非 managed 固定 Python：已有 reconcile_recorded_process_exits。
- Standard：已有 retain_standard_resources / release_standard_logical_slot，仅当前条件全部成立才推荐。
- 丢失 managed 最终提交：列 NEEDS_MANAGED_EVIDENCE_POLICY，不冒用四角色策略。
- 重启缺 exit：现阶段列 RETAIN_AND_REVIEW / NO_SUPPORTED_RELEASE_POLICY。不能把设计中的 future action 显示成可执行。
- 同一报告明确“获取管理所有权将写 owner/gate”，offline read 不能假报 can_apply=true。

## Phase C — Authorised Apply

既有合格路径继续使用现有 action/grant/manage；不增加第二套批准协议。

产品桥接的最小未来顺序：
1. 在明确操作者请求下验证产品实例、host-bound 凭据和**独立恢复管理能力**。连接、Start/Stop 或真实 Solver operator token 不自动等于恢复权限。
2. 取得现有 LocalOwnerLock 的同一排他字节锁，验证原文件身份；OWNER_BUSY 或锁状态不明即拒绝，不删锁/强抢/自动重试。该管理会话不创建 listener/dispatcher/Backend，不替换仍存活的旧 owner。
3. 明确记录管理 owner/epoch（复用 acquisition 元数据），持久 PAUSED；重新在锁内读取和评估。外部预览不是授权依据的最终视图；新 owner 需要新精确 grant。
4. 精确授权绑定 project/context、run/phase/plan、policy/action、revision、preview/evidence digest、owner、gate/version、槽/路径影响、有效期、一次使用、主体/来源/理由及接受的残余风险。实际 scope 纳入已有严格字段校验，新增policy不能以未知字段静默兼容。
5. 同一 owner mutex + SQL事务：先查同namespace/action/key原回执；同请求返回原结果（不因owner/revision/有效期已变丢失旧回执），不同内容IDEMPOTENCY_CONFLICT；然后验证权限/新鲜度/前置条件；追加decision/event，必要投影、槽/gate、receipt/consumption一并提交。
6. 新证据、身份匹配活跃进程、竞态、超限、路径保留不成立、观察过期/相互矛盾均拒绝。OS观察不具备与SQL原子性；只有管理排他权和已批准的保守政策能约束受支持写入者，不宣称排除了同用户恶意外部启动。
7. commit结果未知用原key查回执，不新建key；意图/证据/审计不可删除。文件导出不是提交权威，不以导出失败回滚已提交决定。
8. 不恢复派发、不Stop owner、不新Run、不Retry、不验证ODB、不清输出。若新政策尚未批准，该分支根本不提供 Apply。

**缺 exit 的未来行政政策（CR-D03后段，须独立评审）**：只接受确切新会话证据或明确的持续不确定性评估；任何已知匹配活跃成员/活跃写入owner均禁止释放，未知不能按false处理。操作仅为“接受列明不确定性，释放逻辑槽”，旧路径永久保留、PAUSED、原状态不变。无法保留隔离或不能限定后续危险派发时仅允许保留决定。不能以它通过安全停服 require_idle，不修改正常完成含义。该设计**不是当前可用政策**，D02不会实现，D03若条件仍不可证必须停在retain。

## Phase D — Verify

重新只读查询原receipt、consumption、decision、revision、gate、slot、路径保留；比较原历史事件/退出/Solver/validation摘要不变；确认原未启动队列未变化、无新 START_INTENT/Run/Grant/进程创建。报告“管理处置成功”与“执行证据仍UNKNOWN”并存。旧receipt重放不代表旧权限在新owner继续有效。

## 数据兼容与 GUI 投影

- D02 无 DDL/Schema迁移；新诊断可导出到显式目录（白名单、限额、no-overwrite），不写 Run/Event。沿用 canonical_json/digest 算法但使用新report/rules标识，不改变既有Plan/Grant摘要。
- D03优先复用reconciliations、management_grants/receipts/consumption、control_events。新policy的结构版本必须被reader白名单明确支持，旧reader返回不支持，不能当普通正常完成。若需持久化当前OS观察，必须独立标注新观察时间与source，不伪装旧owner exit。
- 目前不需要新增全局Run状态或DDL。若D03证明字段/索引/约束不足，另出schema版本/显式离线迁移设计；本计划不授权生产迁移。D05旧Run关联不能借force-terminal通过既有retry校验。
- 产品manifest v1与执行schema3不等于Classic project.db。Legacy恢复只操作明确旧格式；不双写、不默认Recent、不复制活跃凭据/恢复许可到Project副本。
- Run023拟议Runs行可有“Interrupted (Unverified)”诊断徽标；Details同时展示原execution、reconciliation、scope、Solver、DAT、ODB、decision、PAUSED/slot、证据来源/时间。点击徽标打开该诊断及证据引用，不能只有颜色。
- Results未有验证则显示未验证，不能按“中断”改成失败；History保留原记录；Execution Evidence按历史/当前观察分组。行政释放另行显示，不能去掉UNKNOWN。
- Classic status_presentation单独修正为Interrupted(Unverified)，不把新投影写回旧DB，也不把旧GUI approval token用于ExecutionService。
- CLI/MCP仍五个Classic只读/预览工具；CR-D04先只读capability协商，写接口另审。语言仅显示偏好，稳定reason code/证据字段不翻译。

