# Run 001R — 当前 Develop 架构复核

依据：[BASELINE.md](BASELINE.md) 中的 `Develop@af3fd79667ef70693d616f7f8cfba9c5a7f5b21b`。本文所有“已实现”指静态代码存在；未在本轮启动 GUI、Runner、Solver 或打开数据。新架构和 Run 002 均未实现。

## 实际调用链

```text
gui_app.AbqJobPilotApp.__init__ -> QueueRunner()
  start_queue -> 用户确认 -> self.runner.start
    -> RunnerOwnership(config.RUNTIME_DIR).acquire
    -> 进程内 daemon Thread(_run_loop)
    -> load_queue -> _next_queued_job -> run_next_job
    -> build_abaqus_*_command -> load_settings -> config.SETTINGS_FILE
    -> _run_command -> subprocess.Popen(command, cwd=job.work_dir)
    -> poll launcher + process identity / phase evidence
    -> classify_datacheck_attempt / classify_final_verdict
    -> update_job + live status + report -> history projection

GUI open_project -> ProjectManager.open_project -> register_project -> _remember(Recent)
  -> _activate_project -> config.use_runtime_dir
  -> refresh_all -> _sync_project_history_if_changed -> sync_history_from_runtime
  -> load_queue -> init_storage

API AbqJobPilotClient.for_project -> ProjectAutomationSurface.resolve
  -> validate_project/load_project_info -> runtime-scoped client（不改全局 Runtime）
  -> preflight/enqueue(dry_run=True) 或 queue-only enqueue
CLI -> AbqJobPilotClient；MCP -> ReadOnlyTools -> 显式 Project client / 只读历史查询
  （当前公共 API 不启动 Runner；当前五个 MCP 工具不入队、不批准执行）
```

证据：[gui_app.py](../../../abqjobpilot/gui_app.py) `__init__` L247、`_activate_project` L500、`refresh_all` L935、`start_queue` L2154；[runner_core.py](../../../abqjobpilot/runner_core.py) `QueueRunner.start` L379、`_run_loop` L410、`run_next_job` L261、`_run_command` L193；[api/client.py](../../../abqjobpilot/api/client.py) `for_project` L40、`enqueue` L173；[mcp/server.py](../../../abqjobpilot/mcp/server.py) `build_server`。

## 写入路径和数据权威

