# Run 001R — 分层验收与 Run 002 施工方案

依据：[当前架构复核](ARCHITECTURE_REVIEW.md)、[冻结 ADR](ADR_AND_CONTRACTS.md)。本文是未来施工与验收清单，**本轮没有实现或运行下列新增验收**。历史测试只作复用参考，不填充本表 PASS。

## A：Run 002 最小可执行切片

目标：无 GUI、单进程 ExecutionService、一个明确隔离临时 Project、一个 Fake 执行槽，完成固定计划→测试批准→幂等提交→Fake→持久化 Run/Event/Validation→只读查询。一个服务可接受两个客户端调用；不是两个执行所有者。独立 Supervisor、IPC、重连监督和跨进程恢复不属于本层。

测试根由 `tmp_path`/TemporaryDirectory 显式传入。Project、Runtime、Recent 哨兵、fixture inputs、DB/journal/产物均在该根内；输入仅 TXT，产物仅 JSON/TXT。不调用旧 Runner，不生成可执行 Abaqus 输入或有效 ODB。

| ID | 场景 / 操作 | 必须观察到的结果与证据 |
| --- | --- | --- |
| R2-01 | 纯内部 API 创建实验 Project、prepare、fixture grant、submit、execute_pending、query | 无 GUI 导入依赖；receipt 已持久化 run_id 后才有 Fake 副作用；Run、事件与 Validation 可查询，solver=NOT_RUN |
| R2-02 | 同 namespace/key/内容重复 submit，完成前后各重发；重复 execute_pending | receipt/run_id/attempt_no 相同；Fake 副作用计数=1；接收事件和授权消耗仅一份 |
| R2-03 | 同 key 改 plan_id/digest、grant_id 或 retry_of | 结构化 IDEMPOTENCY_CONFLICT；原 receipt/Run/事件不变，无额外 Fake 调用 |
| R2-04 | 两客户端在同服务并发提交相同请求及两个不同请求 | 相同请求唯一 Run；不同请求串行 Fake（最大活跃数1）；唯一约束及事务无丢事件，不宣称跨进程 owner 能力 |
| R2-05 | context 的 Project ID/instance/root/manifest 与 Plan 不一致 | PROJECT_IDENTITY_MISMATCH；不接受、不启动，不能从 Recent 或 GUI 纠正到别的 Project |
| R2-06 | prepare 后改输入内容（包括保持大小）或 config_revision/values；提交后 dispatch 前再改变 | 接受前 PLAN_STALE，无 Run；接受后 receipt 保持 ACCEPTED、Run BLOCKED、有失败事件且 Fake 计数0。不能执行时偷偷加载新配置 |
| R2-07 | 无 grant、过期、未登记、自报 approved/allow_solver_submit、错误 Project/Plan/Job/revision、越界 CPU/GPU/输出范围 | 分别返回契约错误/未知字段拒绝；无 Fake 调用；客户端不能签发可信 grant |
| R2-08 | 新 Job 或 revision 试图复用旧计划/授权；复制实验目录后申请执行 | scope/instance/authority 拒绝；复制的授权无执行效力。只读查看历史不等于恢复执行许可 |
| R2-09 | 同 key 在授权到期或输入改变后再次重发已接受请求 | 返回原 receipt，不消耗第二次、不再 dispatch；query 能看到已接受 Run 当前状态 |
| R2-10 | 正常完成后关闭服务/Store，以只读入口重新打开 | 原 receipt、Run、event 序列、observation、Validation 及引用可查；不创建 owner、不自动执行 |
| R2-11 | Fake 已完成但产物缺失、内容损坏、run/phase/plan 不匹配；放入旧成功文本或旧产物 | backend_outcome 可为 COMPLETED；artifact=INVALID/UNKNOWN，validation scope=simulation；solver 不得 PASS；不得采用旧 log 成功字样 |
| R2-12 | 接收事务中、START_INTENT 后、证据写入时、终态事务中注入失败 | 接受原子性；Fake 不能在接受前发生；不假报终态 PASS；原 Run/event 不被删除；不确定处禁止自动第二次副作用。仅逻辑故障注入，不声称 kill/restart 验收 |
| R2-13 | 对已有实验库反复查询；对缺库、损坏/未来 schema、WAL/hot journal 情况查询 | 文件清单/摘要不变；缺库不创建；不支持/需维护时明确错误；不初始化、不迁移、不修复，不使用默认 writable Repository |
| R2-14 | 测试根隔离和路径逃逸、junction/reparse、UNC、任意 executable/backend 请求 | 越界/不支持请求在文件读写前拒绝；默认 Project/Runtime/Recent 访问 trap 为零；没有 Popen/os.system/旧 Runner 调用；所有输出仅测试根 |
| R2-15 | 合法终态的真正 Retry 与非法 retry_of | 新 key/Plan/Grant→新 Run、attempt_no+1、retry_of 保留；旧 Run/证据不变；跨 Job/Project、不存在或待对账引用拒绝 |
| R2-16 | canonicalization 改字段顺序、Unicode 字符串、bool/int、未知字段；事件分页 | 同合法语义摘要稳定；不同语义不误判重放；非法类型拒绝；event_id 去重、sequence 无重复，receipt 接受序列可定位 |

