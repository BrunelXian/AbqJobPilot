# 操作者宿主兼容性验证：仅普通 Python

验证包已完成；**操作者终端尚待实测，不能记为通过。真实 Abaqus 调用预算 0。**

只使用现有 PowerShell，保持终端和 Windows 会话存活。不关闭窗口，不用 Ctrl+C 停止等待。无需更改执行策略、PATH、Python 环境或任何 Job 设置。若脚本被策略拒绝，停止并交回原始错误，不用其他承载渠道规避。

## 一条命令

在你从 Windows 桌面独立打开的、需要验证的 PowerShell 中粘贴：

```powershell
& 'D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\host_compatibility_001\run_host_check.ps1'
```

不要由 Codex、计划任务、服务或另一个后台宿主代开终端。该脚本在**当前 PowerShell OS 进程**中观察，用普通 `.NET Process.Start`、`UseShellExecute=false` 启动固定的 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe -B <本目录 fixture_controller.py> <新建 case_host>`。没有创建新 PowerShell，也没有显式 breakaway。不要单独调用 fixture_controller.py：它需要当前 PowerShell 的身份与握手。

脚本不依赖当前工作目录，参数为零；内部只有登记 venv、固定控制器和原 Run011 Python worker，没有可传入的命令、模型或真实 execute。启动前检查 BUNDLE.json 中引用材料的大小和 SHA-256。它是测试材料变更检测，不是执行授权或防同用户篡改的签名。

## 预期输出和判据

首先打印：

```text
HOST_FIXTURE_EVIDENCE=C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run011_Host_<本次32位随机标识>\case_host
```

正常约 11 秒后输出完整 JSON。worker 原固定最长运行时间为 10 秒；观察控制器复用 0.6 秒测试预算，握手最多等待有限秒数。异常时脚本只有限等待已有进程自行退出，不终止进程、不删除文件、不重试本次链路；磁盘/系统调用自身阻塞不属于硬实时保证。

只有 JSON 同时满足以下条件，才表示**本次固定 Python 链路观察通过**：

1. `status = PASS_OBSERVED_FIXED_PYTHON_CHAIN_ONLY`。
2. `controller_host.job_query_succeeded = true`；实际 `in_any_job` 原样记录，测试不将其伪装成生产准入通过。
3. `controller_chain_OS_evidence` 明确记录 PowerShell → venv 启动器 → 实际基础 Python 控制器三者的 PID、创建时间和映像；预期父关系由控制器 OS 快照核对，PowerShell 又独立核对进程身份并保留句柄。
4. `function_return.not_OS_exit_evidence = true`。函数返回是控制器自报；后续 `controller_exit`、`controller_venv_exit` 分别为保留 OS 引用取得的退出码 0。
5. 在上述两个退出之后，`worker_after_entire_controller_chain_exit.exited = false`，`post_exit_growth.after_bytes > before_bytes`，`worker_after_growth.exited = false`。这些观察绑定同一个 PID+创建时间+映像及同一持有引用。
6. 随后 `worker_exit` 和 `worker_venv_exit` 均有 OS 退出码 0；`worker_self_report` 单独标为文件自报。本次不创建 `release` 文件，worker 到自身 10 秒截止点后退出。
7. `cleanup` 中四个固定 Python 进程均已确认退出，自己的引用关闭；`abaqus_calls=0`、`real_execute_calls=0`、`admission_changed=false`。

`NOT_PASSED`、身份/查询错误、超时或缺失字段均不能默认通过。PowerShell 命令返回、`$?` 或 `$LASTEXITCODE` 不能替代上述 JSON 判据。报告中的 `context` 故意不自称操作者桌面：只有你实际从独立终端调用，才可把它关联到那个操作者上下文。

## 证据位置及交回内容

本次路径由首行和 JSON 的 `evidence_root` 给出，与真实 Run010 实验根完全分离。每次新建目录，不覆盖以前结果。临时测试证据保留，不自动删除。

| 相对 case_host | 内容 |
|---|---|
| `HOST_REPORT.json` | PowerShell 的身份、函数返回、整条控制器启动链退出、worker 后续存活/增长/退出及收尾记录 |
| `observer_context.json`、`controller_ready.json` | 观察者身份、实际控制器身份及 OS 父关系 |
| `worker_launcher.json`、`worker_ready.json` | 控制器持有的直接创建引用及 worker 提供的候选身份；后者必须经过独立 OS 核对 |
| `function_returned.json` | 函数返回事实，不是 OS 退出证据 |
| `observations\controller_report.json`、`controller_events.jsonl` | 原控制器核心在临时 fixture 上生成的记录，成员完整性仍 UNKNOWN |
| `observations\stdout.bin`、`stderr.bin` | worker 启动链直接继承的普通文件；没有 PIPE、没有已退出控制器负责转发 |
| `heartbeat.txt`、`worker_done.json`、`physical_worker_*.json` | 原 worker 的固定自报文件，不能独自证明进程存活/退出 |

把屏幕 JSON 或本次 `HOST_REPORT.json` 的完整路径交回即可。需要时再只读审查该目录的握手和控制器记录，不需要任何完整环境变量或生产数据。不要改写真实实验根，也不要接着运行 Abaqus execute。

## 与真实候选的差异和限制

- 真正的 Run011 `probe.py check/execute`、`windows_host.admit` 及摘要 **645389d8…c016824** 未改变，依旧要求控制器不属于任何 Job。这个测试结果不是它的放行凭据。
- 这里复用原 `engine.run_once` 的文件输出、观察到期、关闭引用和返回路径；与原测试一样，**仅在独立测试驱动内注入准入条件**，同时保留 actual_job_observation。真实 CLI 没有绕过参数。
- 控制器创建 worker 使用绝对登记解释器、参数序列、显式 executable、shell=False、close_fds=True、CREATE_NO_WINDOW、stdin=DEVNULL 和独占普通日志文件。这复现普通创建及句柄策略；不执行 BAT，不模拟 Intel/Abaqus 的动态进程集合。
- worker 使用原夹具的最小替换环境（SystemRoot/TEMP/TMP），而非真实候选完整环境字典；cwd 和输出全部改为新的测试根。该差异必须保留，不能宣称已经测试了真实包装器/许可证/环境。
- PowerShell 自身持续存活并持有**普通进程查询/等待引用**，不打开或持有 Job 对象来改变 Job 生存期；不测试关闭终端、注销、关机或外部终止。Windows 可能创建 conhost 等辅助进程；不宣称完整任意进程树收尾，四个固定 Python 成员的退出分别记录。
- 原候选的“明确不属于任何 Job”比有限观察更强；本结果只证明一次已观察区间内的固定 Python 行为，不能用来推断完整 Job 层级、Job 所有者或所有未来进程不会被结束。

测试结束后停止，等待只读审查。本轮不产生真实执行授权。
