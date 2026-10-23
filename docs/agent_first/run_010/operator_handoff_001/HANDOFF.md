# Run 010 — 操作者独立终端交接

记录日期：2026-10-23。**交接说明已形成；真实启动步骤仍不可执行（缺少实际实验控制器）。本轮真实 Abaqus 调用 0 次。**

## 1. 当前结论与固定对象

`real_001` 保持 `BLOCKED_BEFORE_LAUNCH`：包装器调用 0、额外 Abaqus 调用 0、没有 START_INTENT、没有 Solver 结果。其阻断是受管工具的 Job 生命周期不能保证“停止等待但不终止后代”，不是缺少用户对原实验的授权，也不是求解失败。本轮没有再次试验 breakaway、替代调度或其他脱离手段。

本轮进一步静态核实：**冻结包只有候选调用数据、观察方案及离线检查入口，没有冻结的可执行实验控制器。** 因此不能给出一个实际上不存在的“原控制器启动命令”。用户在独立终端中可以执行第 4 节的材料核验，但不能据此跳过缺失保护，直接把 BAT 或清单字符串当作受保护入口运行。

| 项目 | 固定值 |
|---|---|
| 实验 | `abq2024_r010_a19d17ea` |
| 清单 | `D:\Projects\abqjobpilot_dev\docs\agent_first\run_010\EXPERIMENT_MANIFEST.json` |
| 原批准摘要 | `sha256:04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6` |
| 唯一 Abaqus 入口 | `D:\ABAQUS2024\Commands\abq2024.bat` |
| Job | `r010_bar_a19d17ea` |
| 动作 | 一次 Abaqus/Standard analysis，interactive；额外 Abaqus 调用 0 次 |
| 资源请求 | CPU=1，GPU=0，memory=2048 MB；不是 OS 硬限制或许可证预留 |
| 观察 | START_INTENT 起 300 秒，只停止观察等待；不终止、不重试、不删除输出 |

原摘要是 `execution.models.digest(manifest.body)` 的规范化内容摘要，**不是排版 JSON 文件的字节 SHA-256**。本轮不修改 `execution_authorized=false` 或旧 `NOT_AUTHORIZED_YET`：它们是冻结时事实；后来的用户授权另存于对话及 `real_001/AUTHORIZATION_SCOPE.json`。不要改成 true 来“解锁”。

完整实验根：

`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a`

| 用途 | 实际绝对路径 |
|---|---|
| 输入 | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\engineering\axial_bar.inp` |
| cwd | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\engineering` |
| scratch | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\engineering\scratch` |
| 原始观察目录 | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\observations` |
| 结果提取目录 | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\extracted` |
| 离线核验 cwd | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\client_cwd` |

本轮检查时 engineering 仅有原输入和空 scratch；observations、extracted 为空，没有该 Job 的已有求解输出。这只是读取时事实，不是未来的排他预留。

## 2. 原控制器能否直接复用：实际接口审查

| 实际文件与函数 | 实际能力和边界 |
|---|---|
| `examples/agent_first/abaqus_probe_review.py:review`（15 行）、`main`（63 行） | 复核规范化清单、34 项实际材料、公开 prepare/inspect 预览和 `job.*` 冲突。无启动、Job 查询、START_INTENT、一次尝试锁或 300 秒监督。支持的 CLI 参数仅 `--source`、`--manifest`、`--expected-manifest-digest`。没有 `--execute` 等参数。 |
| 同文件 `no_execution`（73 行） | 审计钩子拒绝 subprocess.Popen、os.system、os.startfile、SQLite 连接及 socket.connect。材料核验不执行 BAT/EXE/环境文件。 |
| `examples/agent_first/abaqus_offline_preview.py` | 公开离线 prepare/inspect/可选 JSON 导出。不是实验启动器；本轮不重跑导出覆盖旧 preview.json。 |
| `abqjobpilot/execution/process_handles.py:ProcessReference`（9 行）、`exit_evidence`（38 行）、`close`（49 行） | 可复用的 Windows 进程引用：核对 PID、创建时间和映像；从保留引用取得退出证据。`close` 关闭它自己打开的进程句柄，无 terminate/kill 调用，无 Job 句柄。它本身不启动实验、不枚举完整成员集合、不控制观察预算。 |
| `OBSERVATION_AND_ACCEPTANCE_PLAN.md` 第 3、27、31、51、53 行 | 明确声明“没有可执行启动入口”；文件日志、START_INTENT、300 秒停止等待等是方案，不是已实现的 controller finally/退出行为。 |
| 清单 `body.windows_call/environment_policy/observation/stop_policy` | 精确命令、环境字典和观察要求是数据。未绑定一个实际控制器文件/摘要/CLI，也没有固定 Codex 会话 ID 或必须由 Codex 调用的宿主条件。不能把数据视为可执行保护机制。 |
| `real_001/HOST_LIFECYCLE_PRECHECK.json` | 历史探针结果，没有可运行的探针入口或控制器程序。记录的是当时工具进程，不是操作者终端，更不能以历史 PID 作为当前身份。 |

