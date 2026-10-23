# Run 005 — 一致读取、诊断与导出契约

## 复用边界与实际读取路径

[store.py](../../../abqjobpilot/execution/store.py)的query_run、query_receipt、events、validations、observations、reconciliations和gate是原读取入口。它们使用_connection(read_only=True)：显式实验context/manifest身份核验、SQLite mode=ro、query_only=ON、foreign_keys=ON，检查DELETE journal模式及meta格式/context摘要；发现wal/shm/journal即维护拒绝。不创建数据库或Schema，不将活跃库标为immutable。

原read()会取得同进程session RLock，但不显式开启覆盖多个SELECT的事务。多个旧查询不能拼成一致报告；原5秒连接等待也不适合本轮2秒IPC约束。新ReadOnlyStore.diagnose只复用连接策略，单独使用0.2秒SQLite忙等待与0.75秒读取截止、SQL进度处理器；不取得/释放执行owner锁，也不等待原session互斥量。原查询和写入默认参数不变。

新路径：显式context+run_id → mode=ro → BEGIN → 按Run读取有界原始记录 → 关闭连接结束读事务 → [diagnostics.build_report](../../../abqjobpilot/execution/diagnostics.py)白名单投影与确定性规则 → 有界序列化 → IPC。客户端export_diagnostic → [audit_export.export_report](../../../abqjobpilot/execution/audit_export.py)，只使用已经取得的同一报告，不访问存储、网络或产物。

## 持久事实与未知信息

事务读取runs、该Run的原receipts、原plans记录、按run_id过滤的events/observations/validations/reconciliations，以及dispatch_gate。报告不读取执行/管理grants、消费表、当前Settings/configuration、原输入、原产物、证据快照文件、owner.json或默认Recent。原消费关系不出现在投影中，也不变更。

Run revision在Run JSON中；事件同时有Project全局sequence和每Run的run_sequence。报告记录读取上界及实际两个序号列表，只按本Run的run_sequence检查历史缺口；其他Run占用全局序号不是缺失事件。

派发门OPEN/PAUSED、version和owner_id在格式3数据库中持久化，属于本次SQL快照。Supervisor的last_error、active_dispatches、活跃OS锁、worker/进程健康属于内存/系统观察，本轮不采集，不将它们与数据库拼成原子视图。格式1/2可读取原表，门和对账表不存在时明确未记录，不迁移。

现有ExecutionError由code/stage/requires_reconciliation等表达；执行包没有独立持久化Failure Classification字段。本轮解释层分类不成为第二套状态机，也不伪造历史分类。原始错误message、重试描述和任意自由文本不进入报告。

旧parsers.py的classify_datacheck_attempt/classify_final_verdict使用真实日志、return_code、fatal_reason及SUCCESS/FAILED/UNKNOWN等判断；本轮只做源码边界核查，不导入或调用它们，不把该Solver分类套到Fake Run，也不修改旧Datacheck行为。原Fake已有PLAN_EXPIRED/PLAN_STALE、GRANT_*、TERMINAL_COMMIT_FAILED/EVIDENCE_WRITE_FAILED等已记录code按白名单保留；其他自由值显示null而不泄漏消息。

## 报告结构与白名单

版本 `af-run-diagnostic-v1`，规则 `fake-diagnostic-rules-v1`。实现中的BODY/FACTS/RUN/EVENT等声明是精确白名单；未知枚举或未记录的可选字段为null，报告明确说明这个约定。不存在“先导出整对象再正则删秘密”的路径。

| 部分 | 包含内容 | 有意省略 |
| --- | --- | --- |
| identity | Project/instance/storage_generation/context摘要、Run/Plan关联、历史Plan摘要 | 绝对存储路径；原Job名称用job_ref摘要代替 |
| view | SQL来源、read_at、Run revision、事件上界和实际序号、database_records_only | 文件系统/进程的原子性承诺 |
| run | 各维度状态、attempt/phase/owner关联、历史创建/对账时间、已知错误code/stage | grant_id、原错误message、任意字段 |
| receipt | request_id、ACCEPTED、accepted_at/sequence、Run ID、初始PENDING | namespace、idempotency_key、授权引用 |
| plan | Plan ID、历史摘要、固定Backend ID/version | 配置、输入、命令、元数据和原始Plan对象 |
| events | ID、双序号、类型、历史时间、证据引用；载荷只投影revision和已知状态维度 | 原始载荷、自由文本、错误堆栈 |
| observations | 已记录Artifact身份、size/mtime/digest、归属、历史观察时间；快照operation/digest/size | 路径和Artifact字节，不检查当前文件 |
| validations | ID、历史verdict/policy/validator/version/scope/时间/引用/快照摘要 | 原始reasons自由文本；不新建ValidationRecord |
| reconciliations | ID、原Run、owner/action、当时来源/结论/时间及observation/validation/snapshot引用 | preview中的绝对路径、管理许可、原始证据对象 |
| diagnostics | 稳定解释原因码、分类、记录事实、固定规则推断、未知项、来源引用、候选下一步和前置条件 | 百分比置信度、命令、批准/执行能力 |

