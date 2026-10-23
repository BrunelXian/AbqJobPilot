# Run011 操作者宿主兼容性验证包

**验证包就绪；操作者终端验收 PENDING。真实 Abaqus 调用 0，真实 execute 调用 0。**

唯一改动范围为本独立目录 `D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\host_compatibility_001`。Dev 为 Develop@fb7912ec9e0107b18f65948b147c87579c87cded，版本仍 0.3.0.dev0，无冲突，原未跟踪成果保留。适用 Dev AGENTS、环境登记、Run011 最终报告/USAGE/实际代码和既有测试均已读取；沿用新记录不覆盖历史证据的 Run 约定。

## 复用判断与最小增量

| 实际入口 | 复用/缺口 |
|---|---|
| `run_011/tests/fixture_process.py:main(worker)` | 原样复用固定普通 Python worker：身份登记、心跳、10秒最长运行时间、自行退出。本包不创建原夹具支持的提前 release 信号。 |
| `tests/test_candidate.py:test_r11_05_06_controller_returns_worker_continues_then_exits` | 原测试已通过 OS 引用核实 controller 退出后 worker 存活，但 `Launched` 默认用基础解释器，不能直接作为完整操作者 venv 链证据。 |
| `run_011/controller/engine.py:run_once` | 原样复用一次意图、文件日志、观察预算、finally 关闭引用及返回行为，参数仅为新的 fixture 根和固定 Python callback；不触及真实实验。 |
| `windows_host.current_host/process_rows/handle_identity`、`execution.process_handles.ProcessReference` | 原样复用 Job 查询、OS 父关系快照、PID+创建时间+映像、保留句柄和退出观察。 |
| 新 `fixture_controller.py` | 薄驱动：固定 venv/worker、有限握手、对真实执行不可达的创建哨兵、明确测试 DI、函数返回记录。没有真实执行操作。 |
| 新 `run_host_check.ps1` | 在实际调用它的 PowerShell 内保留控制器启动器、实际控制器、worker 启动器、实际 worker 的 OS 引用，先验证整个控制器链退出，再验证同一 worker 存活/续写/自然退出。 |

没有新长期 Runner、数据库、后端、共享依赖或系统服务。原候选入口/执行相关材料均保持，其 body SHA-256 仍为 `645389d8f25942e908f04dca25fbefed820d6f63b35fcfb6c308977b6c016824`。新 BUNDLE.json 只绑定独立测试包装及其复用材料，绝非原真实执行许可的扩展。

## 当前实际验证

- 登记解释器 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python 3.12.10，pytest 9.1.0；无安装或升级。
- 最终针对性单元组 **13 passed，0.12s**（UNIT_RESULTS_03.xml）：路径隔离、查询失败/未知、启动链缺口、实际 OS 创建时间不匹配、固定创建哨兵、写入边界、半写握手拒绝等。
- 工具环境 PowerShell 7.6.5 的普通链路验证通过；后续显式使用 Windows PowerShell **5.1.26100.9711** 的同包验证也通过。都是受管工具环境，**不是操作者桌面终端的证据**。
- 最终 5.1 实例 `...\AbqJobPilot_Run011_Host_1cdf06dd4cdc487a9093944c605bbdaf\case_host`：控制器 PID33180、venv PID3220 退出码0；之后同一 worker PID28804 仍存活并继续写入；随后 worker 和它的 venv PID17948 均自行退出0。每项均有创建时间、映像、保留 OS 引用和观察时间。完整路径和数据见 VALIDATION.json / TOOL_WINDOWS_POWERSHELL_EXPLICIT_06.txt。
- 原34项材料、新候选21项材料、前轮106项原文件和本轮开始时的 Run011 文件均匹配。VALIDATION.json 的 changed 列表均为空。
- 共三组成功的 worker 链，以及两组在 worker 创建前失败的控制器链；16个已登记 Python 子进程均有退出证据，自己的引用均关闭。失败控制器退出2，成功成员退出0。未调用 kill/terminate；没有删除目录/输出/旧记录。普通 Python 单元测试进程也正常返回。

开发迭代透明保留：第一次 pytest 命令的 PowerShell 参数写法错误，0项收集；修正调用后12项通过，补充实际创建时间冲突后13项通过。首次链路因 PowerShell 保留变量 ShellId 命名冲突在创建前失败；第二次测试哨兵误拒绝固定 DEVNULL；第三次捕获到 Popen 未显式提供 executable 造成哨兵类型错误。修正新包装后通过，未改旧候选或放宽任意命令限制。第05次请求工具使用5.1但实际仍为7.6.5，因此第06次才用明确5.1入口验证；报告以实际进程映像和版本为准。所有失败记录保留，不当作通过。

没有重跑无关 GUI/Solver 或全部历史回归，因为正式核心和旧夹具没有改动；本轮直接运行的集成组已实际经过复用的 run_once、进程引用及文件日志路径。

## 操作者现在做什么

在从桌面独立打开的实际 PowerShell 中运行：

```powershell
& 'D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\host_compatibility_001\run_host_check.ps1'
```

保持窗口和 Windows 会话存活。证据写入脚本打印的新临时根，详细判据和结果位置见本目录 USAGE.md。预期报告状态为 `PASS_OBSERVED_FIXED_PYTHON_CHAIN_ONLY`；任何失败/缺失必须保留，不能以命令返回成功代替报告。这个状态只表示该次固定 Python 链路，不表示真实候选已经获准绕过 Job 检查。

用户提供的直接 Job 0x3000/0x1800 诊断属于用户观察背景，本包没有补推 Job 层级或所有者；不将某个 kill_on_job_close=false 自动解释为安全。

## 基于源码的最小准入修订建议（本轮未实施）

现在仍应保留原候选拒绝。即使操作者夹具通过，也不能仅删除 `windows_host.admit()` 的 `in_any_job is False` 条件，或用一个直接 Job 的 flags 代替完整保证。

若下一项任务明确选择接受“固定操作者终端持续存活、有限实测兼容”的较窄保证，最小待审修改应局限于一个显式宿主政策：`probe.host_for_launch/check` 与 `windows_host.admit` 使用同一判定，默认仍是原严格政策；固定操作者模式必须绑定经审查的解释器/控制器/父启动链及创建、日志、环境策略，启动当次重新读取自身及父链身份/Job查询，查询失败、身份变化或证据不符继续拒绝。兼容验证结果只是该政策的一项依据，不能充当批准凭据，不能有泛化 skip/approved=true。

这必然改变原 `frozen.configuration().host_admission` 和代码摘要，需要独立的新候选、针对性验证和针对新语义的明确授权。旧摘要或本包结果都不能覆盖这项变化。如果仍要求证明所有 Job 层级不会在观察结束后终止后代，当前证据不足，不能声称这种最小修订已经解决了它。

普通 Python 结果也不覆盖真实 BAT、Intel 环境、Abaqus 成员集合及退出、Solver数值和ODB。没有改用基础解释器作为真实控制器入口，没有执行 breakaway/改Job/任务计划/服务/WMI创建，没有修改核心/版本/环境/授权，没有访问 Stable、生产数据或执行 Git 写操作。

验证包完成后停止，等待操作者执行并交回证据。不自动开始真实实验或下一轮。