额外静态核对了实验根内已存在的 `invoke_package_recheck.py`、`invoke_offline_client.py`：它们只派生普通 Python 离线客户端，使用 PIPE/communicate 并回写原准备报告。**不要重跑这两个中间脚本**，既不能启动实验，也可能覆盖旧证据。其 finally 关闭普通进程引用/管道/Popen 句柄，没有 terminate；这不证明一个尚不存在的 Abaqus 控制器具有相同安全语义。其余 create_inputs.py、freeze_package.py、collect_evidence.py 是准备/证据生成脚本，保留，不运行、不清理。

### stdout/stderr 与退出语义

- 当前可运行的只读核验入口向调用它的 stdout 打印一条 JSON，成功退出 0、拒绝退出 2；无须 Codex 持续读取。普通 PowerShell 变量可捕获该输出。
- 未来 Abaqus 调用在清单中要求 stdin=DEVNULL、stdout=`observations\stdout.bin`、stderr=`observations\stderr.bin`，**独占新建普通文件，不用 PIPE**。这是待实现要求；当前文件不存在，不宣称已有日志句柄所有者。
- 无实际控制器可供审查其超时/异常/finally/正常退出路径。因此不能将“未找到 terminate 代码”推成“未来控制器不会终止后代”。普通进程句柄关闭和带终止语义的 Job 关闭必须区分，外层宿主也必须检查。
- 原只读检查能发现同名输出，但不持久化或互斥保留“一次尝试”。启动意图/未知状态阻断尚未由可调用实现保障。

## 3. 原材料与承载差异

| 项目 | 本轮处理 | 原摘要是否覆盖 |
|---|---|---|
| 输入、Profile、预览、BAT、安装引用、观察方案 | 全部保持；原检查成功 | 清单的 34 项材料逐项覆盖，重新检查匹配 |
| 固定命令、参数、cwd、子进程环境策略 | 不修改、不重拼、不执行 | 原 body 覆盖 |
| Dev 源码/执行核心/版本 | 不修改；53 项历史源码摘要匹配 | 另与 SOURCE_HASHES.json 核对 |
| 操作者自行打开桌面终端 | 仅说明，Codex 不创建/调度 | 不是旧工具探针的同一上下文；实际尚待操作者证明 |
| 子进程环境 | 仍须使用清单完整替换字典 | 直接在交互终端运行 BAT 会继承终端环境，不自动满足冻结策略 |
| 实验控制器 | 原包没有，本轮也没有新增 | 未来新文件/入口、启动和生命周期逻辑不被原 SHA 覆盖 |
| 本交接文档与核验记录 | 新增于 operator_handoff_001 | 不属于原 SHA 覆盖材料；不赋予执行权限 |

因此本轮不是“既有执行控制器换一个宿主即可使用”的情形。后续若需要补最小一次性控制器，应保留原包、单列新控制器及其摘要、命令和验证证据供审查；不能以旧清单仍存在为理由声称整条新执行路径已批准。本轮不重复询问同一模型/资源的泛化授权，也不实施这个新入口。

## 4. A：操作者可执行的普通 Python 材料核验（Abaqus 调用为 0）

请操作者从 Windows 桌面自行打开普通 PowerShell。不要让 Codex、其终端工具、计划任务或服务代开。以下步骤不证明终端不在 Job 中，不满足实际启动的全部条件；执行后仍停在第 5 节。