| 入口 / 函数 | 读取依赖 | 写入 / 时机 | 当前权威和限制 |
| --- | --- | --- | --- |
| `queue_store.load_queue -> init_storage` | 全局 Runtime / queue | 创建 Runtime/reports、`.queue.lock`；缺失时初始化 queue/live | 名为 load 仍会写。审计不能调用 |
| `read_queue(runtime, strict=True)` | 指定 queue | 无应用写入；缺文件返回空，严格模式解析损坏 JSON 会失败 | 可复用读取方法；“缺文件”和“空队列”需新接口进一步区分 |
| `enqueue_record / save_queue / update_job` | queue；enqueue 检查 owner/output | queue 读改写在 `queue_transaction` 下，`write_json` 临时文件+fsync+replace | queue 是旧 Runner 控制状态；不是完整事件账本 |
| `settings_store.load_settings` | 全局 `SETTINGS_FILE` | `ensure_runtime_dirs` 创建目录 | 不是纯查询 |
| `load_settings_for_runtime(runtime)` | 指定 settings + 默认值 | 不创建目录、不保存 | 宽容合并视图；不是严格“已持久化值”证明 |
| `save_settings` / `BasicSettingsDialog.save` | 默认值+表单，全局设置路径 | 写 settings；再写用户 app settings 的默认 Project 根；可改 queued resources | 无显式 Runtime 参数、无回读比较；多个文件不是事务 |
| `ProjectManager.create/open/register` | manifest、queue、Recent | create 写 manifest/runtime；open/register 调 `_remember` 更新 Recent | `validate_project/load_project_info` 可只读校验；不能以 open 替代 |
| `runner_core._write_live_status` | 当前 job/进程观察 | 写全局 `live_status.json`；OSError 被容错 | 临时观察通道，不是 durable Run 或完整进程终止证明 |
| `_run_command` | 固定于 job 的 work_dir；执行时重新读 Settings 生成命令 | 在 work_dir 追加日志；Popen 可写外部 Solver 输出；Runtime 内保存 phase evidence | launcher 轮询周期内采样，不保证完整进程树 |
| `run_evidence.save_phase_evidence` | queue_id、phase、当前 evidence | `reports/process_evidence/<queue_id>.json` 的 phase 快照 | 保留各 phase 最近证据；非不可变事件历史 |
| `_write_report` | job、reports manifest | terminal report、manifest，然后尝试 `sync_history_from_runtime`；失败可写 projection_error | report 是终态历史输入；与 queue/live/DB 分别写，无跨文件原子提交 |
| GUI `refresh_all/_sync_project_history_if_changed`、查看历史 | queue/reports stat；Project | 触发 JSON→SQLite 历史投影；历史视图还使用默认 Repository | GUI 刷新不是只读动作 |
| `ProjectHistoryRepository._connection` 默认 `read_only=False` | project.db | 即使只列历史也先 `initialize_database` | 默认 Repository 可建库/schema，不能用于无写入查询 |
| `ProjectAutomationSurface` 历史查询 | `ProjectHistoryRepository(..., read_only=True)` | 使用 `mode=ro` 及 schema 检查，不调用初始化 | 可复用边界；本轮未打开真实库，未验证活跃 WAL 下文件副作用 |
| `recovery_workflow.apply_approved_recovery` | plan/fingerprint、进程、queue/live/DB | Prepared audit→queue UNKNOWN_INTERRUPTED→live→history→audit outcome | 显式 GUI 批准才应用；可能部分失败；不启动、不终止 Solver |

相关文件：[queue_store.py](../../../abqjobpilot/queue_store.py) `read_queue` L52、`init_storage` L62、`load_queue` L73、`enqueue_record` L210；[settings_store.py](../../../abqjobpilot/settings_store.py) 全部三个公开读写函数；[utils.py](../../../abqjobpilot/utils.py) `ensure_runtime_dirs/read_json/write_json`；[project/manager.py](../../../abqjobpilot/project/manager.py) `load_project_info/validate_project/open_project/_remember`；[database/repository.py](../../../abqjobpilot/database/repository.py) `_connection` L54；[database/connection.py](../../../abqjobpilot/database/connection.py) `open_connection/ensure_project_database`；[recovery_workflow.py](../../../abqjobpilot/recovery_workflow.py) `apply_approved_recovery` L254。

旧格式的单向关系：queue 控制执行；live 显示当前观察；reports 提供终态历史；project.db 投影逻辑 Job、Run、Artifact 索引。[database/reconciliation.py](../../../abqjobpilot/database/reconciliation.py)::`sync_history_from_runtime` 合并 queue 与 reports，同 queue_id 的终态 report 可覆盖非终态 queue **作为投影输入**，不反写 queue。瞬时状态可能未投影；DB Run 并不保证在 Popen 前创建。不能把四处数据合称一个事务事实源。

## 关键判断：已实现、限制与后续设计

