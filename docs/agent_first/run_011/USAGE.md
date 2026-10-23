# Run 011 固定控制器候选：操作者命令

本轮仅开发与非 Solver 验证，**真实 Abaqus 调用 0 次，真实 execute 操作调用 0 次**。下面的 execute 命令是待单独批准的新候选入口，本轮没有执行。

## 固定对象与摘要

- 原实验：`abq2024_r010_a19d17ea`；Job：`r010_bar_a19d17ea`。
- 原清单：`D:\Projects\abqjobpilot_dev\docs\agent_first\run_010\EXPERIMENT_MANIFEST.json`。
- 原规范化 body 摘要：`sha256:04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6`。
- **新候选清单**：`D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\CANDIDATE_MANIFEST.json`。
- **新候选规范化 body 摘要**：`sha256:645389d8f25942e908f04dca25fbefed820d6f63b35fcfb6c308977b6c016824`。
- 控制器：`D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\controller\probe.py`。

摘要计算为 UTF-8 编码的 `json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)` 的 SHA-256，前缀 `sha256:`。不是整个排版清单文件的字节摘要。新 body 包括 21 项执行相关材料的字节摘要及大小、固定调用/环境/观察策略，并引用原清单及其 body 摘要；不包含自身 content_digest。测试、报告、USAGE 和冻结工具不进入执行材料摘要，避免说明引用摘要造成自引用。

新候选没有获得真实执行批准。原实验批准不自动覆盖新增控制器。`--candidate-digest` 仅检查身份，不是凭据、签名、审批记录或 Agent 权限。

## 1. 无 Solver 检查（可执行）

由操作者从 Windows 桌面自行打开 PowerShell，先阅读 `D:\XianLab\envs\ENVIRONMENTS.md`。无需激活环境、安装依赖或修改 PATH。所有命令使用已登记 LangChainEnv 解释器 Python 3.12.10；底层实际 Python 映像为已登记的 `D:\Program Files\Python312\python.exe`，控制器会核对。

```powershell
Set-Location -LiteralPath 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\client_cwd'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B `
  'D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\controller\probe.py' check `
  --candidate-digest 'sha256:645389d8f25942e908f04dca25fbefed820d6f63b35fcfb6c308977b6c016824'
```

默认不写操作名称也是 check；`--help` 仅显示帮助。没有 `--source`、`--root`、`--command`、`--skip-job-check`、`--approved`、`--timeout` 或动态 Backend 参数。

check 在当前 Python 进程重新核对原清单及 34 项材料、新候选及 21 项材料、公开离线预览、固定目录、已有输出/观察/尝试痕迹；随后查询自身身份、解释器、时间、标准句柄类型及 `IsProcessInJob`。不写尝试、不打开执行日志、不生成 Run、不调用外部程序。

`CHECK_ONLY/materials=MATCH/host_condition=PASS_AT_THIS_OBSERVATION_ONLY` 只表示本次检查满足当前条件。若 `host_condition=BLOCKED` 或结构化错误，停止；不能改 Job 配置或尝试脱离。查询必须成功且明确不属于任何 Job。当前 Codex 工具环境实际返回 BLOCKED；**不是操作者终端的测量结果**。

execute 会在自己的实际进程中重新做这些检查，不读取旧 check 结果放行。检查失败返回码 2；检查满足条件返回码 0。这些返回码都不是 Solver 判定。

## 2. 新候选获得明确批准后才能执行（本轮禁止执行）

审批对象应明确引用上面的新候选清单及摘要，并继续限定原实验、原输入与原参数。代码不需要改开关；只能由操作者在批准后主动调用以下明确入口：

```powershell
Set-Location -LiteralPath 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\client_cwd'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B `
  'D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\controller\probe.py' execute `
  --candidate-digest 'sha256:645389d8f25942e908f04dca25fbefed820d6f63b35fcfb6c308977b6c016824'
```

这不是本轮已验证的真实启动命令。它已经对应实际实现，但唯一真实创建函数仅用捕获替身核对了参数，未调用 OS 创建 Abaqus。命令原样取自原清单：绝对 cmd.exe `/d /s /c` 包装绝对 `D:\ABAQUS2024\Commands\abq2024.bat`，固定含空格参数引号，shell=False、CREATE_NO_WINDOW、close_fds=True；不重新 list2cmdline 拼装，不经过 PATH 搜索，不绕过 BAT。

