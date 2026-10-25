# Run019 生命周期契约

## 接入审查与变更

实际基线 Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63，应用仍为 0.3.0.dev0、实验格式 3。本轮没有 schema/IPC envelope 版本迁移。BASELINE.json 保存前置 Git 状态和文件摘要；Run014–018 累计修改并非本轮新写。

原 `FakeSupervisor.serve/_work` 已将 IPC 与执行分开；`LocalOwnerLock` 使用 Project `owner.lock` 的 4096 字节位置 Windows 排他锁，句柄不可继承。旧入口通过外部 stop_event 收尾，缺少公共的空闲管理停服。原新 owner 首次无 Run 时 OPEN，以后启动 PAUSED。Run018 `discover` 已验证 Project/格式、endpoint 与 owner.json 一致、PID+创建时间+映像、认证健康响应、协议和 project_view 能力。该路径继续复用。

新增 `service_lifecycle.ServiceLifecycleManager` 和固定 `service_owner.py` 入口，后者仍持有原 `FakeSupervisor → ExecutionService → Store/Backend`，不是另一个调度器。新增 `execution.lifecycle` 仅管空闲条件/停服事务；`service_host` 仅查询本进程的 Windows 宿主事实。

## 支持与权限

仅支持明确 `<instance>/project` 格式3、在首次使用前由可信设置登记的 TEST_ONLY 生命周期配置。允许 Fake 和受管 ProcessFixture；真实计划、真实 Run、行政处置、未决 Run 均不纳入本轮启动/停服范围。已有真实/旧 owner 仍可按原连接兼容规则观察；不会升级、停止或替换它们。

三种能力分别存在：

| 能力 | 来源/用途 |
|---|---|
| connection credential | 已有 loopback IPC 认证，仅证明连接权限 |
| private/operator.json | `configure_lifecycle` 在原初始 owner lease 内登记的随机生命周期能力；绑定 context_digest，服务端存其摘要；允许明确 start/idle-stop |
| ExecutionGrant / 管理 Grant | 原精确计划、执行、恢复及对账规则；生命周期能力不能替代 |

配置只接受既有固定 Python Backend 配置，不开放任意命令、环境、脚本或插件。注册解释器绝对路径固定于当前 Dev，采用 SystemRoot 与私有 TEMP/TMP 的最小子进程环境；不修改共享环境。普通 GUI 不 mint，Start/Stop 明确操作时使用当前实例已交付的独立 operator 文件。无此文件拒绝。相同 OS 用户任意修改代码/文件不是本机制的隔离威胁模型。

## 共同 API

`ServiceLifecycleManager(project_root, connection_file=None)` 明确绑定 Project。

| 方法 | 行为 / 写入 |
|---|---|
| inspect() | 只读认证发现；返回 CONNECTED / NOT_RUNNING / BLOCKED；不创建服务 |
| connect() | 原 discover，返回 client/context/health，重验身份 |
| disconnect() | 本地断开声明；不操作 owner |
| start(operator_file=None, wait_seconds=8) | 精确权限、原 owner 锁内空闲检查、持久预约，再固定 Python owner 创建；有界确认 |
| stop(owner_id, operation_key, operator_file=None) | 原认证 IPC 新 `lifecycle_stop` 白名单操作；独立能力、精确 owner、幂等、事务空闲停服 |

主要原因码：OWNER_BUSY、START_BLOCKED、START_UNCONFIRMED、LIFECYCLE_PERMISSION_REQUIRED、LIFECYCLE_SCOPE_UNSUPPORTED、SERVICE_NOT_IDLE、SERVICE_STOPPING；沿用 AUTHENTICATION_FAILED、ENDPOINT_IDENTITY_MISMATCH、PROTOCOL_MISMATCH、CAPABILITY_UNAVAILABLE、STORE_REQUIRES_MAINTENANCE 等。GUI 不展示原异常载荷、令牌或 bootstrap。

## 启动竞争和不确定性

