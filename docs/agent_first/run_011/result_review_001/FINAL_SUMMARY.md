# Run 011 首次真实实验：独立离线结果复核

**整体 PARTIAL；Solver 正常完成证据成立，三项指定 DAT 数值均通过。** 完整 Abaqus 成员集合仍未证明；原始控制器的 PARTIAL / EVIDENCE_INSUFFICIENT 记录保持原样。本轮新增 Abaqus 调用 **0**，没有再次 execute。

实验 `abq2024_r010_a19d17ea`；attempt `attempt_d932768199b84915a89c8d7a83ef9c3f`。唯一实验根：

`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a`

## 1. 基线与材料

Dev 为 `Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，无未解决冲突，版本 `0.3.0.dev0`。前轮未跟踪成果保留。本次所有新增文件仅在本 `result_review_001` 目录；未改正式执行核心、旧解析器、控制器或候选。

- 原清单 body：`04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6`。
- 使用候选 body：`d427264f99b2e1128a50d171c09b852cc57662ee002de5c31ba7cdc9d60b840c`。
- 当前复核原 34、旧候选 21、新候选 37 项绑定材料全部 MATCH。调用 `package.load`，没有调用启动前 `check_empty` 来试图再次获得执行资格。
- 输入 SHA-256：`e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3`，与原清单、attempt 和控制器记录一致。
- DAT 10334 bytes；SHA-256：`23ac0cdd7714ef956f481fdf1ec97530cd0cf44a160ae286cd689400efc3f045`，与用户交接和控制器记录一致。

读取 attempt、report、events、stdout、stderr、INP、DAT、STA、MSG 共 9 个源文件。engineering 下没有该 Job 的额外 `.log`；没有打开 ODB 或 PRT 内容，没有执行生成的 `.com`。DAT 的文件身份、大小、mtime 与控制器记录一致；实际 birthtime 晚于启动意图。对读取文件进行前后有界稳定读取核验，并保留摘要和时间。它们是关联证据，不宣称原子文件系统快照或抗同用户篡改签名。

原 Run010/011 的 199 个既有文件保持；9 个实验源文件均保持。详见 `PRESERVATION_BASELINE.json`、`PRESERVATION_CHECK.json`。历史材料中的“尚未授权/调用0”是当时记录，没有改写；本次实际执行事实来自新 attempt、事件及输出。

## 2. 真实调用、宿主与退出

控制器事件序列 1–26 连续，时间顺序成立。仅有 1 个 CREATE_CALL_ENTERING、1 个 PROCESS_OBJECT_RETURNED；匹配一个直接 cmd 进程、一个该 Job 调用转录。结论是本控制器记录的包装器调用 **1 次**，额外人工 Abaqus 调用 **0 次**；包装器内部的许可证 helper 是本次调用子链，不是额外信息查询。本轮复核未创建任何 Abaqus/夹具子进程。

启动意图：2026-10-23 **19:45:59.007158 +08:00**。记录中的实际控制器11948、venv17428、PowerShell22064身份/会话/控制台和成功 Job 查询满足新候选政策。这里只重算记录的政策判定，没有冒充当前宿主检查或重新批准。

直接 cmd22932 的 OS 退出码0在 **19:46:26.135090** 被观察到，即意图后 **27.1279325 秒**。控制器仍观察满300秒，到 **19:50:59.008550**，约300.015秒返回报告。`deadline_reached=true` 表示达到观察预算，并非 Solver 超时失败。

| 记录的进程 | PID | 退出证据 |
|---|---:|---|
| cmd.exe | 22932 | direct Popen retained handle，exit0 |
| conhost.exe | 9148 | retained Windows handle，exit0 |
| SMALauncher.exe | 29748 | 同上，exit0 |
| SMAPython.exe | 28396 | 同上，exit0 |
| eliT_CheckLicense.exe | 21988 | 同上，exit0 |
| SMAPython.exe | 8920 | 同上，exit0 |
| eliT_DriverLM.exe | 4572 | 同上，exit0 |
| pre.exe | 26924 | 同上，exit0，19:46:14记录 |
| standard.exe | 20508 | 同上，exit0，19:46:24记录 |
| SMAEqsDirSolverSymmetric.exe | 16008 | 同上，exit0 |
| SMASimUtility.exe | 4436 | 同上，exit0 |

表格以 PID 简写，实际核验使用 **PID + 创建时间 + 映像路径**；全部11个唯一身份与事件中的识别/退出记录逐项相符。完整身份和观察时间在 `VALIDATION.json`。退出时间是观察时间，不伪称精确死亡时刻。

`all_observed_exited=true` 成立。成员发现使用有界父链候选扫描，不能证明无遗漏，因此 **member_completeness=UNKNOWN、overall_exit=UNKNOWN 原样保留**。没有重新探测旧PID，也没有用“现在不存在”补写退出。没有按进程名称搜索、终止或混入其他 Abaqus 作业。

## 3. Solver 结论与数值

运行时证据显示 **Abaqus 2024 / Abaqus/Standard**。证据组合为：stdout 的 Job名、2024版本、pre/Standard启动与结束及 JOB COMPLETED；STA第6行的step1/inc1/attempt1、总时间1及第8行成功结束；MSG第116行总时间1、第119行完成、第137行0错误；DAT第231行完成；已记录 standard.exe OS退出0。故可以记录“本次分析有可信的正常完成证据”，这与完整进程集合证明、ODB内容验证分开。

stdout 中确有原已接受的 VS2022 路径错误。后续 Standard 启动和完成证据说明它没有阻止本次求解。未修复安装或重跑；stderr 的许可转录只被只读核对，报告不复制许可服务器及无关环境信息。

所有以下值均来自 **Step1 / Increment1 完成摘要之后，step time=total time=1** 的唯一结果段；没有把第128行初始时间0用于判定。DAT第183行是increment summary、第187行是完成时间。数值是打印文本精度下的观测。

| 量/位置 | DAT 行/表头行 | 原始数值 | 参考值 | 绝对误差 | 冻结有效容差 | 判定 |
|---|---|---:|---:|---:|---:|---|
| 节点2，全局U1 | 218 / 215 | 1.0000000E-02 mm | 0.01 mm | 0 mm | 1e-6 mm | PASS |
| BAR，T3D2，单元1，积分点1，S11 | 203 / 200 | 1.000 MPa | 1 MPa | 0 MPa | 1e-4 MPa | PASS |
| 节点1，全局RF1 | 227 / 224 | −1.0000000E+00 N | −1 N | 0 N | 1e-4 N | PASS |

节点2 U2/U3=0、RF1/RF2/RF3=0以及X方向力平衡均满足原附加阈值。**节点1 U1/U2/U3未出现在DAT位移表中**，保持 NOT_RECORDED，不按边界条件或软件零行省略惯例补零。故三项主目标通过，但不能把原清单的所有附加检查汇总为全通过。ODB内容验证仍为 NOT_RUN。

## 4. UNSUPPORTED_TEXT 与独立修复

直接触发点是旧 `controller/printed_results.py:parse` 的 `data.decode('ascii')`：DAT第3行日期包含 CP936 的“月”（字节 `D4 C2`，零基偏移63），触发 UnicodeDecodeError，被旧代码映射为 UNSUPPORTED_TEXT。实际字节再次调用旧解析器准确复现该结果。

并非只改编码即可：真实页眉带日期且重复；产品信息不是旧解析器要求的独立行；步/增量在标题后；总时间与步时间同一行；表头包含 FOOT-/NOTE；表格顺序为S、U、RF；完成标记后有 ANALYSIS COMPLETE 和时间统计；节点1位移行缺失。旧测试版式与真实2024文本不兼容。

本目录 `dat_review.py` 新增 **r011-actual-2024-axial-dat-v1**，只用于这个固定算例的离线解释。严格CP936解码，非ASCII仅允许在已知页眉日期位置出现“月”；验证唯一step/inc、完成时间、T3D2/BAR积分点、全局节点表和完整尾部，拒绝重复/歧义/缺失/错误/超限。没有宽泛正则搜最后一个数字、忽略解码错误或修改容差。

`collect_review.py` 固定实验与attempt，并要求DAT是上述原始摘要；调用已有只读材料和文件身份工具。其审计钩子禁止子进程、shell、网络、SQLite及本新目录以外的写入。仅新增原字节回归副本 `ORIGINAL_DAT.bin` 与 `VALIDATION.json`；不覆盖已有文件。模块只支持本次版本/版式，不能作为通用DAT或已注册的真实Backend验证器。

## 5. 实际离线验证

环境：登记的 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10、pytest9.1.0，Windows。全部用 `-B`，没有安装或改变依赖。

| 验证 | 实际结果/证据 |
|---|---|
| 新真实DAT回归及拒绝边界 | **30 passed**，0 failed/0 skipped，0.12s；TEST_RESULTS_02.xml |
| 原解析器r11_07相关组 | **24 passed，32 deselected**，0.19s；OLD_PARSER_RESULTS.xml。32项属其他控制器/进程主题，本轮未运行 |
| 失败迭代 | 首轮29 passed、2 errors（同一超限输入的setup/teardown）；pytest把1MiB字节串作为测试名，超过Windows环境变量32767字符上限。改为固定短测试ID后通过，未删场景或弱化断言 |
| 失败日志脱敏 | 仅本次新生成的首轮日志移除无关环境repr，并缩短超长参数显示；错误原因和计数保留。没有更改原始实验日志 |
| 无副作用 | 纯解析禁止外部文件读/创建进程测试；实际复核有全程启动失败哨兵；9源文件/199旧交付/所有绑定材料不变 |

实际运行的测试入口（cwd为Dev；输出记录在本目录）为：

```powershell
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest 'docs\agent_first\run_011\result_review_001\test_dat_review.py' -q -p no:cacheprovider --tb=short --basetemp='D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\result_review_001\test_tmp_002' --junitxml='D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\result_review_001\TEST_RESULTS_02.xml'
& 'D:\XianLab\envs\LangChainEnv\Scripts\python.exe' -B -m pytest 'docs\agent_first\run_011\tests\test_candidate.py' -k 'r11_07' -q -p no:cacheprovider --tb=short --basetemp='D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\result_review_001\old_tests_tmp_001' --junitxml='D:\Projects\abqjobpilot_dev\docs\agent_first\run_011\result_review_001\OLD_PARSER_RESULTS.xml'
```

这些是已执行命令记录，不应原样重跑覆盖本次测试证据；后续复测需新记录名。本轮普通Python进程均正常返回，无新增worker/后台观察器，没有需要终止的测试进程。保留测试证据和所有旧清理阻断；未删除实验输出、scratch或attempt。

## 6. 窗口与剩余边界

控制器已结束300秒观察且已记录11个进程均取得退出证据。**就已记录的控制器/执行链而言，没有需要继续靠该PowerShell窗口维持的已知进程，也没有继续空等的证据收益。** 这不证明未观察成员不存在，不能升级为“关闭窗口对任何未知后代绝对无影响”的保证。关闭窗口不应被用作停止未知进程的手段；本轮未代为关闭窗口。

剩余缺口是完整必要成员集合、节点1位移打印证据、ODB内容和全面资源释放证明。保留原attempt永久阻断重复执行；新增结果不返还调用预算、不批准补跑或补充Abaqus后处理。未接触Stable、生产Project/DB、共享环境、版本、执行核心；未提交、推送或自动进入下一阶段。
