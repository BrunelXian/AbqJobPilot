# Run024R — Compact Engineering Cockpit

**REVIEW_READY_ABQJOBPILOT_RUN024R_COMPACT_COCKPIT_PROTOTYPE**

已完成设计复核和独立原生Tk原型；等待用户视觉确认。**不是最终产品GUI通过，也没有替换正在使用的主窗口。**

## 可直接评审

- [打开原生原型](Open_Cockpit_Prototype.vbs)：同登记Python/Tk环境，无浏览器/Web Server。
- [1600×900并排对照](screenshots/COMPARE_1600.png) / [1366×768并排对照](screenshots/COMPARE_1366.png)：A为当前Run024实际控件，B为推荐原型，均明确模拟数据。
- [操作说明](USAGE.md)、[原图与测试范围](VISUAL_REVIEW.md)。

恢复Classic的Queue左/Results右及持续STA/Console布局；顶部压缩Project、Agent Command、模式切换与语言；当前Run和状态集中显示。高级功能收进5个Agent Command子区，默认收起。Classic/Execution双向切换共享视觉，但模拟身份、日志和证据含义分开。空状态为紧凑Create/Open引导。

## 实际改动与结果

所有新增文件仅位于`docs/agent_first/run_024r`：独立原型、禁用副作用的参考截图驱动、有限检查程序、原生截图、设计和后续实施文档。没有修改产品GUI、执行核心、Backend、授权/恢复状态机或Project格式。

13个唯一原型窗口场景PASS，FAIL/SKIP=0；另3张当前Run024参考窗口捕获和2张并排拼图，不混入用例数量。覆盖两种客户区尺寸、模式往返、抽屉、四语言、空状态、中断与失联。初版德语高缩放布局问题和Classic样例来源问题已在原型修正；没有以重跑覆盖历史产品测试失败。

1741个基线文件摘要全部不变，目录外新增0。Develop HEAD仍为`9553755a24ff521dd2ac694ea39cab5a03f88466`，版本仍为`0.3.0.dev0`，无冲突。见[基线](BASELINE.json)和[保护检查](FINAL_CHECKS.json)。此前未提交CR-D03/Run024成果原样保留。

真实Abaqus调用0，Supervisor连接/启动/停止0，生产或历史Project操作0。仅本轮捕获窗口正常退出；没有杀进程、删除历史材料、修改共享环境、访问Stable、提交或推送。

## 限制和下一步

本轮是可操作的显示原型：服务按钮禁用，New/Open仅演示子区，日志为固定样例，Follow不是实时实现。没有验证真实数据分页、服务连接、生产GUI生命周期；这些功能当前代码保留，之后容器适配必须回归。

125/150%为Tk缩放检查，非跨显示器真实OS DPI验收；客户区尺寸不含边框。长德语窄列仍需详情查看，后续补tooltip。四语言主控件词典各58键，法德为Preview，高级技术正文未全部本地化，未宣称完整翻译。

[当前问题](CURRENT_GUI_REVIEW.md)、[Classic复用](CLASSIC_REUSE_ANALYSIS.md)、[信息架构与Agent Command](COCKPIT_AND_AGENT_COMMAND_DESIGN.md)、[后续最小实施计划](IMPLEMENTATION_PLAN.md)已交付。

**停止在视觉确认处。** 只有方向获确认后，才进入生产展示容器的最小替换；正式RC操作继续暂停，既有审计保留。本轮不自动进入下一阶段。
