# Run 003 — 独立 Fake 所有者与本地协议

范围：Windows 本机固定磁盘、单个全新临时实验 Project、每存储一个执行槽。应用仍为 0.3.0.dev0。真实 Backend、生产迁移、主机资源协调均未实现。

## 实际调用链与复用

```text
可信测试 harness：create_experiment -> 原 prepare -> 原 FakeGrantFixture -> close 本地 owner
显式 Python owner 进程：load_bootstrap -> acquire_supervisor_store -> FakeSupervisor.serve
  IPC handler -> ExecutionService.submit -> 原接受事务 -> 原 receipt
  独立 worker -> Store.pending_for_owner -> ExecutionService.execute_pending
             -> 原事务领取/slot -> FakeBackend.emit -> 原独立 validator -> 原终态事务
薄 Python client -> 短 TCP 连接 -> 白名单查询 / 提交
```

接受后 worker 轮询权威数据库，不依赖 handler 向内存队列投递成功，也不依赖客户端等待任务。Fake 在独立工作线程执行；查询线程与其只在短数据库事务上串行。没有另写调度状态机、幂等存储或结果验证器。

新增模块：[ownership.py](../../../abqjobpilot/execution/ownership.py)、[protocol.py](../../../abqjobpilot/execution/protocol.py)、[client.py](../../../abqjobpilot/execution/client.py)、[supervisor.py](../../../abqjobpilot/execution/supervisor.py)。必要修改：[store.py](../../../abqjobpilot/execution/store.py) 添加 owner 生命周期/派发查询；[service.py](../../../abqjobpilot/execution/service.py) 添加派发期间锁持有保护、暂停后的只读重放及 post-artifact 测试检查点。Fake/Plan/Grant/Validator 未改变。

## 所有权、身份与授权

- 新建实验仍显式返回创建进程的本地 owner session。多个 Store/service facade 共用此 session 与原数据库槽；每次事务检查 OS 锁句柄。`close` 在 Fake 执行期间拒绝释放 owner。
- Windows `msvcrt.locking(LK_NBLCK)` 对固定 `owner.lock` 偏移4096处的一字节持有排他锁；该字节在 EOF 之外，不写入数据，也不妨碍只读 inventory。句柄不继承；不删除锁文件、不按残留文件判断忙闲。仅支持 GetDriveTypeW=DRIVE_FIXED 的本机磁盘。
- `acquire_supervisor_store` 先取得 OS 锁，才打开可写实验库及更新 owner 元数据。另一个进程的旧 `ExperimentStore` 无本地 session；显式 owner 接管入口则被 OS 锁拒绝。PID、心跳、端口无响应均不是接管依据。
- owner 实例 ID 每次启动重新生成。记录 project_id、project_instance_id、context_digest、存储路径、PID、创建时间、虚拟环境解释器和实际映像路径。Windows venv 转发启动器与实际 Python PID 分别登记；owner 是实际 Python 进程。
- `owner.json` 与显式 endpoint 文件只是诊断/定位信息；每个请求和响应都校验实际 owner ID/Project/实例/context。服务不以文件中的 PID 自动杀进程或恢复工作。
- 测试 harness 在 owner 取得前用原计划/精确 TEST_ONLY fixture 登记授权。format2 的 meta 保存 fixture authority ID；私有 bootstrap 指定同一个预期 authority，启动时精确匹配。它不把复制目录变成合法新实例，原 context/root/inode/manifest 检查继续有效。authority ID 不是连接密码，也不是可自报的批准。
- 本地连接 credential 是单独的随机64位十六进制字符串（256 bit）；服务端 bootstrap 固定 client_namespace。普通请求无 namespace、mint、approve、prepare、Project 管理或文件操作字段。
- 私有 bootstrap 放在临时根内、可导出 Project 外，不放入业务事件/日志/交付证据。测试结束后删除 bootstrap 与每个进程的私有配置，再扫描剩余测试文件确认不含 credential。
- 同一 OS 用户任意 shell/修改数据库/读取私有文件的能力不在此边界的对抗保证内；没有实现跨用户强授权域或真实 Abaqus 批准。

## 格式与启动策略

仅新创建的实验使用 manifest/schema **2**，保留原业务表，meta 增加 authority_instance、supervisor_started。原格式1仍可只读查询；可写接管明确 UNSUPPORTED_FORMAT。旧生产 Project/数据库 schema、API/JSON schema 均未修改；没有迁移代码。

首次 Supervisor 启动要求尚未被 Supervisor 管理、且无已接受 Run 的新实验库。启动事务记录 supervisor_started=1。后续显式启动一律 query-only，包含正常退出后的重启；启动过程中后续 bind 失败也可能保守进入该状态。没有 unpause/恢复/对账解除入口。