| 项 | 当前已经实现 / 证据 | 当前限制（静态确认，除特别标记） | 目标设计 / 未来实机边界 |
| --- | --- | --- | --- |
| GUI 生命周期 | `QueueRunner.start` 获取 Runtime owner 锁再启动 GUI 进程内线程；GUI 限制运行时切 Project | 无独立 Supervisor；GUI/进程结束不等于 Solver 停止 | 抽离独立执行所有者；Run 002 先验证内部契约，不声称断线监督 |
| 全局 Runtime | `config.use_runtime_dir` 改四个全局路径；Runner 的 queue/live/report/settings 都经这些路径 | Runner 与所持 owner lock 没有不可变 ProjectContext 贯穿绑定 | 显式 context/config snapshot；旧 Runner 暂保留 |
| Settings 与预览 | `load_settings_for_runtime` 只读指定路径；GUI/Runner 用 `load_settings`；API `_abaqus_cmd_prefix_preview` L403 直接用 `config.ABAQUS_CMD` | `read_json` 遇损坏/读取失败回默认；保存只返回待写 merged 值；无严格持久化查询、显式保存绑定或保存后校验。预览与执行配置可不同 | 固定计划生成一次配置/动作快照；严格读取器后续另做；不沿用旧 main 修复结论 |
| Project 绑定 | `for_project` 返回显式 runtime client；`resolve` 路径分支只 validate，不 open/register | ID/name 分支读 Recent；提供 path 时不同时核对额外 project_id；绑定 Runtime 不等于完整计划/身份约束 | 新执行接口要求 root+身份一致，绝不猜 Recent；旧门面后续适配 |
| 身份 | `build_queue_record` 产生 queue ID；repository `_logical_key/_get_or_create_job` 建逻辑 Job，`_create_run` 按 queue_id 幂等投影 Run | legacy `enqueue/status/locate_outputs.job_id` 是 queue_id；Project `show_job.job_id` 才是逻辑 ID；历史 Run 可晚于执行 | 新协议三种 ID 固定含义；compat 明示旧别名；新 Run 先持久化再执行 |
| Datacheck | `parsers.classify_datacheck_attempt` L141 检查 fatal、非零退出及 completion | 末尾兜底返回 PASS，空文本且 return_code 为 0/None 也可放行 | 新 validator 对缺证据返回 UNKNOWN；真实 completion 证据政策需实机验收 |
| Launcher / 子进程 | `_run_command` 持久化 launcher、后代及退出观察；`verify_launch_evidence` 保守区分孤儿/未知 | launcher poll 结束后只验证子进程一次，返回 launcher code；`run_next_job` 未以 `verify_launch_evidence` 的退出门禁阻止下一阶段 | Supervisor 必须观察到所需退出证据才能推进；真实 Abaqus 进程树/漏采需未来验证 |
| 输出冲突 | `require_output_admission` 查同 Runtime 中断记录、匹配 live identity 和 `.lck`；同 Runtime 队列写串行 | 没有主机跨 Project 输出预留；入队预检不是启动瞬间排他保护；两个 Runtime 可独立拥有 runner | 后续 Host Coordinator 区分 Project 锁、主机单槽、输出身份；Run 002 仅自己临时 Project/run 输出目录 |
| Process Identity | `capture_identity/verify_identity` 验证 PID+创建时间+路径；`observe_descendants` 记录父子关系；`verify_launch_evidence` 无候选子进程则不确认全部退出 | 仅已观察身份；名称只表示 candidate；快进程、权限、重父化/未观察后代仍不确定 | 复用观察器，不能将 identity 验证当结果验证；真实 Windows/Abaqus 环境另验 |
| Artifact attempt 归属 | `repository._add_or_update_artifact` 外键 run_id；`sync_records` 对路径取当前 stat；evidence 通过 queue_id 关联历史 Run | 数据库关联不证明文件由该 attempt 产生；同路径后续覆盖会污染历史观察；没有 immutable before/after/digest 验证账本 | 新 ArtifactObservation + ValidationRecord，run/phase/digest/provenance；外部工程文件保持引用 |
| 结果分类 | `latest_attempt_block` 限定有标记的 log；`classify_final_verdict` 检查成功/错误；MCP 输出明确 `odb_validity_verified=False` | 无 log 标记时读全文；STA/MSG/DAT 仍是整个现存文件；旧成功文本有误归属风险，未在本轮构造运行复现 | attempt 绑定、进程退出、Solver 判定、Artifact validation 分离；Fake 完成永远不是 Solver PASS |
| 恢复 | `assess_runtime` 汇总只读观察；`build_recovery_plan` 绑定文件/DB-WAL/进程指纹；GUI 一次性 token 与应用前复核 | assess 包含 OS owner lock probe，非单纯 JSON load；apply 多文件可能部分失败；恢复批准不是执行许可 | 保留保守 UNKNOWN/对账策略；新授权系统独立设计，禁止照搬 recovery token 当 Solver grant |

