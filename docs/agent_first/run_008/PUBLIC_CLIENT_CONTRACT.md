# Run 008 — 公开工作流接缝、职责与契约

本轮复用原ExecutionService、SQLite事务、owner锁、Supervisor执行线程、固定process Backend、独立validator、管理幂等、诊断和导出。不是新增执行核心或第二套SDK。薄客户端仍名为FakeClient，其process功能明确TEST_ONLY。

## 实际接缝与最小补齐

审查前，`client.py:FakeClient`已提供submit/receipt/run/events/validations/diagnose/export_diagnostic以及R4/R7控制包装；没有公开读取固定Plan的操作，也没有显式运行独立validator的客户端操作。`service.py:execute_pending`内部调用`process_validation.py:validate_process_artifact`，只能从测试或内部路径单独调用。授权登记原先在`tests/execution_helpers.py:FakeGrantFixture`、`tests/supervisor_helpers.py:ProcessHarness`和`tests/reconciliation_helpers.py:FakeManagementFixture`；示例若照搬会依赖测试导入或SQL。包`execution/__init__.py`还在导入客户端时连带加载service/store。

因此仅补inspect_plan、validate_run两项IPC及同名包装；加入受owner约束的TEST_ONLY登记助手，改包导出为延迟加载。独立示例不导入tests、pytest或授权工厂。新批准助手使用既有check_grant/check_management_grant验证精确记录，再在既有owner事务登记；不是测试代码手工插入批准，不新增mint/approve RPC。该机制仍仅是开发测试可信入口，不是真实人类批准系统。

## 接口映射

| 步骤/权限 | 公开客户端或操作者入口 | 内部实现 | 输入→输出/副作用 | 主要拒绝 |
|---|---|---|---|---|
| 操作者创建/启用 | operator_demo.main，create_experiment，ProcessFixtureConfig.current | Store/LocalOwnerLock | 新临时根→ProjectContext；创建实验格式3，固定Backend配置 | PROJECT_EXISTS、OUTPUT_SCOPE_VIOLATION、OWNER_BUSY |
| 操作者准备Plan | ExecutionService.prepare | planning.prepare_plan | 显式JobSpec/Config/scenario→固定Plan；保存计划，不创建Run | PLAN_STALE、RESOURCE_LIMIT、TEST_GRANT_ONLY |
| 操作者执行许可 | test_authority.issue_process_execution | check_grant + owner transaction | 固定Plan/期限→精确一次TEST_ONLY Grant；写登记 | GRANT_EXPIRED、GRANT_SCOPE_MISMATCH |
| 启动owner | operator_demo --mode owner | FakeSupervisor/load_bootstrap/acquire_supervisor_store | 私有bootstrap+固定配置→显式独立owner/端点；获得锁 | OWNER_BUSY、ENDPOINT_IDENTITY_MISMATCH |
| 连接/能力 | FakeClient(endpoint, credential).health | supervisor._handle/_invoke | 显式Project/context/owner、认证→操作、Backend、限额、TEST_ONLY范围；无业务写 | AUTHENTICATION_FAILED、PROTOCOL_MISMATCH |
| 检查计划（新增） | FakeClient.inspect_plan(plan_id, expected_digest) | service.inspect_plan/public_workflow.inspect_plan | 原Plan→白名单投影；只读核对原固定摘要，非当前输入/授权预检 | PLAN_STALE、NOT_FOUND、UNSUPPORTED_EVIDENCE_POLICY |
| 提交/回执 | submit、receipt | service.submit/store.query_receipt | 精确Plan+Grant+业务key→原receipt/Run ID；接受与消费同事务 | GRANT_REQUIRED、PLAN_STALE、IDEMPOTENCY_CONFLICT、ACCEPTANCE_UNKNOWN |
| 观察 | run、events(cursor,limit)、validations、dispatch_gate | Store只读路径 | 既有持久化状态、分页事件、历史退出/验证；无OS重探测 | NOT_FOUND、INVALID_REQUEST、STORE_REQUIRES_MAINTENANCE |
| 操作者验证许可（新增） | test_authority.issue_validation | check_management_grant + owner transaction | 完成且退出已验证的Run/revision/Plan/current owner→精确一次管理ticket；写登记 | VALIDATION_PRECONDITION_FAILED、MANAGEMENT_GRANT_EXPIRED |
| 显式验证（新增） | FakeClient.validate_run(request) | reconciliation.manage + public_workflow.validate_recorded + 原validator | 专用管理ticket→操作receipt；有界读取原固定result.json，追加observation/validation/event、更新artifact投影/revision、消费权限 | MANAGEMENT_GRANT_REQUIRED、MANAGEMENT_SCOPE_MISMATCH、STALE_OWNER、STALE_PREVIEW、ACCEPTANCE_UNKNOWN |
| 管理回执 | management_receipt(action,key) | Store管理回执查询 | 原操作身份→原不可变回执；无业务写 | NOT_FOUND |
| 诊断/导出 | diagnose、export_diagnostic(report, export_root, target) | Store只读快照、diagnostics、audit_export | 一次快照→同对象JSON；导出只写客户端新文件 | LIMIT_EXCEEDED、STORE_UNAVAILABLE、OUTPUT_SCOPE_VIOLATION、EXPORT_* |
| 重启后恢复（原有，示例不调用） | 独立resume_dispatch+其精确管理授权 | 原R4 manage | 检查门版本、无未解不确定性、slot→OPEN；写控制事件 | RECONCILIATION_REQUIRED、GATE_PRECONDITION_FAILED |

