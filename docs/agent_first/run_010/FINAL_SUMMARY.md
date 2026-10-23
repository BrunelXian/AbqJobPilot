# Run 010 — 首次 Abaqus 2024 实验准备交接

**PARTIAL（仅临时测试文件清理被自动审批策略阻断）**。实验输入、实际公开预览、静态Runtime身份、调用清单、数值判据与收尾方案已经具体固定，可以审查；不使用全项通过标志掩盖清理缺口。实际Abaqus调用0，未进入执行阶段。

## 1. 固定实验与身份

实验 **abq2024_r010_a19d17ea**，Job **r010_bar_a19d17ea**。一个自包含T3D2轴向杆，Standard单步analysis，CPU1、GPU0、Abaqus内存请求2048MB。N/mm/MPa单位；L10、A1、E1000、载荷+1。唯一自由度是节点2的轴向U1；解析位移+0.01mm、应力+1MPa、节点1反力−1N。输入显式打印U/RF/S，独立从本次DAT读取，不需要额外Abaqus后处理调用。容差、符号和平衡检查在运行前已冻结。

- 实际Dev：`Develop@fb7912ec9e0107b18f65948b147c87579c87cded`，版本`0.3.0.dev0`。
- 当前清单摘要：`sha256:04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6`。
- 输入摘要：`sha256:e2f91730b68f3af72b8054bc168d31b72a3f21ae186e899d64ab4b6b761523a3`。
- 预览摘要：`sha256:1ed98f391032fe9b34a31f87200d5884266e312bb5f2ffc6ce3c0881b3b42b01`。
- 清单`EXPERIMENT_MANIFEST.json`固定34项材料身份，含输入/预览/配置、相关代码、安装入口及环境来源、观察方案。初版清单另存MANIFEST_REVISION_01；只使用上述当前摘要。

完整实验根（保留到审批后）：

`C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a`

