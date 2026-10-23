# Run 004 — Fake 对账、管理授权与受控恢复

日期：2026-10-22（Asia/Shanghai）。仅新建临时实验、Windows本机固定盘、原fake-v1。没有生产审批、旧数据迁移或真实进程恢复功能。

## 证据充分性的依据

[FakeBackend.emit](../../../abqjobpilot/execution/fake_backend.py)的全部动作是：确认本次Run输出目录不存在，创建专用目录，用xb写出固定JSON，flush/fsync，然后返回位置、大小、摘要。没有Solver计算、子进程、输入执行、隐藏的第二份输出或外部动作。内容只由原Plan中的配置/输入摘要及本Run/phase身份确定；原代码没有重新读取输入内容来执行计算。

本轮把同一规范化字节公式抽为[models.fixed_fake_content](../../../abqjobpilot/execution/models.py)，Fake写出的内容和路径不变。对账并非“JSON可解析且run_id匹配”：

1. 核验原context/root/manifest/实例；原Run、Job revision、Plan及其完整规范化摘要。
2. 限定backend=fake-v1/version=1、FAKE phase、原动作、资源、canonicalization与验证政策；输出策略必须与原固定模板完全一致。未知Backend/格式/越界策略在读取候选文件前拒绝。
3. 要求原SubmissionReceipt、一次REQUEST_ACCEPTED、一次START_INTENT、原ExecutionGrant与消费关系；按记录的领取时刻核验历史授权/计划有效性。缺证据不能借当前授权补齐。
4. 使用原Plan保存的配置快照和输入清单/摘要，不读当前Settings、不重新读取已经变动或删除的输入，不创建替代计划。
5. 仅在固定路径读取至多65,537字节，拒绝junction/reparse及共享硬链接；核对文件身份、大小、mtime与确定字节摘要，复用原独立validator检查全部JSON字段、格式、phase/Plan/config/input摘要和policy。
6. 要求实际字节与原固定动作完整预期字节相同。采纳的是这一有限动作的完成条件，不推断其他Backend或真实Solver成功。

结论明确为 `FIXED_FAKE_COMPLETION_INFERRED_NOW`。不证明过去某时刻观察到进程退出或fsync成功，也不证明能抵御同一OS用户伪造整个数据库与文件。原失败/未知事件不改；本次验证、快照持久化和采纳具有本次时间。没有补写过去的FAKE_COMPLETED事件。

## 三个操作及状态边界

实现集中于[reconciliation.py](../../../abqjobpilot/execution/reconciliation.py)，由原[ExecutionService](../../../abqjobpilot/execution/service.py)提供三个方法，复用原Store事务、OS锁、事件更新和validator；未另建执行框架。

| 操作 | 前置与效果 |
| --- | --- |
| preview_reconciliation(context, run_id) | 当前排他owner、PAUSED、无正在进行的本地Fake。只读Run/原计划/历史和固定产物；返回候选动作、具体原因、owner/Run revision/Plan身份、证据指纹和规范化preview_digest。无DB写入、证据副本、授权或门禁变动 |
| apply_reconciliation(context, request) | 精确测试管理授权；重新计算预览并匹配摘要/revision。只允许adopt_verified_fake_artifact。保存此次捕获字节快照，事务追加observation/validation/reconciliation/event/操作回执和管理授权消费；更新同Run为FINISHED，reconciliation=NONE，artifact=VALID，solver=NOT_RUN。当前错误投影清空，旧错误事件保留。只释放本Run占用槽，门仍PAUSED |
| resume_dispatch(context, request) | 另一份精确权限，匹配当前owner/gate version，存储无需维护，无任何不确定Run且槽为空。事务只打开门、增加版本并记录控制事件/回执/消费，不改Run、不延长Plan/Grant、不返还消费 |

候选不充分时返回reasons中的结构化code/message；apply拒绝，无Fake、无补写、无Retry、无强制成功或万能清槽入口。

恢复后原worker继续调用原execute_pending。PENDING在实际领取事务中才归属当前owner，owner_epoch增加；它仍经过原Plan、当前输入/配置、ExecutionGrant、authority、期限与资源检查。失效任务保持BLOCKED；原授权消费不返还。已完成或不确定Run不成为PENDING，不重复执行。

## 格式3与门禁

仅create_experiment创建新manifest/schema **3**。新增dispatch_gate、management_grants、management_receipts、management_consumption、reconciliations、control_events；保留原执行表。格式1/2继续只读原回执/Run/事件/验证；新管理或可写接管明确UNSUPPORTED_FORMAT，绝不隐式迁移。

门记录owner_id、version、OPEN/PAUSED。每次显式Supervisor启动都换owner并增加门版本；只有无Run且从未由Supervisor管理的新实例可首次OPEN，所有重启一律PAUSED。原进程排他锁取得前不能执行管理写入。进程内多个service对象和IPC线程通过原RLock、BEGIN IMMEDIATE及唯一约束串行化。

调度资格从持久门读取，不靠单个客户端或service内存布尔值。旧resume回执与当前门分开：新owner下同请求重放返回旧回执中的历史OPEN版本，但当前门保持新owner的PAUSED。它不是再次恢复命令。

