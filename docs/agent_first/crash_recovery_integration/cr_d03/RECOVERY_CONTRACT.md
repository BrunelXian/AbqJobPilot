# CR-D03 — Preview / Authorise / Apply / Verify

## 三类决策

| decision | 条件 | 本次影响 |
|---|---|---|
| KEEP_BLOCKED | 不支持、证据冲突/不足、无未决 Run、非 PAUSED；Apply 又检查活动/查询失败/锁冲突 | 预览只读；不能登记本动作许可、不能释放 |
| VERIFIED_RECONCILIATION | 原 R7 固定角色完整退出证据，或本版本核验的原受管 Job 创建/绑定/空范围查询链 | 既有有限状态对账、释放目标逻辑槽；不算 Solver/Artifact 成功 |
| AUTHORISED_ADMINISTRATIVE_DISPOSITION | 原 Run014 policy 完整满足，仍有域外不确定性，明确风险接受 | 旧行政记录/槽释放；UNKNOWN、路径隔离、PAUSED 保留 |

`UNKNOWN_INTERRUPTED` 仍仅是 CR-D02 诊断。分类不是权限，更不是进入 VERIFIED 的充分条件。GUI 消失没有恢复意义；活 owner、活记录成员、无法核查身份均阻断 Apply。

## 只读 Preview

`preview_interrupted_recovery(project_context, run_id)` 返回 body、preview_digest、read_at、完整 CR-D02 diagnostic。body 绑定 Project/instance/context、Run/phase_attempt、当前 revision、记录 gate owner、快照摘要、decision/policy/reasons、requires/effects/preserves/forbidden。PAUSED/slot/retention/原退出/Solver/validation 来自 diagnostic 和嵌入 policy。

摘要是既有 digest(body)，即严格 JSON、排序键、紧凑分隔、UTF-8 SHA-256。read_at 在摘要之外。预览默认不查询 OS，不抢锁、不写事件或 revision；R7 分支跨读使用前后 snapshot_digest 栅栏，变化即 STALE_PREVIEW。可考虑处置不是当前进程已停止，也不是授权。正在写入的 Store 可按旧 sidecar/busy 契约返回结构化拒绝。

## 可信本地边界

沿用 Run014 的 **可信同用户本地 Python 登记函数**，不新增人类身份验证平台。产品 DPAPI 只提供合法实例上下文，连接、lifecycle、Solver token 均不是恢复 Grant。

`open_product_recovery(project, run_id)` 是明确、有副作用的本地管理操作：取得与旧 owner 完全相同的 owner.lock（4096 字节位锁），在锁内先核查已有非 PLANNED Run、原消费绑定和记录身份。锁被持有即 OWNER_BUSY，不能删除锁或利用 IPC 超时。通过后沿用原 acquisition 更新管理 owner 元数据并持久 PAUSED；它不启动 Supervisor、dispatcher 或 Backend。

这不是 Preview 的隐式前置步骤。操作者必须先明确请求管理会话，再在锁内取得新 Preview。整个会话持锁，退出仅释放自己的 lease。活跃历史 owner 不被终止/重启/接管。

会话 `.authorize(...)` 是独立的可信调用，必须已有范围明确的实际批准；subject/source 记录来源，**不会自行验证是否为人类批准**。普通 IPC 和 FakeClient 没有 mint/recovery 路由；`approved=true`、修改 subject、TEST_ONLY 或 Solver Grant 不能通过 Apply。拥有同用户任意 Python/文件写权限仍属于现有可信域，不宣称 OS 权限隔离。

Grant 复用现有 management_grants / TrustedStandardOperator / EXPLICIT_STANDARD_DISPOSITION，action 单独为 apply_interrupted_recovery。精确绑定 context、owner、Run、revision、preview_digest、evidence_fingerprint、decision、subject/reason、residual_risk_accepted、operation_key；有效期最多600秒，max_uses=1，approval_source持久化。ADMIN 必须 residual_risk_accepted=True；该布尔字段单独不能批准任何操作。

## Apply / 原子性

`.apply(request)` → reconciliation.manage → 原 _request/_authorize → 原 management SQL事务。先查同命名空间/同key原请求摘要的回执；有原结果则重放，不重新检查已过期的历史权限。不同参数同key拒绝。新请求必须当前管理 owner、PAUSED、quiescent、未消费的精确权限。

在同锁同事务内重读诊断/revision/slot/gate/证据，调用现有 readonly process probe。只查询原记录身份（PID+创建时间+映像），无枚举、终止、Job重开。活对象、查询失败、身份缺失、超预算或缺返回成员拒绝；PID消失或复用仅表示未匹配原对象，不替代历史退出证据。随后再次检查快照和有效期。

决策记录、允许的 Run CAS、slot更新、control_events、管理许可消费与回执同一提交。before_commit失败回滚；after_commit丢应答查询原key。新 owner 只有取得原锁才可查询/重放；没有自动重新应用的机制。

原 Job 分支要求原 Plan 明确 windows-job-list-v1、原 scope/owner/attempt/plan 全绑定、唯一 prepared、末次原句柄 QueryInformationJobObject.BasicAccounting 为 EMPTY_CONFIRMED、创建完成且无后续加入、kill/breakaway均false、查询单调时标和整数计数完整、后续无冲突事件。永不新建空Job来补证。不存在完整证据时，仅可能走独立的旧ADMIN政策，不能伪造 VERIFIED。

锁只证明相同协议写者互斥。OS/数据库不构成原子快照；当前身份读的起止时间与来源保留在独立 RECOVERY_APPLIED audit，不覆盖历史 exit。原持久证据负责范围证明，当前 OS 读是额外否决条件。

## Verify 与限制

`verify_interrupted_recovery(context, request)` 只读按原key核验回执/消费/audit，旧Run字段及原Event前缀、Plan/执行Grant/消费/receipt/observation/validation/其他Run摘要、PAUSED和槽位。每表最多2048条/4MiB，超限拒绝，保留原动作状态；这不是无限历史审计服务。

`.apply` 返回已提交原回执和独立 verification。后续读取失败或状态合法变化使严格比较不成立时，保留原回执并标 `current_verification=NOT_CONFIRMED`，不能重放实际效果来“修复”。直接 Verify 会返回结构化错误。管理 Grant 登记本身与 Apply 是两个事务；登记后崩溃可能留下未消费许可，不能转为自动处置。

`RECOVERY_APPLIED` 只表示管理事务提交。`execution_verified=false` 不抹掉既有可信执行维度，它表示本动作不提供新的完整执行验收。原 R7 exit_verification、Job范围对账、Solver、数值、ODB各自读取。范围对账不放行A→B自动条件，也不自动Stop/Resume。旧工程目录、scratch、输出和 intent 原样保留，原 check_retained_paths 继续隔离；无整机/跨Project排他宣称。
