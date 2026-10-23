# Run 010 — 待批准的观察、数值验收与停止边界

本文件是未来一次性实验的方案，没有可执行启动入口。所有路径、参数和材料摘要以 `EXPERIMENT_MANIFEST.json` 为准。实际调用还须用户另行明确授权，并在调用前只读复核 manifest 与文件摘要、输入预览、目录身份及同名输出。发生变化拒绝本次调用并重新审查；不能就地重建预览后继续使用原批准。

## 唯一模型与参考值

单位为 N、mm、MPa（1 MPa=1 N/mm²）。一个 T3D2，节点1=(0,0,0)，节点2=(10,0,0)，连接1→2，截面积1，E=1000、nu=0.3，小变形线弹性；STEP 不启用 NLGEOM（首次静力步默认小变形的参考语义）。节点1固定U1/U2/U3，节点2固定U2/U3，只有节点2的轴向U1自由。无转动自由度。向节点2全局X施加+1N；无质量/惯性/温度/外部依赖。单步 STATIC 的初始/总/最小/最大步长为1/1/0.00001/1。预期最终时间=1。

独立解析：k=EA/L=100 N/mm；u=F/k=0.01mm；应变u/L=0.001；S11=E*u/L=+1MPa；节点1 RF1=-1N，反力大小1N。`ANALYTICAL_REFERENCE.json` 用有理数另算，不从求解器输出反推参考。

固定容差（运行前冻结）：节点2 U1 相对误差≤1e-4 或绝对误差≤1e-6mm，采用 `abs(actual-expected) <= max(abs_tol, rel_tol*abs(expected))`；S11 与节点1 RF1 各 abs_tol=1e-4、rel_tol=1e-4，分别MPa和N。约束位移三个节点1分量和节点2 U2/U3 均 abs≤1e-8mm。节点2反力应近零（abs≤1e-4N）。全局X外载+两端反力平衡残差 abs≤2e-4N。符号必须核对，不能只比绝对值。

## 输出与独立读取

输入显式 NODE PRINT 输出每个节点的U、RF表；EL PRINT 输出BAR积分点应力S。主要数值来源是本次 `.dat` 的最终 step1/time1 表。**不批准额外 Abaqus Python、Viewer、CAE 或 ODB提取调用**；Abaqus调用预算只有一次 analysis。供应商自然产生的ODB可以登记身份，但其存在、大小或可见性不成为数值验证通过。

运行后由控制器使用登记的普通Python或只读文本工具读取 `.dat`，保存原文件字节摘要、明确表头、节点/单元/积分点、步/增量/时间、行号区间与数值字符串到 `extracted`。首次实际表格版式尚未验证，本轮不预置一个猜测版式的“成功解析器”。人工辅助逐表核对并用独立算术比较上述固定标准；读取不创建执行历史。若无法无歧义确定最终表/实体/分量、缺表、NaN/Inf/截断/星号溢出或版本不明，结论为 NUMERICAL_EVIDENCE_INSUFFICIENT，不能选一个看似接近的数值、补成0、改容差或追加提取调用。需要额外供应商调用必须再次单独授权。

这不是通用结果验证器。提取 JSON 是控制器观察，不伪装成 Supervisor 已持久化的 ValidationRecord。首次实际格式确认后才适合实现固定解析器；科研目标和算法不进入平台层。

## Windows 候选调用与环境

使用绝对 `C:\Windows\System32\cmd.exe`，显式 `/d /s /c` 执行已经冻结的绝对BAT路径与固定参数；Python未来若用于控制，采用 `Popen` 的明确 application/executable、固定 Windows 命令行，shell=False、close_fds=True、CREATE_NO_WINDOW。cmd是明确受审的BAT解释器，不是可由客户端选择的任意shell入口。外层双引号和内层路径/含空格参数引号见 manifest；所有字段固定，无插值输入、百分号、延迟扩展或额外命令。cwd=engineering根；input=axial_bar.inp；job唯一；scratch为其固定子目录。

manifest 环境字典完整替换父环境，Windows基础路径显式固定，用户/临时配置路径重定向隔离目录。没有读取现用户环境文件，没有执行新环境脚本。所选BAT内部的Intel/站点环境处理属于这一次调用的已声明行为；不附加命令补齐环境或探测许可证。真实行为尚未验证。

stdout/stderr 分别用独占新建二进制文件记录到 observations，禁止PIPE积压阻塞。控制器单次分析读取每文件最多16MiB，超出报告证据限额，不截断原始输出冒充完整。这个读取限额不能限制子进程继续向日志写入，也不是磁盘配额；超限或磁盘错误不得假报成功，应转人工处理，仍无自动终止权限。单次启动无后台安装、无系统服务、无长期Runner、无产品Backend注册或真实Grant。

## 进程与文件观察顺序

