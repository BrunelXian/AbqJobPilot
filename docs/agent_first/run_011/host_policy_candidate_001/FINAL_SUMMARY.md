# Run011 宿主政策修订候选与一键自检

**候选可审查；真实 Abaqus 0次，真实 execute 0次。新宿主契约尚未批准。**

候选清单：`D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\host_policy_candidate_001\CANDIDATE_MANIFEST.json`

**body SHA-256：`d427264f99b2e1128a50d171c09b852cc57662ee002de5c31ba7cdc9d60b840c`**。

旧候选 body `645389d8f25942e908f04dca25fbefed820d6f63b35fcfb6c308977b6c016824` 保持不变。原实验 body `04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6` 同样保持。新摘要只冻结候选对象，不表示用户批准，也没有产生任何可用执行Grant。

## 操作者证据已归档

来源是用户明确提供的 `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run011_Host_81de310805b8442da126dcb117fe3fa6\case_host\HOST_REPORT.json`，并非 Codex 工具实例。23项原始记录逐字节复制到本包 operator_evidence，来源/大小/摘要见 OPERATOR_EVIDENCE_INDEX.json；原文件不改写。

交叉核对了观察者上下文、controller_ready、function_returned、worker身份/启动器/完成自报、原控制器报告、7项有序事件、心跳及独立OS退出记录。历史PID未被重新打开或探测。结论：

| 历史观察（UTC） | 证据 |
|---|---|
| 10:21:54.021 / .023 | 实际控制器31852、venv启动器32904分别由PowerShell保留的OS引用确认退出0 |
| 10:21:54.027–.048 | 同一worker13024仍存活，心跳从560增至580字节；前后OS观察绑定同一创建时间及映像 |
| 10:22:03.491 | worker13024和其venv启动器13572分别退出0；文件自报另列，未代替OS退出依据 |

函数返回、实际控制器退出和venv启动器退出保持分开。结论只覆盖那次固定Python实验，条件是PowerShell和Windows会话保持存活；不证明关闭终端、完整Job层级/所有者或Abaqus进程链。原夹具报告中的总体成员集合UNKNOWN仍保留。此次归档不把历史fixture意图转换成真实实验意图。

## 最小实现差异

| 范围 | 实际处理 |
|---|---|
| 旧材料/业务核心 | 全部保留，不修改正式执行核心、数据库、版本、真实实验目录或旧候选 |
| `host_policy.py` | 新固定政策：`evaluate`是check/admit唯一判定来源；自身和父链Job查询必须成功；固定解释器/PowerShell父链身份、活性、会话和控制台关联必须成立 |
| `engine_adapter.py` | 保留原engine所有函数体，仅将admit导入改为新政策；测试逐字核对这一差异。无第二套队列、数据库或监督器 |
| `package.py` / `evidence.py` | 原34+旧21材料复核；新33材料及历史归档交叉核对；同一真实执行参数、输出身份和尝试记录 |
| `candidate.py` | 默认只读check，另有只读report和将来另行批准才可调用的execute；execute在自身进程重查，不接受旧check作为放行凭据 |
| 一键包装 | SELF_CHECK.cmd → 固定Windows PowerShell → self_check.ps1 → 固定登记Python的check。没有参数转发/execute回退，报告只写新临时目录；提供JSON机器接口 |

**待审查的契约弱化不能省略**：原“控制器不属于任何Job”改为“固定操作者父链、成功查询及当前可观测条件成立，并接受终端/会话保持存活的有限政策”。新政策不证明未知上层Job不会终止后代，也不认证终端是人工打开的。此次工具自检也能满足政策，恰好说明它不是操作者身份认证。不能仅看到SELF_CHECK_PASS就宣称承载生命周期已被普遍证明。弱化后的真实路径需要新的明确批准，原授权不自动覆盖。

## 实际验证

登记环境仍为 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10，pytest9.1.0。Dev仍是Develop@fb7912ec9e0107b18f65948b147c87579c87cded，无冲突，0.3.0.dev0不变。已有未提交/未跟踪成果不清理。

- 第一轮30项通过；补充默认/帮助/check/report无写入、材料变化及OS查询/父链失败边界后，**最终38 passed，0 failed，0 skipped，5.58s**（TEST_RESULTS_03.xml）。没有删除弱化旧断言，也没有本轮失败迭代。补充绑定原宿主夹具及包装材料后再次运行38项通过；初稿保留为CANDIDATE_DRAFT_01.json，只有当前清单的d427264f…摘要是最终候选。
- 单元覆盖：历史PASS标签不足以覆盖缺失/冲突退出证据；query未知/父链变化/父进程退出关闭引用并拒绝；check与admit完全一致；拒绝发生在意图和创建前；旧、半写或损坏意图和已有输出继续阻断；创建结果不确定后不重试；引入新候选不增加调用预算。
- 一键底层self_check.ps1在工具中的Windows PowerShell5.1实际调用，SELF_CHECK_PASS/exit0；只生成新的临时SELF_CHECK.json，没有调用外部执行进程。数据见 SELF_CHECK_TOOL_02.txt。双击外壳固定参数静态检查通过，未通过工具打开长期交互窗口。
- report机器入口实际返回NO_ATTEMPT_RECORDED。默认/帮助/check/report均有实际测试，执行创建入口设置失败哨兵；真实execute未调用。
- 测试只创建临时数据，不需要新worker或Abaqus；原操作者worker退出证据来自归档，不重新制造。普通Python/PowerShell自检进程正常返回，无新增后台观察者、私有凭据或待终止进程。没有终止、删除或重置任何实验文件。
- 原engine函数体未改，未重跑无关GUI/Solver或全历史回归。保留核验见 DELIVERY_CHECKS.json。

一键入口及报告字段见本目录USAGE.md。完整一键运行一般数秒，不要求用户逐条输入诊断命令。若被策略拒绝或自检阻断，保留结构化结果，不更换渠道绕过。

## 仍未验收与停止

本包的真实execute仍未运行；实际Abaqus包装器、环境/许可、完整成员集合、退出闭合、真实DAT版式及数值、ODB均未因此验收。VS2022默认路径缺失风险保持。300秒仍仅是观察预算；控制器创建和IO可能影响返回时间，不是Solver强制时限。不自动重试、终止、删除或重建批准材料。

没有访问Stable/生产Project、修改共享环境/依赖/安装/版本、切换恢复Git、提交或推送。新代码与交付仅在本独立目录。完成待审候选后停止，不自行开展真实执行或下一轮。