普通客户端无create/prepare/approve/mint/动态Backend/命令RPC。能力里明确plan_preparation=trusted_operator_preprovisioned。Project在启动时绑定，namespace来自服务端bootstrap，传输request_id和业务idempotency_key不互换。

## 固定计划与示例权限交接

操作者准备一个result_wait计划、TXT输入、固定解释器/fixture摘要、四角色契约和资源上限，授予同一计划的一次测试进程启动许可。新实例首次Supervisor、尚无Run的既有路径允许OPEN；以后启动仍默认PAUSED。本示例不打开旧实例，也不调用resume。

私有connection/offer/validation-ticket保存在operator_private。offer包含精确提交请求；session仅保存公开Plan引用、业务key、原receipt和Run ID，不保存Grant或连接秘密。客户端A通过submit实际创建Run，未预建Run。A退出后owner独立处理；B用原offer/key/Run重连与重放。验证ticket在FINISHED之后由owner中的可信控制线程按预先批准Plan登记，普通RPC没有批准能力。

独立验证本来在正常执行末尾已运行；本轮公开入口允许显式再次验证，或R7确认进程结束而Artifact未验证后首次验证。新增source=explicit_client_validation保留实际验证时间，与原验证记录并存。请求仅允许FINISHED、reconciliation=NONE、完整四角色匹配退出、exit=VERIFIED的固定Backend。仍需独立管理权限；IPC credential或原ExecutionGrant不够。验证不改变执行/退出事实、原接受回执、启动尝试、执行消费、slot或gate，不重跑Backend、不对账、不恢复派发。

授权与请求绑定Project/context、current owner、Run/revision、Plan ID/digest、action、期限、一次消费。使用原manage事务同时提交操作receipt、权限消费、observation/validation、Run revision及事件。同键同内容先返回原成功回执；异内容冲突；并发只写一次。提交确认不明查询同操作key，不换key盲重试。新入口错误不传递底层异常载荷。

## 读取、脱敏和限额

inspect_plan只读已保存计划，不读取当前输入，输出逻辑input:0引用和历史摘要，省略路径、原Config值、授权；不提供任意文件读取。既有IPC仍为127.0.0.1 TCP长度帧、64KiB请求/256KiB响应、2秒I/O超时、8连接、64事件/页。诊断保持原128KiB白名单和短只读事务限额；验证仅原固定64KiB产物。没有扩大协议限额或迁移Schema。

进程诊断继续af-run-diagnostic-v2/process-diagnostic-rules-v3；仅允许验证source新枚举，不增加必需字段。旧v2导出可读，历史缺失source仍null。诊断不重新验证；显式validate_run先产生新的历史记录，随后diagnose再读快照。导出摘要仅覆盖脱敏body，不是签名或执行许可，不包含产物字节、授权、完整数据库或日志。

run/events/validations原查询可包含内部路径/Grant关联；示例不原样落盘这些对象，只保存公开白名单、事件引用和脱敏诊断。未声称旧接口已成为通用匿名化API。历史观察只能说明最后记录；连接失败不能表示任务失败/取消/可安全新建任务。示例出错输出稳定code、原key/Run及query-first前提，不写exception载荷。

同OS用户可修改程序、数据库和凭据，不属于权限隔离威胁模型。示例的审计hook是可检测的开发隔离防线，不是生产沙箱。通用工程任务/Plan准备、真实审批仍待设计。