先阅读 `D:\XianLab\envs\ENVIRONMENTS.md`，运行登记解释器的最小核验。无需安装依赖、激活环境、改 PATH 或设置全局 PYTHONPATH。

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\client_cwd'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -c 'import sys, platform, hashlib, json, pathlib; print(json.dumps({"executable":sys.executable,"python":platform.python_version(),"platform":platform.platform(),"required_stdlib_imports":"OK"}))'
if ($LASTEXITCODE -ne 0) { throw 'Interpreter verification failed; stop' }
git -C 'D:\Projects\abqjobpilot_dev' branch --show-current
git -C 'D:\Projects\abqjobpilot_dev' rev-parse HEAD
git -C 'D:\Projects\abqjobpilot_dev' diff --name-only --diff-filter=U
```

本轮实测解释器为上述 LangChainEnv，Python 3.12.10，Windows 11 10.0.26300；仅需标准库及 Dev 本地离线模块。预期分支 Develop、HEAD `fb7912ec9e0107b18f65948b147c87579c87cded`、无冲突。已有未跟踪成果允许存在，不要求干净；不匹配时停止报告，不自动恢复。旧 Run 001 协议中的 `envs\conda\LangChainEnv` 是迁移前历史路径，本轮使用现行登记路径。

执行下面**现有**核验脚本；这里的参数逐项来自实际 `main()`，不会启动 Solver。先检查脚本自身摘要是一个变更检测，不是数字签名。

```powershell
$reviewScript = 'D:\Projects\abqjobpilot_dev\examples\agent_first\abaqus_probe_review.py'
if ((Get-FileHash -LiteralPath $reviewScript -Algorithm SHA256).Hash.ToLower() -ne 'ade4b27a2fee0dcab148be887243626e64e39493f6ae1653851e09046d0dfe30') {
    throw 'Review entry changed; stop'
}
$materialReview = & 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B `
  'D:\Projects\abqjobpilot_dev\examples\agent_first\abaqus_probe_review.py' `
  --source 'D:\Projects\abqjobpilot_dev' `
  --manifest 'D:\Projects\abqjobpilot_dev\docs\agent_first\run_010\EXPERIMENT_MANIFEST.json' `
  --expected-manifest-digest 'sha256:04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6'