必须给出机器可核对的真实启动不可达证据：新执行包依赖图只通向 domain/stdlib SQLite/Fake；不存在调用旧 `runner_core`、GUI、队列写入或真实 Backend 的分支，也不接受任意命令或动态插件。测试用启动 trap 拦截 `subprocess.Popen/run`、`os.system` 等可能入口，并检查 import/调用边界；trap 是额外保障，不能用 monkeypatch 包住真实 Runner 再宣称新服务天然隔离。

路径隔离证据不通过扫描生产目录获得：用显式路径、默认路径访问即失败的替身、临时根 inventory 和静态依赖审查证明。不要为了比对“不变”而访问范围外 Stable 或真实 Recent。查询 inventory 可含 hash、size、mtime_ns 与新文件检测；不将 atime 当需要保持不变的应用数据。

## 建议模块与实施顺序

以下路径为拟新增项，尚不存在，不是本轮源代码修改清单。优先把实现限制在一个独立实验包，不改变旧 API 或 schema。

| 建议位置 | 最小职责 | 必须避免 |
| --- | --- | --- |
| `abqjobpilot/execution/__init__.py` | 仅导出内部实验契约，标记 experimental | import GUI/Runner/config 或自动注册生产服务 |
| `execution/models.py` | immutable context/spec/plan/grant/receipt/state/error DTO，明确类型/版本 | 复用旧 JobSubmitResult 的 job_id 歧义 |
| `execution/planning.py` | canonical digest、fixture 依赖/配置快照、固定输出模板与校验 | 读取默认 Settings、任意 shell argv、解析真实 INP |
| `execution/store.py` | 显式创建新实验 Project/schema、事务、唯一约束、严格只读重开 | 旧 project.db、默认 Repository、隐式 ensure/migrate、legacy JSON 双写 |
| `execution/authorization.py` | 验证已登记 TEST_ONLY grant 的精确 scope/期限/消费；authority 匹配 | 公开 approve/mint、自报布尔、test→real 类型转换 |
| `execution/service.py` | submit、execute_pending、单进程单槽/唯一 owner、幂等、错误和查询 | IPC、自动恢复未完成 Run、调旧 QueueRunner |
| `execution/fake_backend.py` | 唯一可构造 Backend，固定 emit_fixture_result，无进程能力 | 启动命令、动态插件、写 INP/ODB/CAE/JNL |
| `execution/validation.py` | 独立 fake-result-v1 validator，observation/validation 分开 | 把文件存在、Fake completed 转成 Solver PASS |
| `tests/test_execution_contract.py`、`tests/test_execution_store.py`、`tests/test_execution_isolation.py` | 覆盖 R2-01～16；测试内提供 `FakeGrantFixture` | 使用 default Project/Recent、运行已有真实启动路径 |

实施顺序：领域与只读/创建 Store 分离→Plan 固定与测试 Grant→事务 submit/重放→显式 Fake dispatch/验证→隔离和故障验收→记录本次测试输出。没有必要同时做客户端 SDK、GUI 或服务进程。

存储可以用少量表完成契约，避免一次构建完整调度框架。Plan/配置、grant 登记及 consumption、receipt/幂等、Run、event、observation、validation 必须有清楚权威；表的物理拆分可按实现简化，但接受原子性和终态证据一致性不可省略。

## 现有可复用能力及测试范围

| 当前函数 / 测试 | 可复用什么 | 使用限制 |
| --- | --- | --- |
| `ProjectManager.validate_project/load_project_info`；`AbqJobPilotClient.for_project` | 显式 Project、导航/验证分离、client Runtime 绑定的模式 | 新实验格式不同，Run 002 不直接走 legacy create/open/Recent；不能把 resolve 的 Recent fallback 带入新接口 |
| `read_queue(runtime, strict=True)`；`ProjectHistoryRepository(read_only=True)` | 查询无初始化、严格/宽容区别的现成思路 | 实验存储另写只读入口；不能复用默认 writable `_connection` |
| `utils.write_json` | 原子 replace 单文件的方法 | 该模块导入 config，Run 002 应在新包实现很小的显式路径 writer或使用 stdlib，避免传递导入默认路径；不在本轮抽离它 |
| `process_identity.capture_identity/verify_identity/observe_descendants/verify_launch_evidence` | 后续原生身份观察与保守退出判断 | Run 002 无 OS 进程，状态 NOT_APPLICABLE，不调用这些函数伪装实机验收 |
| `runtime_coordination.queue_transaction/RunnerOwnership` | 后续 Runtime 协调参考；锁超时、失联保守处理 | 不是跨 Project 输出锁，不为了实验绑定旧 Runtime |
| `run_evidence.save_phase_evidence/read_process_evidence`、`recovery_workflow.build_recovery_plan` | phase 归属、引用 containment、快照指纹、失效计划复核 | 原 evidence 是可更新快照；recovery token 不作执行 grant |
| `test_a4_project_automation.py`、`test_mcp_readonly.py` | 显式 Recent、多个 Project、schema/ID、before/after inventory | 新切片测试不必启动 MCP；只借夹具模式 |
| `test_project_database.py` | 事务/唯一性/历史 attempt 与 artifact 外键 | 新实验库不是旧 history schema；不得拿 legacy schema 初始化器凑实现 |
| `test_run006_native_evidence.py`、`test_parsers.py` | phase evidence、旧日志/错误/警告分类的回归素材 | 不把 Fake Popen 通过当真实 Backend 验收；新切片不依赖旧 Runner |
| `test_process_identity.py`、`test_runtime_coordination.py`、`test_recovery_workflow.py` | 后续子进程退出、PID 重用、竞争、保守恢复测试 | 部分会启动测试 Python 进程；Run 002 不需运行这些整组 |