1. 取得另行批准后，复核固定材料和同名输出不存在；创建仅属于该实验的外部控制器尝试ID，独占记录 START_INTENT 与时间、manifest/input摘要。它不是正式 Run，不写Project库/queue。
2. 调用前做限定元数据基线：PID、父PID、创建时间、映像路径；不采集无关命令行、环境或文件。调用明确BAT一次，保留直接cmd进程的Popen OS句柄。
3. 以50ms目标采样间隔观察候选后代链；关系只是候选。对仍可见候选取得 ProcessReference，核对PID+创建时间+映像，并结合启动时间、已知安装映像、当前尝试与输出证据归属。每条记录注明 DIRECT_HANDLE / OS_CANDIDATE / INFERRED_ASSOCIATION；不能只凭父PID或名称归属。查询失败和短命成员漏采均记录未知，不使用测试控制器“预期成员表”补全。
4. 原子追加控制器观察（记录写出后flush；写失败立即报告证据不足，不再推进成功结论）。持有的进程引用可证明该身份退出及退出码，PID消失不能。句柄整数不作跨进程持久身份。launcher退出不会停止对已归属成员的观察，也不会解除输出保护。
5. 原始输出以事前不存在、固定job/cwd、文件身份/创建观察/最终摘要/时间线关联这一次尝试；对仍可能被写的文件只做历史观察，不称最终快照。目录重复使用或输入被改立即使结果归属存疑。
6. 保留 `processes.jsonl`、`file_observations.jsonl`、`stdout.bin`、`stderr.bin`、人工/控制器分析及 `extracted/measurements.json`（均为未来文件，当前不伪造空运行证据）。版本从实际横幅和已冻结安装映像联合判断；仅包装器名不是运行版本证明。

没有静态证明 Abaqus 必需成员集合完整。本次实验是收集其真实启动链，不承诺任意进程树发现。可以取得直接cmd及成功打开引用的成员退出事实；不能确认的阶段/成员记 UNKNOWN。即便所有**已观察**成员退出也不能推出全体必需成员退出。首次观察如不足以建立完整性，总结必须保留 PROCESS_SET_COMPLETENESS_UNKNOWN，不宣布Runtime或产品恢复能力验收。

## 成功、失败、超时和资源释放分别判断

| 维度 | 通过所需证据 | 缺失/矛盾处理 |
|---|---|---|
| 入口和版本 | 冻结入口链身份、实际横幅/版本与运行映像一致 | VERSION_UNCONFIRMED；不运行版本探测补齐 |
| 分析阶段 | 本attempt的Standard完成状态、最终步/时间、日志/MSG/DAT/STA可用证据相互一致，无致命错误或未收敛 | FAILED 或 EVIDENCE_INSUFFICIENT；单行成功文字不足 |
| 进程退出 | 明确归属身份的保留句柄返回退出码；必要集合完整性另有依据 | 未知就保留未知；不能由ODB/结果表推导退出 |
| Artifact | 事前不存在、本attempt产生、稳定读取的文件身份与摘要，输入仍匹配 | 旧文件/增长/冲突/读取失败拒绝有效归属 |
| 数值 | 独立读取最终表并符合冻结解析值与容差 | NUMERICAL_FAIL / NUMERICAL_EVIDENCE_INSUFFICIENT，不覆盖进程或Solver结论 |
| 收尾 | 控制器已观察到的成员退出；日志关闭/本控制器句柄关闭，scratch状态单列 | 关闭观察句柄不等于终止Solver；集合不明不能声称全部资源释放 |

观察总预算从START_INTENT起 **300秒**，包括启动/许可证等待；不是Solver wall-time硬限制。Python3.12标准库 `subprocess.py:Popen._wait` 的Windows分支在WAIT_TIMEOUT时抛 TimeoutExpired，不终止进程；而 `subprocess.run(timeout=...)` 会kill直接子进程，因此禁止将后者用于本次真实调用。不使用 `with Popen(...)` 自动等待收尾，不把 `communicate` 超时等同于结束。推荐非阻塞poll/ProcessReference.exit_evidence与单调时钟预算，不设置Abaqus名为timeout的其他产品参数。

超时/观察写入失败/控制器退出：停止等待和后续派发，保存 OUTCOME_UNKNOWN、已知身份/最后观察时间及人工介入要求。没有自动终止、重试、改参数、继续/恢复、输入修正后的再提交。遗留进程、输出和scratch保留；不得按名称杀进程、删除仍可能使用的文件。本次批准清单**不含任何停止命令**。若以后需要停止，另行给出身份核对、作用范围和新的批准请求；不把停止藏在清理中。没有正式Run可“解锁”，也不将控制器清理变成业务对账。

本轮的通过状态只表示这些动作可审查。未运行造成的版本/语法/许可/进程集合/输出版式未知属于实验拟回答的问题，不得当作已获得的运行证据。
