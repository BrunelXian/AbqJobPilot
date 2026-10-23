# Run 012：现有 GUI 的独立服务查看模式

## 基线与范围

2026-10-23，`D:\Projects\abqjobpilot_dev`，`Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，版本 `0.3.0.dev0`，无冲突。前轮实验包、示例、测试、报告原来即为未跟踪成果，没有清理或要求提交。开始时 tracked diff 为空。

读取 Dev AGENTS、环境登记、Run 001R～008 的相关设计/接口和交接，以及最新 Run 011 `result_review_001/FINAL_SUMMARY.md`。没有额外发现适用于本目录的上级 AGENTS 或独立编号协议；沿用 agent_first 的独立 Run 目录、不覆盖旧证据惯例。

使用登记的 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python 3.12.10、Tk 8.6、pytest 9.1.0；没有安装依赖。测试 OS 为 Windows，真实 Tk 窗口和固定 Python 进程均已运行。Run 010/011 实机实验不参与本演示。

`BASELINE_FILES.json` 记录 345 个既有源码/测试/受保护材料的初始摘要，其中 221 个位于 Run 010/011。`PRESERVATION_CHECK.json` 记录收尾复核。新增副本 `before/` 仅保存本轮改动前的四个接入源文件；历史报告没有重写。

## 接入判断与实际改动

| 接缝 | 实际复用 | 本轮必要改动 |
|---|---|---|
| GUI | `gui_app.AbqJobPilotApp`、样式、状态灯、双日志区、表格/滚动条、窗口关闭 | 构造器增加显式 execution_connection / request_key 模式；旧依赖移动到 `gui_legacy.py`，只在旧工作区加载。默认旧工作区行为保留。 |
| GUI 适配 | `execution.client.FakeClient` | 新 `execution_gui.ExecutionView/Reader`；没有创建第二套 Runner。后台线程只读公共 API，Tk 线程只显示。 |
| 服务与所有权 | `FakeSupervisor.serve/_work`、`acquire_supervisor_store`、OS owner lock、每存储单槽 | 不改变领取、授权、暂停、恢复、对账或退出证据事务。 |
| 固定计划/授权 | `ExecutionService.prepare`、`ProcessFixtureConfig.current`、`issue_process_execution` | 可信演示操作者预置一个 result_wait Plan 和精确 TEST_ONLY Grant；普通提交客户端只消费现有公开接口。 |
| 固定进程 | 原 launcher/worker 与 transport 四角色，OS retained-handle 退出 | `process_fixture.Progress` 添加固定枚举进度记录；执行对象摘要自然变化，新建 Plan 绑定新摘要，旧 Plan 不被静默重建。 |
| 公共日志 | 原认证、Project/owner 绑定、帧限额 | `FakeClient.progress` → Supervisor 白名单 operation `progress` → `progress_log.read_progress`。唯一新 RPC，只读固定 Run 目录内的固定文件。 |
| 产品入口 | 原公共客户端、Tk 应用与 Supervisor | `examples/agent_first/dev_gui_demo.py` 和四个固定 `.vbs` 入口；本地显式开发演示，不是系统服务。 |

旧 GUI 模式仍有原 QueueRunner；新的显式服务模式不导入旧 config、ProjectManager、Runner、Settings 或数据库模块。测试实际设置了导入/进程创建/SQLite 陷阱，证实该分支没有进入旧路径。不是通过把旧队列或 history 填成服务状态来显示。

## 公共读取、线程和证据边界

GUI 的调用链：显式私有连接文件 → `FakeClient.health/receipt/run/validations/events/progress/dispatch_gate` → 原认证 IPC → 原查询存储。没有 submit、approve、resume、stop、验证写入、SQL、进程探测或文件产物读取。

- 连接文件至多 64 KiB，必须绝对本地路径且无重解析点。首次连接绑定 Project/instance/context；之后仅允许同一上下文的 owner 更换。变成其他 Project 时拒绝，不自动重新绑定。
- 一个非 daemon 读取线程，最新视图队列长度 1；查询之间检查停止信号。约 300 ms 轮询，Tk 80 ms 消费快照。所有网络操作沿用现有 2 s I/O 期限和帧限额；关闭窗口后最多等当前有界网络操作收尾，不发控制请求。
- 失联时显示“连接中断 / 缓存不是实时状态”、稳定错误码及最后成功读取时间。不能把传输失败显示为任务失败、已取消或可安全重试。
- 项目状态、事件、进度为多次有界查询的历史视图，不宣称共享原子快照；显示各自已记录状态和最后读取时间。没有在 GUI 读取中重新探测进程或运行 validator。
- 运行中的 `START_INTENT` 是既有执行核心状态；worker 的 WAITING 进度不是退出证据。历史 process_exits、exit_verification、backend_outcome、artifact_validation、Solver NOT_RUN 分行显示。
- 非当前 owner 的未完成 Run 显示服务给出的 reconciliation_requirement；没有修改该 Run 的存储投影。重启 owner 后 PAUSED 和不确定性保持。

## 只读进度协议

请求：`client.progress(run_id, after_sequence=0, limit=64)`。服务不接受路径、命令或任意参数，要求当前实例的已接受 ProcessFixture Run。

固定来源：`<explicit runtime>/process_runs/<run_id>/progress.jsonl`。worker 以排他新文件方式打开，直接写文件，不用 GUI 管道。每条绑定 Project instance、Run、phase attempt、Plan digest，并携带连续序号、观察时间及固定事件枚举：WORKER_READY / RESULT_WRITTEN / WAITING / WORKER_RETURNING。

限额：文件 65,536 bytes、最多 128 行、每行 1,024 bytes、每页最多 64 行；worker WAITING 最快每 0.5 s 一条。返回白名单只有 sequence/event/observed_at 和所属 Run/attempt/instance、读取时间、游标、完整前缀行数。GUI 保留最多 128 条进度、64 条已读业务事件。

读取检查路径边界/重解析点、普通文件、前后文件身份和未缩短，读取固定大小的完整换行前缀。末行正在追加时不当作损坏，后续轮询再读；不复制产物、不注册 Artifact、不追加事件、不更新 revision。文件不存在明确 NOT_RECORDED；超限 LIMIT_EXCEEDED，错误游标 CURSOR_INVALID，归属冲突 EVIDENCE_IDENTITY_MISMATCH，格式/读取失败明确拒绝，不作空成功。

日志是固定 worker 自报，不能替代 OS 退出、Solver 或 Artifact 验证。输出文件同用户篡改不属于本机制能隔离的威胁模型。

## 启动与生命周期契约

可信操作 `start` 新建明确临时实例并预置计划/授权，启动既有 Supervisor；`submit` 使用公共客户端提交该固定请求；`gui` 只连接；`stop` 写该演示自身的显式停止请求。不存在 GUI 自动启动服务、批准、恢复或重新提交。

独立 owner 使用固定普通 Python 创建方式、`shell=False`、`close_fds=True`、CREATE_NO_WINDOW、普通文件 stdout/stderr。没有 breakaway、Job 修改、服务、计划任务或新的 IPC stop。worker 不继承连接/授权秘密和 DB/owner 句柄。

演示 worker 在 result_wait 阶段产生真实进程生命周期和持续日志；可信操作者线程在进度文件出现 45 s 后释放固定测试屏障，worker 自行完成。它不是 GUI 控制操作。最长夹具预算 60 s；owner 演示会话预算 900 s，或由显式 stop 提前请求正常结束。owner 等执行工作返回，未使用 terminate/kill。停止后清除本实例 private/bootstrap、setup、offer、connection 四个文件，保留公开证据。GUI 关闭不做这些清理。

实际验证了完整 GUI 进程、venv 启动器以及服务启动命令退出后的独立运行。没有将 Windows 注销、重启、终端关闭、任意宿主 Job 层级或真实 Abaqus 生命周期列为已验收。资源保护仍仅每实验存储一槽。

## 变更与兼容说明

无 Schema 或版本变化。没有改变原 Plan 摘要算法、Grant 匹配、提交/领取事务、重启 PAUSED、管理授权或对账语义。没有使用 Run 011 外部真实实验数据构造原生 Run。

`tests/test_execution_isolation.py` 只给新只读 progress_log 增加 `os.fstat` 允许项，保留所有原 Popen/旧模块/默认目录陷阱。旧 GUI 延迟导入的 mock.patch 恢复兼容问题经原测试发现并修复，没有降低旧断言。