Run 002 默认只执行新增契约/存储/隔离测试及确有受影响理由、经静态确认隔离的既有非 Solver 测试；不机械跑全量。执行前重读环境登记，核验所选绝对 Python 解释器、版本及 pytest 等必要依赖，不安装共享依赖。未隔离的命令构造测试不得为了凑回归计数运行。本轮上述测试均未执行。

## B：完整模拟服务 MVP（后续）

此层才满足独立执行所有者、多个客户端与断线监督；仍用 Fake Backend/专门的测试进程，不运行 Abaqus。

| ID | 场景 | 验收要求 |
| --- | --- | --- |
| M-01 | 两个独立客户端进程同时提交/断线重发 | 同一 owner/单槽；幂等不随连接消失；独立 Supervisor 继续工作 |
| M-02 | 两 Project 同输出身份、路径大小写/别名、启动瞬间竞争 | Host Coordinator 在 dispatch 前排他预留；没有双启动；未知身份拒绝 |
| M-03 | launcher 退出而测试 child 活跃，或后代观察不全 | 不判完整退出、不进入下一 phase、不释放输出；记录 UNKNOWN/POSSIBLE_ORPHAN |
| M-04 | kill owner：接收提交前后、START_INTENT/Popen 前后、PID 记录前后 | 确认 receipt 原子性；不确定启动时不重复启动；epoch 拒绝旧 owner 写入 |
| M-05 | 证据写入后终态提交前崩溃；终态后响应/释放前崩溃 | 对账同 Run，不重跑；无虚假成功引用；预留释放有明确终止依据 |
| M-06 | GUI/MCP 断线、超时、取消等待、重连按游标查询 | Run 不因传输结束被取消；事件完整可重放；不隐式迁移/修复 |
| M-07 | pause/resume/cancel_pending/stop_after_current 的竞争及服务重启 | 控制持久化，取消与 dispatch 只有一个胜者；stop 等整个 Run 结束 |
| M-08 | 权威存储故障、证据失败、陈旧 lease、主机登记与 Project 不一致 | 保守门禁，保持诊断/对账信息；不释放不确定输出、不自动修复 |
| M-09 | 新客户端伪造授权、复制/导入 Project、旧 SDK 接新格式 | 可信批准域隔离、grant 不继承、旧格式明确拒绝；没有双 writer |

## C：真实 Abaqus 验收（后续独立授权）

| ID | 验收对象 | 所需实机证据 |
| --- | --- | --- |
| A-01 | 目标 Windows/Abaqus 安装与 launcher 行为 | 实际配置来源、argv/cwd、PID 创建时间/路径、候选 Solver lineage、所有必要退出观察 |
| A-02 | Datacheck | 必需完成标记与当前 attempt 绑定；空/截断日志、返回码0但无完成证据不放行 |
| A-03 | Full 求解与结果 | Solver 完成证据、warning/error 分类、ODB 专用检查及物理/数值验收的明确范围；不能靠存在性 |
| A-04 | 输入固定与外部引用 | include/子程序/重启依赖完整清单；计划后改动与 TOCTOU 处理；不默认复制工程文件 |
| A-05 | 输出身份与旧结果 | 跨 Project/别名/启动瞬间保护；旧成功日志/旧 ODB 不归入新 attempt；未知遗留进程不覆盖 |
| A-06 | 异常与恢复 | launcher early exit、孤儿、权限失败、磁盘/DB失败、客户端断线/owner 崩溃；保守对账不重复求解 |
| A-07 | 发布及控制能力 | GUI/CLI/MCP/SDK 一致性、显式迁移/回退、版本与兼容；suspend/resume/terminate 若计划宣称支持则另验，否则保持 unsupported |

真实验收使用未来明确授权的全新可丢弃 Project/工作目录与限制资源；本表不是运行许可。完整模拟层通过也不能替代此层。0.3.0 的发布必须按最终宣称范围提供证据并单独批准，不能用本轮设计 PASS 或 Run 002 Fake PASS 代替。
