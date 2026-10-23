# Run 013 最终报告

**PASS_ABQJOBPILOT_AGENT_FIRST_RUN013_ABAQUS_SERVICE_INTEGRATION_CANDIDATE_READY**

固定 Standard Backend 已接入原公共客户端、Supervisor 工作线程、Project 执行存储及现有 Dev GUI；受控替身和离线验证通过。**本轮真实 Abaqus 调用0次，真实服务链路尚未验收。**

## 实际交付

- 新 `execution/standard_contract.py`：只接受固定轴向杆输入、固定2024入口/资源、明确工程目录/输出身份的可执行计划准备，以及与 TEST_ONLY 分开的精确真实批准类别。Run009预览仍不能提交执行。
- 新 `standard_backend.py`、`standard_process.py`：已有 ExecutionService/Supervisor 中的一次启动路径、输出意图、实际owner内宿主检查、受限进程观察、只读日志及分维度结果持久化；不是独立实验控制器。
- 新 `standard_dat.py`：Run011实际CP936版式解析的产品副本，原冻结文件不变；数值标准未调整。
- 必要修改仅在原 service、supervisor、store、progress_log、diagnostics、execution_gui 和隔离测试白名单。存储沿用实验v3，无迁移；原接收、Grant消费、幂等、所有权、单槽和恢复/对账语义保持。Run010/011包、版本及旧GUI/Runner行为不改。
- 新薄示例 `standard_service.py`、`standard_client.py` 和六个 `R13_*.vbs` 入口。客户端只使用公共接口，GUI只读；批准、owner启动、提交及停止明确分开。

文件/函数接缝、故障窗口、主机政策及权限边界详见 [IMPLEMENTATION.md](IMPLEMENTATION.md)。准确操作步骤见 [USAGE.md](USAGE.md)。

## 测试与证据

最终按用例身份去重 **514项取得通过证据**：主组501、补充准入8、旧GUI/表格5。主组最终501 passed / 298.85s；旧GUI有一次Tk初始化跳过，独立进程重测该项通过。保留所有失败迭代，未弱化旧断言，详见 [ACCEPTANCE_MATRIX.md](ACCEPTANCE_MATRIX.md)。

Windows实际普通Python替身通过公共客户端提交，现有GUI显示同一Run，完整关闭GUI及专属venv启动器后，owner/worker仍存活、日志继续增长；重开同Run，物理替身创建1次。最终已记录进程退出、DAT主三项通过，与成员完整性UNKNOWN、整体退出UNKNOWN、ODB NOT_RUN及PAUSED分别显示。完整证据在 `evidence_003/windows_substitute_gui.json`；原Run012生命周期/故障回归在 `gui_regression_002`。

这些是**受控普通Python替身及历史文本样本**，不是本轮真实Abaqus执行。原DAT样本SHA-256 `23ac0cdd7714ef956f481fdf1ec97530cd0cf44a160ae286cd689400efc3f045` 只用于离线测试；没有导入待批准Project作为已执行证据。

本轮测试只用显式临时根；已记录测试进程/GUI/venv按保留OS句柄确认退出，关闭句柄，清除测试私有bootstrap/connection/offer。故障回归只操作本轮已核实身份的进程。临时业务证据保留，不清理旧目录。原34项冻结材料重新计算全部匹配，纳入基线的220个Run010/011文件保持不变。待批准实例保留必要私有bootstrap，但不存在有效真实执行Grant。详见 DELIVERY_AUDIT.json。

## 唯一待批准实验

| 项目 | 固定内容 |
|---|---|
| 实验 | `run013_e52135d71d2c43d2a45301c586cbfb7e` |
| 清单 | `D:\Projects\abqjobpilot_dev\docs\agent_first\run_013\ACCEPTANCE_MANIFEST.json` |
| 清单body SHA-256 | `3c59461d53e658eb9894d6936bd405f85a7f27b6ebc3deb5343c81d8411ceebe` |
| Plan | `plan_ed1ac113f464496497d8787268189c4f` |
| Plan摘要 | `sha256:62dc0aa95bad8c5e0d61d62515a4451a9d3f694016339fe68d7ca2c55239d46a` |
| Project instance | `pi_776faf62f2d64a4ab23e83c53b665788` |
| 新根 | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run013_e52135d71d2c43d2a45301c586cbfb7e` |
| 输入 / cwd / scratch | 新根下 `engineering\axial_bar.inp` / `engineering` / `engineering\scratch` |
| 唯一入口 | `D:\ABAQUS2024\Commands\abq2024.bat` |
| Job | `r013_bar_d48c54f7` |
| 动作与资源 | 一次Standard analysis启动尝试；CPU1/GPU0/2048 MB；额外Abaqus调用0次 |
| 期限 | 创建耗时单列；创建返回进入观察后300秒只结束观察，不终止、不重试、不删除 |
| 验证 | node2 U1=0.01mm±1e−6；element1/IP1 S11=1MPa±1e−4；node1 RF1=−1N±1e−4；ODB内容不验证 |
| 当前状态 | plans=1；grants/runs/receipts/consumption/observations/validations=0；无同名输出或启动意图 |

清单使用原canonical_json(body)规则，实际引用材料另按字节摘要绑定。CALL_REVIEW.json列出从产品代码导出的Windows调用，供审阅，不是绕过服务的操作入口。

现在可双击 `examples\agent_first\R13_01_Check.vbs`（无Solver）。同一绝对Python入口从非仓库工作目录实际运行过，返回 MATERIALS_MATCH_NO_EXECUTION。获明确批准并经可信入口登记一次许可后，操作路径是：`R13_02_Start_Service.vbs` → `R13_03_Submit_Once.vbs` → `R13_04_Open_Dev_GUI.vbs` → 关闭并重开同一GUI → `R13_05_Read_Report.vbs`。不是用户手工拼装底层Abaqus命令。

## 尚待实机成立的结论

新服务宿主政策只承诺Windows会话保持存活时的独立owner范围；实际owner会重新检查自己的OS身份、Job查询、登记解释器、普通文件输出句柄和当前材料/许可。它不是Run011操作者PowerShell承载链，不承诺owner/Job/会话关闭后存活，也不凭直接Job某个标志推定安全。

实际Abaqus在该服务链中的启动、Runtime证据、GUI关闭时仍运行、重开同Run、日志/数值及退出事实必须由这次新实验取得。模型可能很快完成；未捕获“运行期间GUI退出”不得推定通过或自动再试。

完整Solver成员集合尚未证明，首版因此保留UNKNOWN、RECONCILIATION_REQUIRED、PAUSED及占用槽。已观察进程exit0或DAT通过不会释放冲突资源。真实进程重挂接/恢复/对账/强制停止、完整ODB验证、跨Project主机资源协调、真实人类审批产品化和完整0.3.0均未验收。

## 停止与授权边界

本轮到此停止。未访问Stable或生产数据，未调用Abaqus任何入口，未修改安装/共享环境，未清理旧实验或尝试保护，未提交或推送，版本仍为0.3.0.dev0。

下一步所需授权仅为上述清单绑定的**一次新服务链Standard分析启动尝试**，接受明确宿主/未知成员/不自动停止边界。之所以仍需该具体批准，是因为本轮用户明确将真实调用预算限定为0，且旧Run010/011批准不覆盖新服务、Project、Job和输出位置。候选PASS不构成执行授权。
