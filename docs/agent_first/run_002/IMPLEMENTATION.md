# Agent-first Run 002 — 实现与契约说明

本轮实现 [Run 001R 契约](../run_001_resume/ADR_AND_CONTRACTS.md) 的 Fake 内部切片。它不是独立执行服务进程、真实 Abaqus Backend、外部 Python SDK 或新的 MCP 工具。应用版本和旧 Schema 不变。

## 模块与入口

| 文件 | 实现 |
| --- | --- |
| [execution/__init__.py](../../../abqjobpilot/execution/__init__.py) | 仅导出实验内部 API，不注册 GUI/MCP/CLI 入口 |
| [models.py](../../../abqjobpilot/execution/models.py) | 不可变 ProjectContext、采用 canonical JSON 保存的 JobSpec/ConfigSnapshot/ExecutionPlan 值对象、结构化 ExecutionError |
| [paths.py](../../../abqjobpilot/execution/paths.py) | 显式测试根约束；先拒绝词法越界，再检查 reparse/junction；Run 输出路径只能由服务生成的 ID 派生 |
| [planning.py](../../../abqjobpilot/execution/planning.py) | TXT 输入 SHA-256、fixture 配置 revision/digest、固定 Fake 动作/资源/输出/验证政策，prepare 与 dispatch 前复核 |
| [authorization.py](../../../abqjobpilot/execution/authorization.py) | 只验证登记的 TEST_ONLY grant，检查精确 Project/Plan/Job/资源/输出/期限及消费；不提供批准入口 |
| [store.py](../../../abqjobpilot/execution/store.py) | 显式新建实验格式、事务、唯一约束、owner session、纯只读打开、Run/Event/receipt/证据查询 |
| [service.py](../../../abqjobpilot/execution/service.py) | configure、prepare、幂等 submit、原子 execute_pending；只有固定 Fake Backend |
| [fake_backend.py](../../../abqjobpilot/execution/fake_backend.py) | 只创建有大小限制的 JSON 结果文件；排他创建，不覆盖旧文件，无进程能力 |
| [validation.py](../../../abqjobpilot/execution/validation.py) | 独立验证 schema、simulation 标志、Run/phase/Plan/配置/输入摘要、输出位置、大小和输出摘要 |

调用顺序由 [test_headless_submit_and_validation_run_persisted_before_effect](../../../tests/test_execution_contract.py) 实际验证：`create_experiment → ExperimentStore / ExecutionService → prepare → FakeGrantFixture.issue_exact → submit → execute_pending → Store query`。所有方法都使用显式 context；没有从 GUI 或 Recent 自动选 Project。

`ConfigSnapshot` 当前只接受 `config_revision` 和 `values.label`，是 fixture 配置，不读取旧 settings.json。`configure` 是显式实验配置修改，原计划随之失效。Job revision 的内容不可原地替换；重新准备可以产生新 Plan。普通请求禁止 unknown fields，包括 approved、allow_solver_submit、executable、backend_id、output_dir。

## 多服务对象、所有权和单槽作用域

**本切片单槽作用域为一个实验存储/Project，不是主机全局。** 同一进程可创建多个 `ExecutionService` 和 `ExperimentStore` 对象，它们共享创建该实验时的 owner session/authority，但执行领取由数据库持久状态约束，不能靠服务对象的布尔值重复取得。

领取顺序：

1. `BEGIN IMMEDIATE`，读取 Run；必须仍为 `queue_state=PENDING, execution=PLANNED` 且属于当前创建进程的 owner。
2. 再校验固定 Plan、输入/配置和已消费到本 Run 的授权。
3. `UPDATE slot SET run_id=? WHERE id=1 AND run_id IS NULL`，只能一方取得槽。失败返回 `SLOT_BUSY`，原接受回执不变，Run 保持 PENDING。
4. 对 Run 的旧 canonical body 做条件 UPDATE，写 `START_INTENT` 与事件；与槽领取同事务提交。
5. 提交后才调用 Fake。重复调用看到已领取/终态 Run，只返回视图，不再发生副作用。

共享的进程内 RLock 用于数据库连接操作的串行化（避免把本进程短暂 journal 当维护问题），并不跨越 Fake 执行；真正的领取事实是 SQL slot、Run 状态和提交事务。测试使用不同 store/service 对象、同时竞争同 Run、占槽期间请求另一个 Run，并验证不重复执行。

不同实验存储拥有独立槽，可同时 Fake 执行，已有测试明确证明此作用域。没有主机级槽、跨 Project 输出身份协调或跨进程 owner fencing；不能将本结果宣传为已完成完整模拟 MVP。

## 提交事务与幂等

幂等 namespace 为 `(project_instance_id, configured client_namespace, submit)`；client_namespace 是构造时配置的内部客户端名称，不代表已经完成 IPC 身份认证。主键为 namespace + key。

同 key/digest 返回原 receipt 和同 Run；查到 receipt 后不重新读输入、验证过期 grant 或再次派发。同 key/different digest 在使用新 Plan/Grant 前返回 `IDEMPOTENCY_CONFLICT`。请求摘要版本为 `af-experiment-json-v1`：排序 key、紧凑 UTF-8 JSON、禁止浮点/NaN/Infinity、严格区分 bool/int，保留列表顺序与 Unicode 字符串。

