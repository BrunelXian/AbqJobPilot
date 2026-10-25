# Run018 — 现有服务 GUI 连接交付

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN018_EXISTING_SERVICE_GUI_ATTACHMENT_READY**

实际基线：Develop@271c6f82fd6a4599dbae2df30d903dab2cef1f63，版本0.3.0.dev0不变。保留已有未提交及未跟踪成果；本轮没有Git写操作。

## 已完成

- 正常Dev入口现在直接提供Agent-first连接视图。双击根目录`Open_Dev_GUI.vbs`→明确选择Project→认证已有owner→32项分页选择Run。旧队列GUI保留为独立的Legacy入口。
- 复用公共客户端与现有Supervisor，只新增一个只读`project_view`查询；状态、退出、范围收尾、Solver和验证分别显示，日志有界。GUI不建服务、不发批准／提交／恢复／对账／停服操作，也不直接写DB。
- 发现使用显式Project的manifest、private connection及owner元数据，再核验OS创建身份和认证握手。断线显示过期缓存与最后更新时间；切换Project清空旧选择，重连同Project重新确认身份。
- 实际Windows测试：独立客户端先提交固定ProcessFixture；正常GUI与venv全部退出后，原owner/worker身份保持、日志增长；正常入口重开连接同Run/回执，物理启动1次。最终采用登记pythonw链测试，worker自行完成，Artifact VALID、Solver NOT_RUN。

## 检查结果

**262个唯一用例最终PASS，0最终FAIL/SKIP。** 新增组28项，旧GUI独立15项，主选择246项存在交集，不能相加当唯一数量。保留了两次测试驱动失败及一次legacy pytest日志配置拒绝；修正的是测试屏障/动作确认与隔离日志路径，未削弱业务断言。

98组harness清理、117条进程生命周期和14组native句柄证据通过，私有连接材料剩余0；只读后查未发现本轮身份匹配的存活进程。原历史文件保留；两个旧实时view文件不作为静态哈希断言，另有历史GUI新增exit.json路径保持原样、未读取或操作。

交付导航：

- [GUI使用说明](USAGE.md)
- [实现与发现契约](IMPLEMENTATION_AND_CONTRACT.md)
- [验收矩阵](ACCEPTANCE_MATRIX.md)
- [测试、失败迭代与清理](TEST_RESULTS.md)
- [实际GUI截图](windows_evidence/normal_gui_lifecycle.png)
- [Windows闭环原始证据](windows_evidence/normal_gui_lifecycle.json)
- [基线](BASELINE.json)、[最终保留核对](FINAL_CHECKS.json)

## 边界与下一最小切片

只支持已有Agent-first格式3、明确instance root下Project及可信交接的连接材料。未加载project_view的旧owner显示能力不支持；不停止、重启或接管Run016保留owner。没有接入生产Project、迁移、自动Supervisor启动、真实批准UI、Abaqus提交UI或CLI/MCP写工具。

下一轮建议只做**Supervisor正常启动管理与产品生命周期**：在明确Project和可信既有配置下，独立于GUI连接/授权流程启动；同OS存储锁排他，竞态只连接赢家；已有实例重启保持PAUSED/未决阻断；不批准、不恢复、不重试；活跃/UNKNOWN情况下停服须明确契约。先用固定Python隔离实例验收，继续不增加求解能力。

本轮Abaqus调用 **0**；未访问Stable、生产Project、旧Runtime或历史真实实验数据，未改共享环境，未提交/推送。正常GUI关闭的Python生命周期已验收；真实Abaqus、终端关闭、注销、系统重启和常驻部署不由本轮获得新的验收。完成后停止，未自动进入下一Run。