子进程使用冻结环境字典**完整替换**父环境，不继承终端的整份环境。VS2022 默认路径缺失风险保持，不修复包装器、安装或许可证。不改变模型：Standard analysis 一次，interactive，CPU=1、GPU=0、memory="2048 mb"，额外 Abaqus 调用 0。

操作者保持终端和 Windows 会话存活。不要以 Ctrl+C、关窗口、注销或关机停止等待。300 秒从写 START_INTENT 前的单调时钟起计，含意图持久化、创建和观察；到期停止采样、保存有限结果、关闭本控制器的引用后返回，不终止后代。不使用 subprocess.run(timeout)、with Popen 等自动等待/终止路径。OS 创建和磁盘 IO 本身可能延长命令返回时间，300 秒不是操作系统强制运行上限，也不是每种系统故障下的严格墙钟返回保证。

已有意图（包括空/半写/损坏）、已有 Job 输出、非空观察/提取/scratch、材料改变、路径异常或 Job 准入失败均阻断。意图之后的异常、创建失败、丢应答或不确定状态都**不允许重放 execute**。不删除意图、不换 Job/目录/候选版本继续，不自动重试、修复或删除输出。

## 3. 后续只读报告（可执行，不重探进程）

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B `
  'D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\controller\probe.py' report `
  --candidate-digest 'sha256:645389d8f25942e908f04dca25fbefed820d6f63b35fcfb6c308977b6c016824'
```

report 校验包身份并读取已有记录；不创建外部进程，不重新验证产物或当前进程健康，不写最后访问时间或清理记录。无意图返回 NO_ATTEMPT_RECORDED；有意图无完整报告返回 ATTEMPT_WITHOUT_CONFIRMED_REPORT/UNKNOWN/禁止重试；损坏或读不到数据则明确报错。已有报告是 HISTORICAL_RECORDED_VIEW，不能写成“现在仍存活/现在已验证”。

execute 的返回码 0 只表示已写出报告，不代表实验通过。报告始终单列创建、已观察退出、成员完整性、Solver 文本、数值及 ODB 状态；当前候选不证明 Abaqus 必需成员集合完整，整体保持 PARTIAL。即使未来只读报告显示数值符合，也没有自动对账、恢复或第二次执行能力。

## 固定输入、日志和数值位置

实验根完整路径：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a`。

| 相对上述根 | 含义 |
|---|---|
| `engineering\axial_bar.inp` | 原输入，SHA-256 e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3 |
| `engineering` / `engineering\scratch` | 唯一 cwd / scratch |
| `observations\attempt.json` | 永不自动删除的独占意图，绑定原实验/实际输出身份；不随候选版本变化 |
| `observations\controller_events.jsonl` | 序号/时间/来源明确的外部控制器事件，不是正式 Project 历史 |
| `observations\stdout.bin` / `stderr.bin` | 独占新建普通文件，子进程直接写，不依赖 Codex 管道 |
| `observations\controller_report.json` | 有界报告与窄范围打印比较；只新建，不覆盖 |
| `engineering\r010_bar_a19d17ea.dat` | 有归属条件的本次打印文本；最多读 16 MiB |
| `extracted` | 保留原目录，本候选不复制 DAT/ODB，不额外写 measurements.json；数值记录在 controller_report.json |

原准备方案中的 processes.jsonl/file_observations.jsonl 合并进 controller_events.jsonl/报告；这项新增实现差异由新候选覆盖，旧 SHA 不覆盖控制器。报告不含完整环境、凭据或无关进程命令行。

数值固定为 step1/final time1、node2 U1=+0.01mm（1e-6）、element1/integration point1 S11=+1MPa（1e-4）、node1 RF1=−1N（1e-4），另检查约束位移、node2 反力、X 力平衡。解析器只接受明确的三张表及唯一 step/increment/time/版本/产品/完成标志；**尚未验证真实 2024 DAT 版式**，不支持就返回证据不足。`samples/SYNTHETIC_DAT.txt` 是人工固定测试文本，不是实际 Abaqus 输出。ODB 内容一律 NOT_RUN，不追加任何后处理调用。

可以交回候选摘要、check JSON、尝试/事件/报告及限定日志进行只读审查；不要把整个环境或生产工程包交回。输出缺失、版式不支持或成员未知时不改输入/容差、不补跑。旧三个测试目录及五个脚本保持原状，不调用它们，也不清理。
