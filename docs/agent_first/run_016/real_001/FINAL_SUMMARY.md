# Run016 实机验收结果

**PASS — 本次固定 A→B 受管服务验收通过。**

2026-10-24，现有公共 Python 客户端、独立 Supervisor、Project 执行存储和实际 Dev GUI 完成获批批次。A、B各发生一次包装器/analysis启动，共2次；额外 Abaqus调用0。没有重试、第三项、Datacheck、版本/许可证命令、Abaqus Python后处理或ODB读取。内部正常启动链中的 SMAPython.exe 不属于额外发起的后处理调用。

这份报告追加于 real_001；原准备报告、清单和历史证据保持原样。本次不修改执行核心或候选材料。

## 批准对象、预检与实际状态

- 实验：`run016_8a85583d797345d0b9a4a27b64511b44`。
- 原清单规范化 body SHA-256：`88ddae420d2fd73f0ecb7bace4171bb8f0eb6a6b2098b0d91e558c94338f3fd7`。
- Project：`p_a9c341833aca442f9be8128eff40a484`；instance：`pi_4e7e059e0330465bab4ad35997ae4b71`。
- 根：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run016_8a85583d797345d0b9a4a27b64511b44`。
- 唯一入口：`D:\ABAQUS2024\Commands\abq2024.bat`；两项均CPU1/GPU0/2048MB、固定Standard analysis。
- 实际Dev：Develop@`271c6f82fd6a4599dbae2df30d903dab2cef1f63`，0.3.0.dev0，无冲突。保留前轮脏工作区。
- 环境：登记的 `D:\XianLab\envs\LangChainEnv\Scripts\python.exe`，Python3.12.10，Windows11 build26300。
- 启动前重新核验body、49项执行材料、20项Runtime材料、两项固定Plan和输入；当时Grant/Run/回执/消费/事件全部0，槽空，无启动意图/冲突输出。执行后49+20项仍匹配。

证据：[预检](PREFLIGHT.json)、[授权来源审计引用](AUTHORIZATION_SOURCE.md)、[运行后只读审计](POST_RUN_AUDIT.json)。使用原 `authorize --pair` 一次登记两项精确REAL_FIXED_STANDARD许可，再由原 `start --pair` 启动owner、原 `submit --pair` 薄公共客户端执行；未重建批准协议。

## 启动、范围收尾及顺序

| 维度 | A | B |
|---|---|---|
| Job | r016_bar_a_8a85583d | r016_bar_b_797345d0 |
| Run | r_9ae29c47995d457894c553da404e8680 | r_8ddc32af19a14ae7b16c19f2360e6c81 |
| 最终revision | 37 | 30 |
| attempt / 入口调用 / Grant消费 | 1 / 1 / 1 | 1 / 1 / 1 |
| cmd.exe根PID、创建身份100ns | 5804 / 134373075101400316 | 18504 / 134373075310494263 |
| 创建返回（北京时间） | 17:25:10 | 17:25:31 |
| 正常收尾提交 | 17:25:29 | 17:25:49 |
| 受管累计进程数 / 最终活动数 | 12 / 0 | 12 / 0 |
| 单独保留身份及退出证据 | 9个，均exit0 | 8个，均exit0 |
| 范围收尾 | COMMITTED_EMPTY_SCOPE | COMMITTED_EMPTY_SCOPE |
| 执行 / Backend | FINISHED / COMPLETED | FINISHED / COMPLETED |
| Solver | COMPLETED_TEXT_EVIDENCE | COMPLETED_TEXT_EVIDENCE |
| 数值 / Artifact验证范围 | PRIMARY_THREE_PASS / fixed_standard_dat_only | 同左 |
| ODB内容 | NOT_RUN | NOT_RUN |
| 全局成员完整性 / overall_exit | UNKNOWN / UNKNOWN | UNKNOWN / UNKNOWN |
| 300秒观察上限 | 未触发，约19秒结束观察 | 未触发，约18秒结束观察 |

范围证明来自每个原始Run/phase/owner绑定Job的 `QueryInformationJobObject.BasicAccounting`，不是枚举PID数量推算。根在执行前由JOB_LIST纳入；最终creation_confirmed=true、pending_additions=false、active_processes=0、limit_terminated_processes=0，KILL_ON_JOB_CLOSE与breakaway均未启用。两个scope分别为 `scope_1f310cd2d5854b239e701f797af9cf7c`、`scope_5c53daded2ae4a629a33f02c23f725f5`。

持久事件顺序：A的 **36 STANDARD_MANAGED_COMPLETED → 37 STANDARD_RESULT_RECORDED → B的38 REQUEST_ACCEPTED → 43 STANDARD_CREATE_ENTERING → 44 STANDARD_CREATED → 66/67 B正常收尾/结果**。服务端在提交、领取与实际创建前执行冻结检查；本次没有行政处置、management grant或恢复派发调用。

许可登记T为17:24:01；A最迟17:34:01，实际17:25:10已返回。A接收S为17:25:08，B最迟 `min(T+930,S+330)=17:30:38`，实际17:25:31已返回。批次观察截止17:35:38；实际17:25:50测量结束。没有迟到补启动或延长许可。

每个工程目录保留唯一 `.<job>.intent.json`，其内容与对应Run持久意图相等；每项仅一个CREATE_ENTERING/CREATED事件和一个物理根身份。原回执在重连及最后复核均未改变。详见[全部67个事件](FINAL_EVENTS.json)、[A](FINAL_RUN_A.json)、[B](FINAL_RUN_B.json)。

## Solver与冻结三项数值

服务独立读取本次生成的DAT/STA/MSG，校验时间、文件身份及内容摘要；运行后只读复核再次匹配同一字节和身份。运行时Abaqus2024证据在两份stdout第7行及DAT头；Standard阶段在stdout第13/17行。两项DAT第231行、STA第8行、MSG第119行均包含对应完成标记。结论基于组合证据及完整DAT结构，不只依赖包装器exit0。

两项均为step1、increment1、final_time=1；固定选择及容差未改变：

| 作业 | 检查 | 实际值 | 参考值 | 绝对误差 | 容差 | 判定 / DAT位置 |
|---|---|---:|---:|---:|---:|---|
| A | 节点2 U1（mm） | 0.010000000 | 0.01 | 0 | 0.000001 | PASS / 218行 |
| A | 单元1积分点1 S11（MPa） | 1.000 | 1 | 0 | 0.0001 | PASS / 203行 |
| A | 节点1 RF1（N） | -1.0000000 | -1 | 0 | 0.0001 | PASS / 227行 |
| B | 节点2 U1（mm） | 0.010000000 | 0.01 | 0 | 0.000001 | PASS / 218行 |
| B | 单元1积分点1 S11（MPa） | 1.000 | 1 | 0 | 0.0001 | PASS / 203行 |
| B | 节点1 RF1（N） | -1.0000000 | -1 | 0 | 0.0001 | PASS / 227行 |

- A DAT：10334字节，SHA-256 `a8b36ec7d4bd338bc463dbe8378c499e0a2f86496e9de633faca00e80c489113`。
- B DAT：10334字节，SHA-256 `3579c8ba25f229445f73db967db3c92814c669362cea779b1b81e43596a84e43`。
- [A验证记录](VALIDATIONS_A.json)、[B验证记录](VALIDATIONS_B.json)保留来源、行号、参考值、误差、有效容差及真实验证时间。
- 额外非本轮必需的节点1位移行未打印，仍NOT_RECORDED；`full_frozen_checks=NOT_ALL_ESTABLISHED`没有被改写。通过的是批准的三项主检查，不能扩大为所有场量或ODB内容通过。

## GUI完整退出、后台继续与重连

实际使用原Dev `AbqJobPilotApp`，复用Run013的只读验收遥测入口；不是模拟窗口。遥测进程有旧Runner、数据库和执行能力trap；观察器只作公共查询与本次GUI的身份核验WM_CLOSE，不授权、不提交、不启动Backend。

1. GUI先打开，显示本Project及“未提交”；公共客户端随后提交A。
2. 17:25:20.621，A的真实standard.exe PID17292、创建时间134373075201945586经OS句柄核验仍存活，GUI已显示原Run/回执。
3. 正常WM_CLOSE本次GUI；实际GUI PID24936与专属venv启动器PID24748均通过原保留句柄取得exit0，GUI读取线程正常join。
4. 17:25:20.805，GUI全退出后，原owner PID2792/创建时间134373074463067789和同一standard.exe仍存活。
5. 17:25:21.427，重开的GUI连接同一A Run及原回执，Solver仍存活。17:25:27.073取得GUI退出后MSG增长到5296字节且Solver仍存活的证据；增长按实际字节数判断，不用查询时间变化冒充日志增长。
6. B通过独立只读GUI查看，最终两项GUI与公共客户端均显示FINISHED、范围收尾、Solver/验证及UNKNOWN分维度状态。

[关闭前](BEFORE_GUI_CLOSE.json)、[GUI及启动器退出/后台仍活](AFTER_GUI_CLOSE.json)、[同Run重连](GUI_RECONNECTED.json)、[测量结果](MEASUREMENT_RESULT.json)、[A截图](gui_A_reconnected.png)、[B截图](gui_B.png)。A已满足本批GUI闭环；B未单独重复关闭测试，没有为补证据增加调用。

## 最终状态、保留项与限制

最终只读存储快照：2 Plan、2 Grant、2 Run、2原回执、2授权消费、67事件、2 observation、2 validation；reconciliation/management记录0。逻辑槽NULL，派发仍原有OPEN/version2，未显式恢复派发，无PENDING任务。两项一次许可均已消费；OPEN不赋予任何新任务许可。

owner `owner_9beadf82cc2e484eab023f91c29ee218` 保持原身份并存活。A重连GUI和B GUI有意保留供查看；连接私有材料、输出、scratch和启动意图保留，不清理或停服。公共客户端已输出PAIR_OBSERVED；事后其transport身份无法再取得，不补造退出码。只读测量进程实际exit0。见[剩余状态](REMAINING_STATE.json)。

当前范围证明仅限根及继承CreateProcess的后代。所有已观察候选均通过所属Job检查，但未声明整个系统、外部许可证/broker服务或物理资源全集已结束；9/8个个体退出不冒充12个全部逐个退出码。没有观察到域外关键求解/写出证据；未知域外行为、完整Job层级、owner崩溃后领养、终端关闭、注销、重启不在本次通过范围。全局UNKNOWN保留，正常槽释放依据是新的受管范围证据，不是覆盖UNKNOWN或行政释放。

517项历史保护摘要前后相同，含历史真实数据库；旧revision21/UNKNOWN/PAUSED/路径隔离及行政记录未改，旧owner未查询、停止、重启或接管。无Stable访问、生产数据改写、安装/环境修改、Git切换/恢复/提交/推送。

执行前测量脚本一次读取health字段形状错误在客户端spawn前报KeyError；查询确认A/B均NOT_FOUND且客户端日志不存在后，仅修正观察断言，再首次启动原客户端。执行后审计初稿曾把公共查询增加的两个解释字段与持久行做全对象比较，后改为核验全部持久字段并列出解释字段。两次均属只读证据工具问题，没有改服务、清单或执行条件，没有增加Abaqus调用。

本次未修改产品实现，因此没有重跑历史单元测试；实际验证为本批Windows实机、GUI闭环、同事务记录/顺序及只读完整性审计。完成后停止，不进入Run017。

## 继续只读查看

原入口 [查看A](../../../../examples/agent_first/R16_04_View_A.vbs)、[查看B](../../../../examples/agent_first/R16_05_View_B.vbs)可连接同一已完成Run；[读A报告](../../../../examples/agent_first/R16_06_Read_A_Report.vbs)、[读B报告](../../../../examples/agent_first/R16_07_Read_B_Report.vbs)只读导出当前诊断。**不要再次授权、点击批次提交、重置意图或复用工程输出。** 本次没有执行原停服入口。

原始文本在根下 `engineering_a/r016_bar_a_8a85583d.*`、`engineering_b/r016_bar_b_797345d0.*`；服务stdout/stderr在 `project/runtime/standard_runs/<Run ID>/`；原请求回执在 `session/A/receipt.json`、`session/B/receipt.json`。本目录保存公共诊断快照[A](DIAGNOSTIC_A.json)、[B](DIAGNOSTIC_B.json)，没有复制连接凭据或可用Grant对象。
