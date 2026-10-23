# Run 013 实施边界与接入

本轮只做候选实现、受控替身和离线验收，真实 Abaqus 调用为 0。历史 Run 010/011 的独立实验不导入新 Project，也不消费它的尝试预算。

## 基线与最小接缝

实际 `Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，`0.3.0.dev0`，无冲突。开始时 `gui_app.py` 已有 Run012 修改，执行包、预览包、示例、测试、Run002～012 文档原来即为未跟踪成果。完整清单见 BASELINE_STATUS.txt 和 BASELINE_FILES.json。遵循 Dev AGENTS、环境登记及各轮沿用的独立目录、不覆盖历史惯例；没有另行发现上级 Run 编号协议。

登记解释器为 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，实际 Python3.12.10、pytest9.1.0、Tk8.6。不安装依赖。

| 接缝 | 实际实现和改动 |
|---|---|
| 固定计划 | 新 `standard_contract.prepare`，可信本地准备，仅接收逐字节相同的已验证轴向杆、严格 Job 名和显式隔离目录；使用原 plans/jobs 存储及原 canonical_json/digest。没有修改原 ExecutionPlan、Fake/ProcessFixture 摘要或 Run009 AbaqusPlanPreview。 |
| 真实授权 | `standard_contract.issue_execution/check_grant`，注册 `REAL_FIXED_STANDARD` 精确计划许可。原 TEST_ONLY 工厂不支持该 Backend。普通 IPC 无 approve/mint/prepare/插件入口。 |
| 初次准备租约 | `store.acquire_initial_preparation_store` 只允许从未启动 Supervisor、没有 Run 的原实例，取得同一个 OS 独占锁。它不修改 supervisor_started、不恢复派发；活动/已启动实例拒绝。用于将后续明确批准登记到已经准备好的新实例，不另建授权数据库。 |
| 接受与领取 | 原 `ExecutionService.submit/_execute_pending`，原接收事务、授权消费、幂等回执、单槽原子领取。真实分支额外校验固定计划和能力；Run 在外部创建前存在。 |
| 启动与观察 | 新 `StandardBackend.execute` 位于同一 Supervisor 的原执行线程，RPC 只返回原持久回执。`standard_process` 从旧实验只抽取只读 Win32 观察能力，复用原 ProcessReference；不导入 docs 控制器或旧 Runner。 |
| 输出保护 | 开始前检查固定 Job 的输出、scratch 和 job env 文件；已领取后 O_EXCL+flush+fsync 写固定输出旁的 `.Job.intent.json`。同目录协议参与者不能因更换 Project、Plan 或 owner 绕过已有文件。部分/损坏文件也不删除。不是整机资源管理，不能防止同 OS 用户绕过协议手工运行。 |
| 验证 | `standard_dat` 为 Run011 CP936 实际版式纯解析器的产品副本，原文件不变；冻结主标准 U1=0.01±1e-6、S11=1±1e-4、RF1=−1±1e-4。新 `collect/persist_result` 独立读本 Run 有时间/内容身份依据的有界文本，单独提交 observation/validation。 |
| GUI | 沿用现有 `ExecutionView/Reader`、公共 client 和双日志区。Standard 与 TEST_ONLY 明确区分，显示创建、成员完整性、Solver、DAT、ODB、问题码。查询失败不抹去已持久化执行事实。GUI 不写库、不提交、不批准或恢复。 |
| 诊断 | v3 白名单投影只用于新 Standard Run；v1/v2 仍可读和导出。历史进程/文本记录不变成当前探测；不读取 ODB。 |

## 主机政策与停止语义

新政策 `independent-service-same-windows-session-v1` 绑定在计划和批准摘要中。实际发起调用的 owner 内，检查配置/输入、owner 租约、自己的 OS 身份、登记解释器、IsProcessInJob 查询成功以及 stdout/stderr 为普通文件句柄。创建前再检查，不能沿用 check 命令或 GUI 缓存。

这是**新的、较窄服务会话契约**，不是 Run011 的 PowerShell→venv→控制器承载链。允许记录到的 Job，但不据此证明完整 Job 层级或 Job 关闭行为，也不依据 kill_on_job_close=false 放行。它明确不承诺 owner 崩溃、终端关闭、注销或重启后 Solver 存活。GUI 是独立只读客户端，正常关闭不会主动停止 owner；真实 Abaqus 的 GUI 关闭/重连行为仍是下一次实机验收内容。没有 breakaway、Job 修改、系统服务或计划任务。

实际调用沿用已验证 Windows 引号结构，明确 `C:\Windows\System32\cmd.exe /d /s /c` 包装唯一绝对 BAT，shell=False、close_fds=True、CREATE_NO_WINDOW、stdin DEVNULL，stdout/stderr 写本 Run 文件。固定环境为最小 Windows 变量和新 Run 的 HOME/TEMP；不继承 IPC/Grant 秘密、不执行环境文件做准备。安装 site 配置仍可能影响实际运行，绑定显式已知文件摘要，不宣称完整环境供应链证明。VS2022 默认路径缺失风险保留。

观察预算从创建返回、进入观察时起最多300秒；创建耗时单列，不声称这是 Solver 强制时长或整个操作绝对时限。无 terminate/kill/额外 Abaqus 调用。截止、证据失败或正常观察结束只关闭本进程引用，不关闭带终止策略的 Job，不增加后台观察者。

`FakeSupervisor.serve` 原来就会在结束监听后 join 执行线程。本轮 Standard 操作者 stop 入口进一步等待 active_dispatches=0 再请求 owner 正常退出，让有界观察期间 IPC 继续响应。停止 owner 不代表 Solver 停止；不删除凭据、未解决记录、输出或意图，不重置槽。意外强杀 owner 后原 START_INTENT、PAUSED 和不确定规则仍适用。

## 分维度证据及释放条件

持久顺序：接收/消费事务 → 领取槽/START_INTENT → 输出意图文件 → 数据库 LAUNCH_INTENT → CREATE_ENTERING → 一次 Popen → 记录创建 → 记录观察到的身份与可信退出 → 观察结束 → 文本验证记录。文件与数据库/外部进程之间不承诺 exactly-once。

成员发现是有界的、基于仍存活的保留父进程身份和 OS 创建时间的候选关联。每个成员退出来自直接 Popen 句柄或已核实的 retained Windows handle；PID 消失不补为 exit0。最多16个观测成员，父子关系和发现数量均不证明完整 Solver 集合。

首版始终保留 `member_completeness=UNKNOWN`、`overall_exit=UNKNOWN`、`exit_verification=UNKNOWN`。即使所有已观察进程 exit0、DAT/STA/MSG 有结束依据且三项数值通过，也仅记录这些成立维度。Run 仍 RECONCILIATION_REQUIRED，派发门 PAUSED，槽和输出意图不释放。没有本轮可用的真实对账/解除/Retry；原 Fake 采纳和 ProcessFixture 已记录退出对账均拒绝该 Backend。

本轮可以结束**观察**；不能自动声称允许下一个真实任务派发。非零退出、验证失败、文本缺失/解码/归属错误均不能覆盖先前的创建或退出记录。ODB 内容始终 NOT_RUN。

## 日志及隐私

公共 progress 复用已有 RPC。Standard 只读固定 Job 的 STA/MSG/LOG，每文件≤1MiB，返回字节数和固定完成/失败标记，绝不传回任意原始许可证、环境、命令或异常文本。它是最新有界视图，不是进程退出证明。完整 stdout/stderr 留在隔离 Run 目录供操作者审查。

真实授权绑定存储/Project/Plan 摘要（包含输入、入口身份、资源、环境政策、工作目录和输出键）及一次预算。授权来源是可信操作者的显式审计引用，不是假装实现了生产级身份认证；同 OS 用户任意修改代码/数据库的能力不属于防护模型。本轮待批准实例不会登记有效执行 Grant。