| 用途 | 实际绝对路径 |
|---|---|
| 输入 | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\engineering\axial_bar.inp` |
| submission_cwd | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\engineering` |
| scratch | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\engineering\scratch` |
| 原始观察 | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\observations` |
| 独立提取 | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\extracted` |
| 待批清单 | `C:\Users\wuxia\AppData\Local\Temp\AbqJobPilot_Run010_a19d17ea5ea74540a9cbd1db34261b0a\materials\experiment_manifest.json` |

## 2. Runtime实据与未验证事实

Dev配置指向 `D:\ABAQUS2024\Commands\abq2024.bat`。实际BAT先调用Intel oneAPI环境脚本，再调用 `D:\ABAQUS2024\product\win_b64\code\bin\SMALauncher.exe`。安装登记声明Established Products2024；PE版本6.426.0.23224。只读确认参数表和内存MB说明；没有用信息命令补验。

已知风险：所选BAT的Intel前置步骤查找的三处默认VS2022 vcvarsall路径不存在；显式子进程环境不继承当前shell的VS设置，前置步骤可能报错，BAT没有errorlevel阻止后续native调用。没有用户子程序，未改环境或换入口；必须在批准时看见这个风险。若实际未进入Standard，本次只记录失败，不修复后再跑。

2024在线关键词手册仍未取得，2025参考与本地2024静态材料分开标记。具体2024输入接受、运行时环境/许可证、包装器行为、真实必需成员集合、退出与日志/数值版式都只能在实际实验取得。它们是此次实验拟回答的未知，不能把已有固定Python夹具验收替代进来。准备方案没有新的已知致命模型/入口缺口；仍需用户对当前清单和这些风险的另行授权。

## 3. 代码与契约变化

只修改离线inputs/preview模块和原公开离线示例：新独立档案`windows-standard-axial-print-v1`，仅支持固定NODE PRINT(U/RF)及EL PRINT(S)。原Run009默认档案、ExecutionPlan摘要/授权/执行/恢复语义均保持。新增只读`abaqus_probe_review.py`与21项针对性测试。前轮51项源码/测试初始匹配，其中48项仍逐字节不变；未清理、提交或回滚前轮成果。

没有真实Backend、真实Grant、批准布尔解锁、生产Project/DB、正式Run、队列或事件写入。包复核成功只代表读取时未变；不能保留未来输出或资源，也不能替代执行前最新检查和用户授权。

## 4. 实际验证与清理

登记解释器Python3.12.10，Windows11 10.0.26300，pytest9.1.0；最终 **204 passed，0 failed，0 skipped，28.38s**。范围为全部R9离线与IPC拒绝组、执行/固定进程授权契约、新输出及包复核组。没有机械重跑452项，也没有运行真实Solver或无关GUI测试。

第一轮198通过5失败已保留并修复：4项新测试的错误消息匹配方式、1项旧默认内部调用的关键字兼容。随后203通过；完整包复核暴露cmd.exe合法NTFS硬链接，区分安装材料摘要检查与不变的INP严格路径后，新增回归并取得204通过。原测试断言没有删改。最终非仓库cwd公开prepare/export和只读包复核都有真实进程及文件不变证据。

三轮测试合计3个Fake Supervisor生命周期记录、6次普通离线客户端调用，均通过原受控harness退出；保留包的公开prepare和最终复核客户端也已退出并关闭句柄。另一次失败包复核返回2且finally关闭了句柄，但控制脚本未保存它的PID，此证据限制在PROCESS_AND_CLEANUP_EVIDENCE中明确记录。没有任何测试进程按名称被杀；没有启动固定测试worker或Abaqus。

IPC私有材料已由harness删除并核验不残留。**测试文件清理未完成**：带路径核验的批量清理及改用三个完整LiteralPath的清理，都在执行前被自动审批拒绝，仅返回`blocked by policy`。未换工具绕过。`offline_tests`、`offline_tests_final`、`offline_tests_release`与5个中间脚本保留在本轮根内；不含活动进程。此项使R10-07/本轮整体标PARTIAL。待批准的engineering/materials等目录必须保留，不要整根删除。

## 5. 待批准的唯一真实调用

批准请求：是否批准 **abq2024_r010_a19d17ea**、摘要 **04ed053817a7d05c2355d9a93a41216309bb5d28a235f569a250eea6ee4af2b6** 所固定的这一次实验？

- 入口：`D:\ABAQUS2024\Commands\abq2024.bat`，由绝对`C:\Windows\System32\cmd.exe /d /s /c`解释；固定command_line/子进程环境/cwd见manifest。
- 输入、cwd、scratch和结果目录均为第1节已填实的本轮隔离路径。Job=`r010_bar_a19d17ea`，必须拒绝复用已有同名输出；材料/输入/环境策略变更必须重新审查。
- 动作：**一次analysis**，Standard、interactive、CPU=1、GPU=0、memory="2048 mb"；**额外Abaqus调用0次**。普通Python/只读文本工具核对DAT，不调用Abaqus Python/Viewer/CAE。
- 观察上限300秒，含启动和许可等待。超时只停止等待并报告不确定；**不自动终止、不重试、不修正输入再运行、不删除可能使用中的输出/scratch**。停止命令不在批准范围内。
- 结果分别记录版本/阶段、已取得的OS退出事实与集合未知、本次Artifact身份、数值验证和资源释放；不得以launcher exit0、ODB存在或单行成功文字代替。

需要这一确认，是因为用户明确要求**实验包完成后另行授权，未经授权不得调用真实Abaqus**。本轮停在请求之前的准备交付，不因该文字或manifest字段自动执行。真实人类审批产品机制、长期Runner、自动接管/恢复/Retry、跨Project资源保护、Abaqus Backend与正式0.3.0均未验收。

## 6. 后续边界

本轮没有执行Stable访问、Git写操作、生产数据修改、安装/许可/全局环境修改、版本调整或真实Abaqus调用。当前只需要审查本清单并处理明确保留的测试文件清理；没有自动开始下一Run。即使之后批准，首次实验也只能使用当前清单的一次调用预算；新增探测、停止动作、输入修正或第二次运行须另行明确范围。
