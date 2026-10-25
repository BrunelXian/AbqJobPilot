# Run015 最终报告

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN015_MANAGED_PROCESS_COMPLETION_READY**

固定Python进程的受管范围正常收尾与两任务顺序派发已通过实际Windows验收。本轮Abaqus调用 **0**。真实Standard Backend未切换至此启动方式，未做真实Abaqus兼容性验收。

## 实现结果

在原ProcessFixture Backend启动接缝加入每Run独立、未命名的Windows Job，通过`PROC_THREAD_ATTRIBUTE_JOB_LIST`在根线程运行前关联。没有先启动后Assign的遗漏窗口；不启用KILL_ON_JOB_CLOSE、breakaway或伪造父进程。GUI和Supervisor自身不属于单Run范围。

复用原公共客户端、Supervisor、Project存储、计划、TEST_ONLY授权、领取和终态事务。只有根创建已确认、无待决创建、原Job直接查询ActiveProcesses=0，才将收尾证据、Run投影、验证和槽释放一起提交。下一项仍须满足原授权及门政策；PAUSED保持，执行或验证失败不自动继续。

正常收尾依据本次直接OS范围证据，不调用Run014行政释放。owner崩溃、Job不可查询、创建/持久化故障继续保留槽与未决状态；重启不重建空Job替代原证据，也不能用旧四角色对账绕过范围缺口。

## Windows证据

最终两任务用例中，物理根创建分别为PID10800/创建时间134373030516846797与PID12504/134373030524061955，均为登记解释器。两个不同Run各启动一次；同请求重放没有额外创建。

| 顺序 | Run | 持久事件全局序号 |
|---|---|---|
| 第一项启动 | r_8e62723efddd468ba810e75c98338153 | START_INTENT 2 |
| 第一项收尾 | 同上 | MANAGED_SCOPE_COMPLETED 14；VALIDATION_RECORDED 15，同事务释放槽 |
| 第二项启动 | r_0505cafa4cde4df3b19dde9c114cdfc7 | START_INTENT 16 |
| 第二项收尾 | 同上 | MANAGED_SCOPE_COMPLETED 27；VALIDATION_RECORDED 28 |

见[两任务原始证据](verified_final/test_managed_two_normal_tasks_0.json)。两项范围直接查询均active=0、累计6（含本机venv链），Backend COMPLETED、Artifact VALID、Solver NOT_RUN分别记录。

其他真实场景：延迟多级后代累计12、快速场景累计24；四个关键角色退出后仍有后代时第二项不启动。GUI及专属venv启动器通过WM_CLOSE真实退出，worker继续且日志增长；重开GUI连接原Run/owner/范围，显示COMMITTED_EMPTY_SCOPE。真实终止测试owner后worker继续存活，重新启动的测试owner保持PAUSED及RECONCILIATION_REQUIRED。参见[逐项矩阵](ACCEPTANCE_MATRIX.md)、[GUI重连画面](GUI_RECONNECTED.png)及`verified_final/`。

现有产品入口也从非仓库cwd运行通过：启动器退出后服务独立完成两项；公共客户端和GUI读同一存储。最终产品Run为`r_82fe00929e17427286f08ee2c8347b69`、`r_2cd9cef06b0b4ad1926759a2d194c343`，见[产品入口证据](gui_final/product_entries_managed.json)。VBS命令路径静态核对，未将双击本身描述为额外实测。

## 测试与清理

相关回归首批382通过、1项静态白名单失败；修正限定白名单后9项通过。最终核对发现新计划进程预算12低于含venv链的实际24，改为32的声明预算后，受影响50项通过。按不同测试合并最新结果：**383项PASS、0跳过**；不是声称单次383项全绿。所有失败迭代保留，详见[实际测试记录](TEST_RESULTS.md)。

最终审计覆盖7个本轮明确测试根、121份inventory、28对正常收尾的Job/根句柄关闭记录；635个已登记OS身份的最终只读检查无匹配存活者。此事后检查不补造历史退出码；历史退出仍来自原保留句柄，范围结束来自直接Job查询。两次故障验收仅终止本轮创建且身份核实的owner，后代自行结束。测试私有凭据清理检查通过，业务证据保留。产品入口正常停服不使用进程终止，private_remaining=0。

394项历史保护材料摘要全部一致；旧Run revision21、UNKNOWN、PAUSED、路径隔离及行政处置没有变化。未操作旧owner、Stable、生产Project或共享环境；未迁移数据、修改版本、提交或推送。

## 直接使用

按[使用说明](USAGE.md)依次运行：

1. `examples/agent_first/R15_01_Start_TEST_Service.vbs`：新Temp实例及两个精确TEST_ONLY计划/授权，启动原服务。
2. `R15_02_Submit_Two_Tests.vbs`：公共客户端提交两个请求。
3. `R15_03_Open_Dev_GUI.vbs`：查看第一项，可关闭GUI再开；`R15_05_View_Second_Task.vbs`查看第二项。
4. 完成后显式`R15_04_Stop_TEST_Service.vbs`，沿已有有界演示停服契约。

没有启动本轮面向用户的持久演示实例；点击Start才会新建。当前没有要求用户维持PowerShell窗口的后台测试任务。

## 保证范围及未验收项

已证明的是**本Run Job中根及继承CreateProcess后代的范围结束**，不是整机不存在Abaqus进程，也不是每个瞬时子进程的退出码均成功。关键角色退出、Backend结果、Artifact验证、Solver结论保持独立。

新Job无终止策略不等于外层Job没有限制。当前Windows/登记venv嵌套链已实测；外部服务/broker/WMI/远程执行不在范围内。终端关闭、注销、重启、真实Abaqus包装器与Solver进程集合均未验收。跨Project和整机资源协调、崩溃后接管/重新观察仍未实现。

后续最小候选是单独评估真实Abaqus入口在该创建时Job范围中的兼容性与外部服务边界；任何实机调用须另行授权。本轮到此停止，不自动进入下一轮。