进程/证据文件：[process_identity.py](../../../abqjobpilot/process_identity.py) `capture_identity` L97、`verify_identity` L111、`observe_descendants` L158、`verify_launch_evidence` L236；[run_evidence.py](../../../abqjobpilot/run_evidence.py) `save_phase_evidence/read_process_evidence`；[runtime_coordination.py](../../../abqjobpilot/runtime_coordination.py) `queue_transaction` L80、`RunnerOwnership` L157、`require_output_admission` L220；[parsers.py](../../../abqjobpilot/parsers.py) `latest_attempt_block/classify_datacheck_attempt/classify_final_verdict`；[recovery_assessment.py](../../../abqjobpilot/recovery_assessment.py)::`assess_runtime`。

## 保留、抽离、重新设计

| 处理 | 模块 / 做法 | 首个切片使用方式 |
| --- | --- | --- |
| 保留 | Project-owned Data、外部 INP/CAE/ODB 引用；旧 GUI/Runner/JSON/history 路径 | Run 002 不接管、不迁移、不双写 |
| 保留并后续抽离 | Abaqus command resource 规则、Windows 启动选项、Process Identity、锁、native phase evidence、保守 recovery | 作为真实 Backend/Supervisor 的后续素材；Run 002 不导入执行旧 Runner |
| 复用读取设计 | `for_project`、`load_project_info/validate_project`、`read_queue(strict=True)`、`ProjectHistoryRepository(read_only=True)`、MCP typed scope | 复用边界与测试思路；实验存储独立格式，不强行调用 legacy initializer |
| 重新设计 | ProjectContext、Plan/Grant、幂等 receipt、先建 Run、事务事件、验证记录、attempt 证据与跨 Project 输出预留 | 前七项进入 Run 002 的 Fake 最小实现；跨 Project/独立进程留后续 |
| 后续适配 | GUI/CLI/MCP/外部 SDK | 统一调用服务；本轮和 Run 002 均不添加真实执行入口 |

## 文档与测试证据边界

1. [PROJECT_DATABASE 文档](../../ABQJOBPILOT_PROJECT_DATABASE.md) 的“independent processes writing queue.json are not coordinated”是 P2 历史限制，当前 `queue_transaction` 已有跨进程协调；不能继续用该句概括当前 Dev。仍不代表跨 Project 输出协调。
2. [PROCESS_IDENTITY 文档](../../ABQJOBPILOT_PROCESS_IDENTITY.md) 描述 live evidence 可覆盖；当前另有 `save_phase_evidence` 与 Run 006 测试保留各 phase 快照。仍不是 immutable 事件账本。
3. 原 Agent-first 草案是旧 main 参照，新版不把 Settings 修复当成当前实现；详见 [ADR 变更表](ADR_AND_CONTRACTS.md)。本轮不修改历史文档。
4. 已静态阅读/定位 `test_runner_core.py`、`test_run006_native_evidence.py`、`test_project_database.py`、`test_mcp_readonly.py`、`test_a4_project_automation.py`、`test_process_identity.py`、`test_runtime_coordination.py` 和 recovery 测试的相关夹具/测试点。`test_run006_native_evidence` 使用临时 Project、显式 Recent、Fake Popen 等；不证明真实 Solver 已验收。
5. `test_runner_core.py` 命令构造测试通过实际 `load_settings`，没有自身完整 Runtime 隔离；旧测试文件还出现范围外路径文字。本轮只读取 Dev 内测试源码，不访问这些路径、不执行测试。后续不能因为测试名含 command/fake 就直接批量运行。
6. 部分 process/coordination 测试会启动真实的测试 Python 子进程，和 Fake Backend 无进程切片不同。后续按范围挑选并检查夹具，本轮无测试运行结果。

尚待验证的真实进程行为、输入固定、跨 Project 输出锁和实际结果检查属于后续验收门禁；不阻塞纯 Fake 内部契约施工。未发现要求重新访问 Stable 才能决定 Run 002 的事实缺口。
