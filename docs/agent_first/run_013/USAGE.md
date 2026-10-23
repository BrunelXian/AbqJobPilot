# Run 013 固定 Standard 服务候选

本轮真实 Abaqus 调用 **0**。以下真实提交步骤尚未执行；必须先取得对本清单的明确批准。原 Run010/011 授权不覆盖新 Project、Job、目录或宿主条件。

## 唯一待批准对象

- 实验：`run013_e52135d71d2c43d2a45301c586cbfb7e`
- 清单：`D:\Projects\abqjobpilot_dev\docs\agent_first\run_013\ACCEPTANCE_MANIFEST.json`
- body 摘要：`sha256:3c59461d53e658eb9894d6936bd405f85a7f27b6ebc3deb5343c81d8411ceebe`
- Project：`p_9204fe8fced549d28d8bd62d1b2f8455`
- Project instance：`pi_776faf62f2d64a4ab23e83c53b665788`
- Plan：`plan_ed1ac113f464496497d8787268189c4f`
- Plan 摘要：`sha256:62dc0aa95bad8c5e0d61d62515a4451a9d3f694016339fe68d7ca2c55239d46a`
- Run：尚未创建；只由公共提交的接收事务生成，在启动前持久化。

隔离根：
`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e`

相对该根：

| 内容 | 位置 |
|---|---|
| 原生服务 Project / 存储 | `project\execution.sqlite3`（新建实验 v3，未迁移旧数据） |
| 输入副本 | `engineering\axial_bar.inp` |
| cwd | `engineering` |
| scratch | `engineering\scratch` |
| 固定输出 | `engineering\r013_bar_d48c54f7.*` |
| 输出一次意图 | `engineering\.r013_bar_d48c54f7.intent.json` |
| stdout/stderr | `project\runtime\standard_runs\<接收事务生成的RunID>\stdout.bin`、`stderr.bin` |
| owner 日志 | `logs\standard-owner.stdout.txt`、`standard-owner.stderr.txt` |
| 私有连接/授权交接 | `private`（不导出、不发到聊天中） |
| 公共回执和诊断导出 | `session` |

输入逐字节摘要保持 `sha256:e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3`。副本保留原 Heading，**新 Job 与输出目录不同**；旧 Job 文件不是新 Run 的证据。

唯一入口 `D:\ABAQUS2024\Commands\abq2024.bat`；一次 Standard analysis，interactive，CPU1、GPU0、memory=2048 MB，额外 Abaqus 入口调用0次。参数是 Abaqus 请求，不是 OS 硬限额。完整 Windows 调用字符串由产品代码生成并另列在 CALL_REVIEW.json，供审查；实际执行只能通过服务，不建议复制该底层字符串绕过服务。

## 现在可用的无 Solver 检查

双击 `D:\Projects\abqjobpilot_dev\examples\agent_first\R13_01_Check.vbs`。

等价命令（本轮已从非仓库 cwd 实际运行）：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B 'D:\Projects\abqjobpilot_dev\examples\agent_first\standard_service.py' check
```

预期 `MATERIALS_MATCH_NO_EXECUTION`。该命令核验清单规范化摘要、引用代码/安装声明、输入和输出冲突；不创建 owner、不批准、不提交。它不会把检查进程当成将来的 owner，实际宿主准入仍由实际 owner 内 `standard_process.check_host` 在调用前重新判定。

本轮同一绝对脚本的 `prepare` 已执行一次，结果为 `PREPARED_NO_GRANT_NO_RUN`。不要再次 prepare 或删除清单来创建另一个实验。

## 批准后的分离步骤（本轮未执行）

1. **可信操作者登记精确批准**：通过现有本地独占租约调用 `standard_contract.issue_execution`。已提供 `standard_service.py authorize --approval-source <实际明确授权来源>` 入口；它只接受审计来源引用，不是 `approved=true`，不启动 Backend。必须在首次 owner 启动之前调用；活动 owner、已有 owner 历史、已有 Grant/输出均不能通过这个入口绕开。批准范围应明确对应上述清单摘要。没有授权时不要调用。
2. 双击 `R13_02_Start_Service.vbs`。仅启动已有 Supervisor，缺少已登记许可时拒绝；不提交 Run。
3. 双击 `R13_03_Submit_Once.vbs`。使用薄公共 Python 客户端 inspect_plan/submit，接受后保存 `session\receipt.json`。意外断线只查询原键 `run013-standard-once`；不要换键、Plan、Job、目录或再次批准。
4. 双击 `R13_04_Open_Dev_GUI.vbs`。现有 Dev GUI 连接该 Project/Run。查看接受回执、创建阶段、日志字节/固定标记、历史进程退出、Solver、DAT 和 ODB 各维度。
5. 在实际进程运行阶段正常关闭**整个 GUI**，再双击第4项。GUI 不启动 owner、重新提交、批准、恢复派发或清理凭据。需记录关闭前后 owner/worker 的 OS 身份和日志增长；若真实模型太快已完成，不能把这个场景记为“运行时跨 GUI 退出”通过，也不因此取得第二次调用许可。
6. 第5个入口 `R13_05_Read_Report.vbs` 读取并导出同一诊断快照，不重新验证进程/产物。必须有可连接的 owner。公共源码入口为 `standard_client.py`（只提交）及 `FakeClient.run/events/progress/validations/diagnose/export_diagnostic`；不是新 SDK 框架。
7. 审查完成后可用 `R13_06_Stop_Owner.vbs` 请求 owner 在观察工作返回后正常结束。它不停止 Solver、不清除未解决 Run、槽、意图或输出，也不会移除待审查证据。owner 已退出时，不自动重启或恢复。

所有点击入口都在 `D:\Projects\abqjobpilot_dev\examples\agent_first`。无需拼接长 PowerShell 命令，也不需要为 GUI 查看维持一个 PowerShell 窗口。**保持 Windows 会话存活**；终端关闭、注销、系统重启和 owner 崩溃后的 Abaqus 存活均未验证。不要使用关闭 owner 窗口或 Ctrl+C 作为求解停止方法。

## 准入、结果与限制

实际 owner 在创建前重新校验计划/授权/材料、OS owner 租约、自己的身份、Job 查询和文件 stdout/stderr，再检查同名输出及持久意图。已写意图、输出冲突、存储失败、过期/不匹配许可都不能通过重跑消除。

300秒为创建返回后开始的观察期限；创建耗时单列。期限届满只停止观察，不终止、不重试、不删除输出，不启动后台观察者。包装器 exit0、已记录成员 exit0、Solver 文本完成和数值通过分别记录。

三项冻结主标准：Step1 / Increment1 / final time1；node2 U1=0.01 mm±1e−6；element1 / integration point1 S11=1 MPa±1e−4；node1 RF1=−1 N±1e−4。CP936、实体/步/完成页脚及重复/冲突检查保持。只读 DAT/STA/MSG/LOG，不打开 ODB，不追加 Abaqus Python、CAE、Viewer 或其他调用。

首版成员完整性/整体退出仍 UNKNOWN，所以验证成立也不会自动释放单槽、输出意图或恢复派发。本轮没有真实对账/重新挂接/强制停止能力。若不能取得完整退出证明，整体必须 PARTIAL，已成立的 Solver 和数值维度独立保留。

摘要算法：现有 `models.canonical_json(body)`（UTF-8，键排序，无空白，严格 JSON，无浮点）再 SHA-256，加 `sha256:` 前缀。摘要仅覆盖 body，不包含外层 content_digest；materials 各项为实际文件字节 SHA-256/大小。它证明对象一致，不是授权签名。材料改变后原批准不适用。