新接受事务同时写入：Run、receipt/请求摘要、grant consumption、REQUEST_ACCEPTED event。`run_id`、phase_attempt_id 和 attempt_no 在此分配，早于 Fake 文件副作用。SQLite 有 namespace/key、Job/attempt、grant consumption、project/run event sequence 等唯一约束和外键。

真正 Retry 需要新 Plan、新 Grant、新 key，创建新 Run，保留 retry_of；目前仅接受同 Project/Job、FINISHED 且无待对账状态的前序 Run。不自动重试 BLOCKED 或未完成 Run。旧 receipt、Run、validation 保留。

## TEST_ONLY 授权与真实路径不可达

签发夹具 `FakeGrantFixture` 仅在 [tests/execution_helpers.py](../../../tests/execution_helpers.py)。它登记精确绑定的测试 grant；应用模块只有验证器，没有公开 mint/approve。普通请求仅传 grant_id。复制 Project、关闭 owner session 后重新申请 writer、伪造 authority 或越界使用 grant 都被拒绝。

创建实验时 owner/authority 在本进程登记，多个服务 facade 共享它；关闭实验 writer session 后只允许只读重开。没有“测试授权升级为真实授权”的入口。相同 OS 用户仍可修改 Python/DB；这不是防任意 shell 权限对手的强安全边界。

新包仅导入自身与少量标准库。`ExecutionService` 内部固定构造 FakeBackend，无 Backend 参数、动态 import、插件入口、任意 callable 或真实执行开关。FakeBackend 只调用路径/文件 I/O 和 fsync，不包含 subprocess 或 Solver 命令。AST 依赖检查与运行时启动 trap 都已通过；并非靠 monkeypatch 真实 Runner 来模拟安全。

## 存储、证据与故障

新目录格式是 `experiment.json + execution.sqlite3 + runtime/fake_runs/<run_id>/result.json`。`format_id=abqjobpilot-agent-first-experiment, schema_version=1` 仅属于实验库，不改现有版本常量。创建拒绝已有目录，不生成 legacy project.json、project.db、queue.json 或 live_status.json，不接管任何旧 writer。

SQLite DELETE journal、synchronous FULL；只读入口 `mode=ro` + query_only，仅读取已存在文件/支持格式，看到 WAL/SHM/journal 就返回维护错误。sidecar 检查不跟随链接。不初始化、不迁移、不修复。只读重开要求显式保留的 ProjectContext；尚无 manifest 自动发现、移动/复制后重定位或导入接口，复制目录直接拒绝执行。

Run 维度分别保存 queue_state、execution、backend_outcome、process_observation、exit_verification、solver_conclusion、artifact_validation、reconciliation。Fake 的 process/exit 为 NOT_APPLICABLE，Solver 始终 NOT_RUN。Fake COMPLETED 可以同时拥有 INVALID/UNKNOWN artifact；Validation scope 始终 simulation。

Fake 输出后记录 FAKE_COMPLETED/VALIDATING；独立 validator 再检查。ArtifactObservation、ValidationRecord、Run 终态、事件及槽释放在同一个终态事务。Observation 带 Run/phase、文件身份、大小、mtime、SHA-256、来源和绑定判断；不是仅记录一个路径就声称本次验证成功。

| 实际测试的失败点 | 行为 |
| --- | --- |
| 接受事务提交前 | receipt/Run/事件/消费全部回滚，无 Fake 副作用 |
| 接受已提交但应答/commit acknowledgement 丢失 | 返回 ACCEPTANCE_UNKNOWN；按原 key 查询得到原 receipt，不换 key 盲重发 |
| 领取事务提交前 | Run 仍 PENDING，slot 空，未执行 Fake |
| START_INTENT 已提交、Fake 前 | 留下可识别的不确定 Run，不重新派发 |
| Fake 文件已产生、观察/终态事务失败 | 保留文件；记录 RECONCILIATION_REQUIRED，保持槽占用；重发/重复 execute 不再次写文件 |
| 连“不确定状态”事务也失败 | 已持久 START_INTENT/VALIDATING 仍阻止重复执行；只读视图派生需要对账，不偷偷修复 |
| 终态已提交、最终查询/响应失败 | 查询原 Run 得到终态，重放不执行第二次 |

SQLite 回滚不能撤销文件副作用，不承诺 exactly-once。查询对未结束的 START_INTENT/VALIDATING 保守返回 `reconciliation_requirement`，该派生字段不写库，也不假称真实进程观察。Run 002 不提供释放未知槽或对账修复接口。

## 相对设计的必要实现澄清

- 按本次用户要求允许同进程多个服务/store facade，共享一个创建 session；原设计“拒绝重复 owner”落实为拒绝无该 session 的 writer，而非拒绝第二个 facade。
- 单槽明确为每实验存储，繁忙时返回 SLOT_BUSY，调用方可在槽正常释放后显式调用仍为 PENDING 的 Run；不实现后台调度器。
- Job/Plan 等采用不可变 canonical JSON 值对象；Run/Event/Observation/Validation 以有明确定义字段的持久 JSON 文档及 SQL 约束保存，没有新增外部协议 DTO 层。
- 只读查询借鉴旧边界，未导入旧 utils/config/Repository；事务与文件 writer 是新实验包的小实现。旧工程文件仍保持外部引用，Fake 输入只在临时根。

未实现 Supervisor、IPC、GUI/MCP/CLI 适配、真实 Backend、可信真实批准 UI、跨进程恢复、跨 Project 输出预留、生产迁移与发布。后续需要这些能力时单独施工，不在本轮追加。