重启能查询旧回执，并通过原 ExecutionService 的同一摘要检查规则只读重放原提交；不同内容仍冲突，新 key 返回 DISPATCH_PAUSED。旧 PENDING 仍为 PENDING；START_INTENT、VALIDATING 或已记录不确定状态的 Run 返回 RECONCILIATION_REQUIRED 派生视图，不反写修复。新 owner 不继承旧 Run 的执行权，槽不因失联而释放。

## 帧、边界和白名单

传输唯一为 `127.0.0.1 TCP`，协议 `af-local-json-v1`。每连接一个请求/响应，随后关闭。四字节 unsigned big-endian 长度 + UTF-8 JSON；完整读取循环拒绝 EOF 截断。请求最大65,536字节、响应最大262,144字节；拒绝重复 JSON key、非 UTF-8、浮点/NaN、未知字段及任意对象反序列化。

接收整帧有2秒总截止时间（不是每字节重置），发送超时2秒；客户端连接超时2秒。最多8个活跃请求线程，listen backlog=8；超额连接直接关闭，未完成帧到期释放容量。事件每页1～64条，project_sequence 游标。没有流式订阅。

请求 envelope（credential 不可导出，以下只是字段说明）：

```json
{"protocol":"af-local-json-v1","request_id":"wire_<transport-uuid>",
 "project_id":"<fixed>","project_instance_id":"<fixed>","context_digest":"<fixed>",
 "owner_id":"<current-owner>","credential":"<private-local-token>",
 "operation":"submit","arguments":{"request":{"...":"original fixed Run002 request"}}}
```

外层 request_id 仅用于本次通信关联；内层业务 idempotency_key 用于重连去重；返回 receipt.request_id 是原已接受请求的持久身份。这三者不能互换。服务端 namespace 与原 Project 实例及 operation 共同限定业务 key。

| 操作 | 参数 / 返回 | 副作用 |
| --- | --- | --- |
| health | 空对象；能力、owner 进程、派发开关、界限、诊断错误 | 无业务写入，不承诺磁盘健康检查 |
| submit | 只收原固定计划引用的 request，含 grant_id 和业务 key | 原事务接受；暂停 owner 仅只读重放 |
| receipt | idempotency_key | 原持久回执 |
| run | run_id | 状态维度及不确定派生视图 |
| events | after_sequence、limit | 有界追加事件页面 |
| validations | run_id | 原独立验证记录（simulation scope） |

响应统一包括协议/通信 ID/Project/owner、ok、result；错误 result 沿用 ExecutionError 结构。客户端提交在 EOF/超时后报告 ACCEPTANCE_UNKNOWN，提示查询/重放原业务 key；不会自动换 key、重新批准、启动 owner 或终止 Run。

## 故障与真实启动边界

- 接受 COMMIT 与 socket send 之间允许崩溃窗口；数据库原回执是权威。worker 从数据库发现接受记录，handler 丢失不撤销它。
- 原领取事务先持久 START_INTENT，再进行文件副作用。Fake JSON 已 fsync、终态事务未开始时 kill owner，数据库无法回滚该文件；重启不重复 Fake、不释放槽、不派发旧 PENDING。
- 文件/验证/存储异常沿用原不确定处理，worker 停止后续派发。维护 sidecar 返回 STORE_REQUIRES_MAINTENANCE；查询不删除 journal/WAL、不初始化或迁移。
- 应用实验包没有 subprocess、旧 Runner 或任意命令路径。Fake 仍只写固定 JSON，输入仅临时 TXT。Supervisor 入口承载 Python 服务，不从 RPC 启动其他进程。实际 Popen 仅在测试 harness 固定脚本/解释器/临时参数处。
- 原 Run002 启动/default-path/legacy-import trap 保留；每个测试子进程也安装这些 trap，且 Path IO 限制在显式临时根。只有父 harness 被允许创建测试 Python 进程。

## 可复现无 GUI 多进程验收

在 Dev，使用新临时根，避免 pytest 清理旧 basetemp：

```powershell
$run003Repeat = Join-Path ([IO.Path]::GetTempPath()) ('AbqJobPilot_Run003_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $run003Repeat | Out-Null
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest -p no:cacheprovider tests/test_fake_supervisor.py::test_independent_client_exit_owner_continues_and_reconnects tests/test_fake_supervisor.py::test_actual_owner_crash_after_artifact_restart_uncertain_and_pending_blocked --basetemp="$run003Repeat\cases" -q
```

测试负责创建新实验/计划/TEST_ONLY grant、启动 owner 与客户端、等待确定阶段、核验状态、清理自己创建的进程和私有连接凭据。显式产品入口另为 `python -m abqjobpilot.execution.supervisor --test-root <root> --bootstrap <private-file>`；普通 FakeClient 从不调用该入口。完整测试命令、实际结果和限制见 [验收矩阵](ACCEPTANCE_MATRIX.md) 与 [生命周期证据](PROCESS_AND_ISOLATION_EVIDENCE.md)。