1. 先认证已有 owner；兼容 owner 直接返回同一身份，无第二次创建。
2. 无 owner 且无不明 metadata，取得**原来的 LocalOwnerLock**；在只读数据库事务内检查格式、authority、空槽、所有 Run 和计划。上限各512条，超限拒绝，不扫描生产目录。
3. 锁内以 exclusive-create + flush/fsync 写入 `private/start_*/intent.json` 与 `lifecycle-current.json`。任意半写/损坏/无法读取预约均阻断。之后释放锁才创建固定 owner，解决父子锁交接。
4. 子进程仍取得同一 owner.lock，重新检查空闲和预约/配置摘要，在写 owner 元数据之前 exclusive-create `claimed.json`。竞争者、重复直接调用这个 host、丢应答都不能绕过旧预约再创建有效 owner。
5. 进程创建与文件不是 exactly-once 原子事务。任何预约后失败或不确定只允许 inspect/connect，不自动再创建。保留 created transport PID 与 ready 中实际 Python 身份，二者不混同。
6. 只有同一 owner 的已提交停服回执和正常退出路径生成的 stopped.json 相互匹配，才允许下一次显式 start；原始锁仍须可取得。旧 marker、PID 消失或端口不通本身不授予接管权。

开始服务没有 Run 接受或 Grant 消耗。未决可执行任务拒绝启动。初始已 OPEN 且无 Run 才保留 OPEN；初始 PAUSED 也保持 PAUSED。之后重启一律 PAUSED。无恢复、重试、行政释放或真实 Backend 配置。

## 停服事务与竞争

`LifecycleControl.stop` 在 session RLock + 原 owner lease + SQLite 事务内先临时 PAUSED，然后检查 active_dispatches=0、逻辑槽空、每个 Run FINISHED/reconciliation NONE、无行政处置；ProcessFixture 还必须已持久化 COMMITTED_EMPTY_SCOPE。任何失败回滚派发变化。

成功在同一事务写 management_receipts、control_events、PAUSED。事务提交后仍在同一 session 锁内标记 stopping，所有后续写事务和 dispatch 均拒绝，关闭 submit 预检查与接受事务之间的竞争窗口。原 receipt/Run/事件/Grant 消耗没有修改或删除。

相同键返回原回执；不同请求拒绝。提交结果不确定时保持 stopping 阻断；可通过原 management_receipt 查询，原键重放依据已提交决定完成同一 owner 的正常停服。不会杀 PID 补偿。GUI 键固定为 `gui_stop_<owner_id>`，跨 GUI 重开仍相同。服务退出后 manager 只读验证 stopped.json 对应原数据库回执。

服务 accept 循环停止，执行线程/在途请求正常 join，原 pause_after_error/close 保留 PAUSED 后释放所有权。不调用 terminate/kill，不清除未决记录/输出/锁。未知停服结果、缺少 orderly marker 时拒绝重启；不提供强制修复入口。

## Windows 承载边界

创建：登记 python.exe，`-I -S -B service_owner.py --project … --start-id …`，shell=False、close_fds=True、CREATE_NO_WINDOW；stdin DEVNULL，stdout/stderr 是该 start 目录独立文件。无 breakaway、父进程伪造、服务安装或计划任务。GUI 本身不持有 owner 锁，也不在关闭时销毁 owner 所需资源；GUI 最多等待自己尚未完成的有界生命周期请求结束。

启动请求进程及实际 owner 都记录 IsProcessInJob 查询、直接 Job 限制、PID/创建时间/映像和输出类型。查询失败阻断。测试中两者直接 Job flags=0x3000（含 KILL_ON_JOB_CLOSE 和 SILENT_BREAKAWAY_OK）；没有因为某个 kill=false 放行，也没有改 Job。**通过依据是相同创建路径下，GUI 和专属 venv 启动器的保留句柄证实退出后，owner/worker 的保留身份仍活着且日志增长。** 直接 Job 查询不是完整层级/Job 所有者证明。

只承诺本轮 Windows/登记解释器/普通创建链在会话保持存活时的已观察 GUI 退出行为。关闭外层托管宿主、终端、注销、关机、系统重启，以及其他安装和宿主政策未验收。发现不同宿主失败时必须 BLOCKED/PARTIAL，不靠创建标志宣称独立。真实 Abaqus 路径没有在本轮被生命周期启动器启用或测试。