$materialReviewExit = $LASTEXITCODE
$materialReview
if ($materialReviewExit -ne 0) { throw 'Material review refused; stop, do not change inputs or retry a launch' }
```

预期 JSON：`status=OFFLINE_PACKAGE_UNCHANGED`、同一 experiment_id/manifest_digest/preview_digest，`run_created=false`、`runtime_verified=false`、`output_reserved=false`、`execution_authorized=false`。最后一个字段是此离线工具的固定契约，不否认用户另行批准，也不应改写。

本轮在上述非仓库 cwd 实际运行了该 Python 命令，退出 0，结果保存为本目录 `MATERIAL_RECHECK.json`。**这不是操作者终端实测结果**。操作者可将自己的结果另存一次：

```powershell
$materialReview | Out-File -LiteralPath 'D:\Projects\abqjobpilot_dev\docs\agent_first\run_010\operator_handoff_001\OPERATOR_MATERIAL_RECHECK.json' -Encoding utf8 -NoClobber
```

该可选命令只写交接报告，不写实验输入/输出。文件已存在时保留，不覆盖；也可直接交回屏幕上的 JSON。本轮没有替操作者生成该文件。

常见拒绝：`PACKAGE_CHANGED`（材料/预览不匹配）、`OUTPUT_EXISTS`（同 Job 输出）、`PACKAGE_UNAVAILABLE`（缺失/读取失败）、路径/输入子集对应错误。停止并交回原因码；不要换 Job、目录、输入、入口或重建清单继续原批准。

## 5. 必须在实际控制器内完成的生命周期准入：当前待实现/待验证

**本节当前不能执行，不能由第 4 节或一个独立探针的成功替代。** 没有实际控制器，便没有“实际控制器上下文”的动态证据。本轮不添加一个独立探针，再把它包装成控制器已获准启动。

未来最小控制器须在负责实际创建批准进程的同一个 Python 进程中、紧邻调用之前，记录并检查：

| 必需记录 | 合格条件 | 当前状态 |
|---|---|---|
| 控制器文件/摘要、实际解释器映像、PID+创建时间、观察时间 | 与经审查的新控制器一致；核对 venv 重定向后的实际进程身份，不能仅用父启动器 PID | 未记录：控制器不存在 |
| `IsProcessInJob(GetCurrentProcess(), NULL, ...)` 调用是否成功 | 成功且明确不属于任何 Job；失败、仍在任意 Job、未知均拒绝 | 操作者上下文未验证 |
| stdout/stderr 句柄类型、文件目标及归属 | 批准目录独占新建文件；明确谁持有/继承；不依赖 Codex 管道持续读取 | 仅冻结策略，未取得运行句柄 |
| 300 秒路径、异常/finally/正常退出路径 | 停止观察不终止后代；不关闭带终止语义的 Job；不使用 run(timeout) 自动杀直接子进程或 with Popen 隐式等待 | 只有设计文本，无实际路径可测 |
| 外层终端/Windows 会话条件 | 由操作者维持存活；无受管工具超时强制结束控制器 | 操作者尚未提供证据 |

不改变 Job 配置，不继续尝试脱离；即便查询到某 Job 没有某个 kill 标志，本次最小路线也不接受“仍在 Job 中”。“不在任何 Job”的一次观察只证明该时点自身，不保证未来系统注销/关机/人为终止不存在；操作纪律仍必需。

若以后用普通 Python 固定夹具验证控制器退出行为，应使用**同一控制器入口/同一宿主条件**，保存真正身份、日志和后代存续证据；不得借原 Codex 探针结果或一个先前独立进程的结果放行。此动态验证尚未运行，本轮不创建测试后代。

## 6. B：唯一真实启动步骤 — 当前不可执行

**没有已实现、可给出准确调用参数的原冻结实验控制器；本交接不提供虚构的启动命令。不要将 `abaqus_probe_review.py` 添加 --execute，不要重跑中间脚本，也不要直接运行 BAT 代替缺失入口。**

原清单确有唯一准确的候选 Windows 调用，操作者可用以下只读命令显示原值审阅（不会解释执行字符串）：

```powershell
$frozenPackage = Get-Content -LiteralPath 'D:\Projects\abqjobpilot_dev\docs\agent_first\run_010\EXPERIMENT_MANIFEST.json' -Raw | ConvertFrom-Json
$frozenPackage.body.windows_call | ConvertTo-Json -Depth 4
$frozenPackage.body.actions | ConvertTo-Json -Depth 4
```

其 `command_line` 原文是以下**数据，不是本轮可执行操作步骤**：

```text
"C:\Windows\System32\cmd.exe" /d /s /c ""D:\ABAQUS2024\Commands\abq2024.bat" job=r010_bar_a19d17ea input=axial_bar.inp analysis interactive cpus=1 gpus=0 memory="2048 mb" scratch="C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\engineering\scratch""
```

它还必须伴随原 `application`、cwd、shell=false、close_fds=true、CREATE_NO_WINDOW、DEVNULL、独占文件日志和完整替换环境字典。复制一行到 shell 不会同时实现这些条件；也不能用 Invoke-Expression 或新的拼接方式解释它。

使 B 成为可执行步骤的最小缺口如下（**是待审实现要求，本轮未新增执行程序**）：

1. 一个只服务本实验的一次性控制器及明确 CLI/摘要；不扩展为长期 Runner、Backend、Windows 服务或通用命令执行器。
2. 在实际启动进程中重新核对全部原引用材料、预览、路径、当前分支/冲突、Job 输出及观察日志冲突，并按第 5 节最新生命周期结果拒绝不合格宿主。不能信任先前核验 JSON 或简单 approved=true。
3. 同一实验的互斥准入、持久化且独占创建的启动尝试记录。先写授权对象/摘要/时间/START_INTENT，再至多调用一次；已有 START_INTENT、未知启动结果或其他冲突均阻断。数据库/文件中没有输出不等于从未尝试。
4. 原样使用清单调用及环境；开始前取得日志写入能力，不把控制器继承的交互终端环境传给求解器，不修改安装/VS/许可证配置。
5. 真正实现并离线验证 300 秒预算、过程身份记录、日志错误/异常/正常退出非终止路径、只读结果检查边界。失败不自动重试、修复环境、删除文件或追加任何 Abaqus 调用。
6. 将新增控制器、其调用方式和验证材料作为**原 SHA 不覆盖的补充执行对象**交给操作者审阅。旧实验已授权不等于未存在的新实现也自动被原 SHA 覆盖；不能擅自开始。

这些缺口补齐前，B 保持 `BLOCKED_NO_EXECUTION_CONTROLLER`。第 4 节可以完成材料只读核验，之后把结果交回并停止。

将来 B 具备经审查入口后也必须保持：终端及 Windows 会话存活；不要关闭窗口或按 Ctrl+C 来实现停止等待；300 秒到期不 terminate/kill、不执行 Abaqus terminate、不重试、不删除输出/scratch。失去应答或启动不确定时，**不再次执行启动命令**，保留记录只读审查。未确认终止不写成 Solver 已停止、失败或取消。包装器失败也消耗一次尝试，不修复后重跑。

## 7. 结果、证据与固定数值判据

当前仅有准备材料和 BLOCKED 证据。以下是原方案中的未来目标，**没有创建空文件冒充运行记录**：

- `observations\stdout.bin`、`stderr.bin`：原始标准输出/错误，必须独占新建。
- `observations\processes.jsonl`、`file_observations.jsonl`：带实际时间及来源的外部实验控制器观察；不是正式 Project Run 历史。
- START_INTENT 的具体文件契约/格式/入口目前未实现，不能假设某个文件名已具有一次性保护。
- `engineering\r010_bar_a19d17ea.dat`：本次打印数值来源；ODB 只可记录文件身份，本次不做内容验证、不追加 Viewer/Abaqus Python。
- `extracted\measurements.json`：仅在读到无歧义最终 step1/time1、正确实体/分量时产生；当前没有通用 DAT 自动成功解析器。

| 实体/分量（最终 step1/time1） | 参考 | 冻结容差 | 当前实际/判定 |
|---|---|---|---|
| node2 U1 | +0.01 mm | abs=1e-6 mm，rel=1e-4 | 未取得 / NOT_RUN |
| element1 积分点 S11 | +1 MPa | abs=1e-4 MPa，rel=1e-4 | 未取得 / NOT_RUN |
| node1 RF1 | −1 N | abs=1e-4 N，rel=1e-4 | 未取得 / NOT_RUN |

比较采用 `abs(actual-reference) <= max(abs_tol, rel_tol*abs(reference))`；还包括约束位移≤1e-8 mm、node2 RF≤1e-4 N、X 力平衡残差≤2e-4 N。不得根据实际结果改参考或容差。打印结果缺失/歧义就是证据不足，不追加调用。

操作者现在可以交回：第 4 节解释器结果、分支/HEAD/冲突结果、材料核验 JSON 和错误码。未来有实际控制器后再交回其摘要、同进程生命周期核验、尝试记录、原始日志、身份/退出观察及数值提取；不要提供全环境变量、凭据、生产数据或整个 Runtime。Codex 只读审查，不重放启动。成员集合仍未知时，即使打印数值成立，整体也保留 PARTIAL。

## 8. 本轮验证及保留事项

- 基线：Develop@fb7912ec9e0107b18f65948b147c87579c87cded，0.3.0.dev0，无冲突；先前未跟踪成果保留。
- 实际运行：登记解释器/标准库核验；现有只读包复核，非仓库 cwd，退出 0；34 项实际材料及预览匹配。不是仅验证 JSON 自身。
- 53 项原源码与历史摘要一致；106 项原文档、real_001、源码、实验文件及中间脚本建立前后保留核验，见 `PRESERVATION_BASELINE.json`、`VERIFICATION.json`。
- 仅文档/证据变化，没有新增辅助程序或修改源码，因此没有重跑全量回归；以前的 204/452 等数字不是本轮测试结果。
- 没有在本轮进行新的生命周期探针、创建测试后代、清理进程或删除文件；普通 Python 核验命令均正常返回。本轮无新的长期进程/私有连接凭据需要清理。
- 旧三个测试目录和五个中间脚本保留，未清理；本轮只检查它们的位置和相关脚本，不重新执行。其清理阻断记录仍属于原准备阶段，未被本轮抹去。
- 本轮不访问 Stable，不操作生产数据、共享配置、安装、版本、Git 写操作、真实 Backend 或授权核心。

交接材料完成不表示操作者终端通过、不表示已有真实启动入口、不表示 Abaqus 运行或 Runtime 通过。本轮停止，等待操作者完成允许的只读核验或另行审查所列缺口。