关联ID是已生成的实体标识，不是可用授权：审批/执行仍要求另行登记Grant与最新前置检查。对外generated ID限定既有prefix+UUID十六进制；摘要限定sha256格式；Job自由名称只输出摘要。原始输入/配置路径不输出，Artifact用observation ID和快照operation ID作为逻辑引用。

这是字段级投影，不是通用匿名化或抵御同一OS用户修改程序/数据库的安全域。

## 解释规则与时间语义

REQUEST_ACCEPTED只依赖原回执；WAITING_DISPATCH依赖PENDING；EXECUTION_STARTED依赖历史START_INTENT。沿用原需要对账条件：START_INTENT/VALIDATING或显式RECONCILIATION_REQUIRED，不反写Run。

EVIDENCE_INSUFFICIENT只说明持久记录没有建立验证通过结论，不等同于检查过当前产物后判失败；只读诊断不运行preview_reconciliation或validator。历史PASS/FAIL明确表述为历史simulation验证，不表示当前文件再次验证。EXPLICITLY_RECONCILED取自原对账记录；门是否PAUSED独立报告。Fake COMPLETED与Artifact结论独立，进程/退出仍NOT_APPLICABLE，Solver仍NOT_RUN。无错误记录不推导为成功。

本次read_at与accepted_at、observed_at、recorded_at、reconciled_at分别保留；读取时间是事务读取完成时的系统UTC秒，报告没有声称时钟防篡改。没有历史字段就标未知/null，不补写记录。

每个建议仅为候选步骤，附“认证的显式Project查询、另行授权任何写动作、执行时重新核验owner/evidence/Plan/Grant”等前置条件；不提供可执行命令或批准。

## 限额与失败

| 边界 | 首版限制 |
| --- | ---: |
| 单次报告Run | 1，必须明确generated Run ID |
| 事件/observation/validation/reconciliation | 64 / 16 / 16 / 8 |
| Run/Plan/receipt | 各至多1 |
| 单条原记录UTF-8字节 | 16,384 |
| 本次累计原记录UTF-8字节 | 262,144 |
| manifest字节 / meta条数 | 16,384 / 16 |
| meta键/值字符数；门owner/state字符数 | 256/1,024；256/32 |
| 字符串字符数 / JSON嵌套 / 遍历节点 | 1,024 / 16 / 8,192 |
| 报告序列化字节 | 131,072 |
| SQLite忙等待 / 读取截止 | 0.2秒 / 0.75秒 |
| 原IPC请求/响应/连接数 | 65,536 / 262,144字节 / 8，不变 |
| 原IPC读写超时 | 2秒，不变 |

SQL限定limit+1并在超限时拒绝；CASE先限制body大小，避免把超大记录传到Python后再丢弃。大于限额返回LIMIT_EXCEEDED，没有截断后声称完整。未知格式UNSUPPORTED_FORMAT、缺失NOT_FOUND、sidecar STORE_REQUIRES_MAINTENANCE、损坏/忙/截止STORE_UNAVAILABLE，保持明确失败。诊断错误统一固定消息，不回显底层路径、异常或自由文本。原执行错误行为不改。

连接前manifest有限读取，SQL元数据与门的字符串也先以CASE限制，避免正文之外的字段绕过限额。此策略只在诊断传入deadline时启用，其他原连接入口保持原行为。记录JSON的必要Run/Project/Plan/证据关联若相互矛盾，返回STORE_UNAVAILABLE，不能生成错绑的报告。

只新增一个认证RPC `diagnose`，参数严格只有run_id；不收路径、批准、回调或过滤表达式。沿用Project/instance/context/owner握手与本地连接凭据。诊断传输request_id另外限定generated wire ID，防止把凭据塞入待回显字段；无新管理权限要求。

## 客户端导出与摘要

一个Run、一份JSON、一个明确目标。调用者先取得report，再调用FakeClient.export_diagnostic(report, export_root=..., target=...)。导出目录须已存在，由调用方选定在执行Project、输入/输出之外；本轮测试均采用临时根内独立audit_exports/exports。目标必须为该目录的直接.json子文件；沿用local_path/confined/no_reparse，拒绝逃逸、..、UNC、ADS和重解析路径。

导出对同一份报告做有界序列化、白名单结构和摘要核验，冻结确切字节；不再次查询。先xb创建随机audit_<uuid>.partial，记录文件identity，写完flush/fsync；Windows rename在目标已存在时拒绝，不使用replace覆盖。失败时只清理本次实际创建且identity仍相同的partial。权限/磁盘/发布失败不报告成功；进程崩溃或清理失败可能留下partial，后续普通查询不会清理它。没有数据库和文件的跨介质事务宣称。

content_digest覆盖本次报告body的canonical JSON字节，不含content_digest本身；它与原Plan/Artifact历史摘要引用明确不同。摘要不是签名、来源认证或防篡改保证。报告不包含原Artifact字节、整个DB、Runtime、原日志或授权凭据，不能导入为提交、对账或恢复请求。

可复现三阶段演示、实际限额/故障与进程结果见[验收矩阵](ACCEPTANCE_MATRIX.md)及[测试和进程证据](TEST_AND_PROCESS_EVIDENCE.md)。