## 三类凭据与测试管理控制

| 类别 | 来源与范围 |
| --- | --- |
| IPC credential | 私有bootstrap的连接秘密；只允许连到固定Project/owner及服务端namespace，不能单独批准管理动作 |
| ExecutionGrant | 原TEST_ONLY固定Plan执行授权，仍只管一次原Run接受/领取；不能代替管理权限 |
| 管理Grant | TEST_ONLY_MANAGEMENT，issuer=FakeManagementFixture；绑定原fixture authority、Project实例/context_digest、当前owner、动作、精确scope、expires_at、max_uses=1；存于独立登记/消费表 |

采纳scope为 `run_id, expected_run_revision, preview_digest`；恢复scope为 `expected_gate_version`，另有共同的Project/owner绑定。严格区分bool/int，未知字段/self-approved/管理员角色/任意目标状态全部拒绝。没有mint/approve RPC。

测试支持[FakeManagementFixture](../../../tests/reconciliation_helpers.py)必须持有真实owner的Store，使用其transaction登记。多进程时，显式启用的测试harness在自己创建的控制目录写入原子grant请求文件；owner内测试watcher读取并通过自己的Store登记，原子写回应。父进程不直接打开活跃执行库写授权。这段控制仅在测试入口、且management_control显式开启时存在，产品Supervisor.main没有此机制。控制文件并非面向普通IPC客户端的批准接口。

同一OS用户可直接改程序/数据库/文件的权限不在应用隔离保证内。上述机制只是精确测试权限，未宣传为生产人类审批或通用权限平台。

## 指纹、快照与事务

预览摘要覆盖Project/实例/context、owner、门版本/状态、Run revision、Plan身份、文件路径/identity/size/mtime/actual与expected摘要、原Run/Plan/事件/回执/执行授权摘要及结论原因。无随机验证ID和当前时钟字段，因此同一事实的预览稳定。apply不接收客户端的PASS结论，只收摘要和预期修订，再自行计算。

管理请求使用独立业务key与namespace `(Project实例, 固定client_namespace, action)`；摘要包括contract、Project、owner、管理grant和scope，不包含key。成功重放先查原摘要/回执，再考虑已变化的revision、门、期限和消费，因此不会再次执行；同key异内容直接冲突。不同key并发对账相同revision最多一个提交，其余陈旧。

事务顺序：

1. 查原操作回执，命中则只重放；否则核验管理权限、当前owner及门。
2. 重算历史证据及捕获内容，匹配预览/revision。
3. 在 `runtime/reconciliation_evidence/op_<uuid>.json` 用xb写出捕获的同一组有限字节并fsync。源产物不改。
4. 原事务内追加快照引用、observation/validation/reconciliation、RECONCILIATION_APPLIED、Run投影、回执及管理消费，提交后才返回APPLIED。

快照与validator使用同一captured bytes，防止“先验证一份、再复制另一份”。快照文件没有覆盖/修改API；数据库持久摘要绑定其内容。保留源路径只作来源说明，不以可变源路径代替证据快照。这是应用层不可变约束，不是对同OS用户任意修改磁盘的防御。

文件系统与SQLite不存在跨介质原子事务。快照已写而DB失败时留下以operation ID识别的未引用文件，Run继续不确定，不报告成功、不删除历史；普通查询不清理。commit确认丢失或应答丢失返回ACCEPTANCE_UNKNOWN，应查原key，不能换key盲重试。测试覆盖before/after snapshot、before/after commit及commit已成功却抛确认错误。

## IPC增量

继续唯一的127.0.0.1长度分帧UTF-8 JSON，原2秒读/写/连接界限、请求64KiB、响应256KiB、8连接、事件64条分页保持。保留原六个操作，增加明确白名单：preview_reconciliation、apply_reconciliation、resume_dispatch、dispatch_gate、management_receipt、reconciliations。新客户端仍只连接，不自行管理owner生命周期。

管理请求contract为 `af-management-v1`；它不改变旧API/Project/数据库schema或应用版本。外层wire request_id与管理idempotency_key、操作回执operation_id、原SubmissionReceipt分别独立。

```json
{"contract_version":"af-management-v1","operation":"adopt_verified_fake_artifact",
 "project_id":"<fixed>","project_instance_id":"<fixed>","owner_id":"<current>",
 "management_grant_id":"<registered exact test permission>","idempotency_key":"adopt-001",
 "run_id":"<original>","expected_run_revision":2,"preview_digest":"sha256:<server preview>"}
```

resume请求把operation改为resume_dispatch，scope只用expected_gate_version；必须另有对应grant。操作回执通过management_receipt(action,key)查询，当前Run/门分别通过run/dispatch_gate查询。查询遇journal/WAL/schema问题沿用维护/不支持错误，不初始化或修复。

没有新真实启动能力、任意命令、动态Backend、Solver控制或旧Runner导入。完整实测及边界见[验收矩阵](ACCEPTANCE_MATRIX.md)。
