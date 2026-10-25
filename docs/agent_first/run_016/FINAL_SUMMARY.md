# Run016 最终报告

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN016_MANAGED_ABAQUS_ACCEPTANCE_CANDIDATE_READY**

已完成受限Standard Backend与Run015管理范围的接入、固定A→B服务端条件、相关Windows替身验收和一个待审实机包。**本轮真实Abaqus调用0；待审实例没有真实Grant、Run或提交。** 该状态不表示真实Abaqus新路径已经通过。

## 实现与实际基线

Develop@`271c6f82fd6a4599dbae2df30d903dab2cef1f63`，0.3.0.dev0。开始时已有Run014/015修改完整保留，见BASELINE.json及before/。结束分支/HEAD相同，无冲突。

复用原公共客户端、Supervisor独立worker、所有权、Project执行存储、授权与幂等、持久意图、CP936 DAT解析和实际Dev GUI。Standard新增显式管理计划模式；原Native Job接缝增加仅三个标准文件句柄的HANDLE_LIST，根运行前JOB_LIST关联，不回退到Popen。受管范围直接查询完成后，同一终态事务保存证明、Solver/验证记录和释放槽。没有新执行框架、独立实验控制器、表或迁移。

新增standard_sequence.py只表达本批固定A/B。B在提交、领取、创建前核验A的管理策略、已提交正常收尾/槽释放、Solver和三项DAT通过，且自身Grant、输出、输入、OPEN门及窗口有效。原生创建API紧前再检查截止时间。行政释放不能满足前提。普通客户端在A合格后才提交B，不把B提前留在待执行队列。

现有GUI显示原Project Run、范围收尾、批次位置及截止、Solver、数值和UNKNOWN各维度。查询/重连不会批准、恢复或重新提交。诊断兼容修复仅允许明确旧规则版本缺少新可选字段；仍拒绝额外秘密字段，不回填旧证据。详见[契约及接缝](CONTRACT.md)。

## 验证结论

主回归304通过/1失败（旧诊断导出兼容性），修复后相关58通过；最后原生截止检查及受影响182项通过，客户端清理7项通过。按不同测试合并最新结果**355项PASS、0跳过**，不是一次全量355项通过。全部初始失败及修复原因留在[测试记录](TEST_RESULTS.md)，逐项覆盖见[矩阵](ACCEPTANCE_MATRIX.md)。

实际Windows固定Python替身经过Standard真实服务接缝及同一个原生Job代码：A活动时B拒绝；A收尾事件14/结果15提交后B启动事件17，B收尾29/结果30；物理根各一次。实际GUI及专属venv退出后owner/worker继续，重开连接原Run；owner真正崩溃后worker继续，新ownerPAUSED且B不启动。见`verified_deadline/`，其中Solver/DAT内容明确是历史样本测试，不是新Abaqus结果。

743个本轮登记Python身份最终无匹配存活者；原保留句柄退出、正常用例原生句柄关闭和私有连接清理有记录。没有按名称结束进程。7个测试根业务证据保留；仅逐文件清理本轮确认的假连接材料，未动旧清理阻断。待审实例bootstrap有意保留，未导出秘密。

517项历史保护摘要一致，含旧真实execution.sqlite3原始字节；因此历史revision21/UNKNOWN/PAUSED/路径隔离/行政记录未被本轮改写。没有查询或操纵旧owner，没有Stable、生产Project、Abaqus安装或共享环境修改；无Git切换/恢复/提交/推送。

## 唯一待批准包

- 实验：`run016_8a85583d797345d0b9a4a27b64511b44`
- [单份清单](ACCEPTANCE_MANIFEST.json) body SHA-256：`88ddae420d2fd73f0ecb7bace4171bb8f0eb6a6b2098b0d91e558c94338f3fd7`
- 根：`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run016_8a85583d797345d0b9a4a27b64511b44`
- Project：`p_a9c341833aca442f9be8128eff40a484`；instance：`pi_4e7e059e0330465bab4ad35997ae4b71`
- 入口：`D:\ABAQUS2024\Commands\abq2024.bat`，保持固定包装器和参数，不修复共享环境。
- A：`plan_10f4850d334947a3af4ec022c978d003`；Job `r016_bar_a_8a85583d`；cwd根下engineering_a、scratch为其scratch。
- B：`plan_7c45450805de438c85af08169a2a9ffa`；Job `r016_bar_b_797345d0`；cwd根下engineering_b、scratch为其scratch。
- 两项输入都是各cwd下axial_bar.inp，固定420字节副本；输入SHA-256 `e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3`。
- 每项CPU1/GPU0/2048MB，最多一次Standard analysis；本批最多2次，额外调用0。资源是Abaqus请求，不是OS硬配额。

候选绑定49项执行材料；PREPARATION_CHECK.json验证两计划、零Grant/Run/回执/消费/事件、槽NULL、supervisor_started=0。非仓库cwd的实际`check --pair`返回MATERIALS_MATCH_NO_EXECUTION。body摘要按既有canonical_json计算，不混同整个文件原始摘要。

## 操作与观察边界

[R16_01_Check.vbs](../../../examples/agent_first/R16_01_Check.vbs)现在可无Solver检查。批准后才由原可信authorize入口登记两项精确许可，再用[R16_02_Start_Service.vbs](../../../examples/agent_first/R16_02_Start_Service.vbs)、[R16_03_Run_A_Then_B.vbs](../../../examples/agent_first/R16_03_Run_A_Then_B.vbs)。查看A/B分别是[R16_04_View_A.vbs](../../../examples/agent_first/R16_04_View_A.vbs)、[R16_05_View_B.vbs](../../../examples/agent_first/R16_05_View_B.vbs)，均为现有GUI。准确命令及原键只读报告入口见[USAGE](USAGE.md)。这些真实入口本轮未启动。

未来Grant登记T后600秒内允许A创建。A接受S后，B必须在min(T+930,S+330)前发起创建；每项最多300秒观察，从创建返回计起且截于S+630。观察结束不终止、不重试、不删除、不恢复派发。B未接受前失联即停止编排；B已接受但丢应答时只查原键，不能认定未启动或用新请求重试。

两项均须受管范围结束、正常收尾、Solver正常、节点2 U1=0.01mm±1e-6、单元1/IP1 S11=1MPa±1e-4、节点1 RF1=-1N±1e-4。ODB内容不验证。GUI关闭若错过实际求解时机，单项记未观察到，不补第三个作业。

范围证明是根及继承CreateProcess后代，不是整机无其他Abaqus进程，也不自动验证所有退出码或数值。外部服务/broker/域外输出、外层Job、注销/重启/终端关闭未获得本次证明；发现关键执行未被覆盖不得宣称可靠自动收尾。原完整成员集合/overall_exit UNKNOWN与新的受管范围证明并存，不倒改历史。

## 一次具体授权请求及停止点

请批准以上实验和body摘要绑定的**最多两次固定analysis：先A；只有A的管理范围结束、正常收尾、Solver和三项数值全部通过，且B的当前启动条件仍有效，才执行B**。同时允许通过原可信入口登记这两个固定计划的一次许可并用原公共客户端提交；不含额外探测、重试、ODB调用、终止或旧owner操作。

需要此确认是因为本轮用户明确限定真实Abaqus预算为0，后续两次调用须另行授权；以前单次实验批准不覆盖本新批次。当前实现、证据、路径和摘要已经固定，本轮在批准前停止，不自动开始实机或后续开发。
